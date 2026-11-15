"""Hover/focus/tap detail regression, without API calls or external services.

    python web/tests/analysis_browser_test.py [screenshot_dir]
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    root = Path(__file__).resolve().parents[2]
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="analysis-details-"))
    out.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1000, "height": 700})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/web/tests/")
            page.set_content('<link rel="stylesheet" href="/web/style.css"><div id="outside">Outside</div>'
                             '<section id="notes" style="position:absolute;top:480px;left:700px;width:260px;'
                             'overflow:hidden;transform:translateX(0)"></section>')
            page.evaluate('''async () => {
                const {analysisNote} = await import('/web/analysisnote.js');
                const box=document.querySelector('#notes');
                box.append(analysisNote('Baseline: simplified model',
                  'A fitted approximation, not a measured stellar temperature. Blending and calibration can affect it.'));
                box.append(analysisNote('Possible chemistry match',
                  'Identity unconfirmed. A wavelength match alone does not establish a molecule or object.'));
                window.otherEscape=0;
                document.addEventListener('keydown', e => {if(e.key==='Escape') window.otherEscape++;});
            }''')
            first = page.get_by_role("button", name="Baseline: simplified model")
            assert page.locator(".analysis-detail:visible").count() == 0
            first.hover()
            page.locator(".analysis-detail:visible").wait_for()
            assert "not a measured" in page.locator(".analysis-detail:visible").inner_text()
            rect = page.locator(".analysis-detail:visible").bounding_box()
            page.mouse.move(rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
            assert page.locator(".analysis-detail:visible").count() == 1, "detail stays hoverable"
            page.keyboard.press("Escape")
            assert page.locator(".analysis-detail:visible").count() == 0
            assert page.evaluate("window.otherEscape") == 0, "Escape dismisses the hint without operating other tools"
            first.focus()
            assert first.get_attribute("aria-expanded") == "true"
            page.keyboard.press("Escape")
            assert first.get_attribute("aria-expanded") == "false"
            first.click()
            assert page.locator(".analysis-detail:visible").count() == 1
            page.locator("#outside").click()
            assert page.locator(".analysis-detail:visible").count() == 0
            page.set_viewport_size({"width": 390, "height": 844})
            page.eval_on_selector("#notes", "e=>Object.assign(e.style,{left:'250px',top:'750px',width:'120px'})")
            first.hover()
            rect = page.locator(".analysis-detail:visible").bounding_box()
            assert rect["x"] >= 0 and rect["x"] + rect["width"] <= 390, rect
            assert rect["y"] >= 0 and rect["y"] + rect["height"] <= 844, rect
            page.screenshot(path=str(out / "analysis-details-phone.png"))
            page.eval_on_selector("#notes .analysis-note", "e=>e.remove()")
            page.get_by_role("button", name="Possible chemistry match").hover()
            assert page.locator(".analysis-detail:visible").count() == 1, "panel rerender leaves no stale popover"
            # Render the actual analysis panel against controlled cached API data.
            page.set_viewport_size({"width": 1000, "height": 850})
            page.goto(f"http://127.0.0.1:{server.server_port}/web/tests/")
            page.set_content('<link rel="stylesheet" href="/web/style.css"><div id="analysis-top"></div><div id="sky"></div>')
            page.route("**/web/viewer.js", lambda route: route.fulfill(content_type="text/javascript", body=
                "export const targetBase=()=>location.origin+'/api/targets/test/';"
                "export const currentTarget=()=>null,currentPair=()=>null;"
                "export const showFrame=()=>{},selectPair=()=>{},checkTarget=()=>[],showTarget=()=>{},clearTarget=()=>{},stopBlink=()=>{},initViewer=()=>{},isSynthetic=()=>false;"))
            payload = {"status": "ready", "summary": "Long computed summary", "n_judged": 20,
                       "field": {"n_sources": 25, "n_exposures": 100}, "points": [], "not_judged": [],
                       "items": [{"id": "s1", "name": "Test source", "ra_deg": 10, "dec_deg": 20, "score": 8,
                                  "peer_group": "stars", "bands_um": [3.2, 3.4], "residual_pct": [-40, -45],
                                  "deviations": [{"um_min": 3.2, "um_max": 3.4, "pct": -45, "z": 8, "n_bands": 2,
                                                  "epochs_agree": 2, "epochs_seen": 2, "meaning": "methane absorption?"}]}],
                       "chemistry_profiles": {"method": "Two-feature numerical comparison", "matches": [
                           {"id": "s1", "name": "Test source", "profile_name": "Brown dwarfs", "profile": "brown_dwarfs", "ra_deg": 10, "dec_deg": 20,
                            "redshift_origin": "rest", "features": [{"feature": "ch4", "name": "CH₄", "status": "detected",
                                                                    "pct": -45, "significance": -8, "epochs_agree": 2, "epochs_seen": 2}],
                            "caveats": ["Pattern only; identity unconfirmed."]}]},
                       "redshifts": {"sources": [{"id": "g1", "name": "Galaxy", "ra_deg": 11, "dec_deg": 20,
                                                    "status": "insufficient_evidence", "alternatives": []}]}}
            import json
            page.route("**/spectral-outliers*", lambda route: route.fulfill(content_type="application/json", body=json.dumps(payload)))
            page.evaluate("async()=>{await import('/web/outliers.js');document.dispatchEvent(new CustomEvent('viewer:target',{detail:{target:{id:'test',synthetic:false}}}));}")
            page.wait_for_selector("#outliers:not([hidden])")
            visible = page.locator("#ol-body").inner_text()
            assert "tentative" in visible and "identities unconfirmed" in visible
            assert "null" not in visible and "Long computed summary" not in visible
            assert "1 unresolved shift" in visible
            candidate = page.get_by_role("button", name="Possible brown dwarf")
            candidate.hover()
            assert "identity unconfirmed" in page.locator(".analysis-detail:visible").inner_text()
            page.screenshot(path=str(out / "analysis-panel-details.png"))
            assert not errors, errors
            browser.close()
        print("PASS analysis details: hover/focus/click, Escape/outside dismissal, mobile fit and panel rerender")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
