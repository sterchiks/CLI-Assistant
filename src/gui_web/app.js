/* ============================================================
   CLI Assistant — UI logic.
   Темы / i18n / модели / настройки / чат с pywebview-мостом.
   ============================================================ */

const $  = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

// ─── State ────────────────────────────────────────────────────────────────
const state = {
  apiReady: false,
  chats: [],
  activeChatId: null,
  currentMsg: null,         // { id, el, bubble, toolBoxes }
  yolo: false,
  provider: "",
  model: "",
  language: "ru",
  themeKey: "claude_dark",
  animSpeed: "normal",
  showTools: true,
  showTimestamps: true,
  // catalogs
  themes: {},
  i18n: { ru: {}, en: {} },
  models: { providers: {}, user_models: [], current: "", current_provider: "" },
  // profiles
  profiles: {},
  activeProfile: "",
};

// pywebview готов?
function whenApiReady() {
  return new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api);
    window.addEventListener("pywebviewready", () => resolve(window.pywebview.api), { once: true });
  });
}
const api = () => window.pywebview && window.pywebview.api;

// ─── i18n ─────────────────────────────────────────────────────────────────
function t(key, vars) {
  const dict = state.i18n[state.language] || state.i18n.en || {};
  let s = dict[key];
  if (s === undefined) s = (state.i18n.ru || {})[key] ?? key;
  if (vars) for (const k in vars) s = s.replaceAll("{" + k + "}", String(vars[k]));
  return s;
}
function applyI18n(root = document) {
  $$("[data-i18n]", root).forEach(el => { el.textContent = t(el.dataset.i18n); });
  $$("[data-i18n-placeholder]", root).forEach(el => {
    el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder));
  });
  $$("[data-i18n-tooltip]", root).forEach(el => {
    el.setAttribute("title", t(el.dataset.i18nTooltip));
  });
  // welcome-suggest: тексты переводятся через data-i18n; обновим data-q.
  $$(".suggest-btn[data-q-key]").forEach(btn => {
    const q = t(btn.dataset.qKey);
    if (q && q !== btn.dataset.qKey) btn.dataset.q = q;
  });
  document.documentElement.lang = state.language;
}

// ─── Themes ───────────────────────────────────────────────────────────────
function applyTheme(key) {
  const theme = state.themes[key];
  if (!theme) return;
  const root = document.documentElement;
  root.dataset.theme = key;
  for (const [k, v] of Object.entries(theme.vars || {})) {
    root.style.setProperty(k, v);
  }
  state.themeKey = key;
}
function renderThemeGrid() {
  const grid = $("#theme-grid");
  if (!grid) return;
  grid.innerHTML = "";
  for (const [key, theme] of Object.entries(state.themes)) {
    const card = document.createElement("div");
    card.className = "theme-card" + (state.themeKey === key ? " active" : "");
    card.dataset.themeKey = key;
    const v = theme.vars || {};
    card.innerHTML = `
      <div class="preview" style="
        --p-sidebar:${v["--sidebar"]}; --p-bg:${v["--bg"]}; --p-accent:${v["--accent"]};
      ">
        <div class="p-side"></div>
        <div class="p-main"><div class="p-bubble"></div></div>
      </div>
      <div class="name"><span class="ico">${theme.icon || "🎨"}</span><span>${escapeHtml(theme.name)}</span></div>
    `;
    card.addEventListener("click", () => {
      applyTheme(key);
      $$(".theme-card").forEach(c => c.classList.toggle("active", c === card));
    });
    grid.appendChild(card);
  }
}

// ─── Toast ───────────────────────────────────────────────────────────────
let _toastTimer = null;
function toast(text) {
  const el = $("#toast");
  el.textContent = text;
  el.classList.remove("hide");
  // re-trigger animation
  el.style.animation = "none"; void el.offsetWidth; el.style.animation = "";
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add("hide"), 1800);
}

