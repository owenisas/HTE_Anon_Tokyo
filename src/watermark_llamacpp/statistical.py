from __future__ import annotations

import math
import heapq
from dataclasses import dataclass

try:
    import torch
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    torch = None  # type: ignore

from .keys import derive_context_seed

_MASK63 = (1 << 63) - 1
_A = 2862933555777941757
_B = 3037000493


def _mix63(x: int) -> int:
    return (_A * (x & _MASK63) + _B) & _MASK63


def token_is_green(token_id: int, *, seed: int, greenlist_ratio: float) -> bool:
    threshold = int(greenlist_ratio * _MASK63)
    h = _mix63(token_id ^ (seed & _MASK63))
    return h < threshold


def build_green_mask(vocab_size: int, *, seed: int, greenlist_ratio: float, device) -> "torch.Tensor":
    if torch is None:  # pragma: no cover - only needed for runtime integration
        raise RuntimeError("torch is required for build_green_mask")
    threshold = int(greenlist_ratio * _MASK63)
    ids = torch.arange(vocab_size, device=device, dtype=torch.int64)
    x = ids ^ (seed & _MASK63)
    x = (_A * x + _B) & _MASK63
    return x < threshold


@dataclass(slots=True)
class StatisticalScore:
    total_scored: int
    green_hits: int
    expected: float
    z_score: float
    p_value_one_sided: float


class StatisticalWatermarkDetector:
    def __init__(self, *, context_width: int, greenlist_ratio: float):
        self.context_width = context_width
        self.greenlist_ratio = greenlist_ratio

    def score(self, token_ids: list[int], derived_key: bytes) -> StatisticalScore:
        if len(token_ids) <= self.context_width:
            return StatisticalScore(0, 0, 0.0, 0.0, 1.0)

        hits = 0
        n = 0
        for idx in range(self.context_width, len(token_ids)):
            context = token_ids[idx - self.context_width : idx]
            seed = derive_context_seed(derived_key, context)
            if token_is_green(token_ids[idx], seed=seed, greenlist_ratio=self.greenlist_ratio):
                hits += 1
            n += 1

        expected = n * self.greenlist_ratio
        var = n * self.greenlist_ratio * (1.0 - self.greenlist_ratio)
        z = 0.0 if var <= 0 else (hits - expected) / math.sqrt(var)
        p = 0.5 * math.erfc(z / math.sqrt(2.0))
        return StatisticalScore(
            total_scored=n,
            green_hits=hits,
            expected=expected,
            z_score=z,
            p_value_one_sided=p,
        )


def select_sparse_green_ids(
    *,
    vocab_size: int,
    seed: int,
    greenlist_ratio: float,
    max_bias_tokens: int,
) -> list[int]:
    if vocab_size <= 0:
        return []
    k = int(vocab_size * greenlist_ratio)
    k = max(1, min(k, max_bias_tokens, vocab_size))
    smallest = heapq.nsmallest(
        k,
        range(vocab_size),
        key=lambda tid: _mix63(tid ^ (seed & _MASK63)),
    )
    return smallest


def score_sparse_watermark(
    *,
    token_ids: list[int],
    derived_key: bytes,
    vocab_size: int,
    context_width: int,
    greenlist_ratio: float,
    max_bias_tokens: int,
) -> StatisticalScore:
    if len(token_ids) <= context_width:
        return StatisticalScore(0, 0, 0.0, 0.0, 1.0)

    k = max(1, min(int(vocab_size * greenlist_ratio), max_bias_tokens, vocab_size))
    p_green = k / float(vocab_size)

    hits = 0
    n = 0
    for idx in range(context_width, len(token_ids)):
        context = token_ids[idx - context_width : idx]
        seed = derive_context_seed(derived_key, context)
        green_set = set(
            select_sparse_green_ids(
                vocab_size=vocab_size,
                seed=seed,
                greenlist_ratio=greenlist_ratio,
                max_bias_tokens=max_bias_tokens,
            )
        )
        if token_ids[idx] in green_set:
            hits += 1
        n += 1

    expected = n * p_green
    var = n * p_green * (1.0 - p_green)
    z = 0.0 if var <= 0 else (hits - expected) / math.sqrt(var)
    p = 0.5 * math.erfc(z / math.sqrt(2.0))
    return StatisticalScore(
        total_scored=n,
        green_hits=hits,
        expected=expected,
        z_score=z,
        p_value_one_sided=p,
    )
