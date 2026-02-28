"""MiniMax + Bedrock API Watermark Lab (FastAPI) + Provenance Registry."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

_project_root = Path(__file__).resolve().parent.parent
for _candidate in [
    _project_root / "invisible-text-watermark" / "src",
    _project_root / "watermark-tools" / "invisible-text-watermark" / "src",
]:
    if _candidate.exists():
        sys.path.insert(0, str(_candidate))
        break
from invisible_text_watermark import Watermarker, DetectResult

from registry.auth import (
    create_company,
    hash_text,
    recover_signer,
    sign_hash,
    verify_signature,
    verify_signature_by_address,
)
from registry.chain import SimulatedChain
from registry.db import (
    DB_PATH,
    get_db,
    get_response_by_hash,
    init_db,
    insert_response,
    list_companies,
)

load_dotenv()

app = FastAPI(title="MiniMax + Bedrock Watermark Lab")

# CORS for extension access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Serve static assets (CSS, JS, images)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

MINIMAX_MODELS = [
    {"id": "MiniMax-M2.5", "name": "MiniMax M2.5", "provider": "minimax"},
    {"id": "MiniMax-M2.5-highspeed", "name": "MiniMax M2.5 Highspeed", "provider": "minimax"},
    {"id": "MiniMax-M2.1", "name": "MiniMax M2.1", "provider": "minimax"},
    {"id": "MiniMax-M2.1-highspeed", "name": "MiniMax M2.1 Highspeed", "provider": "minimax"},
    {"id": "MiniMax-M2", "name": "MiniMax M2", "provider": "minimax"},
]

BEDROCK_MODELS = [
    {"id": "anthropic.claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "bedrock"},
    {"id": "anthropic.claude-opus-4-6-v1", "name": "Claude Opus 4.6", "provider": "bedrock"},
    {"id": "anthropic.claude-sonnet-4-5-20250929-v1:0", "name": "Claude Sonnet 4.5", "provider": "bedrock"},
    {"id": "anthropic.claude-opus-4-5-20251101-v1:0", "name": "Claude Opus 4.5", "provider": "bedrock"},
    {"id": "anthropic.claude-haiku-4-5-20251001-v1:0", "name": "Claude Haiku 4.5", "provider": "bedrock"},
    {"id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "name": "Claude 3.5 Sonnet v2", "provider": "bedrock"},
    {"id": "deepseek.v3.2", "name": "DeepSeek V3.2", "provider": "bedrock"},
    {"id": "deepseek.r1-v1:0", "name": "DeepSeek R1", "provider": "bedrock"},
    {"id": "minimax.minimax-m2.1", "name": "MiniMax M2.1 (Bedrock)", "provider": "bedrock"},
    {"id": "minimax.minimax-m2", "name": "MiniMax M2 (Bedrock)", "provider": "bedrock"},
    {"id": "amazon.nova-pro-v1:0", "name": "Nova Pro", "provider": "bedrock"},
    {"id": "amazon.nova-lite-v1:0", "name": "Nova Lite", "provider": "bedrock"},
    {"id": "amazon.nova-micro-v1:0", "name": "Nova Micro", "provider": "bedrock"},
]


def _get_minimax_client():
    import anthropic
    return anthropic.Anthropic(api_key=MINIMAX_API_KEY, base_url=MINIMAX_BASE_URL)


def _get_bedrock_client():
    import boto3
    return boto3.client("bedrock-runtime", region_name="us-east-1")


def _get_watermarker(params: dict) -> Watermarker:
    return Watermarker(
        issuer_id=params.get("issuer_id", 1),
        model_id=params.get("model_id", 0),
        model_version_id=params.get("model_version_id", 0),
        key_id=params.get("key_id", 1),
        repeat_interval_tokens=params.get("repeat_interval_tokens", 160),
    )


class WmParams(BaseModel):
    issuer_id: int = 1
    model_id: int = 0
    model_version_id: int = 0
    key_id: int = 1
    repeat_interval_tokens: int = 160


class ChatRequest(BaseModel):
    model: str = "MiniMax-M2.1"
    provider: str = "minimax"
    messages: list[dict[str, Any]] = []
    system: str = "You are a helpful assistant."
    watermark: bool = True
    wm_params: WmParams = Field(default_factory=WmParams)
    stream: bool = False
    max_tokens: int = 2048
    temperature: float = 0.7


class TextRequest(BaseModel):
    text: str = ""
    wm_params: WmParams = Field(default_factory=WmParams)


class StripRequest(BaseModel):
    text: str = ""


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/models")
async def list_models():
    return {"minimax": MINIMAX_MODELS, "bedrock": BEDROCK_MODELS}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    wm = _get_watermarker(req.wm_params.model_dump()) if req.watermark else None

    if req.provider == "bedrock":
        return await _chat_bedrock(req, wm)
    return await _chat_minimax(req, wm)


async def _chat_minimax(req: ChatRequest, wm):
    import anthropic
    client = _get_minimax_client()
    try:
        resp = client.messages.create(
            model=req.model,
            max_tokens=req.max_tokens,
            system=req.system,
            messages=req.messages,
            temperature=req.temperature,
        )
    except anthropic.APIError as e:
        return {"error": str(e)}

    thinking = ""
    text = ""
    for block in resp.content:
        if block.type == "thinking":
            thinking += block.thinking
        elif block.type == "text":
            text += block.text

    raw_text = text
    if wm and text:
        text = wm.apply(text)

    return {
        "thinking": thinking,
        "text": text,
        "raw_text": raw_text,
        "watermarked": wm is not None,
        "model": req.model,
        "provider": "minimax",
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
    }


async def _chat_bedrock(req: ChatRequest, wm):
    client = _get_bedrock_client()

    bedrock_messages = []
    for msg in req.messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, str):
            bedrock_messages.append({"role": role, "content": [{"text": content}]})
        elif isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    parts.append({"text": c.get("text", "")})
                elif isinstance(c, str):
                    parts.append({"text": c})
            bedrock_messages.append({"role": role, "content": parts})

    try:
        resp = client.converse(
            modelId=req.model,
            messages=bedrock_messages,
            system=[{"text": req.system}],
            inferenceConfig={
                "maxTokens": req.max_tokens,
                "temperature": req.temperature,
            },
        )
    except Exception as e:
        return {"error": str(e)}

    thinking = ""
    text = ""
    output = resp.get("output", {})
    message = output.get("message", {})
    for block in message.get("content", []):
        if "text" in block:
            text += block["text"]
        if "reasoningContent" in block:
            rc = block["reasoningContent"]
            if "reasoningText" in rc:
                thinking += rc["reasoningText"].get("text", "")

    raw_text = text
    if wm and text:
        text = wm.apply(text)

    usage = resp.get("usage", {})
    return {
        "thinking": thinking,
        "text": text,
        "raw_text": raw_text,
        "watermarked": wm is not None,
        "model": req.model,
        "provider": "bedrock",
        "usage": {
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
        },
    }


@app.post("/api/detect")
async def detect(req: TextRequest):
    wm = _get_watermarker(req.wm_params.model_dump())
    result: DetectResult = wm.detect(req.text)
    return {
        "watermarked": result.watermarked,
        "tag_count": result.tag_count,
        "valid_count": result.valid_count,
        "invalid_count": result.invalid_count,
        "payloads": result.payloads,
    }


@app.post("/api/strip")
async def strip(req: StripRequest):
    cleaned = Watermarker.strip(req.text)
    return {"text": cleaned}


@app.post("/api/apply")
async def apply_watermark(req: TextRequest):
    wm = _get_watermarker(req.wm_params.model_dump())
    watermarked = wm.apply(req.text)
    return {"text": watermarked, "raw_text": req.text}


# ======================================================================
# Registry Layer 2 – Company-level provenance (private-key auth)
# ======================================================================

# Initialise DB + chain on startup
init_db()
_chain = SimulatedChain()


class CreateCompanyRequest(BaseModel):
    name: str
    admin_secret: str = ""  # simple shared secret to protect admin endpoints


class AnchorRequest(BaseModel):
    """Submitted by an authorized company after watermarking + signing."""
    text: str                       # watermarked text
    raw_text: str = ""              # original text before watermarking (optional)
    signature_hex: str              # ECDSA sig over SHA-256(text)
    issuer_id: int                  # company's registered issuer_id
    metadata: dict[str, Any] = {}   # optional extra metadata


class VerifyRequest(BaseModel):
    """Public verification – anyone can check provenance."""
    text: str


# Admin secret (set via env var; empty = admin endpoints disabled)
ADMIN_SECRET = os.getenv("REGISTRY_ADMIN_SECRET", "dev-admin-secret")


@app.post("/api/registry/companies")
async def api_create_company(req: CreateCompanyRequest):
    """Create a new authorized company.  Returns the private key ONCE."""
    if req.admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    creds = create_company(req.name)
    return {
        "issuer_id": creds.issuer_id,
        "name": creds.name,
        "eth_address": creds.eth_address,
        "private_key": creds.private_key_hex,
        "warning": "Store this private key securely. It will NOT be shown again.",
    }


@app.get("/api/registry/companies")
async def api_list_companies():
    """List all registered companies (public keys only, no secrets)."""
    with get_db() as conn:
        companies = list_companies(conn)
    return [
        {
            "issuer_id": c["issuer_id"],
            "name": c["name"],
            "eth_address": c["eth_address"],
            "active": bool(c["active"]),
            "created_at": c["created_at"],
        }
        for c in companies
    ]


@app.post("/api/registry/anchor")
async def api_anchor(req: AnchorRequest):
    """Anchor a watermarked response to the provenance chain.

    The company signs SHA-256(watermarked_text) with their private key.
    Only authorized signers (registered companies) can create blocks.
    """
    # 1. Hash the watermarked text
    data_hash = hash_text(req.text)

    # 2. Verify the signature against the registered company
    signer = verify_signature(data_hash, req.signature_hex, req.issuer_id)
    if signer is None:
        raise HTTPException(
            status_code=403,
            detail="Invalid signature or unauthorized issuer_id. "
                   "Only authorized companies with valid private keys can anchor.",
        )

    # 3. Store raw + watermarked response in SQLite
    with get_db() as conn:
        insert_response(
            conn,
            sha256_hash=data_hash,
            issuer_id=signer.issuer_id,
            signature_hex=req.signature_hex,
            raw_text=req.raw_text or req.text,
            watermarked_text=req.text,
            metadata_json=json.dumps(req.metadata),
        )

    # 4. Anchor hash to the simulated chain
    receipt = _chain.anchor(
        data_hash=data_hash,
        issuer_id=signer.issuer_id,
        signature_hex=req.signature_hex,
        metadata=req.metadata,
    )

    return {
        "verified_signer": signer.name,
        "eth_address": signer.eth_address,
        "sha256_hash": data_hash,
        "chain_receipt": receipt.to_dict(),
    }


@app.post("/api/registry/verify")
async def api_verify(req: VerifyRequest):
    """Verify provenance of a text.

    Recomputes the SHA-256 hash and looks it up on the chain.
    Also extracts any embedded watermark metadata.
    """
    data_hash = hash_text(req.text)

    # Look up on chain
    record = _chain.lookup(data_hash)

    # Try to extract watermark tags
    wm = Watermarker()
    detect_result = wm.detect(req.text)

    if record is not None:
        # Found on chain – look up company
        with get_db() as conn:
            from registry.db import get_company_by_issuer
            company = get_company_by_issuer(conn, record.issuer_id)
            company_name = company["name"] if company else "unknown"

        return {
            "verified": True,
            "sha256_hash": data_hash,
            "issuer_id": record.issuer_id,
            "company": company_name,
            "eth_address": company["eth_address"] if company else None,
            "block_num": record.block_num,
            "tx_hash": record.tx_hash,
            "timestamp": record.timestamp,
            "watermark": {
                "detected": detect_result.watermarked,
                "tag_count": detect_result.tag_count,
                "payloads": detect_result.payloads,
            },
        }
    else:
        return {
            "verified": False,
            "sha256_hash": data_hash,
            "reason": "Hash not found on chain. Text may be tampered or never registered.",
            "watermark": {
                "detected": detect_result.watermarked,
                "tag_count": detect_result.tag_count,
                "payloads": detect_result.payloads,
            },
        }


@app.get("/api/registry/chain/status")
async def api_chain_status():
    """Chain health and stats."""
    valid, message = _chain.validate_chain()
    return {
        "length": _chain.chain_length(),
        "valid": valid,
        "message": message,
    }


@app.get("/api/registry/chain/blocks")
async def api_chain_blocks(limit: int = 50, offset: int = 0):
    """List chain blocks (newest first)."""
    with get_db() as conn:
        blocks = conn.execute(
            "SELECT * FROM chain_blocks ORDER BY block_num DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM chain_blocks").fetchone()["c"]
    return {
        "blocks": [dict(b) for b in blocks],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/registry/chain/block/{block_num}")
async def api_chain_block(block_num: int):
    """Get a single block by number."""
    with get_db() as conn:
        block = conn.execute(
            "SELECT * FROM chain_blocks WHERE block_num = ?", (block_num,)
        ).fetchone()
    if block is None:
        raise HTTPException(404, "Block not found")
    return dict(block)


@app.get("/api/registry/responses")
async def api_list_responses(limit: int = 50, offset: int = 0):
    """List stored responses."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, sha256_hash, issuer_id, created_at, metadata_json "
            "FROM responses ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM responses").fetchone()["c"]
    return {
        "responses": [dict(r) for r in rows],
        "total": total,
    }


