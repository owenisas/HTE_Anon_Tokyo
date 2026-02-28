"""ECDSA (secp256k1) company authorization.

Each authorized company receives a private key.  The corresponding
public key + Ethereum-style address is stored in the database.

Companies sign the SHA-256 hash of watermarked text with their private
key.  The backend recovers the signer and verifies it matches a
registered, active company.

The same keypair can later sign real transactions on QDay / Ethereum.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys import keys as eth_keys

from .db import (
    DB_PATH,
    get_company_by_address,
    get_company_by_issuer,
    get_db,
    init_db,
    insert_company,
    list_companies,
)


@dataclass(slots=True)
class CompanyCredentials:
    """Returned once when a company is created."""
    issuer_id: int
    name: str
    eth_address: str
    private_key_hex: str  # 0x-prefixed, 32-byte hex


@dataclass(slots=True)
class VerifiedSigner:
    """Result of a successful signature verification."""
    issuer_id: int
    name: str
    eth_address: str


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def _next_issuer_id(conn) -> int:
    """Auto-increment issuer_id starting from 100 (1-99 reserved)."""
    row = conn.execute("SELECT MAX(issuer_id) AS m FROM companies").fetchone()
    current_max = row["m"] if row["m"] is not None else 99
    return max(current_max + 1, 100)


def create_company(name: str, db_path=DB_PATH) -> CompanyCredentials:
    """Register a new company.  Returns credentials including the private key (shown ONCE)."""
    init_db(db_path)

    # Generate ECDSA secp256k1 keypair
    private_key_hex = "0x" + secrets.token_hex(32)
    acct = Account.from_key(private_key_hex)
    eth_address = acct.address
    # Store uncompressed public key (without 04 prefix? no – keep full)
    public_key_hex = acct.key.hex()  # raw 32-byte private key hex (we derive pubkey on verify)
    # Actually store the public key properly
    pk = eth_keys.PrivateKey(bytes.fromhex(private_key_hex[2:]))
    public_key_hex = pk.public_key.to_hex()  # 0x04... uncompressed

    with get_db(db_path) as conn:
        issuer_id = _next_issuer_id(conn)
        insert_company(conn, name, issuer_id, eth_address, public_key_hex)

    return CompanyCredentials(
        issuer_id=issuer_id,
        name=name,
        eth_address=eth_address,
        private_key_hex=private_key_hex,
    )


# ---------------------------------------------------------------------------
# Signing helpers (used by companies on their side)
# ---------------------------------------------------------------------------

def sign_hash(data_hash_hex: str, private_key_hex: str) -> str:
    """Sign a hex-encoded SHA-256 hash with a private key.

    Returns the signature as a hex string.
    This function is intended to run on the company's infrastructure.
    """
    message = encode_defunct(text=data_hash_hex)
    signed = Account.sign_message(message, private_key=private_key_hex)
    return signed.signature.hex()


def hash_text(text: str) -> str:
    """SHA-256 hash of text, returned as hex."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Signature verification (runs on our backend)
# ---------------------------------------------------------------------------

def recover_signer(data_hash_hex: str, signature_hex: str) -> str:
    """Recover Ethereum address from a signature over a hash string.

    Returns the checksummed Ethereum address of the signer.
    """
    message = encode_defunct(text=data_hash_hex)
    sig_bytes = bytes.fromhex(signature_hex.removeprefix("0x"))
    address = Account.recover_message(message, signature=sig_bytes)
    return address


def verify_signature(
    data_hash_hex: str,
    signature_hex: str,
    issuer_id: int,
    db_path=DB_PATH,
) -> VerifiedSigner | None:
    """Verify that the signature was produced by the registered company.

    Returns VerifiedSigner on success, None on failure.
    """
    try:
        recovered_address = recover_signer(data_hash_hex, signature_hex)
    except Exception:
        return None

    with get_db(db_path) as conn:
        company = get_company_by_issuer(conn, issuer_id)
        if company is None:
            return None
        # Case-insensitive address comparison
        if recovered_address.lower() != company["eth_address"].lower():
            return None
        return VerifiedSigner(
            issuer_id=company["issuer_id"],
            name=company["name"],
            eth_address=company["eth_address"],
        )


def verify_signature_by_address(
    data_hash_hex: str,
    signature_hex: str,
    db_path=DB_PATH,
) -> VerifiedSigner | None:
    """Verify signature and look up company by recovered address (no issuer_id needed)."""
    try:
        recovered_address = recover_signer(data_hash_hex, signature_hex)
    except Exception:
        return None

    with get_db(db_path) as conn:
        company = get_company_by_address(conn, recovered_address)
        if company is None:
            # Try case-insensitive
            for c in list_companies(conn):
                if c["eth_address"].lower() == recovered_address.lower():
                    return VerifiedSigner(
                        issuer_id=c["issuer_id"],
                        name=c["name"],
                        eth_address=c["eth_address"],
                    )
            return None
        return VerifiedSigner(
            issuer_id=company["issuer_id"],
            name=company["name"],
            eth_address=company["eth_address"],
        )
