from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .config import WatermarkConfig, parse_effective_request
from .detector import WatermarkDetector
from .keys import derive_context_seed, derive_step_key, get_master_key
from .payload import PackedMetadata, pack_payload
from .policy import get_opt_out_secret, verify_opt_out_token
from .statistical import select_sparse_green_ids
from .zero_width import TagInjector, encode_payload_to_tag

logger = logging.getLogger("watermark_llamacpp.gateway")


def _load_cfg_from_env() -> WatermarkConfig:
    model_id_map = json.loads(os.environ.get("WATERMARK_MODEL_ID_MAP", "{}"))
    model_ver_map = json.loads(os.environ.get("WATERMARK_MODEL_VERSION_MAP", "{}"))
    cfg = WatermarkConfig(
        schema_version=int(os.environ.get("WATERMARK_SCHEMA_VERSION", "1")),
        issuer_id=int(os.environ.get("WATERMARK_ISSUER_ID", "1")),
        active_key_id=int(os.environ.get("WATERMARK_ACTIVE_KEY_ID", "1")),
        model_id_map={str(k): int(v) for k, v in model_id_map.items()},
        model_version_map={str(k): int(v) for k, v in model_ver_map.items()},
    )
    cfg.statistical.context_width = int(
        os.environ.get("WATERMARK_CONTEXT_WIDTH", str(cfg.statistical.context_width))
    )
    cfg.statistical.greenlist_ratio = float(
        os.environ.get("WATERMARK_GREENLIST_RATIO", str(cfg.statistical.greenlist_ratio))
    )
    cfg.statistical.bias_delta = float(
        os.environ.get("WATERMARK_BIAS_DELTA", str(cfg.statistical.bias_delta))
    )
    cfg.statistical.max_bias_tokens = int(
        os.environ.get(
            "WATERMARK_MAX_BIAS_TOKENS", str(cfg.statistical.max_bias_tokens)
        )
    )
    cfg.tag.repeat_interval_tokens = int(
        os.environ.get("WATERMARK_REPEAT_INTERVAL_TOKENS", str(cfg.tag.repeat_interval_tokens))
    )
    return cfg


def _parse_oai_logit_bias(obj: Any) -> dict[int, float]:
    if obj is None:
        return {}
    out: dict[int, float] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            try:
                tid = int(key)
                out[tid] = float(value)
            except (TypeError, ValueError):
                continue
    elif isinstance(obj, list):
        for entry in obj:
            if isinstance(entry, list) and len(entry) == 2:
                try:
                    out[int(entry[0])] = float(entry[1])
                except (TypeError, ValueError):
                    continue
    return out


def _merge_logit_bias(*maps: dict[int, float]) -> dict[int, float]:
    merged: dict[int, float] = {}
    for mapping in maps:
        for tid, bias in mapping.items():
            merged[tid] = merged.get(tid, 0.0) + bias
    return merged


async def _llama_tokenize(client: httpx.AsyncClient, text: str, add_special: bool) -> list[int]:
    resp = await client.post(
        "/tokenize",
        json={"content": text, "add_special": add_special, "parse_special": True},
    )
    resp.raise_for_status()
    data = resp.json()
    toks = data.get("tokens") or []
    out: list[int] = []
    for tok in toks:
        if isinstance(tok, int):
            out.append(tok)
        elif isinstance(tok, dict) and isinstance(tok.get("id"), int):
            out.append(tok["id"])
    return out


async def _llama_apply_template(
    client: httpx.AsyncClient, *, messages: list[dict[str, Any]], model: str | None
) -> str:
    payload: dict[str, Any] = {"messages": messages}
    if model:
        payload["model"] = model
    resp = await client.post("/apply-template", json=payload)
    resp.raise_for_status()
    data = resp.json()
    err = data.get("error")
    if isinstance(err, str) and "Unexpected endpoint or method" in err:
        raise HTTPException(
            status_code=501,
            detail=(
                "upstream does not expose /apply-template; "
                "statistical watermark mode requires llama-server native endpoints"
            ),
        )
    prompt = data.get("prompt")
    if not isinstance(prompt, str):
        raise HTTPException(status_code=500, detail="/apply-template did not return prompt")
    return prompt


