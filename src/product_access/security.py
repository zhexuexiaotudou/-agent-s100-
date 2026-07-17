from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.request
from http.cookies import SimpleCookie

SESSION_COOKIE = "digua_session"


def parse_cookie(header: str | None, name: str = SESSION_COOKIE) -> str | None:
    if not header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(header)
    except Exception:
        return None
    item = jar.get(name)
    return item.value if item else None


def csrf_token(session_token: str) -> str:
    return hashlib.sha256(("digua-csrf-v1:" + session_token).encode("utf-8")).hexdigest()


def valid_csrf(session_token: str, supplied: str | None) -> bool:
    return bool(supplied) and secrets.compare_digest(csrf_token(session_token), str(supplied))


def session_cookie(token: str, *, secure: bool, max_age: int = 86400) -> str:
    parts = [f"{SESSION_COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Lax", f"Max-Age={max_age}"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_session_cookie(*, secure: bool) -> str:
    return session_cookie("deleted", secure=secure, max_age=0)


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _rsa_sha256_verify(signing_input: bytes, signature: bytes, n: int, e: int) -> bool:
    size = (n.bit_length() + 7) // 8
    if len(signature) != size:
        return False
    encoded = pow(int.from_bytes(signature, "big"), e, n).to_bytes(size, "big")
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(signing_input).digest()
    expected = b"\x00\x01" + b"\xff" * (size - len(digest_info) - 3) + b"\x00" + digest_info
    return secrets.compare_digest(encoded, expected)


class CloudflareJwtVerifier:
    """Validate Access RS256 JWTs without storing tunnel credentials."""

    def __init__(self, team_domain: str, audience: str, *, fetcher=None, cache_seconds: int = 3600) -> None:
        self.team_domain = team_domain.strip().rstrip("/")
        if not self.team_domain.startswith("https://"):
            self.team_domain = "https://" + self.team_domain
        self.audience = audience
        self.fetcher = fetcher or self._fetch
        self.cache_seconds = cache_seconds
        self._keys: dict[str, dict] = {}
        self._loaded_at = 0.0

    @staticmethod
    def _fetch(url: str) -> dict:
        with urllib.request.urlopen(url, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))

    def _load_keys(self, *, force: bool = False) -> dict[str, dict]:
        if not force and self._keys and time.time() - self._loaded_at < self.cache_seconds:
            return self._keys
        payload = self.fetcher(self.team_domain + "/cdn-cgi/access/certs")
        self._keys = {str(item.get("kid")): item for item in payload.get("keys", []) if item.get("kid")}
        self._loaded_at = time.time()
        return self._keys

    def verify(self, token: str) -> dict:
        try:
            head_raw, body_raw, sig_raw = token.split(".")
            header = json.loads(_b64url_decode(head_raw))
            claims = json.loads(_b64url_decode(body_raw))
            if header.get("alg") != "RS256":
                return {"ok": False, "error": "unsupported_jwt_algorithm"}
            kid = str(header.get("kid") or "")
            key = self._load_keys().get(kid)
            if not key:
                key = self._load_keys(force=True).get(kid)
            if not key or key.get("kty") != "RSA":
                return {"ok": False, "error": "jwt_key_not_found"}
            n = int.from_bytes(_b64url_decode(str(key["n"])), "big")
            e = int.from_bytes(_b64url_decode(str(key["e"])), "big")
            if not _rsa_sha256_verify((head_raw + "." + body_raw).encode("ascii"), _b64url_decode(sig_raw), n, e):
                return {"ok": False, "error": "jwt_signature_invalid"}
            now = int(time.time())
            if int(claims.get("exp") or 0) <= now:
                return {"ok": False, "error": "jwt_expired"}
            if int(claims.get("nbf") or 0) > now + 30:
                return {"ok": False, "error": "jwt_not_yet_valid"}
            if str(claims.get("iss") or "").rstrip("/") != self.team_domain:
                return {"ok": False, "error": "jwt_issuer_invalid"}
            audiences = claims.get("aud") or []
            if isinstance(audiences, str):
                audiences = [audiences]
            if self.audience not in audiences:
                return {"ok": False, "error": "jwt_audience_invalid"}
            subject = str(claims.get("email") or claims.get("sub") or "").strip().lower()
            if not subject:
                return {"ok": False, "error": "jwt_subject_missing"}
            return {"ok": True, "subject": subject, "claims": claims}
        except Exception as exc:
            return {"ok": False, "error": f"jwt_validation_failed:{type(exc).__name__}"}
