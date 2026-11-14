"""SQLite storage for non-sensitive operator configuration and session metadata."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS operator_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS session_metadata (
                    session_id TEXT PRIMARY KEY,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def set_config(self, key: str, value: str) -> None:
        if not key or not value:
            raise ValueError("config key and value must be non-empty")
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO operator_config(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_config(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM operator_config WHERE key = ?", (key,)
            ).fetchone()
        return None if row is None else str(row["value"])

    def record_session(self, session_id: str, source_lang: str, target_lang: str, state: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO session_metadata(session_id, source_lang, target_lang, state) VALUES (?, ?, ?, ?)",
                (session_id, source_lang, target_lang, state),
            )

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT session_id, source_lang, target_lang, state FROM session_metadata ORDER BY created_at, session_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def session_columns(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute("PRAGMA table_info(session_metadata)").fetchall()
        return {str(row["name"]) for row in rows}
