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


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
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
