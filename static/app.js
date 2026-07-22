const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const backendEl = document.getElementById("backend");
const modeEl = document.getElementById("mode");
const modelEl = document.getElementById("model");
const pullBtn = document.getElementById("pullModel");
const ingestBtn = document.getElementById("ingestRag");
const preloadBtn = document.getElementById("preloadModel");
const trainBtn = document.getElementById("trainUnsloth");
const settingsBtn = document.getElementById("settingsBtn");
const topSettingsBtn = document.getElementById("topSettingsBtn");
const hermesNewSessionBtn = document.getElementById("hermesNewSession");
const settingsModal = document.getElementById("settingsModal");
const settingsForm = document.getElementById("settingsForm");
const settingsTrainBtn = document.getElementById("settingsTrainBtn");
const hermesRefreshStatusBtn = document.getElementById("hermesRefreshStatus");
const finetuneHint = document.getElementById("finetuneHint");
const lanTipEl = document.getElementById("lanTip");
const menuToggle = document.getElementById("menuToggle");
const sidebarEl = document.getElementById("sidebar");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");
const controlsEl = document.getElementById("controls");
const quickEl = document.getElementById("quickPrompts");
const emptyStateEl = document.getElementById("emptyState");
const newChatBtn = document.getElementById("newChatBtn");
const chatListEl = document.getElementById("chatList");
const topbarChatTitleEl = document.getElementById("topbarChatTitle");
const topbarModeEl = document.getElementById("topbarMode");
const ragEl = document.getElementById("useRag");
const webSearchEl = document.getElementById("useWebSearch");
const statusEl = document.getElementById("status");
const setupPanelEl = document.getElementById("setupPanel");
const setupTitleEl = document.getElementById("setupTitle");
const setupTextEl = document.getElementById("setupText");
const setupPrimaryEl = document.getElementById("setupPrimary");
const setupDismissEl = document.getElementById("setupDismiss");
/** @type {"" | "copy" | "preload" | "settings" | "docs"} */
let setupAction = "";
let setupDismissedKey = sessionStorage.getItem("setupDismissed") || "";
const emptyLeadEl = document.querySelector(".empty-lead");

const CHAT_STORE_KEY = "hackgpt.chats.v1";
const CHAT_STORE_LEGACY = "pentestgpt.chats.v1";
const MAX_CHATS = 40;
const MAX_MESSAGES = 40;

/** @type {{role: string, content: string}[]} */
let history = [];
let streaming = false;
/** @type {Record<string, string[]>} */
let quickPrompts = {};
let lastSetupCommand = "";
let backendReady = false;
let hermesSessionId = localStorage.getItem("hermesSessionId") || "";
let resetHermesNext = false;
let autoSwitchAttempted = false;
/** @type {string} */
let currentChatId = "";
/** @type {{id: string, title: string, createdAt: number, updatedAt: number, mode: string, messages: {role: string, content: string}[]}[]} */
let chatStore = [];

function on(el, event, handler) {
  if (el) el.addEventListener(event, handler);
}

