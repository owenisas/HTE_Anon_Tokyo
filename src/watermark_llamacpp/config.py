from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

WatermarkMode = Literal["hybrid", "statistical_only", "tag_only"]


@dataclass(slots=True)
class StatisticalConfig:
    context_width: int = 2
    greenlist_ratio: float = 0.25
    bias_delta: float = 1.0
    max_bias_tokens: int = 2048
    z_threshold_verified: float = 4.0
    z_threshold_likely: float = 2.5


@dataclass(slots=True)
class TagConfig:
    repeat_interval_tokens: int = 160
    zero_char: str = "\u200b"  # ZWSP
    one_char: str = "\u200c"  # ZWNJ
    start_char: str = "\u2063"  # INVISIBLE SEPARATOR
    end_char: str = "\u2064"  # INVISIBLE PLUS


@dataclass(slots=True)
class WatermarkConfig:
    schema_version: int = 1
    issuer_id: int = 1
    active_key_id: int = 1
    model_id_map: dict[str, int] = field(default_factory=dict)
    model_version_map: dict[str, int] = field(default_factory=dict)
    statistical: StatisticalConfig = field(default_factory=StatisticalConfig)
    tag: TagConfig = field(default_factory=TagConfig)

    def model_id_for(self, model_name: str | None) -> int:
        if not model_name:
            return 0
        return self.model_id_map.get(model_name, 0)

    def model_version_id_for(self, model_name: str | None) -> int:
        if not model_name:
            return 0
        return self.model_version_map.get(model_name, 0)


@dataclass(slots=True)
class EffectiveWatermarkRequest:
    enabled: bool = True
    mode: WatermarkMode = "hybrid"
    key_id: int | None = None
    opt_out_token: str | None = None


def parse_effective_request(payload: dict[str, Any] | None) -> EffectiveWatermarkRequest:
    if not payload:
        return EffectiveWatermarkRequest()
    mode = payload.get("mode", "hybrid")
    if mode not in {"hybrid", "statistical_only", "tag_only"}:
        mode = "hybrid"
    key_id = payload.get("key_id")
    try:
        key_id = int(key_id) if key_id is not None else None
    except (TypeError, ValueError):
        key_id = None
    enabled_raw = payload.get("enabled", True)
    if isinstance(enabled_raw, bool):
        enabled = enabled_raw
    elif isinstance(enabled_raw, (int, float)):
        enabled = bool(enabled_raw)
    else:
        enabled = str(enabled_raw).strip().lower() in {"1", "true", "yes", "on"}
    return EffectiveWatermarkRequest(
        enabled=bool(enabled),
        mode=mode,
        key_id=key_id,
        opt_out_token=payload.get("opt_out_token"),
    )
