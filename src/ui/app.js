"use strict";

const $ = (id) => document.getElementById(id);
const state = {
  name: "untitled.md",
  content: "# Untitled\n",
  savedContent: "# Untitled\n",
  hasLocalFile: false,
  catalog: [],
  selectedSection: null,
  pullPreviewId: null,
  pushPreviewId: null,
  transferPreview: null,
  language: "en",
  providerConfig: null,
  editorMode: "source",
  renderedContent: null,
  locked: false,
  status: { key: "ready", args: [], error: false },
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
    provider: "Provider", enabled: "Enabled", url: "URL", token: "Token", saveProvider: "Save provider", editor: "Markdown source", preview: "Rendered Markdown",
    differenceMode: "Difference", sourceMode: "Markdown source", renderMode: "Render",
    differenceHint: "Inspect the latest pull or push difference.", sourceHint: "Edit the Markdown text directly.", renderHint: "Secondary read-only view rendered with CommonMark.", rendering: "Rendering…",
    discardChanges: "Discard unsaved changes and open another document?",
    localUnchanged: "Local file unchanged", unsavedLocal: "Not saved locally", noLocalCopy: "No local copy",
    downloadStarted: "Copy download started", transferTargetChanged: "Transfer target changed; preview again.",
    clearStoredToken: "Clear stored token",
    focusEntered: "Immersive editing enabled; press Escape to exit",
    focusExited: "Immersive editing disabled", tokenConfigured: "Token configured", tokenMissing: "Token not configured",
    tokenKeep: "Leave blank to keep the configured token", tokenEnter: "Enter a provider token",
    selectedCount: (count) => `${count} selected`, focusWriteReady: "Edit the exact source below, then write it back safely.",
    focusWriteMultiple: "Multiple sections can be read together; select exactly one and read again to enable writing.",
    ready: "Ready", catalogStatus: (count) => `Catalog: ${count} headings`, readStatus: (count) => `Read ${count} section(s)`,
    sectionApplied: "Section applied", remoteObjectsStatus: (count) => `Remote objects: ${count}`,
    pullPreviewReady: "Pull preview ready", pullApplied: "Pull applied", pushPreviewReady: "Push preview ready", pushComplete: "Push complete",
    uploadPartial: "Upload partially completed", uploadComplete: "Upload complete", providerSaved: (name) => `${name} configuration saved`,
    documentChanged: "Document changed; preview the transfer again.", noContentChange: "No content change",
    fileChanged: (count) => `${count} file${count === 1 ? "" : "s"} changed`, pullTransfer: "Pull · remote → source", pushTransfer: "Push · source → remote",
    workbenchModeLabel: "Workbench mode", languageLabel: "Language", remoteObjectsLabel: "Remote objects",
    editorLabel: "Markdown source editor", previewLabel: "Rendered Markdown preview", editorDisplayModeLabel: "Editor display mode",
    focusEmpty: "Select headings and read to inspect source.", diffEmpty: "Preview a Pull or Push to inspect source changes.",
    baseBranch: "Base branch", headBranch: "Head branch", pullRequestBranches: "Pull Request branches",
    pullRequestBranchesHint: "Required only when creating a GitHub or Gitee Pull Request.",
    pullRequestBranchesRequired: "Base and head branches are required for Pull Request uploads.",
  },
  zh: {
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
    provider: "Provider", enabled: "启用", url: "地址", token: "令牌", saveProvider: "保存 Provider", editor: "Markdown 源码", preview: "Markdown 渲染",
    differenceMode: "差异", sourceMode: "Markdown 源码", renderMode: "渲染",
    differenceHint: "检查最近一次 Pull 或 Push 的差异。", sourceHint: "直接编辑 Markdown 文本。", renderHint: "使用 CommonMark 的次要只读视图。", rendering: "正在渲染…",
    localUnchanged: "本地文件未更改", unsavedLocal: "尚未保存到本地", noLocalCopy: "无本地副本",
    downloadStarted: "已开始下载副本", transferTargetChanged: "传输目标已更改；请重新预览。",
    clearStoredToken: "清除已存储令牌",
    focusEntered: "已进入沉浸编辑；按 Esc 退出",
    focusExited: "已退出沉浸编辑", tokenConfigured: "令牌已配置", tokenMissing: "令牌未配置",
    tokenKeep: "留空可保留当前令牌", tokenEnter: "请输入 Provider 令牌",
    selectedCount: (count) => `已选 ${count} 项`, focusWriteReady: "编辑下方精确原文，然后安全写回。",
    focusWriteMultiple: "可以合并读取多个章节；如需写回，请只选一个标题并重新读取。",
    ready: "就绪", catalogStatus: (count) => `目录：${count} 个标题`, readStatus: (count) => `已读取 ${count} 个章节`,
    sectionApplied: "章节已写回", remoteObjectsStatus: (count) => `远端对象：${count} 个`,
    pullPreviewReady: "拉取差异已就绪", pullApplied: "拉取已应用", pushPreviewReady: "推送差异已就绪", pushComplete: "推送完成",
    uploadPartial: "上传已部分完成", uploadComplete: "上传完成", providerSaved: (name) => `${name} 配置已保存`,
    documentChanged: "文档已更改；请重新预览传输差异。", noContentChange: "内容无变化",
    fileChanged: (count) => `${count} 个文件有变化`, pullTransfer: "拉取 · 远端 → 源码", pushTransfer: "推送 · 源码 → 远端",
    workbenchModeLabel: "工作台模式", languageLabel: "语言", remoteObjectsLabel: "远端对象",
    editorLabel: "Markdown 源码编辑器", previewLabel: "Markdown 渲染预览", editorDisplayModeLabel: "编辑器显示模式",
    focusEmpty: "请选择标题并读取，以检查章节原文。", diffEmpty: "请预览拉取或推送操作，以检查源码差异。",
    baseBranch: "目标分支", headBranch: "来源分支", pullRequestBranches: "Pull Request 分支",
    pullRequestBranchesHint: "仅在新建 GitHub 或 Gitee Pull Request 时必填。",
    pullRequestBranchesRequired: "新建 Pull Request 时必须填写目标分支和来源分支。",
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
  state.status = null;
  $("statusMessage").textContent = message;
  $("statusMessage").dataset.error = String(error);
}