async def _llama_model_meta(client: httpx.AsyncClient, model: str | None) -> tuple[str, int]:
    resp = await client.get("/v1/models")
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data") or []
    if not items:
        return model or "llama.cpp", 32000

    chosen = items[0]
    if model is not None:
        for it in items:
            if it.get("id") == model:
                chosen = it
                break
    model_id = str(chosen.get("id", model or "llama.cpp"))
    meta = chosen.get("meta") or {}
    n_vocab = int(meta.get("n_vocab", 32000))
    return model_id, n_vocab


def _build_sparse_wm_logit_bias(
    *,
    context_tokens: list[int],
    cfg: WatermarkConfig,
    model_id_num: int,
    key_id: int,
    date_str: str,
    n_vocab: int,
) -> dict[int, float]:
    if len(context_tokens) < cfg.statistical.context_width:
        return {}

    _, master_key = get_master_key(key_id)
    derived = derive_step_key(
        master_key,
        model_id=model_id_num,
        date_str=date_str,
        key_id=key_id,
    )
    seed = derive_context_seed(derived, context_tokens[-cfg.statistical.context_width :])
    green_ids = select_sparse_green_ids(
        vocab_size=n_vocab,
        seed=seed,
        greenlist_ratio=cfg.statistical.greenlist_ratio,
        max_bias_tokens=cfg.statistical.max_bias_tokens,
    )
    delta = cfg.statistical.bias_delta
    return {tid: delta for tid in green_ids}


def _to_llama_completion_req(
    body: dict[str, Any],
    *,
    prompt: str,
    n_predict: int,
    logit_bias: dict[int, float],
    id_slot: int,
) -> dict[str, Any]:
    req: dict[str, Any] = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": body.get("temperature", 0.8),
        "top_p": body.get("top_p", 0.95),
        "stop": body.get("stop", []),
        "stream": False,
        "cache_prompt": True,
        "id_slot": id_slot,
        "return_tokens": True,
    }

    if body.get("top_k") is not None:
        req["top_k"] = body["top_k"]
    if body.get("min_p") is not None:
        req["min_p"] = body["min_p"]
    if body.get("seed") is not None:
        req["seed"] = body["seed"]
    if body.get("presence_penalty") is not None:
        req["presence_penalty"] = body["presence_penalty"]
    if body.get("frequency_penalty") is not None:
        req["frequency_penalty"] = body["frequency_penalty"]
    if body.get("repetition_penalty") is not None:
        req["repeat_penalty"] = body["repetition_penalty"]

    if logit_bias:
        req["logit_bias"] = {str(k): v for k, v in logit_bias.items()}
    return req


