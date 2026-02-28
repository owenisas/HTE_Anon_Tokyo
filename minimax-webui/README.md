# MiniMax WebUI + Provenance Registry Demo

This folder contains a FastAPI web app and a provenance demo flow for watermark verification.

## What was implemented

### 1) Registry navigation consistency
All registry pages now include the same top navigation links:
- Dashboard
- Demo
- Companies
- Anchor
- Verify
- Chain

Updated pages:
- `static/registry/companies.html`
- `static/registry/anchor.html`
- `static/registry/verify.html`
- `static/registry/chain.html`

### 2) Demo company flow uses real model output
The **Company Operator View** (`/registry/demo/company`) now supports:
- Model provider selection (`MiniMax` or `Bedrock`)
- Model selection based on provider
- Prompt and system prompt input
- Live generation via `/api/chat`
- Auto-filling generated response into the verifiable-output flow before watermark/sign/anchor

Updated page:
- `static/registry/demo-company.html`

## Run locally

```bash
cd minimax-webui
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
MINIMAX_API_KEY='YOUR_KEY' ./.venv/bin/python app.py
```

Open:
- Dashboard: `http://127.0.0.1:5050/registry`
- Role demo: `http://127.0.0.1:5050/registry/demo`
- Company view: `http://127.0.0.1:5050/registry/demo/company`
- User view: `http://127.0.0.1:5050/registry/demo/user`

> Bedrock generation requires valid AWS credentials configured for `boto3`.

## Extension

The browser extension is in the sibling folder:
- `../extension`

Load it via Chrome:
1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

This extension can be used to detect zero-width watermark signals in text rendered on webpages.

## Additional docs

- Demo script/runbook: `DEMO_RUNBOOK.md`
