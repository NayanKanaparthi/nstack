"""The factory dashboard server: the board in a browser, on this computer only, read-only.

Started by `factory dashboard` (scripts/factory.py loads this file by path and calls run()).
Python 3.9, standard library only. Importing this module does nothing: no bind, no thread, no
print, no file access. The server answers GET and HEAD, serves five fixed files and one JSON
endpoint, and never writes anything anywhere.

Public names: api(query), bind(start_port, tries=20), Handler, run(...), ROUTES, NoFreePort.
"""
import errno
import http.server
import importlib
import json
import os
import re
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs

HERE = Path(__file__).resolve().parent
KIT_SCRIPTS = HERE.parent / "scripts"

LOOPBACK = "127.0.0.1"
DEFAULT_PORT = 7878
PORT_TRIES = 20

BUILD_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
MAX_QUERY = 300

MSG_BAD_NAME = "That build name is not valid."
MSG_MISSING_KIT = "The dashboard could not find the kit's scripts folder next to it."
MSG_UNREADABLE = "This build's log could not be read."
MSG_INTERNAL = "The factory view could not be loaded. Try again in a moment."

CACHE_FLOOR_S = 1.0

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = (
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Content-Security-Policy", CSP),
)

HTML = "text/html; charset=utf-8"
JS = "text/javascript; charset=utf-8"
CSS = "text/css; charset=utf-8"
SVG = "image/svg+xml"
JSON_TYPE = "application/json; charset=utf-8"
TEXT = "text/plain; charset=utf-8"

# The fixed route table: a request path maps to a fixed answer. No part of a request path is ever
# joined to a file path, so there is no reading by name, no folder listing and no `..` handling.
ROUTES = {
    "/": ("file", "index.html", HTML),
    "/index.html": ("file", "index.html", HTML),
    "/app.js": ("file", "app.js", JS),
    "/style.css": ("file", "style.css", CSS),
    "/mark.svg": ("file", "mark.svg", SVG),
    "/favicon.ico": ("empty", None, None),
    "/api/factory": ("api", None, JSON_TYPE),
}

_lock = threading.Lock()
_cache = {}  # key -> (signature, stamp, result)

# The environment the server was started with decides which factory home it reads (and the clock
# the board uses), even if the program that started it changes its own environment afterwards.
_ENV_KEYS = ("FACTORY_HOME", "FACTORY_NOW", "HOME")
_env_lock = threading.Lock()
_bound_env = {}


class NoFreePort(Exception):
    """Every port from `first` to `last` was taken."""

    def __init__(self, first, last):
        Exception.__init__(self, "ports %d to %d are all in use" % (first, last))
        self.first = first
        self.last = last


# ---------------------------------------------------------------------------
# data: the board, shaped exactly like the endpoint of the private dashboard
# ---------------------------------------------------------------------------

def _kit():
    """The factorylib module, or None when the kit scripts are not beside the dashboard."""
    if not KIT_SCRIPTS.is_dir():
        return None
    path = str(KIT_SCRIPTS)
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        return importlib.import_module("factorylib")
    except Exception:
        return None


class _EnvScope(object):
    """Apply the start-time environment for one data read, only when it differs from now."""

    def __init__(self):
        self.saved = None

    def __enter__(self):
        diff = {}
        for key in _ENV_KEYS:
            if key in _bound_env and os.environ.get(key) != _bound_env[key]:
                diff[key] = _bound_env[key]
        if diff:
            _env_lock.acquire()
            self.saved = {key: os.environ.get(key) for key in diff}
            for key, value in diff.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return self

    def __exit__(self, *_exc):
        if self.saved is not None:
            for key, value in self.saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            _env_lock.release()
        return False


def _stat_key(path):
    try:
        st = path.stat()
        return (str(path), st.st_size, st.st_mtime_ns)
    except OSError:
        return (str(path), None, None)


def _signature(root, selected):
    """Cheap fingerprint of every log under root plus the selected build's other files."""
    parts = []
    try:
        projects = sorted(os.listdir(str(root)))
    except OSError:
        return ()
    for project in projects:
        folder = root / project
        try:
            builds = sorted(os.listdir(str(folder)))
        except OSError:
            continue
        for build in builds:
            parts.append(_stat_key(folder / build / "trace.jsonl"))
            parts.append(_stat_key(folder / build / "build.json"))
    if selected:
        parts.append(_stat_key(root / selected / "log-errors.jsonl"))
        parts.append(_stat_key(root / selected / "messages"))
        # the plan: plan.json, and the folder itself so a new plan-<stamp>.json is noticed
        parts.append(_stat_key(root / selected / "plan.json"))
        parts.append(_stat_key(root / selected))
    return tuple(parts)


