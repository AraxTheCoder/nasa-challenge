"""Exploratory browser check of the viewer on REAL data, against the running Live API (:8000) + viewer (:8080)
started by `python web/dev.py` (unlike browser_test.py, which uses fixtures and its own servers). Mati, T115-T117.

    python web/tests/live_check.py <out_dir> [scenario,scenario,...]

Ten scenarios (default load, a field with the blink tools, map tools, chemistry presets / any number of features /
redshift, the tour, Surprise me, bad URLs, form input, phone width) on fields that are cached on the dev machine
(Barnard's Star, rho Oph, NGC 6240, the tour's five targets). Per scenario it records page errors, console errors,
HTTP >= 400 answers and failed requests (report.json) and screenshots. It does not assert: read the report and
look at the screenshots. Map tiles outside a field's footprint answer 404 by design (HiPS "no tile"), as does
/motion when no catalogued star moves at the spot.

Chromium without system libraries (no sudo for `playwright install-deps`): only libasound.so.2 was missing on
Ubuntu 22.04; `apt-get download libasound2 && dpkg -x libasound2_*.deb <dir>` and run with
LD_LIBRARY_PATH=<dir>/usr/lib/x86_64-linux-gnu.
"""
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

WEB = "http://localhost:8080/web/"
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 else None
report = {}


