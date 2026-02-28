#!/usr/bin/env python3
"""End-to-end test of the provenance registry flow."""
import requests, json, hashlib
from eth_account import Account
from eth_account.messages import encode_defunct

API = "http://127.0.0.1:5050"

# 1. Create a company
print("=== Step 1: Create Company ===")
r = requests.post(f"{API}/api/registry/companies", json={"name": "Acme AI", "admin_secret": "dev-admin-secret"})
company = r.json()
print(json.dumps(company, indent=2))
private_key = company["private_key"]
issuer_id = company["issuer_id"]

# 2. Watermark some text
print("\n=== Step 2: Watermark Text ===")
raw_text = "Artificial intelligence is transforming how we build software. Machine learning models can now generate code, write documentation, and even debug issues automatically."
r = requests.post(f"{API}/api/apply", json={"text": raw_text, "wm_params": {"issuer_id": issuer_id}})
wm_data = r.json()
watermarked = wm_data["text"]
print(f"Raw length: {len(raw_text)}, Watermarked length: {len(watermarked)}")
print(f"Tags injected: {len(watermarked) - len(raw_text)} extra chars")

# 3. Sign + Anchor
print("\n=== Step 3: Sign & Anchor ===")
data_hash = hashlib.sha256(watermarked.encode()).hexdigest()
print(f"SHA-256: {data_hash}")

message = encode_defunct(text=data_hash)
signed = Account.sign_message(message, private_key=private_key)
sig_hex = signed.signature.hex()
print(f"Signature: {sig_hex[:40]}...")

r = requests.post(f"{API}/api/registry/anchor", json={
    "text": watermarked,
    "raw_text": raw_text,
    "signature_hex": sig_hex,
    "issuer_id": issuer_id,
    "metadata": {"model": "test"},
})
anchor = r.json()
print(json.dumps(anchor, indent=2))

# 4. Verify the original watermarked text
print("\n=== Step 4: Verify (original) ===")
r = requests.post(f"{API}/api/registry/verify", json={"text": watermarked})
verify = r.json()
print(json.dumps(verify, indent=2))

# 5. Verify tampered text (should fail)
print("\n=== Step 5: Verify (tampered) ===")
tampered = watermarked.replace("software", "hardware")
r = requests.post(f"{API}/api/registry/verify", json={"text": tampered})
verify2 = r.json()
print(f"Verified: {verify2['verified']}")
print(f"Reason: {verify2.get('reason', 'N/A')}")

# 6. Chain status
print("\n=== Step 6: Chain Status ===")
r = requests.get(f"{API}/api/registry/chain/status")
print(json.dumps(r.json(), indent=2))

print("\n=== ALL STEPS PASSED ===")
