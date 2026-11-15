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
# Multi-epoch synthetic target for the timeline/filter/pairs checks (T12). Lives in data/ (gitignored),
# reuses the fixture images, and is removed at the end.
import json
MULTI = repo / "data" / "test-targets"
shutil.rmtree(MULTI, ignore_errors=True)
(MULTI / "multi-epoch" / "frames").mkdir(parents=True)
_src = sorted((repo / "fixtures" / "targets" / "demo-synthetic" / "frames").glob("*.png"))
_spec = [  # id, epoch, mjd, detector, wavelength
    ("f000", 1, 60790.0, 2, 1.200), ("f001", 1, 60790.5, 2, 1.230), ("f002", 1, 60791.0, 3, 1.800),
    ("f003", 1, 60792.0, 3, 1.830), ("f004", 2, 60970.0, 2, 1.210), ("f005", 2, 60970.5, 2, 1.300),
    ("f006", 2, 60971.0, 3, 1.820), ("f007", 3, 61150.5, 2, 1.235), ("f008", 3, 61151.0, 3, 2.100),
]
_fixture = json.loads((repo / "fixtures" / "targets" / "demo-synthetic" / "target.json").read_text())
_frames = []
for i, (fid, ep, mjd, det, lam) in enumerate(_spec):
    shutil.copy(_src[i % len(_src)], MULTI / "multi-epoch" / "frames" / f"{fid}.png")
    _frames.append({"id": fid, "time_utc": f"2025-01-01T00:00:00Z", "mjd": mjd, "epoch": ep, "detector": det,
                    "wavelength_um": lam, "bandwidth_um": 0.03, "image": f"frames/{fid}.png",
                    "obs_id": None, "source_url": None})