function renderLocalizedStatus() {
  if (!state.status) return;
  const value = messages[state.language][state.status.key];
  $("statusMessage").textContent = typeof value === "function" ? value(...state.status.args) : value;
  $("statusMessage").dataset.error = String(state.status.error);
}

function setLocalizedStatus(key, args = [], error = false) {
  state.status = { key, args, error };
  renderLocalizedStatus();
}

function updateDirtyState() {
  const dirty = hasUnsavedChanges();
  $("dirtyBadge").dataset.state = dirty ? "dirty" : "clean";
  const key = dirty ? "unsavedLocal" : (state.hasLocalFile ? "localUnchanged" : "noLocalCopy");
  $("dirtyBadge").textContent = messages[state.language][key];
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
  setLocalizedStatus(active ? "focusEntered" : "focusExited");
  if (active) {
    setEditorMode("source");
    $("editor").focus();
  }
}

function hasUnsavedChanges() {
  return state.content !== state.savedContent;
}

function confirmDiscard() {
  return !hasUnsavedChanges() || window.confirm(messages[state.language].discardChanges);
}

function setWorkbenchLocked(locked) {
  state.locked = locked;
  const workspace = $("dropZone");
  workspace.inert = locked;
  workspace.setAttribute("aria-busy", String(locked));
  $("editor").readOnly = locked;
  $("focusEditor").readOnly = locked;
  $("openFileButton").disabled = locked;
  $("fileInput").disabled = locked;
  $("focusModeButton").disabled = locked;
}

function withWorkbenchLock(action) {
  return async (...args) => {
    if (state.locked) return;
    setWorkbenchLocked(true);
    try { return await action(...args); }
    finally { setWorkbenchLocked(false); }
  };
}

function isPullRequestCollection(target) {
  const parts = target.trim().replace(/^\/+|\/+$/g, "").split("/");
  return parts.length === 4
    && ["github", "gitee"].includes(parts[0].toLowerCase())
    && parts[1].toLowerCase() === "pulls";
}

function updatePullRequestFields() {
  const visible = isPullRequestCollection($("collectionInput").value);
  $("pullRequestFields").hidden = !visible;
  $("baseInput").required = visible;
  $("headInput").required = visible;
}

async function refreshRenderedPreview() {
  const content = state.content;
  if (state.renderedContent === content) return;
  $("preview").textContent = messages[state.language].rendering;
  const result = await api("/api/v1/document/render", { name: state.name, content });
  if (content !== state.content) return;
  $("preview").innerHTML = result.html;
  state.renderedContent = content;
}

