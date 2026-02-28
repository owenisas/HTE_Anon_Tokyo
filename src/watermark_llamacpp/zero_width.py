from __future__ import annotations

import re
import string

from .config import TagConfig

SAFE_BOUNDARY_CHARS = set(string.whitespace + ".,;:!?)]}\"'")


def encode_payload_to_tag(payload64: int, cfg: TagConfig) -> str:
    bits = f"{payload64:064b}"
    body = "".join(cfg.one_char if b == "1" else cfg.zero_char for b in bits)
    return f"{cfg.start_char}{body}{cfg.end_char}"


def decode_tags_from_text(text: str, cfg: TagConfig) -> list[int]:
    start = re.escape(cfg.start_char)
    end = re.escape(cfg.end_char)
    zero = re.escape(cfg.zero_char)
    one = re.escape(cfg.one_char)
    pattern = re.compile(f"{start}([{zero}{one}]{{64}}){end}")
    out: list[int] = []
    for m in pattern.finditer(text):
        bits = "".join("1" if ch == cfg.one_char else "0" for ch in m.group(1))
        out.append(int(bits, 2))
    return out


def insert_tag_at_safe_boundary(text: str, tag: str) -> str:
    if not text:
        return tag
    for i in range(len(text) - 1, -1, -1):
        if text[i] in SAFE_BOUNDARY_CHARS:
            return text[: i + 1] + tag + text[i + 1 :]
    return text + tag


class TagInjector:
    def __init__(self, tag: str, repeat_interval_tokens: int):
        self.tag = tag
        self.repeat_interval_tokens = repeat_interval_tokens
        self.approx_tokens_since_last = 0

    def _count_approx_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len([tok for tok in text.split() if tok])

    def inject_delta(self, text: str, *, finalize: bool = False) -> str:
        self.approx_tokens_since_last += self._count_approx_tokens(text)
        num_insertions = 0
        if self.repeat_interval_tokens > 0:
            num_insertions = self.approx_tokens_since_last // self.repeat_interval_tokens
        if finalize:
            num_insertions = max(1, num_insertions)
        if num_insertions <= 0:
            return text
        self.approx_tokens_since_last = (
            0 if finalize else self.approx_tokens_since_last % self.repeat_interval_tokens
        )
        out = text
        for _ in range(num_insertions):
            out = insert_tag_at_safe_boundary(out, self.tag)
        return out
