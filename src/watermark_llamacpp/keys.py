from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime


def hkdf_sha256(ikm: bytes, info: bytes, length: int = 32, salt: bytes = b"") -> bytes:
    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm += t
        counter += 1
    return okm[:length]


def _load_master_key_map_from_env() -> dict[int, bytes]:
    raw_map = os.environ.get("WATERMARK_MASTER_KEYS")
    if raw_map:
        parsed = json.loads(raw_map)
        out: dict[int, bytes] = {}
        for key_id, b64 in parsed.items():
            out[int(key_id)] = base64.b64decode(b64)
        if out:
            return out

    # Fallback single-key mode.
    single = os.environ.get("WATERMARK_MASTER_KEY")
    if single:
        return {1: base64.b64decode(single)}

    # Deterministic dev fallback (not for production).
    return {1: b"dev-only-master-key-change-me"}


def get_master_key(key_id: int | None) -> tuple[int, bytes]:
    keys = _load_master_key_map_from_env()
    if key_id is not None and key_id in keys:
        return key_id, keys[key_id]
    first_id = sorted(keys.keys())[0]
    return first_id, keys[first_id]


def derive_step_key(
    master_key: bytes,
    *,
    model_id: int,
    date_str: str | None,
    key_id: int,
) -> bytes:
    if date_str is None:
        date_str = datetime.now(UTC).strftime("%Y%m%d")
    info = f"{model_id}|{date_str}|{key_id}".encode("utf-8")
    return hkdf_sha256(master_key, info, length=32)


def derive_context_seed(derived_key: bytes, context_tokens: list[int]) -> int:
    msg = b"|".join(str(t).encode("ascii") for t in context_tokens)
    digest = hmac.new(derived_key, msg, hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big", signed=False)
