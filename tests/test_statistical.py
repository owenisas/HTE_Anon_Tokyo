import unittest

from watermark_llamacpp.keys import derive_context_seed, derive_step_key
from watermark_llamacpp.statistical import score_sparse_watermark, token_is_green


class StatisticalTests(unittest.TestCase):
    def test_dense_green_predicate(self):
        self.assertIsInstance(token_is_green(1, seed=2, greenlist_ratio=0.25), bool)

    def test_sparse_score(self):
        model_id = 3
        key_id = 1
        master = b"m"
        derived = derive_step_key(master, model_id=model_id, date_str="20260225", key_id=key_id)

        seq = [11, 12, 13, 14, 15, 16, 17]
        score = score_sparse_watermark(
            token_ids=seq,
            derived_key=derived,
            vocab_size=32000,
            context_width=2,
            greenlist_ratio=0.25,
            max_bias_tokens=256,
        )
        self.assertEqual(score.total_scored, len(seq) - 2)


if __name__ == "__main__":
    unittest.main()
