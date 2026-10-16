"""Dashboard HTML.

Kept as a module string rather than a static file so the package stays
single-import with no data-file packaging concerns. The palette is injected at
request time from the Python theme module, so the web UI and the desktop UI can
never drift apart.

All user-supplied text is written with textContent — never innerHTML.
"""

from __future__ import annotations

from ..gui.theme import DARK, LIGHT

_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="__MODE__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EliLain-Music</title>
<style>
:root {
  --bg-top: __BG_TOP__;      --bg-bottom: __BG_BOTTOM__;
  --surface: __SURFACE__;    --surface-alt: __SURFACE_ALT__;
  --border: __BORDER__;      --border-strong: __BORDER_STRONG__;
  --text: __TEXT__;          --text-dim: __TEXT_DIM__;  --text-faint: __TEXT_FAINT__;
  --accent: __ACCENT__;      --accent-hover: __ACCENT_HOVER__;
  --accent-press: __ACCENT_PRESS__; --accent-text: __ACCENT_TEXT__;
  --signal: __SIGNAL__;
  --ok: __OK__;  --warn: __WARN__;  --err: __ERR__;
  --track: __TRACK__;
  --radius: 6px;
  --mono: "Cascadia Mono", ui-monospace, Consolas, monospace;
}
__PALETTE_OVERRIDES__
[data-theme="light"] { color-scheme: light; }
[data-theme="dark"]  { color-scheme: dark; }

* { box-sizing: border-box; }
html { min-height: 100%; }
body {
  margin: 0; padding: 32px;
  background: var(--bg-top); color: var(--text);
  font: 14px/1.6 "Segoe UI", system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1280px; margin: 0 auto; display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 24px; align-items: start; }