async def _watermarked_generate(
    *,
    client: httpx.AsyncClient,
    body: dict[str, Any],
    cfg: WatermarkConfig,
    prompt: str,
    model_name: str,
    mode: str,
    enabled: bool,
    key_id: int,
) -> tuple[str, list[int], int]:
    _, n_vocab = await _llama_model_meta(client, body.get("model"))

    prompt_tokens = await _llama_tokenize(client, prompt, add_special=True)
    generated_text = ""
    generated_tokens: list[int] = []

    max_tokens = body.get("max_tokens", 16)
    if max_tokens is None:
        max_tokens = 16
    max_tokens = int(max_tokens)
    if max_tokens < 0:
        max_tokens = 16

    user_bias = _parse_oai_logit_bias(body.get("logit_bias"))
    slot = int(body.get("id_slot", 0))
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    model_id_num = cfg.model_id_for(model_name)

    for _ in range(max_tokens):
        wm_bias: dict[int, float] = {}
        if enabled and mode in {"hybrid", "statistical_only"}:
            ctx = prompt_tokens + generated_tokens
            wm_bias = _build_sparse_wm_logit_bias(
                context_tokens=ctx,
                cfg=cfg,
                model_id_num=model_id_num,
                key_id=key_id,
                date_str=date_str,
                n_vocab=n_vocab,
            )

        req = _to_llama_completion_req(
            body,
            prompt=prompt + generated_text,
            n_predict=1,
            logit_bias=_merge_logit_bias(user_bias, wm_bias),
            id_slot=slot,
        )

        resp = await client.post("/completion", json=req)
        resp.raise_for_status()
        data = resp.json()
        err = data.get("error")
        if isinstance(err, str) and "Unexpected endpoint or method" in err:
            raise HTTPException(
                status_code=501,
                detail=(
                    "upstream does not expose /completion; "
                    "statistical watermark mode requires llama-server native endpoints"
                ),
            )

        piece = data.get("content", "")
        if not isinstance(piece, str):
            piece = str(piece)

        step_toks = data.get("tokens") or []
        step_ids: list[int] = [t for t in step_toks if isinstance(t, int)]
        if not step_ids and piece:
            step_ids = await _llama_tokenize(client, piece, add_special=False)

        generated_text += piece
        generated_tokens.extend(step_ids)

        stop_type = data.get("stop_type")
        if stop_type in {"eos", "word"}:
            break

    return generated_text, generated_tokens, len(prompt_tokens)


