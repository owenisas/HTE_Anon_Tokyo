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
  const FIELD_MARK_ATTR = "data-zwm-field";
  const FLOAT_ID    = "zwm-float";
  let currentMode = "off";
  let autoDetectObserver = null;
  let autoDetectScheduled = false;

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
    ZW_GLOBAL.lastIndex = 0;
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
          if (p.isContentEditable || p.closest("[contenteditable=''], [contenteditable='true'], [contenteditable='plaintext-only']"))
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

    highlightTaintedEditableFields();
  }

  function getEditableText(el) {
    if (!el) return "";
    if (el.tagName === "TEXTAREA") return el.value || "";
    if (el.tagName === "INPUT") return el.value || "";
    if (el.isContentEditable) return el.textContent || "";
    return "";
  }

  function getEditableCandidates() {
    return document.querySelectorAll("textarea, input, [contenteditable=''], [contenteditable='true'], [contenteditable='plaintext-only']");
  }

  function highlightTaintedEditableFields() {
    const candidates = getEditableCandidates();
    candidates.forEach((el) => {
      if (!el || el.id === FLOAT_ID || (el.closest && el.closest("#" + FLOAT_ID))) return;
      if (el.tagName === "INPUT") {
        const t = (el.type || "text").toLowerCase();
        const allowed = ["text", "search", "email", "url", "tel", "password", ""];
        if (!allowed.includes(t)) return;
      }

      const raw = getEditableText(el);
      if (!raw) return;

      const result = analyzeText(raw);
      if (result.zwCount <= 0) return;

      el.setAttribute(FIELD_MARK_ATTR, "1");
      el.classList.remove("zwm-field-tainted", "zwm-field-suspicious", "zwm-field-watermark");

      if (result.tags.length > 0 && result.tags.some((t) => t.valid)) {
        el.classList.add("zwm-field-watermark");
        el.title = "AI watermark tag detected (" + result.zwCount + " hidden chars)";
      } else if (result.tags.length > 0) {
        el.classList.add("zwm-field-suspicious");
        el.title = "Suspicious watermark tag (" + result.zwCount + " hidden chars, CRC invalid)";
      } else {
        el.classList.add("zwm-field-tainted");
        el.title = result.zwCount + " hidden zero-width char(s) found in this field";
      }
    });
  }

  function scheduleAutoDetect() {
    if (autoDetectScheduled) return;
    autoDetectScheduled = true;
    requestAnimationFrame(() => {
      autoDetectScheduled = false;
      if (currentMode === "autoDetect") {
        if (autoDetectObserver) autoDetectObserver.disconnect();
        runAutoDetect();
        if (autoDetectObserver) {
          autoDetectObserver.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true,
          });
        }
      }
    });
  }

  function enableAutoDetect() {
    if (autoDetectObserver) return;
    autoDetectObserver = new MutationObserver(() => {
      scheduleAutoDetect();
    });

    // Initial run
    if (autoDetectObserver) autoDetectObserver.disconnect();
    runAutoDetect();
    if (autoDetectObserver) {
      autoDetectObserver.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    }
  }

  function disableAutoDetect() {
    if (autoDetectObserver) {
      autoDetectObserver.disconnect();
      autoDetectObserver = null;
    }
    clearAutoDetect();
  }

  function highlightTaintedText(textNode) {
    const raw = textNode.textContent;
    if (!raw) return;

    const result = analyzeText(raw);
    const visibleText = raw.replace(ZW_STRIP, "");

    if (!visibleText.trim()) return;

    const wrapper = document.createElement("span");
    wrapper.setAttribute(MARKER_ATTR, "1");
    wrapper.setAttribute("data-zwm-orig", raw);
    wrapper.textContent = raw; // Preserve ZW chars in the DOM

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
      const origText = el.getAttribute("data-zwm-orig") || el.textContent;
      const text = document.createTextNode(origText);
      el.replaceWith(text);
    });

    document.querySelectorAll("[" + FIELD_MARK_ATTR + "]").forEach((el) => {
      el.removeAttribute(FIELD_MARK_ATTR);
      el.classList.remove("zwm-field-tainted", "zwm-field-suspicious", "zwm-field-watermark");
      if (el.title && el.title.includes("hidden")) {
        el.removeAttribute("title");
      }
    });
  }

  /* -------------------------------------------------------------- */
  /*  MODE 2: Selection scan — floating result on mouseup            */
  /* -------------------------------------------------------------- */

  function getRawSelectedText() {
    const active = document.activeElement;
    if (active && (active.tagName === "TEXTAREA" || active.tagName === "INPUT")) {
      const start = active.selectionStart;
      const end = active.selectionEnd;
      if (typeof start === "number" && typeof end === "number" && end > start) {
        return (active.value || "").slice(start, end);
      }
    }

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

  function getHoverRawText(target, x, y) {
    if (!target) return "";

    const el = target.nodeType === Node.ELEMENT_NODE
      ? target
      : (target.parentElement || null);
    if (!el) return "";

    if (el.id === FLOAT_ID || (el.closest && el.closest("#" + FLOAT_ID))) {
      return "";
    }

    const editable = el.closest("textarea, input, [contenteditable=''], [contenteditable='true'], [contenteditable='plaintext-only']");
    if (editable) {
      return getEditableText(editable);
    }

    // Prefer the exact text node under cursor for better precision on regular DOM text.
    try {
      let pointNode = null;
      if (typeof document.caretPositionFromPoint === "function") {
        const pos = document.caretPositionFromPoint(x, y);
        pointNode = pos && pos.offsetNode ? pos.offsetNode : null;
      } else if (typeof document.caretRangeFromPoint === "function") {
        const range = document.caretRangeFromPoint(x, y);
        pointNode = range && range.startContainer ? range.startContainer : null;
      }

      if (pointNode) {
        if (pointNode.nodeType === Node.TEXT_NODE) {
          return pointNode.textContent || "";
        }
        if (pointNode.nodeType === Node.ELEMENT_NODE) {
          const pointEl = pointNode;
          const badTag = (pointEl.tagName || "").toUpperCase();
          if (badTag !== "SCRIPT" && badTag !== "STYLE" && badTag !== "NOSCRIPT") {
            return pointEl.textContent || "";
          }
        }
      }
    } catch {
      // Fallback to element textContent below.
    }

    const tag = (el.tagName || "").toUpperCase();
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") {
      return "";
    }

    return el.textContent || "";
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

  function showFloat(x, y, result, text_for_verify) {
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

    // Add "Verify Provenance" button for watermarked or suspicious text
    if (result.verdict === "watermarked" || result.verdict === "suspicious") {
      var verifyBtn = document.createElement("button");
      verifyBtn.textContent = "\uD83D\uDD17 Verify Provenance";
      verifyBtn.className = "zwm-float-verify-btn";
      verifyBtn.addEventListener("click", function(ev) {
        ev.stopPropagation();
        verifyProvenance(result._rawText || text_for_verify, el);
      });
      el.appendChild(verifyBtn);
    }

    // Stash the raw text for verification
    el._lastText = result._rawText || text_for_verify;

    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const left = Math.min(x + 12, vw - 340);
    const top  = y + 24 + 200 > vh ? y - 130 : y + 24;

    el.style.left = Math.max(8, left) + "px";
    el.style.top  = Math.max(8, top) + "px";
  }

  /* -------------------------------------------------------------- */
  /*  Provenance Verification (Layer 2 bridge)                      */
  /* -------------------------------------------------------------- */

  function verifyProvenance(text, floatEl) {
    if (!text) return;
    
    // Strip standard invisible padding (like trailing newlines/spaces) 
    // that the browser selection API might inject during hovering,
    // but without destroying the actual internal ZW payload characters
    text = text.replace(/^[\s\n\r]+|[\s\n\r]+$/g, "");

    // Show loading state
    var existingBtn = floatEl.querySelector(".zwm-float-verify-btn");
    if (existingBtn) existingBtn.textContent = "\u23F3 Verifying...";

    chrome.runtime.sendMessage({ type: "verifyProvenance", text: text }, function(resp) {
      if (chrome.runtime.lastError) {
        if (existingBtn) existingBtn.textContent = "⚠️ Backend unavailable";
        console.warn("ZWM provenance verify runtime error:", chrome.runtime.lastError.message);
        return;
      }

      if (!resp || !resp.ok) {
        if (existingBtn) existingBtn.textContent = "⚠️ Backend unavailable";
        console.warn("ZWM provenance verify backend error:", resp && (resp.error || resp.data));
        return;
      }

      var data = resp.data;
      var resultDiv = floatEl.querySelector(".zwm-verify-result");
      if (!resultDiv) {
        resultDiv = document.createElement("div");
        resultDiv.className = "zwm-verify-result";
        floatEl.appendChild(resultDiv);
      }

      if (data.verified) {
        resultDiv.className = "zwm-verify-result zwm-verify-ok";
        resultDiv.innerHTML =
          '\u2705 <strong>Provenance Verified</strong><br>' +
          'Company: ' + data.company + '<br>' +
          'Block #' + data.block_num + ' &bull; ' + data.timestamp + '<br>' +
          '<span class="zwm-verify-hash">tx: ' + data.tx_hash.substring(0, 16) + '...</span>';
      } else {
        resultDiv.className = "zwm-verify-result zwm-verify-fail";
        resultDiv.innerHTML =
          '\u274C <strong>Not Verified</strong><br>' +
          (data.reason || 'Hash not found on provenance chain.');
      }

      if (existingBtn) existingBtn.textContent = "\uD83D\uDD17 Verify Provenance";
    });
  }

  function onSelectionMouseUp(e) {
    if (floatEl && floatEl.contains(e.target)) return;

    let text = getRawSelectedText();
    if (!text || text.length < 2) {
      text = getHoverRawText(e.target, e.clientX, e.clientY);
    }

    if (!text || text.length < 2) {
      hideFloat();
      return;
    }

    const result = analyzeText(text);
    showFloat(e.clientX, e.clientY, result, text);
  }

  let hoverRaf = 0;
  let lastHoverTarget = null;

  function onSelectionMouseMove(e) {
    if (floatEl && floatEl.contains(e.target)) return;

    const selectedText = getRawSelectedText();
    if (selectedText && selectedText.length >= 2) {
      return;
    }

    if (e.target === lastHoverTarget && hoverRaf) return;
    lastHoverTarget = e.target;

    if (hoverRaf) cancelAnimationFrame(hoverRaf);
    hoverRaf = requestAnimationFrame(() => {
      hoverRaf = 0;
      const raw = getHoverRawText(e.target, e.clientX, e.clientY);
      if (!raw || raw.length < 2) {
        hideFloat();
        return;
      }

      const result = analyzeText(raw);
      if (result.zwCount > 0 || result.tags.length > 0) {
        showFloat(e.clientX, e.clientY, result, raw);
      } else {
        hideFloat();
      }
    });
  }

  function onSelectionKeyUp() {
    const text = getRawSelectedText();
    if (!text) hideFloat();
  }

  let selectionScanActive = false;

  function enableSelectionScan() {
    if (selectionScanActive) return;
    selectionScanActive = true;
    document.addEventListener("mouseup", onSelectionMouseUp, true);
    document.addEventListener("keyup", onSelectionKeyUp, true);
    document.addEventListener("mousemove", onSelectionMouseMove, true);
  }

  function disableSelectionScan() {
    if (!selectionScanActive) return;
    selectionScanActive = false;
    document.removeEventListener("mouseup", onSelectionMouseUp, true);
    document.removeEventListener("keyup", onSelectionKeyUp, true);
    document.removeEventListener("mousemove", onSelectionMouseMove, true);
    hideFloat();
  }

  document.addEventListener("input", () => {
    if (currentMode === "autoDetect") {
      scheduleAutoDetect();
    }
  }, true);

  document.addEventListener("mousedown", function(e) {
    if (floatEl && !floatEl.contains(e.target)) hideFloat();
  }, true);

  /* -------------------------------------------------------------- */
  /*  State management — single mode: "off" | "autoDetect" | "selectionScan" */
  /* -------------------------------------------------------------- */

  function applyMode(mode) {
    currentMode = mode || "off";
    disableAutoDetect();
    disableSelectionScan();

    if (currentMode === "autoDetect")    enableAutoDetect();
    if (currentMode === "selectionScan") enableSelectionScan();
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (!msg || !msg.type) return;
    if (msg.type === "applyMode") {
      applyMode(msg.mode || "off");
      sendResponse({ ok: true, mode: currentMode });
    }
    return true;
  });

  // On page load, read the active mode and apply it
  chrome.storage.local.get({ mode: "off" }, (s) => {
    applyMode(s.mode);
  });
})();