.console { min-width: 0; display: flex; flex-direction: column; gap: 24px; }
.skip-link { position: absolute; top: 8px; left: 8px; padding: 10px 16px; background: var(--accent); color: var(--accent-text); z-index: 5; transform: translateY(-160%); border-radius: var(--radius); }
.skip-link:focus { transform: none; }
header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
h1 { margin: 0; font-size: clamp(24px, 3vw, 34px); line-height: 1.2; font-weight: 600; letter-spacing: -1px; overflow-wrap: anywhere; }
.tag { color: var(--signal); font: 11px/1.6 var(--mono); letter-spacing: 1.2px; margin-top: 8px; }
.who { flex-shrink: 0; font: 11px/1.7 var(--mono); color: var(--text-dim); text-align: right; }
.who button { margin-top: 8px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 24px; box-shadow: inset 0 1px 0 rgba(255,255,255,.035); min-width: 0; }
.card > h2 { margin: 0 0 20px; font: 600 12px/1.5 var(--mono); letter-spacing: 1.4px; color: var(--text-dim); }
.row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; min-width: 0; }
.row + .row { margin-top: 16px; }
.grow { flex: 1 1 280px; min-width: 0; }
.source-label { display: block; margin-bottom: 8px; font-weight: 600; }
.help { margin: 8px 0 0; color: var(--text-faint); font-size: 12px; }
input[type=text], input[type=url], select {
  width: 100%; min-width: 0; min-height: 44px; padding: 10px 12px;
  background: var(--surface-alt); border: 1px solid var(--border-strong);
  border-radius: var(--radius); color: var(--text); font: inherit;
  box-shadow: inset 0 2px 3px rgba(0,0,0,.08);
}
input:hover, select:hover { border-color: var(--signal); }
input::placeholder { color: var(--text-faint); }
input[aria-invalid="true"] { border-color: var(--err); }
select { cursor: pointer; }
.field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.field > span { font-size: 12px; color: var(--text-dim); }
.field.wide { flex: 1 1 220px; }
button {
  display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  min-height: 40px; max-width: 100%; padding: 10px 16px;
  border: 1px solid transparent; border-radius: var(--radius);
  background: var(--accent); color: var(--accent-text);
  font: inherit; font-weight: 600; cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.22), inset 0 -1px 0 rgba(0,0,0,.15), 0 2px 3px rgba(0,0,0,.08);
}
button:hover:not(:disabled) { background: var(--accent-hover); }
button:active:not(:disabled) { background: var(--accent-press); box-shadow: inset 0 2px 3px rgba(0,0,0,.18); }
button.ghost { background: var(--surface-alt); color: var(--text); border-color: var(--border-strong); }
button.ghost:hover:not(:disabled) { background: var(--border); border-color: var(--signal); }
button.ghost:active:not(:disabled) { background: var(--surface); border-color: var(--signal); }
button.danger { background: var(--surface-alt); color: var(--err); border-color: var(--border-strong); }
button.danger:hover:not(:disabled) { border-color: var(--err); }
button.danger:active:not(:disabled) { background: var(--surface); }
button:disabled { background: var(--surface-alt); color: var(--text-faint); border-color: var(--border); box-shadow: none; cursor: not-allowed; }
button:disabled kbd { color: inherit; border-color: var(--border); box-shadow: none; }
button:focus-visible, input:focus-visible, select:focus-visible, a:focus-visible { outline: 2px solid var(--signal); outline-offset: 3px; }
kbd { display: inline-block; padding: 2px 6px; min-width: 24px; border: 1px solid var(--border-strong); border-bottom: 3px solid var(--border-strong); border-radius: 4px; background: var(--surface-alt); color: var(--signal); font: 11px/1.4 var(--mono); box-shadow: inset 0 1px 0 rgba(255,255,255,.09); white-space: nowrap; }
button kbd { color: inherit; border-color: currentColor; background: transparent; font-size: 10px; }
.shortcuts { display: flex; gap: 12px 20px; flex-wrap: wrap; color: var(--text-dim); font-size: 12px; }
.shortcuts span { display: inline-flex; gap: 6px; align-items: center; }
label.chk { display: inline-flex; align-items: center; gap: 8px; min-height: 40px; color: var(--text-dim); cursor: pointer; }
label.chk input { accent-color: var(--accent); width: 18px; height: 18px; margin: 0; cursor: pointer; }
ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
li.job { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 12px; padding: 14px 16px; background: var(--surface-alt); border: 1px solid var(--border); border-left: 3px solid var(--text-faint); border-radius: var(--radius); }
li.job[data-state="running"] { border-left-color: var(--signal); }
li.job[data-state="done"] { border-left-color: var(--ok); }
li.job[data-state="error"] { border-left-color: var(--err); }
li.job[data-state="cancelled"] { border-left-color: var(--warn); }
.jname { min-width: 0; font-weight: 600; overflow-wrap: anywhere; }
.jmeta { grid-column: 1 / -1; font: 12px/1.6 var(--mono); color: var(--text-dim); overflow-wrap: anywhere; }
.jstate { font: 600 11px/1.6 var(--mono); text-transform: uppercase; align-self: start; color: var(--text-dim); overflow-wrap: anywhere; max-width: 130px; }
li.job[data-state="running"] .jstate { color: var(--signal); }
li.job[data-state="done"] .jstate { color: var(--ok); }
li.job[data-state="error"] .jstate { color: var(--err); }
li.job[data-state="cancelled"] .jstate { color: var(--warn); }
.bar { grid-column: 1 / -1; height: 5px; border-radius: 3px; background: var(--track); overflow: hidden; margin: 4px 0; }
.bar > i { display: block; height: 100%; background: var(--accent); border-radius: 3px; }
.empty { padding: 28px 16px; text-align: center; color: var(--text-dim); border: 1px dashed var(--border-strong); border-radius: var(--radius); }
.empty strong { display: block; font: 600 12px/1.6 var(--mono); letter-spacing: 1.6px; color: var(--signal); margin-bottom: 8px; }
.empty p { margin: 0; font-size: 13px; }
.error { color: var(--err); font-size: 13px; overflow-wrap: anywhere; margin: 8px 0 0; }
.error:empty, .connection-status:empty { display: none; }
.connection-status { margin: 0; color: var(--warn); font-size: 13px; }
.queue-footer { margin-top: 16px; justify-content: space-between; }
.pill { font: 11px/1.6 var(--mono); color: var(--text-dim); padding: 5px 9px; border: 1px solid var(--border); border-radius: var(--radius); overflow-wrap: anywhere; max-width: 100%; }
.pill b { color: var(--text); font-weight: 600; }
.no { color: var(--err); }
/* Artwork defines this interface; no copy overlays the original images. */
.wired-side { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.serial { font: 10px/1.6 var(--mono); letter-spacing: 1.2px; color: var(--text-dim); }
.lain-title { font: 64px/1 Georgia, serif; margin: 0; color: var(--text); letter-spacing: -3px; }
.portrait { margin: 0; position: relative; overflow: hidden; border: 1px solid var(--border-strong); border-radius: var(--radius); background: #000; }
.portrait img { width: 100%; aspect-ratio: 1; object-fit: contain; display: block; }
.wired-banner { margin: 0; background: #000; border: 1px solid var(--border-strong); border-radius: 14px; overflow: hidden; }
.wired-banner img { width: 100%; aspect-ratio: 734 / 241; object-fit: contain; display: block; }
.wires { width: 100%; height: 50px; color: var(--signal); }
.scene { display: block; width: 100%; height: auto; border: 1px solid var(--border); border-radius: var(--radius); }
.aside-note { margin: 0; font-size: 12px; color: var(--text-dim); }
.art-credit { font-size: 11px; color: var(--text-faint); }
@media (prefers-reduced-motion: no-preference) {
  [data-motion="on"] .portrait::after { content: ""; position: absolute; inset: 0; pointer-events: none; background: repeating-linear-gradient(to bottom,transparent 0px,transparent 3px,rgba(0,0,0,.08) 3px,rgba(0,0,0,.08) 4px); }
  [data-motion="on"] .portrait::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px; background: rgba(255,255,255,.12); z-index: 1; animation: trace 25s linear infinite; pointer-events: none; }
}
@keyframes trace { to { top: 100%; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
@media (forced-colors: active) { button, input, select, kbd { border: 1px solid ButtonText; } :focus-visible { outline-color: Highlight; } }
@media (max-width: 960px) {
  body { padding: 24px; }
  .wrap { grid-template-columns: 210px minmax(0, 1fr); gap: 20px; }
  .wired-side { padding: 16px; }
  header { align-items: flex-start; flex-direction: column; }
  .who { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; text-align: left; }
  .who button { margin: 0; }
}
@media (max-width: 700px) {
  body { padding: 16px; }
  .wrap { grid-template-columns: minmax(0, 1fr); gap: 20px; }
  .wired-side { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px 16px; }
  .portrait { grid-column: 1; grid-row: 1 / 5; align-self: center; }
  .serial, .lain-title { grid-column: 2; }
  .lain-title { font-size: 48px; }
  .wires, .scene { display: none; }
  .aside-note, .art-credit { grid-column: 1 / -1; }
  .card { padding: 18px; }
  input[type=text], input[type=url], select { font-size: 16px; }
  button { min-height: 44px; }
  .row > .grow { flex-basis: 100%; }
  .field.wide { flex-basis: 100%; }
  .jstate { max-width: 90px; }
}
</style>
</head>
<body>
<a class="skip-link" href="#source">Skip to source connection</a>
<div class="wrap">
  <aside class="wired-side" aria-label="Serial Experiments Lain artwork">
    <div class="serial">SERIAL EXPERIMENTS</div>
    <div class="lain-title">lain.</div>
    <div class="serial">岩倉玲音 / IWAKURA LAIN</div>
    <figure class="portrait"><img src="/art/lain.png" alt="Lain leaning toward her monitor, lit in cyan"></figure>
    <div class="serial">REAL WORLD ↔ WIRED</div>
    <svg class="wires" viewBox="0 0 214 70" fill="none" aria-hidden="true">
      <path d="M-8 4C76 68 134 4 226 32M-8 12C76 76 134 12 226 40M-8 20C76 84 134 20 226 48" stroke="currentColor"/>
      <path d="M147 5V70M125 14H169" stroke="currentColor" stroke-width="2"/>
    </svg>
    <img class="scene" src="/art/wired-city.png" alt="Blue ruins of Nakano in the Wired">
    <p class="aside-note">A quiet place for your music.<br>Saved here. Not in the cloud.</p>
    <label class="chk"><input type="checkbox" id="motionToggle"> CRT motion</label>
    <span class="art-credit" title="Artwork © its respective rights holders; not covered by the app's MIT license.">User-supplied fan artwork · rights retained by their respective holders.</span>
  </aside>
  <main class="console">
  <figure class="wired-banner"><img src="/art/wired-banner.png" alt="A cyan hand and a hot-pink hand reaching across the black Wired"></figure>
  <header>
    <div>
      <h1>EliLain-Music</h1>
      <div class="tag">LAYER : SOUND / LOCAL AUDIO ARCHIVE</div>
    </div>
    <div class="who">
      <div>yt-dlp <span id="ytdlp">…</span></div>
      <div>ffmpeg <span id="ffmpeg">…</span></div>
      <button class="ghost" id="themeBtn" aria-keyshortcuts="Control+T" aria-label="Switch to Real World light theme"><span id="theme-label">Real World</span><kbd aria-hidden="true">Ctrl T</kbd></button>
    </div>
  </header>

  <section class="card" id="source" tabindex="-1" aria-labelledby="source-title">
    <h2 id="source-title">01 / SOURCE CONNECTION</h2>
    <label for="url" class="source-label">Music link or search</label>
    <div class="row">
      <input class="grow" type="text" id="url" name="source" autocomplete="off" spellcheck="false" aria-describedby="url-help source-error" aria-keyshortcuts="Control+L"
             placeholder="Paste a music link or type a search">
      <button id="go" aria-keyshortcuts="Control+Enter">Download <kbd aria-hidden="true">Ctrl ↵</kbd></button>
      <button class="danger" id="cancelAll" aria-keyshortcuts="Escape" disabled>Stop all <kbd aria-hidden="true">Esc</kbd></button>
    </div>
    <p class="help" id="url-help">YouTube · YouTube Music · SoundCloud · Spotify. Audio stays on this computer.</p>
    <p class="error" id="source-error" role="alert"></p>
    <div class="row">
      <label class="field wide">
        <span>Quality</span>
        <select id="quality">
          <option value="low">Low · 96 kbps opus</option>
          <option value="medium">Medium · 192 kbps opus</option>
          <option value="high" selected>High · 320 kbps mp3</option>
          <option value="best">Best · native codec</option>
          <option value="lossless">Lossless · FLAC</option>
        </select>
      </label>
      <label class="chk"><input type="checkbox" id="meta" checked> Tags</label>
      <label class="chk"><input type="checkbox" id="art" checked> Cover</label>
      <span class="pill">Output <b id="outdir">Configured local folder</b></span>
    </div>
  </section>

  <p class="connection-status" id="connection-status" role="status"></p>
  <section class="card" aria-labelledby="queue-title">
    <h2 id="queue-title">02 / TRANSFER QUEUE</h2>
    <ul id="jobs" aria-label="Audio transfers"></ul>
    <div class="empty" id="empty"><strong>NO SIGNAL YET</strong><p>Your archive starts with a connection.<br>Paste a link or search above, then choose Download.</p></div>
    <div class="row queue-footer">
      <span class="pill" id="summary" role="status">Ready to connect</span>
      <button class="ghost" id="clear">Clear finished</button>
    </div>
  </section>
  <footer class="shortcuts" aria-label="Keyboard shortcuts">
    <span><kbd>Ctrl</kbd><kbd>L</kbd> Focus source</span>
    <span><kbd>Ctrl</kbd><kbd>Enter</kbd> Download</span>
    <span><kbd>Ctrl</kbd><kbd>T</kbd> Switch theme</span>
    <span><kbd>Esc</kbd> Stop active transfers</span>
  </footer>
  </main>
</div>

<script>
const $ = (id) => document.getElementById(id);
function updateThemeLabel() {
  const dark = document.documentElement.dataset.theme === "dark";
  $("theme-label").textContent = dark ? "Real World" : "Wired";
  $("themeBtn").setAttribute("aria-label", dark ? "Switch to Real World light theme" : "Switch to Wired dark theme");
}
updateThemeLabel();
try { $("motionToggle").checked = localStorage.getItem("elilain-motion") === "on"; } catch (e) { /* storage may be unavailable */ }
function setMotion() {
  const value = $("motionToggle").checked ? "on" : "off";
  document.documentElement.dataset.motion = value;
  try { localStorage.setItem("elilain-motion", value); } catch (e) { /* still works without storage */ }
}
$("motionToggle").addEventListener("change", setMotion);
setMotion();
const fmtBytes = (n) => {
  if (!n) return "—";
  const u = ["B","KB","MB","GB"];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v.toFixed(0) : v.toFixed(1)) + " " + u[i];
};
const fmtEta = (s) => {
  if (!s || s < 0) return "—";
  s = Math.round(s);
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60);
  return m < 60 ? m + "m " + String(s % 60).padStart(2, "0") + "s"
                  : Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m";
};

let pollTimer = null;

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let message = await res.text();
    try {
      const body = JSON.parse(message);
      if (typeof body.detail === "string") message = body.detail;
    } catch (e) { /* a local proxy may return plain text */ }
    throw new Error(message || "The local service could not complete this request.");
  }
  return res.json();
}

