#!/usr/bin/env python3

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = os.environ.get("LMCANVAS_PROXY_HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT") or os.environ.get("LMCANVAS_PROXY_PORT", "8787"))
LMCANVAS_CHAT_URL = os.environ.get("LMCANVAS_CHAT_URL", "https://lmcanvas.ai/api/chat")
LMCANVAS_DEFAULT_MODEL = os.environ.get("LMCANVAS_DEFAULT_MODEL", "gpt-5.3")
PROXY_AUTH_TOKEN = (os.environ.get("PROXY_AUTH_TOKEN") or "").strip()
LMCANVAS_MODELS = [
    model.strip()
    for model in os.environ.get(
        "LMCANVAS_MODELS",
        "gpt-5.3,claude-opus-4.6,claude-sonnet-4.6,gemini-2.5-flash",
    ).split(",")
    if model.strip()
]
LMCANVAS_USER_AGENT = os.environ.get(
    "LMCANVAS_USER_AGENT", "ai-sdk/5.0.93 runtime/browser"
)


def now_ts() -> int:
    return int(time.time())


def extract_text_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"text", "input_text"}:
                chunks.append(item.get("text", ""))
        return "".join(chunks)
    return str(content)


def openai_messages_to_lmcanvas(messages: list[dict]) -> list[dict]:
    converted = []
    for index, message in enumerate(messages):
        role = message.get("role", "user")
        if role == "tool":
            tool_name = message.get("name") or message.get("tool_call_id") or "tool"
            text = extract_text_content(message.get("content"))
            role = "user"
            content = f"[Tool result from {tool_name}]\n{text}"
        else:
            content = extract_text_content(message.get("content"))
        if message.get("tool_calls"):
            content = (
                content
                + ("\n\n" if content else "")
                + "[Assistant tool calls requested]\n"
                + json.dumps(message["tool_calls"], ensure_ascii=True)
            )
        converted.append(
            {
                "role": role,
                "parts": [{"type": "text", "text": content}],
                "id": message.get("id") or f"msg-{index + 1}",
            }
        )
    return converted


def parse_lmcanvas_sse(text: str):
    events = []
    output_text = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        events.append(event)
        if event.get("type") == "text-delta":
            output_text.append(event.get("delta", ""))
    return "".join(output_text), events


def forward_to_lmcanvas(payload: dict):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        LMCANVAS_CHAT_URL,
        data=data,
        headers={
            "content-type": "application/json",
            "user-agent": LMCANVAS_USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.status, dict(response.headers), response.read().decode("utf-8", "ignore")


def error_response(message: str, code: int = 400):
    return code, {
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": code,
        }
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _request_token(self) -> str:
        auth = (self.headers.get("Authorization") or "").strip()
        api_key = (self.headers.get("X-API-Key") or "").strip()
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return api_key

    def _require_auth(self) -> bool:
        if not PROXY_AUTH_TOKEN:
            return True
        if self._request_token() == PROXY_AUTH_TOKEN:
            return True
        self._send_json(
            401,
            {
                "error": {
                    "message": "Unauthorized",
                    "type": "authentication_error",
                }
            },
        )
        return False

    def _send_sse_headers(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self):
        if not self._require_auth():
            return
        if self.path == "/health":
            self._send_json(200, {"ok": True, "service": "lmcanvas-openai-proxy"})
            return
        if self.path == "/v1/models":
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": model, "object": "model", "owned_by": "lmcanvas"}
                        for model in LMCANVAS_MODELS
                    ],
                },
            )
            return
        self._send_json(404, {"error": {"message": "Not found"}})

    def do_POST(self):
        if not self._require_auth():
            return
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": {"message": "Not found"}})
            return

        try:
            request_json = self._read_json()
        except json.JSONDecodeError:
            self._send_json(*error_response("Body must be valid JSON."))
            return

        messages = request_json.get("messages")
        if not isinstance(messages, list) or not messages:
            self._send_json(*error_response("`messages` must be a non-empty array."))
            return

        model = request_json.get("model") or LMCANVAS_DEFAULT_MODEL
        stream = bool(request_json.get("stream"))
        lmcanvas_payload = {
            "modelId": model,
            "payg": False,
            "reasoning": False,
            "id": f"proxy-{uuid.uuid4().hex[:16]}",
            "messages": openai_messages_to_lmcanvas(messages),
            "trigger": "submit-message",
        }

        try:
            status, headers, body = forward_to_lmcanvas(lmcanvas_payload)
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", "ignore")
            self._send_json(
                exc.code,
                {
                    "error": {
                        "message": error_body or "LMCanvas upstream error",
                        "type": "upstream_error",
                        "code": exc.code,
                    }
                },
            )
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": {"message": str(exc), "type": "proxy_error"}})
            return

        text, events = parse_lmcanvas_sse(body)
        event_types = [event.get("type") for event in events]

        if stream:
            completion_id = f"chatcmpl-{uuid.uuid4().hex}"
            created = now_ts()
            self._send_sse_headers()
            first_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            self.wfile.write(f"data: {json.dumps(first_chunk)}\n\n".encode("utf-8"))
            self.wfile.flush()
            for event in events:
                if event.get("type") != "text-delta":
                    continue
                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": event.get("delta", "")},
                            "finish_reason": None,
                        }
                    ],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode("utf-8"))
                self.wfile.flush()
            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True
            return

        response_payload = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": now_ts(),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": None,
            "_lmcanvas": {
                "status": status,
                "headers": headers,
                "event_types": event_types,
            },
        }
        self._send_json(200, response_payload)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LMCanvas OpenAI proxy listening on http://{HOST}:{PORT}", flush=True)
    print(f"Forwarding chat requests to {LMCANVAS_CHAT_URL}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
