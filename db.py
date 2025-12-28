#!/usr/bin/env python3
"""
Database module for BB-Poster-Automation.
Handles job queue, status tracking, and credentials storage.
"""

import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

PROJECT_ROOT = os.path.expanduser("~/BB-Poster-Automation")
DB_FILE = os.path.join(PROJECT_ROOT, "poster.sqlite3")

# Job statuses
STATUS_PENDING = "pending"
STATUS_POSTING = "posting"
STATUS_POSTED = "posted"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"  # For files you want to ignore

# -----------------------------------------------------------------------------
# Database Setup
# -----------------------------------------------------------------------------

SCHEMA = """
-- Main job queue table
CREATE TABLE IF NOT EXISTS media_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path       TEXT UNIQUE NOT NULL,       -- Relative path from PROJECT_ROOT
    file_size       INTEGER,                    -- Bytes, for change detection
    file_mtime      REAL,                       -- Modification time
    detected_at     INTEGER NOT NULL,           -- Unix timestamp when scanner found it
    
    -- Parsed from path structure
    country         TEXT,
    model_name      TEXT,
    platform        TEXT,                       -- 'FB_Page', 'Instagram', 'FB_Account'
    content_type    TEXT,                       -- 'Reels', 'Stories', 'Photos', 'Videos', 'Feeds'
    
    -- Posting state
    status          TEXT DEFAULT 'pending',
    attempts        INTEGER DEFAULT 0,
    max_attempts    INTEGER DEFAULT 3,
    last_attempt_at INTEGER,
    posted_at       INTEGER,
    platform_post_id TEXT,                      -- ID returned by platform API
    error_message   TEXT,
    
    -- Metadata
    caption         TEXT,                       -- Optional caption for the post
    scheduled_for   INTEGER                     -- Optional: schedule for future posting
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_media_status ON media_files(status);
CREATE INDEX IF NOT EXISTS idx_media_platform_model ON media_files(platform, model_name);
CREATE INDEX IF NOT EXISTS idx_media_detected ON media_files(detected_at);

-- Credentials table for API access
CREATE TABLE IF NOT EXISTS credentials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    country         TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    platform        TEXT NOT NULL,              -- 'FB_Page', 'Instagram'
    
    -- Facebook/Instagram API credentials
    page_id         TEXT,
    ig_user_id      TEXT,
    access_token    TEXT,
    token_expires   INTEGER,                    -- Unix timestamp
    
    -- Metadata
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL,
    is_active       INTEGER DEFAULT 1,
    
    UNIQUE(country, model_name, platform)
);

-- Post history / audit log (optional but useful)
CREATE TABLE IF NOT EXISTS post_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    media_file_id   INTEGER NOT NULL,
    timestamp       INTEGER NOT NULL,
    action          TEXT NOT NULL,              -- 'attempt', 'success', 'failure'
    details         TEXT,                       -- JSON or plain text details
    
    FOREIGN KEY (media_file_id) REFERENCES media_files(id)
);

CREATE INDEX IF NOT EXISTS idx_log_media ON post_log(media_file_id);
"""


def init_db() -> None:
    """Initialize database with schema."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with sqlite3.connect(DB_FILE) as con:
        con.executescript(SCHEMA)
        con.commit()
    print(f"Database initialized: {DB_FILE}")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield con
    finally:
        con.close()


# -----------------------------------------------------------------------------
# Media File Operations
# -----------------------------------------------------------------------------

def file_exists(file_path: str) -> bool:
    """Check if a file path is already in the database."""
    with get_connection() as con:
        cur = con.execute(
            "SELECT 1 FROM media_files WHERE file_path = ?",
            (file_path,)
        )
        return cur.fetchone() is not None


def insert_media_file(
    file_path: str,
    file_size: int,
    file_mtime: float,
    country: str,
    model_name: str,
    platform: str,
    content_type: str,
    caption: Optional[str] = None,
    scheduled_for: Optional[int] = None
) -> Optional[int]:
    """
    Insert a new media file into the queue.
    Returns the new row ID, or None if it already exists.
    """
    with get_connection() as con:
        try:
            cur = con.execute(
                """
                INSERT INTO media_files 
                    (file_path, file_size, file_mtime, detected_at,
                     country, model_name, platform, content_type, caption, scheduled_for)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_path, file_size, file_mtime, int(time.time()),
                 country, model_name, platform, content_type, caption, scheduled_for)
            )
            con.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            # Already exists
            return None