// ─── Boot ────────────────────────────────────────────────────────────────
async function boot() {
  // Глобальный объект для push-событий из Python.
  window.cli = { on: handlePushEvent };

  await whenApiReady();
  state.apiReady = true;

  // Загружаем темы и i18n из бэкенда (это файлы gui_web/themes.json и i18n.json).
  try { state.themes = await api().get_themes() || {}; } catch (_) {}
  try { state.i18n   = await api().get_i18n() || state.i18n; } catch (_) {}

  // Загружаем настройки.
  let s = {};
  try { s = await api().get_settings() || {}; } catch (_) {}
  state.yolo     = !!s.yolo;
  state.provider = s.provider || "";
  state.model    = s.model || "";
  state.language = s.language || "ru";
  state.themeKey = s.theme || "claude_dark";

  // Полная конфигурация — для скорости анимаций и пр.
  try {
    const full = await api().get_settings_full();
    if (full && full.ui) {
      state.animSpeed     = full.ui.animation_speed || "normal";
      state.showTools     = !!full.ui.show_tool_calls;
      state.showTimestamps= !!full.ui.show_timestamps;
    }
  } catch (_) {}

  // Применяем тему / язык / анимации
  applyTheme(state.themeKey);
  applyI18n();
  document.documentElement.dataset.anim = state.animSpeed;

  // Бейдж провайдера
  $("#provider-badge").textContent =
    `${prettyProvider(state.provider)}${state.model ? " · " + state.model : ""}`;

  // YOLO mode
  applyModeUI(state.yolo);

  // Модели
  await refreshModels();

  // Чаты
  await refreshChats();

  bindUI();
}

function prettyProvider(p) {
  if (!p) return "—";
  return ({
    "anthropic":         "Claude",
    "gemini":            "Gemini",
    "openai_compatible": "OpenAI",
  })[p] || p;
}

// ─── UI bindings ─────────────────────────────────────────────────────────
function bindUI() {
  // Sidebar collapse
  $("#toggle-sidebar").addEventListener("click", () => {
    $("#app").classList.add("sidebar-collapsed");
    $("#show-sidebar").classList.remove("hide");
  });
  $("#show-sidebar").addEventListener("click", () => {
    $("#app").classList.remove("sidebar-collapsed");
    $("#show-sidebar").classList.add("hide");
  });

  // New chat
  $("#new-chat").addEventListener("click", newChat);

  // Search
  $("#search-input").addEventListener("input", (e) => filterChats(e.target.value));

  // Composer
  const ta = $("#input");
  ta.addEventListener("input", () => autoResize(ta));
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  $("#send-btn").addEventListener("click", sendMessage);

  // Welcome suggestions
  $$(".suggest-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      ta.value = btn.dataset.q || btn.textContent.trim();
      autoResize(ta); ta.focus();
    });
  });

  // Mode toggle
  $("#mode-btn").addEventListener("click", async () => {
    try {
      const newYolo = await api().toggle_yolo();
      state.yolo = !!newYolo;
      applyModeUI(state.yolo);
      toast(state.yolo ? t("mode.auto_on") : t("mode.safe_on"));
    } catch (_) {}
  });

  // Model popover
  $("#model-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    toggleModelPopover();
  });
  $("#model-open-settings").addEventListener("click", () => {
    closeModelPopover(); openSettings("ai");
  });
  document.addEventListener("click", (e) => {
    const pop = $("#model-popover");
    if (!pop.classList.contains("hide") && !pop.contains(e.target) && e.target.id !== "model-btn") {
      closeModelPopover();
    }
  });

  // Confirm dialog
  $("#confirm-yes").addEventListener("click", () => resolveConfirm(true));
  $("#confirm-no").addEventListener("click",  () => resolveConfirm(false));

  // Sudo dialog
  $("#sudo-ok").addEventListener("click", submitSudo);
  $("#sudo-cancel").addEventListener("click", () => submitSudo(true));
  $("#sudo-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitSudo();
    else if (e.key === "Escape") submitSudo(true);
  });

  // Settings open/close
  $("#open-settings").addEventListener("click", () => openSettings("ai"));
  $("#settings-close").addEventListener("click", closeSettings);
  $("#settings-cancel").addEventListener("click", closeSettings);
  $("#settings-save").addEventListener("click", saveSettings);
  $("#settings-test").addEventListener("click", testProvider);
  $("#toggle-key").addEventListener("click", () => {
    const inp = $("#set-api-key");
    inp.type = inp.type === "password" ? "text" : "password";
  });
  $("#set-provider").addEventListener("change", () => onProviderChanged());
  $$(".settings-tabs .tab").forEach(tab => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });
  $("#prof-add-btn").addEventListener("click", addProfileFromForm);

  // ESC закрывает диалоги
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (!$("#settings-overlay").classList.contains("hide")) closeSettings();
      else if (!$("#model-popover").classList.contains("hide")) closeModelPopover();
    }
  });
}