def _error(message, status=200):
    return status, {"ok": False, "error": message}


def _payload(lib, home, wanted):
    root = lib.runs_root(home)
    builds = lib.list_builds(home)
    if wanted is None:
        if not builds:
            return 200, {"ok": True, "builds": [], "selected": None, "board": None}
        wanted = "%s/%s" % (builds[0]["project"], builds[0]["id"])
    project, build = wanted.split("/", 1)
    build_dir = root / project / build
    if not build_dir.is_dir():
        return _error("No build called %s." % wanted, 404)
    trace = build_dir / "trace.jsonl"
    if not trace.exists():
        return _error("No build called %s." % wanted, 404)
    if not trace.is_file():
        return _error(MSG_UNREADABLE)
    board = lib.board(build_dir)
    return 200, {"ok": True, "builds": builds, "selected": wanted, "board": board}


def api(query=""):
    """Answer a GET /api/factory request. `query` is the text after the question mark.

    Returns (http status, json-able dict). It never raises: every failure is a plain sentence in
    {"ok": false, "error": ...}.
    """
    try:
        if len(query or "") > MAX_QUERY:
            return _error(MSG_BAD_NAME, 400)
        params = parse_qs(query or "", keep_blank_values=True)
        wanted = None
        if "build" in params:
            wanted = params["build"][0]
            parts = wanted.split("/")
            if not BUILD_RE.fullmatch(wanted) or any(p in (".", "..") for p in parts):
                return _error(MSG_BAD_NAME, 400)
        lib = _kit()
        if lib is None:
            return _error(MSG_MISSING_KIT)
        with _EnvScope():
            home = lib.home()
            root = lib.runs_root(home)
            key = (str(home), wanted)
            signature = _signature(root, wanted)
            now = time.monotonic()
            with _lock:
                hit = _cache.get(key)
            if hit and hit[0] == signature and now - hit[1] < CACHE_FLOOR_S:
                return hit[2]
            result = _payload(lib, home, wanted)
            if result[0] == 200 and result[1].get("ok"):
                with _lock:
                    if len(_cache) > 64:
                        _cache.clear()
                    _cache[key] = (signature, now, result)
            return result
    except Exception:
        return _error(MSG_INTERNAL)


def _json_bytes(payload):
    """JSON text with no angle bracket and no ampersand: they leave as escape codes."""
    try:
        text = json.dumps(payload, ensure_ascii=False)
        raw = text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        return raw.encode("utf-8")
    except (UnicodeEncodeError, ValueError):
        text = json.dumps(payload)
        return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").encode("ascii")


