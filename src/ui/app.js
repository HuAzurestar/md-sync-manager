"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  name: "untitled.md",
  content: "# Untitled\n",
  savedContent: "# Untitled\n",
  catalog: [],
  selectedSection: null,
  pullPreviewId: null,
  language: "en",
  providerConfig: null,
};

const messages = {
  en: {
    title: "Markdown Focus Workbench", openFile: "Open file", download: "Download",
    immersiveMode: "Immersive editing", exitImmersive: "Exit immersive", documentMode: "Document / Sections", syncMode: "Sync",
    catalog: "Catalog", refresh: "Refresh", catalogHint: "Select several headings to read, or one heading to modify.",
    readSelection: "Read selection", focusSource: "Selected source", applySelection: "Apply selected section",
    remoteSync: "Remote sync", collection: "Collection", collectionHint: "Use a complete collection path, for example youtrack/issues/DEMO.",
    listRemote: "List remote", remoteObject: "Remote object", push: "Push", upload: "Upload / New",
    openRemote: "Open", pullPreview: "Preview pull", confirmPull: "Confirm pull", providerConfig: "Provider configuration",
    provider: "Provider", enabled: "Enabled", url: "URL", token: "Token", saveProvider: "Save provider", editor: "Editor", preview: "Preview",
    showEditor: "Editor", showPreview: "Preview",
    discardChanges: "Discard unsaved changes and open another document?",
    saved: "Saved", unsaved: "Unsaved", focusEntered: "Immersive editing enabled; press Escape to exit",
    focusExited: "Immersive editing disabled", tokenConfigured: "Token configured", tokenMissing: "Token not configured",
    tokenKeep: "Leave blank to keep the configured token", tokenEnter: "Enter a provider token",
  },
  zh: {
    showEditor: "\u7f16\u8f91", showPreview: "\u9884\u89c8",
    discardChanges: "\u653e\u5f03\u672a\u4fdd\u5b58\u7684\u66f4\u6539\u5e76\u6253\u5f00\u53e6\u4e00\u4e2a\u6587\u6863\uff1f",
    title: "Markdown 聚焦工作台", openFile: "打开文件", download: "下载副本",
    immersiveMode: "沉浸编辑", exitImmersive: "退出沉浸", documentMode: "文档 / 章节", syncMode: "同步",
    catalog: "目录", refresh: "刷新", catalogHint: "多选标题进行读取，单选标题进行修改。",
    readSelection: "读取所选", focusSource: "所选原文", applySelection: "应用所选章节",
    remoteSync: "远端同步", collection: "集合路径", collectionHint: "请输入完整集合路径，例如 youtrack/issues/DEMO。",
    listRemote: "列出远端", remoteObject: "远端对象", push: "推送", upload: "上传 / 新建",
    openRemote: "打开", pullPreview: "预览拉取", confirmPull: "确认拉取", providerConfig: "Provider 配置",
    provider: "Provider", enabled: "启用", url: "地址", token: "令牌", saveProvider: "保存 Provider", editor: "编辑器", preview: "预览",
    saved: "已保存", unsaved: "未保存", focusEntered: "已进入沉浸编辑；按 Esc 退出",
    focusExited: "已退出沉浸编辑", tokenConfigured: "令牌已配置", tokenMissing: "令牌未配置",
    tokenKeep: "留空可保留当前令牌", tokenEnter: "请输入 Provider 令牌",
  },
};