function autoResize(ta) {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 220) + "px";
}

// ─── Mode (Safe/Auto) ────────────────────────────────────────────────────
function applyModeUI(isYolo) {
  const btn = $("#mode-btn");
  btn.classList.toggle("safe", !isYolo);
  btn.classList.toggle("auto", isYolo);
  $(".mode-label", btn).textContent = isYolo ? t("mode.auto") : t("mode.safe");
  btn.title = isYolo ? t("mode.auto_tooltip") : t("mode.safe_tooltip");
}

// ─── Models popover ──────────────────────────────────────────────────────
async function refreshModels() {
  try { state.models = await api().get_models() || state.models; } catch (_) {}
  $("#model-name").textContent = state.models.current || "—";
  renderModelList();
}

function renderModelList() {
  const list = $("#model-list");
  list.innerHTML = "";

  const all = collectModelsForPopover();
  if (!all.length) {
    const empty = document.createElement("div");
    empty.className = "popover-empty";
    empty.textContent = t("model.no_models");
    list.appendChild(empty);
    return;
  }
  for (const item of all) {
    const row = document.createElement("div");
    row.className = "popover-item" + (item.value === state.models.current ? " active" : "");
    row.innerHTML = `
      <span>${escapeHtml(item.value)}</span>
      <span class="group">${escapeHtml(item.group)}</span>
      <span class="check">✓</span>
    `;
    row.addEventListener("click", () => selectModel(item.value));
    list.appendChild(row);
  }
}

function collectModelsForPopover() {
  // Сначала пользовательские — те что он реально вводил.
  const seen = new Set();
  const out = [];
  for (const m of (state.models.user_models || [])) {
    if (!m || seen.has(m)) continue;
    seen.add(m);
    out.push({ value: m, group: t("settings.tab.profiles") });
  }
  // Затем встроенные модели текущего провайдера.
  const cur = state.models.current_provider;
  for (const [prov, list] of Object.entries(state.models.providers || {})) {
    if (cur && prov !== cur) continue;
    for (const m of list) {
      if (!m || seen.has(m)) continue;
      seen.add(m);
      out.push({ value: m, group: prettyProvider(prov) });
    }
  }
  return out;
}

function toggleModelPopover() {
  const pop = $("#model-popover");
  const btn = $("#model-btn");
  const willOpen = pop.classList.contains("hide");
  pop.classList.toggle("hide");
  btn.classList.toggle("open", willOpen);
}
function closeModelPopover() {
  $("#model-popover").classList.add("hide");
  $("#model-btn").classList.remove("open");
}

async function selectModel(model) {
  try {
    const ok = await api().set_model(model);
    if (ok) {
      state.models.current = model;
      $("#model-name").textContent = model;
      $("#provider-badge").textContent =
        `${prettyProvider(state.provider)} · ${model}`;
      renderModelList();
      toast(t("model.changed", { model }));
    }
  } catch (_) {}
  closeModelPopover();
}

// ─── Chats ────────────────────────────────────────────────────────────────
async function refreshChats() {
  try { state.chats = await api().list_chats() || []; } catch (_) {}
  renderChats();
}