# ---------------------------------------------------------------------------
# the request handler
# ---------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "factory-dashboard"
    sys_version = ""
    protocol_version = "HTTP/1.0"
    timeout = 10

    def version_string(self):
        return self.server_version

    def log_message(self, *_args):
        """No access log."""

    def end_headers(self):
        """Every answer, including the library's own error pages, carries the safety headers."""
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)
        http.server.BaseHTTPRequestHandler.end_headers(self)

    def send_error(self, code, message=None, explain=None):
        """The library's own answers for broken requests stay below 500."""
        if code >= 500:
            code, message, explain = 400, None, None
        http.server.BaseHTTPRequestHandler.send_error(self, code, message, explain)

    def __getattr__(self, name):
        # Any method name the library does not know reaches the same read-only answer.
        if name.startswith("do_"):
            return self._read_only
        raise AttributeError(name)

    # -- answers ----------------------------------------------------------

    def _send(self, status, content_type, body, head, extra=()):
        try:
            self.send_response(status)
            if status != 204:
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
            for name, value in extra:
                self.send_header(name, value)
            self.end_headers()
            if not head and status != 204:
                self.wfile.write(body)
        except (OSError, ValueError):
            self.close_connection = True

    def _host_ok(self):
        host = self.headers.get("Host")
        if host is None:
            return False
        port = self.server.server_address[1]
        return host.strip().lower() in ("%s:%d" % (LOOPBACK, port), "localhost:%d" % port)

    def _resolve(self):
        """(status, content type, body) for a GET or HEAD. Never raises."""
        if not self._host_ok():
            return 403, TEXT, b"Forbidden."
        path, _sep, query = self.path.partition("?")
        route = ROUTES.get(path)
        if route is None:
            return 404, TEXT, b"Not found."
        kind, filename, content_type = route
        if kind == "empty":
            return 204, None, b""
        if kind == "api":
            try:
                status, payload = api(query)
                return status, content_type, _json_bytes(payload)
            except Exception:
                body = _json_bytes({"ok": False, "error": MSG_INTERNAL})
                return 200, content_type, body
        try:
            return 200, content_type, (HERE / filename).read_bytes()
        except Exception:
            return 404, TEXT, b"Not found."

    def _answer(self, head):
        try:
            status, content_type, body = self._resolve()
        except Exception:
            status, content_type, body = 404, TEXT, b"Not found."
        self._send(status, content_type, body, head)

    def do_GET(self):
        self._answer(False)

    def do_HEAD(self):
        self._answer(True)

    def _read_only(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if 0 < length <= 65536:
                self.rfile.read(length)
        except Exception:
            pass
        self._send(405, TEXT, b"Read only.", self.command == "HEAD", (("Allow", "GET, HEAD"),))


# ---------------------------------------------------------------------------
# bind and run
# ---------------------------------------------------------------------------

class DashboardServer(http.server.ThreadingHTTPServer):
    """Loopback only. Never shares a port another program already holds."""

    allow_reuse_address = False
    daemon_threads = True

    def handle_error(self, request, client_address):
        """A client that hangs up halfway is not worth a stack trace."""


def bind(start_port, tries=PORT_TRIES):
    """Bind 127.0.0.1 on start_port, else the next free port, up to `tries` ports in all.

    Returns (server, port). Port 0 means any free port. Raises NoFreePort when all are taken and
    OSError for any other bind error.
    """
    global _bound_env
    _bound_env = {key: os.environ.get(key) for key in _ENV_KEYS}
    if start_port == 0:
        httpd = DashboardServer((LOOPBACK, 0), Handler)
        return httpd, httpd.server_address[1]
    last = min(start_port + tries - 1, 65535)
    for port in range(start_port, last + 1):
        try:
            return DashboardServer((LOOPBACK, port), Handler), port
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                raise
    raise NoFreePort(start_port, last)


def _say(stream, text):
    try:
        stream.write(text + "\n")
        stream.flush()
    except (OSError, ValueError):
        pass


def _open_browser(url):
    """Open the address in a browser. Says so on stderr when it could not; never fails over it."""
    opened = False
    try:
        choice = os.environ.get("BROWSER", "").split(os.pathsep)[0].strip()
        if choice:
            opened = webbrowser.get(choice).open(url)
        else:
            opened = webbrowser.open(url)
    except Exception:
        opened = False
    if not opened:
        _say(sys.stderr, "factory: could not open a browser. Open the address above yourself.")


def _stop_signal(_signum, _frame):
    raise KeyboardInterrupt


def run(port=DEFAULT_PORT, open_browser=True, build=None):
    """Bind, announce, serve until Ctrl-C or SIGTERM, then stop. Returns the exit code."""
    try:
        httpd, used = bind(port)
    except NoFreePort as exc:
        _say(sys.stderr, "factory: ports %d to %d are all in use. Pass a different --port." % (exc.first, exc.last))
        return 1
    except OSError as exc:
        _say(sys.stderr, "factory: could not start the dashboard (%s)." % (exc.strerror or exc))
        return 1
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _stop_signal)
        signal.signal(signal.SIGTERM, _stop_signal)
    address = "http://%s:%d/" % (LOOPBACK, used)
    if build:
        address += "?build=" + build
    try:
        if port != 0 and used != port:
            _say(sys.stdout, "Port %d is in use, so the dashboard is on port %d." % (port, used))
            time.sleep(0.03)  # the notice and the address arrive as two separate reads
        _say(sys.stdout, "Factory dashboard: " + address)
        _say(sys.stdout, "It updates by itself while agents work. Press Ctrl-C to stop.")
        if open_browser:
            threading.Thread(target=_open_browser, args=(address,), daemon=True).start()
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        httpd.server_close()
    _say(sys.stdout, "Factory dashboard stopped.")
    return 0
