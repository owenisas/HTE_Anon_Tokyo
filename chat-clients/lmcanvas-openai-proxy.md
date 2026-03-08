# LMCanvas OpenAI Proxy

This shim exposes a minimal OpenAI-compatible `/v1/chat/completions` API and forwards requests to `https://lmcanvas.ai/api/chat`.

## Start

```bash
python3 /Users/user/Documents/random-AI-Projects/chat-clients/lmcanvas-openai-proxy.py
```

Default listen address:

- Base URL: `http://127.0.0.1:8787/v1`
- Health: `http://127.0.0.1:8787/health`
- Models: `http://127.0.0.1:8787/v1/models`

## Environment variables

```bash
export LMCANVAS_PROXY_HOST=127.0.0.1
export LMCANVAS_PROXY_PORT=8787
export PROXY_AUTH_TOKEN=your-secret-token
export LMCANVAS_CHAT_URL=https://lmcanvas.ai/api/chat
export LMCANVAS_DEFAULT_MODEL=gpt-5.3
export LMCANVAS_MODELS=gpt-5.3,claude-opus-4.6,claude-sonnet-4.6,gemini-2.5-flash
```

## Example

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{
    "model": "gpt-5.3",
    "messages": [
      {"role": "system", "content": "Reply briefly."},
      {"role": "user", "content": "Say hello."}
    ]
  }'
```

## Integration notes

- This is meant to be easy to point tools like OpenClaw at if they support OpenAI-compatible chat endpoints.
- If `PROXY_AUTH_TOKEN` is set, send it as `Authorization: Bearer ...` or `X-API-Key`.
- Caller-supplied `system` messages are forwarded.
- Multi-turn `messages` are forwarded.
- `tool` role and `tool_calls` are flattened into text best-effort because LMCanvas rejected raw UI-style tool messages in testing.
- Built-in LMCanvas tool usage such as `web_search` may still happen internally, but it is not exposed as OpenAI tool calls by this shim.
