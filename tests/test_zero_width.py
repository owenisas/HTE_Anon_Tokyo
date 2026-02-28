import unittest

from watermark_llamacpp.config import TagConfig
from watermark_llamacpp.zero_width import TagInjector, decode_tags_from_text, encode_payload_to_tag


class ZeroWidthTests(unittest.TestCase):
    def test_encode_decode(self):
        cfg = TagConfig()
        payload = 0x1234567890ABCDEF
        tag = encode_payload_to_tag(payload, cfg)
        got = decode_tags_from_text(f"a{tag}b", cfg)
        self.assertEqual(got, [payload])

    def test_finalize_inserts(self):
        inj = TagInjector("<t>", 100)
        out = inj.inject_delta("hello", finalize=True)
        self.assertIn("<t>", out)


if __name__ == "__main__":
    unittest.main()
