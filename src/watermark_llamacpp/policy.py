from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + pad)


def get_opt_out_secret() -> bytes:
    secret = os.environ.get("WATERMARK_OPTOUT_SECRET")
    if secret:
        return secret.encode("utf-8")
    return b"dev-only-optout-secret-change-me"


def make_opt_out_token(payload: dict, secret: bytes, *, ttl_seconds: int = 3600) -> str:
    body = dict(payload)
    body.setdefault("iat", int(time.time()))
    body.setdefault("exp", int(time.time()) + ttl_seconds)
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret, raw, hashlib.sha256).digest()
    return f"{_b64url_encode(raw)}.{_b64url_encode(sig)}"


def verify_opt_out_token(token: str | None, secret: bytes) -> tuple[bool, str]:
    if not token:
        return False, "missing opt_out_token"
    try:
        enc_payload, enc_sig = token.split(".", 1)
        payload = _b64url_decode(enc_payload)
        sig = _b64url_decode(enc_sig)
    except Exception:
        return False, "malformed token"

    expected = hmac.new(secret, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return False, "invalid signature"

    try:
        parsed = json.loads(payload)
    except Exception:
        return False, "invalid JSON payload"

    now = int(time.time())
    exp = int(parsed.get("exp", 0))
    if exp < now:
        return False, "expired token"

    return True, "ok"
