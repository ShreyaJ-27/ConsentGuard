from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time
from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
)

from gateway.app.services.consent_store import (
    ConsentRequestRecord,
    ConsentStoreError,
    SQLiteConsentStore,
)


class ConsentState(str, Enum):
    MISSING = "missing"
    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_ISSUER = "invalid_issuer"
    INVALID_TOKEN = "invalid_token"
    EXPIRED = "expired"
    REVOKED = "revoked"
    WRONG_SCOPE = "wrong_scope"
    WRONG_APP = "wrong_app"
    FACE_MISMATCH = "face_mismatch"
    UNAVAILABLE = "unavailable"


class ConsentVerifier(Protocol):
    def verify(
        self,
        token: str | None,
        *,
        app_id: str,
        scope: str,
        target_ref: str | None = None,
    ) -> ConsentState: ...


class UnavailableConsentVerifier:
    """Safe integration boundary when consent token verification is not configured."""

    def verify(
        self,
        token: str | None,
        *,
        app_id: str,
        scope: str,
        target_ref: str | None = None,
    ) -> ConsentState:
        del app_id, scope, target_ref
        return ConsentState.MISSING if token is None else ConsentState.UNAVAILABLE


def target_reference_digest(target_ref: str) -> str:
    return hashlib.sha256(target_ref.encode("utf-8")).hexdigest()


def action_secret_digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def load_signing_key(path: str) -> Ed25519PrivateKey:
    try:
        key_data = Path(path).expanduser().read_bytes()
        key = serialization.load_pem_private_key(key_data, password=None)
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError("Unable to load configured Ed25519 signing key.") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Consent signing key must be an Ed25519 private key.")
    return key


class ConsentTokenService:
    def __init__(
        self,
        *,
        store: SQLiteConsentStore,
        signing_key: Ed25519PrivateKey,
        issuer: str,
        token_ttl_seconds: int,
    ) -> None:
        self._store = store
        self._signing_key = signing_key
        self._public_key: Ed25519PublicKey = signing_key.public_key()
        self._issuer = issuer
        self._token_ttl_seconds = token_ttl_seconds
        self._kid = hashlib.sha256(
            self._public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).hexdigest()[:16]

    @property
    def key_id(self) -> str:
        return self._kid

    def approve(
        self, request: ConsentRequestRecord, *, action_secret: str
    ) -> tuple[str, int]:
        now = int(time.time())
        jti = str(uuid4())
        expires_at = min(now + self._token_ttl_seconds, request.expires_at)
        claims = {
            "iss": self._issuer,
            "aud": request.app_id,
            "iat": now,
            "exp": expires_at,
            "jti": jti,
            "sub": request.subject_ref,
            "consent_request_id": request.request_id,
            "scope": request.scope,
            "target_ref": request.target_digest,
        }
        encoded = jwt.encode(
            claims,
            self._signing_key,
            algorithm="EdDSA",
            headers={"kid": self._kid, "typ": "JWT"},
        )
        changed = self._store.transition_pending(
            request_id=request.request_id,
            action_secret_hash=action_secret_digest(action_secret),
            action="approved",
            now=now,
            token={"jti": jti, "issued_at": now, "expires_at": expires_at},
        )
        if not changed:
            raise ConsentStoreError("consent_transition_rejected")
        return encoded, expires_at

    def deny(self, request_id: str, *, action_secret: str) -> None:
        changed = self._store.transition_pending(
            request_id=request_id,
            action_secret_hash=action_secret_digest(action_secret),
            action="denied",
            now=int(time.time()),
        )
        if not changed:
            raise ConsentStoreError("consent_transition_rejected")

    def revoke(self, jti: str, *, action_secret: str) -> None:
        changed = self._store.revoke(
            jti=jti,
            action_secret_hash=action_secret_digest(action_secret),
            now=int(time.time()),
        )
        if not changed:
            raise ConsentStoreError("consent_transition_rejected")

    def verify(
        self,
        token: str | None,
        *,
        app_id: str,
        scope: str,
        target_ref: str | None = None,
        check_id: str | None = None,
    ) -> ConsentState:
        if token is None:
            return ConsentState.MISSING
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "EdDSA" or header.get("kid") != self._kid:
                return ConsentState.INVALID_SIGNATURE
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=["EdDSA"],
                audience=app_id,
                issuer=self._issuer,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "iat",
                        "exp",
                        "jti",
                        "sub",
                        "consent_request_id",
                        "scope",
                        "target_ref",
                    ]
                },
            )
        except ExpiredSignatureError:
            return ConsentState.EXPIRED
        except InvalidAudienceError:
            return ConsentState.WRONG_APP
        except InvalidIssuerError:
            return ConsentState.INVALID_ISSUER
        except InvalidSignatureError:
            return ConsentState.INVALID_SIGNATURE
        except (InvalidTokenError, TypeError, ValueError):
            return ConsentState.INVALID_TOKEN

        if (
            not isinstance(claims["jti"], str)
            or not claims["jti"]
            or not isinstance(claims["sub"], str)
            or not claims["sub"]
            or not isinstance(claims["consent_request_id"], str)
            or not claims["consent_request_id"]
            or not isinstance(claims["scope"], str)
            or not isinstance(claims["target_ref"], str)
            or claims["aud"] != app_id
        ):
            return ConsentState.INVALID_TOKEN
        if claims["scope"] != scope:
            return ConsentState.WRONG_SCOPE
        if target_ref is None or not hmac.compare_digest(
            str(claims["target_ref"]), target_reference_digest(target_ref)
        ):
            return ConsentState.FACE_MISMATCH

        try:
            record = self._store.get_token(str(claims["jti"]))
        except sqlite3.Error:
            return ConsentState.UNAVAILABLE
        if record is None:
            return ConsentState.UNAVAILABLE
        if (
            record.app_id != app_id
            or (check_id is not None and record.check_id != check_id)
            or claims["aud"] != app_id
            or record.scope != scope
            or record.target_digest != claims["target_ref"]
            or record.request_id != claims["consent_request_id"]
            or record.subject_ref != claims["sub"]
            or record.issued_at != claims["iat"]
            or record.expires_at != claims["exp"]
        ):
            return ConsentState.INVALID_TOKEN
        if record.revoked_at is not None or record.request_status == "revoked":
            return ConsentState.REVOKED
        if record.request_status != "approved":
            return ConsentState.UNAVAILABLE
        if min(record.expires_at, record.request_expires_at) <= int(time.time()):
            return ConsentState.EXPIRED
        return ConsentState.VALID


def new_demo_action_secret() -> str:
    return secrets.token_urlsafe(32)
