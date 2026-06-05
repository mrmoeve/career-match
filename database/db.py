import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover - optional until installed
    psycopg = None
    dict_row = None


DB_PATH = Path(__file__).resolve().parent / "applications.db"
LOGGER_NAME = "career_match"
_ENGINE_LOGGED = False


@dataclass
class ApplicationRecord:
    user_email: str = ""
    created_at: str = ""
    original_resume_text: str = ""
    optimized_resume_text: str = ""
    original_ats_score: int = 0
    optimized_ats_score: int = 0
    company_name: str = ""
    job_title: str = ""
    job_url: str = ""
    job_location: str = ""
    job_date_posted: str = ""
    job_category: str = ""
    resume_text: str = ""
    job_description_text: str = ""
    ats_score: int = 0
    payment_type_used: str = "free"
    is_admin_test: int = 0
    payload_json: str = ""


@dataclass
class UserRecord:
    id: int = 0
    created_at: str = ""
    updated_at: str = ""
    email: str = ""
    password_hash: str = ""
    full_name: str = ""
    subscription_status: str = "free"
    subscription_plan: str = "free"
    subscription_start: str = ""
    subscription_end: str = ""
    free_assessments_used: int = 0
    free_assessments_limit: int = 1
    assessment_credits: int = 0
    stripe_customer_id: str = ""
    stripe_subscription_id: str = ""
    email_verified: int = 0
    is_admin: int = 0


@dataclass
class PasswordResetToken:
    email: str = ""
    token: str = ""
    expires_at: str = ""


@dataclass
class ContactSubmission:
    created_at: str = ""
    user_id: int = 0
    user_email: str = ""
    name: str = ""
    message_type: str = ""
    message: str = ""
    status: str = "new"


@dataclass
class AnalysisFeedback:
    created_at: str = ""
    user_email: str = ""
    user_id: int = 0
    application_id: int = 0
    rating: str = ""
    comment: str = ""


@dataclass
class PaymentRecord:
    user_id: int = 0
    stripe_session_id: str = ""
    stripe_payment_intent: str = ""
    amount: int = 0
    currency: str = "usd"
    product_type: str = ""
    status: str = ""
    created_at: str = ""


@dataclass
class PageViewRecord:
    created_at: str = ""
    user_id: int = 0
    user_email: str = ""
    session_id: str = ""
    view_name: str = ""
    app_page: str = ""


@dataclass
class AffiliateClickRecord:
    user_email: str = ""
    assessment_id: int = 0
    recommendation_name: str = ""
    recommendation_category: str = ""
    provider: str = ""
    affiliate_url: str = ""
    clicked_at: str = ""


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _database_engine() -> str:
    url = _database_url().lower()
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        return "postgresql"
    return "sqlite"


def _postgres_url() -> str:
    url = _database_url()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def _log_engine_once() -> None:
    global _ENGINE_LOGGED
    if _ENGINE_LOGGED:
        return
    engine = _database_engine()
    if engine == "postgresql":
        parsed = urlparse(_postgres_url())
        target = parsed.hostname or "postgres-host"
        _logger().info("Database engine active: postgresql (%s)", target)
    else:
        _logger().info("Database engine active: sqlite (%s)", DB_PATH.name)
    _ENGINE_LOGGED = True


def get_database_diagnostics() -> dict:
    engine = _database_engine()
    diagnostics = {"engine": engine, "postgres_configured": engine == "postgresql"}
    if engine == "postgresql":
        parsed = urlparse(_postgres_url())
        diagnostics["target"] = parsed.hostname or "postgres-host"
    else:
        diagnostics["target"] = str(DB_PATH)
    return diagnostics


