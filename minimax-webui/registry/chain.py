"""Local simulated hash-chain for provenance anchoring.

Each block contains:
  - block_num:  auto-incremented
  - prev_hash:  hash of previous block (genesis = 64 zeros)
  - tx_hash:    SHA-256(prev_hash || data_hash || issuer_id || timestamp)
  - data_hash:  SHA-256 of the watermarked text
  - issuer_id:  company that created this record
  - signature:  ECDSA signature from the company's private key
  - timestamp:  ISO-8601 UTC

The chain is backed by SQLite – no external node, no gas fees.
In production, ``tx_hash`` can be submitted to QDay via
``ProvenanceRegistry.anchor(bytes32)``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .db import (
    DB_PATH,
    get_block_by_data_hash,
    get_block_by_tx_hash,
    get_db,
    get_latest_block,
    init_db,
    insert_block,
)


GENESIS_PREV_HASH = "0" * 64  # 32 zero-bytes in hex


@dataclass(slots=True)
class ChainReceipt:
    """Returned after successfully anchoring a record."""
    tx_hash: str
    block_num: int
    data_hash: str
    issuer_id: int
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ChainRecord:
    """A block from the chain."""
    block_num: int
    prev_hash: str
    tx_hash: str
    data_hash: str
    issuer_id: int
    signature_hex: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class SimulatedChain:
    """SQLite-backed hash-chain."""

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = db_path
        init_db(db_path)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def anchor(
        self,
        data_hash: str,
        issuer_id: int,
        signature_hex: str,
        metadata: dict | None = None,
    ) -> ChainReceipt:
        """Anchor a data hash to the chain.  Returns a receipt."""
        ts = datetime.now(timezone.utc).isoformat()

        with get_db(self.db_path) as conn:
            latest = get_latest_block(conn)
            prev_hash = latest["tx_hash"] if latest else GENESIS_PREV_HASH

            # Deterministic tx hash
            preimage = f"{prev_hash}{data_hash}{issuer_id}{ts}"
            tx_hash = hashlib.sha256(preimage.encode()).hexdigest()

            payload_json = json.dumps(metadata or {})

            block_num = insert_block(
                conn,
                prev_hash=prev_hash,
                tx_hash=tx_hash,
                data_hash=data_hash,
                issuer_id=issuer_id,
                signature_hex=signature_hex,
                payload_json=payload_json,
            )

        return ChainReceipt(
            tx_hash=tx_hash,
            block_num=block_num,
            data_hash=data_hash,
            issuer_id=issuer_id,
            timestamp=ts,
        )

    # ------------------------------------------------------------------
    # Read / verify
    # ------------------------------------------------------------------

    def lookup(self, data_hash: str) -> ChainRecord | None:
        """Find a block by its data_hash."""
        with get_db(self.db_path) as conn:
            row = get_block_by_data_hash(conn, data_hash)
            if row is None:
                return None
            return self._row_to_record(row)

    def lookup_tx(self, tx_hash: str) -> ChainRecord | None:
        """Find a block by its tx_hash."""
        with get_db(self.db_path) as conn:
            row = get_block_by_tx_hash(conn, tx_hash)
            if row is None:
                return None
            return self._row_to_record(row)

    def verify(self, data_hash: str, tx_hash: str) -> bool:
        """Confirm that a data_hash is anchored with the given tx_hash."""
        with get_db(self.db_path) as conn:
            row = get_block_by_data_hash(conn, data_hash)
            if row is None:
                return False
            return row["tx_hash"] == tx_hash

    def chain_length(self) -> int:
        """Number of blocks in the chain."""
        with get_db(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM chain_blocks").fetchone()
            return row["c"]

    def validate_chain(self) -> tuple[bool, str]:
        """Walk the full chain and verify prev_hash linkage.

        Returns (valid, message).
        """
        with get_db(self.db_path) as conn:
            blocks = conn.execute(
                "SELECT * FROM chain_blocks ORDER BY block_num ASC"
            ).fetchall()

        if not blocks:
            return True, "empty chain"

        # First block must point to genesis
        if blocks[0]["prev_hash"] != GENESIS_PREV_HASH:
            return False, f"block {blocks[0]['block_num']}: invalid genesis prev_hash"

        for i in range(1, len(blocks)):
            if blocks[i]["prev_hash"] != blocks[i - 1]["tx_hash"]:
                return (
                    False,
                    f"block {blocks[i]['block_num']}: prev_hash mismatch "
                    f"(expected {blocks[i-1]['tx_hash']}, got {blocks[i]['prev_hash']})",
                )

        return True, f"valid chain with {len(blocks)} blocks"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row) -> ChainRecord:
        return ChainRecord(
            block_num=row["block_num"],
            prev_hash=row["prev_hash"],
            tx_hash=row["tx_hash"],
            data_hash=row["data_hash"],
            issuer_id=row["issuer_id"],
            signature_hex=row["signature_hex"],
            timestamp=row["timestamp"],
        )
