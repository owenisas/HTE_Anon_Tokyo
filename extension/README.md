# Text Fetcher — Chrome Extension

Detects zero-width character watermarks embedded in web page text. Companion tool for the [watermark-llamacpp](../README.md) system.

## Features

- **Auto-Detect mode** — Highlights text containing hidden zero-width characters directly on the page. Red = confirmed watermark tag, yellow = suspicious, purple = hidden chars present.
- **Selection Scan mode** — Select any text and a floating badge appears showing whether it contains AI watermarks.
- Decodes the full watermark payload (schema version, issuer ID, model ID, key ID) with CRC-8 validation.
- Detects 14 types of zero-width / invisible Unicode characters.

## Installation

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked** and select this `extension/` folder
4. The extension icon appears in your toolbar

## Usage

1. Click the extension icon to open the control panel
2. Choose a mode:
   - **Auto-Detect** — scans the page and highlights tainted text
   - **Selection Scan** — select text to see a floating verdict badge
3. The active tab reloads automatically when switching modes

## Files

```
manifest.json    — Chrome MV3 extension config
background.js    — Service worker (state management, badge)
content.js       — Content script (DOM scanning, highlighting, selection analysis)
content.css      — Highlight styles and floating badge
popup.html/css/js — Mode switcher popup UI
test_page.html   — Test page with embedded zero-width characters
icons/           — Extension icons (add 16/48/128px PNGs)
```

## Zero-Width Characters Detected

| Unicode | Name | Watermark Role |
|---------|------|---------------|
| U+200B | Zero-Width Space (ZWSP) | Bit 0 |
| U+200C | Zero-Width Non-Joiner (ZWNJ) | Bit 1 |
| U+2063 | Invisible Separator | Tag start delimiter |
| U+2064 | Invisible Plus | Tag end delimiter |
| U+200D | Zero-Width Joiner (ZWJ) | — |
| U+200E/F | LRM / RLM | — |
| U+2060 | Word Joiner | — |
| U+FEFF | BOM | — |
| + 6 more | Various invisible chars | — |
