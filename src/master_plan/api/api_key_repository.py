"""JSON-file-backed repository for API keys.

Mirrors the other repositories (in-memory, rewritten to a JSON file on every
mutation). Keys are indexed by ``token_sha256`` for O(1) authentication lookup
and are always addressed **per owner** so one user can never touch another's
keys.

``last_used_at`` is stamped on authentication, throttled to at most once per
minute so a burst of API calls does not rewrite the file on every request.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from master_plan.api._io import atomic_write_text
from master_plan.api.api_key_schemas import ApiKeyRecord

__all__ = ["ApiKeyRepository"]

_TOUCH_THROTTLE = timedelta(minutes=1)


class ApiKeyRepository:
    """In-memory API-key store persisted to a JSON file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._records: dict[str, ApiKeyRecord] = {}
        self._by_hash: dict[str, str] = {}
        self._load()

    # -- persistence -------------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8") or "[]")
        self._records = {
            item["id"]: ApiKeyRecord.model_validate(item) for item in raw
        }
        self._reindex()

    def _reindex(self) -> None:
        self._by_hash = {r.token_sha256: r.id for r in self._records.values()}

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [r.model_dump(mode="json") for r in self._records.values()]
        atomic_write_text(
            self._path, json.dumps(payload, indent=2, ensure_ascii=False)
        )

    # -- queries -----------------------------------------------------------
    def get_by_token(self, token_sha256: str) -> ApiKeyRecord | None:
        """Return the record whose stored hash equals ``token_sha256``."""
        key_id = self._by_hash.get(token_sha256)
        return self._records.get(key_id) if key_id else None

    def get(self, key_id: str, owner_id: str) -> ApiKeyRecord | None:
        """Return the owner's key with ``key_id``, or ``None``."""
        record = self._records.get(key_id)
        if record is None or record.owner_id != owner_id:
            return None
        return record

    def list_for_owner(self, owner_id: str) -> list[ApiKeyRecord]:
        """Return the owner's keys, newest first."""
        rows = [r for r in self._records.values() if r.owner_id == owner_id]
        return sorted(rows, key=lambda r: r.created_at, reverse=True)

    # -- mutations ---------------------------------------------------------
    def add(self, record: ApiKeyRecord) -> ApiKeyRecord:
        """Persist a new key record and return it."""
        self._records[record.id] = record
        self._by_hash[record.token_sha256] = record.id
        self._persist()
        return record

    def touch(self, key_id: str, now: datetime) -> None:
        """Stamp ``last_used_at`` (throttled) for auditing."""
        record = self._records.get(key_id)
        if record is None:
            return
        last = record.last_used_at
        if last is not None and now - last < _TOUCH_THROTTLE:
            return
        self._records[key_id] = record.model_copy(update={"last_used_at": now})
        self._persist()

    def revoke(self, key_id: str, owner_id: str, now: datetime) -> bool:
        """Soft-revoke the owner's key; return ``True`` if one was revoked."""
        record = self.get(key_id, owner_id)
        if record is None or record.revoked_at is not None:
            return False
        self._records[key_id] = record.model_copy(update={"revoked_at": now})
        self._persist()
        return True
