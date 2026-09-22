"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  name: "untitled.md",
  content: "# Untitled\n",
  savedContent: "# Untitled\n",
  catalog: [],
  selectedSection: null,
  pullPreviewId: null,
  pushPreviewId: null,
  language: "en",
  providerConfig: null,
};

const messages = {
  en: {
    title: "Markdown Focus Workbench", openFile: "Open file", download: "Download",
    immersiveMode: "Immersive editing", exitImmersive: "Exit immersive", documentMode: "Document / Sections", syncMode: "Sync",
    stepOne: "Step 1", stepTwo: "Step 2", stepThree: "Step 3",
    catalog: "Catalog", refresh: "Refresh", catalogHint: "Select headings from the current document.",
    focusReadTitle: "Focus read", focusReadHint: "Select one or more headings, then read their exact source.",
    focusWriteTitle: "Focus write", focusWriteHint: "Select exactly one heading and read it before editing.",
    readSelection: "Read selected sections", focusSource: "Selected section source", applySelection: "Write selected section",
    remoteBrowse: "Remote list", collection: "Collection", collectionHint: "Use a complete collection path, for example youtrack/issues/DEMO.",
    listRemote: "List remote", remoteObject: "Remote object", push: "Push", pull: "Pull", upload: "Upload / New",
    openRemote: "Open remote", transferPreview: "Preview changes", confirm: "Confirm", providerConfig: "Provider configuration",
    transferTitle: "Transfer", transferHint: "Preview remote changes before replacing either side.",
    pullHint: "Remote → editor", pushHint: "Editor → remote", fileCopies: "File copies", fileCopiesHint: "Local copy or new remote",
    changePreview: "Change preview / result",
    provider: "Provider", enabled: "Enabled", url: "URL", token: "Token", saveProvider: "Save provider", editor: "Markdown source", preview: "Rendered preview",
    sourceBadge: "Editable source", renderedBadge: "Rendered result",
    showEditor: "Editor", showPreview: "Preview",
    discardChanges: "Discard unsaved changes and open another document?",
    saved: "Saved", unsaved: "Unsaved", focusEntered: "Immersive editing enabled; press Escape to exit",
    focusExited: "Immersive editing disabled", tokenConfigured: "Token configured", tokenMissing: "Token not configured",
    tokenKeep: "Leave blank to keep the configured token", tokenEnter: "Enter a provider token",
    selectedCount: (count) => `${count} selected`, focusWriteReady: "Edit the exact source below, then write it back safely.",
    focusWriteMultiple: "Multiple sections can be read together; select exactly one and read again to enable writing.",
  },
  zh: {
    showEditor: "\u7f16\u8f91", showPreview: "\u9884\u89c8",
    discardChanges: "\u653e\u5f03\u672a\u4fdd\u5b58\u7684\u66f4\u6539\u5e76\u6253\u5f00\u53e6\u4e00\u4e2a\u6587\u6863\uff1f",
    title: "Markdown 聚焦工作台", openFile: "打开文件", download: "下载副本",
    immersiveMode: "沉浸编辑", exitImmersive: "退出沉浸", documentMode: "文档 / 章节", syncMode: "同步",
    stepOne: "第 1 步", stepTwo: "第 2 步", stepThree: "第 3 步",
    catalog: "标题目录", refresh: "刷新", catalogHint: "从当前文档中选择一个或多个标题。",
    focusReadTitle: "Focus 读取", focusReadHint: "选择一个或多个标题，读取对应章节的精确原文。",
    focusWriteTitle: "Focus 写回", focusWriteHint: "请选择一个标题并先读取，随后才能编辑写回。",
    readSelection: "读取所选章节", focusSource: "所选章节原文", applySelection: "写回所选章节",
    remoteBrowse: "远端列表", collection: "集合路径", collectionHint: "请输入完整集合路径，例如 youtrack/issues/DEMO。",
    listRemote: "列出远端", remoteObject: "远端对象", push: "推送", pull: "拉取", upload: "上传 / 新建",
    openRemote: "打开远端", transferPreview: "预览差异", confirm: "确认", providerConfig: "Provider 配置",
    transferTitle: "传输操作", transferHint: "覆盖本地或远端前，先预览变化。",
    pullHint: "远端 → 编辑器", pushHint: "编辑器 → 远端", fileCopies: "文件副本", fileCopiesHint: "下载本地副本或新建远端",
    changePreview: "差异预览 / 操作结果",
    provider: "Provider", enabled: "启用", url: "地址", token: "令牌", saveProvider: "保存 Provider", editor: "Markdown 源码", preview: "渲染预览",
    sourceBadge: "可编辑源码", renderedBadge: "渲染结果",
    saved: "已保存", unsaved: "未保存", focusEntered: "已进入沉浸编辑；按 Esc 退出",
    focusExited: "已退出沉浸编辑", tokenConfigured: "令牌已配置", tokenMissing: "令牌未配置",
    tokenKeep: "留空可保留当前令牌", tokenEnter: "请输入 Provider 令牌",
    selectedCount: (count) => `已选 ${count} 项`, focusWriteReady: "编辑下方精确原文，然后安全写回。",
    focusWriteMultiple: "可以合并读取多个章节；如需写回，请只选一个标题并重新读取。",
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

function appendInlineMarkdown(target, source) {
  const pattern = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\n]+\*|\[[^\]\n]+\]\((?:https?:\/\/|mailto:)[^)\s]+\))/g;
  let cursor = 0;
  for (const match of source.matchAll(pattern)) {
    target.append(document.createTextNode(source.slice(cursor, match.index)));
    const token = match[0];
    let node;
    if (token.startsWith("**")) {
      node = document.createElement("strong");
      node.textContent = token.slice(2, -2);
    } else if (token.startsWith("`")) {
      node = document.createElement("code");
      node.textContent = token.slice(1, -1);
    } else if (token.startsWith("*")) {
      node = document.createElement("em");
      node.textContent = token.slice(1, -1);
    } else {
      const parts = token.match(/^\[([^\]]+)\]\((.+)\)$/);
      node = document.createElement("a");
      node.textContent = parts[1];
      node.href = parts[2];
      node.rel = "noopener noreferrer";
      node.target = "_blank";
    }
    target.append(node);
    cursor = match.index + token.length;
  }
  target.append(document.createTextNode(source.slice(cursor)));
}