async function api(path, payload = null, method = "POST") {
  const options = { method, headers: {} };
  if (payload !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  const envelope = await response.json();
  if (!response.ok || envelope.status !== "success") {
    throw new Error(envelope.error?.message || `${response.status} ${response.statusText}`);
  }
  return envelope.data;
}

function setStatus(message, error = false) {
  $("statusMessage").textContent = message;
  $("statusMessage").dataset.error = String(error);
}

function updateDirtyState() {
  const dirty = state.content !== state.savedContent;
  $("dirtyBadge").dataset.state = dirty ? "dirty" : "clean";
  $("dirtyBadge").textContent = messages[state.language][dirty ? "unsaved" : "saved"];
}

function updateFocusModeButton() {
  const active = document.body.classList.contains("focus-mode");
  const button = $("focusModeButton");
  button.textContent = messages[state.language][active ? "exitImmersive" : "immersiveMode"];
  button.setAttribute("aria-pressed", String(active));
  button.title = active ? messages[state.language].focusExited : messages[state.language].focusEntered;
}

function renderProviderTokenStatus() {
  const provider = state.providerConfig;
  if (!provider) return;
  const status = $("providerTokenStatus");
  const configured = provider.token_configured;
  const source = provider.token_source ? ` · ${provider.token_source}` : "";
  status.dataset.state = configured ? "configured" : "missing";
  status.textContent = `${messages[state.language][configured ? "tokenConfigured" : "tokenMissing"]}${source}`;
  $("providerToken").placeholder = messages[state.language][configured ? "tokenKeep" : "tokenEnter"];
}

function setFocusMode(active) {
  document.body.classList.toggle("focus-mode", active);
  updateFocusModeButton();
  setStatus(messages[state.language][active ? "focusEntered" : "focusExited"]);
  if (active) $("editor").focus();
}

function hasUnsavedChanges() {
  return state.content !== state.savedContent;
}

function confirmDiscard() {
  return !hasUnsavedChanges() || window.confirm(messages[state.language].discardChanges);
}

function renderContent() {
  $("editor").value = state.content;
  $("preview").textContent = state.content;
  $("currentName").textContent = state.name;
  updateDirtyState();
}

function setDocument(name, content, saved = true) {
  state.name = name || "untitled.md";
  state.content = content;
  if (saved) state.savedContent = content;
  state.catalog = [];
  state.selectedSection = null;
  state.pullPreviewId = null;
  $("catalogList").replaceChildren();
  $("focusEditor").value = "";
  $("focusApplyButton").disabled = true;
  $("pullConfirmButton").disabled = true;
  renderContent();
}

function selectedHeadings() {
  return [...document.querySelectorAll(".catalog-select:checked")].map((item) => item.value);
}

function renderCatalog(entries) {
  const container = $("catalogList");
  container.replaceChildren();
  entries.forEach((entry, index) => {
    const label = document.createElement("label");
    label.className = "catalog-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "catalog-select";
    checkbox.value = entry.heading;
    checkbox.addEventListener("change", () => {
      const count = selectedHeadings().length;
      $("focusReadButton").disabled = count === 0;
      $("focusApplyButton").disabled = count !== 1 || !state.selectedSection;
    });
    const text = document.createElement("span");
    text.textContent = `${index + 1}. ${entry.heading} · L${entry.line}`;
    label.append(checkbox, text);
    container.append(label);
  });
}

async function refreshCatalog() {
  const result = await api("/api/v1/document/catalog", { name: state.name, content: state.content });
  state.catalog = result.entries;
  renderCatalog(result.entries);
  setStatus(`Catalog: ${result.entries.length} headings`);
}

async function readFocus() {
  const selectors = selectedHeadings();
  const result = await api("/api/v1/document/focus/read", { name: state.name, content: state.content, selectors });
  $("focusEditor").value = result.sections.map((item) => item.source).join("\n");
  state.selectedSection = result.sections.length === 1 ? result.sections[0] : null;
  $("focusApplyButton").disabled = !state.selectedSection;
  setStatus(`Read ${result.sections.length} section(s)`);
}

async function applyFocus() {
  const selectors = selectedHeadings();
  if (selectors.length !== 1 || !state.selectedSection) return;
  const result = await api("/api/v1/document/focus/apply", {
    name: state.name,
    content: state.content,
    selector: selectors[0],
    expected_source: state.selectedSection.source,
    replacement: $("focusEditor").value,
  });
  state.content = result.content;
  state.selectedSection = result.section;
  renderContent();
  await refreshCatalog();
  setStatus("Section applied");
}

async function openLocalFile(file) {
  if (!file || !file.name.toLowerCase().endsWith(".md")) throw new Error("Choose a .md file");
  if (!confirmDiscard()) return false;
  setDocument(file.name, await file.text(), true);
  await refreshCatalog();
  return true;
}

async function listRemote() {
  const target = $("collectionInput").value.trim();
  const result = await api("/api/v1/sync/list", { target });
  const select = $("remoteObjectSelect");
  select.replaceChildren(new Option("—", ""));
  result.items.forEach((item) => select.add(new Option(`${item.id} · ${item.title}`, item.id)));
  setStatus(`Remote objects: ${result.items.length}`);
}

async function openRemote() {
  if (!confirmDiscard()) return;
  const result = await api("/api/v1/sync/open", { remote: $("remoteInput").value.trim() });
  setDocument(result.name, result.content, true);
  await refreshCatalog();
}

async function previewPull() {
  const source = $("remoteInput").value.trim() || null;
  const result = await api("/api/v1/sync/pull/preview", { name: state.name, content: state.content, source });
  state.pullPreviewId = result.preview_id;
  $("pullConfirmButton").disabled = false;
  $("syncOutput").textContent = result.diff || "No content change";
  setStatus("Pull preview ready");
}

async function confirmPull() {
  const result = await api("/api/v1/sync/pull/confirm", {
    name: state.name, content: state.content, preview_id: state.pullPreviewId,
  });
  setDocument(state.name, result.content, true);
  await refreshCatalog();
  setStatus("Pull applied");
}

async function pushDocument() {
  const result = await api("/api/v1/sync/push", { name: state.name, content: state.content });
  state.savedContent = state.content;
  updateDirtyState();
  $("syncOutput").textContent = JSON.stringify(result.result, null, 2);
  setStatus("Push complete");
}

async function uploadDocument() {
  const result = await api("/api/v1/sync/upload", {
    name: state.name, content: state.content, target: $("collectionInput").value.trim(),
  });
  setDocument(state.name, result.content, true);
  $("syncOutput").textContent = JSON.stringify(result.result, null, 2);
  setStatus(result.result.status === "PARTIAL" ? "Upload partially completed" : "Upload complete");
}

async function loadProvider() {
  const config = await api("/api/v1/providers", null, "GET");
  const provider = config.providers[$("providerSelect").value];
  state.providerConfig = provider;
  $("providerEnabled").checked = provider.enabled;
  $("providerUrl").value = provider.url;
  $("providerToken").value = "";
  renderProviderTokenStatus();
}

async function saveProvider() {
  const name = $("providerSelect").value;
  const values = { enabled: $("providerEnabled").checked, url: $("providerUrl").value.trim() };
  if ($("providerToken").value) values.token = $("providerToken").value;
  await api("/api/v1/providers", { providers: { [name]: values } }, "PUT");
  $("providerToken").value = "";
  setStatus(`${name} configuration saved`);
  await loadProvider();
}

function downloadDocument() {
  const blob = new Blob([state.content], { type: "text/markdown;charset=utf-8" });
  const anchor = document.createElement("a");
  const objectUrl = URL.createObjectURL(blob);
  anchor.href = objectUrl;
  anchor.download = state.name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

function applyLanguage() {
  document.documentElement.lang = state.language;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = messages[state.language][node.dataset.i18n] || node.textContent;
  });
  updateDirtyState();
  updateFocusModeButton();
  renderProviderTokenStatus();
}

