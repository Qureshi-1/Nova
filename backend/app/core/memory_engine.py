import json
import os
import uuid
from pathlib import Path

MEMORY_DIR = Path(os.path.expanduser("~")) / ".nova_memory"
MEMORY_FILE = MEMORY_DIR / "memory.json"
SESSION_FILE = MEMORY_DIR / "session.json"

MAX_ENTRIES = 200
LONG_TERM_ROLES = ("memory", "settings")


class MemoryEngine:
    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.entries = []
        self.session_id = self._load_session()
        self._load()

    def _load_session(self) -> str:
        if SESSION_FILE.exists():
            try:
                data = json.loads(SESSION_FILE.read_text("utf-8"))
                if data.get("session_id"):
                    return data["session_id"]
            except (json.JSONDecodeError, OSError):
                pass
        session_id = str(uuid.uuid4())
        SESSION_FILE.write_text(json.dumps({"session_id": session_id}), "utf-8")
        return session_id

    def _persist_session(self):
        SESSION_FILE.write_text(
            json.dumps({"session_id": self.session_id}), "utf-8"
        )

    def _load(self):
        if MEMORY_FILE.exists():
            try:
                self.entries = json.loads(MEMORY_FILE.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self.entries = []

    def _persist(self):
        MEMORY_FILE.write_text(
            json.dumps(self.entries, indent=2, ensure_ascii=False), "utf-8"
        )

    def save(self, entry: dict):
        if not isinstance(entry, dict):
            raise TypeError("Memory entry must be a dict")
        entry["ts"] = entry.get("ts", 0)
        entry["session"] = self.session_id
        self.entries.append(entry)
        self.entries = self.entries[-MAX_ENTRIES:]
        self._persist()

    def clear_role(self, role: str) -> int:
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.get("role") != role]
        removed = before - len(self.entries)
        self._persist()
        return removed

    def new_session(self) -> int:
        kept = [e for e in self.entries if e.get("role") in LONG_TERM_ROLES]
        self.entries = kept
        self.session_id = str(uuid.uuid4())
        self._persist_session()
        self._persist()
        return len(kept)

    def recall(self, limit: int = 10) -> list:
        return self.entries[-limit:]

    def recall_session(self, limit: int = 10) -> list:
        current = [
            e for e in self.entries if e.get("session") == self.session_id
        ]
        return current[-limit:]

    def search(self, query: str) -> list:
        q = query.lower()
        return [e for e in self.entries if q in str(e.get("content", "")).lower()]

    def count(self) -> int:
        return len(self.entries)
