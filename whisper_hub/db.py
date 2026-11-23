"""SQLite storage: devices, pairing codes, transcriptions and FTS5 search."""

from __future__ import annotations

import base64
import binascii
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'other',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'revoked')),
    key_hash TEXT UNIQUE,
    key_prefix TEXT,
    builtin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    activated_at TEXT,
    revoked_at TEXT,
    deleted_at TEXT,
    last_seen_at TEXT,
    last_ip TEXT,
    last_user_agent TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pairing_codes (
    code_hash TEXT PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    claimed_at TEXT
);

CREATE TABLE IF NOT EXISTS transcriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,
    detected_language TEXT,
    language_probability REAL,
    task TEXT NOT NULL,
    audio_duration_s REAL,
    processing_ms INTEGER,
    model TEXT,
    endpoint TEXT,
    client_user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_transcriptions_created
    ON transcriptions(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_transcriptions_device_created
    ON transcriptions(device_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_devices_key_hash ON devices(key_hash);
CREATE INDEX IF NOT EXISTS idx_pairing_device ON pairing_codes(device_id);

CREATE VIRTUAL TABLE IF NOT EXISTS transcriptions_fts USING fts5(
    text,
    content='transcriptions',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS transcriptions_ai AFTER INSERT ON transcriptions BEGIN
    INSERT INTO transcriptions_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS transcriptions_ad AFTER DELETE ON transcriptions BEGIN
    INSERT INTO transcriptions_fts(transcriptions_fts, rowid, text)
    VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS transcriptions_au AFTER UPDATE OF text ON transcriptions BEGIN
    INSERT INTO transcriptions_fts(transcriptions_fts, rowid, text)
    VALUES ('delete', old.id, old.text);
    INSERT INTO transcriptions_fts(rowid, text) VALUES (new.id, new.text);
END;
"""

DEVICE_QUERY = """
SELECT d.*,
       (SELECT COUNT(*) FROM transcriptions t WHERE t.device_id = d.id) AS transcription_count,
       (SELECT t.created_at FROM transcriptions t
         WHERE t.device_id = d.id ORDER BY t.created_at DESC, t.id DESC LIMIT 1) AS last_transcription_at,
       (SELECT t.text FROM transcriptions t
         WHERE t.device_id = d.id ORDER BY t.created_at DESC, t.id DESC LIMIT 1) AS last_text,
       (SELECT t.detected_language FROM transcriptions t
         WHERE t.device_id = d.id ORDER BY t.created_at DESC, t.id DESC LIMIT 1) AS last_language,
       (SELECT t.task FROM transcriptions t
         WHERE t.device_id = d.id ORDER BY t.created_at DESC, t.id DESC LIMIT 1) AS last_task
FROM devices d
"""

TRANSCRIPTION_QUERY = """
SELECT t.id, t.device_id, t.created_at, t.text, t.detected_language,
       t.language_probability, t.task, t.audio_duration_s, t.processing_ms,
       t.model, t.endpoint, t.client_user_agent,
       d.name AS device_name, d.kind AS device_kind, d.deleted_at AS device_deleted_at
FROM transcriptions t
LEFT JOIN devices d ON d.id = t.device_id
"""

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fts_query(raw: str) -> str | None:
    """Turn arbitrary user input into a safe FTS5 prefix query.

    Every token is quoted (so FTS syntax characters cannot be injected) and
    turned into a prefix term: ``"meet"* "notes"*``.
    """
    tokens: list[str] = []
    for match in _WORD_RE.finditer(raw or ""):
        token = match.group(0)[:64]
        if token:
            tokens.append(token)
        if len(tokens) >= 12:
            break
    if not tokens:
        return None
    return " ".join(f'"{token}"*' for token in tokens)


def encode_cursor(created_at: str, row_id: int) -> str:
    raw = f"{created_at}|{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str | None) -> tuple[str, int] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        created_at, _, row_id = raw.rpartition("|")
        return created_at, int(row_id)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise ValueError("invalid cursor") from None


class _Connection(sqlite3.Connection):
    """``with conn:`` commits/rolls back *and* closes, so write helpers do not leak handles."""

    def __exit__(self, exc_type, exc, tb):  # type: ignore[override]
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._write_lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, factory=_Connection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        # Deleted transcripts are overwritten on disk instead of lingering in free pages.
        conn.execute("PRAGMA secure_delete = ON")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            # WAL lets history reads and new transcriptions proceed concurrently instead of a
            # long write (delete-all, export) stalling every request. Persists in the file.
            conn.execute("PRAGMA journal_mode = WAL")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    # ------------------------------------------------------------------ devices

    @staticmethod
    def _device(row: sqlite3.Row) -> dict[str, Any]:
        deleted = row["deleted_at"] is not None
        item = dict(row)
        item["deleted"] = deleted
        item["display_name"] = "Deleted device" if deleted else row["name"]
        item["has_key"] = row["key_hash"] is not None
        item.pop("key_hash", None)
        return item

    def get_device(self, device_id: int) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(DEVICE_QUERY + " WHERE d.id = ?", (device_id,)).fetchone()
        finally:
            conn.close()
        return self._device(row) if row else None

    def get_device_by_key_hash(self, key_hash: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            # Runs on every API request: plain row only, no history aggregates.
            row = conn.execute(
                "SELECT d.* FROM devices d"
                " WHERE d.key_hash = ? AND d.status = 'active' AND d.deleted_at IS NULL",
                (key_hash,),
            ).fetchone()
        finally:
            conn.close()
        return self._device(row) if row else None

    def list_devices(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(DEVICE_QUERY + " ORDER BY d.builtin ASC, d.id ASC").fetchall()
        finally:
            conn.close()
        return [self._device(row) for row in rows]

    def create_device(self, name: str, kind: str = "other", *, builtin: bool = False) -> dict[str, Any]:
        now = utc_now_iso()
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO devices (name, kind, status, builtin, created_at) VALUES (?, ?, 'pending', ?, ?)",
                (name, kind, 1 if builtin else 0, now),
            )
            device_id = int(cur.lastrowid)
        device = self.get_device(device_id)
        assert device is not None
        return device

    def get_builtin_device(self, kind: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                DEVICE_QUERY + " WHERE d.builtin = 1 AND d.kind = ? ORDER BY d.id LIMIT 1", (kind,)
            ).fetchone()
        finally:
            conn.close()
        return self._device(row) if row else None

    def rename_device(self, device_id: int, name: str | None = None, kind: str | None = None) -> dict[str, Any] | None:
        fields: list[str] = []
        values: list[Any] = []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if kind is not None:
            fields.append("kind = ?")
            values.append(kind)
        if fields:
            values.append(device_id)
            with self._write_lock, self._connect() as conn:
                conn.execute(f"UPDATE devices SET {', '.join(fields)} WHERE id = ?", values)
        return self.get_device(device_id)

    def set_device_key(self, device_id: int, key_hash: str, key_prefix: str) -> None:
        now = utc_now_iso()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE devices SET key_hash = ?, key_prefix = ?, status = 'active', "
                "activated_at = COALESCE(activated_at, ?), revoked_at = NULL WHERE id = ?",
                (key_hash, key_prefix, now, device_id),
            )

    def activate_without_key(self, device_id: int) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE devices SET status = 'active', activated_at = COALESCE(activated_at, ?) WHERE id = ?",
                (utc_now_iso(), device_id),
            )

    def revoke_device(self, device_id: int) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE devices SET status = 'revoked', revoked_at = ?, key_hash = NULL, key_prefix = NULL "
                "WHERE id = ?",
                (utc_now_iso(), device_id),
            )
            # An outstanding QR/link must not be able to re-activate a revoked device.
            conn.execute(
                "DELETE FROM pairing_codes WHERE device_id = ? AND claimed_at IS NULL", (device_id,)
            )

    def touch_device(self, device_id: int, ip: str | None, user_agent: str | None) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE devices SET last_seen_at = ?, last_ip = ?, last_user_agent = ? WHERE id = ?",
                (utc_now_iso(), (ip or "")[:100] or None, (user_agent or "")[:300] or None, device_id),
            )

    def delete_device(self, device_id: int, *, delete_history: bool) -> bool:
        with self._write_lock, self._connect() as conn:
            if delete_history:
                conn.execute("DELETE FROM transcriptions WHERE device_id = ?", (device_id,))
                cur = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
                return cur.rowcount > 0
            cur = conn.execute(
                "UPDATE devices SET deleted_at = ?, status = 'revoked', key_hash = NULL, key_prefix = NULL "
                "WHERE id = ? AND deleted_at IS NULL",
                (utc_now_iso(), device_id),
            )
            conn.execute("DELETE FROM pairing_codes WHERE device_id = ?", (device_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------------ pairing

    def create_pairing_code(self, device_id: int, code_hash: str, expires_at: str) -> None:
        now = utc_now_iso()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM pairing_codes WHERE device_id = ? AND claimed_at IS NULL", (device_id,)
            )
            conn.execute(
                "INSERT INTO pairing_codes (code_hash, device_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (code_hash, device_id, now, expires_at),
            )

    def get_pairing(self, code_hash: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT p.*, d.name AS device_name, d.kind AS device_kind, d.status AS device_status, "
                "d.deleted_at AS device_deleted_at "
                "FROM pairing_codes p JOIN devices d ON d.id = p.device_id WHERE p.code_hash = ?",
                (code_hash,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        item = dict(row)
        item["expired"] = row["expires_at"] <= utc_now_iso()
        item["claimed"] = row["claimed_at"] is not None
        item["display_name"] = "Deleted device" if row["device_deleted_at"] else row["device_name"]
        return item

    def claim_pairing(self, code_hash: str, key_hash: str, key_prefix: str) -> dict[str, Any] | None:
        """Atomically consume a pairing code and install a fresh device key."""
        now = utc_now_iso()
        with self._write_lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT p.device_id, p.claimed_at, p.expires_at, d.deleted_at "
                    "FROM pairing_codes p JOIN devices d ON d.id = p.device_id WHERE p.code_hash = ?",
                    (code_hash,),
                ).fetchone()
                if (
                    row is None
                    or row["claimed_at"] is not None
                    or row["expires_at"] <= now
                    or row["deleted_at"] is not None
                ):
                    conn.rollback()
                    return None
                conn.execute("UPDATE pairing_codes SET claimed_at = ? WHERE code_hash = ?", (now, code_hash))
                conn.execute(
                    "UPDATE devices SET key_hash = ?, key_prefix = ?, status = 'active', "
                    "activated_at = COALESCE(activated_at, ?), revoked_at = NULL WHERE id = ?",
                    (key_hash, key_prefix, now, row["device_id"]),
                )
                conn.commit()
                device_id = int(row["device_id"])
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
        return self.get_device(device_id)

    # ------------------------------------------------------------- transcriptions

    @staticmethod
    def _transcription(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["device_name"] = "Deleted device" if row["device_deleted_at"] else row["device_name"]
        item["device_deleted"] = row["device_deleted_at"] is not None
        item.pop("device_deleted_at", None)
        return item

    def insert_transcription(
        self,
        *,
        device_id: int,
        text: str,
        detected_language: str | None,
        language_probability: float | None,
        task: str,
        audio_duration_s: float | None,
        processing_ms: int | None,
        model: str | None,
        endpoint: str | None,
        client_user_agent: str | None,
    ) -> dict[str, Any] | None:
        created_at = utc_now_iso()
        try:
            with self._write_lock, self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO transcriptions (device_id, created_at, text, detected_language, "
                    "language_probability, task, audio_duration_s, processing_ms, model, endpoint, "
                    "client_user_agent) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        device_id,
                        created_at,
                        text,
                        detected_language,
                        language_probability,
                        task,
                        audio_duration_s,
                        processing_ms,
                        model,
                        endpoint,
                        (client_user_agent or "")[:500] or None,
                    ),
                )
                row_id = int(cur.lastrowid)
        except sqlite3.IntegrityError:
            # The device was hard-deleted while this request was transcribing: the caller
            # still gets its text, the history simply does not keep it.
            return None
        return self.get_transcription(row_id)

    def get_transcription(self, row_id: int) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(TRANSCRIPTION_QUERY + " WHERE t.id = ?", (row_id,)).fetchone()
        finally:
            conn.close()
        return self._transcription(row) if row else None

    def list_transcriptions(
        self,
        *,
        device_id: int | None = None,
        q: str | None = None,
        before: tuple[str, int] | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], bool]:
        clauses: list[str] = []
        params: list[Any] = []
        if device_id is not None:
            clauses.append("t.device_id = ?")
            params.append(device_id)
        query = fts_query(q or "")
        if query:
            clauses.append(
                "t.id IN (SELECT rowid FROM transcriptions_fts WHERE transcriptions_fts MATCH ?)"
            )
            params.append(query)
        elif (q or "").strip():
            # Punctuation/emoji-only search: nothing can match, not "everything matches".
            return [], False
        if before is not None:
            clauses.append("(t.created_at, t.id) < (?, ?)")
            params.extend([before[0], before[1]])
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit + 1)
        conn = self._connect()
        try:
            rows = conn.execute(
                TRANSCRIPTION_QUERY + where + " ORDER BY t.created_at DESC, t.id DESC LIMIT ?", params
            ).fetchall()
        finally:
            conn.close()
        has_more = len(rows) > limit
        return [self._transcription(row) for row in rows[:limit]], has_more

    def delete_transcription(self, row_id: int) -> bool:
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM transcriptions WHERE id = ?", (row_id,))
            return cur.rowcount > 0

    def stats(self) -> dict[str, Any]:
        local_now = datetime.now().astimezone()
        local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = local_midnight.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM transcriptions").fetchone()[0]
            today_count = conn.execute(
                "SELECT COUNT(*) FROM transcriptions WHERE created_at >= ?", (today,)
            ).fetchone()[0]
            devices = conn.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status = 'active' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS active, "
                "SUM(CASE WHEN status = 'pending' AND deleted_at IS NULL THEN 1 ELSE 0 END) AS pending "
                "FROM devices"
            ).fetchone()
            last = conn.execute("SELECT MAX(created_at) FROM transcriptions").fetchone()[0]
        finally:
            conn.close()
        return {
            "transcriptions_total": total,
            "transcriptions_today": today_count,
            "last_transcription_at": last,
            "devices_total": devices["total"] or 0,
            "devices_active": devices["active"] or 0,
            "devices_pending": devices["pending"] or 0,
        }

    def iter_transcriptions(self, page_size: int = 2000) -> Iterator[list[dict[str, Any]]]:
        """Every transcript in chronological order, one keyset page at a time.

        A fresh connection per page: the export streams from a worker thread and must not
        hold a read transaction (or a connection) across yields.
        """
        after: tuple[str, int] = ("", 0)
        while True:
            conn = self._connect()
            try:
                rows = conn.execute(
                    TRANSCRIPTION_QUERY
                    + " WHERE (t.created_at, t.id) > (?, ?) ORDER BY t.created_at ASC, t.id ASC LIMIT ?",
                    (after[0], after[1], page_size),
                ).fetchall()
            finally:
                conn.close()
            if not rows:
                return
            after = (rows[-1]["created_at"], rows[-1]["id"])
            yield [self._transcription(row) for row in rows]

    def all_transcriptions(self) -> list[dict[str, Any]]:
        """Every transcript in chronological order (used by the data export)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                TRANSCRIPTION_QUERY + " ORDER BY t.created_at ASC, t.id ASC"
            ).fetchall()
        finally:
            conn.close()
        return [self._transcription(row) for row in rows]

    def clear_transcriptions(self) -> int:
        with self._write_lock:
            with self._connect() as conn:
                cur = conn.execute("DELETE FROM transcriptions")
                count = cur.rowcount
                # Merge FTS segments so deleted tokens leave the index blobs too.
                conn.execute("INSERT INTO transcriptions_fts(transcriptions_fts) VALUES('optimize')")
            conn = self._connect()
            try:
                conn.execute("VACUUM")
            finally:
                conn.close()
        return count

    # ------------------------------------------------------------------ settings

    def get_settings(self) -> dict[str, str]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        finally:
            conn.close()
        return {row["key"]: row["value"] for row in rows}

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        conn = self._connect()
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        finally:
            conn.close()
        return row["value"] if row else default

    def set_settings(self, values: dict[str, str]) -> None:
        if not values:
            return
        now = utc_now_iso()
        with self._write_lock, self._connect() as conn:
            conn.executemany(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                [(key, value, now) for key, value in values.items()],
            )

    def set_setting(self, key: str, value: str) -> None:
        self.set_settings({key: value})

    def delete_setting(self, key: str) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute("DELETE FROM settings WHERE key = ?", (key,))
