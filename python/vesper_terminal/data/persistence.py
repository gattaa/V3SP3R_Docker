from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from vesper_terminal.domain.models import AuditEntry


class SqlitePersistence:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at INTEGER DEFAULT (strftime('%s','now')*1000)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_entries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    risk_level TEXT,
                    user_approved INTEGER,
                    command_json TEXT,
                    result_json TEXT,
                    metadata_json TEXT,
                    timestamp INTEGER NOT NULL
                )
                """
            )

    def save_chat(self, session_id: str, role: str, content: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO chat_messages(session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )

    def history(self, session_id: str, limit: int = 50) -> list[tuple[str, str]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return list(reversed(rows))

    def save_audit(self, entry: AuditEntry) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_entries
                (id, session_id, action_type, risk_level, user_approved, command_json, result_json, metadata_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.session_id,
                    entry.action_type.value,
                    entry.risk_level.value if entry.risk_level else None,
                    1 if entry.user_approved else 0 if entry.user_approved is not None else None,
                    json.dumps(entry.command, default=lambda o: o.__dict__) if entry.command else None,
                    json.dumps(entry.result, default=lambda o: o.__dict__) if entry.result else None,
                    json.dumps(entry.metadata),
                    entry.timestamp,
                ),
            )
