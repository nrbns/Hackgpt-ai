const chatEl = document.getElementById("chat");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const backendEl = document.getElementById("backend");
const modeEl = document.getElementById("mode");
const modelEl = document.getElementById("model");
const pullBtn = document.getElementById("pullModel");
const ingestBtn = document.getElementById("ingestRag");
const quickEl = document.getElementById("quickPrompts");
const ragEl = document.getElementById("useRag");
const statusEl = document.getElementById("status");
const setupPanelEl = document.getElementById("setupPanel");
const setupTitleEl = document.getElementById("setupTitle");
const setupTextEl = document.getElementById("setupText");
const setupPrimaryEl = document.getElementById("setupPrimary");

/** @type {{role: string, content: string}[]} */
let history = [];
let streaming = false;
/** @type {Record<string, string[]>} */
let quickPrompts = {};
let lastSetupCommand = "";

marked.setOptions({ breaks: true, gfm: true });

function renderMarkdown(text) {
  return marked.parse(text);
}

function appendMessage(role, content, isHtml = false) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  const label = document.createElement("div");
  label.className = "role";
  label.textContent = role;
  const body = document.createElement("div");
  if (isHtml) {
    body.innerHTML = content;
  } else {
    body.textContent = content;
  }
  div.append(label, body);
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return body;
}

function showSetupPanel(title, text, command = "") {
  setupTitleEl.textContent = title;
  setupTextEl.textContent = text;
  lastSetupCommand = command;
  setupPrimaryEl.textContent = command ? "Copy command" : "Open docs";
  setupPanelEl.classList.remove("hidden");
}

function hideSetupPanel() {
  setupPanelEl.classList.add("hidden");
  lastSetupCommand = "";
}

function renderQuickPrompts() {
  quickEl.innerHTML = "";
  const prompts = quickPrompts[modeEl.value] || [];
  for (const text of prompts) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = text;
    btn.addEventListener("click", () => {
      inputEl.value = text;
      sendMessage();
    });
    quickEl.appendChild(btn);
  }
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

    if (backend === "huggingface") {
      const opt = document.createElement("option");
      opt.value = data.current;
      opt.textContent = data.current;
      modelEl.appendChild(opt);
      modelEl.value = data.current;
      return;
    }

    if (backend === "openai_compat") {
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

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const rag = data.rag_documents != null ? ` · RAG:${data.rag_documents}` : "";
    const backend = data.backend;
    backendEl.value = backend;

    if (backend === "ollama") {
      modelEl.disabled = false;
      pullBtn.disabled = streaming;
      if (!data.ollama_connected) {
        statusEl.textContent = `Ollama offline${rag}`;
        statusEl.className = "status err";
        showSetupPanel(
          "Start Ollama",
          "The UI is ready, but no Ollama server is running yet. Start Ollama and pull a model to enable chat.",
          "ollama pull mistral"
        );
      } else if (!data.ollama_has_models) {
        statusEl.textContent = `Ollama ready · pull a model${rag}`;
        statusEl.className = "status err";
        showSetupPanel(
          "Pull a local model",
          "Ollama is reachable, but no local model is installed yet.",
          "ollama pull mistral"
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
            "Start the LM Studio local server in OpenAI-compatible mode on http://localhost:1234/v1, then refresh.",
            "See docs/cursor-local-models.md"
          );
        } else {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        }
      } else if (backend === "huggingface") {
        if (data.hf_model_loaded) {
          statusEl.textContent = `${backend} · ${data.model}${rag}`;
          statusEl.className = "status ok";
          hideSetupPanel();
        } else {
          statusEl.textContent = `${backend} · ${data.model}${statusSuffix}${rag}`;
          statusEl.className = "status ok";
          showSetupPanel(
            "Hugging Face model not loaded yet",
            "The first chat request downloads and loads the model. For faster replies later, install Ollama or LM Studio.",
          );
        }
      } else {
        statusEl.textContent = `${backend} · ${data.model}${rag}`;
        statusEl.className = data.backend_ready ? "status ok" : "status err";
        if (!data.backend_ready) {
          showSetupPanel(
            "Local backend active",
            "Check README.md for backend setup if chat is not responding."
          );
        } else {
          hideSetupPanel();
        }
      }
    }
  } catch {
    statusEl.textContent = "Offline";
    statusEl.className = "status err";
    showSetupPanel(
      "Server offline",
      "The frontend could not reach the PentestGPT backend. Start the app with .\\scripts\\start.ps1."
    );
  }
}

async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message || streaming) return;

  streaming = true;
  sendBtn.disabled = true;
  inputEl.value = "";

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
      }),
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      fullText += chunk;
      assistantBody.innerHTML = renderMarkdown(fullText);
      chatEl.scrollTop = chatEl.scrollHeight;
    }

    assistantBody.classList.remove("typing");
    history.push({ role: "user", content: message });
    history.push({ role: "assistant", content: fullText });
    if (history.length > 40) history = history.slice(-40);
  } catch (err) {
    assistantBody.classList.remove("typing");
    assistantBody.innerHTML = renderMarkdown(`**Error:** ${err.message}`);
  } finally {
    streaming = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

sendBtn.addEventListener("click", sendMessage);
pullBtn.addEventListener("click", pullModel);
ingestBtn.addEventListener("click", ingestRag);
backendEl.addEventListener("change", () => switchBackend(backendEl.value));
modeEl.addEventListener("change", renderQuickPrompts);
setupPrimaryEl.addEventListener("click", async () => {
  if (lastSetupCommand) {
    try {
      await navigator.clipboard.writeText(lastSetupCommand);
      appendMessage("assistant", renderMarkdown(`Copied command: \`${lastSetupCommand}\``), true);
    } catch {
      appendMessage("assistant", renderMarkdown(`Run this command:\n\n\`${lastSetupCommand}\``), true);
    }
  } else {
    appendMessage(
      "assistant",
      renderMarkdown("See `README.md` and `docs/cursor-local-models.md` for backend setup steps."),
      true
    );
  }
});

modelEl.addEventListener("change", () => {
  if (backendEl.value !== "ollama") return;
  const opt = modelEl.selectedOptions[0];
  if (opt?.dataset.notInstalled) return;
  switchModel(modelEl.value);
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

loadBackend();
loadModes();
loadModels();
checkHealth().then(showWelcome);
setInterval(checkHealth, 30000);

async function showWelcome() {
  let ragCount = "24";
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    if (data.rag_documents != null) ragCount = String(data.rag_documents);
  } catch {
    /* use default */
  }

  appendMessage(
    "assistant",
    renderMarkdown(
      `## Welcome to PentestGPT

**${ragCount} RAG docs** · **6 modes** · real-time streaming

Click a **quick prompt** above, or ask anything about pentest, blue team, malware analysis, and labs.

Use the **backend selector** to switch between Ollama, LM Studio, and Hugging Face.

> Authorized & defensive security only.`
    ),
    true
  );
}
