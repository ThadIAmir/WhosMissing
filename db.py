"""
Database layer for Who's Missing — standard library sqlite3.
"""

import html
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'fa'
            );

            CREATE TABLE IF NOT EXISTS members (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL DEFAULT '',
                username TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS polls (
                poll_id TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                options_json TEXT NOT NULL,
                explanation TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS poll_votes (
                poll_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (poll_id, user_id),
                FOREIGN KEY (poll_id) REFERENCES polls(poll_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_polls_chat_active
                ON polls (chat_id, is_active);
            """
        )


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Member:
    chat_id: int
    user_id: int
    first_name: str
    last_name: str = ""
    username: Optional[str] = None

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username or f"User {self.user_id}"

    @property
    def tag(self) -> str:
        if self.username:
            return f"@{self.username}"
        escaped = html.escape(self.display_name)
        return f'<a href="tg://user?id={self.user_id}">{escaped}</a>'


# ---------------------------------------------------------------------------
# Chat Settings
# ---------------------------------------------------------------------------

def get_chat_language(chat_id: int, default: str = "fa") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT language FROM chat_settings WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return row["language"] if row else default


def set_chat_language(chat_id: int, lang: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO chat_settings (chat_id, language) VALUES (?, ?)
               ON CONFLICT(chat_id) DO UPDATE SET language = excluded.language""",
            (chat_id, lang),
        )


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

def save_member(
    chat_id: int, user_id: int,
    first_name: str, last_name: str = "", username: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO members (chat_id, user_id, first_name, last_name, username, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(chat_id, user_id) DO UPDATE SET
                   first_name = excluded.first_name,
                   last_name  = excluded.last_name,
                   username   = excluded.username,
                   updated_at = CURRENT_TIMESTAMP""",
            (chat_id, user_id, first_name, last_name, username),
        )


def remove_member(chat_id: int, user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM members WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )


def get_chat_members(chat_id: int) -> list[Member]:
    with get_connection() as conn:
        # Avoid SELECT * so we do not fetch 'updated_at' into our Member dataclass
        rows = conn.execute(
            """SELECT chat_id, user_id, first_name, last_name, username
               FROM members WHERE chat_id = ?
               ORDER BY first_name COLLATE NOCASE""",
            (chat_id,),
        ).fetchall()
        return [Member(**dict(r)) for r in rows]


def get_member_by_username(chat_id: int, username: str) -> Optional[Member]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT chat_id, user_id, first_name, last_name, username
               FROM members
               WHERE chat_id = ? AND LOWER(username) = LOWER(?)""",
            (chat_id, username),
        ).fetchone()
        return Member(**dict(row)) if row else None


def get_member_by_id(chat_id: int, user_id: int) -> Optional[Member]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT chat_id, user_id, first_name, last_name, username
               FROM members
               WHERE chat_id = ? AND user_id = ?""",
            (chat_id, user_id),
        ).fetchone()
        return Member(**dict(row)) if row else None


# ---------------------------------------------------------------------------
# Polls
# ---------------------------------------------------------------------------

def create_poll(
    poll_id: str, chat_id: int, message_id: int,
    question: str, options: list[str], explanation: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE polls SET is_active = 0 WHERE chat_id = ? AND is_active = 1",
            (chat_id,),
        )
        conn.execute(
            """INSERT INTO polls
               (poll_id, chat_id, message_id, question, options_json, explanation, is_active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (poll_id, chat_id, message_id, question, json.dumps(options), explanation),
        )


def get_active_poll(chat_id: int) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT poll_id, chat_id, message_id, question, options_json, explanation
               FROM polls WHERE chat_id = ? AND is_active = 1
               ORDER BY created_at DESC LIMIT 1""",
            (chat_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["options"] = json.loads(d.pop("options_json"))
        return d


def get_poll_by_id(poll_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT poll_id, chat_id, message_id, question, options_json, explanation FROM polls WHERE poll_id = ?",
            (poll_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["options"] = json.loads(d.pop("options_json"))
        return d


def close_poll(poll_id: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE polls SET is_active = 0 WHERE poll_id = ?", (poll_id,))


# ---------------------------------------------------------------------------
# Votes
# ---------------------------------------------------------------------------

def record_vote(poll_id: str, user_id: int, user_name: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO poll_votes (poll_id, user_id, user_name, voted_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(poll_id, user_id) DO UPDATE SET
                   user_name = excluded.user_name, voted_at = CURRENT_TIMESTAMP""",
            (poll_id, user_id, user_name),
        )


def retract_vote(poll_id: str, user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM poll_votes WHERE poll_id = ? AND user_id = ?",
            (poll_id, user_id),
        )


def get_poll_voters(poll_id: str) -> dict[int, str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id, user_name FROM poll_votes WHERE poll_id = ?", (poll_id,)
        ).fetchall()
        return {r["user_id"]: r["user_name"] for r in rows}