function uid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`;
}

function titleFromMessages(messages) {
  const firstUser = (messages || []).find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return "New chat";
  const t = firstUser.content.trim().replace(/\s+/g, " ");
  return t.length > 42 ? `${t.slice(0, 42)}…` : t;
}

function formatChatTime(ts) {
  const d = new Date(ts || Date.now());
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function loadChatStore() {
  try {
    let raw = localStorage.getItem(CHAT_STORE_KEY);
    if (!raw) {
      raw = localStorage.getItem(CHAT_STORE_LEGACY);
      if (raw) {
        localStorage.setItem(CHAT_STORE_KEY, raw);
      }
    }
    if (!raw) {
      chatStore = [];
      currentChatId = "";
      return;
    }
    const data = JSON.parse(raw);
    chatStore = Array.isArray(data.chats) ? data.chats : [];
    currentChatId = data.currentId || (chatStore[0] && chatStore[0].id) || "";
  } catch {
    chatStore = [];
    currentChatId = "";
  }
}

function saveChatStore() {
  try {
    localStorage.setItem(
      CHAT_STORE_KEY,
      JSON.stringify({
        currentId: currentChatId,
        chats: chatStore.slice(0, MAX_CHATS),
      })
    );
  } catch {
    /* quota / private mode */
  }
}

function getCurrentChat() {
  return chatStore.find((c) => c.id === currentChatId) || null;
}

function persistCurrentChat() {
  const chat = getCurrentChat();
  if (!chat) return;
  chat.messages = history.slice(-MAX_MESSAGES);
  chat.updatedAt = Date.now();
  chat.mode = modeEl?.value || chat.mode || "default";
  chat.title = titleFromMessages(chat.messages);
  chatStore = [chat, ...chatStore.filter((c) => c.id !== chat.id)].slice(0, MAX_CHATS);
  saveChatStore();
  renderChatList();
  updateChatTitle();
}

function updateChatTitle() {
  const chat = getCurrentChat();
  const title = chat?.title || "New chat";
  if (topbarChatTitleEl) topbarChatTitleEl.textContent = title;
  document.title = `${title} — HackGPT`;
}

function renderTranscript(messages) {
  chatEl.innerHTML = "";
  for (const msg of messages || []) {
    if (msg.role === "assistant") {
      appendMessage("assistant", renderMarkdown(msg.content || ""), true);
    } else if (msg.role === "user") {
      appendMessage("user", msg.content || "", false);
    }
  }
  syncEmptyState();
  chatEl.scrollTop = chatEl.scrollHeight;
}

function renderChatList() {
  if (!chatListEl) return;
  chatListEl.innerHTML = "";
  const sorted = [...chatStore].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  for (const chat of sorted) {
    const row = document.createElement("div");
    row.className = `chat-item${chat.id === currentChatId ? " active" : ""}`;
    row.setAttribute("role", "listitem");

    const main = document.createElement("button");
    main.type = "button";
    main.className = "chat-item-main";
    main.title = chat.title || "Chat";
    main.innerHTML = `<span class="chat-item-title">${escapeHtml(chat.title || "New chat")}</span>
      <span class="chat-item-meta">${escapeHtml(formatChatTime(chat.updatedAt))}</span>`;
    main.addEventListener("click", () => openChat(chat.id));

    const del = document.createElement("button");
    del.type = "button";
    del.className = "chat-item-delete";
    del.title = "Delete chat";
    del.setAttribute("aria-label", "Delete chat");
    del.textContent = "×";
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteChat(chat.id);
    });

    row.append(main, del);
    chatListEl.appendChild(row);
  }
}

function createChat(activate = true, { clearUi = true } = {}) {
  const chat = {
    id: uid(),
    title: "New chat",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    mode: modeEl?.value || "default",
    messages: [],
  };
  chatStore = [chat, ...chatStore].slice(0, MAX_CHATS);
  if (activate) {
    currentChatId = chat.id;
    if (clearUi) {
      history = [];
      chatEl.innerHTML = "";
      syncEmptyState();
    }
    updateChatTitle();
  }
  saveChatStore();
  renderChatList();
  return chat;
}

function openChat(id) {
  if (streaming) return;
  if (!id || id === currentChatId) {
    closeSidebar();
    return;
  }
  const chat = chatStore.find((c) => c.id === id);
  if (!chat) return;

  // Save current before switching
  persistCurrentChat();

  currentChatId = chat.id;
  history = (chat.messages || []).slice(-MAX_MESSAGES);
  if (chat.mode && modeEl) {
    modeEl.value = chat.mode;
    updateModeLabel();
    renderQuickPrompts();
  }
  renderTranscript(history);
  updateChatTitle();
  saveChatStore();
  renderChatList();
  closeSidebar();
  inputEl?.focus();
}

function deleteChat(id) {
  if (streaming) return;
  const next = chatStore.filter((c) => c.id !== id);
  chatStore = next;
  if (currentChatId === id) {
    if (chatStore.length) {
      currentChatId = chatStore[0].id;
      history = (chatStore[0].messages || []).slice(-MAX_MESSAGES);
      renderTranscript(history);
      if (chatStore[0].mode && modeEl) {
        modeEl.value = chatStore[0].mode;
        updateModeLabel();
        renderQuickPrompts();
      }
    } else {
      createChat(true);
      return;
    }
  }
  saveChatStore();
  renderChatList();
  updateChatTitle();
}

function newChat() {
  if (streaming) return;
  const current = getCurrentChat();
  if (current && (!history || history.length === 0)) {
    // Already on empty chat
    chatEl.innerHTML = "";
    syncEmptyState();
    updateChatTitle();
    closeSidebar();
    inputEl?.focus();
    renderChatList();
    return;
  }
  persistCurrentChat();
  createChat(true);
  closeSidebar();
  inputEl?.focus();
}

function ensureActiveChat() {
  loadChatStore();
  if (!currentChatId || !getCurrentChat()) {
    if (chatStore.length) {
      currentChatId = chatStore[0].id;
    } else {
      createChat(true);
      return;
    }
  }
  const chat = getCurrentChat();
  history = (chat.messages || []).slice(-MAX_MESSAGES);
  if (chat.mode && modeEl) {
    modeEl.value = chat.mode;
  }
  renderTranscript(history);
  updateChatTitle();
  renderChatList();
  updateModeLabel();
}

if (typeof marked !== "undefined" && marked.setOptions) {
  marked.setOptions({ breaks: true, gfm: true });
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdown(text) {
  if (typeof marked !== "undefined" && typeof marked.parse === "function") {
    return marked.parse(text);
  }
  return `<pre class="md-fallback">${escapeHtml(text)}</pre>`;
}

function syncEmptyState() {
  if (!emptyStateEl) return;
  const hasMessages = chatEl && chatEl.children.length > 0;
  emptyStateEl.classList.toggle("hidden", hasMessages);
}

function appendMessage(role, content, isHtml = false) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "user" ? "Y" : "H";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (isHtml) {
    bubble.innerHTML = content;
  } else {
    bubble.textContent = content;
  }

  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role;

  div.append(avatar, label, bubble);
  chatEl.appendChild(div);
  syncEmptyState();
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function resizeInput() {
  if (!inputEl) return;
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, window.innerHeight * 0.28)}px`;
}

