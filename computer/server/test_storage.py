"""SQLite persistence tests for operator configuration and session metadata."""
import sqlite3

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