function renderJob(job) {
  const li = document.createElement("li");
  li.className = "job";
  li.dataset.state = job.state;

  const name = document.createElement("div");
  name.className = "jname";
  name.textContent = job.label;              // textContent, not innerHTML
  name.title = job.url;

  const state = document.createElement("div");
  state.className = "jstate";
  state.textContent = job.status_text;

  const bar = document.createElement("div");
  bar.className = "bar";
  const percent = Math.max(0, Math.min(100, Number(job.percent) || 0));
  bar.setAttribute("role", "progressbar");
  bar.setAttribute("aria-label", "Transfer progress: " + job.label);
  bar.setAttribute("aria-valuemin", "0");
  bar.setAttribute("aria-valuemax", "100");
  bar.setAttribute("aria-valuenow", String(percent));
  const fill = document.createElement("i");
  fill.style.width = percent + "%";
  bar.appendChild(fill);

  const meta = document.createElement("div");
  meta.className = "jmeta";
  if (job.state === "done") {
    meta.textContent = job.files.length > 1
      ? job.files.length + " files · " + job.path
      : job.path;
  } else if (job.state === "error") {
    meta.textContent = job.error;
  } else if (job.state === "running") {
    meta.textContent = fmtBytes(job.speed) + "/s · ETA " + fmtEta(job.eta) +
                       " · " + job.quality;
  } else {
    meta.textContent = job.quality;
  }

  li.append(name, state, bar, meta);
  return li;
}

