"""SQLite persistence tests for operator configuration and session metadata."""
import sqlite3
from contextlib import closing

import pytest

from computer.server.storage import SQLiteStore


def test_store_initializes_schema_and_round_trips_operator_config(tmp_path):
    store = SQLiteStore(tmp_path / "computer.db")

    store.set_config("source_lang", "vi")
    store.set_config("target_lang", "en")

    assert store.get_config("source_lang") == "vi"
    assert store.get_config("target_lang") == "en"
    with sqlite3.connect(tmp_path / "computer.db") as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"operator_config", "session_metadata"} <= tables


def test_store_keeps_only_non_sensitive_session_metadata(tmp_path):
    store = SQLiteStore(tmp_path / "computer.db")

    store.record_session("session-1", "vi", "en", "completed")

    assert store.list_sessions() == [
        {"session_id": "session-1", "source_lang": "vi", "target_lang": "en", "state": "completed"}
    ]
    columns = store.session_columns()
    assert "transcript" not in columns
    assert "audio" not in columns


def test_upgrade_existing_unversioned_database_preserves_config(tmp_path):
    database = tmp_path / "legacy.db"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("CREATE TABLE operator_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO operator_config VALUES ('source_lang', 'fr')")
    assert SQLiteStore(database).get_config("source_lang") == "fr"
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)


def test_store_rejects_unknown_newer_schema(tmp_path):
    database = tmp_path / "future.db"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA user_version = 999")
    with pytest.raises(ValueError, match="schema version"):
        SQLiteStore(database)
