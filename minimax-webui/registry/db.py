"""SQLite storage for the provenance registry.

Tables
------
companies   – authorized companies with ECDSA public keys.
responses   – raw + watermarked LLM responses indexed by SHA-256 hash.
chain_blocks – simulated hash-chain of anchored records.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DB_PATH = Path(__file__).resolve().parent / "provenance.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    issuer_id       INTEGER NOT NULL UNIQUE,
    eth_address     TEXT    NOT NULL UNIQUE,       -- 0x-prefixed, checksum
    public_key_hex  TEXT    NOT NULL,              -- uncompressed hex (no 0x)
    active          INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS responses (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256_hash      TEXT    NOT NULL,
    issuer_id        INTEGER NOT NULL,
    signature_hex    TEXT    NOT NULL,
    raw_text         TEXT    NOT NULL,
    watermarked_text TEXT    NOT NULL,
    metadata_json    TEXT    NOT NULL DEFAULT '{}',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (issuer_id) REFERENCES companies(issuer_id)
);
CREATE INDEX IF NOT EXISTS idx_responses_hash ON responses(sha256_hash);

CREATE TABLE IF NOT EXISTS chain_blocks (
    block_num    INTEGER PRIMARY KEY AUTOINCREMENT,
    prev_hash    TEXT    NOT NULL,
    tx_hash      TEXT    NOT NULL UNIQUE,
    data_hash    TEXT    NOT NULL,
    issuer_id    INTEGER NOT NULL,
    signature_hex TEXT   NOT NULL,
    payload_json TEXT    NOT NULL DEFAULT '{}',
    timestamp    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Create tables if they don't exist."""
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def get_db(db_path: Path | str = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context-managed database connection (auto-commit on success)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Company CRUD helpers
# ---------------------------------------------------------------------------

def insert_company(
    conn: sqlite3.Connection,
    name: str,
    issuer_id: int,
    eth_address: str,
    public_key_hex: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO companies (name, issuer_id, eth_address, public_key_hex) VALUES (?, ?, ?, ?)",
        (name, issuer_id, eth_address, public_key_hex),
    )
    return cur.lastrowid  # type: ignore[return-value]


def get_company_by_issuer(conn: sqlite3.Connection, issuer_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM companies WHERE issuer_id = ? AND active = 1", (issuer_id,)
    ).fetchone()


def get_company_by_address(conn: sqlite3.Connection, eth_address: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM companies WHERE eth_address = ? AND active = 1", (eth_address,)
    ).fetchone()


def list_companies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM companies ORDER BY id").fetchall()


def deactivate_company(conn: sqlite3.Connection, issuer_id: int) -> None:
    conn.execute("UPDATE companies SET active = 0 WHERE issuer_id = ?", (issuer_id,))


# ---------------------------------------------------------------------------
# Response storage helpers
# ---------------------------------------------------------------------------

def insert_response(
    conn: sqlite3.Connection,
    sha256_hash: str,
    issuer_id: int,
    signature_hex: str,
    raw_text: str,
    watermarked_text: str,
    metadata_json: str = "{}",
) -> int:
    cur = conn.execute(
        """INSERT INTO responses
           (sha256_hash, issuer_id, signature_hex, raw_text, watermarked_text, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (sha256_hash, issuer_id, signature_hex, raw_text, watermarked_text, metadata_json),
    )
    return cur.lastrowid  # type: ignore[return-value]


def get_response_by_hash(conn: sqlite3.Connection, sha256_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM responses WHERE sha256_hash = ?", (sha256_hash,)
    ).fetchone()


# ---------------------------------------------------------------------------
# Chain block helpers
# ---------------------------------------------------------------------------

def insert_block(
    conn: sqlite3.Connection,
    prev_hash: str,
    tx_hash: str,
    data_hash: str,
    issuer_id: int,
    signature_hex: str,
    payload_json: str = "{}",
) -> int:
    cur = conn.execute(
        """INSERT INTO chain_blocks
           (prev_hash, tx_hash, data_hash, issuer_id, signature_hex, payload_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (prev_hash, tx_hash, data_hash, issuer_id, signature_hex, payload_json),
    )
    return cur.lastrowid  # type: ignore[return-value]


def get_latest_block(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM chain_blocks ORDER BY block_num DESC LIMIT 1"
    ).fetchone()


def get_block_by_data_hash(conn: sqlite3.Connection, data_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM chain_blocks WHERE data_hash = ?", (data_hash,)
    ).fetchone()


def get_block_by_tx_hash(conn: sqlite3.Connection, tx_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM chain_blocks WHERE tx_hash = ?", (tx_hash,)
    ).fetchone()