async function poll() {
  let data;
  try { data = await api("/api/jobs"); }
  catch (e) {
    $("connection-status").textContent = "Connection to the local service was lost. Retrying automatically; your queue is preserved.";
    startPolling();
    return;
  }
  $("connection-status").textContent = "";

  const list = $("jobs");
  list.replaceChildren();
  const jobs = data.jobs;

  for (const job of jobs) list.appendChild(renderJob(job));

  $("empty").style.display = jobs.length ? "none" : "block";

  const running = jobs.filter(j => j.state === "running").length;
  const queued = jobs.filter(j => j.state === "queued").length;
  const done = jobs.filter(j => j.state === "done").length;
  const failed = jobs.filter(j => j.state === "error").length;
  const summary = jobs.length ? `${queued} queued · ${running} running · ${done} done · ${failed} failed` : "Ready to connect";
  if ($("summary").textContent !== summary) $("summary").textContent = summary;
  $("cancelAll").disabled = running + queued === 0;

  // Stop polling once nothing is in flight.
  if (running + queued > 0) startPolling();
  if (running + queued === 0 && pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  if (!pollTimer) pollTimer = setInterval(poll, 700);
}

async function submit() {
  if ($("go").disabled) return;
  const url = $("url").value.trim();
  if (!url) {
    $("source-error").textContent = "Paste a music link or enter a search to connect.";
    $("url").setAttribute("aria-invalid", "true");
    $("url").focus(); return;
  }
  $("source-error").textContent = "";
  $("url").removeAttribute("aria-invalid");
  $("go").disabled = true;
  try {
    await api("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        quality: $("quality").value,
        embed_metadata: $("meta").checked,
        embed_thumbnail: $("art").checked,
      }),
    });
    $("url").value = "";
    startPolling();
    poll();
  } catch (e) {
    $("source-error").textContent = "Could not start: " + e.message + ". Your source is preserved; try again.";
  } finally {
    $("go").disabled = false;
  }
}