def attach(page, log):
    page.on("pageerror", lambda e: log["pageerror"].append(str(e)[:300]))
    page.on("console", lambda m: log["console"].append(f"{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    page.on("requestfailed", lambda r: log["failed"].append(f"{r.method} {r.url[:160]} {r.failure}")
            if "net::ERR_ABORTED" not in str(r.failure) else None)
    page.on("response", lambda r: log["http"].append(f"{r.status} {r.request.method} {r.url[:160]}") if r.status >= 400 else None)


def scenario(name):
    def deco(fn):
        fn._name = name
        SCEN.append(fn)
        return fn
    return deco


SCEN = []


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


def visible(page, sel):
    try:
        return page.locator(sel).first.is_visible()
    except Exception:
        return False


def wait_field(page, timeout=180):
    """Until the viewer shows a field (target name filled) or an error message."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        name = (page.text_content("#target-name") or "").strip() if page.locator("#target-name").count() else ""
        if name:
            return name
        if visible(page, "#stage-error"):
            return "ERROR: " + (page.text_content("#stage-error") or "")
        page.wait_for_timeout(1000)
    return None


@scenario("default_load")
def s_default(page, log):
    page.goto(WEB)
    page.wait_for_timeout(15000)
    shot(page, "default_load")
    log["notes"].append(f"messages: {(page.text_content('#messages') or '').strip()[:200]}")
    log["notes"].append(f"blink status: {(page.text_content('#blink-status') or '').strip()[:120]}")


@scenario("barnard_field")
def s_barnard(page, log):
    page.goto(WEB + "?ra=269.4463&dec=4.7682&size=15")
    name = wait_field(page)
    log["notes"].append(f"field: {name}")
    page.wait_for_timeout(5000)
    shot(page, "barnard_loaded")
    # viewer controls
    for sel in ["#btn-a", "#btn-b", "#btn-diff", "#btn-diff", "#btn-play", "#btn-play", "#btn-film", "#btn-film"]:
        try:
            if page.locator(sel).is_visible():
                page.click(sel)
                page.wait_for_timeout(700)
            else:
                log["notes"].append(f"{sel} not visible")
        except Exception as e:
            log["notes"].append(f"click {sel}: {str(e)[:120]}")
    # labels toggle on
    try:
        if not page.locator("#labels-toggle").is_checked():
            page.click("#labels-toggle")
        page.wait_for_timeout(6000)
        shot(page, "barnard_labels")
        log["notes"].append(f"labels note: {(page.text_content('#labels-note') or '').strip()[:120]}")
    except Exception as e:
        log["notes"].append(f"labels: {str(e)[:150]}")
    # objects panel
    log["notes"].append(f"objects summary: {(page.text_content('#objects-summary') or '').strip()[:200]}")
    log["notes"].append(f"objects rows: {page.locator('#objects-list .obj-row').count()}")
    # lambda filter + match
    try:
        page.fill("#lam-at", "3.3"); page.press("#lam-at", "Enter"); page.wait_for_timeout(1500)
        log["notes"].append(f"lam-at note: {(page.text_content('#lam-at-note') or '').strip()[:160]}")
    except Exception as e:
        log["notes"].append(f"lam-at: {str(e)[:150]}")
    # spectrum at centre
    try:
        if page.locator("#ph-centre").is_visible():
            page.click("#ph-centre")
            for _ in range(60):
                st = (page.text_content("#ph-status") or "")
                if page.locator("#ph-body svg").count() or "fail" in st.lower() or "error" in st.lower():
                    break
                page.wait_for_timeout(1000)
            log["notes"].append(f"photometry status: {(page.text_content('#ph-status') or '').strip()[:160]}")
            page.locator("#photometry").scroll_into_view_if_needed()
            shot(page, "barnard_spectrum")
        else:
            log["notes"].append("#ph-centre not visible")
    except Exception as e:
        log["notes"].append(f"photometry: {str(e)[:150]}")
    # keyboard shortcuts on stage
    try:
        page.locator("#stage").scroll_into_view_if_needed()
        page.click("#stage")
        for k in ["ArrowRight", "ArrowLeft", "d", "d", "p", "p", "m", "t", "t"]:
            page.keyboard.press(k); page.wait_for_timeout(300)
    except Exception as e:
        log["notes"].append(f"keys: {str(e)[:150]}")
    shot(page, "barnard_after_keys")


@scenario("map_tools")
def s_map(page, log):
    page.goto(WEB + "?ra=269.4463&dec=4.7682&size=15")
    wait_field(page)
    page.wait_for_timeout(4000)
    page.locator("#sky").scroll_into_view_if_needed()
    # blink toggle
    try:
        page.click("#blink-on"); page.wait_for_timeout(800); page.click("#blink-on")
    except Exception as e:
        log["notes"].append(f"blink-on: {str(e)[:120]}")
    # passes / survey buttons
    for sel in ["#explore-passes button", "#explore-survey button", "#map-tools button"]:
        n = page.locator(sel).count()
        log["notes"].append(f"{sel}: {n}")
        for i in range(min(n, 6)):
            try:
                b = page.locator(sel).nth(i)
                if b.is_visible() and b.is_enabled():
                    txt = (b.text_content() or "").strip()[:30]
                    b.click(); page.wait_for_timeout(1500)
                    log["notes"].append(f"clicked {sel}[{i}] '{txt}'")
            except Exception as e:
                log["notes"].append(f"{sel}[{i}]: {str(e)[:100]}")
    shot(page, "map_tools")
    # toggles in the map bar: outliers, flags
    for tid in ["#outliers-toggle", "#flags-toggle"]:
        try:
            if page.locator(tid).count():
                page.click(tid); page.wait_for_timeout(8000)
                shot(page, f"map_{tid[1:]}")
                page.click(tid); page.wait_for_timeout(500)
            else:
                log["notes"].append(f"{tid} missing")
        except Exception as e:
            log["notes"].append(f"{tid}: {str(e)[:120]}")
    # band slider: move
    try:
        sl = page.locator("#explore-band")
        if sl.count() and sl.is_visible():
            sl.fill("50"); page.wait_for_timeout(2000)
            log["notes"].append(f"band out: {(page.text_content('#explore-band-out') or '').strip()}")
            page.click("#band-colour"); page.wait_for_timeout(2000); page.click("#band-colour")
    except Exception as e:
        log["notes"].append(f"band: {str(e)[:120]}")
    # zoom with wheel on the map + drag
    try:
        box = page.locator("#sky").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(cx, cy)
        for _ in range(4):
            page.mouse.wheel(0, 600); page.wait_for_timeout(600)
        page.mouse.down(); page.mouse.move(cx + 120, cy + 40, steps=8); page.mouse.up()
        for _ in range(6):
            page.mouse.wheel(0, -600); page.wait_for_timeout(600)
        page.wait_for_timeout(4000)
        shot(page, "map_zoomed")
        log["notes"].append(f"map pos: {(page.text_content('#map-pos') or page.text_content('#explore-pos') or '').strip()[:120]}")
    except Exception as e:
        log["notes"].append(f"zoom: {str(e)[:120]}")


@scenario("chemistry")
def s_chem(page, log):
    page.goto(WEB + "?ra=246.79&dec=-24.54&size=30")
    wait_field(page)
    page.wait_for_timeout(4000)
    page.locator("#sky").scroll_into_view_if_needed()
    try:
        page.click("#chem-box summary"); page.wait_for_timeout(2500)
        shot(page, "chem_open")
        log["notes"].append(f"presets: {page.locator('.chem-preset').count()}, features: {page.locator('#chem-list .chem-row').count()}")
        log["notes"].append(f"z hint: {(page.text_content('#chem-z-hint') or '').strip()[:160]}; z={page.input_value('#chem-z')}")
        page.locator(".chem-preset").first.click()
        for _ in range(120):
            note = page.text_content("#chem-note") or ""
            if "one colour each" in note or "unavailable" in note or "not answering" in note:
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(3000)
        shot(page, "chem_preset1")
        log["notes"].append(f"note: {(page.text_content('#chem-note') or '').strip()[:220]}")
        # second preset
        page.click("#chem-box summary") if not page.locator("#chem-box[open]").count() else None
        page.locator(".chem-preset").nth(1).click()
        for _ in range(120):
            note = page.text_content("#chem-note") or ""
            if "Ices in cold clouds" in note and "one colour each" in note:
                break
            page.wait_for_timeout(1000)
        shot(page, "chem_preset2")
        # tick 4 more features by hand (any number)
        rows = page.locator("#chem-list .chem-row input")
        for i in range(rows.count()):
            if not rows.nth(i).is_checked():
                rows.nth(i).check(); page.wait_for_timeout(300)
                if page.locator("#chem-list .chem-row input:checked").count() >= 5:
                    break
        for _ in range(180):
            note = page.text_content("#chem-note") or ""
            if "with 5 colours" in note or "unavailable" in note:
                break
            page.wait_for_timeout(1000)
        shot(page, "chem_5")
        log["notes"].append(f"5-note: {(page.text_content('#chem-note') or '').strip()[:200]}")
        # z change while shown
        page.fill("#chem-z", "0.01"); page.press("#chem-z", "Enter"); page.locator("#chem-z").blur()
        page.wait_for_timeout(2000)
        log["notes"].append(f"after z: {(page.text_content('#chem-note') or '').strip()[:160]}")
        page.fill("#chem-z", "abc"); page.locator("#chem-z").blur(); page.wait_for_timeout(500)
        page.fill("#chem-z", "0"); page.locator("#chem-z").blur(); page.wait_for_timeout(1500)
        # clear
        if page.locator("#chem-clear").is_visible():
            page.click("#chem-clear")
        page.wait_for_timeout(1500)
        log["notes"].append(f"after clear: summary={(page.text_content('#chem-summary') or '').strip()}, note hidden={page.locator('#chem-note').is_hidden()}")
        shot(page, "chem_cleared")
    except Exception as e:
        log["notes"].append(f"chem: {str(e)[:200]}")


@scenario("chem_redshift")
def s_chemz(page, log):
    page.goto(WEB + "?ra=253.2454&dec=2.4009&size=10")
    wait_field(page)
    page.wait_for_timeout(3000)
    page.locator("#sky").scroll_into_view_if_needed()
    try:
        page.click("#chem-box summary")
        for _ in range(30):
            if page.input_value("#chem-z") not in ("0", ""):
                break
            page.wait_for_timeout(500)
        log["notes"].append(f"z={page.input_value('#chem-z')} hint={(page.text_content('#chem-z-hint') or '').strip()[:140]}")
        page.locator("#chem-list .chem-row", has_text="PAH").locator("input").check()
        for _ in range(120):
            note = page.text_content("#chem-note") or ""
            if "minus its continuum" in note or "unavailable" in note:
                break
            page.wait_for_timeout(1000)
        log["notes"].append(f"note: {(page.text_content('#chem-note') or '').strip()[:200]}")
        shot(page, "chemz_pah")
    except Exception as e:
        log["notes"].append(f"chemz: {str(e)[:200]}")


@scenario("tour")
def s_tour(page, log):
    page.goto(WEB + "?tour=1")
    page.wait_for_timeout(5000)
    shot(page, "tour_start")
    for i in range(6):
        btns = page.locator("button.primary", has_text=re.compile(r"Start|Next"))
        if not btns.count():
            log["notes"].append(f"no Next button at step {i}")
            break
        try:
            btns.first.click()
        except Exception as e:
            log["notes"].append(f"next {i}: {str(e)[:120]}")
            break
        name = wait_field(page, timeout=150)
        log["notes"].append(f"stop {i + 1}: {name}")
        page.wait_for_timeout(2000)
        shot(page, f"tour_stop{i + 1}")


@scenario("surprise_and_presets")
def s_surprise(page, log):
    page.goto(WEB)
    page.wait_for_timeout(4000)
    try:
        opts = page.locator("#preset option")
        log["notes"].append(f"quick picks: {opts.count()}")
        page.click("#surprise")
        name = wait_field(page, timeout=200)
        log["notes"].append(f"surprise: {name}  url={page.url[len(WEB):]}")
        shot(page, "surprise")
    except Exception as e:
        log["notes"].append(f"surprise: {str(e)[:150]}")


@scenario("bad_urls")
def s_bad(page, log):
    for q in ["?ra=abc&dec=xyz", "?ra=10&dec=100&size=15", "?ra=10&dec=5&size=99999", "?ra=10&dec=5&size=-3",
              "?lam=abc&ra=269.4463&dec=4.7682&size=15", "?ra=269.4463&dec=4.7682&size=15&detector=9",
              "?api=http://localhost:1", "?ra=%3Cscript%3Ealert(1)%3C/script%3E&dec=0"]:
        page.goto(WEB + q)
        page.wait_for_timeout(5000)
        msg = (page.text_content("#messages") or "").strip()
        err = (page.text_content("#stage-error") or "").strip() if visible(page, "#stage-error") else ""
        form = page.input_value("#field-form input[name=ra]") if page.locator("#field-form input[name=ra]").count() else ""
        log["notes"].append(f"{q} -> msg='{msg[:120]}' err='{err[:80]}' ra_box='{form}'")
    shot(page, "bad_last")


@scenario("form_inputs")
def s_form(page, log):
    page.goto(WEB)
    page.wait_for_timeout(3000)
    cases = [("08h55m10.8s", "-7d14m42.5s", "15"), ("133.795", "-7.245", "4"), ("133.795", "-7.245", "500"),
             ("", "", ""), ("361", "0", "15"), ("12:00:00", "+91:00:00", "15")]
    for ra, dec, size in cases:
        try:
            page.fill("#field-form input[name=ra]", ra)
            page.fill("#field-form input[name=dec]", dec)
            if page.locator("#field-form input[name=size]").count():
                page.fill("#field-form input[name=size]", size)
            page.click("#field-form button[type=submit]")
            page.wait_for_timeout(2500)
            msg = (page.text_content("#messages") or "").strip()
            valid = page.evaluate("() => [...document.querySelectorAll('#field-form input')].map(i => i.name + ':' + i.validationMessage).join(' | ')")
            log["notes"].append(f"({ra!r},{dec!r},{size!r}) -> msg='{msg[:110]}' validity='{valid[:140]}' url={page.url[len(WEB):][:60]}")
        except Exception as e:
            log["notes"].append(f"form {ra}: {str(e)[:120]}")
    shot(page, "form_last")


@scenario("phone")
def s_phone(page, log):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(WEB + "?ra=246.79&dec=-24.54&size=30")
    wait_field(page)
    page.wait_for_timeout(4000)
    sw = page.evaluate("() => document.documentElement.scrollWidth")
    log["notes"].append(f"scrollWidth={sw}")
    wide = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect();
        return r.width > 0 && r.right > window.innerWidth + 1 && getComputedStyle(e).position !== 'fixed'; })
        .slice(0, 12).map(e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + [...e.classList].join('.')) + ':' + Math.round(e.getBoundingClientRect().right))""")
    log["notes"].append(f"elements past the right edge: {wide}")
    shot(page, "phone_top")
    try:
        page.click("#chem-box summary"); page.wait_for_timeout(1500)
        shot(page, "phone_chem_open")
        sw2 = page.evaluate("() => document.documentElement.scrollWidth")
        log["notes"].append(f"scrollWidth with chemistry open={sw2}")
    except Exception as e:
        log["notes"].append(f"phone chem: {str(e)[:120]}")
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight / 2)")
    page.wait_for_timeout(1000)
    shot(page, "phone_mid")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for fn in SCEN:
            if ONLY and fn._name not in ONLY:
                continue
            ctx = b.new_context(viewport={"width": 1400, "height": 1000})
            page = ctx.new_page()
            log = {"pageerror": [], "console": [], "failed": [], "http": [], "notes": []}
            attach(page, log)
            t0 = time.time()
            try:
                fn(page, log)
            except Exception as e:
                log["notes"].append(f"SCENARIO CRASH: {str(e)[:300]}")
                try:
                    shot(page, fn._name + "_crash")
                except Exception:
                    pass
            log["seconds"] = round(time.time() - t0)
            report[fn._name] = log
            ctx.close()
            print(f"== {fn._name} ({log['seconds']} s): pageerror {len(log['pageerror'])}, console {len(log['console'])}, "
                  f"http>=400 {len(log['http'])}, failed {len(log['failed'])}", flush=True)
        b.close()
    (OUT / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))


main()
