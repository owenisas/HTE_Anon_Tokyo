"""MiniMax + Bedrock API Watermark Lab (FastAPI)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

_wm_src = Path(__file__).resolve().parent.parent / "invisible-text-watermark" / "src"
if _wm_src.exists():
    sys.path.insert(0, str(_wm_src))
from invisible_text_watermark import Watermarker, DetectResult

load_dotenv()

app = FastAPI(title="MiniMax + Bedrock Watermark Lab")

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"

STATIC_DIR = Path(__file__).resolve().parent / "static"

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


if __name__ == "__main__":
    import uvicorn
    if not MINIMAX_API_KEY:
        print("WARNING: MINIMAX_API_KEY not set. Set it in .env or environment.")
    uvicorn.run("app:app", host="127.0.0.1", port=5050, reload=True)
