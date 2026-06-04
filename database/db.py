import hashlib
import hmac
import os
import sqlite3
import secrets
from dataclasses import dataclass
from datetime import datetime
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


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
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
                email_verified INTEGER NOT NULL DEFAULT 0
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
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
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
            """
        )
        conn.execute(
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
            """
        )
        conn.execute(
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
            """
        )
        conn.execute(
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
        resume_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(saved_resumes)").fetchall()
        }
        if "full_name" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT NOT NULL DEFAULT ''")
        if "updated_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        if "subscription_status" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'free'")
        if "subscription_plan" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_plan TEXT NOT NULL DEFAULT 'free'")
        if "subscription_start" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_start TEXT NOT NULL DEFAULT ''")
        if "subscription_end" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN subscription_end TEXT NOT NULL DEFAULT ''")
        if "free_assessments_used" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN free_assessments_used INTEGER NOT NULL DEFAULT 0")
        if "free_assessments_limit" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN free_assessments_limit INTEGER NOT NULL DEFAULT 1")
        if "assessment_credits" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN assessment_credits INTEGER NOT NULL DEFAULT 0")
        if "stripe_customer_id" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN stripe_customer_id TEXT DEFAULT ''")
        if "stripe_subscription_id" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN stripe_subscription_id TEXT DEFAULT ''")
        if "email_verified" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
        if "user_id" not in feedback_columns:
            conn.execute("ALTER TABLE analysis_feedback ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")
        if "rating" not in feedback_columns:
            conn.execute("ALTER TABLE analysis_feedback ADD COLUMN rating TEXT NOT NULL DEFAULT ''")
        if "resume_type" not in resume_columns:
            conn.execute("ALTER TABLE saved_resumes ADD COLUMN resume_type TEXT NOT NULL DEFAULT ''")
        if "updated_at" not in resume_columns:
            conn.execute("ALTER TABLE saved_resumes ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        if "last_used_at" not in resume_columns:
            conn.execute("ALTER TABLE saved_resumes ADD COLUMN last_used_at TEXT NOT NULL DEFAULT ''")
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


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
            INSERT INTO users (
                created_at, updated_at, email, password_hash, full_name, subscription_status,
                subscription_plan, free_assessments_used, free_assessments_limit, assessment_credits,
                stripe_customer_id, stripe_subscription_id, email_verified
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
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
            SELECT id, created_at, updated_at, email, full_name, subscription_status, subscription_plan,
                   subscription_start, subscription_end, free_assessments_used, free_assessments_limit,
                   assessment_credits, stripe_customer_id, stripe_subscription_id, email_verified
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
    credits = int(profile.get("assessment_credits", 0))
    subscription_status = (profile.get("subscription_status", "free") or "free").lower()
    subscription_plan = (profile.get("subscription_plan", "free") or "free").lower()
    is_pro = subscription_status in {"pro", "active", "paid"} or subscription_plan == "pro"
    remaining = max(limit - used, 0)
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "credits": credits,
        "subscription_status": subscription_status,
        "subscription_plan": subscription_plan,
        "is_pro": is_pro,
        "can_run_analysis": is_pro or credits > 0 or remaining > 0,
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


def consume_assessment_credit(email: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    access = get_assessment_access(normalized_email)
    if access["is_pro"]:
        return True, "Pro user does not consume credits."
    if access["credits"] <= 0:
        return False, "No assessment credits available."
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            UPDATE users
            SET assessment_credits = MAX(assessment_credits - 1, 0), updated_at = ?
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
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
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
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            "UPDATE users SET subscription_status = ?, updated_at = ? WHERE email = ?",
            ((subscription_status or "free").strip().lower(), _now(), normalized_email),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "User not found."
        return True, "Subscription status updated."
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
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
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
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            """
            UPDATE users
            SET stripe_customer_id = ?, stripe_subscription_id = ?, updated_at = ?
            WHERE email = ?
            """,
            ((stripe_customer_id or "").strip(), (stripe_subscription_id or "").strip(), _now(), normalized_email),
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


def create_email_verification_token(email: str, expires_at: str) -> tuple[bool, str]:
    normalized_email = _normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    try:
        user = conn.execute("SELECT 1 FROM users WHERE email = ?", (normalized_email,)).fetchone()
        if not user:
            return False, "We couldn't find an account with that email."
        token = secrets.token_urlsafe(24)
        conn.execute("DELETE FROM email_verification_tokens WHERE email = ?", (normalized_email,))
        conn.execute(
            """
            INSERT INTO email_verification_tokens (email, token, expires_at)
            VALUES (?, ?, ?)
            """,
            (normalized_email, token, expires_at),
        )
        conn.commit()
        return True, token
    finally:
        conn.close()


def consume_email_verification_token(token: str, current_time: str) -> tuple[bool, str]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT email, token, expires_at FROM email_verification_tokens WHERE token = ?",
            ((token or "").strip(),),
        ).fetchone()
        if not row:
            return False, "That verification token is not valid."
        if row["expires_at"] < current_time:
            conn.execute("DELETE FROM email_verification_tokens WHERE token = ?", (row["token"],))
            conn.commit()
            return False, "That verification token has expired."
        conn.execute(
            "UPDATE users SET email_verified = 1, updated_at = ? WHERE email = ?",
            (_now(), row["email"]),
        )
        conn.execute("DELETE FROM email_verification_tokens WHERE email = ?", (row["email"],))
        conn.commit()
        return True, "Email verified."
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
            "assessment_credits": access["credits"],
            "current_plan": profile.get("subscription_plan", profile.get("subscription_status", "free")),
        }
    finally:
        conn.close()


def save_payment_record(payment: PaymentRecord) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
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
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_contact_messages(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT message_id, user_id, user_email, name, email, message_type, message, status, created_at
            FROM contact_messages
            ORDER BY message_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_feedback(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT feedback_id, user_id, user_email, application_id, rating, comment, created_at
            FROM analysis_feedback
            ORDER BY feedback_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def delete_application(user_email: str, application_id: int) -> tuple[bool, str]:
    normalized_email = _normalize_email(user_email)
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            "DELETE FROM applications WHERE user_email = ? AND id = ?",
            (normalized_email, int(application_id)),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "Analysis not found."
        return True, "Analysis deleted."
    finally:
        conn.close()


def admin_metrics() -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        totals = {
            "total_users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "free_users": conn.execute("SELECT COUNT(*) FROM users WHERE subscription_plan = 'free'").fetchone()[0],
            "pro_users": conn.execute("SELECT COUNT(*) FROM users WHERE subscription_plan = 'pro' OR subscription_status IN ('pro','active','paid')").fetchone()[0],
            "total_analyses": conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
            "total_contact_messages": conn.execute("SELECT COUNT(*) FROM contact_messages").fetchone()[0],
            "total_feedback_items": conn.execute("SELECT COUNT(*) FROM analysis_feedback").fetchone()[0],
            "average_fit_score": conn.execute("SELECT COALESCE(ROUND(AVG(ats_score)), 0) FROM applications").fetchone()[0],
        }
        recent_contact = list_contact_messages(limit=5)
        recent_feedback = list_feedback(limit=5)
        missing_skills_counter: dict[str, int] = {}
        rows = conn.execute("SELECT payload_json FROM applications WHERE payload_json <> ''").fetchall()
        for row in rows:
            payload_json = row["payload_json"]
            try:
                import json as _json
                payload = _json.loads(payload_json)
            except Exception:
                continue
            analysis = payload.get("analysis", {})
            for item in analysis.get("missing_keywords", [])[:8]:
                missing_skills_counter[item] = missing_skills_counter.get(item, 0) + 1
        most_common_missing = sorted(missing_skills_counter.items(), key=lambda item: item[1], reverse=True)[:10]
        return {
            **totals,
            "recent_contact_messages": recent_contact,
            "recent_feedback": recent_feedback,
            "most_common_missing_skills": most_common_missing,
        }
    finally:
        conn.close()


def save_contact_submission(submission: ContactSubmission) -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
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
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def save_resume_stub(user_email: str, resume_name: str, original_filename: str, extracted_text: str, created_at: str, resume_type: str = "") -> int:
    user_id = get_user_id(user_email)
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO saved_resumes (user_id, resume_name, resume_type, original_filename, extracted_text, created_at, updated_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                (resume_name or "").strip(),
                (resume_type or "").strip(),
                (original_filename or "").strip(),
                extracted_text,
                created_at,
                created_at,
                created_at,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_saved_resumes(user_email: str) -> list[dict]:
    user_id = get_user_id(user_email)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT resume_id, resume_name, resume_type, original_filename, created_at, updated_at, last_used_at
            FROM saved_resumes
            WHERE user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_saved_resume(user_email: str, resume_id: int) -> dict | None:
    user_id = get_user_id(user_email)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT resume_id, resume_name, resume_type, original_filename, extracted_text, created_at, updated_at, last_used_at
            FROM saved_resumes
            WHERE user_id = ? AND resume_id = ?
            """,
            (user_id, int(resume_id)),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def rename_saved_resume(user_email: str, resume_id: int, resume_name: str) -> tuple[bool, str]:
    user_id = get_user_id(user_email)
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            """
            UPDATE saved_resumes
            SET resume_name = ?, updated_at = ?
            WHERE user_id = ? AND resume_id = ?
            """,
            ((resume_name or "").strip(), _now(), user_id, int(resume_id)),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "Saved resume not found."
        return True, "Saved resume renamed."
    finally:
        conn.close()


def delete_saved_resume(user_email: str, resume_id: int) -> tuple[bool, str]:
    user_id = get_user_id(user_email)
    conn = sqlite3.connect(DB_PATH)
    try:
        result = conn.execute(
            "DELETE FROM saved_resumes WHERE user_id = ? AND resume_id = ?",
            (user_id, int(resume_id)),
        )
        conn.commit()
        if result.rowcount == 0:
            return False, "Saved resume not found."
        return True, "Saved resume deleted."
    finally:
        conn.close()


def mark_saved_resume_used(user_email: str, resume_id: int) -> None:
    user_id = get_user_id(user_email)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
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
