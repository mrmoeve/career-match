import hashlib
import hmac
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "applications.db"


@dataclass
class ApplicationRecord:
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


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def create_user(created_at: str, email: str, password: str) -> tuple[bool, str]:
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
            INSERT INTO users (created_at, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (created_at, normalized_email, _hash_password(password)),
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


def save_application(record: ApplicationRecord) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO applications (
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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
    finally:
        conn.close()


def list_applications(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT created_at, company_name, job_title, job_url, job_location, job_date_posted, job_category, ats_score,
                   original_ats_score, optimized_ats_score
            FROM applications
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
