from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


class ConsentStoreError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CheckContext:
    check_id: str
    app_id: str
    scope: str
    target_digest: str | None
    decision: str
    expires_at: int
    consent_check_id: str | None = None


@dataclass(frozen=True)
class ConsentRequestRecord:
    request_id: str
    check_id: str
    app_id: str
    scope: str
    target_digest: str
    subject_ref: str
    action_secret_hash: str
    status: str
    expires_at: int


@dataclass(frozen=True)
class TokenRecord:
    jti: str
    request_id: str
    check_id: str
    app_id: str
    scope: str
    target_digest: str
    subject_ref: str
    issued_at: int
    expires_at: int
    request_expires_at: int
    revoked_at: int | None
    request_status: str


class SQLiteConsentStore:
    """Durable consent state for a single-host prototype deployment."""

    def __init__(self, database_path: str) -> None:
        if database_path != ":memory:":
            resolved_path = Path(database_path).expanduser().resolve()
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            self._database_path = str(resolved_path)
        else:
            self._database_path = database_path
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS checks (
                    check_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    target_digest TEXT,
                    decision TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    consent_check_id TEXT
                );
                CREATE TABLE IF NOT EXISTS consent_requests (
                    request_id TEXT PRIMARY KEY,
                    check_id TEXT NOT NULL UNIQUE REFERENCES checks(check_id),
                    app_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    target_digest TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    action_secret_hash TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('pending', 'approved', 'denied', 'revoked')
                    ),
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS consent_tokens (
                    jti TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE
                        REFERENCES consent_requests(request_id),
                    app_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    target_digest TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    revoked_at INTEGER
                );
                CREATE INDEX IF NOT EXISTS consent_tokens_request_id
                    ON consent_tokens(request_id);
                """
            )
            request_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(consent_requests)"
                )
            }
            if "subject_ref" not in request_columns:
                connection.execute(
                    "ALTER TABLE consent_requests ADD COLUMN "
                    "subject_ref TEXT NOT NULL DEFAULT ''"
                )
            check_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(checks)")
            }
            if "consent_check_id" not in check_columns:
                connection.execute(
                    "ALTER TABLE checks ADD COLUMN consent_check_id TEXT"
                )
            token_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(consent_tokens)")
            }
            if "issued_at" not in token_columns:
                connection.execute(
                    "ALTER TABLE consent_tokens ADD COLUMN "
                    "issued_at INTEGER NOT NULL DEFAULT 0"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path, timeout=10, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record_check(self, context: CheckContext) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO checks
                    (check_id, app_id, scope, target_digest, decision, expires_at,
                     consent_check_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    context.check_id,
                    context.app_id,
                    context.scope,
                    context.target_digest,
                    context.decision,
                    context.expires_at,
                    context.consent_check_id,
                ),
            )

    def get_check(
        self, check_id: str, *, app_id: str, now: int
    ) -> CheckContext | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT check_id, app_id, scope, target_digest, decision, expires_at,
                       consent_check_id
                FROM checks WHERE check_id = ? AND app_id = ? AND expires_at > ?
                """,
                (check_id, app_id, now),
            ).fetchone()
        return CheckContext(**dict(row)) if row else None

    def create_request(
        self,
        *,
        request_id: str,
        check_id: str,
        app_id: str,
        subject_ref: str,
        action_secret_hash: str,
        now: int,
        expires_at: int,
    ) -> ConsentRequestRecord:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT check_id, app_id, scope, target_digest, decision, expires_at
                FROM checks
                WHERE check_id = ? AND app_id = ? AND expires_at > ?
                """,
                (check_id, app_id, now),
            ).fetchone()
            if row is None or row["decision"] != "needs_consent":
                raise ConsentStoreError("check_not_eligible")
            if row["target_digest"] is None:
                raise ConsentStoreError("target_required")
            expires_at = min(expires_at, row["expires_at"])
            if expires_at <= now:
                raise ConsentStoreError("check_not_eligible")
            try:
                connection.execute(
                    """
                    INSERT INTO consent_requests
                        (request_id, check_id, app_id, scope, target_digest,
                         subject_ref, action_secret_hash, status, created_at,
                         expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        request_id,
                        check_id,
                        app_id,
                        row["scope"],
                        row["target_digest"],
                        subject_ref,
                        action_secret_hash,
                        now,
                        expires_at,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConsentStoreError("consent_request_exists") from exc
            result = connection.execute(
                """
                SELECT request_id, check_id, app_id, scope, target_digest,
                       subject_ref, action_secret_hash, status, expires_at
                FROM consent_requests WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        assert result is not None
        return ConsentRequestRecord(**dict(result))

    def get_request(self, request_id: str) -> ConsentRequestRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT request_id, check_id, app_id, scope, target_digest,
                       subject_ref, action_secret_hash, status, expires_at
                FROM consent_requests WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        return ConsentRequestRecord(**dict(row)) if row else None

    def transition_pending(
        self,
        *,
        request_id: str,
        action_secret_hash: str,
        action: str,
        now: int,
        token: dict[str, Any] | None = None,
    ) -> bool:
        if action not in {"approved", "denied"}:
            raise ValueError("Invalid pending consent transition.")
        if (action == "approved") != (token is not None):
            raise ValueError("Approval must atomically include exactly one token.")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            request = connection.execute(
                """
                SELECT app_id, scope, target_digest, subject_ref
                FROM consent_requests
                WHERE request_id = ? AND action_secret_hash = ?
                  AND status = 'pending' AND expires_at > ?
                """,
                (request_id, action_secret_hash, now),
            ).fetchone()
            if request is None:
                return False
            changed = connection.execute(
                """
                UPDATE consent_requests SET status = ?
                WHERE request_id = ? AND status = 'pending' AND expires_at > ?
                """,
                (action, request_id, now),
            ).rowcount
            if changed != 1:
                return False
            if token is not None:
                if action != "approved":
                    raise ValueError("Only approved requests may receive a token.")
                connection.execute(
                    """
                    INSERT INTO consent_tokens
                        (jti, request_id, app_id, scope, target_digest, issued_at,
                         expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        token["jti"],
                        request_id,
                        request["app_id"],
                        request["scope"],
                        request["target_digest"],
                        token["issued_at"],
                        token["expires_at"],
                    ),
                )
            return True

    def revoke(
        self, *, jti: str, action_secret_hash: str, now: int
    ) -> bool:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                """
                UPDATE consent_tokens SET revoked_at = ?
                WHERE jti = ? AND revoked_at IS NULL
                  AND request_id IN (
                    SELECT request_id FROM consent_requests
                    WHERE action_secret_hash = ? AND status = 'approved'
                  )
                """,
                (now, jti, action_secret_hash),
            ).rowcount
            if changed != 1:
                return False
            request_changed = connection.execute(
                """
                UPDATE consent_requests SET status = 'revoked'
                WHERE request_id = (
                    SELECT request_id FROM consent_tokens WHERE jti = ?
                ) AND status = 'approved'
                """,
                (jti,),
            ).rowcount
            if request_changed != 1:
                raise RuntimeError("Token revocation state transition was incomplete.")
            return True

    def get_token(self, jti: str) -> TokenRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT t.jti, t.request_id, t.app_id, t.scope, t.target_digest,
                       r.check_id, r.subject_ref, t.issued_at, t.expires_at,
                       r.expires_at AS request_expires_at,
                       t.revoked_at, r.status AS request_status
                FROM consent_tokens t
                JOIN consent_requests r ON r.request_id = t.request_id
                WHERE t.jti = ?
                """,
                (jti,),
            ).fetchone()
        return TokenRecord(**dict(row)) if row else None

    def get_request_status(
        self, request_id: str, *, action_secret_hash: str
    ) -> ConsentRequestRecord | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT request_id, check_id, app_id, scope, target_digest,
                       subject_ref, action_secret_hash, status, expires_at
                FROM consent_requests
                WHERE request_id = ? AND action_secret_hash = ?
                """,
                (request_id, action_secret_hash),
            ).fetchone()
        return ConsentRequestRecord(**dict(row)) if row else None
