"use strict";
const base = location.pathname.replace(/\/$/, "");
let revision = new URLSearchParams(location.search).get("revision");
let workRef, state, logicalRoot, stale = false, offline = false;
let pollTimer, activityTimer, currentProbe, lastProbe = -Infinity, lastActivity = -Infinity;
const retries = new WeakMap();
const CONTENT_TIMEOUT_MS = 60000, CONTROL_TIMEOUT_MS = 10000;
let probeAvailable = false;
const content = document.querySelector("#content");
const notice = document.querySelector("#notice");
document.querySelector("#current").href = base;

function node(tag, text, parent) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (parent) parent.append(element);
  return element;
}

function message(text, kind = "state") {
  notice.hidden = false;
  notice.dataset.kind = kind;
  notice.querySelector("span").textContent = text;
}

function superseded() {
  stale = true;
  clearTimeout(pollTimer);
  clearTimeout(activityTimer);
  message("方案已有新版本，请重新读取当前内容。");
}

function url(action, args = {}) {
  const query = new URLSearchParams(args);
  if (revision) query.set("revision", revision);
  return base + "/" + action + "?" + query;
}

function disconnected() {
  offline = true;
  probeAvailable = false;
  clearTimeout(pollTimer);
  clearTimeout(activityTimer);
  if (!stale) message("继续查看时，请让 Agent 重新打开此方案。", "connection");
}

async function request(address, options = {}, timeout = CONTENT_TIMEOUT_MS) {
  // This bounds the browser request, not the server's projection lifetime.
  return fetch(address, {cache: "no-store", signal: AbortSignal.timeout(timeout), ...options});
}

function readProblem(error) {
  return error.code === "view_request_timeout" ? "读取时间较长，请稍后重试。" :
    error.code === "view_resource_busy" ? "资源繁忙，请稍后重试。" : "读取暂时失败，请重试。";
}

async function transportFailure(error) {
  // A deadline or one failed resource request does not prove the host exited.
  await checkCurrent(true);
  const failure = new Error("读取未完成");
  failure.code = stale ? "view_superseded" : offline ? "view_service_unavailable" :
    error.name === "TimeoutError" ? "view_request_timeout" : "view_resource_unavailable";
  return failure;
}

async function read(action, args = {}) {
  if (offline && !await checkCurrent()) throw new Error("服务离线");
  let response, value;
  try {
    response = await request(url(action, args), {}, action === "current" ? CONTROL_TIMEOUT_MS : CONTENT_TIMEOUT_MS);
    value = await response.json();
  } catch (error) {
    throw await transportFailure(error);
  }
  if (response.status === 409) superseded();
  if (!response.ok) {
    if (value.error === "retiring") disconnected();
    const error = new Error("读取失败");
    error.code = value.error;
    throw error;
  }
  if (action !== "current" && (stale || (revision && value.revision !== revision) || (workRef && value.work_ref !== workRef))) {
    superseded();
    throw new Error("版本不一致");
  }
  return value;
}

function schedulePoll(remaining) {
  clearTimeout(pollTimer);
  if (!stale && !offline && document.visibilityState === "visible" && remaining > 0) {
    pollTimer = setTimeout(checkCurrent, Math.min(4000, remaining * 1000));
  }
}

async function checkCurrent(force = false) {
  if (stale) return false;
  if (currentProbe) return currentProbe;
  if (!force && performance.now() - lastProbe < (offline ? 4000 : 1000)) return probeAvailable;
  lastProbe = performance.now();
  currentProbe = (async () => {
    probeAvailable = false;
    try {
      const response = await request(url("current"), {}, CONTROL_TIMEOUT_MS);
      const current = await response.json();
      if (response.status === 409) {
        superseded();
        return false;
      }
      if (!response.ok) {
        if (current.error === "retiring") disconnected();
        else {
          clearTimeout(pollTimer);
          message("暂时无法检查预览，请稍后重试。", "read");
        }
        return false;
      }
      if (revision && current.revision !== revision) superseded();
      else {
        // First-load recovery can bind an as-yet empty current page. An exact
        // page or already loaded content must never adopt a newer revision.
        revision = revision || current.revision;
        if (state !== undefined && current.state !== state) message("此方案的状态已更新，请重新读取当前内容。");
        else if (notice.dataset.kind === "connection") notice.hidden = true;
      }
      offline = false;
      probeAvailable = !stale;
      schedulePoll(current.idle_remaining_seconds);
      return probeAvailable;
    } catch (error) {
      clearTimeout(pollTimer);
      if (error instanceof TypeError) disconnected(); // Failed connection, not a deadline.
      else message("暂时无法检查预览，请稍后重试。", "read");
      return false;
    } finally {
      currentProbe = null;
    }
  })();
  return currentProbe;
}