function renderChats(filter = "") {
  const list = $("#chats-list");
  list.innerHTML = "";
  const f = (filter || "").toLowerCase();
  const items = state.chats.filter(c => !f || (c.title || "").toLowerCase().includes(f));
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "popover-empty";
    empty.style.padding = "12px";
    empty.textContent = t("sidebar.no_chats");
    list.appendChild(empty);
    return;
  }
  for (const c of items) {
    const row = document.createElement("div");
    row.className = "chat-item" + (state.activeChatId === c.id ? " active" : "");
    row.innerHTML = `
      <span class="chat-title-text">${escapeHtml(c.title || "Новый чат")}</span>
      <button class="del-btn" title="${t("sidebar.delete_chat")}" aria-label="delete">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
      </button>`;
    row.addEventListener("click", () => openChat(c.id));
    $(".del-btn", row).addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(t("sidebar.confirm_delete", { title: c.title || "" }))) return;
      try { await api().delete_chat(c.id); } catch (_) {}
      if (state.activeChatId === c.id) {
        state.activeChatId = null;
        $("#chat-title").textContent = t("topbar.new_chat");
        $("#messages").innerHTML = '<div id="welcome" class="welcome"></div>';
        renderWelcome();
      }
      toast(t("sidebar.deleted"));
      await refreshChats();
    });
    list.appendChild(row);
  }
}
function filterChats(q) { renderChats(q); }

async function newChat() {
  try {
    const c = await api().create_chat();
    state.activeChatId = c.id;
    $("#chat-title").textContent = c.title || t("topbar.new_chat");
    $("#messages").innerHTML = '<div id="welcome" class="welcome"></div>';
    renderWelcome();
    await refreshChats();
  } catch (_) {}
}

async function openChat(id) {
  try {
    const c = await api().select_chat(id);
    if (!c) return;
    state.activeChatId = id;
    $("#chat-title").textContent = c.title || t("topbar.new_chat");
    const msgs = $("#messages"); msgs.innerHTML = "";
    for (const m of (c.messages || [])) addMessage(m.role, m.content);
    msgs.scrollTop = msgs.scrollHeight;
    renderChats($("#search-input").value);
  } catch (_) {}
}

function renderWelcome() {
  // Восстанавливаем welcome (после очистки сообщений).
  $("#messages").innerHTML = `
    <div id="welcome" class="welcome">
      <div class="welcome-mark">✸</div>
      <h2 data-i18n="welcome.title"></h2>
      <p class="welcome-sub" data-i18n="welcome.sub"></p>
      <div class="welcome-suggest">
        <button class="suggest-btn" data-i18n="welcome.s1" data-q-key="welcome.q1"></button>
        <button class="suggest-btn" data-i18n="welcome.s2" data-q-key="welcome.q2"></button>
        <button class="suggest-btn" data-i18n="welcome.s3" data-q-key="welcome.q3"></button>
        <button class="suggest-btn" data-i18n="welcome.s4" data-q-key="welcome.q4"></button>
      </div>
    </div>`;
  applyI18n($("#messages"));
  // re-bind
  $$(".suggest-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const ta = $("#input");
      ta.value = btn.dataset.q || btn.textContent.trim();
      autoResize(ta); ta.focus();
    });
  });
}

