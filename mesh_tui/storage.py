"""Persistent message history backed by SQLite."""

from __future__ import annotations

import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    conv TEXT NOT NULL,
    author_id TEXT NOT NULL DEFAULT '',
    author_name TEXT NOT NULL,
    text TEXT NOT NULL,
    direction TEXT NOT NULL,
    ack_state TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages (conv, id);
"""


def default_db_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "mesh_tui" / "history.db"


@dataclass
class Message:
    rowid: int
    ts: float
    conv: str
    author_id: str
    author_name: str
    text: str
    direction: str
    ack_state: str | None


class MessageStore:
    """Message history storage (thread-safe)."""

    def __init__(self, path: str | Path | None = None) -> None:
        path = Path(path) if path is not None else default_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def add(
        self,
        ts: float,
        conv: str,
        author_id: str,
        author_name: str,
        text: str,
        direction: str,
        ack_state: str | None = None,
    ) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO messages (ts, conv, author_id, author_name, text,"
                " direction, ack_state) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ts, conv, author_id, author_name, text, direction, ack_state),
            )
            self._db.commit()
            return int(cur.lastrowid)

    def set_ack(self, rowid: int, state: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE messages SET ack_state = ? WHERE id = ?", (state, rowid)
            )
            self._db.commit()

    def recent(self, conv: str, limit: int = 200) -> list[Message]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM (SELECT * FROM messages WHERE conv = ?"
                " ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
                (conv, limit),
            ).fetchall()
        return [
            Message(
                rowid=r["id"],
                ts=r["ts"],
                conv=r["conv"],
                author_id=r["author_id"],
                author_name=r["author_name"],
                text=r["text"],
                direction=r["direction"],
                ack_state=r["ack_state"],
            )
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._db.close()