async function cancelAll() {
  if ($("cancelAll").disabled) return;
  $("cancelAll").disabled = true;
  try {
    await api("/api/jobs", { method: "DELETE" });
    await poll();
  } catch (e) {
    $("connection-status").textContent = "Could not stop transfers: " + e.message + ". Try again.";
    $("cancelAll").disabled = false;
  }
}

async function clearFinished() {
  if ($("clear").disabled) return;
  $("clear").disabled = true;
  try {
    await api("/api/jobs/finished", { method: "DELETE" });
    await poll();
  } catch (e) {
    $("connection-status").textContent = "Could not clear finished transfers: " + e.message + ". Try again.";
  } finally {
    $("clear").disabled = false;
  }
}

async function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  updateThemeLabel();
  try {
    await api("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: next }),
    });
  } catch (e) { /* theme is cosmetic; ignore persistence failure */ }
}

$("go").addEventListener("click", submit);
$("url").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.repeat && !e.isComposing) {
    e.preventDefault();
    submit();
  }
});
document.addEventListener("keydown", (e) => {
  if (e.defaultPrevented || e.repeat || e.isComposing || e.altKey || e.shiftKey) return;
  const modifier = e.ctrlKey || e.metaKey;
  const key = e.key.toLowerCase();
  if (modifier && key === "l") {
    e.preventDefault(); $("url").focus(); $("url").select();
  } else if (modifier && key === "enter") {
    e.preventDefault(); submit();
  } else if (modifier && key === "t") {
    e.preventDefault(); toggleTheme();
  } else if (!modifier && key === "escape" && !$("cancelAll").disabled) {
    e.preventDefault(); cancelAll();
  }
});
$("cancelAll").addEventListener("click", cancelAll);
$("clear").addEventListener("click", clearFinished);
$("themeBtn").addEventListener("click", toggleTheme);

