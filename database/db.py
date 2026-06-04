import hashlib
import hmac
import os
import sqlite3
import secrets
from dataclasses import dataclass
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "applications.db"


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
    payload_json: str = ""


@dataclass
class UserRecord:
    id: int = 0
    created_at: str = ""
    email: str = ""
    password_hash: str = ""
    full_name: str = ""
    subscription_status: str = "free"
    free_assessments_used: int = 0
    free_assessments_limit: int = 1
    stripe_customer_id: str = ""
    stripe_subscription_id: str = ""


@dataclass
class PasswordResetToken:
    email: str = ""
    token: str = ""
    expires_at: str = ""


@dataclass
class ContactSubmission:
    created_at: str = ""
    user_email: str = ""
    name: str = ""
    message_type: str = ""
    message: str = ""


@dataclass
class AnalysisFeedback:
    created_at: str = ""
    user_email: str = ""
    user_id: int = 0
    application_id: int = 0
    helpful: int = 0
    comment: str = ""


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL DEFAULT '',
                subscription_status TEXT NOT NULL DEFAULT 'free',
                free_assessments_used INTEGER NOT NULL DEFAULT 0,
                free_assessments_limit INTEGER NOT NULL DEFAULT 1,
                stripe_customer_id TEXT DEFAULT '',
                stripe_subscription_id TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contact_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_email TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                message_type TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_email TEXT NOT NULL DEFAULT '',
                user_id INTEGER NOT NULL DEFAULT 0,
                application_id INTEGER NOT NULL,
                helpful INTEGER NOT NULL,
                comment TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 0,
                resume_name TEXT NOT NULL DEFAULT '',
                original_filename TEXT NOT NULL DEFAULT '',
                extracted_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
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
                payload_json TEXT NOT NULL
            )
            """
        )
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(applications)").fetchall()
        }
        user_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        feedback_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(analysis_feedback)").fetchall()
        }
        if "full_name" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
        if "subscription_status" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'free'")
        if "free_assessments_used" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN free_assessments_used INTEGER NOT NULL DEFAULT 0")
        if "free_assessments_limit" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN free_assessments_limit INTEGER NOT NULL DEFAULT 1")
        if "stripe_customer_id" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT DEFAULT ''")
        if "stripe_subscription_id" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT DEFAULT ''")
        if "user_id" not in feedback_columns:
            conn.execute("ALTER TABLE analysis_feedback ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")
        if "user_email" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN user_email TEXT NOT NULL DEFAULT ''")
        if "job_url" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN job_url TEXT NOT NULL DEFAULT ''")
        if "original_resume_text" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN original_resume_text TEXT NOT NULL DEFAULT ''")
        if "optimized_resume_text" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN optimized_resume_text TEXT NOT NULL DEFAULT ''")
        if "original_ats_score" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN original_ats_score INTEGER NOT NULL DEFAULT 0")
        if "optimized_ats_score" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN optimized_ats_score INTEGER NOT NULL DEFAULT 0")
        if "job_location" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN job_location TEXT NOT NULL DEFAULT ''")
        if "job_date_posted" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN job_date_posted TEXT NOT NULL DEFAULT ''")
        if "job_category" not in columns:
            conn.execute("ALTER TABLE applications ADD COLUMN job_category TEXT NOT NULL DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


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

    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate_digest, expected_digest)


def create_user(created_at: str, email: str, password: str, full_name: str = "") -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    if not normalized_email:
        return False, "Enter an email address."
    if len(password or "") < 8:
        return False, "Use a password with at least 8 characters."

    conn = sqlite3.connect(DB_PATH)
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
        if existing:
            return False, "An account with that email already exists."

        conn.execute(
            """
            INSERT INTO users (created_at, email, password_hash, full_name, subscription_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (created_at, normalized_email, _hash_password(password), (full_name or "").strip(), "free"),
        )
        conn.commit()
        return True, normalized_email
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, created_at, email, password_hash
            FROM users
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()
        if not row:
            return False, "We couldn't find an account with that email."
        if not _verify_password(password, row["password_hash"]):
            return False, "The password you entered is incorrect."
        return True, row["email"]
    finally:
        conn.close()


