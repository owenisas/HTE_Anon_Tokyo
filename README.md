# watermark-llamacpp

Hybrid watermark gateway for `llama-server`:

- Layer A: step-wise statistical watermarking using dynamic `logit_bias`
- Layer B: zero-width metadata tags in generated text
- Internal verifier endpoint: `/internal/watermark/verify`

## Why a gateway (instead of patching llama.cpp source)

This implementation is a sidecar around `llama-server` and does not modify the `llama.cpp` repo itself.

## Endpoints

- `POST /v1/completions`
- `POST /v1/chat/completions`
- `POST /internal/watermark/verify`

The generation endpoints accept an additional request field:

```json
{
  "watermark": {
    "enabled": true,
    "mode": "hybrid",
    "key_id": 1,
    "opt_out_token": "..."
  }
}
```

Modes:
- `hybrid`: statistical + tag
- `statistical_only`
- `tag_only`

## Notes on Layer A in llama.cpp mode

`llama-server` does not expose per-step custom samplers as a plugin API, so this gateway performs generation one token at a time through `/completion` and updates `logit_bias` each step.

To keep requests practical, it applies sparse greenlist bias (bounded by `WATERMARK_MAX_BIAS_TOKENS`) rather than biasing the entire vocabulary each step.

## Environment

- `UPSTREAM_LLAMACPP_URL` (default `http://127.0.0.1:8080`)
- `WATERMARK_MASTER_KEYS` or `WATERMARK_MASTER_KEY`
- `WATERMARK_OPTOUT_SECRET`
- `WATERMARK_ACTIVE_KEY_ID`
- `WATERMARK_SCHEMA_VERSION`
- `WATERMARK_ISSUER_ID`
- `WATERMARK_MODEL_ID_MAP` (JSON)
- `WATERMARK_MODEL_VERSION_MAP` (JSON)
- `WATERMARK_CONTEXT_WIDTH` (default 2)
- `WATERMARK_GREENLIST_RATIO` (default 0.25)
- `WATERMARK_BIAS_DELTA` (default 1.0)
- `WATERMARK_MAX_BIAS_TOKENS` (default 2048)
- `WATERMARK_REPEAT_INTERVAL_TOKENS` (default 160)

## Run

```bash
watermark-llamacpp-gateway --host 0.0.0.0 --port 9002
```

Point your client to `http://localhost:9002/v1`.

## Fast install for multiple inference SDKs

Install helper CLI:

```bash
pip install -e .
watermark-install-engines --list-engines
```

Install everything in one shot:

```bash
watermark-install-engines --engines all --upgrade
```

Install only selected engines:

```bash
watermark-install-engines --engines vllm,sglang,mlx-lm
```

Preview command without installing:

```bash
watermark-install-engines --engines vllm,transformers --dry-run
```

## SDK adapters

This repo now includes lightweight adapter classes in
`watermark_llamacpp.integrations` for:

- `vLLM`: `VLLMStatisticalLogitsProcessor`
- `SGLang`: `SGLangCustomLogitsProcessor`
- `MLX-LM`: `MLXLMLogitsProcessor`
- Shared text tag injector: `TagTextPostProcessor`

Example:

```python
from watermark_llamacpp.config import WatermarkConfig
from watermark_llamacpp.integrations import (
    VLLMStatisticalLogitsProcessor,
    build_vllm_tag_postprocessor,
)

cfg = WatermarkConfig()
logits_processor = VLLMStatisticalLogitsProcessor(cfg=cfg, model_name="my-model")
tagger = build_vllm_tag_postprocessor(cfg=cfg, model_name="my-model")

text_chunk = tagger.inject("generated text ", finalize=False)
final_text = tagger.inject(text_chunk, finalize=True)
```

Note: in LM Studio OpenAI-compatible mode, statistical watermarking is not available
with this gateway path; use `tag_only` there.