function isMarkdownBlockStart(line) {
  return /^(#{1,6})\s+/.test(line)
    || /^```/.test(line)
    || /^>\s?/.test(line)
    || /^\s*[-*+]\s+/.test(line)
    || /^\s*\d+\.\s+/.test(line);
}

function renderMarkdownPreview(content) {
  const preview = $("preview");
  preview.replaceChildren();
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  if (lines[0] === "---") {
    const end = lines.indexOf("---", 1);
    if (end > 0) {
      const details = document.createElement("details");
      details.className = "frontmatter-preview";
      const summary = document.createElement("summary");
      summary.textContent = "Document metadata";
      const source = document.createElement("pre");
      source.textContent = lines.slice(1, end).join("\n");
      details.append(summary, source);
      preview.append(details);
      index = end + 1;
    }
  }

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index += 1; continue; }

    if (/^```/.test(line)) {
      const codeLines = [];
      index += 1;
      while (index < lines.length && !/^```/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.textContent = codeLines.join("\n");
      pre.append(code);
      preview.append(pre);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const node = document.createElement(`h${heading[1].length}`);
      appendInlineMarkdown(node, heading[2]);
      preview.append(node);
      index += 1;
      continue;
    }

    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
    if (unordered || ordered) {
      const list = document.createElement(unordered ? "ul" : "ol");
      const matcher = unordered ? /^\s*[-*+]\s+(.+)$/ : /^\s*\d+\.\s+(.+)$/;
      while (index < lines.length) {
        const item = lines[index].match(matcher);
        if (!item) break;
        const entry = document.createElement("li");
        appendInlineMarkdown(entry, item[1]);
        list.append(entry);
        index += 1;
      }
      preview.append(list);
      continue;
    }

    if (/^>\s?/.test(line)) {
      const quote = document.createElement("blockquote");
      const quoteLines = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quoteLines.push(lines[index].replace(/^>\s?/, ""));
        index += 1;
      }
      appendInlineMarkdown(quote, quoteLines.join(" "));
      preview.append(quote);
      continue;
    }

    const paragraphLines = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !isMarkdownBlockStart(lines[index])) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    const paragraph = document.createElement("p");
    appendInlineMarkdown(paragraph, paragraphLines.join(" "));
    preview.append(paragraph);
  }
}

function renderSyncOutput(value, kind = "result") {
  const output = $("syncOutput");
  output.replaceChildren();
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  if (!text && kind !== "diff") return;
  for (const line of (text || "No content change").split("\n")) {
    const row = document.createElement("span");
    row.className = "output-line";
    if (kind === "diff") {
      if (line.startsWith("+") && !line.startsWith("+++")) row.classList.add("diff-add");
      else if (line.startsWith("-") && !line.startsWith("---")) row.classList.add("diff-remove");
      else if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) row.classList.add("diff-meta");
    }
    row.textContent = line || " ";
    output.append(row);
  }
}

function renderContent() {
  $("editor").value = state.content;
  renderMarkdownPreview(state.content);
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
  state.pushPreviewId = null;
  $("catalogList").replaceChildren();
  $("focusReadOutput").textContent = "";
  $("focusEditor").value = "";
  $("focusEditor").disabled = true;
  $("focusApplyButton").disabled = true;
  $("focusReadButton").disabled = true;
  $("pullConfirmButton").disabled = true;
  $("pushConfirmButton").disabled = true;
  renderSyncOutput("");
  updateFocusSelection();
  renderContent();
}

function selectedHeadings() {
  return [...document.querySelectorAll(".catalog-select:checked")].map((item) => item.value);
}

function updateFocusSelection(resetRead = false) {
  const count = selectedHeadings().length;
  const copy = messages[state.language];
  $("focusSelectionBadge").textContent = copy.selectedCount(count);
  $("focusReadButton").disabled = count === 0;
  if (resetRead) {
    state.selectedSection = null;
    $("focusReadOutput").textContent = "";
    $("focusEditor").value = "";
  }
  const writable = count === 1 && Boolean(state.selectedSection);
  $("focusEditor").disabled = !writable;
  $("focusApplyButton").disabled = !writable;
  $("focusWriteHint").textContent = writable
    ? copy.focusWriteReady
    : (count > 1 ? copy.focusWriteMultiple : copy.focusWriteHint);
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
    checkbox.addEventListener("change", () => updateFocusSelection(true));
    const text = document.createElement("span");
    text.textContent = `${index + 1}. ${entry.heading} · L${entry.line}`;
    label.append(checkbox, text);
    container.append(label);
  });
  updateFocusSelection(true);
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
  const combined = result.sections.map((item) => item.source).join("\n");
  $("focusReadOutput").textContent = combined;
  state.selectedSection = result.sections.length === 1 ? result.sections[0] : null;
  $("focusEditor").value = state.selectedSection ? state.selectedSection.source : "";
  updateFocusSelection();
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
  renderSyncOutput(result.diff, "diff");
  setStatus("Pull preview ready");
}

async function confirmPull() {
  const result = await api("/api/v1/sync/pull/confirm", {
    name: state.name, content: state.content, preview_id: state.pullPreviewId,
  });
  state.pullPreviewId = null;
  $("pullConfirmButton").disabled = true;
  setDocument(state.name, result.content, true);
  await refreshCatalog();
  setStatus("Pull applied");
}

async function previewPush() {
  const result = await api("/api/v1/sync/push/preview", { name: state.name, content: state.content });
  state.pushPreviewId = result.preview_id;
  $("pushConfirmButton").disabled = false;
  renderSyncOutput(result.diff, "diff");
  setStatus("Push preview ready");
}

async function confirmPush() {
  const result = await api("/api/v1/sync/push/confirm", {
    name: state.name, content: state.content, preview_id: state.pushPreviewId,
  });
  state.pushPreviewId = null;
  $("pushConfirmButton").disabled = true;
  state.savedContent = state.content;
  updateDirtyState();
  renderSyncOutput(result.result);
  setStatus("Push complete");
}

async function uploadDocument() {
  const result = await api("/api/v1/sync/upload", {
    name: state.name, content: state.content, target: $("collectionInput").value.trim(),
  });
  setDocument(state.name, result.content, true);
  renderSyncOutput(result.result);
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
  const tokenInput = $("providerToken");
  const values = { enabled: $("providerEnabled").checked, url: $("providerUrl").value.trim() };
  if (tokenInput.value) values.token = tokenInput.value;
  tokenInput.value = "";
  await api("/api/v1/providers", { providers: { [name]: values } }, "PUT");
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
  updateFocusSelection();
}

function handleError(action) {
  return async (...args) => {
    try { await action(...args); }
    catch (error) { setStatus(error.message || String(error), true); }
  };
}

$("editor").addEventListener("input", () => {
  state.content = $("editor").value;
  renderMarkdownPreview(state.content);
  updateFocusSelection(true);
  state.pullPreviewId = null;
  state.pushPreviewId = null;
  $("pullConfirmButton").disabled = true;
  $("pushConfirmButton").disabled = true;
  renderSyncOutput("Document changed; preview the transfer again.");
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
$("pushPreviewButton").addEventListener("click", handleError(previewPush));
$("pushConfirmButton").addEventListener("click", handleError(confirmPush));
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