def get_user_profile(email: str) -> dict | None:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, created_at, email, full_name, subscription_status
                 , free_assessments_used, free_assessments_limit, stripe_customer_id, stripe_subscription_id
            FROM users
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_profile(email: str, full_name: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            "UPDATE users SET full_name = ? WHERE email = ?",
            ((full_name or "").strip(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Profile updated."
    finally:
        conn.close()


def get_user_id(email: str) -> int:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def get_assessment_access(email: str) -> dict:
    profile = get_user_profile(email) or {}
    used = int(profile.get("free_assessments_used", 0))
    limit = int(profile.get("free_assessments_limit", 1))
    subscription_status = (profile.get("subscription_status", "free") or "free").lower()
    is_pro = subscription_status in {"pro", "active", "paid"}
    remaining = max(limit - used, 0)
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "subscription_status": subscription_status,
        "is_pro": is_pro,
        "can_run_analysis": is_pro or remaining > 0,
    }


def increment_free_assessment_usage(email: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    access = get_assessment_access(normalized_email)
    if access["is_pro"]:
        return True, "Pro user does not consume free assessments."
    if access["remaining"] <= 0:
        return False, "Free assessment limit reached."
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            UPDATE users
            SET free_assessments_used = free_assessments_used + 1
            WHERE email = ?
            """,
            (normalized_email,),
        )
        conn.commit()
        return True, "Free assessment usage updated."
    finally:
        conn.close()


def set_subscription_status(email: str, subscription_status: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            "UPDATE users SET subscription_status = ? WHERE email = ?",
            ((subscription_status or "free").strip().lower(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Subscription status updated."
    finally:
        conn.close()


def set_stripe_customer_details(email: str, stripe_customer_id: str = "", stripe_subscription_id: str = "") -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            """
            UPDATE users
            SET stripe_customer_id = ?, stripe_subscription_id = ?
            WHERE email = ?
            """,
            ((stripe_customer_id or "").strip(), (stripe_subscription_id or "").strip(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Stripe details updated."
    finally:
        conn.close()


def create_password_reset_token(email: str, expires_at: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    try:
        user = conn.execute(
            "SELECT 1 FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
        if not user:
            return False, "We couldn't find an account with that email."
        token = secrets.token_urlsafe(24)
        conn.execute("DELETE FROM password_reset_tokens WHERE email = ?", (normalized_email,))
        conn.execute(
            """
            INSERT INTO password_reset_tokens (email, token, expires_at)
            VALUES (?, ?, ?)
            """,
            (normalized_email, token, expires_at),
        )
        conn.commit()
        return True, token
    finally:
        conn.close()


def consume_password_reset_token(token: str, new_password: str, current_time: str) -> tuple[bool, str]:
    if len(new_password or "") < 8:
        return False, "Use a password with at least 8 characters."
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT email, token, expires_at
            FROM password_reset_tokens
            WHERE token = ?
            """,
            ((token or "").strip(),),
        ).fetchone()
        if not row:
            return False, "That reset token is not valid."
        if row["expires_at"] < current_time:
            conn.execute("DELETE FROM password_reset_tokens WHERE token = ?", (row["token"],))
            conn.commit()
            return False, "That reset token has expired."
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (_hash_password(new_password), row["email"]),
        )
        conn.execute("DELETE FROM password_reset_tokens WHERE email = ?", (row["email"],))
        conn.commit()
        return True, "Password updated."
    finally:
        conn.close()


def save_application(record: ApplicationRecord) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO applications (
                user_email,
                created_at,
                original_resume_text,
                optimized_resume_text,
                original_ats_score,
                optimized_ats_score,
                company_name,
                job_title,
                job_url,
                job_location,
                job_date_posted,
                job_category,
                resume_text,
                job_description_text,
                ats_score,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                record.payload_json,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_applications(limit: int = 20, user_email: str = "") -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        normalized_email = _normalize_email(user_email)
        if normalized_email:
            rows = conn.execute(
                """
                SELECT id, user_email, created_at, company_name, job_title, job_url, job_location, job_date_posted, job_category,
                       ats_score, original_ats_score, optimized_ats_score, payload_json
                FROM applications
                WHERE user_email = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (normalized_email, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, user_email, created_at, company_name, job_title, job_url, job_location, job_date_posted, job_category,
                       ats_score, original_ats_score, optimized_ats_score, payload_json
                FROM applications
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_dashboard_metrics(user_email: str) -> dict:
    normalized_email = _normalize_email(user_email)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        access = get_assessment_access(normalized_email)
        profile = get_user_profile(normalized_email) or {}
        rows = conn.execute(
            """
            SELECT job_title, company_name, created_at, ats_score, original_ats_score, optimized_ats_score
            FROM applications
            WHERE user_email = ?
            ORDER BY id DESC
            """,
            (normalized_email,),
        ).fetchall()
        items = [dict(row) for row in rows]
        fit_scores = [int(item.get("ats_score", 0)) for item in items]
        return {
            "recent_analyses": items[:5],
            "average_fit_score": round(sum(fit_scores) / len(fit_scores)) if fit_scores else 0,
            "best_fit_score": max(fit_scores) if fit_scores else 0,
            "jobs_analyzed": len(items),
            "free_assessments_used": access["used"],
            "free_assessments_remaining": access["remaining"],
            "free_assessments_limit": access["limit"],
            "current_plan": profile.get("subscription_status", "free"),
        }
    finally:
        conn.close()


def save_contact_submission(submission: ContactSubmission) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO contact_submissions (created_at, user_email, name, message_type, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                submission.created_at,
                submission.user_email,
                submission.name,
                submission.message_type,
                submission.message,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_analysis_feedback(feedback: AnalysisFeedback) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO analysis_feedback (created_at, user_email, user_id, application_id, helpful, comment)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                feedback.created_at,
                feedback.user_email,
                feedback.user_id,
                feedback.application_id,
                feedback.helpful,
                feedback.comment,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_resume_stub(user_email: str, resume_name: str, original_filename: str, extracted_text: str, created_at: str) -> int:
    user_id = get_user_id(user_email)
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO saved_resumes (user_id, resume_name, original_filename, extracted_text, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                (resume_name or "").strip(),
                (original_filename or "").strip(),
                extracted_text,
                created_at,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()
