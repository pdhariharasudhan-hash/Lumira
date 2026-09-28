import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from app.services.persistence.atomic_json_store import AtomicJsonStore, PersistenceIntegrityError


class LocalAuthService:
    """Signed bearer tokens for the trusted single-user local backend."""

    TOKEN_LIFETIME_SECONDS = 3600
    ISSUER = "lumira-local"

    def __init__(self, key_path: str | Path | None = None):
        self.key_path = Path(key_path or os.environ.get("LUMIRA_API_KEY_FILE", "memory/local_api_signing_key.json"))
        self.store = AtomicJsonStore(self.key_path)

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _signing_key(self) -> bytes:
        if not self.key_path.exists():
            key = secrets.token_bytes(32)
            self.store.write({"schema_version": 1, "key": self._encode(key)})
            try:
                os.chmod(self.key_path, 0o600)
            except OSError:
                pass
        document = self.store.read()
        if not isinstance(document, dict) or document.get("schema_version") != 1 or not isinstance(document.get("key"), str):
            raise PersistenceIntegrityError("Local API signing key is invalid")
        try:
            key = self._decode(document["key"])
        except (ValueError, TypeError) as exc:
            raise PersistenceIntegrityError("Local API signing key is invalid") from exc
        if len(key) < 32:
            raise PersistenceIntegrityError("Local API signing key is too short")
        return key

    def issue_local_token(self) -> dict:
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "iss": self.ISSUER,
            "sub": "local",
            "owner_id": "local",
            "iat": now,
            "exp": now + self.TOKEN_LIFETIME_SECONDS,
            "jti": secrets.token_urlsafe(18),
        }
        signing_input = f"{self._encode(json.dumps(header, separators=(',', ':')).encode())}.{self._encode(json.dumps(payload, separators=(',', ':')).encode())}"
        signature = hmac.new(self._signing_key(), signing_input.encode("ascii"), hashlib.sha256).digest()
        return {"access_token": f"{signing_input}.{self._encode(signature)}", "token_type": "bearer", "expires_in": self.TOKEN_LIFETIME_SECONDS, "owner_id": "local"}

    def verify(self, token: str) -> dict | None:
        if not isinstance(token, str) or len(token) > 4096:
            return None
        try:
            header_part, payload_part, signature_part = token.split(".")
            signing_input = f"{header_part}.{payload_part}"
            expected = hmac.new(self._signing_key(), signing_input.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, self._decode(signature_part)):
                return None
            header = json.loads(self._decode(header_part))
            payload = json.loads(self._decode(payload_part))
            if header != {"alg": "HS256", "typ": "JWT"}:
                return None
            if payload.get("iss") != self.ISSUER or payload.get("sub") != "local" or payload.get("owner_id") != "local":
                return None
            if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(time.time()):
                return None
            if not isinstance(payload.get("iat"), int) or payload["iat"] > int(time.time()) + 60:
                return None
            return {"subject": "local", "owner_id": "local", "expires_at": payload["exp"]}
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, PersistenceIntegrityError):
            return None
