// ── DOM references ──────────────────────────────────────────────
const statusEl = document.getElementById("connection-status");
const promptInput = document.getElementById("prompt-input");
const promptBtn = document.getElementById("prompt-btn");

const statObjects = document.querySelector("#stat-objects .stat-value");
const statPeople = document.querySelector("#stat-people .stat-value");
const statAlerts = document.querySelector("#stat-alerts .stat-value");

const alertsContainer = document.getElementById("alerts-container");
const alertsList = document.getElementById("alerts-list");
const countsContainer = document.getElementById("counts-container");
const countsList = document.getElementById("counts-list");
const historyList = document.getElementById("history-list");

const MAX_HISTORY = 40;

// ── WebSocket connection ────────────────────────────────────────
let ws = null;
let reconnectTimer = null;

function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.addEventListener("open", () => {
    statusEl.textContent = "Connected";
    statusEl.className = "status connected";
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  });

  ws.addEventListener("close", () => {
    statusEl.textContent = "Disconnected";
    statusEl.className = "status disconnected";
    scheduleReconnect();
  });

  ws.addEventListener("error", () => {
    ws.close();
  });

  ws.addEventListener("message", (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleMessage(msg);
    } catch {
      /* ignore malformed */
    }
  });
}

function scheduleReconnect() {
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 2000);
  }
}

// ── Message handling ────────────────────────────────────────────
function handleMessage(msg) {
  if (msg.type === "detection_result") {
    renderResult(msg.payload);
  } else if (msg.type === "status") {
    if (msg.payload.prompt !== undefined) {
      promptInput.value = msg.payload.prompt;
    }
  }
}

// ── Rendering ───────────────────────────────────────────────────
function renderResult(r) {
  const totalObjects = r.detections ? r.detections.length : 0;
  statObjects.textContent = totalObjects;
  statPeople.textContent = r.total_people || 0;
  statAlerts.textContent = r.alerts ? r.alerts.length : 0;

  renderAlerts(r.alerts || []);
  renderCounts(r.object_counts || {});
  addHistoryEntry(r);
}

function renderAlerts(alerts) {
  if (alerts.length === 0) {
    alertsContainer.hidden = true;
    return;
  }
  alertsContainer.hidden = false;
  alertsList.innerHTML = alerts
    .map(
      (a) => `<div class="card alert-card">
        <div class="card-title">${esc(a.label)} &mdash; ${(a.confidence * 100).toFixed(0)}%</div>
        ${a.reason ? `<div class="card-detail">${esc(a.reason)}</div>` : ""}
      </div>`
    )
    .join("");
}

function renderCounts(counts) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    countsContainer.hidden = true;
    return;
  }
  countsContainer.hidden = false;
  countsList.innerHTML = entries
    .map(
      ([label, count]) => `<div class="card count-card">
        <span>${esc(label)}</span>
        <span class="count-num">${count}</span>
      </div>`
    )
    .join("");
}

function addHistoryEntry(r) {
  const ts = r.timestamp
    ? new Date(r.timestamp).toLocaleTimeString()
    : new Date().toLocaleTimeString();

  const counts = r.object_counts || {};
  const summary = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([label, n]) => `${n} ${label}`)
    .join(", ");

  const hasAlerts = r.alerts && r.alerts.length > 0;

  const entry = document.createElement("div");
  entry.className = "history-entry" + (hasAlerts ? " history-alert" : "");
  entry.innerHTML = `<span class="history-time">${ts}</span>${esc(summary || "No detections")}`;

  historyList.prepend(entry);
  while (historyList.children.length > MAX_HISTORY) {
    historyList.removeChild(historyList.lastChild);
  }
}

// ── Prompt submission ───────────────────────────────────────────
function sendPrompt() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(
    JSON.stringify({
      type: "set_prompt",
      payload: { prompt: promptInput.value },
    })
  );
}

promptBtn.addEventListener("click", sendPrompt);
promptInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendPrompt();
  }
});

// ── Helpers ─────────────────────────────────────────────────────
function esc(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

// ── Init ────────────────────────────────────────────────────────
connect();
