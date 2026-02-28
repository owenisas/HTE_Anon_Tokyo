from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..config import WatermarkConfig
from ..keys import derive_context_seed, derive_step_key, get_master_key
from ..payload import PackedMetadata, pack_payload
from ..statistical import select_sparse_green_ids
from ..zero_width import TagInjector, encode_payload_to_tag


def normalize_token_ids(token_ids: Any) -> list[int]:
    if token_ids is None:
        return []
    if isinstance(token_ids, list):
        if token_ids and isinstance(token_ids[0], list):
            return [int(x) for x in token_ids[0]]
        return [int(x) for x in token_ids]
    tolist = getattr(token_ids, "tolist", None)
    if callable(tolist):
        data = tolist()
        if isinstance(data, list):
            if data and isinstance(data[0], list):
                return [int(x) for x in data[0]]
            return [int(x) for x in data]
    return []


class KeyedSparseGreenlist:
    def __init__(
        self,
        *,
        cfg: WatermarkConfig,
        model_name: str,
        key_id: int | None = None,
        date_str: str | None = None,
    ):
        self.cfg = cfg
        self.model_name = model_name
        selected_key_id, master_key = get_master_key(key_id if key_id is not None else cfg.active_key_id)
        self.key_id = selected_key_id
        if date_str is None:
            date_str = datetime.now(UTC).strftime("%Y%m%d")
        self._derived_key = derive_step_key(
            master_key,
            model_id=cfg.model_id_for(model_name),
            date_str=date_str,
            key_id=selected_key_id,
        )

    def _green_ids(self, *, context_tokens: list[int], vocab_size: int) -> list[int]:
        width = self.cfg.statistical.context_width
        if len(context_tokens) < width:
            return []
        seed = derive_context_seed(self._derived_key, context_tokens[-width:])
        return select_sparse_green_ids(
            vocab_size=vocab_size,
            seed=seed,
            greenlist_ratio=self.cfg.statistical.greenlist_ratio,
            max_bias_tokens=self.cfg.statistical.max_bias_tokens,
        )

    def bias_map(self, *, context_tokens: list[int], vocab_size: int) -> dict[int, float]:
        delta = self.cfg.statistical.bias_delta
        return {tid: delta for tid in self._green_ids(context_tokens=context_tokens, vocab_size=vocab_size)}

    def apply_bias(self, *, logits: Any, context_tokens: list[int], vocab_size: int) -> Any:
        green_ids = self._green_ids(context_tokens=context_tokens, vocab_size=vocab_size)
        if not green_ids:
            return logits
        delta = self.cfg.statistical.bias_delta
        try:
            logits[green_ids] += delta
            return logits
        except Exception:
            for tid in green_ids:
                logits[tid] = logits[tid] + delta
            return logits


class TagTextPostProcessor:
    def __init__(
        self,
        *,
        cfg: WatermarkConfig,
        model_name: str,
        key_id: int | None = None,
    ):
        resolved_key_id = cfg.active_key_id if key_id is None else key_id
        payload64 = pack_payload(
            PackedMetadata(
                schema_version=cfg.schema_version,
                issuer_id=cfg.issuer_id,
                model_id=cfg.model_id_for(model_name),
                model_version_id=cfg.model_version_id_for(model_name),
                key_id=resolved_key_id,
            )
        )
        tag = encode_payload_to_tag(payload64, cfg.tag)
        self._injector = TagInjector(tag, cfg.tag.repeat_interval_tokens)

    def inject(self, text: str, *, finalize: bool = False) -> str:
        return self._injector.inject_delta(text, finalize=finalize)