def _oai_completion_response(
    *,
    model: str,
    text: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict[str, Any]:
    return {
        "id": f"cmpl-wm-{int(time.time() * 1000)}",
        "object": "text_completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "text": text,
                "logprobs": None,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _oai_chat_response(
    *,
    model: str,
    text: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-wm-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _inject_tag_nonstream(resp: dict[str, Any], tag: str, repeat_interval: int) -> dict[str, Any]:
    inj = TagInjector(tag, repeat_interval)
    if isinstance(resp.get("choices"), list):
        for choice in resp["choices"]:
            if isinstance(choice.get("text"), str):
                choice["text"] = inj.inject_delta(choice["text"], finalize=True)
            msg = choice.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                msg["content"] = inj.inject_delta(msg["content"], finalize=True)
    return resp


def create_app() -> FastAPI:
    app = FastAPI(title="watermark-llamacpp-gateway", version="0.1.0")

    cfg = _load_cfg_from_env()
    detector = WatermarkDetector(cfg)
    opt_out_secret = get_opt_out_secret()
    upstream = os.environ.get("UPSTREAM_LLAMACPP_URL", "http://127.0.0.1:8080")

    @app.post("/internal/watermark/verify")
    async def verify_endpoint(payload: dict[str, Any]):
        text = payload.get("text")
        if not isinstance(text, str) or not text:
            raise HTTPException(status_code=400, detail="text is required")

        model_hint = payload.get("model_hint")
        token_ids = payload.get("token_ids")
        if token_ids is not None and not all(isinstance(t, int) for t in token_ids):
            raise HTTPException(status_code=400, detail="token_ids must be integer list")

        async with httpx.AsyncClient(base_url=upstream, timeout=httpx.Timeout(30.0, read=120.0)) as client:
            model_id, n_vocab = await _llama_model_meta(client, model_hint)
            if token_ids is None:
                token_ids = await _llama_tokenize(client, text, add_special=True)

        result = detector.verify(
            text=text,
            model_hint=model_id,
            token_ids=token_ids,
            vocab_size=n_vocab,
        )

        stat = None
        if result.statistical_score is not None:
            stat = {
                "total_scored": result.statistical_score.total_scored,
                "green_hits": result.statistical_score.green_hits,
                "expected": result.statistical_score.expected,
                "z_score": result.statistical_score.z_score,
                "p_value_one_sided": result.statistical_score.p_value_one_sided,
            }

        return {
            "status": result.status,
            "statistical_score": stat,
            "payload": result.payload,
            "key_id": result.key_id,
            "explanations": result.explanations,
        }

    async def _handle_common(
        body: dict[str, Any],
        *,
        as_chat: bool,
    ) -> dict[str, Any]:
        req_wm = parse_effective_request(body.pop("watermark", None))
        if not req_wm.enabled:
            ok, reason = verify_opt_out_token(req_wm.opt_out_token, opt_out_secret)
            if not ok:
                raise HTTPException(status_code=403, detail=f"watermark opt-out denied: {reason}")

        model_name = str(body.get("model") or "llama.cpp")
        key_id = req_wm.key_id if req_wm.key_id is not None else cfg.active_key_id

        tag_ctx: dict[str, Any] | None = None
        if req_wm.enabled and req_wm.mode in {"hybrid", "tag_only"}:
            payload64 = pack_payload(
                PackedMetadata(
                    schema_version=cfg.schema_version,
                    issuer_id=cfg.issuer_id,
                    model_id=cfg.model_id_for(model_name),
                    model_version_id=cfg.model_version_id_for(model_name),
                    key_id=key_id,
                )
            )
            tag_ctx = {
                "tag": encode_payload_to_tag(payload64, cfg.tag),
                "repeat_interval_tokens": cfg.tag.repeat_interval_tokens,
            }

        async with httpx.AsyncClient(base_url=upstream, timeout=httpx.Timeout(30.0, read=180.0)) as client:
            if req_wm.enabled and req_wm.mode in {"hybrid", "statistical_only"}:
                if as_chat:
                    messages = body.get("messages")
                    if not isinstance(messages, list):
                        raise HTTPException(status_code=400, detail="messages is required for chat completions")
                    prompt = await _llama_apply_template(
                        client,
                        messages=messages,
                        model=body.get("model"),
                    )
                    text, out_tokens, prompt_tokens = await _watermarked_generate(
                        client=client,
                        body=body,
                        cfg=cfg,
                        prompt=prompt,
                        model_name=model_name,
                        mode=req_wm.mode,
                        enabled=req_wm.enabled,
                        key_id=key_id,
                    )
                    resp = _oai_chat_response(
                        model=model_name,
                        text=text,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=len(out_tokens),
                    )
                else:
                    prompt = body.get("prompt")
                    if not isinstance(prompt, str):
                        raise HTTPException(status_code=400, detail="this gateway currently supports string prompt only")
                    text, out_tokens, prompt_tokens = await _watermarked_generate(
                        client=client,
                        body=body,
                        cfg=cfg,
                        prompt=prompt,
                        model_name=model_name,
                        mode=req_wm.mode,
                        enabled=req_wm.enabled,
                        key_id=key_id,
                    )
                    resp = _oai_completion_response(
                        model=model_name,
                        text=text,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=len(out_tokens),
                    )
                if tag_ctx is not None:
                    resp = _inject_tag_nonstream(resp, tag_ctx["tag"], int(tag_ctx["repeat_interval_tokens"]))
                return resp

            # passthrough modes (disabled or tag_only)
            path = "/v1/chat/completions" if as_chat else "/v1/completions"
            upstream_resp = await client.post(path, json=body)
            if upstream_resp.status_code >= 400:
                raise HTTPException(status_code=upstream_resp.status_code, detail=upstream_resp.text)
            data = upstream_resp.json()
            if tag_ctx is not None:
                data = _inject_tag_nonstream(data, tag_ctx["tag"], int(tag_ctx["repeat_interval_tokens"]))
            return data

    @app.post("/v1/completions")
    async def completions(request: Request):
        body = await request.json()
        return JSONResponse(await _handle_common(body, as_chat=False))

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        body = await request.json()
        return JSONResponse(await _handle_common(body, as_chat=True))

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Watermark gateway for llama.cpp server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=9002, type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    import uvicorn

    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
