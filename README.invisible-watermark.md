# Invisible Text Watermark Plan (Team of 5)

This README is the execution plan for shipping **invisible text watermarking** support and tooling.

Scope is intentionally focused on the zero-width tag path (Layer B).  
Out of scope for this plan: step-wise statistical/L2 generation watermarking.

---

## 1) Goal

Build a production-ready workflow that can:

1. Detect zero-width watermark tags in text.
2. Parse/decode the embedded payload.
3. Validate payload integrity (CRC).
4. Show metadata in a Chrome extension UI.
5. Support optional server-side verification and future integrations.

---

## 2) Existing Ground Truth in This Repo

Current implementation already provides the core logic:

- Tag encoding/decoding: `src/watermark_llamacpp/zero_width.py`
- Payload packing/unpacking + CRC8: `src/watermark_llamacpp/payload.py`
- Verification endpoint: `POST /internal/watermark/verify` in `src/watermark_llamacpp/gateway.py`

### Zero-width character mapping

- `0` bit: U+200B (ZWSP)
- `1` bit: U+200C (ZWNJ)
- Start delimiter: U+2063 (Invisible Separator)
- End delimiter: U+2064 (Invisible Plus)

Tag format:

- 1 start char + 64 payload bits + 1 end char

### Payload bit layout (64 bits total)

- Top 56 bits metadata:
  - `schema_version`: 4 bits
  - `issuer_id`: 12 bits
  - `model_id`: 16 bits
  - `model_version_id`: 16 bits
  - `key_id`: 8 bits
- Bottom 8 bits:
  - CRC8 checksum (`poly = 0x07`) over the top 56 bits (7 bytes)

---

## 3) Team Assignment (5 People)

## Owner A - Core Parser + JS Library

**Mission:** Port Python decode/CRC logic to TypeScript for browser use.

Deliverables:

- `packages/wm-parser/src/decode.ts`
- `packages/wm-parser/src/crc8.ts`
- `packages/wm-parser/src/types.ts`
- Unit tests with known vectors from Python output

Acceptance criteria:

- Decodes all valid tags found by Python decoder.
- Produces identical metadata fields and CRC validity.
- Handles malformed/partial tags without crashing.

---

## Owner B - Chrome Extension (MV3) Content Detection

**Mission:** Detect watermark candidates from web page text safely and efficiently.

Deliverables:

- `chrome-extension/manifest.json` (MV3)
- `chrome-extension/src/content.ts`
- Incremental scanner for:
  - selected text
  - focused editable element
  - visible page text fallback

Acceptance criteria:

- Can detect count of watermark tags in real pages.
- Scanning does not freeze UI on large pages.
- Works on major Chromium browsers.

---

## Owner C - Chrome Extension UI + Metadata Visualization

**Mission:** Build popup/sidepanel UI showing decode results and confidence.

Deliverables:

- `chrome-extension/src/popup/*` or `sidepanel/*`
- Result cards showing:
  - tag count
  - CRC valid/invalid
  - parsed fields (`schema_version`, `issuer_id`, `model_id`, `model_version_id`, `key_id`)
  - raw payload hex and bits

Acceptance criteria:

- One-click scan and clear UX states (no tag / invalid / valid).
- Copy buttons for JSON and raw payload.
- Export result as JSON file.

---

## Owner D - Backend Verification + API Integration

**Mission:** Support optional verification against gateway endpoint.

Deliverables:

- API client module in extension (or optional local helper service)
- Integration with `POST /internal/watermark/verify`
- Retry/timeout/error handling

Acceptance criteria:

- Decoded local results can be compared with server verification output.
- CORS strategy documented and implemented (direct call, local bridge, or hosted verifier).
- API failures degrade gracefully to local-only decoding.

---

## Owner E - QA, Benchmarks, Security, and Docs

**Mission:** Validate correctness, performance, and abuse resistance.

Deliverables:

- Test corpus (valid, invalid, adversarial, large text)
- Benchmark scripts for scanning throughput
- Abuse cases:
  - fake delimiters
  - random zero-width noise
  - repeated tags
  - mixed Unicode normalization inputs
- End-user docs + troubleshooting

Acceptance criteria:

- Test matrix green in CI.
- Latency and memory budgets documented.
- False-positive and false-negative profile reported.

---

## 4) Suggested Repo Structure

```text
watermark-llamacpp/
  README.invisible-watermark.md
  packages/
    wm-parser/
      src/
        decode.ts
        crc8.ts
        types.ts
      test/
        decode.test.ts
  chrome-extension/
    manifest.json
    src/
      content.ts
      background.ts
      popup.tsx
      parser-adapter.ts
    public/
      icons/
```

---

## 5) Chrome Extension Build Guide (MV3)

### Feature set (MVP)

1. User clicks extension icon.
2. Extension scans current tab text for watermark tags.
3. Parser decodes each candidate.
4. UI shows metadata and validity.
5. Optional: call verifier API and display `status`, `payload`, and explanations.

### Architecture

- **Content script**
  - Extracts text from DOM (with limits/chunking).
  - Sends extracted text to background/service worker.
- **Background/service worker**
  - Runs parser (or delegates to shared parser lib).
  - Handles optional API calls.
- **Popup/sidepanel**
  - Displays summary + detail.
  - Allows exporting JSON.

### Parsing pipeline (browser)

1. Locate all start/end-delimited candidates.
2. Ensure body length is exactly 64 bits worth of mapped chars.
3. Convert chars to bitstring (`200B -> 0`, `200C -> 1`).
4. Parse `payload64` into fields.
5. Recompute CRC8 and mark valid/invalid.

### Performance notes

- Scan incrementally (chunk large text nodes).
- Cap maximum scanned characters per click (configurable).
- Use debounced scans for auto mode.
- Keep parser pure and sync; move heavy scan orchestration off UI thread if needed.

### UX states

- No watermark detected
- Watermark detected but CRC invalid
- Watermark verified locally (CRC valid)
- Watermark verified by server (optional)

---

## 6) Milestones (2 Weeks Example)

### Week 1

- Day 1-2: Owner A ships parser + tests.
- Day 2-4: Owner B ships content scanning MVP.
- Day 3-5: Owner C ships popup UI with local decode view.
- Day 5: Integration checkpoint (A+B+C).

### Week 2

- Day 6-8: Owner D adds verifier integration and resilient error handling.
- Day 7-9: Owner E runs corpus/benchmark/security tests.
- Day 10: Hardening, docs polish, release candidate.

---

## 7) Definition of Done

- Extension can detect and parse invisible watermark tags from real web text.
- Metadata display is accurate and understandable.
- CRC validity is correctly reported.
- Optional server verification works or fails safely.
- Tests cover parser correctness and scanning edge cases.
- User docs explain interpretation and limitations.

---

## 8) Other Ways To Use This (Beyond Chrome Extension)

1. **Moderation dashboard plugin**: scan user-submitted text and attach provenance metadata.
2. **CMS/editor plugin**: verify generated content before publication.
3. **Email/security gateway**: classify incoming AI-generated content streams.
4. **CLI audit tool**: batch-scan text files and export CSV/JSON reports.
5. **Chat platform bot**: annotate messages with detected watermark metadata.
6. **Data pipeline enrichment**: add watermark fields to warehouse records.
7. **Forensic toolkit**: compare suspected copies by watermark metadata signatures.

---

## 9) Risks and Mitigations

- **Risk:** Some systems strip zero-width characters.
  - **Mitigation:** Treat absence as inconclusive, not proof of no watermark.
- **Risk:** Adversary inserts random zero-width chars.
  - **Mitigation:** Strict delimiters + CRC validation.
- **Risk:** Browser extraction misses hidden/virtualized text.
  - **Mitigation:** Support multiple extraction modes and manual paste input.
- **Risk:** Privacy concerns when sending text to verifier API.
  - **Mitigation:** Default to local decode; opt-in remote verify only.

---

## 10) Quick Start for Team

1. Freeze parser spec from Python implementation.
2. Build and test TypeScript parser first.
3. Integrate parser into extension scanning flow.
4. Add UI and export.
5. Add optional verifier API.
6. Run benchmark + adversarial test suite before release.

If needed, we can split this into separate implementation docs:

- `docs/parser-spec.md`
- `docs/extension-architecture.md`
- `docs/testing-plan.md`

