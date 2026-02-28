"""Tests for the provenance registry – auth, chain, verification round-trip."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_wm_src = Path(__file__).resolve().parent.parent.parent / "invisible-text-watermark" / "src"
if _wm_src.exists():
    sys.path.insert(0, str(_wm_src))
# Also check under watermark-tools/
_wm_src_alt = Path(__file__).resolve().parent.parent.parent / "watermark-tools" / "invisible-text-watermark" / "src"
if _wm_src_alt.exists():
    sys.path.insert(0, str(_wm_src_alt))

from registry.db import DB_PATH, get_db, init_db, insert_company, get_company_by_issuer
from registry.auth import (
    create_company,
    hash_text,
    sign_hash,
    recover_signer,
    verify_signature,
    verify_signature_by_address,
)
from registry.chain import SimulatedChain, GENESIS_PREV_HASH


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_provenance.db"
    init_db(db_path)
    return db_path


# ======================================================================
# db.py
# ======================================================================

class TestDB:
    def test_init_creates_tables(self, tmp_db):
        with get_db(tmp_db) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            names = {t["name"] for t in tables}
            assert "companies" in names
            assert "responses" in names
            assert "chain_blocks" in names

    def test_insert_and_get_company(self, tmp_db):
        with get_db(tmp_db) as conn:
            insert_company(conn, "TestCorp", 100, "0xAbC123", "04abcdef")
            company = get_company_by_issuer(conn, 100)
            assert company is not None
            assert company["name"] == "TestCorp"
            assert company["eth_address"] == "0xAbC123"
            assert company["active"] == 1

    def test_duplicate_issuer_id_fails(self, tmp_db):
        with get_db(tmp_db) as conn:
            insert_company(conn, "Corp1", 100, "0xABC", "04aaa")
        with pytest.raises(sqlite3.IntegrityError):
            with get_db(tmp_db) as conn:
                insert_company(conn, "Corp2", 100, "0xDEF", "04bbb")


# ======================================================================
# auth.py – ECDSA key management & signatures
# ======================================================================

class TestAuth:
    def test_create_company_returns_credentials(self, tmp_db):
        creds = create_company("Acme Inc", db_path=tmp_db)
        assert creds.issuer_id >= 100
        assert creds.name == "Acme Inc"
        assert creds.eth_address.startswith("0x")
        assert creds.private_key_hex.startswith("0x")
        assert len(creds.private_key_hex) == 66  # 0x + 64 hex chars

    def test_sign_and_recover(self, tmp_db):
        creds = create_company("SignCorp", db_path=tmp_db)
        text = "Hello, provenance world!"
        data_hash = hash_text(text)
        sig = sign_hash(data_hash, creds.private_key_hex)
        recovered = recover_signer(data_hash, sig)
        assert recovered.lower() == creds.eth_address.lower()

    def test_verify_signature_success(self, tmp_db):
        creds = create_company("VerifyCorp", db_path=tmp_db)
        data_hash = hash_text("test content")
        sig = sign_hash(data_hash, creds.private_key_hex)

        result = verify_signature(data_hash, sig, creds.issuer_id, db_path=tmp_db)
        assert result is not None
        assert result.issuer_id == creds.issuer_id
        assert result.name == "VerifyCorp"

    def test_verify_signature_wrong_key_fails(self, tmp_db):
        creds1 = create_company("Corp1", db_path=tmp_db)
        creds2 = create_company("Corp2", db_path=tmp_db)

        data_hash = hash_text("test")
        # Sign with corp2's key but claim corp1's issuer_id
        sig = sign_hash(data_hash, creds2.private_key_hex)
        result = verify_signature(data_hash, sig, creds1.issuer_id, db_path=tmp_db)
        assert result is None  # should fail

    def test_verify_signature_tampered_data_fails(self, tmp_db):
        creds = create_company("TamperCorp", db_path=tmp_db)
        data_hash = hash_text("original text")
        sig = sign_hash(data_hash, creds.private_key_hex)

        # Verify with a different hash (tampered text)
        tampered_hash = hash_text("tampered text")
        result = verify_signature(tampered_hash, sig, creds.issuer_id, db_path=tmp_db)
        assert result is None

    def test_verify_by_address(self, tmp_db):
        creds = create_company("AddrCorp", db_path=tmp_db)
        data_hash = hash_text("address lookup test")
        sig = sign_hash(data_hash, creds.private_key_hex)

        result = verify_signature_by_address(data_hash, sig, db_path=tmp_db)
        assert result is not None
        assert result.name == "AddrCorp"


# ======================================================================
# chain.py – simulated hash chain
# ======================================================================

class TestChain:
    def test_anchor_creates_block(self, tmp_db):
        chain = SimulatedChain(db_path=tmp_db)
        receipt = chain.anchor("abc123hash", 100, "sig_placeholder")
        assert receipt.block_num == 1
        assert receipt.data_hash == "abc123hash"
        assert receipt.tx_hash  # not empty

    def test_chain_linkage(self, tmp_db):
        chain = SimulatedChain(db_path=tmp_db)
        r1 = chain.anchor("hash1", 100, "sig1")
        r2 = chain.anchor("hash2", 100, "sig2")

        rec1 = chain.lookup_tx(r1.tx_hash)
        rec2 = chain.lookup_tx(r2.tx_hash)
        assert rec1 is not None
        assert rec2 is not None
        assert rec1.prev_hash == GENESIS_PREV_HASH
        assert rec2.prev_hash == r1.tx_hash  # linked!

    def test_lookup_by_data_hash(self, tmp_db):
        chain = SimulatedChain(db_path=tmp_db)
        chain.anchor("myhash", 100, "sig")
        record = chain.lookup("myhash")
        assert record is not None
        assert record.data_hash == "myhash"

    def test_verify(self, tmp_db):
        chain = SimulatedChain(db_path=tmp_db)
        receipt = chain.anchor("verifyhash", 100, "sig")
        assert chain.verify("verifyhash", receipt.tx_hash) is True
        assert chain.verify("verifyhash", "wrongtx") is False
        assert chain.verify("wronghash", receipt.tx_hash) is False

    def test_validate_chain(self, tmp_db):
        chain = SimulatedChain(db_path=tmp_db)
        chain.anchor("h1", 100, "s1")
        chain.anchor("h2", 101, "s2")
        chain.anchor("h3", 100, "s3")

        valid, msg = chain.validate_chain()
        assert valid is True
        assert "3 blocks" in msg

    def test_chain_length(self, tmp_db):
        chain = SimulatedChain(db_path=tmp_db)
        assert chain.chain_length() == 0
        chain.anchor("h1", 100, "s1")
        assert chain.chain_length() == 1
        chain.anchor("h2", 100, "s2")
        assert chain.chain_length() == 2


# ======================================================================
# Full round-trip: create company → watermark → sign → anchor → verify
# ======================================================================

class TestRoundTrip:
    def test_full_provenance_flow(self, tmp_db):
        """End-to-end: company embeds watermark, signs, anchors, verification succeeds."""
        from invisible_text_watermark import Watermarker

        # 1. Admin creates a company
        creds = create_company("RoundTripCorp", db_path=tmp_db)

        # 2. Company watermarks text
        wm = Watermarker(issuer_id=creds.issuer_id)
        raw_text = "This is an AI-generated response about quantum computing."
        watermarked = wm.apply(raw_text)
        assert watermarked != raw_text  # tags were injected

        # 3. Company hashes & signs
        data_hash = hash_text(watermarked)
        sig = sign_hash(data_hash, creds.private_key_hex)

        # 4. Verify signature
        signer = verify_signature(data_hash, sig, creds.issuer_id, db_path=tmp_db)
        assert signer is not None
        assert signer.name == "RoundTripCorp"

        # 5. Anchor to chain
        chain = SimulatedChain(db_path=tmp_db)
        receipt = chain.anchor(data_hash, creds.issuer_id, sig)
        assert receipt.block_num >= 1

        # 6. Verify provenance
        record = chain.lookup(data_hash)
        assert record is not None
        assert record.issuer_id == creds.issuer_id

        # 7. Detect watermark in the text
        detect = wm.detect(watermarked)
        assert detect.watermarked
        assert detect.tag_count >= 1

        # 8. Tampered text should NOT verify
        tampered = watermarked.replace("quantum", "classical")
        tampered_hash = hash_text(tampered)
        assert chain.lookup(tampered_hash) is None  # not on chain

    def test_unauthorized_signer_rejected(self, tmp_db):
        """A random private key that's not registered should fail verification."""
        import secrets
        from eth_account import Account

        create_company("LegitCorp", db_path=tmp_db)

        # Random unregistered key
        rogue_key = "0x" + secrets.token_hex(32)
        data_hash = hash_text("some text")
        sig = sign_hash(data_hash, rogue_key)

        # Try to verify – should fail (address not in DB)
        result = verify_signature_by_address(data_hash, sig, db_path=tmp_db)
        assert result is None