function closeSidebar() {
  sidebarEl?.classList.remove("open");
  sidebarBackdrop?.classList.remove("show");
  if (sidebarBackdrop) sidebarBackdrop.hidden = true;
  menuToggle?.setAttribute("aria-expanded", "false");
  document.body.classList.remove("sidebar-open");
}

function openSidebar() {
  sidebarEl?.classList.add("open");
  if (sidebarBackdrop) {
    sidebarBackdrop.hidden = false;
    requestAnimationFrame(() => sidebarBackdrop.classList.add("show"));
  }
  menuToggle?.setAttribute("aria-expanded", "true");
  document.body.classList.add("sidebar-open");
}

function updateModeLabel() {
  if (!topbarModeEl || !modeEl) return;
  const opt = modeEl.selectedOptions[0];
  topbarModeEl.textContent = opt ? opt.textContent : modeEl.value;
  // Cyber modes keep live search on by default
  if (webSearchEl) webSearchEl.checked = true;
}

function showSetupPanel(title, text, options = {}) {
  const {
    command = "",
    action = command ? "copy" : "docs",
    tone = "error",
    key = "",
  } = typeof options === "string"
    ? { command: options, action: options ? "copy" : "docs", tone: "error", key: "" }
    : options;

  // Soft info banners can be dismissed for the session
  if (tone === "info" && key && setupDismissedKey === key) {
    hideSetupPanel();
    return;
  }

  setupTitleEl.textContent = title;
  setupTextEl.textContent = text;
  lastSetupCommand = command;
  setupAction = action;
  setupPanelEl.dataset.tone = tone;
  setupPanelEl.dataset.key = key || "";

  if (action === "preload") setupPrimaryEl.textContent = "Preload model";
  else if (action === "settings") setupPrimaryEl.textContent = "Open Settings";
  else if (action === "copy" && command) setupPrimaryEl.textContent = "Copy command";
  else setupPrimaryEl.textContent = "Open docs";

  if (setupDismissEl) {
    setupDismissEl.classList.toggle("hidden", tone === "error");
  }

  setupPanelEl.classList.remove("hidden");
}

function hideSetupPanel() {
  setupPanelEl.classList.add("hidden");
  lastSetupCommand = "";
  setupAction = "";
}

function openSettings() {
  settingsModal.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  loadSettingsForm();
  refreshFinetuneHint();
  loadPlatformTip();
  refreshHermesStatus();
}

function closeSettings() {
  settingsModal.classList.add("hidden");
  document.body.style.overflow = "";
}

function toggleMenu() {
  if (sidebarEl?.classList.contains("open")) closeSidebar();
  else openSidebar();
}

async function loadPlatformTip() {
  if (!lanTipEl) return;
  try {
    const res = await fetch("/api/platform");
    const p = await res.json();
    const urls = (p.lan_urls || []).map((u) => `<code>${u}</code>`).join(" · ");
    lanTipEl.innerHTML =
      `${p.client_note || ""}` +
      (urls ? `<br/><strong>LAN:</strong> ${urls}` : "") +
      (p.os ? `<br/><strong>Host OS:</strong> ${p.os} · Python ${p.python}` : "");
  } catch {
    lanTipEl.textContent =
      "Phones/tablets: open this app via your host LAN IP on port 8080 (same Wi‑Fi). Backends run on the host.";
  }
}

