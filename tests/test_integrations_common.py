from __future__ import annotations

import unittest

from watermark_llamacpp.config import WatermarkConfig
from watermark_llamacpp.integrations.common import (
    KeyedSparseGreenlist,
    TagTextPostProcessor,
    normalize_token_ids,
)


class IntegrationCommonTests(unittest.TestCase):
    def test_normalize_token_ids(self) -> None:
        self.assertEqual(normalize_token_ids([1, 2, 3]), [1, 2, 3])
        self.assertEqual(normalize_token_ids([[4, 5]]), [4, 5])

    def test_apply_bias_changes_logits(self) -> None:
        cfg = WatermarkConfig()
        core = KeyedSparseGreenlist(cfg=cfg, model_name="demo-model", key_id=1, date_str="20260101")
        logits = [0.0] * 100
        core.apply_bias(logits=logits, context_tokens=[11, 22, 33], vocab_size=100)
        self.assertTrue(any(v > 0.0 for v in logits))

    def test_tag_postprocessor_inserts_zero_width(self) -> None:
        cfg = WatermarkConfig()
        tagger = TagTextPostProcessor(cfg=cfg, model_name="demo-model", key_id=1)
        out = tagger.inject("hello world", finalize=True)
        self.assertNotEqual(out, "hello world")
        self.assertIn("\u2063", out)
        self.assertIn("\u2064", out)


if __name__ == "__main__":
    unittest.main()
