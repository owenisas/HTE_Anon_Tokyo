const segBtns  = document.querySelectorAll(".seg-btn");
const modeIcon = document.getElementById("modeIcon");
const modeDesc = document.getElementById("modeDesc");
const statusEl = document.getElementById("status");

function canMessageTab(url) {
  if (!url) return false;
  const blocked = ["chrome://", "chrome-extension://", "edge://", "about:"];
  return !blocked.some(prefix => url.startsWith(prefix));
}

const MODE_INFO = {
  off: {
    icon: "",
    desc: "Extension is idle. Pick a mode above.",
    status: "Off",
  },
  autoDetect: {
    icon: "\uD83D\uDD0D",
    desc: "Highlights text that contains hidden zero-width characters directly on the page. Red = confirmed watermark, yellow = suspicious, purple = hidden chars.",
    status: "Auto-Detect active",
  },
  selectionScan: {
    icon: "\u2712\uFE0F",
    desc: "Select any text on the page \u2014 a floating badge appears showing whether it contains AI watermarks or hidden characters.",
    status: "Selection Scan active",
  },
};

function updateUI(mode) {
  segBtns.forEach(btn => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });

  const info = MODE_INFO[mode] || MODE_INFO.off;
  modeIcon.textContent = info.icon;
  modeDesc.textContent = info.desc;

  if (mode === "off") {
    statusEl.className = "status off";
    statusEl.textContent = info.status;
  } else {
    statusEl.className = "status on";
    statusEl.textContent = info.status;
  }
}

// Load initial state
chrome.runtime.sendMessage({ type: "getMode" }, (mode) => {
  if (mode) updateUI(mode);
});

// Click handler — switch mode, reload active tab
segBtns.forEach(btn => {
  btn.addEventListener("click", async () => {
    const mode = btn.dataset.mode;

    chrome.runtime.sendMessage({ type: "setMode", mode }, (saved) => {
      if (saved) updateUI(saved);
    });

    // Apply mode in active tab without reloading the page
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.id && canMessageTab(tab.url)) {
      chrome.tabs.sendMessage(tab.id, { type: "applyMode", mode }, () => {
        const err = chrome.runtime.lastError;
        if (err) {
          return;
        }
      });
    }
  });
});