async function sendActivity() {
  activityTimer = undefined;
  if (document.visibilityState !== "visible" || stale || offline || !revision) return;
  lastActivity = performance.now();
  try {
    const response = await request(base + "/activity", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({revision})
    }, CONTROL_TIMEOUT_MS);
    if (response.status === 409) return superseded();
    if (!response.ok) {
      if ((await response.json()).error === "retiring") disconnected();
      return;
    }
    schedulePoll((await response.json()).idle_remaining_seconds);
  } catch { await checkCurrent(true); /* Probe once; never replay activity. */ }
}

function activity(event) {
  if (!event.isTrusted || document.visibilityState !== "visible" || stale || offline) return;
  const wait = 30000 - (performance.now() - lastActivity);
  if (wait <= 0) sendActivity();
  else if (!activityTimer) activityTimer = setTimeout(sendActivity, wait);
}
for (const kind of ["pointerdown", "click", "keydown", "touchstart", "scroll"]) {
  document.addEventListener(kind, activity, {passive: true, capture: true});
}
document.addEventListener("visibilitychange", async () => {
  clearTimeout(pollTimer);
  clearTimeout(activityTimer);
  activityTimer = undefined;
  if (document.visibilityState === "visible" && revision && await checkCurrent()) {
    activity({isTrusted: true});
  }
});

function sample(item, parent) {
  const figure = node("figure", undefined, parent);
  const label = item.label || "预览图片";
  const caption = node("figcaption", label, figure);
  let visual;
  function placeholder(text, temporary) {
    const missing = node("p", text);
    missing.className = "missing";
    missing.dataset.temporary = temporary ? "true" : "false";
    if (visual) visual.replaceWith(missing);
    else figure.insertBefore(missing, caption);
    visual = missing;
  }
  async function load() {
    if (stale) return placeholder("此版本已过期。", false);
    if (offline && !await checkCurrent()) return placeholder("暂时无法连接预览。", true);
    const link = node("a");
    link.href = url("asset", {ref: item.evidence_ref});
    link.target = "_blank";
    link.rel = "noopener";
    link.setAttribute("aria-label", "打开图片：" + label);
    const img = node("img", undefined, link);
    img.alt = label;
    img.loading = "lazy";
    img.addEventListener("error", async () => {
      if (!await checkCurrent()) return placeholder(stale ? "此版本已过期。" : "暂时无法读取预览，重新展开可重试。", !stale);
      try {
        const response = await request(link.href);
        if (response.status === 409) {
          superseded();
          return placeholder("此版本已过期。", false);
        }
        if (!response.ok) {
          const value = await response.json();
          if (value.error === "view_resource_busy") return placeholder("资源繁忙，重新展开可重试。", true);
          if (value.error === "retiring") {
            disconnected();
            return placeholder("暂时无法连接预览。", true);
          }
          if (value.error === "operation_failed") return placeholder("预览暂时无法读取，重新展开可重试。", true);
        }
        if (response.ok) await response.body?.cancel();
        if (stale) return placeholder("此版本已过期。", false);
        if (response.ok) {
          // A successful probe can follow a transient image failure. Retry the
          // original image once, without recursively probing/reloading the page.
          img.addEventListener("error", () => {
            placeholder(stale ? "此版本已过期。" : "预览暂时无法读取，重新展开可重试。", !stale);
          }, {once: true});
          img.src = link.href;
          return;
        }
        placeholder("图片无法读取", false);
      } catch (error) {
        const failure = await transportFailure(error);
        placeholder(stale ? "此版本已过期。" : offline ? "暂时无法连接预览。" :
          failure.code === "view_request_timeout" ? "图片读取较慢，重新展开可重试。" : "预览暂时无法读取，重新展开可重试。", !stale);
      }
    }, {once: true});
    if (visual) visual.replaceWith(link);
    else figure.insertBefore(link, caption);
    visual = link;
    img.src = link.href;
  }
  retries.set(figure, () => {
    if (visual?.dataset.temporary === "true") load();
  });
  if (item.evidence_ref && item.available) load();
  else placeholder("图片无法读取", false);
}