for f in _frames:  # real-looking times from MJD
    from datetime import datetime, timedelta, timezone
    f["time_utc"] = (datetime(1858, 11, 17, tzinfo=timezone.utc) + timedelta(days=f["mjd"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    f["collection"] = "spherex_qr3" if f["epoch"] == 3 else "spherex_dr1"   # T64: release per frame (made up here)
_t = dict(_fixture, id="multi-epoch", name="Synthetic multi-epoch test field (NOT SPHEREx data)", schema_version="0.2",
          frames=_frames, labels=[],
          detections=[
              {"id": "d001", "status": "unknown", "matched_object": None, "synthetic": True, "score": 0.8,
               "track": [{"frame_id": f, "ra_deg": 150.0, "dec_deg": 2.2, "x": x, "y": 30.0} for f, x in (("f004", 40.0), ("f005", 45.0), ("f006", 50.0))],
               "motion": {"rate_arcsec_per_hr": 120.0, "pa_deg": 45.0}},
              {"id": "d002", "status": "artifact", "matched_object": None, "synthetic": True, "score": 0.1,
               "reason": "seen in one frame only: nothing to confirm motion with",
               "track": [{"frame_id": "f000", "ra_deg": 150.0, "dec_deg": 2.2, "x": 10.0, "y": 10.0}]},
              {"id": "d003", "status": "known", "matched_object": "(99) Testia", "synthetic": True, "score": 0.9,
               "track": [{"frame_id": f, "ra_deg": 150.0, "dec_deg": 2.2, "x": 60.0, "y": y} for f, y in (("f000", 60.0), ("f001", 62.0))],
               "motion": {"rate_arcsec_per_hr": 30.0, "pa_deg": 270.0}}],
          known_objects=[
              {"name": "(99) Testia", "source": "synthetic", "synthetic": True,
               "positions": [{"frame_id": f, "ra_deg": 150.0, "dec_deg": 2.2, "x": 60.0, "y": y} for f, y in (("f000", 60.0), ("f001", 62.0))]},
              {"name": "(77) Missedia", "source": "synthetic", "synthetic": True,
               "positions": [{"frame_id": f, "ra_deg": 150.0, "dec_deg": 2.2, "x": 20.0, "y": 70.0} for f in ("f007", "f008")]}],
          pairs=[{"a": "f000", "b": "f004", "detector": 2, "dwave_um": 0.01, "dt_days": 180.0},
                 {"a": "f001", "b": "f007", "detector": 2, "dwave_um": 0.005, "dt_days": 360.0},
                 {"a": "f003", "b": "f006", "detector": 3, "dwave_um": 0.01, "dt_days": 179.0}])
(MULTI / "multi-epoch" / "target.json").write_text(json.dumps(_t))
# Same frames, no detection run, provenance worded like a real build ("per epoch+detector").
_nd = dict(_t, id="no-detect", detections=[], known_objects=[k for k in _t["known_objects"] if k["name"] == "(77) Missedia"], provenance=[
    {"service": "IRSA SPHEREx cutouts", "query": "2 per epoch+detector of 358 images; 0 failed", "retrieved_utc": "2026-11-14T00:00:00Z"},
    {"service": "JPL SB Identification (sb_ident, first pass)", "query": "q", "retrieved_utc": "2026-11-14T00:00:01Z"}])
shutil.copytree(MULTI / "multi-epoch" / "frames", MULTI / "no-detect" / "frames")
(MULTI / "no-detect" / "target.json").write_text(json.dumps(_nd))
(MULTI / "index.json").write_text(json.dumps({"schema_version": "0.1", "targets": [
    {"id": "multi-epoch", "name": _t["name"], "synthetic": True, "ra_deg": 150.0, "dec_deg": 2.2, "n_frames": 9},
    {"id": "no-detect", "name": _t["name"] + " without detection", "synthetic": True, "ra_deg": 150.0, "dec_deg": 2.2, "n_frames": 9}]}))

API, WEB = "http://127.0.0.1:8001", "http://127.0.0.1:8081/web/"
Q = "explore=0&api=" + API  # explore=0: no sky map, the test must not depend on external tile servers
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
        groups = page.eval_on_selector_all("#preset optgroup", "gs => gs.map(g => [g.label, g.children.length])")
        check(groups[0] == ["Official test fields", 5] and len(groups) >= 2 and all(n >= 5 for _, n in groups[1:]),
              f"quick picks: 5 official fields + groups from discover.json (T65) {groups}")
        check("fixture mode" in page.text_content("#source-info"), f"footer shows fixture mode ({page.text_content('#source-info')})")
        # Default field pre-filled (T25), but nothing is requested until the user presses Show.
        check(page.input_value("#field-form input[name=ra]") == "269.4463" and page.input_value("#field-form input[name=dec]") == "4.7682"
              and page.input_value("#field-form input[name=size]") == "15", "form pre-filled with the default field")
        check(page.eval_on_selector("#preset", "s => s.options[s.selectedIndex].text") == "Barnard's Star",
              "test-field dropdown shows the default")
        check(page.locator("#form-hint").count() == 0, "no inline hint line any more (T29)")
        page.focus("#field-form input[name=dec]")
        check(page.is_hidden("#form-tip"), "help bubble is switched off by default (T29)")
        page.click("#form-help")
        check(page.is_visible("#form-tip"), "? button opens the bubble even when it is switched off")
        page.click("#form-help")
        check(page.is_hidden("#form-tip"), "? button closes it again")
        check(page.is_visible("#empty-default") and "Barnard's Star" in page.text_content("#empty-default"),
              "empty state names the pre-filled field")
        check(page.is_hidden("#viewer-body") and page.is_hidden("#job") and "ra=" not in page.url, "default is not loaded automatically")
        page.screenshot(path=str(out / "t20-empty.png"), full_page=True)
        page.fill("#field-form input[name=ra]", "10")
        check(page.input_value("#preset") == "" and page.is_hidden("#empty-default"), "typing own coordinates clears the default marker")
        page.fill("#field-form input[name=ra]", "269.4463")
        check(page.input_value("#preset") != "", "typing the default back re-selects it")

        # 1b. T65: "Surprise me" opens a field from discover.json and says why it is interesting
        check(page.is_visible("#surprise") and page.is_hidden("#pick-why"), "Surprise me button, no reason line for the default")
        page.click("#surprise")
        wait_loaded(page)
        picked = page.eval_on_selector("#preset", "s => s.options[s.selectedIndex].parentElement.label")
        check(picked != "Official test fields" and page.is_visible("#pick-why") and "Moves" in page.text_content("#pick-why")
              and "ra=" in page.url, f"Surprise me loads a discover field with its reason ({picked}: {page.text_content('#pick-why')[:80]})")
        page.fill("#field-form input[name=ra]", "10")
        check(page.is_hidden("#pick-why"), "own coordinates hide the reason line")
        page.goto(WEB + "?" + Q)   # back to the bare page, so step 2 waits for its own build
        page.wait_for_function("document.querySelector('#source-info').textContent.includes('Live API')")


        # 2. pick a preset -> builds (202, progress) -> ready
        page.select_option("#preset", label="WISE 0855-0714")
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        check(True, "build progress panel appears")
        page.screenshot(path=str(out / "t20-building.png"), full_page=True)
        wait_loaded(page)
        check(page.is_hidden("#job"), "progress panel hides when ready")
        check(page.is_hidden("#chem-box") and page.is_hidden("#chem-note"),
              "T93: no Chemistry selector for a synthetic field (no SPHEREx exposures to map)")
        check("ra=133.7598" in page.url and "dec=-7.2422" in page.url and "size=15" in page.url, f"URL carries field: {page.url}")
        check("served for request" in page.text_content("#target-name"), "target.json comes from the Live API")
        check(page.is_visible("#synthetic-badge") and page.is_visible("#stage-watermark"), "fixture shown as synthetic")
        srcs = page.eval_on_selector_all("#frame-stack img", "els => els.map(e => [e.src, e.naturalWidth])")
        check(all(s.startswith(API + "/api/targets/") and w == 96 for s, w in srcs), "frames load from API, relative to target_url")
        check(all("v=" in s for s, _ in srcs), "frame URLs carry a build stamp (rebuilds must not show cached old frames)")
        check(page.input_value("#preset") != "", "preset select marks the chosen field")
        check(page.is_hidden("#photometry"), "synthetic field: no photometry panel, nothing real to measure (T49)")
        page.click("#btn-diff")
        page.wait_for_selector("#diff-canvas:not([hidden]), #diff-note:has-text('unavailable')", timeout=8000)
        check(page.is_visible("#diff-canvas"), f"difference view works on frames from the Live API (CORS) {page.text_content('#diff-note')}")
        page.click("#btn-diff")
        page.screenshot(path=str(out / "t20-loaded.png"), full_page=True)

        # 3. same field again = cache hit: no progress panel
        page.click("#field-form button[type=submit]")
        page.wait_for_timeout(600)
        check(page.is_hidden("#job"), "cached field loads without progress panel")

        # 4. typed sexagesimal coordinates, then back button
        page.fill("#field-form input[name=ra]", "08h55m10.831s")
        page.fill("#field-form input[name=dec]", "-7d14m42.53s")
        label_before = page.text_content("#stage-label")
        page.focus("#field-form input[name=ra]")
        page.keyboard.press("x")  # typing must not flip frames
        check(page.text_content("#stage-label") == label_before, "typing x in a text field doesn't flip frames")
        page.fill("#field-form input[name=ra]", "08h55m10.831s")
        page.click("#field-form button[type=submit]")
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        wait_loaded(page)
        page.wait_for_selector("#job[hidden]", state="attached", timeout=10000)
        check("ra=08h55m10.831s" in page.url, "typed sexagesimal coordinates in URL")
        check("c1337951-m072451-s15" in page.text_content("#target-name") or "133.795" in page.text_content("#target-name"),
              f"server parsed sexagesimal: {page.text_content('#target-name')}")
        page.go_back()
        page.wait_for_function("document.querySelector('#field-form input[name=ra]').value === '133.7598'")
        check(True, "back button restores the previous field")
        page.go_back()
        page.wait_for_selector("#empty:not([hidden])")
        check(page.is_hidden("#viewer-body"), "back to bare page shows empty state")
        check(page.input_value("#field-form input[name=ra]") == "269.4463", "back to bare page refills the default field")

        # 5. stop waiting
        page.goto(WEB + "?ra=10&dec=20&size=20&" + Q)
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        page.click("#job-cancel")
        check(page.is_hidden("#job") and "Stopped waiting" in page.text_content(".msg-warn"), "stop waiting hides progress, explains")

        # 6. rebuild
        page.goto(WEB + "?ra=10&dec=20&size=20&" + Q)
        wait_loaded(page)
        before = page.eval_on_selector("#frame-stack img", "e => e.src")
        page.wait_for_timeout(1100)  # provenance timestamps have 1 s resolution
        page.click("#btn-rebuild")
        page.wait_for_selector("#job:not([hidden])", timeout=5000)
        wait_loaded(page)
        page.wait_for_selector("#job[hidden]", state="attached", timeout=10000)
        after = page.eval_on_selector("#frame-stack img", "e => e.src")
        check(before != after and before.split("?")[0] == after.split("?")[0],
              f"rebuild gives the same frame a new URL, so the browser fetches the new image ({before[-24:]} -> {after[-24:]})")
        check(not errors, f"no console errors on happy paths: {errors}")

        # 6b. RA/Dec help bubble, previewed with ?tip=1 (T29)
        t = b.new_page(viewport={"width": 1280, "height": 800})
        t.goto(WEB + "?tip=1&" + Q)
        t.wait_for_selector("#form-tip:not([hidden])", timeout=5000)
        check("decimal degrees" in t.text_content("#form-tip"), "?tip=1 shows the help bubble on the start page")
        tip_box, ra_box = t.locator("#form-tip").bounding_box(), t.locator("#field-form input[name=ra]").bounding_box()
        check(tip_box["y"] > ra_box["y"] + ra_box["height"] and abs(tip_box["x"] - ra_box["x"]) < 40,
              f"bubble sits under the RA input (tip {tip_box['x']:.0f},{tip_box['y']:.0f}; RA {ra_box['x']:.0f},{ra_box['y']:.0f})")
        t.screenshot(path=str(out / "t29-tip.png"))
        t.keyboard.press("Escape")
        check(t.is_hidden("#form-tip"), "Escape closes the bubble")
        t.focus("#field-form input[name=dec]")
        check(t.is_visible("#form-tip"), "focusing RA/Dec opens it again")
        t.click("#form-tip-close")
        check(t.is_hidden("#form-tip"), "Got it closes the bubble")
        t.reload()
        t.wait_for_function("document.querySelector('#source-info').textContent.includes('Live API')")
        t.focus("#field-form input[name=ra]")
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
        e.goto(WEB + "?explore=0&ra=10&dec=20&size=15&api=http://127.0.0.1:9")   # size= asks for a build (T90: ra/dec alone only moves the map)
        e.wait_for_selector(".msg-error")
        check("Can't reach the Live API" in e.text_content(".msg-error"), "unreachable API explained")
        e.goto(WEB + "?explore=0&api=http://127.0.0.1:9")
        e.wait_for_selector(".msg-warn")
        check("not reachable" in e.text_content(".msg-warn"), "unreachable API warned on bare page")

        # 8. offline mode
        o = b.new_page()
        oerr = []
        o.on("pageerror", lambda x: oerr.append(str(x)))
        o.goto(WEB + "?explore=0&data=../fixtures/targets/")
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
        # T13 objects panel on the fixture (one synthetic known asteroid, detected)
        rows = o.locator("#objects-list .obj-row")
        check(rows.count() == 1 and "Fake asteroid" in rows.first.text_content() and "synthetic" in rows.first.text_content(),
              "objects panel: fixture asteroid listed once, with synthetic badge")
        check("3.1″/h → W" in rows.first.text_content() and "score 0.95" in rows.first.text_content(), "objects panel: motion and score")
        check("1 moving object" in o.text_content("#objects-summary") and "synthetic" in o.text_content("#objects-summary"),
              f"headline count: {o.text_content('#objects-summary')}")
        # T22 paths overlay (Joerg's agent cannot run a browser)
        check(o.locator("#paths-layer").count() == 1 and "Fake asteroid · synthetic" in (o.text_content("#overlay") or ""),
              "T22: paths layer drawn, synthetic object named as such")
        check(o.is_hidden("#explore"), "offline mode hides the sky map (no tile server)")
        # T56: the committed schema-0.2 fixture (every optional field) loads and shows what it contains
        o.goto(WEB + "?explore=0&data=../fixtures/targets/&target=demo-epochs")
        wait_loaded(o)
        o.wait_for_selector("#objects-list .obj-row")
        txt = o.text_content("#objects-list")
        check(o.locator(".table-wrap tbody tr").count() == 9 and o.locator("#pair-select option").count() >= 3,
              "demo-epochs fixture: 9 frames and its pairs")
        check("Synthetic asteroid A" in txt and "Synthetic asteroid B" in txt and "unknown" in txt.lower(),
              f"demo-epochs fixture: known, not-detected and unknown objects listed ({txt[:160]})")
        if not o.is_checked("#labels-toggle"):
            o.click("#labels-toggle")   # labels are remembered per browser; an earlier check may have switched them off
        o.wait_for_selector(".path-hit[aria-label^='Synthetic star PM-1']", state="attached", timeout=5000)
        check(o.locator(".path-hit[aria-label^='Synthetic variable V-1']").count() == 1, "demo-epochs: its labels are drawn")
        check(not oerr, f"offline: no page errors {oerr}")

        # 8b. timeline, wavelength filter, matched pairs (T12) on the multi-epoch target
        z = b.new_page(viewport={"width": 1280, "height": 900})
        zerr = []
        z.on("pageerror", lambda x: zerr.append(str(x)))
        z.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(z)
        a_id = lambda: z.eval_on_selector("input[name=slot-a]:checked", "e => e.value")
        b_id = lambda: z.eval_on_selector("input[name=slot-b]:checked", "e => e.value")
        check(z.locator(".tl-panel").count() == 3 and z.locator(".tl-frame").count() == 9, "timeline: 3 epoch panels, 9 frames")
        check((a_id(), b_id()) == ("f001", "f007"), f"default A/B = matched pair with longest baseline ({a_id()}, {b_id()})")
        check(z.locator(".tl-frame.is-a").get_attribute("data-frame") == "f001"
              and z.locator(".tl-frame.is-b").get_attribute("data-frame") == "f007", "timeline marks A and B")
        check("wavelength-matched" in z.text_content("#frame-info"), "frame info says A/B are wavelength-matched")
        check("SPHEREx DR1 + QR3" in z.text_content("#target-meta") and "DR1 (spherex_dr1)" in z.text_content("#frame-info")
              and z.is_hidden("#target-updates"), f"T64: releases in the field line and the frame info ({z.text_content('#target-meta')})")
        check(z.is_visible("#pair-select") and "f001 ↔ f007" in z.eval_on_selector("#pair-select", "s => s.options[s.selectedIndex].text"),
              "pair picker shows the current pair")
        z.fill("#lam-max", "1.5"); z.press("#lam-max", "Enter"); z.locator("#lam-max").blur()
        z.wait_for_function("document.querySelector('#filter-count').textContent.includes('5 of 9')")
        rows = z.eval_on_selector_all("#frame-table tbody tr", "rs => rs.filter(r => !r.hidden).length")
        check(rows == 5 and z.locator(".tl-frame.is-out").count() == 4, f"λ ≤ 1.5: 5 rows, 4 timeline dots dimmed ({rows})")
        z.fill("#lam-min", "1.7"); z.fill("#lam-max", "2.0"); z.locator("#lam-max").blur()
        z.wait_for_function("document.querySelector('#filter-count').textContent.includes('3 of 9')")
        check((a_id(), b_id()) == ("f002", "f006"), f"filter moves A/B inside it, B = closest λ in another epoch ({a_id()}, {b_id()})")
        z.click("#btn-a"); z.keyboard.press("ArrowRight")
        check("f003" in z.text_content("#stage-label"), "stepping skips frames outside the filter")
        z.click("#lam-reset")
        check(z.locator(".tl-frame.is-out").count() == 0 and z.text_content("#filter-count") == "", "All frames resets the filter")
        z.select_option("#det-filter", "2")
        check(z.locator(".tl-frame.is-out").count() == 4, "detector filter D2 keeps 5 frames")
        z.click("#lam-reset")
        z.check("input[name=slot-a][value=f005]")
        z.click("#stage")  # focus away from the radio so M goes to the page
        z.keyboard.press("m")
        check(b_id() == "f007", f"M: B = closest wavelength in another epoch, same detector ({b_id()})")
        z.check("input[name=slot-b][value=f008]")
        z.check("input[name=slot-a][value=f000]")
        check("different wavelengths" in z.text_content("#frame-info"), "frame info warns when A/B are at different wavelengths")
        z.select_option("#pair-select", label=z.eval_on_selector("#pair-select", "s => [...s.options].find(o => o.text.startsWith('f000')).text"))
        check((a_id(), b_id()) == ("f000", "f004"), "picking a pair sets A and B")
        z.locator('.tl-frame[data-frame="f005"] .tl-hit').click()
        check("f005" in z.text_content("#stage-label"), "clicking a timeline dot shows that frame")
        z.screenshot(path=str(out / "t12-timeline.png"), full_page=True)
        zp = b.new_page(viewport={"width": 390, "height": 844})
        zp.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(zp)
        sw = zp.evaluate("document.documentElement.scrollWidth")
        check(sw <= 390 and zp.locator(".tl-panel").count() == 3, f"timeline fits on a phone (scrollWidth={sw})")
        zp.screenshot(path=str(out / "t12-phone.png"), full_page=True)
        check(not zerr, f"T12: no page errors {zerr}")

        # 8b2. difference view A − B (T43) on the multi-epoch target (offline, same origin)
        g = b.new_page(viewport={"width": 1280, "height": 900})
        gerr = []
        g.on("pageerror", lambda x: gerr.append(str(x)))
        g.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(g)
        diff_px = lambda x, y: g.evaluate(f"() => Array.from(document.querySelector('#diff-canvas').getContext('2d').getImageData({x}, {y}, 1, 1).data)")
        g.click("#stage"); g.keyboard.press("d")
        g.wait_for_selector("#diff-canvas:not([hidden])", timeout=5000)
        check(g.get_attribute("#btn-diff", "aria-pressed") == "true" and "A − B · f001 − f007" in g.text_content("#stage-diff-label"),
              f"D shows A − B for the current pair ({g.text_content('#stage-diff-label')})")
        check(g.is_hidden("#stage-label") and "wavelength-matched" in g.text_content("#diff-note"), "frame label hidden, legend says the pair is matched")
        # fixture asteroid: at x=26 in A (f001), at x=38 in B (f007 = fixture f003), y=48
        white, black, sky = diff_px(26, 48)[0], diff_px(38, 48)[0], diff_px(5, 5)[0]
        check(white > 168 and black < 88 and 96 < sky < 160, f"mover = white in A's place, black in B's, sky grey ({white}, {black}, {sky})")
        g.select_option("#pair-select", label=g.eval_on_selector("#pair-select", "s => [...s.options].find(o => o.text.startsWith('f000')).text"))
        g.wait_for_function("document.querySelector('#stage-diff-label').textContent.includes('f000 − f004')")
        spread = g.evaluate("""() => { const d = document.querySelector('#diff-canvas').getContext('2d').getImageData(0, 0, 96, 96).data;
            let lo = 255, hi = 0; for (let i = 0; i < d.length; i += 4) if (d[i] === d[i + 1] && d[i] === d[i + 2]) { lo = Math.min(lo, d[i]); hi = Math.max(hi, d[i]); } return [lo, hi]; }""")
        check(spread[0] >= 124 and spread[1] <= 132, f"identical frames give a flat grey difference ({spread})")
        g.check("#trail-on")
        check(g.get_attribute("#btn-diff", "aria-pressed") == "false" and g.is_hidden("#diff-canvas"), "turning the trail view on ends the difference view")
        g.uncheck("#trail-on")
        g.click("#btn-diff"); g.wait_for_selector("#diff-canvas:not([hidden])")
        g.click("#btn-play")
        check(g.get_attribute("#btn-diff", "aria-pressed") == "false" and g.is_visible("#stage-label"), "starting the blink ends the difference view")
        g.click("#btn-play")
        check(not gerr, f"T43: no page errors {gerr}")

        # 8b3. play the series like a video (T45) on the multi-epoch target
        v = b.new_page(viewport={"width": 1280, "height": 900})
        verr = []
        v.on("pageerror", lambda x: verr.append(str(x)))
        v.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(v)
        v.evaluate("() => { const s = document.querySelector('#speed'); s.value = 100; s.dispatchEvent(new Event('input')); }")
        def seen(page, ms=1600):
            out = []
            for _ in range(ms // 40):
                fid = page.text_content("#stage-label").replace("A · ", "").replace("B · ", "").split(" · ")[0]
                if not out or out[-1] != fid:
                    out.append(fid)
                page.wait_for_timeout(40)
            return out
        v.click("#stage"); v.keyboard.press("p")
        check(v.get_attribute("#btn-film", "aria-pressed") == "true" and "Pause" in v.text_content("#btn-film"), "P starts Play all")
        seq = seen(v)
        order = [f"f00{i}" for i in range(9)]
        steps_ok = all(order.index(y) == (order.index(x) + 1) % 9 for x, y in zip(seq, seq[1:]))
        check(len(set(seq)) >= 6 and steps_ok, f"plays all frames in time order and loops ({seq})")
        v.select_option("#film-mode", "epoch")
        v.wait_for_timeout(300)
        seq = seen(v, 1200)
        check(set(seq) == {"f001", "f004", "f007"}, f"one per epoch at A's wavelength: f001, f004, f007 ({sorted(set(seq))})")
        v.select_option("#film-mode", "all")
        v.fill("#lam-max", "1.5"); v.locator("#lam-max").blur()
        v.wait_for_timeout(300)
        seq = seen(v, 1200)
        check(set(seq) <= {"f000", "f001", "f004", "f005", "f007"} and len(set(seq)) >= 4, f"film follows the wavelength filter ({sorted(set(seq))})")
        v.click("#lam-reset")
        v.click("#btn-play")
        check(v.get_attribute("#btn-film", "aria-pressed") == "false" and v.get_attribute("#btn-play", "aria-pressed") == "true",
              "starting the blink stops the film")
        v.click("#btn-play")
        v.click("#btn-diff"); v.wait_for_selector("#diff-canvas:not([hidden])")
        v.click("#stage"); v.keyboard.press("p")
        check(v.get_attribute("#btn-diff", "aria-pressed") == "false" and v.get_attribute("#btn-film", "aria-pressed") == "true",
              "starting the film ends the difference view")
        v.keyboard.press("ArrowRight")
        check(v.get_attribute("#btn-film", "aria-pressed") == "false", "stepping by hand stops the film")
        check(not verr, f"T45: no page errors {verr}")

        # 8b4. light curves + spectra (T49): the API answer is stubbed (CI has no real FITS)
        ph = b.new_page(viewport={"width": 1280, "height": 1000})
        pherr, phreq = [], []
        ph.on("pageerror", lambda x: pherr.append(str(x)))
        def stub(route):
            phreq.append(route.request.url)
            rows = []
            for fid, ep, lam, flux, masked in (("f000", 1, 1.200, 1000, False), ("f001", 1, 1.230, 1100, False), ("f002", 1, 1.800, 900, False),
                                                ("f003", 1, 1.830, 0, True), ("f004", 2, 1.210, 1500, False), ("f005", 2, 1.300, 1200, False),
                                                ("f006", 2, 1.820, 950, False), ("f007", 3, 1.235, 2000, False), ("f008", 3, 2.100, 800, False)):
                rows.append({"frame_id": fid, "epoch": ep, "mjd": 60790 + 180 * (ep - 1), "time_utc": "2025-04-25T00:00:00Z", "detector": 2,
                             "wavelength_um": lam, "bandwidth_um": 0.03, "flux_ujy": None if masked else flux, "err_ujy": None if masked else 30,
                             "masked_fraction": 0.9 if masked else 0.0, "masked": masked})
            route.fulfill(json={"status": "ready", "id": "multi-epoch", "ra_deg": 150.0, "dec_deg": 2.2, "aperture_px": 3,
                                "annulus_px": [5, 8], "unit": "uJy", "frames": rows, "missing": [], "note": "stub note"})
        ph.route(lambda url: url.split("?")[0].endswith("/photometry"), stub)  # the API path only, not photometry.js
        ph.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(ph)
        ph.wait_for_selector("#photometry:not([hidden]) #ph-body svg", timeout=8000)
        titles = ph.eval_on_selector_all("#ph-body .ph-title", "es => es.map(e => e.textContent)")
        check(titles == ["Epoch 1", "Epoch 2", "Epoch 3"], f"spectrum: one panel per epoch ({titles})")
        check("8 of 9 frames measured at the field centre" in ph.text_content(".ph-where") and ph.locator(".ph-masked").count() == 1,
              f"counts measured frames, marks the flagged one ({ph.text_content('.ph-where')})")
        legend = ph.text_content(".ph-legend")
        # matches within half a channel (0.015 µm): f000↔f004 (+50%) and f001↔f007 (+82%)
        check("epoch 1 → 2: median +50%" in legend and "epoch 1 → 3: median +82%" in legend and ph.locator(".ph-dot-c").count() == 2,
              f"change at the same wavelength across epoch pairs ({legend})")
        # T63 spectrum context (the science itself is checked in web/tests/spectrum_check.mjs)
        check(ph.locator(".ph-context").count() == 1 and "Baseline" in ph.text_content(".ph-context") and ph.locator(".ph-base").count() >= 2,
              "T63: baseline drawn and explained under the spectrum")
        ph.click("text=Feature markers")
        check(ph.locator(".ph-feature").count() == 8 * 3 and "H₂O ice 3.05" in ph.text_content(".ph-features-key"),
              "T63: feature markers in every epoch panel, with a key")
        ph.click("text=Expected + hints")
        check(ph.locator(".ph-context").count() == 0 and ph.locator(".ph-base").count() == 0, "T63: baseline + hints can be switched off")
        ph.click("text=Expected + hints"); ph.click("text=Feature markers")
        ph.click("#ph-measure")
        cb = ph.locator("#ph-catcher").bounding_box()
        ph.locator("#ph-catcher").click(position={"x": cb["width"] * 0.25, "y": cb["height"] * 0.5})
        ph.wait_for_function("document.querySelector('.ph-where').textContent.includes('clicked star')")
        check("x=" in phreq[-1] and "y=" in phreq[-1] and ph.locator("#ph-layer .ph-marker").count() == 3,
              "Measure a star: click sends the pixel, marks the spot")
        check(ph.get_attribute("#ph-measure", "aria-pressed") == "false" and ph.is_hidden("#ph-catcher"), "measure mode ends after one click")
        check(not pherr, f"T49: no page errors {pherr}")

        # 8b5. T78: type an exact wavelength -> A/B = closest frames in the earliest and latest epoch
        lp = b.new_page(viewport={"width": 1280, "height": 900})
        lperr = []
        lp.on("pageerror", lambda x: lperr.append(str(x)))
        lp.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(lp)
        lp.fill("#lam-at", "1.23"); lp.press("#lam-at", "Enter")
        lp.wait_for_function("document.querySelector('#lam-at-note').textContent.includes('f007')")
        note = lp.text_content("#lam-at-note")
        check("A f001" in note and "B f007" in note and "fair comparison" in note and "lam=1.23" in lp.url,
              f"T78: 1.23 µm picks f001 (epoch 1) and f007 (epoch 3), URL remembers it ({note})")
        check("A · f001" in lp.text_content("#stage-label"), "T78: A is shown")
        lp.fill("#lam-at", "1.82"); lp.press("#lam-at", "Enter")
        lp.wait_for_function("document.querySelector('#lam-at-note').textContent.includes('f006')")
        check("A f003" in lp.text_content("#lam-at-note"), f"T78: 1.82 µm stays on one detector ({lp.text_content('#lam-at-note')})")
        lp.fill("#lam-at", "abc"); lp.press("#lam-at", "Enter")
        check("between 0.75 and 5.0" in lp.text_content("#lam-at-note"), "T78: a typo gets a hint, nothing changes")
        check(lp.eval_on_selector_all("#lam-features option", "os => os.length") >= 8, "T78: feature wavelengths offered as suggestions")
        lp.goto(WEB + "?explore=0&data=../data/test-targets/&lam=1.21")
        wait_loaded(lp)
        lp.wait_for_function("document.querySelector('#lam-at-note').textContent.includes('B ')")
        check(lp.input_value("#lam-at") == "1.21" and "A f000" in lp.text_content("#lam-at-note"),
              f"T78: ?lam=1.21 in a link is applied on load ({lp.text_content('#lam-at-note')})")
        check(not lperr, f"T78: no page errors {lperr}")

        # 8b6. T59: stacks (per epoch / per detector) over the stage, blinkable, exclusive with A - B and trail
        sk = b.new_page(viewport={"width": 1280, "height": 900})
        skerr = []
        sk.on("pageerror", lambda x: skerr.append(str(x)))
        sk.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(sk)
        sk.select_option("#stack-mode", "epoch")
        sk.wait_for_selector("#stack-canvas:not([hidden])", timeout=8000)
        lab = sk.text_content("#stage-stack-label")
        check("Stack · epoch" in lab and "all detectors" in lab and sk.is_hidden("#stage-label") and "better" in sk.text_content("#stack-note"),
              f"T59: per-epoch stack drawn and labelled ({lab})")
        ep_a = lab
        sk.keyboard.press("x")
        sk.wait_for_function("document.querySelector('#stage-stack-label').textContent.startsWith('B')")
        check(sk.text_content("#stage-stack-label") != ep_a, f"T59: flipping to B shows B's epoch stack ({sk.text_content('#stage-stack-label')})")
        sk.select_option("#stack-mode", "detector")
        sk.wait_for_function("document.querySelector('#stage-stack-label').textContent.includes('detector')")
        check("epochs" in sk.text_content("#stage-stack-label"), f"T59: per-detector stack over the epochs ({sk.text_content('#stage-stack-label')})")
        sk.click("#btn-diff")
        sk.wait_for_selector("#diff-canvas:not([hidden])", timeout=8000)
        check(sk.input_value("#stack-mode") == "off" and sk.is_hidden("#stack-canvas") and sk.is_hidden("#stage-stack-label"),
              "T59: A − B ends the stack")
        sk.select_option("#stack-mode", "epoch")
        sk.wait_for_selector("#stack-canvas:not([hidden])", timeout=8000)
        check(sk.get_attribute("#btn-diff", "aria-pressed") == "false" and sk.is_hidden("#diff-canvas"), "T59: the stack ends A − B")
        sk.check("#trail-on")
        check(sk.input_value("#stack-mode") == "off" and sk.is_hidden("#stack-canvas"), "T59: the trail view ends the stack")
        # T69: shift-and-stack along a clicked object / a guessed motion
        sk.select_option("#stack-mode", "object")
        check("Click an object" in sk.text_content("#stack-note") and sk.is_hidden("#stack-canvas"), "T69: along an object asks for a click first")
        sk.evaluate("""() => document.dispatchEvent(new CustomEvent('paths:select', { detail: { obj: { name: '(99) Testia',
            positions: [{ frame_id: 'f000', ra_deg: 150.0, dec_deg: 2.2, x: 60, y: 60 }, { frame_id: 'f001', ra_deg: 150.0, dec_deg: 2.2, x: 60, y: 62 }] } } }))""")
        sk.wait_for_selector("#stack-canvas:not([hidden])", timeout=8000)
        check("Stack along (99) Testia · 2 frames" in sk.text_content("#stage-stack-label") and "stays in place" in sk.text_content("#stack-note"),
              f"T69: stack along the selected object ({sk.text_content('#stage-stack-label')})")
        sk.select_option("#stack-mode", "motion")
        sk.wait_for_function("document.querySelector('#stage-stack-label').textContent.includes('guessed motion')")
        check(sk.is_visible("#stack-rate") and "0.25″/h toward 90° (E)" in sk.text_content("#stage-stack-label"),
              f"T69: guessed motion with rate + direction ({sk.text_content('#stage-stack-label')})")
        sk.fill("#stack-rate", "0.5"); sk.press("#stack-rate", "Enter")
        sk.wait_for_function("document.querySelector('#stage-stack-label').textContent.includes('0.5″/h')")
        check(True, "T69: changing the rate restacks")
        sk.select_option("#stack-mode", "off")
        check(sk.is_hidden("#stack-motion") and sk.is_hidden("#stack-canvas"), "T69: off hides the motion inputs")
        check(not skerr, f"T59: no page errors {skerr}")

        # 8c. objects panel (T13) on the multi-epoch target
        q = b.new_page(viewport={"width": 1280, "height": 900})
        qerr = []
        q.on("pageerror", lambda x: qerr.append(str(x)))
        q.goto(WEB + "?explore=0&data=../data/test-targets/")
        wait_loaded(q)
        names = q.eval_on_selector_all("#objects-list .obj-name", "es => es.map(e => e.textContent)")
        check(names == ["Unknown mover", "(99) Testia", "(77) Missedia"], f"objects: unknown first, artifact hidden, known listed once ({names})")
        summ = q.text_content("#objects-summary")
        check("2 moving objects" in summ and "1 unknown" in summ, f"headline: {summ}")
        check("known · not detected" in q.locator("#objects-list .obj-row").nth(2).text_content(), "catalogued object we did not detect is marked so")
        check("120″/h → NE" in q.locator("#objects-list .obj-row").first.text_content(), "unknown mover shows rate and direction")
        q.check("#objects-show-artifacts")
        check(q.locator("#objects-list .obj-row").count() == 4 and "Artifact d002" in q.text_content("#objects-list"), "artifacts appear on request")
        check("seen in one frame only" in q.text_content("#objects-list"), "artifact shows its reason (v0.9, T08)")
        q.uncheck("#objects-show-artifacts")
        q.locator("#objects-list .obj-row").first.click()
        check("f004" in q.text_content("#stage-label"), "clicking an object jumps to a frame where it is")
        ring = q.locator("#focus-layer .focus-ring")
        check(ring.count() == 1 and ring.get_attribute("cx") == "40" and ring.get_attribute("cy") == "30", "focus ring on the object in that frame")
        q.keyboard.press("ArrowRight")
        check(q.locator("#focus-layer .focus-ring").get_attribute("cx") == "45", "focus ring follows the object to the next frame")
        q.locator("#objects-list .obj-row").first.click()
        check(q.locator("#focus-layer .focus-ring").count() == 0, "clicking again clears the focus")
        q.screenshot(path=str(out / "t13-objects.png"), full_page=True)
        q.goto(WEB + "?explore=0&data=../data/test-targets/&target=no-detect")
        wait_loaded(q)
        q.wait_for_function("document.querySelector('#objects-summary').textContent.length > 0")
        check("has not run" in q.text_content("#objects-summary"),
              f"no detection run: headline says so, 'detector' in provenance doesn't fool it ({q.text_content('#objects-summary')})")
        check("1 known solar-system object" in q.text_content("#objects-summary")
              and "catalogued" in q.text_content("#objects-list") and "not detected" not in q.text_content("#objects-list"),
              "JPL known objects without detection: listed as catalogued, not as missed")
        check(not qerr, f"T13: no page errors {qerr}")

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
    shutil.rmtree(MULTI, ignore_errors=True)
print(f"\n{len(fails)} failures · screenshots in {out}")
sys.exit(1 if fails else 0)