def get_pending_jobs(
    limit: int = 10,
    platform: Optional[str] = None,
    model_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get pending jobs ready for posting.
    Optionally filter by platform or model.
    """
    query = """
        SELECT * FROM media_files 
        WHERE status = ? 
          AND (scheduled_for IS NULL OR scheduled_for <= ?)
          AND attempts < max_attempts
    """
    params: List[Any] = [STATUS_PENDING, int(time.time())]
    
    if platform:
        query += " AND platform = ?"
        params.append(platform)
    if model_name:
        query += " AND model_name = ?"
        params.append(model_name)
    
    query += " ORDER BY detected_at ASC LIMIT ?"
    params.append(limit)
    
    with get_connection() as con:
        cur = con.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def get_job_by_id(job_id: int) -> Optional[Dict[str, Any]]:
    """Get a single job by ID."""
    with get_connection() as con:
        cur = con.execute("SELECT * FROM media_files WHERE id = ?", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_job_status(
    job_id: int,
    status: str,
    error_message: Optional[str] = None,
    platform_post_id: Optional[str] = None
) -> None:
    """Update job status after a posting attempt."""
    now = int(time.time())
    
    with get_connection() as con:
        if status == STATUS_POSTED:
            con.execute(
                """
                UPDATE media_files 
                SET status = ?, posted_at = ?, platform_post_id = ?,
                    last_attempt_at = ?, attempts = attempts + 1
                WHERE id = ?
                """,
                (status, now, platform_post_id, now, job_id)
            )
        elif status == STATUS_FAILED:
            con.execute(
                """
                UPDATE media_files 
                SET status = ?, error_message = ?,
                    last_attempt_at = ?, attempts = attempts + 1
                WHERE id = ?
                """,
                (status, error_message, now, job_id)
            )
        else:
            con.execute(
                """
                UPDATE media_files 
                SET status = ?, last_attempt_at = ?
                WHERE id = ?
                """,
                (status, now, job_id)
            )
        con.commit()
        
        # Log the action
        log_action(con, job_id, status, error_message or platform_post_id)


def mark_job_posting(job_id: int) -> None:
    """Mark a job as currently being processed (prevents double-processing)."""
    with get_connection() as con:
        con.execute(
            "UPDATE media_files SET status = ? WHERE id = ?",
            (STATUS_POSTING, job_id)
        )
        con.commit()


def reset_stale_jobs(stale_seconds: int = 300) -> int:
    """
    Reset jobs stuck in 'posting' status (e.g., after a crash).
    Returns number of jobs reset.
    """
    cutoff = int(time.time()) - stale_seconds
    with get_connection() as con:
        cur = con.execute(
            """
            UPDATE media_files 
            SET status = ?
            WHERE status = ? AND last_attempt_at < ?
            """,
            (STATUS_PENDING, STATUS_POSTING, cutoff)
        )
        con.commit()
        return cur.rowcount


def retry_failed_jobs(max_attempts: int = 3) -> int:
    """Reset failed jobs that haven't exceeded max attempts."""
    with get_connection() as con:
        cur = con.execute(
            """
            UPDATE media_files 
            SET status = ?
            WHERE status = ? AND attempts < ?
            """,
            (STATUS_PENDING, STATUS_FAILED, max_attempts)
        )
        con.commit()
        return cur.rowcount


def clear_pending_jobs() -> int:
    """
    Delete all pending jobs from the database.
    Useful for re-scanning files with new schedule times.
    Returns number of jobs deleted.
    """
    with get_connection() as con:
        cur = con.execute(
            "DELETE FROM media_files WHERE status = ?",
            (STATUS_PENDING,)
        )
        con.commit()
        return cur.rowcount


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

def log_action(con, media_file_id: int, action: str, details: Optional[str] = None) -> None:
    """Log an action to the post_log table."""
    con.execute(
        "INSERT INTO post_log (media_file_id, timestamp, action, details) VALUES (?, ?, ?, ?)",
        (media_file_id, int(time.time()), action, details)
    )


# -----------------------------------------------------------------------------
# Credentials Management
# -----------------------------------------------------------------------------

def get_credentials(country: str, model_name: str, platform: str) -> Optional[Dict[str, Any]]:
    """Get credentials for a specific account."""
    with get_connection() as con:
        cur = con.execute(
            """
            SELECT * FROM credentials 
            WHERE country = ? AND model_name = ? AND platform = ? AND is_active = 1
            """,
            (country, model_name, platform)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def upsert_credentials(
    country: str,
    model_name: str,
    platform: str,
    page_id: Optional[str] = None,
    ig_user_id: Optional[str] = None,
    access_token: Optional[str] = None,
    token_expires: Optional[int] = None
) -> None:
    """Insert or update credentials for an account."""
    now = int(time.time())
    with get_connection() as con:
        con.execute(
            """
            INSERT INTO credentials 
                (country, model_name, platform, page_id, ig_user_id, 
                 access_token, token_expires, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(country, model_name, platform) DO UPDATE SET
                page_id = COALESCE(excluded.page_id, page_id),
                ig_user_id = COALESCE(excluded.ig_user_id, ig_user_id),
                access_token = COALESCE(excluded.access_token, access_token),
                token_expires = COALESCE(excluded.token_expires, token_expires),
                updated_at = excluded.updated_at
            """,
            (country, model_name, platform, page_id, ig_user_id,
             access_token, token_expires, now, now)
        )
        con.commit()


def get_scheduled_jobs(days_ahead: int = 7) -> List[Dict[str, Any]]:
    """Get jobs scheduled for the next N days."""
    now = int(time.time())
    future = now + (days_ahead * 86400)
    
    with get_connection() as con:
        cur = con.execute(
            """
            SELECT * FROM media_files 
            WHERE status = ? 
              AND scheduled_for IS NOT NULL
              AND scheduled_for BETWEEN ? AND ?
            ORDER BY scheduled_for ASC
            """,
            (STATUS_PENDING, now, future)
        )
        return [dict(row) for row in cur.fetchall()]


def get_all_scheduled_jobs() -> List[Dict[str, Any]]:
    """Get ALL scheduled jobs (no date limit)."""
    with get_connection() as con:
        cur = con.execute(
            """
            SELECT * FROM media_files 
            WHERE status = ? 
              AND scheduled_for IS NOT NULL
            ORDER BY scheduled_for ASC
            """,
            (STATUS_PENDING,)
        )
        return [dict(row) for row in cur.fetchall()]


# -----------------------------------------------------------------------------
# Statistics
# -----------------------------------------------------------------------------

def get_stats() -> Dict[str, Any]:
    """Get queue statistics."""
    with get_connection() as con:
        stats = {}
        
        # Count by status
        cur = con.execute(
            "SELECT status, COUNT(*) as count FROM media_files GROUP BY status"
        )
        stats["by_status"] = {row["status"]: row["count"] for row in cur.fetchall()}
        
        # Count by platform
        cur = con.execute(
            "SELECT platform, COUNT(*) as count FROM media_files GROUP BY platform"
        )
        stats["by_platform"] = {row["platform"]: row["count"] for row in cur.fetchall()}
        
        # Recent activity
        cur = con.execute(
            "SELECT COUNT(*) as count FROM media_files WHERE posted_at > ?",
            (int(time.time()) - 86400,)  # Last 24 hours
        )
        stats["posted_24h"] = cur.fetchone()["count"]
        
        return stats


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="Database management for BB-Poster")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--stats", action="store_true", help="Show queue statistics")
    parser.add_argument("--pending", action="store_true", help="List pending jobs")
    parser.add_argument("--scheduled", action="store_true", help="List scheduled jobs for next 7 days")
    parser.add_argument("--scheduled-all", action="store_true", help="List ALL scheduled jobs")
    parser.add_argument("--reset-stale", action="store_true", help="Reset stale 'posting' jobs")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed jobs")
    parser.add_argument("--clear-pending", action="store_true", help="Delete all pending jobs (for re-scanning)")
    args = parser.parse_args()
    
    if args.init:
        init_db()
    elif args.stats:
        init_db()
        print(json.dumps(get_stats(), indent=2))
    elif args.pending:
        init_db()
        jobs = get_pending_jobs(limit=20)
        for job in jobs:
            scheduled = ""
            if job.get("scheduled_for"):
                dt = datetime.fromtimestamp(job["scheduled_for"])
                scheduled = f" [scheduled: {dt.strftime('%m/%d %I:%M %p')}]"
            print(f"[{job['id']}] {job['platform']}/{job['content_type']}: {job['file_path']}{scheduled}")
        if not jobs:
            print("No pending jobs.")
    elif args.scheduled:
        init_db()
        jobs = get_scheduled_jobs(days_ahead=7)
        if jobs:
            print(f"Scheduled posts for next 7 days ({len(jobs)} total):\n")
            for job in jobs:
                dt = datetime.fromtimestamp(job["scheduled_for"])
                caption_preview = ""
                if job.get("caption"):
                    caption_preview = f" - \"{job['caption'][:30]}...\""
                print(f"  {dt.strftime('%m/%d/%Y %I:%M %p')} | [{job['id']}] {job['platform']}/{job['content_type']}: {job['file_path']}{caption_preview}")
        else:
            print("No scheduled jobs for the next 7 days.")
    elif args.scheduled_all:
        init_db()
        jobs = get_all_scheduled_jobs()
        if jobs:
            print(f"ALL scheduled posts ({len(jobs)} total):\n")
            for job in jobs:
                dt = datetime.fromtimestamp(job["scheduled_for"])
                caption_preview = ""
                if job.get("caption"):
                    caption_preview = f" - \"{job['caption'][:30]}...\""
                print(f"  {dt.strftime('%m/%d/%Y %I:%M %p')} | [{job['id']}] {job['platform']}/{job['content_type']}: {job['file_path']}{caption_preview}")
        else:
            print("No scheduled jobs.")
    elif args.reset_stale:
        init_db()
        count = reset_stale_jobs()
        print(f"Reset {count} stale job(s).")
    elif args.retry_failed:
        init_db()
        count = retry_failed_jobs()
        print(f"Reset {count} failed job(s) for retry.")
    elif args.clear_pending:
        init_db()
        count = clear_pending_jobs()
        print(f"Cleared {count} pending job(s). Run scanner to re-add with new times.")
    else:
        parser.print_help()