function renderQuickPrompts() {
  if (!quickEl) return;
  quickEl.innerHTML = "";
  const prompts = (quickPrompts[modeEl.value] || []).slice(0, 4);
  for (const text of prompts) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = text;
    btn.addEventListener("click", () => {
      inputEl.value = text;
      resizeInput();
      sendMessage();
    });
    quickEl.appendChild(btn);
  }
  updateModeLabel();
}

async function loadModes() {
  try {
    const res = await fetch("/api/modes");
    const data = await res.json();
    quickPrompts = data.quick_prompts || {};
    renderQuickPrompts();
  } catch {
    quickEl.innerHTML = "";
  }
}

async function loadBackend() {
  try {
    const res = await fetch("/api/backend");
    const data = await res.json();
    backendEl.value = data.backend;
  } catch {
    backendEl.value = "ollama";
  }
}

async function loadModels() {
  try {
    const res = await fetch("/api/models");
    const data = await res.json();
    modelEl.innerHTML = "";
    const backend = data.backend || backendEl.value;

    if (
      backend === "huggingface" ||
      backend === "unsloth" ||
      backend === "openai_compat" ||
      backend === "hermes"
    ) {
      const opt = document.createElement("option");
      opt.value = data.current;
      opt.textContent = data.current;
      modelEl.appendChild(opt);
      modelEl.value = data.current;
      return;
    }

    const added = new Set();

    for (const name of data.installed || []) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      modelEl.appendChild(opt);
      added.add(name);
    }

    for (const rec of data.recommended || []) {
      if (added.has(rec.pull)) continue;
      const opt = document.createElement("option");
      opt.value = rec.pull;
      opt.textContent = `${rec.name} (not installed)`;
      opt.dataset.notInstalled = "1";
      modelEl.appendChild(opt);
    }

    if (data.current) {
      const match = [...modelEl.options].find(
        (o) => o.value === data.current || o.value.startsWith(data.current)
      );
      if (match) modelEl.value = match.value;
    }
  } catch {
    modelEl.innerHTML = '<option value="">Models unavailable</option>';
  }
}

async function loadSettingsForm() {
  try {
    const res = await fetch("/api/settings");
    const s = await res.json();
    document.getElementById("setOllamaUrl").value = s.ollama_base_url || "";
    document.getElementById("setOllamaModel").value = s.ollama_model || "";
    document.getElementById("setHfModel").value = s.hf_model || "";
    document.getElementById("setHfToken").value = "";
    document.getElementById("hfTokenHint").textContent = s.hf_token_set
      ? "Saved: •••••••• (hidden)"
      : "Not set — required for gated Hugging Face / Unsloth models";
    document.getElementById("setUnslothModel").value = s.unsloth_model || "";
    document.getElementById("setUnslothAdapter").value = s.unsloth_adapter_dir || "";
    document.getElementById("setUnslothSeq").value = s.unsloth_max_seq_length || 2048;
    document.getElementById("setUnsloth4bit").checked = Boolean(s.unsloth_load_in_4bit);
    document.getElementById("setHermesUrl").value = s.hermes_base_url || "";
    document.getElementById("setHermesModel").value = s.hermes_model || "";
    document.getElementById("setHermesKey").value = "";
    document.getElementById("hermesKeyHint").textContent = s.hermes_api_key_set
      ? "Saved: •••••••• (hidden)"
      : "Not set";
    document.getElementById("setHermesSessionKey").value = "";
    const sessionHint = document.getElementById("hermesSessionKeyHint");
    if (sessionHint) {
      sessionHint.textContent = s.hermes_session_key_set
        ? "Saved: •••••••• (hidden)"
        : "Optional — leave blank to keep";
    }
    document.getElementById("setHermesTools").checked = s.hermes_show_tool_progress !== false;
    document.getElementById("setCompatUrl").value = s.openai_compat_base_url || "";
    document.getElementById("setCompatModel").value = s.openai_compat_model || "";
    document.getElementById("setCompatKey").value = "";
    document.getElementById("compatKeyHint").textContent = s.openai_compat_api_key_set
      ? "Saved: •••••••• (hidden)"
      : "Not set";
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Settings load failed:** ${err.message}`), true);
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const payload = {
    ollama_base_url: document.getElementById("setOllamaUrl").value.trim(),
    ollama_model: document.getElementById("setOllamaModel").value.trim(),
    hf_model: document.getElementById("setHfModel").value.trim(),
    hf_token: document.getElementById("setHfToken").value.trim(),
    unsloth_model: document.getElementById("setUnslothModel").value.trim(),
    unsloth_adapter_dir: document.getElementById("setUnslothAdapter").value.trim(),
    unsloth_max_seq_length: Number(document.getElementById("setUnslothSeq").value) || 2048,
    unsloth_load_in_4bit: document.getElementById("setUnsloth4bit").checked,
    hermes_base_url: document.getElementById("setHermesUrl").value.trim(),
    hermes_model: document.getElementById("setHermesModel").value.trim(),
    hermes_api_key: document.getElementById("setHermesKey").value.trim(),
    hermes_session_key: document.getElementById("setHermesSessionKey").value.trim(),
    hermes_show_tool_progress: document.getElementById("setHermesTools").checked,
    openai_compat_base_url: document.getElementById("setCompatUrl").value.trim(),
    openai_compat_model: document.getElementById("setCompatModel").value.trim(),
    openai_compat_api_key: document.getElementById("setCompatKey").value.trim(),
  };
  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    appendMessage("assistant", renderMarkdown("**Settings saved** to `.env` (secrets are masked in the UI)."), true);
    await loadSettingsForm();
    await loadModels();
    await checkHealth();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Save failed:** ${err.message}`), true);
  }
}

