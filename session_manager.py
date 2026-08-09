"""SQLite-backed session manager for persisted chat sessions."""

from __future__ import annotations

import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class SessionManager:
    """Manage session records in a single SQLite database file."""

    def __init__(self, store_path: str | Path | None = None):
        self.store_path = Path(store_path) if store_path is not None else Path(__file__).resolve().parent / "sessions.db"
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        self._migrate_legacy_json_store()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.store_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created TEXT NOT NULL,
                    modified TEXT NOT NULL,
                    chatHistory TEXT NOT NULL,
                    investigation TEXT NOT NULL,
                    isContinue INTEGER NOT NULL,
                    auto_allow INTEGER NOT NULL DEFAULT 0,
                    model TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            # Migration check for existing databases lacking the auto_allow or model columns
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()]
            if "auto_allow" not in columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN auto_allow INTEGER NOT NULL DEFAULT 0")
                columns.append("auto_allow")
            if "model" not in columns:
                conn.execute("ALTER TABLE sessions ADD COLUMN model TEXT NOT NULL DEFAULT ''")

    def _load_store(self) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, title, created, modified, chatHistory, investigation, isContinue, auto_allow, model FROM sessions"
            ).fetchall()

        store: dict[str, dict[str, Any]] = {}
        for row in rows:
            store[row["id"]] = {
                "id": row["id"],
                "title": row["title"],
                "created": row["created"],
                "modified": row["modified"],
                "chatHistory": json.loads(row["chatHistory"]),
                "investigation": json.loads(row["investigation"]),
                "isContinue": bool(row["isContinue"]),
                "auto_allow": bool(row["auto_allow"]),
                "model": row["model"],
            }
        return store

    def load_setting(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (str(key),)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def save_setting(self, key: str, value: Any) -> None:
        if value is None:
            return
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (str(key), json.dumps(value, ensure_ascii=False)),
            )

    def _migrate_legacy_json_store(self) -> None:
        legacy_path = self.store_path.parent / "sessions_store.json"
        if not legacy_path.exists() or self.store_path.exists() and self.list_sessions():
            return

        try:
            with legacy_path.open("r", encoding="utf-8") as handle:
                legacy_store = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        if not isinstance(legacy_store, dict):
            return

        for legacy_session in legacy_store.values():
            self.create_session(legacy_session)

    def _normalize_session(self, session: dict[str, Any] | None) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        source = session if isinstance(session, dict) else {}
        normalized = {
            "id": str(source.get("id") or uuid4()),
            "title": str(source.get("title") or "New Chat"),
            "created": str(source.get("created") or now),
            "modified": str(source.get("modified") or now),
            "chatHistory": copy.deepcopy(source.get("chatHistory", [])),
            "investigation": copy.deepcopy(source.get("investigation", {})),
            "isContinue": bool(source.get("isContinue", False)),
            "auto_allow": bool(source.get("auto_allow", False)),
            "model": str(source.get("model") or "").strip(),
        }
        return normalized

    def create_session(self, session: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized = self._normalize_session(session)
        normalized["id"] = str(normalized["id"] or uuid4())
        normalized["created"] = str(normalized["created"] or datetime.now(timezone.utc).isoformat())
        normalized["modified"] = str(normalized["modified"] or normalized["created"])

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (id, title, created, modified, chatHistory, investigation, isContinue, auto_allow, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["id"],
                    normalized["title"],
                    normalized["created"],
                    normalized["modified"],
                    json.dumps(normalized["chatHistory"], ensure_ascii=False),
                    json.dumps(normalized["investigation"], ensure_ascii=False),
                    int(normalized["isContinue"]),
                    int(normalized["auto_allow"]),
                    normalized["model"],
                ),
            )

        return copy.deepcopy(normalized)

    def save_session(self, session: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_session(session)
        normalized["modified"] = datetime.now(timezone.utc).isoformat()
        if not normalized["id"]:
            normalized["id"] = str(uuid4())

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (id, title, created, modified, chatHistory, investigation, isContinue, auto_allow, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["id"],
                    normalized["title"],
                    normalized["created"],
                    normalized["modified"],
                    json.dumps(normalized["chatHistory"], ensure_ascii=False),
                    json.dumps(normalized["investigation"], ensure_ascii=False),
                    int(normalized["isContinue"]),
                    int(normalized["auto_allow"]),
                    normalized["model"],
                ),
            )

        return copy.deepcopy(normalized)

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, created, modified, chatHistory, investigation, isContinue, auto_allow, model
                FROM sessions
                WHERE id = ?
                """,
                (str(session_id),),
            ).fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "title": row["title"],
            "created": row["created"],
            "modified": row["modified"],
            "chatHistory": json.loads(row["chatHistory"]),
            "investigation": json.loads(row["investigation"]),
            "isContinue": bool(row["isContinue"]),
            "auto_allow": bool(row["auto_allow"]),
            "model": row["model"],
        }

    def list_sessions(self) -> list[dict[str, Any]]:
        store = self._load_store()
        sessions = [copy.deepcopy(session) for session in store.values()]
        sessions.sort(key=lambda item: item.get("modified", ""), reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (str(session_id),))
        return cursor.rowcount > 0

    def rename_session(self, session_id: str, title: str) -> dict[str, Any] | None:
        session = self.load_session(session_id)
        if session is None:
            return None
        session["title"] = title or "New Chat"
        session["modified"] = datetime.now(timezone.utc).isoformat()
        return self.save_session(session)

    def switch_session(self, session_id: str) -> dict[str, Any] | None:
        return self.load_session(session_id)
