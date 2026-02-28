import unittest

from watermark_llamacpp.payload import PackedMetadata, pack_payload, unpack_payload


class PayloadTests(unittest.TestCase):
    def test_roundtrip(self):
        meta = PackedMetadata(1, 123, 4567, 89, 7)
        raw = pack_payload(meta)
        back, valid = unpack_payload(raw)
        self.assertTrue(valid)
        self.assertEqual(back, meta)


if __name__ == "__main__":
    unittest.main()