async function refreshHermesStatus() {
  const hint = document.getElementById("hermesStatusHint");
  if (!hint) return;
  hint.textContent = "Status: checking…";
  try {
    const res = await fetch("/api/hermes/status");
    const data = await res.json();
    if (!data.reachable) {
      hint.textContent = `Status: offline — ${data.error || "start hermes gateway"}`;
      return;
    }
    const models = (data.models || []).join(", ") || data.model || "hermes-agent";
    const feats = data.capabilities?.features
      ? Object.entries(data.capabilities.features)
          .filter(([, v]) => v)
          .map(([k]) => k)
          .slice(0, 6)
          .join(", ")
      : "chat_completions";
    hint.textContent = `Status: online · models: ${models} · features: ${feats}`;
  } catch (err) {
    hint.textContent = `Status: error — ${err.message}`;
  }
}

function newHermesSession() {
  hermesSessionId = "";
  localStorage.removeItem("hermesSessionId");
  resetHermesNext = true;
  appendMessage(
    "assistant",
    renderMarkdown("**New Hermes session** — next message starts a fresh Hermes Agent transcript (tools/memory scope uses your session key)."),
    true
  );
}

async function refreshFinetuneHint() {
  try {
    const res = await fetch("/api/finetune");
    const job = await res.json();
    if (job.status === "idle") {
      finetuneHint.textContent = "Idle — trains on data/ethical_pentest_dataset.jsonl";
    } else {
      finetuneHint.textContent = `${job.status}: ${job.message || job.engine}`;
    }
    const busy = job.status === "running";
    trainBtn.disabled = busy || streaming;
    settingsTrainBtn.disabled = busy;
  } catch {
    finetuneHint.textContent = "Finetune status unavailable";
  }
}

