"""Offline browser redesign contracts; never invoke the download engine."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from elilain_music.web.assets import render

main = import_module("elilain_music.web.main")


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def css_rule(html, selector):
    style = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    return re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]+)\}", style).group(1)


def test_user_artwork_preserves_full_composition():
    html = render()
    images = [attrs for tag, attrs in Document(html).tags if tag == "img"]
    assert {image["src"] for image in images} == {
        "/art/lain.png", "/art/wired-city.png", "/art/wired-banner.png"
    }
    assert "object-fit: contain" in css_rule(html, ".portrait img")
    assert "aspect-ratio: 1" in css_rule(html, ".portrait img")
    assert "object-fit: contain" in css_rule(html, ".wired-banner img")
    assert "734 / 241" in css_rule(html, ".wired-banner img")
    assert "user-supplied fan artwork" in html.lower()
    assert "official series site" not in html.lower()


def test_banner_route_is_allowlisted_without_opening_arbitrary_files(tmp_path, monkeypatch):
    # Temporary files isolate routing from concurrent replacement of user artwork.
    banner = b"\x89PNG\r\n\x1a\nlocal-banner"
    (tmp_path / "wired-banner.png").write_bytes(banner)
    (tmp_path / "private.txt").write_text("not public", encoding="utf-8")
    monkeypatch.setattr(main, "ART_DIR", tmp_path)
    with TestClient(main.create_app()) as client:
        response = client.get("/art/wired-banner.png")
        assert response.status_code == 200
        assert response.content == banner
        assert response.headers["content-type"] == "image/png"
        assert client.get("/art/private.txt").status_code == 404
        assert client.get("/art/lain.png").status_code == 404
        assert client.get("/art/%2e%2e%2fprivate.txt").status_code == 404


def test_wired_controls_have_shared_tokens_tactile_states_and_reflow():
    html = render()
    assert "--radius: 6px" in html
    assert "border-radius: 14px" in css_rule(html, ".card")
    assert "min-height: 40px" in css_rule(html, "button")
    assert "inset" in css_rule(html, "button")
    assert "var(--surface-alt)" in css_rule(html, "button.ghost")
    assert css_rule(html, "button.ghost:active:not(:disabled)")
    assert "var(--signal)" in css_rule(html, "kbd")
    assert "border-bottom" in css_rule(html, "kbd")
    assert "minmax(0, 1fr)" in html
    assert "font-size: 16px" in html
    assert "transition: width" not in html
    assert '@media (prefers-reduced-motion: no-preference)' in html
    assert "data-motion=\"on\"" in html
    assert '<h1>EliLain-Music</h1>' in html
    assert '<label for="url"' in html
    assert 'id="url-help"' in html
    assert 'aria-describedby="url-help source-error"' in html
    assert 'id="source-error" role="alert"' in html
    assert 'id="connection-status" role="status"' in html
    assert '<a class="skip-link" href="#source">' in html
    assert not re.search(r"https?://", html)
    from elilain_music.gui.theme import DARK, LIGHT
    for mode, palette in (("dark", DARK), ("light", LIGHT)):
        themed = render(mode)
        assert f'--accent: {palette.accent}' in themed
        assert f'--text-dim: {palette.text_dim}' in themed


# Execute the actual rendered script. Only browser/transport boundaries are faked;
# this deliberately cannot create jobs or contact a network download source.
NODE_DOM = r'''
const assert = require("node:assert/strict");
const vm = require("node:vm");
const input = JSON.parse(require("node:fs").readFileSync(0, "utf8"));
const nodes = new Map();
const handlers = new Map();
let active = null;
let requests = [];
let jobs = [];
let failDownload = false;
let failJobs = false;
let failAction = false;
let storageBlocked = false;
let holdDownload = false;
let releaseDownload;
const store = new Map();
const el = id => nodes.get(id);
function element(attrs = {}) {
  return {
    attrs: {...attrs}, dataset: {}, style: {}, children: [], textContent: "",
    value: attrs.value || "", checked: "checked" in attrs, disabled: "disabled" in attrs,
    setAttribute(k,v) { this.attrs[k] = String(v); },
    getAttribute(k) { return this.attrs[k] ?? null; },
    removeAttribute(k) { delete this.attrs[k]; },
    focus() { active = this; }, select() { this.selected = true; },
    addEventListener(k, cb) { this[k] = cb; },
    append(...items) { this.children.push(...items); },
    appendChild(item) { this.children.push(item); },
    replaceChildren(...items) { this.children = items; },
  };
}
for (const attrs of input.nodes) nodes.set(attrs.id, element(attrs));
el("quality").value = "high";
global.document = {
  documentElement: { dataset: { theme: "dark" } },
  getElementById: el, createElement: () => element(),
  addEventListener: (name, cb) => handlers.set(name, cb),
};
global.localStorage = {
  getItem(k) { if(storageBlocked) throw Error("blocked"); return store.get(k) || null; },
  setItem(k,v) { if(storageBlocked) throw Error("blocked"); store.set(k,v); },
};
global.fetch = async (path, options = {}) => {
  requests.push({path, ...options});
  if (path === "/api/download" && holdDownload) await new Promise(resolve => releaseDownload = resolve);
  if ((path === "/api/download" && failDownload) || (path === "/api/jobs" && failJobs) || (options.method === "DELETE" && failAction)) {
    return {ok:false, text:async () => JSON.stringify({detail:"Local service unavailable <unsafe>"})};
  }
  const payload = path === "/api/health" ? {yt_dlp:"offline-test",ffmpeg:true}
    : path === "/api/jobs" ? {jobs}
    : path === "/api/theme" ? {theme:JSON.parse(options.body).mode} : {};
  return {ok:true, json:async () => payload};
};
global.setInterval = () => 1;
global.clearInterval = () => {};
global.alert = () => { throw Error("Blocking browser alerts are not accessible inline errors"); };
const tick = () => new Promise(resolve => setImmediate(resolve));
function key(key, ctrlKey=false, extra={}) {
  const event = {key,ctrlKey,metaKey:false,altKey:false,shiftKey:false,repeat:false,isComposing:false,
    defaultPrevented:false, preventDefault() { this.defaultPrevented=true; },...extra};
  if (handlers.get("keydown")) handlers.get("keydown")(event);
  return event;
}
vm.runInThisContext(input.script);
(async () => {
  await tick();
  requests = [];
  await vm.runInThisContext("(async () => {" + input.check + "})()");
  console.log("actual dashboard JavaScript assertions passed");
})().catch(error => { console.error(error.stack); process.exitCode=1; });
'''


def run_dashboard_js(check):
    html = render()
    payload = {
        "nodes": [attrs for _, attrs in Document(html).tags if "id" in attrs],
        "script": re.search(r"<script>(.*?)</script>", html, re.S).group(1),
        "check": check,
    }
    node = shutil.which("node")
    assert node, "Node is required to exercise dashboard JavaScript offline"
    result = subprocess.run([node, "-e", NODE_DOM], input=json.dumps(payload),
                            text=True, capture_output=True, timeout=15, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "assertions passed" in result.stdout


def test_shortcuts_run_once_preserve_keycaps_and_respect_disabled_state():
    run_dashboard_js(r'''
      assert.equal(key("l",true).defaultPrevented,true);
      assert.equal(active,el("url"));
      assert.equal(el("url").selected,true);
      key("t",true); await tick();
      assert.equal(document.documentElement.dataset.theme,"light");
      assert.equal(el("theme-label").textContent,"Wired");
      assert.match(el("themeBtn").getAttribute("aria-label"),/Wired.*dark/);
      assert.equal(JSON.parse(requests.find(r => r.path === "/api/theme").body).mode,"light");
      storageBlocked = true;
      el("motionToggle").checked = true;
      el("motionToggle").change();
      assert.equal(document.documentElement.dataset.motion,"on");
      key("t",true); await tick();
      assert.equal(document.documentElement.dataset.theme,"dark");
      requests = [];
      key("Escape"); await tick();
      assert.equal(requests.length,0);
      el("cancelAll").disabled=false;
      assert.equal(key("Escape").defaultPrevented,true); await tick();
      assert.equal(requests.filter(r => r.method === "DELETE").length,1);
      requests = [];
      el("url").value="offline search";
      holdDownload=true;
      key("Enter",true); await tick();
      assert.equal(el("go").disabled,true);
      key("Enter",true); key("Enter",true,{repeat:true}); await tick();
      assert.equal(requests.filter(r => r.path === "/api/download").length,1);
      const request=JSON.parse(requests.find(r => r.path === "/api/download").body);
      assert.deepEqual(request,{url:"offline search",quality:"high",embed_metadata:true,embed_thumbnail:true});
      releaseDownload(); await tick();
      assert.equal(el("go").disabled,false);
      assert.equal(el("url").value,"");
      assert.equal(key("l",true,{isComposing:true}).defaultPrevented,false);
      assert.equal(key("t",true,{altKey:true}).defaultPrevented,false);
    ''')


def test_inline_errors_keep_input_and_recover_without_unsafe_html():
    run_dashboard_js(r'''
      await submit();
      assert.equal(el("url").getAttribute("aria-invalid"),"true");
      assert.match(el("source-error").textContent,/link.*search/i);
      assert.equal(active,el("url"));
      assert.equal(requests.length,0);
      failDownload=true;
      el("url").value="preserved source";
      await submit();
      assert.match(el("source-error").textContent,/Could not start: Local service unavailable <unsafe>/);
      assert.equal(el("url").value,"preserved source");
      assert.equal(el("go").disabled,false);
      failDownload=false;
      await submit(); await tick();
      assert.equal(el("source-error").textContent,"");
      assert.equal(el("url").getAttribute("aria-invalid"),null);
      failJobs=true;
      await poll();
      assert.match(el("connection-status").textContent,/reconnect|retry/i);
      assert.notEqual(pollTimer,null);
      failJobs=false;
      await poll();
      assert.equal(el("connection-status").textContent,"");
      failAction=true;
      await clearFinished();
      assert.match(el("connection-status").textContent,/Could not clear/);
      el("cancelAll").disabled=false;
      await cancelAll();
      assert.match(el("connection-status").textContent,/Could not stop/);
      assert.equal(el("cancelAll").disabled,false);
    ''')
    html = render()
    assert not re.search(r"\.(?:innerHTML|outerHTML)\s*\+?=", html)
    assert "document.write" not in html
    assert "alert(" not in html


def test_queued_jobs_keep_polling_and_expose_accessible_progress():
    run_dashboard_js(r'''
      const job = {label:"<img src=x onerror=alert(1)>",url:"offline",quality:"high",
        state:"queued",percent:125,status_text:"Queued",files:[],path:"",error:""};
      jobs=[job];
      startPolling();
      await poll();
      assert.notEqual(pollTimer,null);
      assert.equal(el("cancelAll").disabled,false);
      assert.match(el("summary").textContent,/1 queued/);
      const row=el("jobs").children[0];
      assert.equal(row.children[0].textContent,job.label);
      const bar=row.children[2];
      assert.equal(bar.getAttribute("role"),"progressbar");
      assert.equal(bar.getAttribute("aria-valuenow"),"100");
      assert.equal(bar.getAttribute("aria-valuemin"),"0");
      assert.equal(bar.getAttribute("aria-valuemax"),"100");
      assert.match(bar.getAttribute("aria-label"),/Transfer progress/);
      assert.equal(bar.children[0].style.width,"100%");
      jobs=[];
      await poll();
      assert.equal(pollTimer,null);
      assert.equal(el("empty").style.display,"block");
      assert.equal(el("summary").textContent,"Ready to connect");
      assert.equal(el("cancelAll").disabled,true);
      assert.equal(el("outdir").textContent,"Configured local folder");
    ''')


@pytest.fixture(scope="module")
def chromium(tmp_path_factory):
    """Optional real Chromium checks, isolated profile and loopback-only app."""
    import os
    import socket
    import threading
    import time
    from pathlib import Path
    from unittest.mock import patch
    from urllib.request import urlopen

    import uvicorn

    websocket = pytest.importorskip("websocket")
    candidates = [os.environ.get("ELILAIN_TEST_CHROMIUM", ""),
                  shutil.which("chromium") or "", shutil.which("google-chrome") or "",
                  str(Path.home() / "AppData/Local/hermes/tools/chromium-1208/chrome-win64/chrome.exe")]
    binary = next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)
    if binary is None:
        pytest.skip("Set ELILAIN_TEST_CHROMIUM to run real-browser checks")
    directory = tmp_path_factory.mktemp("chromium-redesign")

    class MemorySettings:
        def get(self, key):
            return {"theme": "dark", "output_dir": str(directory / "music")}.get(key, "")

        def set(self, *args):
            pass

        def save(self):
            pass

    with patch.object(main, "Settings", MemorySettings):
        app = main.create_app()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="off", ws="none"))
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    process = subprocess.Popen([binary, "--headless=new", "--disable-gpu", "--no-first-run",
                                "--disable-background-networking", "--disable-default-apps",
                                "--remote-debugging-port=0", "--remote-allow-origins=*",
                                "--no-proxy-server", f"--user-data-dir={directory / 'profile'}", "about:blank"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        deadline = time.monotonic() + 25
        debug_file = directory / "profile/DevToolsActivePort"
        while not debug_file.is_file() or not server.started:
            assert process.poll() is None, "Chromium exited during startup"
            assert time.monotonic() < deadline, "Loopback browser/server startup timed out"
            time.sleep(.1)
        debug_port = int(debug_file.read_text().splitlines()[0])
        with urlopen(f"http://127.0.0.1:{debug_port}/json/list") as response:
            targets = json.load(response)
        target = next(target for target in targets if target["type"] == "page")
        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10)

        class Browser:
            seq = 0
            events = []
            artifacts = directory

            def call(self, method, **params):
                self.seq += 1
                ws.send(json.dumps({"id": self.seq, "method": method, "params": params}))
                while True:
                    message = json.loads(ws.recv())
                    if message.get("id") == self.seq:
                        assert "error" not in message, message
                        return message.get("result", {})
                    self.events.append(message)

            def evaluate(self, expression):
                result = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
                assert "exceptionDetails" not in result, result
                return result.get("result", {}).get("value")

        browser = Browser()
        browser.call("Page.enable")
        browser.call("Runtime.enable")
        browser.call("Network.enable")
        browser.call("Page.navigate", url=f"http://127.0.0.1:{port}/")
        while not browser.evaluate("document.readyState === 'complete' && document.getElementById('summary') !== null"):
            assert time.monotonic() < deadline, "Dashboard load timed out"
            time.sleep(.1)
        browser.evaluate("poll()")
        yield browser
    finally:
        if ws is not None:
            ws.close()
        process.terminate()
        process.wait(timeout=10)
        server.should_exit = True
        worker.join(timeout=10)


def test_real_browser_reflows_both_modes_without_cropping_or_motion(chromium):
    browser = chromium
    records = []
    for mode in ("dark", "light"):
        browser.evaluate(f"document.documentElement.dataset.theme = {json.dumps(mode)}")
        for width in (320, 390, 768, 1280):
            browser.call("Emulation.setDeviceMetricsOverride", width=width, height=1000, deviceScaleFactor=1, mobile=False)
            data = browser.evaluate(r'''(() => {
              const style = selector => getComputedStyle(document.querySelector(selector));
              return {
                width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                controls: [...document.querySelectorAll('button, input[type=text], select')].map(el => el.getBoundingClientRect().height),
                images: [...document.images].map(el => ({src:el.getAttribute('src'),loaded:el.complete && el.naturalWidth>0})),
                portraitFit: style('.portrait img').objectFit,
                portraitRatio: style('.portrait img').aspectRatio,
                bannerFit: style('.wired-banner img').objectFit,
                footerInMain: !!document.querySelector('main .shortcuts'),
                animation: getComputedStyle(document.querySelector('.portrait'),'::before').animationName,
                inputSize: style('#url').fontSize,
                keycaps: document.querySelectorAll('button kbd').length,
              };
            })()''')
            records.append({"mode": mode, **data})
            assert data["scrollWidth"] <= width, data
            assert min(data["controls"]) >= 40, data
            assert all(image["loaded"] for image in data["images"]), data
            assert data["portraitFit"] == data["bannerFit"] == "contain", data
            assert data["portraitRatio"] == "1 / 1", data
            assert data["footerInMain"], data
            assert data["animation"] == "none", data
            assert data["keycaps"] == 3, data
            if width < 700:
                assert data["inputSize"] == "16px", data
    browser.evaluate("document.getElementById('motionToggle').checked=true; setMotion()")
    browser.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"}])
    assert browser.evaluate("getComputedStyle(document.querySelector('.portrait'),'::before').animationName") == "none"
    browser.call("Emulation.setEmulatedMedia", features=[])
    browser.evaluate("document.getElementById('motionToggle').checked=false; setMotion(); document.documentElement.dataset.theme='dark'")
    assert not [event for event in browser.events if event.get("method") == "Runtime.exceptionThrown"]
    requests = [event["params"]["request"]["url"] for event in browser.events if event.get("method") == "Network.requestWillBeSent"]
    assert all(url.startswith("http://127.0.0.1:") for url in requests), requests
    print("\nChromium reflow records:", json.dumps(records))


def test_real_browser_keyboard_states_long_errors_and_artwork_snapshots(chromium):
    import base64
    browser = chromium
    # Real keyboard events enter the page via CDP; all service writes are mocked.
    browser.evaluate(r'''window.__requests=[]; window.__originalFetch=window.fetch;
      window.fetch=async (path,opts={}) => {
        window.__requests.push({path,method:opts.method||'GET',body:opts.body});
        if(path==='/api/download') return {ok:false,text:async()=>JSON.stringify({detail:'Offline test error <img src=x>'})};
        if(path==='/api/theme') return {ok:true,json:async()=>({theme:JSON.parse(opts.body).mode})};
        return window.__originalFetch(path,opts);
      };''')
    def press(key, code, virtual, modifiers=0):
        browser.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=code,
                     windowsVirtualKeyCode=virtual, modifiers=modifiers)
        browser.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code,
                     windowsVirtualKeyCode=virtual, modifiers=modifiers)

    press("l", "KeyL", 76, 2)
    assert browser.evaluate("document.activeElement.id") == "url"
    press("t", "KeyT", 84, 2)
    assert browser.evaluate("document.documentElement.dataset.theme") == "light"
    assert browser.evaluate("document.querySelector('#themeBtn kbd') !== null")
    assert browser.evaluate("document.getElementById('theme-label').textContent") == "Wired"
    browser.evaluate("document.getElementById('url').value='offline test search'")
    press("Enter", "Enter", 13, 2)
    assert browser.evaluate("new Promise(resolve => setTimeout(() => resolve(document.getElementById('source-error').textContent),100))").startswith("Could not start: Offline test error <img src=x>")
    assert not browser.evaluate("document.querySelector('#source-error img') !== null")
    assert browser.evaluate("document.getElementById('url').value") == "offline test search"
    assert browser.evaluate("document.querySelectorAll('button kbd').length") == 3
    press("Escape", "Escape", 27)
    assert not browser.evaluate("window.__requests.some(request => request.method === 'DELETE')")
    # Error/path strings must reflow, never get clipped into unreadable ellipses.
    browser.evaluate(r'''document.getElementById('jobs').appendChild(renderJob({
      label:'Long source '+ 'x'.repeat(180),url:'offline',state:'error',status_text:'Failed',
      percent:0,quality:'high',files:[],path:'',error:'Recoverable error '+ 'x'.repeat(300)}));''')
    for width in (320,390,768,1280):
        browser.call("Emulation.setDeviceMetricsOverride", width=width, height=1000, deviceScaleFactor=1, mobile=False)
        assert browser.evaluate("document.documentElement.scrollWidth <= innerWidth")
    browser.call("DOM.enable")
    browser.call("CSS.enable")
    root = browser.call("DOM.getDocument")["root"]["nodeId"]
    go = browser.call("DOM.querySelector", nodeId=root, selector="#go")["nodeId"]
    from elilain_music.gui.theme import DARK, LIGHT
    for mode, palette in (("dark",DARK),("light",LIGHT)):
        browser.evaluate(f"document.documentElement.dataset.theme={json.dumps(mode)}; updateThemeLabel()")
        for state, color in (("hover",palette.accent_hover),("active",palette.accent_press)):
            browser.call("CSS.forcePseudoState", nodeId=go, forcedPseudoClasses=[state])
            actual = browser.evaluate("getComputedStyle(document.getElementById('go')).backgroundColor")
            expected = tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))
            assert actual == f"rgb({expected[0]}, {expected[1]}, {expected[2]})"
        browser.call("CSS.forcePseudoState", nodeId=go, forcedPseudoClasses=["focus-visible"])
        assert browser.evaluate("getComputedStyle(document.getElementById('go')).outlineWidth") == "2px"
        browser.call("CSS.forcePseudoState", nodeId=go, forcedPseudoClasses=[])
        browser.evaluate("document.getElementById('go').disabled=true")
        assert browser.evaluate("getComputedStyle(document.getElementById('go')).cursor") == "not-allowed"
        browser.evaluate("document.getElementById('go').disabled=false")
        # Empty and error screenshots share the original artwork without overlays.
        browser.evaluate("document.getElementById('jobs').replaceChildren(); document.getElementById('source-error').textContent=''; document.getElementById('url').value=''")
        for width in (390,1280):
            browser.call("Emulation.setDeviceMetricsOverride", width=width, height=1100, deviceScaleFactor=1, mobile=False)
            shot = browser.call("Page.captureScreenshot", format="png", captureBeyondViewport=True)
            path = browser.artifacts / f"{mode}-{width}.png"
            path.write_bytes(base64.b64decode(shot["data"]))
            print("\nBrowser screenshot:",path)
    browser.evaluate("window.fetch=window.__originalFetch")
    assert not [event for event in browser.events if event.get("method") == "Runtime.exceptionThrown"]