function handleError(action) {
  return async (...args) => {
    try { await action(...args); }
    catch (error) { setStatus(error.message || String(error), true); }
  };
}

$("editor").addEventListener("input", () => {
  state.content = $("editor").value;
  $("preview").textContent = state.content;
  state.selectedSection = null;
  $("focusApplyButton").disabled = true;
  updateDirtyState();
});
$("fileInput").addEventListener("change", handleError(async (event) => {
  await openLocalFile(event.target.files[0]);
  event.target.value = "";
}));
$("catalogButton").addEventListener("click", handleError(refreshCatalog));
$("focusReadButton").addEventListener("click", handleError(readFocus));
$("focusApplyButton").addEventListener("click", handleError(applyFocus));
$("remoteListButton").addEventListener("click", handleError(listRemote));
$("remoteOpenButton").addEventListener("click", handleError(openRemote));
$("pullPreviewButton").addEventListener("click", handleError(previewPull));
$("pullConfirmButton").addEventListener("click", handleError(confirmPull));
$("pushButton").addEventListener("click", handleError(pushDocument));
$("uploadButton").addEventListener("click", handleError(uploadDocument));
$("providerSelect").addEventListener("change", handleError(loadProvider));
$("providerSaveButton").addEventListener("click", handleError(saveProvider));
$("downloadButton").addEventListener("click", downloadDocument);
$("focusModeButton").addEventListener("click", () => {
  setFocusMode(!document.body.classList.contains("focus-mode"));
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.body.classList.contains("focus-mode")) setFocusMode(false);
});
$("languageSelect").addEventListener("change", (event) => { state.language = event.target.value; applyLanguage(); });
document.querySelectorAll(".mobile-pane-switch button").forEach((button) => {
  button.addEventListener("click", () => {
    const pane = button.dataset.mobilePane;
    document.querySelector(".editor-column").dataset.mobilePane = pane;
    document.querySelectorAll(".mobile-pane-switch button").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
  });
});
$("remoteObjectSelect").addEventListener("change", (event) => {
  const id = event.target.value;
  if (id) $("remoteInput").value = `${$("collectionInput").value.trim()}/${id}`;
});
document.querySelectorAll(".mode-button").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".mode-button").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".control-panel").forEach((panel) => panel.classList.toggle("active", panel.id === button.dataset.panel));
}));

const dropZone = $("dropZone");
dropZone.addEventListener("dragover", (event) => { event.preventDefault(); dropZone.classList.add("dragging"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragging"));
dropZone.addEventListener("drop", handleError(async (event) => {
  event.preventDefault(); dropZone.classList.remove("dragging"); await openLocalFile(event.dataTransfer.files[0]);
}));
window.addEventListener("beforeunload", (event) => {
  if (!hasUnsavedChanges()) return;
  event.preventDefault();
  event.returnValue = "";
});

renderContent();
applyLanguage();
handleError(refreshCatalog)();
handleError(loadProvider)();