function group(item, parent) {
  const details = node("details", undefined, parent);
  details.className = "group";
  const summary = node("summary", undefined, details);
  node("span", item.relative_path.join(" / ") || logicalRoot, summary);
  node("span", item.total + " 个", summary).className = "count";
  // Collapsed groups retain their place without loading every image. Opening
  // another group or appending a page never rebuilds an existing gallery.
  details.addEventListener("toggle", () => {
    if (!details.open) return;
    if (details.dataset.loaded) {
      for (const figure of details.querySelectorAll("figure")) retries.get(figure)?.();
      return;
    }
    details.dataset.loaded = "true";
    const samples = item.samples || [];
    if (!samples.length) {
      node("p", "暂无预览图片。", details).className = "empty";
      return;
    }
    const gallery = node("div", undefined, details);
    gallery.className = "gallery";
    for (const item of samples) sample(item, gallery);
  });
}

async function groups() {
  const list = node("div", undefined, content);
  const continuation = node("div", undefined, content);
  continuation.className = "continuation";
  const status = node("p", "", continuation);
  status.setAttribute("role", "status");
  const button = node("button", "读取分组", continuation);
  let cursor = null, shown = 0;
  async function load() {
    button.disabled = true;
    status.textContent = "正在读取…";
    try {
      if (stale) throw new Error("版本已过期");
      const page = await read("page", {collection: "groups", ...(cursor ? {cursor} : {})});
      // An in-flight response must not append after obsolescence was observed.
      if (stale) throw new Error("版本已过期");
      for (const item of page.items) group(item, list);
      shown += page.items.length;
      cursor = page.next_cursor;
      status.textContent = page.complete ? "" : "已显示 " + shown + " / " + page.total + " 组";
      if (!shown && page.complete) status.textContent = "尚未保存分组。";
      button.hidden = page.complete;
      button.textContent = "继续浏览";
    } catch (error) {
      status.textContent = stale ? "此版本已过期。" : offline ? "暂时无法连接预览。" :
        error.code === "view_request_timeout" || error.code === "view_resource_busy" ? readProblem(error) : "分组读取失败，请重试。";
      button.hidden = stale;
      button.textContent = "重试读取";
    } finally {
      button.disabled = false;
    }
  }
  button.addEventListener("click", load);
  await load();
}

let starting = false, startRetry;
async function start() {
  if (starting || stale) return;
  starting = true;
  if (startRetry) startRetry.disabled = true;
  try {
    const value = await read("overview");
    revision = value.revision;
    workRef = value.work_ref;
    state = value.state;
    logicalRoot = value.logical_root;
    if (notice.dataset.kind === "read") notice.hidden = true;
    content.replaceChildren();
    startRetry = undefined;
    await groups();
    schedulePoll(600);
  } catch (error) {
    // Keep the page and any existing content. A user gesture makes one bounded
    // retry; an unfinished server request is never replayed by a timer.
    const status = content.querySelector('[role="status"]');
    if (status) status.textContent = stale ? "此版本已过期。" : "分组尚未载入。";
    if (!stale && !offline) message(readProblem(error), "read");
    if (!stale && !startRetry) {
      startRetry = node("button", "重试读取", content);
      startRetry.addEventListener("click", start);
    }
  } finally {
    starting = false;
    if (startRetry) startRetry.disabled = false;
  }
}
start();
