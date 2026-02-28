/* ================================================================== */
/*  Zero-Width Watermark Detector — Content Script                    */
/* ================================================================== */

(() => {
  if (window.__zwmLoaded) return;
  window.__zwmLoaded = true;

  /* -------------------------------------------------------------- */
  /*  Constants                                                       */
  /* -------------------------------------------------------------- */

  const ZW_CHARS = {
    "\u200B": "ZWSP",
    "\u200C": "ZWNJ",
    "\u200D": "ZWJ",
    "\u200E": "LRM",
    "\u200F": "RLM",
    "\u2060": "WJ",
    "\u2061": "FnApply",
    "\u2062": "InvTimes",
    "\u2063": "InvSep",
    "\u2064": "InvPlus",
    "\uFEFF": "BOM",
    "\u034F": "CGJ",
    "\u061C": "ALM",
    "\u180E": "MVS",
  };

  const ZW_PATTERN = "[" + Object.keys(ZW_CHARS).join("") + "]";
  const ZW_TEST   = new RegExp(ZW_PATTERN);
  const ZW_GLOBAL = new RegExp(ZW_PATTERN, "g");
  const ZW_STRIP  = new RegExp(ZW_PATTERN, "g");

  const TAG_START = "\u2063";
  const TAG_END   = "\u2064";
  const BIT_ZERO  = "\u200B";
  const BIT_ONE   = "\u200C";

  const TAG_REGEX = new RegExp(
    esc(TAG_START) + "([" + esc(BIT_ZERO) + esc(BIT_ONE) + "]{64})" + esc(TAG_END),
    "g"
  );

  function esc(c) { return c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  const MARKER_ATTR = "data-zwm";
  const FLOAT_ID    = "zwm-float";

  /* -------------------------------------------------------------- */
  /*  CRC-8 + payload (port of payload.py)                           */
  /* -------------------------------------------------------------- */

  function crc8(bytes) {
    let crc = 0;
    for (const b of bytes) {
      crc ^= b;
      for (let i = 0; i < 8; i++)
        crc = crc & 0x80 ? ((crc << 1) ^ 0x07) & 0xff : (crc << 1) & 0xff;
    }
    return crc;
  }

  function unpackPayload(bits64) {
    const val = BigInt("0b" + bits64);
    const raw56 = val >> 8n;
    const checksum = Number(val & 0xFFn);
    const rawBytes = [];
    for (let i = 6; i >= 0; i--) rawBytes.push(Number((raw56 >> BigInt(i * 8)) & 0xFFn));
    return {
      valid: crc8(rawBytes) === checksum,
      schema: Number((raw56 >> 52n) & 0xFn),
      issuer: Number((raw56 >> 40n) & 0xFFFn),
      model:  Number((raw56 >> 24n) & 0xFFFFn),
      ver:    Number((raw56 >> 8n) & 0xFFFFn),
      keyId:  Number(raw56 & 0xFFn),
    };
  }

  /* -------------------------------------------------------------- */
  /*  Analyze a string for ZW chars and watermark tags               */
  /* -------------------------------------------------------------- */

  function analyzeText(text) {
    if (!text) return { zwCount: 0, zwTypes: {}, tags: [], verdict: "clean" };

    let zwCount = 0;
    const zwTypes = {};
    for (const m of text.matchAll(ZW_GLOBAL)) {
      zwCount++;
      const name = ZW_CHARS[m[0]] || "?";
      zwTypes[name] = (zwTypes[name] || 0) + 1;
    }

    const tags = [];
    TAG_REGEX.lastIndex = 0;
    for (const m of text.matchAll(TAG_REGEX)) {
      const bits = [...m[1]].map(c => c === BIT_ONE ? "1" : "0").join("");
      tags.push(unpackPayload(bits));
    }

    let verdict = "clean";
    if (tags.length > 0 && tags.some(t => t.valid)) {
      verdict = "watermarked";
    } else if (tags.length > 0) {
      verdict = "suspicious";
    } else if (zwCount > 0) {
      verdict = "suspicious";
    }

    return { zwCount, zwTypes, tags, verdict };
  }

  /* -------------------------------------------------------------- */
  /*  MODE 1: Auto-detect — highlight words that contain ZW chars    */
  /* -------------------------------------------------------------- */

  function runAutoDetect() {
    clearAutoDetect();

    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          const p = node.parentElement;
          if (!p) return NodeFilter.FILTER_REJECT;
          const tag = p.tagName;
          if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT" ||
              tag === "TEXTAREA" || tag === "INPUT")
            return NodeFilter.FILTER_REJECT;
          if (p.closest("#" + FLOAT_ID))
            return NodeFilter.FILTER_REJECT;
          if (p.hasAttribute(MARKER_ATTR))
            return NodeFilter.FILTER_REJECT;
          if (ZW_TEST.test(node.textContent))
            return NodeFilter.FILTER_ACCEPT;
          return NodeFilter.FILTER_SKIP;
        },
      }
    );

    const nodesToWrap = [];
    while (walker.nextNode()) nodesToWrap.push(walker.currentNode);

    for (const textNode of nodesToWrap) {
      highlightTaintedText(textNode);
    }
  }

  function highlightTaintedText(textNode) {
    const raw = textNode.textContent;
    if (!raw) return;

    const result = analyzeText(raw);
    const visibleText = raw.replace(ZW_STRIP, "");

    if (!visibleText.trim()) return;

    const wrapper = document.createElement("span");
    wrapper.setAttribute(MARKER_ATTR, "1");
    wrapper.textContent = visibleText;

    if (result.tags.length > 0 && result.tags.some(t => t.valid)) {
      wrapper.className = "zwm-tainted-watermark";
      wrapper.title = "AI watermark tag detected (" + result.zwCount + " hidden chars)";
    } else if (result.tags.length > 0) {
      wrapper.className = "zwm-tainted-suspicious";
      wrapper.title = "Suspicious watermark tag (" + result.zwCount + " hidden chars, CRC invalid)";
    } else {
      wrapper.className = "zwm-tainted";
      wrapper.title = result.zwCount + " hidden zero-width char(s) found in this text";
    }

    textNode.parentNode.replaceChild(wrapper, textNode);
  }

  function clearAutoDetect() {
    document.querySelectorAll("[" + MARKER_ATTR + "]").forEach(el => {
      const text = document.createTextNode(el.textContent);
      el.replaceWith(text);
    });
  }

  /* -------------------------------------------------------------- */
  /*  MODE 2: Selection scan — floating result on mouseup            */
  /* -------------------------------------------------------------- */

  function getRawSelectedText() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return "";

    // cloneContents preserves all characters including zero-width,
    // unlike sel.toString() which strips them
    try {
      const frag = sel.getRangeAt(0).cloneContents();
      return frag.textContent || "";
    } catch {
      return sel.toString() || "";
    }
  }

  let floatEl = null;

  function createFloat() {
    if (floatEl) return floatEl;
    floatEl = document.createElement("div");
    floatEl.id = FLOAT_ID;
    document.body.appendChild(floatEl);
    return floatEl;
  }

  function hideFloat() {
    if (floatEl) floatEl.classList.remove("zwm-float-visible");
  }

  function showFloat(x, y, result) {
    const el = createFloat();

    let icon, label, color, detail;

    if (result.verdict === "watermarked") {
      icon  = "\u26A0\uFE0F";
      label = "AI Watermark Detected";
      color = "zwm-float-alert";
      const t = result.tags.find(t => t.valid);
      detail = t
        ? "CRC valid &bull; Issuer " + t.issuer + " &bull; Model " + t.model + " &bull; Key " + t.keyId
        : result.tags.length + " tag(s) found";
    } else if (result.verdict === "suspicious") {
      icon  = "\uD83D\uDD0D";
      label = "Suspicious \u2014 Hidden Chars Found";
      color = "zwm-float-warn";
      const types = Object.entries(result.zwTypes || {}).map(function(e) { return e[0] + ":" + e[1]; }).join(", ");
      detail = result.zwCount + " zero-width char(s) \u2014 " + types;
    } else {
      icon  = "\u2705";
      label = "Clean \u2014 No Hidden Characters";
      color = "zwm-float-clean";
      detail = "No zero-width or watermark characters detected.";
    }

    el.className = "zwm-float-visible " + color;
    el.innerHTML =
      '<div class="zwm-float-header">' + icon + ' <strong>' + label + '</strong></div>' +
      '<div class="zwm-float-detail">' + detail + '</div>' +
      '<div class="zwm-float-meta">' + result.zwCount + ' ZW chars &bull; ' + result.tags.length + ' tag(s)</div>';

    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const left = Math.min(x + 12, vw - 340);
    const top  = y + 24 + 200 > vh ? y - 130 : y + 24;

    el.style.left = Math.max(8, left) + "px";
    el.style.top  = Math.max(8, top) + "px";
  }

  function onSelectionMouseUp(e) {
    if (floatEl && floatEl.contains(e.target)) return;

    const text = getRawSelectedText();

    if (!text || text.length < 2) {
      hideFloat();
      return;
    }

    const result = analyzeText(text);
    showFloat(e.clientX, e.clientY, result);
  }

  function onSelectionKeyUp() {
    const sel = window.getSelection();
    if (!sel || !sel.toString()) hideFloat();
  }

  let selectionScanActive = false;

  function enableSelectionScan() {
    if (selectionScanActive) return;
    selectionScanActive = true;
    document.addEventListener("mouseup", onSelectionMouseUp, true);
    document.addEventListener("keyup", onSelectionKeyUp, true);
  }

  function disableSelectionScan() {
    if (!selectionScanActive) return;
    selectionScanActive = false;
    document.removeEventListener("mouseup", onSelectionMouseUp, true);
    document.removeEventListener("keyup", onSelectionKeyUp, true);
    hideFloat();
  }

  document.addEventListener("mousedown", function(e) {
    if (floatEl && !floatEl.contains(e.target)) hideFloat();
  }, true);

  /* -------------------------------------------------------------- */
  /*  State management — single mode: "off" | "autoDetect" | "selectionScan" */
  /* -------------------------------------------------------------- */

  function applyMode(mode) {
    clearAutoDetect();
    disableSelectionScan();

    if (mode === "autoDetect")    runAutoDetect();
    if (mode === "selectionScan") enableSelectionScan();
  }

  // On page load, read the active mode and apply it
  chrome.storage.local.get({ mode: "off" }, (s) => {
    applyMode(s.mode);
  });
})();
