import unittest

from watermark_llamacpp.policy import make_opt_out_token, verify_opt_out_token


class PolicyTests(unittest.TestCase):
    def test_token(self):
        tok = make_opt_out_token({"sub": "x"}, b"secret", ttl_seconds=30)
        ok, _ = verify_opt_out_token(tok, b"secret")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
