chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set({ mode: "off" });
});

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
});

chrome.storage.onChanged.addListener(() => {
  chrome.storage.local.get({ mode: "off" }, (s) => {
    const on = s.mode !== "off";
    chrome.action.setBadgeText({ text: on ? "ON" : "" });
    chrome.action.setBadgeBackgroundColor({ color: "#6d28d9" });
  });
});