@app.get("/api/registry/demo/latest-response")
async def api_demo_latest_response():
    """Get latest anchored response payload for demo handoff (company -> user)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT r.id, r.sha256_hash, r.issuer_id, r.raw_text, r.watermarked_text, "
            "r.created_at, c.name AS company_name "
            "FROM responses r "
            "LEFT JOIN companies c ON c.issuer_id = r.issuer_id "
            "ORDER BY r.id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise HTTPException(404, "No anchored responses found yet")
    return dict(row)


# ======================================================================
# Registry frontend pages
# ======================================================================

REGISTRY_DIR = Path(__file__).resolve().parent / "static" / "registry"


@app.get("/registry")
async def registry_dashboard():
    return FileResponse(REGISTRY_DIR / "index.html")


@app.get("/registry/companies")
async def registry_companies_page():
    return FileResponse(REGISTRY_DIR / "companies.html")


@app.get("/registry/anchor")
async def registry_anchor_page():
    return FileResponse(REGISTRY_DIR / "anchor.html")


@app.get("/registry/verify")
async def registry_verify_page():
    return FileResponse(REGISTRY_DIR / "verify.html")


@app.get("/registry/chain")
async def registry_chain_page():
    return FileResponse(REGISTRY_DIR / "chain.html")


@app.get("/registry/demo")
async def registry_demo_page():
    return FileResponse(REGISTRY_DIR / "demo.html")


@app.get("/registry/demo/company")
async def registry_demo_company_page():
    return FileResponse(REGISTRY_DIR / "demo-company.html")


@app.get("/registry/demo/user")
async def registry_demo_user_page():
    return FileResponse(REGISTRY_DIR / "demo-user.html")


if __name__ == "__main__":
    import uvicorn
    if not MINIMAX_API_KEY:
        print("WARNING: MINIMAX_API_KEY not set. Set it in .env or environment.")
    print("Registry DB:", DB_PATH)
    print("Admin secret:", "SET" if ADMIN_SECRET else "NOT SET")
    uvicorn.run("app:app", host="127.0.0.1", port=5050, reload=True)
