"""SQLite storage for non-sensitive operator configuration and session metadata."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
CONFIG_UPSERT = (
    "INSERT INTO operator_config(key, value) VALUES (?, ?) "
    "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
)


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == SCHEMA_VERSION:
                return
            if version != 0:
                raise ValueError(f"unsupported database schema version: {version}")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operator_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS session_metadata (
                    session_id TEXT PRIMARY KEY,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self.path, timeout=0.25)) as connection, connection:
            connection.row_factory = sqlite3.Row
            yield connection

    def set_config(self, key: str, value: str) -> None:
        if not key or not value:
            raise ValueError("config key and value must be non-empty")
        with self._connect() as connection:
            connection.execute(CONFIG_UPSERT, (key, value))

    def get_config(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM operator_config WHERE key = ?", (key,)
            ).fetchone()
        return None if row is None else str(row["value"])

    def set_languages(self, source_lang: str, target_lang: str) -> None:
        with self._connect() as connection:
            connection.executemany(CONFIG_UPSERT, (
                ("source_lang", source_lang), ("target_lang", target_lang),
            ))

    def get_languages(self) -> dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, value FROM operator_config WHERE key IN ('source_lang', 'target_lang')"
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def record_session(self, session_id: str, source_lang: str, target_lang: str, state: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO session_metadata(session_id, source_lang, target_lang, state) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET state = excluded.state",
                (session_id, source_lang, target_lang, state),
            )

    def cancel_interrupted_sessions(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE session_metadata SET state = 'cancelled' "
                "WHERE state IN ('active', 'disconnected_grace')"
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
