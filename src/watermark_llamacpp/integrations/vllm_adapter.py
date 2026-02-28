from __future__ import annotations

from typing import Any

from ..config import WatermarkConfig
from .common import KeyedSparseGreenlist, TagTextPostProcessor, normalize_token_ids


class VLLMStatisticalLogitsProcessor:
    """Callable compatible with vLLM custom logits processor hook."""

    def __init__(self, *, cfg: WatermarkConfig, model_name: str, key_id: int | None = None):
        self._core = KeyedSparseGreenlist(cfg=cfg, model_name=model_name, key_id=key_id)

    def __call__(self, token_ids: Any, scores: Any) -> Any:
        context = normalize_token_ids(token_ids)
        if getattr(scores, "ndim", 1) == 2:
            row = scores[0]
            vocab_size = int(row.shape[-1])
            self._core.apply_bias(logits=row, context_tokens=context, vocab_size=vocab_size)
            return scores
        vocab_size = int(scores.shape[-1])
        self._core.apply_bias(logits=scores, context_tokens=context, vocab_size=vocab_size)
        return scores


def build_vllm_tag_postprocessor(
    *, cfg: WatermarkConfig, model_name: str, key_id: int | None = None
) -> TagTextPostProcessor:
    return TagTextPostProcessor(cfg=cfg, model_name=model_name, key_id=key_id)
