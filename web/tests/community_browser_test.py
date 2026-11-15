"""T129 regression checks: real community API + DOM, deterministic map/viewer adapters, no external services.

Run: python web/tests/community_browser_test.py
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

REPO = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] == "/web/community-test.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b'<html><head><link rel="stylesheet" href="/web/style.css"></head><body>'
                             b'<header class="app-header"><h1 class="brand">SPHEREx Blink</h1><nav class="workspace-tabs" role="tablist" aria-label="Workspace">'
                             b'<button id="workspace-explore" role="tab" aria-selected="true">Explore</button>'
                             b'<button id="workspace-community" role="tab" aria-selected="false">Community</button></nav></header>'
                             b'<div id="explore-workspace"><div id="explore"><div id="sky" style="width:800px;height:600px"></div>'
                             b'<div class="hud-row"><label><input type="checkbox" id="labels-toggle">Labels</label></div></div>'
                             b'<input type="checkbox" id="flags-toggle"></div>'
                             b'<script type="module" src="/web/community.js"></script>'
                             b'<script type="module" src="/web/community-coverage.js"></script></body></html>')
        else:
            super().do_GET()

    def log_message(self, *args):
        pass


def run():
    with tempfile.TemporaryDirectory(prefix="community-test-") as tmp:
        screenshots = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tmp)
        screenshots.mkdir(parents=True, exist_ok=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            api_port = sock.getsockname()[1]
        api = f"http://127.0.0.1:{api_port}"
        web = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(REPO)))
        threading.Thread(target=web.serve_forever, daemon=True).start()
        origin = f"http://127.0.0.1:{web.server_port}"
        env = dict(os.environ, PYTHONPATH=str(REPO))
        with open(Path(tmp) / "api.log", "w") as log:
            proc = subprocess.Popen([sys.executable, "-m", "server", "--fixture", "--port", str(api_port),
                                     "--cache", str(Path(tmp) / "targets"), "--tiles-remote", "none"],
                                    cwd=tmp, env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(api + "/api/health", timeout=1)
                        break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise AssertionError("test API did not start")
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("requestfailed", lambda request: print("REQUEST FAILED", request.url, request.failure))
                    page.on("console", lambda msg: print("BROWSER", msg.text) if msg.type == "error" else None)
                    # Keep map navigation deterministic while exercising the real DOM, drafts, network and SQLite.
                    page.route("**/web/explore.js", lambda route: route.fulfill(content_type="text/javascript", body=f'''
                      let v = {{ra: 150, dec: 2.2, fovArcmin: 15}};
                      const changes = [], hooks = [], canvas = document.createElement("canvas");
                      canvas.width = 800; canvas.height = 600;
                      const ctx = canvas.getContext("2d"), stroke = ctx.stroke.bind(ctx);
                      window.coverageStrokes = 0;
                      ctx.stroke = () => {{ window.coverageStrokes++; stroke(); }};
                      const sky = {{on: (event, fn) => changes.push(fn), base: {{slice: 0}},
                        addDrawHook: fn => hooks.push(fn), proj: {{
                          fromScreen: (x,y) => [v.ra+(x/800-.5)*v.fovArcmin/60, v.dec+(y/600-.5)*v.fovArcmin/60],
                          toScreen: (ra,dec) => ({{x:(ra-v.ra)*60/v.fovArcmin*800+400,y:(dec-v.dec)*60/v.fovArcmin*600+300,front:true}})
                        }} }};
                      export const getApiBase = () => {json.dumps(api)};
                      export const view = () => v;
                      export const getSky = () => sky;
                      export const redraw = () => hooks.forEach(fn => fn(ctx, sky.proj));
                      export const goTo = (ra, dec, fov) => {{v = {{ra, dec, fovArcmin: (fov ?? .25) * 60}}; changes.forEach(fn => fn());}};
                      window.communityMove = goTo;
                      export const bandWavelengths = () => [1.2, 4.5];
                      export const setBand = i => window.restoredBand = i;
                      export const currentLayer = () => "f000";
                      export const showLayer = async key => {{window.restoredLayer = key; return true;}};
                    '''))
                    page.route("**/web/viewer.js", lambda route: route.fulfill(content_type="text/javascript", body='''
                      const a = {id: 'f000', time_utc: '2025-01-01T00:00:00Z', obs_id: 'obs-a'},
                            b = {id: 'f004', time_utc: '2025-07-01T00:00:00Z', obs_id: 'obs-b'};
                      export const currentTarget = () => ({id: 'saved-field', center: {ra_deg: 150, dec_deg: 2.2},
                        size_arcmin: 15, synthetic: true, frames: window.changedFrames ? [{...a, time_utc: '2026-01-01T00:00:00Z'}, b] : [a,b]});
                      export const currentPair = () => ({a,b});
                      export const selectPair = (a,b) => window.restoredPair = [a,b];
                      document.addEventListener('community:restore', e => e.detail.done(!window.failRestore));
                    '''))
                    url = origin + "/web/community-test.html"
                    page.goto(url)
                    page.locator("#community-btn").click()
                    expect(page.locator("#community-text")).to_be_visible()
                    pix = page.evaluate("spherexCommunity.tile()")
                    # Seed a real parent; use it to check separate root/reply drafts.
                    page.request.post(f"{api}/api/community/tiles/{pix}/comments", data={"author": "Ada", "text": "Can you help check this source?"}).json()["comment"]
                    page.get_by_role("button", name="This tile", exact=True).click()
                    page.locator("#community-text").fill("My original observation")
                    page.locator("#community-attach").uncheck()
                    page.locator("#community-text").focus()
                    expect(page.locator("#community-views")).to_have_text("👁 1 visits", timeout=7000)
                    expect(page.locator("#community-text")).to_have_value("My original observation")
                    expect(page.locator("#community-text")).to_be_focused()
                    page.get_by_role("button", name="Recent", exact=True).click()
                    page.get_by_role("button", name="This tile", exact=True).click()
                    expect(page.locator("#community-text")).to_have_value("My original observation")
                    expect(page.locator("#community-attach")).not_to_be_checked()
                    page.get_by_role("button", name="Reply", exact=True).click()
                    page.locator("#community-text").fill("Reply draft for Ada")
                    page.get_by_role("button", name="Cancel reply", exact=True).click()
                    expect(page.locator("#community-text")).to_have_value("My original observation")
                    page.get_by_role("button", name="Reply", exact=True).click()
                    expect(page.locator("#community-text")).to_have_value("Reply draft for Ada")
                    page.evaluate("communityMove(10, 0, .25)")
                    expect(page.locator("#community-text")).to_have_value("")
                    expect(page.locator("#community-kind")).to_be_visible()
                    page.locator("#community-text").fill("Other tile draft")
                    page.evaluate("communityMove(150, 2.2, .25)")
                    expect(page.locator("#community-text")).to_have_value("My original observation")
                    page.reload()
                    page.locator("#community-btn").click()
                    expect(page.locator("#community-text")).to_have_value("My original observation")
                    page.locator("#community-kind").select_option("second_look")
                    page.locator("#community-title").fill("<b>Is this moving?</b>")
                    expect(page.locator("#community-attach")).to_be_checked()
                    expect(page.locator("#community-attach")).to_be_disabled()
                    page.route("**/api/community/tiles/*/comments", lambda route: route.fulfill(status=429,
                               content_type="application/json", body='{"message":"Please try again"}'), times=1)
                    page.get_by_role("button", name="Post", exact=True).click()
                    expect(page.locator("#community-msg")).to_contain_text("Your draft is saved")
                    expect(page.locator("#community-text")).to_have_value("My original observation")
                    expect(page.get_by_role("button", name="Post", exact=True)).to_be_enabled()
                    page.get_by_role("button", name="Post", exact=True).click()
                    expect(page.locator("#community-text")).to_have_value("")
                    expect(page.get_by_role("button", name="Post", exact=True)).to_be_enabled()
                    expect(page.locator("h4", has_text="<b>Is this moving?</b>")).to_have_count(1)
                    assert page.locator("#community b").count() == 0, "title must be plain text"
                    expect(page.locator(".cm-evidence")).to_contain_text("SYNTHETIC")
                    posted = page.request.get(f"{api}/api/community/recent?unanswered=true").json()["latest"][0]
                    assert posted["evidence"]["frame_a_obs"] == "obs-a"
                    page.get_by_role("button", name="Unanswered", exact=True).click()
                    expect(page.get_by_role("button", name="Open discussion →")).to_have_count(1)
                    page.get_by_role("button", name="Open discussion →").click()
                    expect(page.locator(f"#cm-comment-{posted['id']}")).to_have_class("cm-item cm-highlight")
                    # A direct link reopens the actual comment and restores available evidence.
                    page.goto(f"{url}?community={pix}&comment={posted['id']}")
                    expect(page.locator(f"#cm-comment-{posted['id']}")).to_be_visible()
                    page.wait_for_function("window.restoredPair?.join(',') === 'f000,f004'")
                    assert page.evaluate("window.restoredLayer") == "f000"
                    page.locator("#community-coverage-toggle").check()
                    expect(page.locator("#community-coverage-note")).to_contain_text("gray = unvisited")
                    page.wait_for_function("window.coverageStrokes > 0")
                    page.evaluate("communityMove(150, 2.2, 12)")
                    expect(page.locator("#community-coverage-note")).to_contain_text("Zoom in")
                    page.evaluate("communityMove(150, 2.2, .25)")
                    expect(page.locator("#community-coverage-note")).to_contain_text("gray = unvisited")
                    page.locator("#community-coverage-toggle").uncheck()
                    expect(page.locator("#community-coverage-note")).to_be_hidden()
                    page.get_by_role("button", name="Coverage", exact=True).click()
                    expect(page.locator(".cm-coverage-card")).to_have_count(4)
                    target_tile = page.locator(".cm-coverage-list .cm-item").first.locator("strong").text_content()
                    page.locator(".cm-coverage-list .cm-item").first.get_by_role("button", name="View on map →", exact=True).click()
                    expect(page.locator("#community h3")).to_have_text(target_tile)
                    page.goto(f"{url}?community={pix}&comment={posted['id']}")
                    expect(page.locator(f"#cm-comment-{posted['id']}")).to_be_visible()
                    page.evaluate("window.changedFrames = true; window.restoredPair = null; window.restoredLayer = null")
                    page.get_by_role("button", name="Open saved evidence").click()
                    expect(page.locator("#community")).to_contain_text("saved frames are unavailable")
                    assert page.evaluate("window.restoredPair") is None
                    assert page.evaluate("window.restoredLayer") is None
                    page.evaluate("window.changedFrames = false; window.failRestore = true")
                    page.get_by_role("button", name="Open saved evidence").click()
                    expect(page.locator("#community")).to_contain_text("saved field is no longer available")
                    # Reply from the DOM clears the unanswered request, without clearing another draft.
                    page.locator(f"#cm-comment-{posted['id']}").get_by_role("button", name="Reply", exact=True).click()
                    page.locator("#community-text").fill("I checked both observations.")
                    page.locator(".cm-form").get_by_role("button", name="Reply", exact=True).click()
                    expect(page.locator(".cm-reply")).to_have_count(1)
                    page.get_by_role("button", name="Unanswered", exact=True).click()
                    expect(page.locator("#community")).to_contain_text("No unanswered requests")
                    # A delayed success stays bound to the original tile and leaves a new tile's composer intact.
                    page.get_by_role("button", name="This tile", exact=True).click()
                    page.locator("#community-text").fill("Posted on the original tile")
                    pending = []
                    page.route("**/api/community/tiles/*/comments", lambda route: pending.append(route), times=1)
                    page.get_by_role("button", name="Post", exact=True).click()
                    page.wait_for_timeout(100)
                    assert len(pending) == 1
                    original_url = pending[0].request.url
                    page.evaluate("communityMove(10, 0, .25)")
                    expect(page.locator("#community-text")).to_have_value("Other tile draft")
                    page.locator("#community-text").fill("Keep this newer draft")
                    pending[0].continue_()
                    page.wait_for_timeout(300)
                    assert original_url.endswith(f"/{pix}/comments")
                    expect(page.locator("#community-text")).to_have_value("Keep this newer draft")
                    # Hidden map time while browsing Community must not inflate coverage.
                    page.evaluate("communityMove(40, 60, .25)")
                    hidden_pix = page.evaluate("spherexCommunity.tile()")
                    page.get_by_role("tab", name="Community", exact=True).click()
                    expect(page.get_by_role("tab", name="Community", exact=True)).to_have_attribute("aria-selected", "true")
                    page.wait_for_timeout(4200)  # longer than the 4-second map view-count dwell
                    assert page.request.get(f"{api}/api/community/tiles/{hidden_pix}").json()["views"] == 0
                    page.get_by_role("tab", name="Explore", exact=True).click()
                    page.locator("#community-btn").click()
                    expect(page.locator("#community-text")).to_be_visible()
                    # Narrow screen layout and Escape from inside the composer.
                    page.set_viewport_size({"width": 390, "height": 844})
                    assert page.locator("#community").bounding_box()["width"] <= 390
                    page.locator("#community-text").focus()
                    page.keyboard.press("Escape")
                    expect(page.locator("#community")).to_be_hidden()
                    assert not errors, errors
                    # Exercise the real app's saved-field handler too, without external sky-map services.
                    result = page.request.get(f"{api}/api/target?ra=150&dec=2.2&size=15").json()
                    for _ in range(100):
                        if result["status"] != "building":
                            break
                        time.sleep(0.05)
                        result = page.request.get(api + result["poll_url"]).json()
                    assert result["status"] == "ready"
                    app_page = browser.new_page()
                    app_page.on("pageerror", lambda error: errors.append(str(error)))
                    app_page.goto(f"{origin}/web/?explore=0&api={api}")
                    app_page.wait_for_function("document.querySelector('#source-info').textContent.includes('Live API')")
                    restored = app_page.evaluate("id => new Promise(done => document.dispatchEvent(new CustomEvent('community:restore', {detail: {targetId: id, done}})))", result["id"])
                    assert restored is True, "normal application must restore cached fields"
                    expect(app_page.locator("#viewer-body")).to_be_visible()
                    missing = app_page.evaluate("() => new Promise(done => document.dispatchEvent(new CustomEvent('community:restore', {detail: {targetId: 'missing-field', done}})))")
                    assert missing is False
                    # Dedicated Community navigation works before a map is available, preserving the loaded field.
                    field_name = app_page.locator("#target-name").text_content()
                    app_page.get_by_role("tab", name="Community", exact=True).click()
                    expect(app_page.get_by_role("tab", name="Community", exact=True)).to_have_attribute("aria-selected", "true")
                    expect(app_page.locator("#community")).to_have_attribute("role", "tabpanel")
                    assert app_page.locator("#explore-workspace").evaluate("node => node.inert") is True
                    assert "view=community" in app_page.url
                    app_page.get_by_role("button", name="Coverage", exact=True).click()
                    expect(app_page.locator(".cm-coverage-card")).to_have_count(4)
                    expect(app_page.locator(".cm-coverage-list .cm-item")).to_have_count(24)
                    expect(app_page.locator("#community")).to_contain_text("do not measure the chance")
                    app_page.locator("#community-coverage-sort").select_option("most")
                    expect(app_page.locator(".cm-coverage-list .cm-item").first).to_contain_text("1 browser")
                    app_page.locator(".cm-coverage-list .cm-item").first.get_by_role("button", name="Discuss tile").click()
                    expect(app_page.locator("#community-tile-coverage")).to_contain_text("Light attention")
                    app_page.locator("#community-text").fill("Community workspace draft")
                    app_page.get_by_role("tab", name="Explore", exact=True).click()
                    expect(app_page.locator("#target-name")).to_have_text(field_name)
                    app_page.go_back()
                    expect(app_page.get_by_role("tab", name="Community", exact=True)).to_have_attribute("aria-selected", "true")
                    app_page.go_forward()
                    expect(app_page.get_by_role("tab", name="Explore", exact=True)).to_have_attribute("aria-selected", "true")
                    expect(app_page.locator("#target-name")).to_have_text(field_name)
                    # Arrow navigation changes workspace without triggering viewer shortcuts.
                    app_page.get_by_role("tab", name="Explore", exact=True).focus()
                    app_page.keyboard.press("ArrowRight")
                    expect(app_page.get_by_role("tab", name="Community", exact=True)).to_be_focused()
                    app_page.get_by_role("button", name="Coverage", exact=True).click()
                    app_page.locator("#community-coverage-sort").select_option("most")
                    app_page.locator(".cm-coverage-list .cm-item").first.get_by_role("button", name="Discuss tile").click()
                    expect(app_page.locator("#community-text")).to_have_value("Community workspace draft")
                    app_page.set_viewport_size({"width": 390, "height": 844})
                    app_page.screenshot(path=str(screenshots / "community-before-mobile-check.png"))
                    assert app_page.evaluate("document.documentElement.scrollWidth") <= 390, app_page.evaluate("[...document.querySelectorAll('body *')].filter(n=>n.getBoundingClientRect().right>390).map(n=>[n.tagName,n.id,n.className,n.getBoundingClientRect().width]).slice(0,20)")
                    app_page.get_by_role("button", name="Recent", exact=True).click()
                    expect(app_page.get_by_role("heading", name="Recent discussions", exact=True)).to_be_visible()
                    app_page.screenshot(path=str(screenshots / "community-mobile.png"))
                    app_page.get_by_role("button", name="Coverage", exact=True).click()
                    expect(app_page.locator(".cm-coverage-card")).to_have_count(4)
                    app_page.screenshot(path=str(screenshots / "community-coverage-mobile.png"))
                    app_page.reload()
                    expect(app_page.get_by_role("tab", name="Community", exact=True)).to_have_attribute("aria-selected", "true")
                    expect(app_page.locator("#community")).to_contain_text("Recent discussions")
                    # New shared links land in the separate workspace and focus the exact comment.
                    app_page.goto(f"{origin}/web/?explore=0&api={api}&view=community&community={pix}&comment={posted['id']}")
                    expect(app_page.locator(f"#cm-comment-{posted['id']}")).to_be_visible()
                    expect(app_page.get_by_role("tab", name="Community", exact=True)).to_have_attribute("aria-selected", "true")
                    app_page.set_viewport_size({"width": 320, "height": 700})
                    expect(app_page.get_by_role("tab", name="Community", exact=True)).to_be_visible()
                    app_page.wait_for_function("document.documentElement.scrollWidth <= innerWidth")
                    assert not errors, errors
                    browser.close()
                    print("Community browser checks passed: drafts, reply/tile isolation, counts/focus, failures, second looks, links, saved evidence, feed, delayed posts and phone layout, Community workspace/coverage navigation, history and deep links.")
            finally:
                proc.terminate()
                proc.wait(timeout=10)
                web.shutdown()
                web.server_close()


if __name__ == "__main__":
    run()