async function setEditorMode(mode) {
  state.editorMode = mode;
  document.querySelector(".editor-column").dataset.editorMode = mode;
  document.querySelectorAll(".mode-surface").forEach((surface) => {
    surface.classList.toggle("active", surface.id === ({ difference: "syncOutput", source: "editor", render: "preview" })[mode]);
  });
  document.querySelectorAll(".editor-mode-switch button").forEach((button) => {
    const active = button.dataset.editorMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const copy = messages[state.language];
  const titleKey = mode === "difference" ? "differenceMode" : (mode === "render" ? "preview" : "editor");
  $("editorModeTitle").textContent = copy[titleKey];
  $("editorModeHint").textContent = copy[`${mode}Hint`];
  if (mode === "render") await refreshRenderedPreview();
}

function renderSyncOutput(value, kind = "result", activate = false, direction = null) {
  const viewer = $("diffViewer");
  const stats = $("diffStats");
  viewer.replaceChildren();
  stats.hidden = true;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  if (!text && kind !== "diff") return;
  if (kind === "diff") {
    const files = window.Diff2Html.parse(text || "");
    const added = files.reduce((total, file) => total + file.addedLines, 0);
    const deleted = files.reduce((total, file) => total + file.deletedLines, 0);
    const copy = messages[state.language];
    const transfer = direction === "pull" ? copy.pullTransfer : (direction === "push" ? copy.pushTransfer : "");
    const fileCount = copy.fileChanged(files.length);
    $("diffFiles").textContent = transfer ? `${transfer} · ${fileCount}` : fileCount;
    $("diffAdded").textContent = `+${added}`;
    $("diffDeleted").textContent = `−${deleted}`;
    stats.hidden = false;
    if (files.length) {
      viewer.innerHTML = window.Diff2Html.html(files, {
        drawFileList: false,
        matching: "lines",
        diffStyle: "word",
        outputFormat: "line-by-line",
        renderNothingWhenEmpty: false,
      });
    } else {
      viewer.textContent = copy.noContentChange;
    }
  } else {
    const result = document.createElement("pre");
    result.className = "transfer-result";
    result.textContent = text;
    viewer.append(result);
  }
  if (activate) setEditorMode("difference");
}

function renderTransferPreview() {
  if (!state.transferPreview) return;
  renderSyncOutput(
    state.transferPreview.diff,
    "diff",
    true,
    state.transferPreview.direction,
  );
}

function invalidateTransferPreview() {
  if (!state.pullPreviewId && !state.pushPreviewId) return;
  state.pullPreviewId = null;
  state.pushPreviewId = null;
  state.transferPreview = null;
  $("pullConfirmButton").disabled = true;
  $("pushConfirmButton").disabled = true;
  renderSyncOutput(messages[state.language].transferTargetChanged);
  setLocalizedStatus("transferTargetChanged");
}

function renderContent() {
  $("editor").value = state.content;
  $("currentName").textContent = state.name;
  updateDirtyState();
  if (state.editorMode === "render") handleError(refreshRenderedPreview)();
}

function setDocument(name, content, {
  localFile = false, preserveLocalBaseline = false, preserveTransferPreview = false,
} = {}) {
  state.name = name || "untitled.md";
  state.content = content;
  if (!preserveLocalBaseline) {
    state.savedContent = content;
    state.hasLocalFile = localFile;
  }
  state.catalog = [];
  state.selectedSection = null;
  state.pullPreviewId = null;
  state.pushPreviewId = null;
  if (!preserveTransferPreview) state.transferPreview = null;
  state.renderedContent = null;
  $("catalogList").replaceChildren();
  $("focusReadOutput").textContent = "";
  $("focusEditor").value = "";
  $("focusEditor").disabled = true;
  $("focusApplyButton").disabled = true;
  $("focusReadButton").disabled = true;
  $("pullConfirmButton").disabled = true;
  $("pushConfirmButton").disabled = true;
  if (!preserveTransferPreview) {
    renderSyncOutput("");
    setEditorMode("source");
  }
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
  setLocalizedStatus("catalogStatus", [result.entries.length]);
}

async function readFocus() {
  const selectors = selectedHeadings();
  const result = await api("/api/v1/document/focus/read", { name: state.name, content: state.content, selectors });
  const combined = result.sections.map((item) => item.source).join("\n");
  $("focusReadOutput").textContent = combined;
  state.selectedSection = result.sections.length === 1 ? result.sections[0] : null;
  $("focusEditor").value = state.selectedSection ? state.selectedSection.source : "";
  updateFocusSelection();
  setLocalizedStatus("readStatus", [result.sections.length]);
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
  setLocalizedStatus("sectionApplied");
}

async function openLocalFile(file) {
  if (!file || !file.name.toLowerCase().endsWith(".md")) throw new Error("Choose a .md file");
  if (!confirmDiscard()) return false;
  setDocument(file.name, await file.text(), { localFile: true });
  await refreshCatalog();
  return true;
}

async function listRemote() {
  const target = $("collectionInput").value.trim();
  const result = await api("/api/v1/sync/list", { target });
  const select = $("remoteObjectSelect");
  select.replaceChildren(new Option("—", ""));
  result.items.forEach((item) => select.add(new Option(`${item.id} · ${item.title}`, item.id)));
  setLocalizedStatus("remoteObjectsStatus", [result.items.length]);
}

async function openRemote() {
  if (!confirmDiscard()) return;
  const result = await api("/api/v1/sync/open", { remote: $("remoteInput").value.trim() });
  setDocument(result.name, result.content);
  await refreshCatalog();
}

async function previewPull() {
  const source = $("remoteInput").value.trim() || null;
  const result = await api("/api/v1/sync/pull/preview", { name: state.name, content: state.content, source });
  state.pushPreviewId = null;
  $("pushConfirmButton").disabled = true;
  state.pullPreviewId = result.preview_id;
  state.transferPreview = { diff: result.diff, direction: result.direction };
  $("pullConfirmButton").disabled = false;
  renderTransferPreview();
  setLocalizedStatus("pullPreviewReady");
}

async function confirmPull() {
  const result = await api("/api/v1/sync/pull/confirm", {
    name: state.name, content: state.content, preview_id: state.pullPreviewId,
  });
  state.pullPreviewId = null;
  $("pullConfirmButton").disabled = true;
  setDocument(state.name, result.content, {
    preserveLocalBaseline: true, preserveTransferPreview: true,
  });
  await refreshCatalog();
  renderTransferPreview();
  setLocalizedStatus("pullApplied");
}

async function previewPush() {
  const result = await api("/api/v1/sync/push/preview", { name: state.name, content: state.content });
  state.pullPreviewId = null;
  $("pullConfirmButton").disabled = true;
  state.pushPreviewId = result.preview_id;
  state.transferPreview = { diff: result.diff, direction: result.direction };
  $("pushConfirmButton").disabled = false;
  renderTransferPreview();
  setLocalizedStatus("pushPreviewReady");
}

async function confirmPush() {
  await api("/api/v1/sync/push/confirm", {
    name: state.name, content: state.content, preview_id: state.pushPreviewId,
  });
  state.pushPreviewId = null;
  $("pushConfirmButton").disabled = true;
  updateDirtyState();
  renderTransferPreview();
  setLocalizedStatus("pushComplete");
}

async function uploadDocument() {
  const target = $("collectionInput").value.trim();
  const payload = { name: state.name, content: state.content, target };
  if (isPullRequestCollection(target)) {
    const base = $("baseInput").value.trim();
    const head = $("headInput").value.trim();
    if (!base || !head) throw new Error(messages[state.language].pullRequestBranchesRequired);
    payload.base = base;
    payload.head = head;
  }
  const result = await api("/api/v1/sync/upload", payload);
  setDocument(state.name, result.content, { preserveLocalBaseline: true });
  renderSyncOutput(result.result, "result", true);
  setLocalizedStatus(result.result.status === "PARTIAL" ? "uploadPartial" : "uploadComplete");
}

async function loadProvider() {
  const config = await api("/api/v1/providers", null, "GET");
  const provider = config.providers[$("providerSelect").value];
  state.providerConfig = provider;
  $("providerEnabled").checked = provider.enabled;
  $("providerUrl").value = provider.url;
  $("providerToken").value = "";
  $("providerToken").disabled = false;
  $("providerClearToken").checked = false;
  $("providerClearToken").disabled = provider.token_source !== "yaml";
  renderProviderTokenStatus();
}

async function saveProvider() {
  const name = $("providerSelect").value;
  const tokenInput = $("providerToken");
  const values = { enabled: $("providerEnabled").checked, url: $("providerUrl").value.trim() };
  if ($("providerClearToken").checked) values.clear_token = true;
  else if (tokenInput.value) values.token = tokenInput.value;
  tokenInput.value = "";
  await api("/api/v1/providers", { providers: { [name]: values } }, "PUT");
  setLocalizedStatus("providerSaved", [name]);
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
  setLocalizedStatus("downloadStarted");
}

function applyLanguage() {
  document.documentElement.lang = state.language;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = messages[state.language][node.dataset.i18n] || node.textContent;
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((node) => {
    node.setAttribute("aria-label", messages[state.language][node.dataset.i18nAriaLabel]);
  });
  $("focusReadOutput").dataset.emptyMessage = messages[state.language].focusEmpty;
  $("diffViewer").dataset.emptyMessage = messages[state.language].diffEmpty;
  updateDirtyState();
  updateFocusModeButton();
  renderProviderTokenStatus();
  updateFocusSelection();
  renderLocalizedStatus();
  setEditorMode(state.editorMode);
}

function handleError(action) {
  return async (...args) => {
    try { await action(...args); }
    catch (error) { setStatus(error.message || String(error), true); }
  };
}

$("editor").addEventListener("input", () => {
  state.content = $("editor").value;
  state.renderedContent = null;
  updateFocusSelection(true);
  state.pullPreviewId = null;
  state.pushPreviewId = null;
  state.transferPreview = null;
  $("pullConfirmButton").disabled = true;
  $("pushConfirmButton").disabled = true;
  renderSyncOutput(messages[state.language].documentChanged);
  setLocalizedStatus("documentChanged");
  updateDirtyState();
});
$("openFileButton").addEventListener("click", () => { if (!state.locked) $("fileInput").click(); });
$("fileInput").addEventListener("change", handleError(withWorkbenchLock(async (event) => {
  await openLocalFile(event.target.files[0]);
  event.target.value = "";
})));
$("catalogButton").addEventListener("click", handleError(withWorkbenchLock(refreshCatalog)));
$("focusReadButton").addEventListener("click", handleError(withWorkbenchLock(readFocus)));
$("focusApplyButton").addEventListener("click", handleError(withWorkbenchLock(applyFocus)));
$("remoteListButton").addEventListener("click", handleError(withWorkbenchLock(listRemote)));
$("remoteOpenButton").addEventListener("click", handleError(withWorkbenchLock(openRemote)));
$("pullPreviewButton").addEventListener("click", handleError(withWorkbenchLock(previewPull)));
$("pullConfirmButton").addEventListener("click", handleError(withWorkbenchLock(confirmPull)));
$("pushPreviewButton").addEventListener("click", handleError(withWorkbenchLock(previewPush)));
$("pushConfirmButton").addEventListener("click", handleError(withWorkbenchLock(confirmPush)));
$("uploadButton").addEventListener("click", handleError(withWorkbenchLock(uploadDocument)));
$("providerSelect").addEventListener("change", handleError(withWorkbenchLock(loadProvider)));
$("providerSaveButton").addEventListener("click", handleError(withWorkbenchLock(saveProvider)));
$("providerClearToken").addEventListener("change", () => {
  const clearing = $("providerClearToken").checked;
  $("providerToken").disabled = clearing;
  if (clearing) $("providerToken").value = "";
});
$("downloadButton").addEventListener("click", downloadDocument);
$("focusModeButton").addEventListener("click", () => {
  setFocusMode(!document.body.classList.contains("focus-mode"));
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.body.classList.contains("focus-mode")) setFocusMode(false);
});
$("languageSelect").addEventListener("change", (event) => { state.language = event.target.value; applyLanguage(); });
$("collectionInput").addEventListener("input", () => {
  updatePullRequestFields();
  invalidateTransferPreview();
});
$("remoteInput").addEventListener("input", invalidateTransferPreview);
document.querySelectorAll(".editor-mode-switch button").forEach((button) => {
  button.addEventListener("click", handleError(withWorkbenchLock(() => setEditorMode(button.dataset.editorMode))));
});
$("remoteObjectSelect").addEventListener("change", (event) => {
  const id = event.target.value;
  if (id) $("remoteInput").value = `${$("collectionInput").value.trim()}/${id}`;
  invalidateTransferPreview();
});
document.querySelectorAll(".mode-button").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".mode-button").forEach((item) => item.classList.toggle("active", item === button));
  document.querySelectorAll(".control-panel").forEach((panel) => panel.classList.toggle("active", panel.id === button.dataset.panel));
}));

const dropZone = $("dropZone");
dropZone.addEventListener("dragover", (event) => { event.preventDefault(); dropZone.classList.add("dragging"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragging"));
dropZone.addEventListener("drop", handleError(withWorkbenchLock(async (event) => {
  event.preventDefault(); dropZone.classList.remove("dragging"); await openLocalFile(event.dataTransfer.files[0]);
})));
window.addEventListener("beforeunload", (event) => {
  if (!hasUnsavedChanges()) return;
  event.preventDefault();
  event.returnValue = "";
});

renderContent();
applyLanguage();
updatePullRequestFields();
handleError(refreshCatalog)();
handleError(loadProvider)();