def _connect():
    _log_engine_once()
    if _database_engine() == "postgresql":
        if not psycopg:
            raise RuntimeError("DATABASE_URL is set for PostgreSQL, but psycopg is not installed.")
        return psycopg.connect(_postgres_url(), row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _adapt_sql(query: str) -> str:
    if _database_engine() == "postgresql":
        return query.replace("?", "%s")
    return query


def _execute(conn, query: str, params: tuple = ()):
    return conn.execute(_adapt_sql(query), params)


def _fetchone_dict(conn, query: str, params: tuple = ()) -> dict | None:
    row = _execute(conn, query, params).fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def _fetchall_dicts(conn, query: str, params: tuple = ()) -> list[dict]:
    rows = _execute(conn, query, params).fetchall()
    return [dict(row) if not isinstance(row, dict) else dict(row) for row in rows]


def _scalar(conn, query: str, params: tuple = (), default=0):
    row = _execute(conn, query, params).fetchone()
    if row is None:
        return default
    if isinstance(row, dict):
        values = list(row.values())
        return values[0] if values else default
    return row[0]


def _insert_and_get_id(conn, query: str, params: tuple, id_column: str) -> int:
    if _database_engine() == "postgresql":
        cursor = _execute(conn, f"{query.rstrip()} RETURNING {id_column}", params)
        value = cursor.fetchone()
        if isinstance(value, dict):
            return int(value[id_column])
        return int(value[0])
    cursor = _execute(conn, query, params)
    return int(cursor.lastrowid)


def _table_columns(conn, table_name: str) -> set[str]:
    if _database_engine() == "postgresql":
        rows = _execute(
            conn,
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table_name,),
        ).fetchall()
        return {row["column_name"] if isinstance(row, dict) else row[0] for row in rows}
    rows = _execute(conn, f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(conn, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        _execute(conn, f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _run_admin_migration_once(conn, emails: list[str] | tuple[str, ...] | set[str] | None = None) -> None:
    targets = emails or ["mrmoeve@gmail.com"]
    for email in targets:
        normalized_email = _normalize_email(email)
        _logger().info(
            "Running bootstrap admin migration. engine=%s target_email=%s",
            _database_engine(),
            normalized_email,
        )
        result = _execute(
            conn,
            """
            UPDATE users
            SET is_admin = 1, updated_at = ?
            WHERE email = ? AND COALESCE(is_admin, 0) <> 1
            """,
            (_now(), normalized_email),
        )
        if getattr(result, "rowcount", 0):
            _logger().info("Admin migration completed for %s", normalized_email)
        current_row = _fetchone_dict(
            conn,
            "SELECT email, COALESCE(is_admin, 0) AS is_admin FROM users WHERE email = ?",
            (normalized_email,),
        )
        _logger().info(
            "Bootstrap admin verification. engine=%s email=%s is_admin=%s found=%s",
            _database_engine(),
            normalized_email,
            (current_row or {}).get("is_admin", 0),
            bool(current_row),
        )


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{iterations}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        iterations_str, salt_hex, digest_hex = password_hash.split("$", 2)
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
    except (TypeError, ValueError):
        return False
    candidate_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate_digest, expected_digest)


def test_database_connection() -> tuple[bool, str]:
    try:
        conn = _connect()
        try:
            _scalar(conn, "SELECT 1", default=1)
            return True, _database_engine()
        finally:
            conn.close()
    except Exception as exc:
        return False, str(exc)


def init_db() -> None:
    conn = _connect()
    try:
        if _database_engine() == "postgresql":
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    subscription_status TEXT NOT NULL DEFAULT 'free',
                    subscription_plan TEXT NOT NULL DEFAULT 'free',
                    subscription_start TEXT NOT NULL DEFAULT '',
                    subscription_end TEXT NOT NULL DEFAULT '',
                    free_assessments_used INTEGER NOT NULL DEFAULT 0,
                    free_assessments_limit INTEGER NOT NULL DEFAULT 1,
                    assessment_credits INTEGER NOT NULL DEFAULT 0,
                    stripe_customer_id TEXT NOT NULL DEFAULT '',
                    stripe_subscription_id TEXT NOT NULL DEFAULT '',
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    is_admin INTEGER NOT NULL DEFAULT 0
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    email TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS email_verification_tokens (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    email TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS contact_messages (
                    message_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    user_email TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    message_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new'
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS analysis_feedback (
                    feedback_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    user_email TEXT NOT NULL DEFAULT '',
                    user_id INTEGER NOT NULL DEFAULT 0,
                    application_id INTEGER NOT NULL,
                    rating TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT ''
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS saved_resumes (
                    resume_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    resume_name TEXT NOT NULL DEFAULT '',
                    resume_type TEXT NOT NULL DEFAULT '',
                    original_filename TEXT NOT NULL DEFAULT '',
                    extracted_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    last_used_at TEXT NOT NULL DEFAULT ''
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    stripe_session_id TEXT NOT NULL DEFAULT '',
                    stripe_payment_intent TEXT NOT NULL DEFAULT '',
                    amount INTEGER NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'usd',
                    product_type TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS page_views (
                    view_id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    user_email TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL DEFAULT '',
                    view_name TEXT NOT NULL DEFAULT '',
                    app_page TEXT NOT NULL DEFAULT ''
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS affiliate_clicks (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    user_email TEXT NOT NULL DEFAULT '',
                    assessment_id INTEGER NOT NULL DEFAULT 0,
                    recommendation_name TEXT NOT NULL DEFAULT '',
                    recommendation_category TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    affiliate_url TEXT NOT NULL DEFAULT '',
                    clicked_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                    user_email TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    original_resume_text TEXT NOT NULL DEFAULT '',
                    optimized_resume_text TEXT NOT NULL DEFAULT '',
                    original_ats_score INTEGER NOT NULL DEFAULT 0,
                    optimized_ats_score INTEGER NOT NULL DEFAULT 0,
                    company_name TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    job_url TEXT NOT NULL DEFAULT '',
                    job_location TEXT NOT NULL DEFAULT '',
                    job_date_posted TEXT NOT NULL DEFAULT '',
                    job_category TEXT NOT NULL DEFAULT '',
                    resume_text TEXT NOT NULL,
                    job_description_text TEXT NOT NULL,
                    ats_score INTEGER NOT NULL,
                    payment_type_used TEXT NOT NULL DEFAULT 'free',
                    is_admin_test INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL
                )
                """,
            )
        else:
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL DEFAULT '',
                    subscription_status TEXT NOT NULL DEFAULT 'free',
                    subscription_plan TEXT NOT NULL DEFAULT 'free',
                    subscription_start TEXT NOT NULL DEFAULT '',
                    subscription_end TEXT NOT NULL DEFAULT '',
                    free_assessments_used INTEGER NOT NULL DEFAULT 0,
                    free_assessments_limit INTEGER NOT NULL DEFAULT 1,
                    assessment_credits INTEGER NOT NULL DEFAULT 0,
                    stripe_customer_id TEXT DEFAULT '',
                    stripe_subscription_id TEXT DEFAULT '',
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    is_admin INTEGER NOT NULL DEFAULT 0
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS email_verification_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS contact_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    user_email TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    message_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new'
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS analysis_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    user_email TEXT NOT NULL DEFAULT '',
                    user_id INTEGER NOT NULL DEFAULT 0,
                    application_id INTEGER NOT NULL,
                    rating TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT ''
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS saved_resumes (
                    resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    resume_name TEXT NOT NULL DEFAULT '',
                    resume_type TEXT NOT NULL DEFAULT '',
                    original_filename TEXT NOT NULL DEFAULT '',
                    extracted_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    last_used_at TEXT NOT NULL DEFAULT ''
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    stripe_session_id TEXT NOT NULL DEFAULT '',
                    stripe_payment_intent TEXT NOT NULL DEFAULT '',
                    amount INTEGER NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'usd',
                    product_type TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS page_views (
                    view_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    user_id INTEGER NOT NULL DEFAULT 0,
                    user_email TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL DEFAULT '',
                    view_name TEXT NOT NULL DEFAULT '',
                    app_page TEXT NOT NULL DEFAULT ''
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS affiliate_clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT NOT NULL DEFAULT '',
                    assessment_id INTEGER NOT NULL DEFAULT 0,
                    recommendation_name TEXT NOT NULL DEFAULT '',
                    recommendation_category TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    affiliate_url TEXT NOT NULL DEFAULT '',
                    clicked_at TEXT NOT NULL
                )
                """,
            )
            _execute(
                conn,
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    original_resume_text TEXT NOT NULL DEFAULT '',
                    optimized_resume_text TEXT NOT NULL DEFAULT '',
                    original_ats_score INTEGER NOT NULL DEFAULT 0,
                    optimized_ats_score INTEGER NOT NULL DEFAULT 0,
                    company_name TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    job_url TEXT NOT NULL DEFAULT '',
                    job_location TEXT NOT NULL DEFAULT '',
                    job_date_posted TEXT NOT NULL DEFAULT '',
                    job_category TEXT NOT NULL DEFAULT '',
                    resume_text TEXT NOT NULL,
                    job_description_text TEXT NOT NULL,
                    ats_score INTEGER NOT NULL,
                    payment_type_used TEXT NOT NULL DEFAULT 'free',
                    is_admin_test INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL
                )
                """,
            )

        _add_column_if_missing(conn, "users", "full_name", "full_name TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "updated_at", "updated_at TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "subscription_status", "subscription_status TEXT NOT NULL DEFAULT 'free'")
        _add_column_if_missing(conn, "users", "subscription_plan", "subscription_plan TEXT NOT NULL DEFAULT 'free'")
        _add_column_if_missing(conn, "users", "subscription_start", "subscription_start TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "subscription_end", "subscription_end TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "free_assessments_used", "free_assessments_used INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "users", "free_assessments_limit", "free_assessments_limit INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "users", "assessment_credits", "assessment_credits INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "users", "stripe_customer_id", "stripe_customer_id TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "stripe_subscription_id", "stripe_subscription_id TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "users", "email_verified", "email_verified INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "users", "is_admin", "is_admin INTEGER NOT NULL DEFAULT 0")

        _add_column_if_missing(conn, "analysis_feedback", "user_id", "user_id INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "analysis_feedback", "rating", "rating TEXT NOT NULL DEFAULT ''")

        _add_column_if_missing(conn, "saved_resumes", "resume_type", "resume_type TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "saved_resumes", "updated_at", "updated_at TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "saved_resumes", "last_used_at", "last_used_at TEXT NOT NULL DEFAULT ''")

        _add_column_if_missing(conn, "page_views", "user_id", "user_id INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "page_views", "user_email", "user_email TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "page_views", "session_id", "session_id TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "page_views", "view_name", "view_name TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "page_views", "app_page", "app_page TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "affiliate_clicks", "user_email", "user_email TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "affiliate_clicks", "assessment_id", "assessment_id INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "affiliate_clicks", "recommendation_name", "recommendation_name TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "affiliate_clicks", "recommendation_category", "recommendation_category TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "affiliate_clicks", "provider", "provider TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "affiliate_clicks", "affiliate_url", "affiliate_url TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "affiliate_clicks", "clicked_at", "clicked_at TEXT NOT NULL DEFAULT ''")

        _add_column_if_missing(conn, "applications", "user_email", "user_email TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "applications", "job_url", "job_url TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "applications", "original_resume_text", "original_resume_text TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "applications", "optimized_resume_text", "optimized_resume_text TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "applications", "original_ats_score", "original_ats_score INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "applications", "optimized_ats_score", "optimized_ats_score INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "applications", "job_location", "job_location TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "applications", "job_date_posted", "job_date_posted TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "applications", "job_category", "job_category TEXT NOT NULL DEFAULT ''")
        _add_column_if_missing(conn, "applications", "payment_type_used", "payment_type_used TEXT NOT NULL DEFAULT 'free'")
        _add_column_if_missing(conn, "applications", "is_admin_test", "is_admin_test INTEGER NOT NULL DEFAULT 0")
        _run_admin_migration_once(conn, ["mrmoeve@gmail.com", "talisa.salvador@gmail.com"])
        conn.commit()
    finally:
        conn.close()


def create_user(created_at: str, email: str, password: str, full_name: str = "", is_admin: bool = False) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return False, "Enter an email address."
    if len(password or "") < 8:
        return False, "Use a password with at least 8 characters."
    conn = _connect()
    try:
        existing = _scalar(conn, "SELECT id FROM users WHERE email = ?", (normalized_email,), default=None)
        if existing:
            return False, "An account with that email already exists."
        _execute(
            conn,
            """
            INSERT INTO users (
                created_at, updated_at, email, password_hash, full_name, subscription_status,
                subscription_plan, free_assessments_used, free_assessments_limit, assessment_credits,
                stripe_customer_id, stripe_subscription_id, email_verified, is_admin
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_at,
                created_at,
                normalized_email,
                _hash_password(password),
                (full_name or "").strip(),
                "free",
                "free",
                0,
                1,
                0,
                "",
                "",
                0,
                1 if is_admin else 0,
            ),
        )
        conn.commit()
        return True, normalized_email
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        row = _fetchone_dict(
            conn,
            """
            SELECT id, created_at, email, password_hash
            FROM users
            WHERE email = ?
            """,
            (normalized_email,),
        )
        if not row:
            return False, "We couldn't find an account with that email."
        if not _verify_password(password, row["password_hash"]):
            return False, "The password you entered is incorrect."
        return True, row["email"]
    finally:
        conn.close()


def get_user_profile(email: str) -> dict | None:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        return _fetchone_dict(
            conn,
            """
            SELECT id, created_at, updated_at, email, full_name, subscription_status, subscription_plan,
                   subscription_start, subscription_end, free_assessments_used, free_assessments_limit,
                   assessment_credits, stripe_customer_id, stripe_subscription_id, email_verified, is_admin
            FROM users
            WHERE email = ?
            """,
            (normalized_email,),
        )
    finally:
        conn.close()


def get_user_profile_by_id(user_id: int) -> dict | None:
    conn = _connect()
    try:
        return _fetchone_dict(
            conn,
            """
            SELECT id, created_at, updated_at, email, full_name, subscription_status, subscription_plan,
                   subscription_start, subscription_end, free_assessments_used, free_assessments_limit,
                   assessment_credits, stripe_customer_id, stripe_subscription_id, email_verified, is_admin
            FROM users
            WHERE id = ?
            """,
            (int(user_id),),
        )
    finally:
        conn.close()


def get_user_profile_by_stripe_customer_id(stripe_customer_id: str) -> dict | None:
    conn = _connect()
    try:
        return _fetchone_dict(
            conn,
            """
            SELECT id, created_at, updated_at, email, full_name, subscription_status, subscription_plan,
                   subscription_start, subscription_end, free_assessments_used, free_assessments_limit,
                   assessment_credits, stripe_customer_id, stripe_subscription_id, email_verified, is_admin
            FROM users
            WHERE stripe_customer_id = ?
            """,
            (((stripe_customer_id or "").strip()),),
        )
    finally:
        conn.close()


def get_user_profile_by_stripe_subscription_id(stripe_subscription_id: str) -> dict | None:
    conn = _connect()
    try:
        return _fetchone_dict(
            conn,
            """
            SELECT id, created_at, updated_at, email, full_name, subscription_status, subscription_plan,
                   subscription_start, subscription_end, free_assessments_used, free_assessments_limit,
                   assessment_credits, stripe_customer_id, stripe_subscription_id, email_verified, is_admin
            FROM users
            WHERE stripe_subscription_id = ?
            """,
            (((stripe_subscription_id or "").strip()),),
        )
    finally:
        conn.close()


def update_user_profile(email: str, full_name: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        result = _execute(
            conn,
            "UPDATE users SET full_name = ?, updated_at = ? WHERE email = ?",
            ((full_name or "").strip(), _now(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Profile updated."
    finally:
        conn.close()


def get_user_id(email: str) -> int:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        value = _scalar(conn, "SELECT id FROM users WHERE email = ?", (normalized_email,), default=0)
        return int(value or 0)
    finally:
        conn.close()


def get_assessment_access(email: str) -> dict:
    profile = get_user_profile(email) or {}
    used = int(profile.get("free_assessments_used", 0))
    limit = int(profile.get("free_assessments_limit", 1))
    credits = int(profile.get("assessment_credits", 0))
    subscription_status = (profile.get("subscription_status", "free") or "free").lower()
    subscription_plan = (profile.get("subscription_plan", "free") or "free").lower()
    is_pro = subscription_status in {"pro", "active", "paid", "trialing"} or subscription_plan == "pro"
    remaining = max(limit - used, 0)
    current_plan_label = "Pro" if is_pro else ("One-Time Credits" if credits > 0 else "Free")
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "credits": credits,
        "subscription_status": subscription_status,
        "subscription_plan": subscription_plan,
        "is_pro": is_pro,
        "current_plan_label": current_plan_label,
        "can_run_analysis": is_pro or credits > 0 or remaining > 0,
    }


def increment_free_assessment_usage(email: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    access = get_assessment_access(normalized_email)
    if access["is_pro"]:
        return True, "Pro user does not consume free assessments."
    if access["remaining"] <= 0:
        return False, "Free assessment limit reached."
    conn = _connect()
    try:
        _execute(
            conn,
            """
            UPDATE users
            SET free_assessments_used = free_assessments_used + 1, updated_at = ?
            WHERE email = ?
            """,
            (_now(), normalized_email),
        )
        conn.commit()
        return True, "Free assessment usage updated."
    finally:
        conn.close()


def consume_assessment_credit(email: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    access = get_assessment_access(normalized_email)
    if access["is_pro"]:
        return True, "Pro user does not consume credits."
    if access["credits"] <= 0:
        return False, "No assessment credits available."
    conn = _connect()
    try:
        _execute(
            conn,
            """
            UPDATE users
            SET assessment_credits = CASE WHEN assessment_credits > 0 THEN assessment_credits - 1 ELSE 0 END,
                updated_at = ?
            WHERE email = ?
            """,
            (_now(), normalized_email),
        )
        conn.commit()
        return True, "Assessment credit consumed."
    finally:
        conn.close()


def add_assessment_credits(email: str, credits: int) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        result = _execute(
            conn,
            """
            UPDATE users
            SET assessment_credits = assessment_credits + ?, updated_at = ?
            WHERE email = ?
            """,
            (max(int(credits), 0), _now(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Assessment credits added."
    finally:
        conn.close()


def set_subscription_status(email: str, subscription_status: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        result = _execute(
            conn,
            "UPDATE users SET subscription_status = ?, updated_at = ? WHERE email = ?",
            (((subscription_status or "free").strip().lower()), _now(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Subscription status updated."
    finally:
        conn.close()


def set_user_admin(email: str, is_admin: bool = True) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        result = _execute(
            conn,
            "UPDATE users SET is_admin = ?, updated_at = ? WHERE email = ?",
            (1 if is_admin else 0, _now(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Admin access updated."
    finally:
        conn.close()


def set_subscription_plan(
    email: str,
    subscription_status: str,
    subscription_plan: str,
    subscription_start: str = "",
    subscription_end: str = "",
) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        result = _execute(
            conn,
            """
            UPDATE users
            SET subscription_status = ?, subscription_plan = ?, subscription_start = ?, subscription_end = ?, updated_at = ?
            WHERE email = ?
            """,
            (
                (subscription_status or "free").strip().lower(),
                (subscription_plan or "free").strip().lower(),
                (subscription_start or "").strip(),
                (subscription_end or "").strip(),
                _now(),
                normalized_email,
            ),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Subscription plan updated."
    finally:
        conn.close()


def set_stripe_customer_details(email: str, stripe_customer_id: str = "", stripe_subscription_id: str = "") -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        result = _execute(
            conn,
            """
            UPDATE users
            SET stripe_customer_id = ?, stripe_subscription_id = ?, updated_at = ?
            WHERE email = ?
            """,
            (((stripe_customer_id or "").strip()), ((stripe_subscription_id or "").strip()), _now(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Stripe details updated."
    finally:
        conn.close()


def create_password_reset_token(email: str, expires_at: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        user = _scalar(conn, "SELECT 1 FROM users WHERE email = ?", (normalized_email,), default=None)
        if not user:
            return False, "We couldn't find an account with that email."
        token = secrets.token_urlsafe(24)
        _execute(conn, "DELETE FROM password_reset_tokens WHERE email = ?", (normalized_email,))
        _execute(
            conn,
            "INSERT INTO password_reset_tokens (email, token, expires_at) VALUES (?, ?, ?)",
            (normalized_email, token, expires_at),
        )
        conn.commit()
        return True, token
    finally:
        conn.close()


def create_email_verification_token(email: str, expires_at: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = _connect()
    try:
        user = _scalar(conn, "SELECT 1 FROM users WHERE email = ?", (normalized_email,), default=None)
        if not user:
            return False, "We couldn't find an account with that email."
        token = secrets.token_urlsafe(24)
        _execute(conn, "DELETE FROM email_verification_tokens WHERE email = ?", (normalized_email,))
        _execute(
            conn,
            "INSERT INTO email_verification_tokens (email, token, expires_at) VALUES (?, ?, ?)",
            (normalized_email, token, expires_at),
        )
        conn.commit()
        return True, token
    finally:
        conn.close()


def consume_email_verification_token(token: str, current_time: str) -> tuple[bool, str]:
    conn = _connect()
    try:
        row = _fetchone_dict(
            conn,
            "SELECT email, token, expires_at FROM email_verification_tokens WHERE token = ?",
            (((token or "").strip()),),
        )
        if not row:
            return False, "That verification token is not valid."
        if row["expires_at"] < current_time:
            _execute(conn, "DELETE FROM email_verification_tokens WHERE token = ?", (row["token"],))
            conn.commit()
            return False, "That verification token has expired."
        _execute(conn, "UPDATE users SET email_verified = 1, updated_at = ? WHERE email = ?", (_now(), row["email"]))
        _execute(conn, "DELETE FROM email_verification_tokens WHERE email = ?", (row["email"],))
        conn.commit()
        return True, "Email verified."
    finally:
        conn.close()


def consume_password_reset_token(token: str, new_password: str, current_time: str) -> tuple[bool, str]:
    if len(new_password or "") < 8:
        return False, "Use a password with at least 8 characters."
    conn = _connect()
    try:
        row = _fetchone_dict(
            conn,
            "SELECT email, token, expires_at FROM password_reset_tokens WHERE token = ?",
            (((token or "").strip()),),
        )
        if not row:
            return False, "That reset token is not valid."
        if row["expires_at"] < current_time:
            _execute(conn, "DELETE FROM password_reset_tokens WHERE token = ?", (row["token"],))
            conn.commit()
            return False, "That reset token has expired."
        _execute(conn, "UPDATE users SET password_hash = ?, updated_at = ? WHERE email = ?", (_hash_password(new_password), _now(), row["email"]))
        _execute(conn, "DELETE FROM password_reset_tokens WHERE email = ?", (row["email"],))
        conn.commit()
        return True, "Password updated."
    finally:
        conn.close()


def save_application(record: ApplicationRecord) -> int:
    conn = _connect()
    try:
        application_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO applications (
                user_email, created_at, original_resume_text, optimized_resume_text,
                original_ats_score, optimized_ats_score, company_name, job_title, job_url,
                job_location, job_date_posted, job_category, resume_text, job_description_text,
                ats_score, payment_type_used, is_admin_test, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                getattr(record, "user_email", ""),
                record.created_at,
                record.original_resume_text,
                record.optimized_resume_text,
                record.original_ats_score,
                record.optimized_ats_score,
                record.company_name,
                record.job_title,
                record.job_url,
                record.job_location,
                record.job_date_posted,
                record.job_category,
                record.resume_text,
                record.job_description_text,
                record.ats_score,
                getattr(record, "payment_type_used", "free"),
                int(getattr(record, "is_admin_test", 0) or 0),
                record.payload_json,
            ),
            "id",
        )
        conn.commit()
        return application_id
    finally:
        conn.close()


def list_applications(limit: int = 20, user_email: str = "") -> list[dict]:
    conn = _connect()
    try:
        normalized_email = _normalize_email(user_email)
        if normalized_email:
            return _fetchall_dicts(
                conn,
                """
                SELECT id, user_email, created_at, company_name, job_title, job_url, job_location, job_date_posted, job_category,
                       ats_score, original_ats_score, optimized_ats_score, payment_type_used, is_admin_test, payload_json,
                       original_resume_text, optimized_resume_text, resume_text, job_description_text
                FROM applications
                WHERE user_email = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (normalized_email, limit),
            )
        return _fetchall_dicts(
            conn,
            """
            SELECT id, user_email, created_at, company_name, job_title, job_url, job_location, job_date_posted, job_category,
                   ats_score, original_ats_score, optimized_ats_score, payment_type_used, is_admin_test, payload_json,
                   original_resume_text, optimized_resume_text, resume_text, job_description_text
            FROM applications
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
    finally:
        conn.close()


def get_dashboard_metrics(user_email: str) -> dict:
    normalized_email = _normalize_email(user_email)
    conn = _connect()
    try:
        access = get_assessment_access(normalized_email)
        profile = get_user_profile(normalized_email) or {}
        items = _fetchall_dicts(
            conn,
            """
            SELECT job_title, company_name, job_location, created_at, ats_score, original_ats_score, optimized_ats_score, payment_type_used
            FROM applications
            WHERE user_email = ?
            ORDER BY id DESC
            """,
            (normalized_email,),
        )
        fit_scores = [int(item.get("ats_score", 0)) for item in items]
        return {
            "recent_analyses": items[:5],
            "average_fit_score": round(sum(fit_scores) / len(fit_scores)) if fit_scores else 0,
            "best_fit_score": max(fit_scores) if fit_scores else 0,
            "jobs_analyzed": len(items),
            "free_assessments_used": access["used"],
            "free_assessments_remaining": access["remaining"],
            "free_assessments_limit": access["limit"],
            "assessment_credits": access["credits"],
            "current_plan": access["current_plan_label"],
            "subscription_status": profile.get("subscription_status", "free"),
            "renewal_date": profile.get("subscription_end", ""),
        }
    finally:
        conn.close()


def save_payment_record(payment: PaymentRecord) -> int:
    conn = _connect()
    try:
        payment_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO payments (
                user_id, stripe_session_id, stripe_payment_intent, amount, currency, product_type, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payment.user_id,
                payment.stripe_session_id,
                payment.stripe_payment_intent,
                payment.amount,
                payment.currency,
                payment.product_type,
                payment.status,
                payment.created_at,
            ),
            "payment_id",
        )
        conn.commit()
        return payment_id
    finally:
        conn.close()


def save_page_view(view: PageViewRecord) -> int:
    conn = _connect()
    try:
        view_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO page_views (created_at, user_id, user_email, session_id, view_name, app_page)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                view.created_at,
                int(view.user_id or 0),
                _normalize_email(view.user_email),
                (view.session_id or "").strip(),
                (view.view_name or "").strip(),
                (view.app_page or "").strip(),
            ),
            "view_id",
        )
        conn.commit()
        return view_id
    finally:
        conn.close()


def count_page_views(limit_days: int = 30) -> int:
    threshold = datetime.now().replace(microsecond=0).isoformat(timespec="seconds")
    if limit_days > 0:
        from datetime import timedelta

        threshold = (datetime.now() - timedelta(days=limit_days)).replace(microsecond=0).isoformat(timespec="seconds")
    conn = _connect()
    try:
        return int(_scalar(conn, "SELECT COUNT(*) FROM page_views WHERE created_at >= ?", (threshold,), default=0) or 0)
    finally:
        conn.close()


def get_latest_payment_for_user(user_id: int) -> dict | None:
    conn = _connect()
    try:
        return _fetchone_dict(
            conn,
            """
            SELECT payment_id, user_id, stripe_session_id, stripe_payment_intent, amount, currency, product_type, status, created_at
            FROM payments
            WHERE user_id = ?
            ORDER BY payment_id DESC
            LIMIT 1
            """,
            (int(user_id),),
        )
    finally:
        conn.close()


def list_contact_messages(limit: int = 20) -> list[dict]:
    conn = _connect()
    try:
        return _fetchall_dicts(
            conn,
            """
            SELECT message_id, user_id, user_email, name, email, message_type, message, status, created_at
            FROM contact_messages
            ORDER BY message_id DESC
            LIMIT ?
            """,
            (limit,),
        )
    finally:
        conn.close()


def update_contact_message_status(message_id: int, status: str) -> tuple[bool, str]:
    normalized_status = (status or "").strip().lower()
    if normalized_status not in {"open", "closed"}:
        return False, "Status must be Open or Closed."
    conn = _connect()
    try:
        result = _execute(
            conn,
            "UPDATE contact_messages SET status = ? WHERE message_id = ?",
            (normalized_status, int(message_id)),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "Message not found."
        return True, "Message status updated."
    finally:
        conn.close()


def count_open_contact_messages() -> int:
    conn = _connect()
    try:
        return int(
            _scalar(
                conn,
                "SELECT COUNT(*) FROM contact_messages WHERE LOWER(COALESCE(status, 'new')) IN ('new', 'open')",
                default=0,
            )
            or 0
        )
    finally:
        conn.close()


def save_affiliate_click(record: AffiliateClickRecord) -> int:
    conn = _connect()
    try:
        click_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO affiliate_clicks (
                user_email, assessment_id, recommendation_name, recommendation_category,
                provider, affiliate_url, clicked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.user_email,
                int(record.assessment_id or 0),
                record.recommendation_name,
                record.recommendation_category,
                record.provider,
                record.affiliate_url,
                record.clicked_at,
            ),
            "id",
        )
        conn.commit()
        return click_id
    finally:
        conn.close()


def list_affiliate_clicks(limit: int = 25) -> list[dict]:
    conn = _connect()
    try:
        return _fetchall_dicts(
            conn,
            """
            SELECT id, user_email, assessment_id, recommendation_name, recommendation_category,
                   provider, affiliate_url, clicked_at
            FROM affiliate_clicks
            ORDER BY clicked_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )
    finally:
        conn.close()


def list_feedback(limit: int = 20) -> list[dict]:
    conn = _connect()
    try:
        return _fetchall_dicts(
            conn,
            """
            SELECT feedback_id, user_id, user_email, application_id, rating, comment, created_at
            FROM analysis_feedback
            ORDER BY feedback_id DESC
            LIMIT ?
            """,
            (limit,),
        )
    finally:
        conn.close()


def delete_application(user_email: str, application_id: int) -> tuple[bool, str]:
    normalized_email = _normalize_email(user_email)
    conn = _connect()
    try:
        result = _execute(conn, "DELETE FROM applications WHERE user_email = ? AND id = ?", (normalized_email, int(application_id)))
        conn.commit()
        if result.rowcount == 0:
            return False, "Analysis not found."
        return True, "Analysis deleted."
    finally:
        conn.close()


def admin_metrics() -> dict:
    conn = _connect()
    try:
        from datetime import timedelta

        now = datetime.now()
        recent_threshold = (datetime.now() - timedelta(days=30)).replace(microsecond=0).isoformat(timespec="seconds")
        affiliate_7d_threshold = (now - timedelta(days=7)).replace(microsecond=0).isoformat(timespec="seconds")
        affiliate_30d_threshold = (now - timedelta(days=30)).replace(microsecond=0).isoformat(timespec="seconds")
        total_users = int(_scalar(conn, "SELECT COUNT(*) FROM users", default=0) or 0)
        active_users = int(
            _scalar(
                conn,
                """
                SELECT COUNT(DISTINCT user_email)
                FROM page_views
                WHERE user_email <> '' AND created_at >= ?
                """,
                (recent_threshold,),
                default=0,
            )
            or 0
        )
        pro_users = int(
            _scalar(
                conn,
                "SELECT COUNT(*) FROM users WHERE subscription_plan = 'pro' OR subscription_status IN ('pro','active','paid','trialing')",
                default=0,
            )
            or 0
        )
        paid_users = int(
            _scalar(
                conn,
                """
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                LEFT JOIN payments p ON p.user_id = u.id AND p.amount > 0
                WHERE (u.subscription_plan = 'pro' OR u.subscription_status IN ('pro','active','paid','trialing'))
                   OR p.payment_id IS NOT NULL
                """,
                default=0,
            )
            or 0
        )
        totals = {
            "total_users": total_users,
            "active_users": active_users,
            "free_users": int(_scalar(conn, "SELECT COUNT(*) FROM users WHERE subscription_plan = 'free'", default=0) or 0),
            "paid_users": paid_users,
            "pro_users": pro_users,
            "registrations": total_users,
            "total_analyses": int(_scalar(conn, "SELECT COUNT(*) FROM applications", default=0) or 0),
            "completed_assessments": int(_scalar(conn, "SELECT COUNT(*) FROM applications WHERE COALESCE(is_admin_test, 0) = 0", default=0) or 0),
            "paid_assessments": int(_scalar(conn, "SELECT COUNT(*) FROM applications WHERE payment_type_used = 'credit'", default=0) or 0),
            "admin_test_analyses": int(_scalar(conn, "SELECT COUNT(*) FROM applications WHERE COALESCE(is_admin_test, 0) = 1", default=0) or 0),
            "page_views": int(_scalar(conn, "SELECT COUNT(*) FROM page_views", default=0) or 0),
            "total_affiliate_clicks": int(_scalar(conn, "SELECT COUNT(*) FROM affiliate_clicks", default=0) or 0),
            "affiliate_clicks_7d": int(_scalar(conn, "SELECT COUNT(*) FROM affiliate_clicks WHERE clicked_at >= ?", (affiliate_7d_threshold,), default=0) or 0),
            "affiliate_clicks_30d": int(_scalar(conn, "SELECT COUNT(*) FROM affiliate_clicks WHERE clicked_at >= ?", (affiliate_30d_threshold,), default=0) or 0),
            "total_contact_messages": int(_scalar(conn, "SELECT COUNT(*) FROM contact_messages", default=0) or 0),
            "open_contact_messages": int(
                _scalar(conn, "SELECT COUNT(*) FROM contact_messages WHERE LOWER(COALESCE(status, 'new')) IN ('new', 'open')", default=0) or 0
            ),
            "total_feedback_items": int(_scalar(conn, "SELECT COUNT(*) FROM analysis_feedback", default=0) or 0),
            "average_fit_score": int(_scalar(conn, "SELECT COALESCE(ROUND(AVG(ats_score)), 0) FROM applications", default=0) or 0),
        }
        totals["conversion_rate"] = round((paid_users / total_users) * 100, 1) if total_users else 0.0
        recent_contact = list_contact_messages(limit=5)
        recent_feedback = list_feedback(limit=5)
        recent_affiliate_clicks = list_affiliate_clicks(limit=10)
        missing_skills_counter: dict[str, int] = {}
        builder_gap_identified = 0
        builder_gap_addressed = 0
        builder_keywords_added = 0
        builder_keywords_rejected = 0
        builder_ats_before_total = 0
        builder_ats_after_total = 0
        builder_count = 0
        rows = _fetchall_dicts(conn, "SELECT payload_json FROM applications WHERE payload_json <> ''")
        for row in rows:
            payload_json = row.get("payload_json", "")
            try:
                import json as _json
                payload = _json.loads(payload_json)
            except Exception:
                continue
            analysis = payload.get("analysis", {})
            for item in analysis.get("missing_keywords", [])[:8]:
                missing_skills_counter[item] = missing_skills_counter.get(item, 0) + 1
            builder = (payload.get("generated", {}) or {}).get("resume_builder", {}) or {}
            analytics = builder.get("analytics", {}) or {}
            if analytics:
                builder_gap_identified += int(analytics.get("gaps_identified", 0) or 0)
                builder_gap_addressed += int(analytics.get("gaps_addressed", 0) or 0)
                builder_keywords_added += int(analytics.get("keywords_added", 0) or 0)
                builder_keywords_rejected += int(analytics.get("keywords_rejected_as_unsupported", 0) or 0)
                builder_ats_before_total += int(analytics.get("ats_before", 0) or 0)
                builder_ats_after_total += int(analytics.get("ats_after", 0) or 0)
                builder_count += 1
        most_common_missing = sorted(missing_skills_counter.items(), key=lambda item: item[1], reverse=True)[:10]
        top_clicked_recommendation_row = _fetchone_dict(
            conn,
            """
            SELECT recommendation_name, COUNT(*) AS click_count
            FROM affiliate_clicks
            GROUP BY recommendation_name
            ORDER BY click_count DESC, recommendation_name ASC
            LIMIT 1
            """,
        )
        top_clicked_category_row = _fetchone_dict(
            conn,
            """
            SELECT recommendation_category, COUNT(*) AS click_count
            FROM affiliate_clicks
            GROUP BY recommendation_category
            ORDER BY click_count DESC, recommendation_category ASC
            LIMIT 1
            """,
        )
        return {
            **totals,
            "recent_contact_messages": recent_contact,
            "recent_feedback": recent_feedback,
            "most_common_missing_skills": most_common_missing,
            "top_clicked_recommendation": (top_clicked_recommendation_row or {}).get("recommendation_name", ""),
            "top_clicked_category": (top_clicked_category_row or {}).get("recommendation_category", ""),
            "recent_affiliate_clicks": recent_affiliate_clicks,
            "resume_builder_gap_metrics": {
                "gaps_identified": builder_gap_identified,
                "gaps_addressed": builder_gap_addressed,
                "keywords_added": builder_keywords_added,
                "keywords_rejected": builder_keywords_rejected,
                "average_ats_before": round(builder_ats_before_total / builder_count) if builder_count else 0,
                "average_ats_after": round(builder_ats_after_total / builder_count) if builder_count else 0,
            },
        }
    finally:
        conn.close()


def save_contact_submission(submission: ContactSubmission) -> int:
    conn = _connect()
    try:
        message_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO contact_messages (created_at, user_id, user_email, name, email, message_type, message, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submission.created_at,
                submission.user_id,
                submission.user_email,
                submission.name,
                submission.user_email,
                submission.message_type,
                submission.message,
                submission.status,
            ),
            "message_id",
        )
        conn.commit()
        return message_id
    finally:
        conn.close()


def save_analysis_feedback(feedback: AnalysisFeedback) -> int:
    conn = _connect()
    try:
        feedback_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO analysis_feedback (created_at, user_email, user_id, application_id, rating, comment)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                feedback.created_at,
                feedback.user_email,
                feedback.user_id,
                feedback.application_id,
                feedback.rating,
                feedback.comment,
            ),
            "feedback_id",
        )
        conn.commit()
        return feedback_id
    finally:
        conn.close()


def save_resume_stub(user_email: str, resume_name: str, original_filename: str, extracted_text: str, created_at: str, resume_type: str = "") -> int:
    user_id = get_user_id(user_email)
    conn = _connect()
    try:
        resume_id = _insert_and_get_id(
            conn,
            """
            INSERT INTO saved_resumes (user_id, resume_name, resume_type, original_filename, extracted_text, created_at, updated_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                (resume_name or "").strip() or "Resume",
                (resume_type or "").strip(),
                (original_filename or "").strip(),
                extracted_text,
                created_at,
                created_at,
                created_at,
            ),
            "resume_id",
        )
        conn.commit()
        return resume_id
    finally:
        conn.close()


def list_saved_resumes(user_email: str) -> list[dict]:
    user_id = get_user_id(user_email)
    conn = _connect()
    try:
        return _fetchall_dicts(
            conn,
            """
            SELECT resume_id, user_id, resume_name, resume_type, original_filename, extracted_text, created_at, updated_at, last_used_at
            FROM saved_resumes
            WHERE user_id = ?
            ORDER BY resume_id DESC
            """,
            (user_id,),
        )
    finally:
        conn.close()


def get_saved_resume(user_email: str, resume_id: int) -> dict | None:
    user_id = get_user_id(user_email)
    conn = _connect()
    try:
        return _fetchone_dict(
            conn,
            """
            SELECT resume_id, user_id, resume_name, resume_type, original_filename, extracted_text, created_at, updated_at, last_used_at
            FROM saved_resumes
            WHERE user_id = ? AND resume_id = ?
            """,
            (user_id, int(resume_id)),
        )
    finally:
        conn.close()


def rename_saved_resume(user_email: str, resume_id: int, resume_name: str) -> tuple[bool, str]:
    user_id = get_user_id(user_email)
    conn = _connect()
    try:
        result = _execute(
            conn,
            """
            UPDATE saved_resumes
            SET resume_name = ?, updated_at = ?
            WHERE user_id = ? AND resume_id = ?
            """,
            (((resume_name or "").strip() or "Resume"), _now(), user_id, int(resume_id)),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "Saved resume not found."
        return True, "Resume renamed."
    finally:
        conn.close()


def delete_saved_resume(user_email: str, resume_id: int) -> tuple[bool, str]:
    user_id = get_user_id(user_email)
    conn = _connect()
    try:
        result = _execute(conn, "DELETE FROM saved_resumes WHERE user_id = ? AND resume_id = ?", (user_id, int(resume_id)))
        conn.commit()
        if result.rowcount == 0:
            return False, "Saved resume not found."
        return True, "Saved resume deleted."
    finally:
        conn.close()


def mark_saved_resume_used(user_email: str, resume_id: int) -> None:
    user_id = get_user_id(user_email)
    conn = _connect()
    try:
        _execute(
            conn,
            """
            UPDATE saved_resumes
            SET last_used_at = ?, updated_at = ?
            WHERE user_id = ? AND resume_id = ?
            """,
            (_now(), _now(), user_id, int(resume_id)),
        )
        conn.commit()
    finally:
        conn.close()


def count_contact_messages_for_user(user_email: str) -> int:
    conn = _connect()
    try:
        return int(_scalar(conn, "SELECT COUNT(*) FROM contact_messages WHERE user_email = ?", (_normalize_email(user_email),), default=0) or 0)
    finally:
        conn.close()


def count_feedback_for_user(user_email: str) -> int:
    conn = _connect()
    try:
        return int(_scalar(conn, "SELECT COUNT(*) FROM analysis_feedback WHERE user_email = ?", (_normalize_email(user_email),), default=0) or 0)
    finally:
        conn.close()


def count_saved_resumes_for_user(user_email: str) -> int:
    user_id = get_user_id(user_email)
    conn = _connect()
    try:
        return int(_scalar(conn, "SELECT COUNT(*) FROM saved_resumes WHERE user_id = ?", (user_id,), default=0) or 0)
    finally:
        conn.close()
