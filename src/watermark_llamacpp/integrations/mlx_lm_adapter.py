from __future__ import annotations

from typing import Any

from ..config import WatermarkConfig
from .common import KeyedSparseGreenlist, TagTextPostProcessor, normalize_token_ids


class MLXLMLogitsProcessor:
    """Callable for MLX-LM generate/stream_generate logits_processors lists."""

    def __init__(self, *, cfg: WatermarkConfig, model_name: str, key_id: int | None = None):
        self._core = KeyedSparseGreenlist(cfg=cfg, model_name=model_name, key_id=key_id)

    def __call__(self, token_ids: Any, logits: Any) -> Any:
        context = normalize_token_ids(token_ids)
        if getattr(logits, "ndim", 1) == 2:
            row = logits[0]
            vocab_size = int(row.shape[-1])
            self._core.apply_bias(logits=row, context_tokens=context, vocab_size=vocab_size)
            return logits
        vocab_size = int(logits.shape[-1])
        self._core.apply_bias(logits=logits, context_tokens=context, vocab_size=vocab_size)
        return logits


def build_mlx_tag_postprocessor(
    *, cfg: WatermarkConfig, model_name: str, key_id: int | None = None
) -> TagTextPostProcessor:
    return TagTextPostProcessor(cfg=cfg, model_name=model_name, key_id=key_id)
