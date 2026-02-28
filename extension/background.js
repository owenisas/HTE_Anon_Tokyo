chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set({ mode: "off" });
});

const REGISTRY_URL = "http://127.0.0.1:5050";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "getMode") {
    chrome.storage.local.get({ mode: "off" }, (s) => sendResponse(s.mode));
    return true;
  }

  if (msg.type === "setMode") {
    const mode = msg.mode || "off";
    chrome.storage.local.set({ mode }, () => sendResponse(mode));
    return true;
  }

  if (msg.type === "verifyProvenance") {
    const text = (msg.text || "").trim();
    if (!text) {
      sendResponse({ ok: false, error: "No text provided" });
      return false;
    }

    fetch(REGISTRY_URL + "/api/registry/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    })
      .then(async (r) => {
        let data;
        try {
          data = await r.json();
        } catch {
          data = { error: "Invalid backend response" };
        }
        if (!r.ok) {
          sendResponse({ ok: false, status: r.status, data });
          return;
        }
        sendResponse({ ok: true, data });
      })
      .catch((error) => {
        sendResponse({ ok: false, error: String(error) });
      });

    return true;
  }
});

chrome.storage.onChanged.addListener(() => {
  chrome.storage.local.get({ mode: "off" }, (s) => {
    const on = s.mode !== "off";
    chrome.action.setBadgeText({ text: on ? "ON" : "" });
    chrome.action.setBadgeBackgroundColor({ color: "#6d28d9" });
  });
});
