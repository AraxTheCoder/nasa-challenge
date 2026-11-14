"""Run the Live API and the viewer together, then open the viewer in the browser.

    python web/dev.py                 # fixture or live, whichever works right now (see below)
    python web/dev.py --fixture       # always the synthetic demo field, no network needed
    python web/dev.py --live          # real SPHEREx data from IRSA (needs pipeline.build)
    python web/dev.py --lan           # let teammates on the same network open it too

Starts `python -m server` (the Live API) and a small static server for the viewer, prints the URL,
opens it, and stops both on Ctrl+C. Works on Linux, macOS, Windows and WSL.

Default mode: live if `pipeline.build` exists (track A, T02-T04), otherwise fixture.
The static server only serves `web/` and `fixtures/`, never the rest of the repo.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import posixpath
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parent.parent
SERVED = ("/web/", "/fixtures/")  # only these folders are reachable over HTTP


def allowed(raw_path: str) -> bool:
    """Only paths inside SERVED, judged after decoding and normalising (no `..` or %2e%2e tricks)."""
    path = posixpath.normpath(unquote(raw_path.split("?", 1)[0].split("#", 1)[0]))
    return any(path == p.rstrip("/") or path.startswith(p) for p in SERVED)


class ViewerHandler(SimpleHTTPRequestHandler):
    """Static files from the repo root, restricted to SERVED; `/` redirects to `/web/`."""

    def do_GET(self):  # noqa: N802 (stdlib naming)
        path, _, query = self.path.partition("?")
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/web/" + (f"?{query}" if query else ""))
            self.end_headers()
            return
        if not allowed(self.path):
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):  # noqa: N802
        if not allowed(self.path):
            self.send_error(404)
            return
        super().do_HEAD()

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")  # always load the latest JS while developing
        super().end_headers()

    def log_message(self, *args):  # keep the terminal quiet
        pass


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":
            # Same as uvicorn/http.server: a port in TIME_WAIT after a restart counts as free.
            # (Not on Windows, where SO_REUSEADDR would let us bind over a live server.)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def lan_ip() -> str:
    """Best guess of this machine's address on the local network."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))  # TEST-NET address, nothing is sent
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def open_browser(url: str) -> None:
    if "microsoft" in platform.uname().release.lower():  # WSL: open the Windows browser
        opener = shutil.which("wslview") or shutil.which("explorer.exe")
        if opener:
            subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return  # headless Linux: don't start a text-mode browser in this terminal
    webbrowser.open(url)


def wait_for_api(url: str, proc: subprocess.Popen, timeout: float = 30) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.3)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(prog="python web/dev.py", description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--fixture", action="store_true", help="serve the synthetic demo field for every request")
    mode.add_argument("--live", action="store_true", help="build fields from real SPHEREx data")
    ap.add_argument("--api-port", type=int, default=8000)
    ap.add_argument("--web-port", type=int, default=8080)
    ap.add_argument("--lan", action="store_true", help="listen on all interfaces so others on your network can open it")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # show the URL even when output is piped

    sys.path.insert(0, str(REPO))
    missing = [m for m in ("fastapi", "uvicorn") if not has_module(m)]
    if missing:
        print(f"Missing Python packages: {', '.join(missing)}. Install them (inside your venv) with:\n"
              f"  python -m pip install -r server/requirements.txt", file=sys.stderr)
        return 1

    if args.live:
        fixture = False
    elif args.fixture:
        fixture = True
    else:
        fixture = not has_module("pipeline.build")

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    for name, port in (("API", args.api_port), ("viewer", args.web_port)):
        if not port_free(host, port):
            flag = "--api-port" if name == "API" else "--web-port"
            print(f"Port {port} for the {name} is already in use (another server still running?).\n"
                  f"Stop it, or pick another port, e.g.  python web/dev.py {flag} {port + 1}", file=sys.stderr)
            return 1

    cmd = [sys.executable, "-m", "server", "--host", host, "--port", str(args.api_port)]
    if fixture:
        cmd.append("--fixture")
    api = subprocess.Popen(cmd, cwd=REPO)

    web = ThreadingHTTPServer((host, args.web_port), partial(ViewerHandler, directory=str(REPO)))
    threading.Thread(target=web.serve_forever, daemon=True).start()

    try:
        if not wait_for_api(f"http://127.0.0.1:{args.api_port}/api/health", api):
            print("The Live API did not start; see the error above.", file=sys.stderr)
            return 1

        shown_host = lan_ip() if args.lan else "localhost"
        url = f"http://{shown_host}:{args.web_port}/web/"
        if args.api_port != 8000:  # the viewer looks for the API on port 8000 of the page's host
            url += f"?api=http://{shown_host}:{args.api_port}"
        print()
        print(f"  Viewer:   {url}")
        print(f"  Live API: http://{shown_host}:{args.api_port}  "
              f"({'fixture mode: every field is the synthetic demo' if fixture else 'live SPHEREx data'})")
        if args.lan:
            print("  Others on your network can open the viewer URL (allow it in your firewall if asked).")
        print("  Ctrl+C stops both.\n")
        if not args.no_browser:
            open_browser(url)
        api.wait()
        return api.returncode or 0
    except KeyboardInterrupt:
        return 0
    finally:
        web.shutdown()
        if api.poll() is None:
            api.terminate()
            try:
                api.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api.kill()


if __name__ == "__main__":
    sys.exit(main())
