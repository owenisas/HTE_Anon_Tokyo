# Provenance Registry Demo Runbook

## Repository and locations

- Remote repository: `https://github.com/owenisas/HTE_Anon_Tokyo.git`
- Workspace root: `/Users/user/Documents/random-AI-Projects`
- Demo app folder: `/Users/user/Documents/random-AI-Projects/minimax-webui`

## What this demo shows

Two role views for provenance traceability:

1. **Company Operator View**
   - Registers company credentials
   - Watermarks model output
   - Signs hash with private key
   - Anchors response to simulated chain

2. **End User View**
   - Receives model output
   - Verifies provenance without private key
   - Sees verified/failed result and chain metadata

## Prerequisites

- macOS/Linux shell
- Python 3.10+
- Internet access (for CDN `ethers.js` and Google Fonts)

## One-time setup

From `minimax-webui`:

```bash
cd /Users/user/Documents/random-AI-Projects/minimax-webui
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

## Start the server

```bash
cd /Users/user/Documents/random-AI-Projects/minimax-webui
MINIMAX_API_KEY='YOUR_KEY_HERE' ./.venv/bin/python app.py
```

Notes:
- For registry-only demo, `MINIMAX_API_KEY` can be a placeholder (for example `test`).
- Default port is `5050`.

If port is busy:

```bash
lsof -ti:5050 | xargs kill -9
```

## Demo URLs

- Dashboard: `http://127.0.0.1:5050/registry`
- Role selector: `http://127.0.0.1:5050/registry/demo`
- Company view: `http://127.0.0.1:5050/registry/demo/company`
- User view: `http://127.0.0.1:5050/registry/demo/user`
- Chain explorer: `http://127.0.0.1:5050/registry/chain`

## Admin secret (company registration)

- Default admin secret: `dev-admin-secret`
- Override with environment variable before start:

```bash
export REGISTRY_ADMIN_SECRET='your-secret'
```

## Recommended live demo script (3-5 minutes)

1. Open **Role selector** (`/registry/demo`) and explain the two personas.
2. Go to **Company View** (`/registry/demo/company`).
3. Register company:
   - Company Name: `Acme AI`
   - Admin Secret: `dev-admin-secret` (or your override)
4. Paste a sample model response.
5. Click **Watermark, Sign, and Anchor**.
6. Show receipt details (hash, block, tx hash).
7. Open **User View** (`/registry/demo/user`).
8. Click **Use Latest Anchored Output** (or **Use Output from Company View**).
9. Click **Verify Provenance** and show the VERIFIED state.
10. Optional: Change one word and verify again to show FAILED/tamper detection.
11. Open **Chain Explorer** to show the anchored block.

## Quick validation checks

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5050/registry/demo
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5050/registry/demo/company
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5050/registry/demo/user
curl -s http://127.0.0.1:5050/api/registry/demo/latest-response | head -c 200
```

## Troubleshooting

- **Button click seems to do nothing**
  - Hard refresh page: `Cmd+Shift+R`
  - Check browser console for script/load errors
- **`401 Unauthorized` during company registration**
  - Admin secret mismatch; verify `REGISTRY_ADMIN_SECRET` and input value
- **Verify fails unexpectedly**
  - Ensure text is exactly the anchored output (no edits/normalization)
- **Server import error for watermark package**
  - Run from the project paths in this runbook; app auto-detects known source locations

## Stop server

Press `Ctrl+C` in the terminal where `app.py` is running.
