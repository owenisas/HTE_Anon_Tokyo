from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from .config import WatermarkConfig
from .keys import derive_step_key, get_master_key
from .payload import unpack_payload
from .statistical import (
    StatisticalScore,
    StatisticalWatermarkDetector,
    score_sparse_watermark,
)
from .zero_width import decode_tags_from_text


class TokenizerLike(Protocol):
    def encode(self, text: str) -> list[int]:
        ...


@dataclass(slots=True)
class VerifyResult:
    status: str
    statistical_score: StatisticalScore | None
    payload: dict[str, Any] | None
    key_id: int | None
    explanations: list[str]


class WatermarkDetector:
    def __init__(self, cfg: WatermarkConfig):
        self.cfg = cfg

    @staticmethod
    def _candidate_dates(days_back: int = 7) -> list[str]:
        now = datetime.now(UTC).date()
        return [(now - timedelta(days=i)).strftime("%Y%m%d") for i in range(days_back + 1)]

    def _score_statistical(
        self,
        token_ids: list[int],
        model_id: int,
        key_id: int,
        days_back: int,
        vocab_size: int | None = None,
    ) -> StatisticalScore | None:
        if not token_ids:
            return None

        master_id, master_key = get_master_key(key_id)
        detector = StatisticalWatermarkDetector(
            context_width=self.cfg.statistical.context_width,
            greenlist_ratio=self.cfg.statistical.greenlist_ratio,
        )

        best: StatisticalScore | None = None
        for date_str in self._candidate_dates(days_back):
            dkey = derive_step_key(
                master_key,
                model_id=model_id,
                date_str=date_str,
                key_id=master_id,
            )
            if vocab_size is None:
                score = detector.score(token_ids, dkey)
            else:
                score = score_sparse_watermark(
                    token_ids=token_ids,
                    derived_key=dkey,
                    vocab_size=vocab_size,
                    context_width=self.cfg.statistical.context_width,
                    greenlist_ratio=self.cfg.statistical.greenlist_ratio,
                    max_bias_tokens=self.cfg.statistical.max_bias_tokens,
                )
            if best is None or score.z_score > best.z_score:
                best = score
        return best

    def verify(
        self,
        *,
        text: str,
        model_hint: str | None = None,
        token_ids: list[int] | None = None,
        tokenizer: TokenizerLike | None = None,
        vocab_size: int | None = None,
        days_back: int = 7,
    ) -> VerifyResult:
        explanations: list[str] = []

        payload = None
        payload_key_id: int | None = None
        decoded = decode_tags_from_text(text, self.cfg.tag)
        if decoded:
            explanations.append(f"found {len(decoded)} zero-width tag candidate(s)")
        for candidate in decoded:
            meta, valid = unpack_payload(candidate)
            if valid:
                payload = asdict(meta)
                payload_key_id = meta.key_id
                explanations.append("valid CRC metadata payload recovered")
                break
        if payload is None and decoded:
            explanations.append("zero-width tags found but CRC invalid")

        if token_ids is None and tokenizer is not None:
            try:
                token_ids = tokenizer.encode(text)
            except Exception as exc:
                explanations.append(f"tokenization failed for statistical scoring: {exc}")

        model_id = self.cfg.model_id_for(model_hint)
        stat_score: StatisticalScore | None = None
        stat_key_id = payload_key_id if payload_key_id is not None else self.cfg.active_key_id

        if token_ids:
            stat_score = self._score_statistical(
                token_ids=token_ids,
                model_id=model_id,
                key_id=stat_key_id,
                days_back=days_back,
                vocab_size=vocab_size,
            )
            if stat_score:
                explanations.append(
                    f"statistical z-score={stat_score.z_score:.3f} over {stat_score.total_scored} tokens"
                )

        status = "none"
        if payload is not None:
            status = "verified"
        elif stat_score is not None:
            if stat_score.z_score >= self.cfg.statistical.z_threshold_verified:
                status = "verified"
            elif stat_score.z_score >= self.cfg.statistical.z_threshold_likely:
                status = "likely"

        return VerifyResult(
            status=status,
            statistical_score=stat_score,
            payload=payload,
            key_id=payload_key_id if payload_key_id is not None else stat_key_id,
            explanations=explanations,
        )
