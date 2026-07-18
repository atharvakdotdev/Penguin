"""Dedicated JSON-backed session manager for persisted chat sessions."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class SessionManager:
    """Manage session records in a single JSON store."""

    def __init__(self, store_path: str | Path | None = None):
        self.store_path = Path(store_path) if store_path is not None else Path(__file__).resolve().parent / "sessions_store.json"
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self.store_path.write_text(json.dumps({}, indent=2), encoding="utf-8")

    def _load_store(self) -> dict[str, dict[str, Any]]:
        try:
            with self.store_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
                if isinstance(raw, dict):
                    return raw
        except json.JSONDecodeError:
            pass

        self.store_path.write_text(json.dumps({}, indent=2), encoding="utf-8")
        return {}

    def _write_store(self, store: dict[str, dict[str, Any]]) -> None:
        with self.store_path.open("w", encoding="utf-8") as handle:
            json.dump(store, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

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
        }
        return normalized

    def create_session(self, session: dict[str, Any] | None = None) -> dict[str, Any]:
        store = self._load_store()
        normalized = self._normalize_session(session)
        normalized["id"] = str(normalized["id"] or uuid4())
        normalized["created"] = str(normalized["created"] or datetime.now(timezone.utc).isoformat())
        normalized["modified"] = str(normalized["modified"] or normalized["created"])
        store[normalized["id"]] = normalized
        self._write_store(store)
        return copy.deepcopy(normalized)

    def save_session(self, session: dict[str, Any]) -> dict[str, Any]:
        store = self._load_store()
        normalized = self._normalize_session(session)
        normalized["modified"] = datetime.now(timezone.utc).isoformat()
        if not normalized["id"]:
            normalized["id"] = str(uuid4())
        store[normalized["id"]] = normalized
        self._write_store(store)
        return copy.deepcopy(normalized)

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        store = self._load_store()
        session = store.get(str(session_id))
        if session is None:
            return None
        return copy.deepcopy(session)

    def list_sessions(self) -> list[dict[str, Any]]:
        store = self._load_store()
        sessions = [copy.deepcopy(session) for session in store.values()]
        sessions.sort(key=lambda item: item.get("modified", ""), reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        store = self._load_store()
        removed = store.pop(str(session_id), None)
        if removed is None:
            return False
        self._write_store(store)
        return True

    def rename_session(self, session_id: str, title: str) -> dict[str, Any] | None:
        session = self.load_session(session_id)
        if session is None:
            return None
        session["title"] = title or "New Chat"
        session["modified"] = datetime.now(timezone.utc).isoformat()
        return self.save_session(session)

    def switch_session(self, session_id: str) -> dict[str, Any] | None:
        return self.load_session(session_id)
