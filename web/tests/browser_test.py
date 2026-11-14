"""End-to-end browser test for web/ against the Live API in fixture mode.

    python web/tests/browser_test.py [out_dir]

Needs: pip install playwright fastapi uvicorn && playwright install chromium.
Starts `python -m server --fixture` on :8001 (cache in a temp dir) and a static server on :8081,
so it does not clash with servers you already run on :8000 / :8080. Screenshots go to out_dir.
"""
import shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

repo = Path(__file__).resolve().parents[2]
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="web-test-"))
out.mkdir(parents=True, exist_ok=True)
cache = Path(tempfile.mkdtemp(prefix="web-test-cache-"))
API, WEB = "http://127.0.0.1:8001", "http://127.0.0.1:8081/web/"
Q = "api=" + API
procs = [
    subprocess.Popen([sys.executable, "-m", "server", "--fixture", "--port", "8001", "--cache", str(cache)],
                     cwd=repo, stdout=subprocess.DEVNULL, stderr=open(out / "server.log", "w")),
    subprocess.Popen([sys.executable, "-m", "http.server", "8081", "--bind", "127.0.0.1"], cwd=repo,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
]
for _ in range(50):
    try:
        urllib.request.urlopen(API + "/api/health"); break
    except Exception:
        time.sleep(0.2)

fails = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: fails.append(msg)

def wait_loaded(page):
    page.wait_for_selector("#viewer-body:not([hidden])", timeout=15000)
    page.wait_for_function("[...document.querySelectorAll('#frame-stack img')].every(i => i.complete)")

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("dialog", lambda d: d.accept())

        # 1. bare page
        page.goto(WEB + "?" + Q)
        page.wait_for_function("document.querySelector('#source-info').textContent.includes('Live API')")
        check(page.is_visible("#empty"), "empty state shown without coordinates")
        check(page.locator("#preset option").count() == 6, "5 test fields + placeholder in quick picks")
        check("fixture mode" in page.text_content("#source-info"), "footer shows fixture mode")
        # Default field pre-filled (T25), but nothing is requested until the user presses Show.
        check(page.input_value("input[name=ra]") == "269.4463" and page.input_value("input[name=dec]") == "4.7682"
              and page.input_value("input[name=size]") == "15", "form pre-filled with the default field")
        check(page.eval_on_selector("#preset", "s => s.options[s.selectedIndex].text") == "Barnard's Star",
              "test-field dropdown shows the default")
        check(page.locator("#form-hint").count() == 0, "no inline hint line any more (T29)")
        page.focus("input[name=dec]")
        check(page.is_hidden("#form-tip"), "help bubble is switched off by default (T29)")
        page.click("#form-help")
        check(page.is_visible("#form-tip"), "? button opens the bubble even when it is switched off")
        page.click("#form-help")
        check(page.is_hidden("#form-tip"), "? button closes it again")
        check(page.is_visible("#empty-default") and "Barnard's Star" in page.text_content("#empty-default"),
              "empty state names the pre-filled field")
        check(page.is_hidden("#viewer-body") and page.is_hidden("#job") and "ra=" not in page.url, "default is not loaded automatically")
        page.screenshot(path=str(out / "t20-empty.png"), full_page=True)
        page.fill("input[name=ra]", "10")
        check(page.input_value("#preset") == "" and page.is_hidden("#empty-default"), "typing own coordinates clears the default marker")
        page.fill("input[name=ra]", "269.4463")
        check(page.input_value("#preset") != "", "typing the default back re-selects it")

        # 2. pick a preset -> builds (202, progress) -> ready
        page.select_option("#preset", label="WISE 0855-0714")
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        check(True, "build progress panel appears")
        page.screenshot(path=str(out / "t20-building.png"), full_page=True)
        wait_loaded(page)
        check(page.is_hidden("#job"), "progress panel hides when ready")
        check("ra=133.7598" in page.url and "dec=-7.2422" in page.url and "size=15" in page.url, f"URL carries field: {page.url}")
        check("served for request" in page.text_content("#target-name"), "target.json comes from the Live API")
        check(page.is_visible("#synthetic-badge") and page.is_visible("#stage-watermark"), "fixture shown as synthetic")
        srcs = page.eval_on_selector_all("#frame-stack img", "els => els.map(e => [e.src, e.naturalWidth])")
        check(all(s.startswith(API + "/api/targets/") and w == 96 for s, w in srcs), "frames load from API, relative to target_url")
        check(page.input_value("#preset") != "", "preset select marks the chosen field")
        page.screenshot(path=str(out / "t20-loaded.png"), full_page=True)

        # 3. same field again = cache hit: no progress panel
        page.click("#field-form button[type=submit]")
        page.wait_for_timeout(600)
        check(page.is_hidden("#job"), "cached field loads without progress panel")

        # 4. typed sexagesimal coordinates, then back button
        page.fill("input[name=ra]", "08h55m10.831s")
        page.fill("input[name=dec]", "-7d14m42.53s")
        label_before = page.text_content("#stage-label")
        page.focus("input[name=ra]")
        page.keyboard.press("x")  # typing must not flip frames
        check(page.text_content("#stage-label") == label_before, "typing x in a text field doesn't flip frames")
        page.fill("input[name=ra]", "08h55m10.831s")
        page.click("#field-form button[type=submit]")
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        wait_loaded(page)
        page.wait_for_selector("#job[hidden]", state="attached", timeout=10000)
        check("ra=08h55m10.831s" in page.url, "typed sexagesimal coordinates in URL")
        check("c1337951-m072451-s15" in page.text_content("#target-name") or "133.795" in page.text_content("#target-name"),
              f"server parsed sexagesimal: {page.text_content('#target-name')}")
        page.go_back()
        page.wait_for_function("document.querySelector('input[name=ra]').value === '133.7598'")
        check(True, "back button restores the previous field")
        page.go_back()
        page.wait_for_selector("#empty:not([hidden])")
        check(page.is_hidden("#viewer-body"), "back to bare page shows empty state")
        check(page.input_value("input[name=ra]") == "269.4463", "back to bare page refills the default field")

        # 5. stop waiting
        page.goto(WEB + "?ra=10&dec=20&size=20&" + Q)
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        page.click("#job-cancel")
        check(page.is_hidden("#job") and "Stopped waiting" in page.text_content(".msg-warn"), "stop waiting hides progress, explains")

        # 6. rebuild
        page.goto(WEB + "?ra=10&dec=20&size=20&" + Q)
        wait_loaded(page)
        page.click("#btn-rebuild")
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        wait_loaded(page)
        page.wait_for_selector("#job[hidden]", state="attached", timeout=10000)
        check(True, "rebuild goes through a build again")
        check(not errors, f"no console errors on happy paths: {errors}")

        # 6b. RA/Dec help bubble, previewed with ?tip=1 (T29)
        t = b.new_page(viewport={"width": 1280, "height": 800})
        t.goto(WEB + "?tip=1&" + Q)
        t.wait_for_selector("#form-tip:not([hidden])", timeout=5000)
        check("decimal degrees" in t.text_content("#form-tip"), "?tip=1 shows the help bubble on the start page")
        tip_box, ra_box = t.locator("#form-tip").bounding_box(), t.locator("input[name=ra]").bounding_box()
        check(tip_box["y"] > ra_box["y"] + ra_box["height"] and abs(tip_box["x"] - ra_box["x"]) < 40,
              f"bubble sits under the RA input (tip {tip_box['x']:.0f},{tip_box['y']:.0f}; RA {ra_box['x']:.0f},{ra_box['y']:.0f})")
        t.screenshot(path=str(out / "t29-tip.png"))
        t.keyboard.press("Escape")
        check(t.is_hidden("#form-tip"), "Escape closes the bubble")
        t.focus("input[name=dec]")
        check(t.is_visible("#form-tip"), "focusing RA/Dec opens it again")
        t.click("#form-tip-close")
        check(t.is_hidden("#form-tip"), "Got it closes the bubble")
        t.reload()
        t.wait_for_function("document.querySelector('#source-info').textContent.includes('Live API')")
        t.focus("input[name=ra]")
        check(t.is_hidden("#form-tip"), "Got it is remembered after reload")
        t.click("#form-help")
        check(t.is_visible("#form-tip"), "? button reopens it after Got it")
        t.evaluate("localStorage.clear()")
        tp = b.new_page(viewport={"width": 390, "height": 844})
        tp.goto(WEB + "?tip=1&" + Q)
        tp.wait_for_selector("#form-tip:not([hidden])", timeout=5000)
        sw = tp.evaluate("document.documentElement.scrollWidth")
        check(sw <= 390, f"bubble fits on a phone (scrollWidth={sw})")
        covered = tp.evaluate("""() => {
            const t = document.querySelector('#form-tip').getBoundingClientRect();
            return [...document.querySelectorAll('#field-form input, #field-form select')].filter(c => {
                const r = c.getBoundingClientRect();
                return r.width && r.bottom > t.top && r.top < t.bottom && r.right > t.left && r.left < t.right;
            }).map(c => c.name || c.id);
        }""")
        check(not covered, f"bubble covers no input on a phone (covered: {covered})")
        tp.screenshot(path=str(out / "t29-tip-phone.png"))

        # 7. error paths
        e = b.new_page()
        e.goto(WEB + "?ra=abc&dec=20&" + Q)
        e.wait_for_selector(".msg-error")
        check("Can't use these coordinates" in e.text_content(".msg-error"), f"bad coordinates: {e.text_content('.msg-error')}")
        e.goto(WEB + "?ra=10&dec=20&api=http://127.0.0.1:9")
        e.wait_for_selector(".msg-error")
        check("Can't reach the Live API" in e.text_content(".msg-error"), "unreachable API explained")
        e.goto(WEB + "?api=http://127.0.0.1:9")
        e.wait_for_selector(".msg-warn")
        check("not reachable" in e.text_content(".msg-warn"), "unreachable API warned on bare page")

        # 8. offline mode
        o = b.new_page()
        oerr = []
        o.on("pageerror", lambda x: oerr.append(str(x)))
        o.goto(WEB + "?data=../fixtures/targets/")
        wait_loaded(o)
        check(o.is_hidden("#field-form") and o.is_visible("#picker"), "offline mode: picker instead of form")
        check("target=demo-synthetic" in o.url, "offline mode: target in URL")
        o.keyboard.press("x")
        check("B · f003" in o.text_content("#stage-label"), "offline mode: blink keys work")
        # The frame table still follows the current frame inside its own scroll box.
        o.evaluate("document.querySelector('.table-wrap').style.maxHeight = '60px'")
        o.click("#btn-a")
        o.keyboard.press("ArrowRight"); o.keyboard.press("ArrowRight"); o.keyboard.press("ArrowRight")
        visible = o.evaluate("""() => {
            const box = document.querySelector('.table-wrap').getBoundingClientRect();
            const row = document.querySelector('tr.shown').getBoundingClientRect();
            return document.querySelector('.table-wrap').scrollTop > 0 && row.bottom <= box.bottom + 1;
        }""")
        check(visible, "frame table scrolls inside its box to the shown frame")
        check(not oerr, f"offline: no page errors {oerr}")

        # 9. phone width
        m = b.new_page(viewport={"width": 390, "height": 844})
        m.goto(WEB + "?ra=133.7598&dec=-7.2422&size=15&" + Q)
        wait_loaded(m)
        sw = m.evaluate("document.documentElement.scrollWidth")
        check(sw <= 390, f"no horizontal scroll on phone (scrollWidth={sw})")
        # Narrow layout puts the frame table under the image; blinking must not scroll the page to it.
        m.evaluate("document.querySelector('#stage').scrollIntoView({block: 'start'})")
        y0 = m.evaluate("window.scrollY")
        m.click("#btn-play")
        m.wait_for_timeout(1600)
        m.click("#btn-play")
        m.keyboard.press("ArrowRight")
        y1 = m.evaluate("window.scrollY")
        check(y1 == y0, f"blinking/stepping keeps the page still on phone (scrollY {y0} -> {y1})")
        m.screenshot(path=str(out / "t20-mobile.png"), full_page=True)
        b.close()
finally:
    for pr in procs:
        pr.terminate()
    shutil.rmtree(cache, ignore_errors=True)
print(f"\n{len(fails)} failures · screenshots in {out}")
sys.exit(1 if fails else 0)
