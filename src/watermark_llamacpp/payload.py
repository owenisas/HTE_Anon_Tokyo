from __future__ import annotations

from dataclasses import dataclass


def crc8(data: bytes) -> int:
    crc = 0
    poly = 0x07
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


@dataclass(slots=True)
class PackedMetadata:
    schema_version: int
    issuer_id: int
    model_id: int
    model_version_id: int
    key_id: int


def pack_payload(meta: PackedMetadata) -> int:
    raw56 = (
        ((meta.schema_version & 0xF) << 52)
        | ((meta.issuer_id & 0xFFF) << 40)
        | ((meta.model_id & 0xFFFF) << 24)
        | ((meta.model_version_id & 0xFFFF) << 8)
        | (meta.key_id & 0xFF)
    )
    raw_bytes = raw56.to_bytes(7, "big")
    checksum = crc8(raw_bytes)
    return (raw56 << 8) | checksum


def unpack_payload(payload64: int) -> tuple[PackedMetadata, bool]:
    raw56 = payload64 >> 8
    checksum = payload64 & 0xFF
    raw_bytes = raw56.to_bytes(7, "big")
    valid = crc8(raw_bytes) == checksum

    meta = PackedMetadata(
        schema_version=(raw56 >> 52) & 0xF,
        issuer_id=(raw56 >> 40) & 0xFFF,
        model_id=(raw56 >> 24) & 0xFFFF,
        model_version_id=(raw56 >> 8) & 0xFFFF,
        key_id=raw56 & 0xFF,
    )
    return meta, valid