(async function boot() {
  try {
    const h = await api("/api/health");
    $("ytdlp").textContent = h.yt_dlp;
    const ff = $("ffmpeg");
    ff.textContent = h.ffmpeg ? "ok" : "missing";
    if (!h.ffmpeg) ff.className = "no";
    $("outdir").textContent = "Configured local folder";
  } catch (e) { /* first paint still works */ }
  poll();
})();
</script>
</body>
</html>
"""


def render(mode: str = "dark") -> str:
    """Fill the template with a palette. Callers pass 'dark' or 'light'."""
    p = DARK if mode == "dark" else LIGHT
    replacements = {
        "__MODE__": mode,
        "__BG_TOP__": p.bg_top,
        "__BG_BOTTOM__": p.bg_bottom,
        "__SURFACE__": p.surface,
        "__SURFACE_ALT__": p.surface_alt,
        "__BORDER__": p.border,
        "__BORDER_STRONG__": p.border_strong,
        "__TEXT__": p.text,
        "__TEXT_DIM__": p.text_dim,
        "__TEXT_FAINT__": p.text_faint,
        "__ACCENT__": p.accent,
        "__ACCENT_HOVER__": p.accent_hover,
        "__ACCENT_PRESS__": p.accent_press,
        "__ACCENT_TEXT__": p.accent_text,
        "__SIGNAL__": p.signal,
        "__OK__": p.ok,
        "__WARN__": p.warn,
        "__ERR__": p.err,
        "__TRACK__": p.track,
    }
    # Both palettes are present in CSS, so a data-theme change repaints immediately.
    # A single initial :root palette would make the toggle change only its label.
    css = []
    for palette in (DARK, LIGHT):
        declarations = ";".join(
            f"--{key.replace('_', '-')}: {value}"
            for key, value in palette.__dict__.items() if key not in ("name", "glow")
        )
        css.append(f'[data-theme="{palette.name}"] {{{declarations};}}')
    replacements["__PALETTE_OVERRIDES__"] = "\n".join(css)
    out = _TEMPLATE
    for key, value in replacements.items():
        out = out.replace(key, value)
    return out


DASHBOARD_HTML = render("dark")