// ─── Messages render ─────────────────────────────────────────────────────
function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function renderMarkdown(text) {
  // Минимальный безопасный «markdown»: ```код```, `inline`, **bold**, *italic*.
  const fences = [];
  text = text.replace(/```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```/g, (m, lang, code) => {
    const id = fences.length;
    fences.push(`<pre><code data-lang="${escapeHtml(lang)}">${escapeHtml(code)}</code></pre>`);
    return `\u0000FENCE${id}\u0000`;
  });
  text = escapeHtml(text);
  text = text.replace(/`([^`\n]+?)`/g, (_m, c) => `<code>${c}</code>`);
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/(^|\W)\*([^*]+)\*(?=\W|$)/g, "$1<em>$2</em>");
  text = text.replace(/\u0000FENCE(\d+)\u0000/g, (_m, id) => fences[parseInt(id, 10)]);
  return text;
}

function addMessage(role, content) {
  const messages = $("#messages");
  const w = $("#welcome"); if (w) w.remove();
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = role === "user" ? escapeHtml(content) : renderMarkdown(content);
  row.appendChild(bubble);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
  return { row, bubble };
}

// ─── Send message ────────────────────────────────────────────────────────
async function sendMessage() {
  const ta = $("#input");
  const text = ta.value.trim();
  if (!text || !state.apiReady) return;
  ta.value = ""; autoResize(ta);

  addMessage("user", text);
  // Pre-create assistant bubble (will be filled by chunks).
  const { row, bubble } = addMessage("assistant", "");
  bubble.classList.add("typing");
  state.currentMsg = { id: null, row, bubble, fullText: "", toolBoxes: {} };

  try {
    const cid = await api().send_message(state.activeChatId || "", text);
    state.activeChatId = cid;
  } catch (e) {
    bubble.classList.remove("typing");
    bubble.innerHTML = `<span style="color:var(--danger)">${t("error.prefix")}${escapeHtml(String(e))}</span>`;
  }
}

// ─── Push events from Python ─────────────────────────────────────────────
function handlePushEvent(event, payload) {
  switch (event) {
    case "chat_created":      onChatCreated(payload);   break;
    case "title_updated":     onTitleUpdated(payload);  break;
    case "msg_start":         onMsgStart(payload);      break;
    case "msg_chunk":         onMsgChunk(payload);      break;
    case "tool_start":        onToolStart(payload);     break;
    case "tool_done":         onToolDone(payload);      break;
    case "msg_end":           onMsgEnd(payload);        break;
    case "msg_error":         onMsgError(payload);      break;
    case "ask_confirm":       onAskConfirm(payload);    break;
    case "ask_sudo":          onAskSudo(payload);       break;
  }
}
async function onChatCreated(p)  { state.activeChatId = p.id; await refreshChats(); }
async function onTitleUpdated(p) {
  if (state.activeChatId === p.id) $("#chat-title").textContent = p.title;
  await refreshChats();
}
function onMsgStart(p) {
  if (state.currentMsg) state.currentMsg.id = p.msg_id;
}
function onMsgChunk(p) {
  if (!state.currentMsg) return;
  state.currentMsg.fullText += p.chunk;
  state.currentMsg.bubble.innerHTML = renderMarkdown(state.currentMsg.fullText);
  state.currentMsg.bubble.classList.add("typing");
  const m = $("#messages"); m.scrollTop = m.scrollHeight;
}
function onToolStart(p) {
  if (!state.currentMsg || !state.showTools) return;
  const card = document.createElement("div");
  card.className = "tool-card";
  card.dataset.toolId = p.id;
  card.innerHTML = `<span class="tool-title">⚙ ${escapeHtml(p.tool_name)}</span> · <span class="muted">${t("tool.running")}</span>`;
  state.currentMsg.row.appendChild(card);
  state.currentMsg.toolBoxes[p.id] = card;
  const m = $("#messages"); m.scrollTop = m.scrollHeight;
}
function onToolDone(p) {
  if (!state.currentMsg) return;
  const card = state.currentMsg.toolBoxes[p.id];
  if (!card) return;
  card.classList.add("done");
  card.innerHTML = `<span class="tool-title">✓ ${escapeHtml(p.tool_name)}</span> · <span class="muted">${t("tool.done")}</span>`;
}
function onMsgEnd(p) {
  if (!state.currentMsg) return;
  state.currentMsg.bubble.classList.remove("typing");
  state.currentMsg = null;
}
function onMsgError(p) {
  if (!state.currentMsg) return;
  state.currentMsg.bubble.classList.remove("typing");
  state.currentMsg.bubble.innerHTML =
    `<span style="color:var(--danger)">${t("error.prefix")}${escapeHtml(p.error || "")}</span>`;
  state.currentMsg = null;
}

// ─── Confirm / Sudo ──────────────────────────────────────────────────────
let _confirmId = null;
function onAskConfirm(p) {
  _confirmId = p.id;
  $("#confirm-action").textContent = p.action || "";
  $("#confirm-target").textContent = p.target || "";
  $("#confirm-overlay").classList.remove("hide");
}
function resolveConfirm(yes) {
  if (_confirmId == null) return;
  try { api().resolve_confirm(_confirmId, !!yes); } catch (_) {}
  _confirmId = null;
  $("#confirm-overlay").classList.add("hide");
}
let _sudoId = null;
function onAskSudo(p) {
  _sudoId = p.id;
  const inp = $("#sudo-input"); inp.value = "";
  $("#sudo-overlay").classList.remove("hide");
  setTimeout(() => inp.focus(), 50);
}
function submitSudo(cancel) {
  if (_sudoId == null) return;
  const pwd = cancel ? "" : ($("#sudo-input").value || "");
  try { api().resolve_sudo(_sudoId, pwd); } catch (_) {}
  _sudoId = null;
  $("#sudo-overlay").classList.add("hide");
}

// ─── Settings ────────────────────────────────────────────────────────────
async function openSettings(initialTab) {
  // Загружаем актуальные значения и отрисовываем.
  let full = {};
  try { full = await api().get_settings_full() || {}; } catch (_) {}
  const ai = full.ai || {}; const ui = full.ui || {}; const safety = full.safety || {};

  $("#set-provider").value  = ai.provider || "anthropic";
  $("#set-base-url").value  = ai.base_url || "";
  $("#set-api-key").value   = ai.api_key  || "";
  $("#set-language").value  = ui.language || "ru";
  $("#set-anim").value      = ui.animation_speed || "normal";
  $("#set-show-tools").checked = !!ui.show_tool_calls;
  $("#set-show-ts").checked    = !!ui.show_timestamps;

  // Темы — отрисуем сетку и подсветим активную.
  renderThemeGrid();

  // Провайдер → модели
  await onProviderChanged(ai.model || "");

  // Профили
  await refreshProfiles();

  switchTab(initialTab || "ai");
  $("#settings-overlay").classList.remove("hide");
  applyI18n($("#settings-overlay"));
}
function closeSettings() {
  $("#settings-overlay").classList.add("hide");
  $("#settings-test-status").textContent = "";
  $("#settings-test-status").className = "test-status";
}
function switchTab(name) {
  $$(".settings-tabs .tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  $$(".tab-panel").forEach(p => p.classList.toggle("active", p.dataset.panel === name));
}

async function onProviderChanged(forcedModel) {
  const provider = $("#set-provider").value;
  const sel = $("#set-model-select");
  sel.innerHTML = "";
  let list = (state.models.providers && state.models.providers[provider]) || [];
  if (!list.length) {
    try {
      state.models = await api().get_models() || state.models;
      list = (state.models.providers && state.models.providers[provider]) || [];
    } catch (_) {}
  }
  for (const m of list) {
    const opt = document.createElement("option");
    opt.value = m; opt.textContent = m;
    sel.appendChild(opt);
  }
  // подставим текущую (или forced)
  const wanted = forcedModel ?? state.model;
  if (wanted && list.includes(wanted)) sel.value = wanted;
  $("#set-model-input").value = (wanted && !list.includes(wanted)) ? wanted : "";

  // Подсказка base_url по известным провайдерам
  const known = state.models.known_endpoints || {};
  const baseInp = $("#set-base-url");
  if (provider === "openai_compatible" && !baseInp.value && known["openai"]) {
    baseInp.placeholder = known["openai"];
  }
}

async function saveSettings() {
  const customModel = ($("#set-model-input").value || "").trim();
  const selectedModel = $("#set-model-select").value || "";
  const model = customModel || selectedModel;

  const payload = {
    ai: {
      provider:  $("#set-provider").value,
      model:     model,
      api_key:   $("#set-api-key").value || "",
      base_url:  $("#set-base-url").value || "",
    },
    ui: {
      theme:           state.themeKey,
      language:        $("#set-language").value,
      animation_speed: $("#set-anim").value,
      show_tool_calls: $("#set-show-tools").checked,
      show_timestamps: $("#set-show-ts").checked,
    },
    safety: {
      yolo_mode: state.yolo,
    },
  };

  let res = { ok: false };
  try { res = await api().save_settings(payload); } catch (e) { res = { ok: false, error: String(e) }; }

  if (res && res.ok) {
    state.provider = payload.ai.provider;
    state.model    = payload.ai.model;
    state.language = payload.ui.language;
    state.animSpeed= payload.ui.animation_speed;
    state.showTools= payload.ui.show_tool_calls;
    state.showTimestamps = payload.ui.show_timestamps;

    document.documentElement.dataset.anim = state.animSpeed;
    applyTheme(state.themeKey);
    applyI18n();

    // Обновляем кнопку моделей и бейдж
    await refreshModels();
    $("#provider-badge").textContent =
      `${prettyProvider(state.provider)}${state.model ? " · " + state.model : ""}`;

    closeSettings();
    toast(t("settings.saved"));
  } else {
    toast((res && res.error) || "Save failed");
  }
}

async function testProvider() {
  const status = $("#settings-test-status");
  status.textContent = t("settings.testing"); status.className = "test-status";
  const customModel = ($("#set-model-input").value || "").trim();
  const payload = {
    provider: $("#set-provider").value,
    model:    customModel || $("#set-model-select").value || "",
    api_key:  $("#set-api-key").value,
    base_url: $("#set-base-url").value,
  };
  let r = { ok: false };
  try { r = await api().test_provider(payload); } catch (e) { r = { ok: false, error: String(e) }; }
  if (r && r.ok) { status.textContent = t("settings.test_ok");  status.className = "test-status ok"; }
  else           { status.textContent = t("settings.test_fail", { err: (r && r.error) || "?" }); status.className = "test-status fail"; }
}

// ─── Profiles ────────────────────────────────────────────────────────────
async function refreshProfiles() {
  let r = {};
  try { r = await api().list_profiles() || {}; } catch (_) {}
  state.profiles      = r.profiles || {};
  state.activeProfile = r.active   || "";
  renderProfiles();
}

function renderProfiles() {
  const list = $("#profiles-list"); list.innerHTML = "";
  const entries = Object.entries(state.profiles || {});
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "popover-empty";
    empty.style.padding = "16px 4px";
    empty.textContent = "—";
    list.appendChild(empty);
    return;
  }
  for (const [name, p] of entries) {
    const isActive = name === state.activeProfile;
    const row = document.createElement("div");
    row.className = "profile-row" + (isActive ? " active" : "");
    row.innerHTML = `
      <div class="pmeta">
        <div class="pname">${escapeHtml(name)}</div>
        <div class="psub">${escapeHtml(prettyProvider(p.provider))} · ${escapeHtml(p.model || "—")}${p.base_url ? " · " + escapeHtml(p.base_url) : ""}</div>
      </div>
      ${isActive ? `<span class="ptag">${t("settings.profile_active")}</span>` : `<button class="ghost-btn small use-btn">${t("settings.profile_use")}</button>`}
      <button class="ghost-btn small del-pbtn">${t("settings.profile_delete")}</button>
    `;
    const useBtn = $(".use-btn", row);
    if (useBtn) useBtn.addEventListener("click", async () => {
      try { await api().switch_profile(name); } catch (_) {}
      toast(t("settings.profile_switched", { name }));
      await refreshProfiles();
      // обновим текущий провайдер/модель в форме
      const full = await api().get_settings_full();
      if (full && full.ai) {
        $("#set-provider").value = full.ai.provider || "anthropic";
        $("#set-base-url").value = full.ai.base_url || "";
        $("#set-api-key").value  = full.ai.api_key  || "";
        await onProviderChanged(full.ai.model);
      }
      // и в основном UI
      await refreshModels();
    });
    $(".del-pbtn", row).addEventListener("click", async () => {
      try { await api().delete_profile(name); } catch (_) {}
      toast(t("settings.profile_deleted"));
      await refreshProfiles();
    });
    list.appendChild(row);
  }
}

async function addProfileFromForm() {
  const name = ($("#prof-name").value || "").trim();
  if (!name) return;
  const customModel = ($("#set-model-input").value || "").trim();
  const provider = $("#set-provider").value;
  const model    = customModel || $("#set-model-select").value || "";
  const apiKey   = $("#set-api-key").value || "";
  const baseUrl  = $("#set-base-url").value || "";
  let ok = false;
  try { ok = await api().add_profile(name, provider, model, apiKey, baseUrl); } catch (_) {}
  if (ok) {
    $("#prof-name").value = "";
    toast(t("settings.profile_added"));
    await refreshProfiles();
    await refreshModels();
  }
}

// ─── Start ────────────────────────────────────────────────────────────────
boot().catch(console.error);