async function startUnslothTrain() {
  const epochs = Number(document.getElementById("setTrainEpochs")?.value) || 1;
  try {
    const res = await fetch("/api/finetune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ engine: "unsloth", epochs }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    appendMessage(
      "assistant",
      renderMarkdown(
        `**Unsloth training started** (${data.model} → \`${data.output}\`, ${data.epochs} epoch(s)).\n\nGPU recommended. Watch status via Settings or `/api/finetune`.`
      ),
      true
    );
    refreshFinetuneHint();
    closeSettings();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Train failed to start:** ${err.message}`), true);
  }
}

async function switchModel(modelName) {
  if (!modelName) return;
  if (backendEl.value !== "ollama") return;
  await fetch("/api/models/switch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: modelName }),
  });
  checkHealth();
}

async function switchBackend(backend) {
  await fetch("/api/backend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ backend }),
  });
  await loadModels();
  await checkHealth();
}

async function ingestRag() {
  if (streaming) return;
  ingestBtn.disabled = true;
  try {
    const res = await fetch("/api/ingest", { method: "POST" });
    const data = await res.json();
    appendMessage(
      "assistant",
      renderMarkdown(`**RAG re-indexed:** ${data.documents_ingested} documents.`),
      true
    );
    checkHealth();
  } catch (err) {
    appendMessage("assistant", renderMarkdown(`**Re-index failed:** ${err.message}`), true);
  } finally {
    ingestBtn.disabled = false;
  }
}

async function pullModel() {
  const modelName = modelEl.value;
  if (!modelName || streaming) return;

  streaming = true;
  pullBtn.disabled = true;
  sendBtn.disabled = true;

  const body = appendMessage("assistant", "", false);
  body.classList.add("typing");
  let fullText = `Pulling **${modelName}** via Ollama…\n\n`;

  try {
    const res = await fetch("/api/models/pull", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      fullText += decoder.decode(value, { stream: true });
      body.innerHTML = renderMarkdown(fullText);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(fullText + "\n\n**Done.** Refreshing model list…");
    await loadModels();
    await switchModel(modelName);
  } catch (err) {
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(`**Pull failed:** ${err.message}`);
  } finally {
    streaming = false;
    pullBtn.disabled = false;
    sendBtn.disabled = false;
  }
}

async function preloadModel() {
  if (streaming) return;
  if (backendEl.value !== "huggingface" && backendEl.value !== "unsloth") return;

  streaming = true;
  preloadBtn.disabled = true;
  sendBtn.disabled = true;

  const body = appendMessage("assistant", "", false);
  body.classList.add("typing");
  let fullText = `Preloading **${modelEl.value}**…\n\n`;

  try {
    const res = await fetch("/api/models/preload", { method: "POST" });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      fullText += decoder.decode(value, { stream: true });
      body.innerHTML = renderMarkdown(fullText);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(fullText + "\n\n**Model ready.**");
    await checkHealth();
  } catch (err) {
    body.classList.remove("typing");
    body.innerHTML = renderMarkdown(`**Preload failed:** ${err.message}`);
  } finally {
    streaming = false;
    preloadBtn.disabled = false;
    sendBtn.disabled = false;
  }
}

async function ensureWorkingBackend(healthData) {
  if (autoSwitchAttempted) return false;
  if (healthData.backend_ready) return false;
  autoSwitchAttempted = true;
  try {
    const res = await fetch("/api/backends/probe");
    const probe = await res.json();
    const next = probe.recommended;
    if (!next || next === healthData.backend) {
      return false;
    }
    await switchBackend(next);
    appendMessage(
      "assistant",
      renderMarkdown(
        `**Auto-switched AI backend** to \`${next}\` because \`${healthData.backend}\` was offline.\n\nYou can change this anytime in the backend dropdown or Settings.`
      ),
      true
    );
    return true;
  } catch {
    return false;
  }
}

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const rag = data.rag_documents != null ? ` · RAG:${data.rag_documents}` : "";
    const backend = data.backend;
    backendEl.value = backend;

    // Prefer ready remote backends; fall back to HuggingFace/Unsloth (loads on chat)
    const canChat =
      Boolean(data.backend_ready) ||
      data.backend_status === "loads_on_chat";
    backendReady = canChat;
    sendBtn.disabled = streaming || !backendReady;
    preloadBtn.classList.add("hidden");
    trainBtn.classList.add("hidden");
    if (hermesNewSessionBtn) hermesNewSessionBtn.classList.add("hidden");

    if (!canChat) {
      const switched = await ensureWorkingBackend(data);
      if (switched) return;
    }

    if (data.finetune) {
      const ft = data.finetune;
      if (ft.status === "running") {
        finetuneHint.textContent = `running: ${ft.message || ft.model}`;
        trainBtn.disabled = true;
      } else if (ft.status === "completed" || ft.status === "failed") {
        finetuneHint.textContent = `${ft.status}: ${ft.message}`;
        trainBtn.disabled = streaming;
      }
    }

    if (backend === "ollama") {
      modelEl.disabled = false;
      pullBtn.disabled = streaming;
      if (!data.ollama_connected) {
        statusEl.textContent = `Ollama offline${rag}`;
        statusEl.className = "status err";
        showSetupPanel(
          "Start Ollama",
          "No Ollama server is running yet. Start Ollama, then pull a model to enable chat.",
          { command: "ollama pull tinyllama", action: "copy", tone: "error" }
        );
      } else if (!data.ollama_has_models) {
        statusEl.textContent = `Ollama ready · pull a model${rag}`;
        statusEl.className = "status err";
        showSetupPanel(
          "Pull a local model",
          "Ollama is reachable, but no local model is installed yet.",
          { command: "ollama pull tinyllama", action: "copy", tone: "warn" }
        );
      } else {
        statusEl.textContent = `${backend} · ${data.model}${rag}`;
        statusEl.className = "status ok";
        hideSetupPanel();
      }
    } else {
      modelEl.disabled = false;
      pullBtn.disabled = true;
      const statusSuffix = data.backend_status === "loads_on_chat" ? " · loads on first chat" : "";

      if (backend === "openai_compat") {
        if (!data.backend_ready) {
          statusEl.textContent = `LM Studio offline${rag}`;
          statusEl.className = "status err";
          showSetupPanel(
            "LM Studio offline",
            "Start LM Studio’s local server (OpenAI-compatible) on http://localhost:1234/v1, or fix the URL/key in Settings.",
            { action: "settings", tone: "error" }
          );
        } else {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        }
      } else if (backend === "hermes") {
        if (hermesNewSessionBtn) hermesNewSessionBtn.classList.remove("hidden");
        if (!data.backend_ready) {
          statusEl.textContent = `Hermes offline${rag}`;
          statusEl.className = "status err";
          showSetupPanel(
            "Hermes Agent offline",
            "Run hermes gateway with API_SERVER_ENABLED=true. Set the API key in Settings to match API_SERVER_KEY.",
            { command: "hermes gateway", action: "copy", tone: "error" }
          );
        } else {
          const sid = hermesSessionId ? ` · sess:${hermesSessionId.slice(0, 8)}…` : "";
          statusEl.textContent = `${backend} · ${data.model}${sid}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        }
      } else if (backend === "unsloth") {
        trainBtn.classList.remove("hidden");
        preloadBtn.classList.remove("hidden");
        if (data.unsloth_model_loaded) {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        } else {
          statusEl.textContent = `${backend} · ${data.model}${statusSuffix}${rag}`;
          statusEl.className = "status ok";
          // Ready to chat — soft tip only, not an error
          const tip = data.hf_token_set
            ? "Unsloth will load on first chat. You can also Preload now."
            : "Unsloth will load on first chat. Add an HF token in Settings only for gated models.";
          showSetupPanel("Unsloth ready", tip, {
            action: "preload",
            tone: "info",
            key: "unsloth-ready",
          });
        }
      } else if (backend === "huggingface") {
        preloadBtn.classList.remove("hidden");
        if (data.hf_model_loaded) {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        } else {
          statusEl.textContent = `${backend} · ${data.model}${statusSuffix}${rag}`;
          statusEl.className = "status ok";
          // Chat works — model lazy-loads. Soft tip, not a red error.
          const tip = data.hf_token_set
            ? "Model loads on first message. Preload now if you want it ready ahead of time."
            : "Model loads on first message. Optional: add HF token in Settings for gated models.";
          showSetupPanel("Hugging Face ready", tip, {
            action: "preload",
            tone: "info",
            key: "hf-ready",
          });
        }
      } else {
        statusEl.textContent = `${backend} · ${data.model}${rag}`;
        statusEl.className = data.backend_ready ? "status ok" : "status err";
        if (!data.backend_ready) {
          showSetupPanel(
            "Backend not ready",
            "Check Settings and README for backend setup if chat is not responding.",
            { action: "settings", tone: "error" }
          );
        } else {
          hideSetupPanel();
        }
      }
    }
  } catch {
    backendReady = false;
    sendBtn.disabled = true;
    statusEl.textContent = "Offline";
    statusEl.className = "status err";
    showSetupPanel(
      "Server offline",
      "Start the backend with .\\scripts\\start.ps1 (Windows) or bash scripts/start.sh (Linux/macOS).",
      { command: ".\\scripts\\start.ps1", action: "copy", tone: "error" }
    );
  }
}

async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message || streaming) return;
  if (!backendReady) {
    appendMessage(
      "assistant",
      renderMarkdown("**Backend not ready.** Check the status bar and connect a local model backend first."),
      true
    );
    return;
  }

  streaming = true;
  sendBtn.disabled = true;
  inputEl.value = "";
  resizeInput();

  appendMessage("user", message);

  const assistantBody = appendMessage("assistant", "", false);
  assistantBody.classList.add("typing");
  let fullText = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history,
        mode: modeEl.value,
        use_rag: ragEl.checked,
        use_web_search: webSearchEl ? webSearchEl.checked : modeEl.value === "research",
        hermes_session_id: hermesSessionId || null,
        reset_hermes_session: resetHermesNext,
      }),
    });
    resetHermesNext = false;

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const headerSid = res.headers.get("X-Hermes-Session-Id");
    if (headerSid) {
      hermesSessionId = headerSid;
      localStorage.setItem("hermesSessionId", hermesSessionId);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let carry = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      carry += decoder.decode(value, { stream: true });
      // Hermes session marker may arrive split across chunks
      carry = carry.replace(/\[\[hermes_session:([^\]]+)\]\]/g, (_, sid) => {
        hermesSessionId = sid;
        localStorage.setItem("hermesSessionId", hermesSessionId);
        return "";
      });
      // Keep a short tail in case marker is split
      if (carry.includes("[[hermes_session:") && !carry.includes("]]")) {
        continue;
      }
      fullText += carry;
      carry = "";
      assistantBody.innerHTML = renderMarkdown(fullText);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    if (carry) {
      carry = carry.replace(/\[\[hermes_session:([^\]]+)\]\]/g, (_, sid) => {
        hermesSessionId = sid;
        localStorage.setItem("hermesSessionId", hermesSessionId);
        return "";
      });
      fullText += carry;
      assistantBody.innerHTML = renderMarkdown(fullText);
    }

    assistantBody.classList.remove("typing");
    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: fullText });
    if (history.length > MAX_MESSAGES) history = history.slice(-MAX_MESSAGES);
    if (!getCurrentChat()) createChat(true, { clearUi: false });
    persistCurrentChat();
    await checkHealth();
  } catch (err) {
    assistantBody.classList.remove("typing");
    assistantBody.innerHTML = renderMarkdown(`**Error:** ${err.message}`);
  } finally {
    streaming = false;
    sendBtn.disabled = !backendReady;
    inputEl.focus();
  }
}

sendBtn.addEventListener("click", sendMessage);
on(pullBtn, "click", pullModel);
on(preloadBtn, "click", preloadModel);
on(trainBtn, "click", () => openSettings());
on(ingestBtn, "click", ingestRag);
on(settingsBtn, "click", openSettings);
on(topSettingsBtn, "click", openSettings);
on(hermesNewSessionBtn, "click", newHermesSession);
on(hermesRefreshStatusBtn, "click", refreshHermesStatus);
on(menuToggle, "click", toggleMenu);
on(sidebarBackdrop, "click", closeSidebar);
on(newChatBtn, "click", newChat);
on(settingsForm, "submit", saveSettings);
on(settingsTrainBtn, "click", startUnslothTrain);
if (settingsModal) {
  settingsModal.querySelectorAll("[data-close-settings]").forEach((el) => {
    el.addEventListener("click", closeSettings);
  });
}
on(backendEl, "change", () => {
  switchBackend(backendEl.value);
  closeSidebar();
});
on(modeEl, "change", () => {
  renderQuickPrompts();
  const chat = getCurrentChat();
  if (chat) {
    chat.mode = modeEl.value;
    persistCurrentChat();
  }
  closeSidebar();
});
on(setupPrimaryEl, "click", async () => {
  if (setupAction === "preload") {
    hideSetupPanel();
    await preloadModel();
    return;
  }
  if (setupAction === "settings") {
    openSettings();
    return;
  }
  if (setupAction === "copy" && lastSetupCommand) {
    try {
      await navigator.clipboard.writeText(lastSetupCommand);
      appendMessage("assistant", renderMarkdown(`Copied command: \`${lastSetupCommand}\``), true);
    } catch {
      appendMessage("assistant", renderMarkdown(`Run this command:\n\n\`${lastSetupCommand}\``), true);
    }
    return;
  }
  appendMessage(
    "assistant",
    renderMarkdown("See `README.md` and `docs/cursor-local-models.md` for backend setup steps."),
    true
  );
});
on(setupDismissEl, "click", () => {
  const key = setupPanelEl?.dataset?.key || "";
  if (key) {
    setupDismissedKey = key;
    sessionStorage.setItem("setupDismissed", key);
  }
  hideSetupPanel();
});

on(modelEl, "change", () => {
  if (backendEl.value !== "ollama") return;
  const opt = modelEl.selectedOptions[0];
  if (opt?.dataset.notInstalled) return;
  switchModel(modelEl.value);
});

on(inputEl, "keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
on(inputEl, "input", resizeInput);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (settingsModal && !settingsModal.classList.contains("hidden")) closeSettings();
    else closeSidebar();
  }
});

loadBackend();
loadModes();
loadModels();
ensureActiveChat();
checkHealth().then(showWelcome);
setInterval(checkHealth, 15000);
resizeInput();

async function showWelcome() {
  let ragCount = "24";
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.rag_documents != null) ragCount = String(data.rag_documents);
  } catch {
    /* use default */
  }

  if (emptyLeadEl) {
    emptyLeadEl.textContent =
      "Authorized pentesting, CTFs, and blue-team workflows — local and private.";
  }
  const leadMeta = document.getElementById("emptyMeta");
  if (leadMeta) leadMeta.textContent = `${ragCount} RAG docs ready`;
  // Don't overwrite a restored conversation
  syncEmptyState();
  renderChatList();
  updateChatTitle();
}
