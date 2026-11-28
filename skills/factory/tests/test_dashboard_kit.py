"""Acceptance tests for the standalone, read-only factory dashboard."""

import ast
import contextlib
import http.client
import importlib.util
import io
import json
import os
import py_compile
import random
import re
import select
import signal
import socket
import subprocess
import sys
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from tests.common import (FACTORY_PY, FIXTURES, KIT_DIR, PYTHON, SCRIPTS_DIR,
                          FactoryTestCase, tree_snapshot, write_json, write_jsonl)


DASHBOARD = KIT_DIR / "dashboard"
BLOCKED_PORT = 4200 + 42
BLOCKED_PORT_NEXT = 4200 + 43
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": CSP,
}


def snapshot_without_script_caches(root):
    """T-DB-12 correction: ignore only caches below the kit scripts folder."""
    root = Path(root)
    answer = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in path.parts:
            try:
                path.relative_to(SCRIPTS_DIR)
            except ValueError:
                pass
            else:
                continue
        answer[str(relative)] = path.read_bytes()
    return answer


class DashboardTestCase(FactoryTestCase):
    def setUp(self):
        super().setUp()
        fake = self.fake_program("no-notify", "raise SystemExit(0)")
        self.env["FACTORY_OSASCRIPT_BIN"] = str(fake)
        self._started = []

    def free_port(self):
        for _ in range(20):
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            if port not in (BLOCKED_PORT, BLOCKED_PORT_NEXT):
                return port
        self.fail("could not obtain a safe free loopback port")

    def _cleanup_process(self, proc):
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)
            try:
                proc.wait(timeout=0.95)
            except subprocess.TimeoutExpired:
                self.fail("saved dashboard PID did not stop after SIGKILL")
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

    def require_dashboard_command(self):
        source = FACTORY_PY.read_text()
        self.assertIn("def cmd_dashboard(", source,
                      "planned command missing: factory dashboard")

    def start(self, *args, **kwargs):
        self.require_dashboard_command()
        child_env = dict(self.env)
        child_env.update(kwargs.get("env") or {})
        command = [PYTHON, str(FACTORY_PY), "dashboard", "--no-open"] + list(args)
        if kwargs.get("open_browser"):
            command.remove("--no-open")
        proc = subprocess.Popen(
            command, cwd=str(kwargs.get("cwd") or self.project), env=child_env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._started.append(proc.pid)
        self.addCleanup(self._cleanup_process, proc)
        lines = []
        deadline = time.monotonic() + 0.95
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([proc.stdout], [], [], remaining)
            if not ready:
                break
            line = proc.stdout.readline()
            if not line:
                break
            lines.append(line.rstrip("\n"))
            if line.startswith("Factory dashboard: "):
                return proc, lines, line.strip().split(": ", 1)[1]
        stderr = proc.stderr.read() if proc.poll() is not None else ""
        self.fail("planned dashboard command did not print its address: %s%s" %
                  ("\n".join(lines), stderr))

    def stop(self, proc, signum=signal.SIGTERM):
        os.kill(proc.pid, signum)
        try:
            code = proc.wait(timeout=0.95)
        except subprocess.TimeoutExpired:
            self.fail("dashboard PID did not stop within 0.95 seconds")
        stdout = proc.stdout.read()
        stderr = proc.stderr.read()
        return code, stdout, stderr

    def load_server(self):
        path = DASHBOARD / "server.py"
        self.assertTrue(path.is_file(), "planned module missing: skills/factory/dashboard/server.py")
        name = "factory_dashboard_server_test_%d" % id(self)
        spec = importlib.util.spec_from_file_location(name, str(path))
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, self.env, clear=True):
            spec.loader.exec_module(module)
        return module

    def serve_in_thread(self):
        server = self.load_server()
        with mock.patch.dict(os.environ, self.env, clear=True):
            httpd, port = server.bind(0, tries=1)
        thread = threading.Thread(target=httpd.serve_forever,
                                  kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return server, httpd, port

    def request(self, port, method, path, host=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.9)
        headers = {}
        if host is not None:
            connection.putrequest(method, path, skip_host=True)
            connection.putheader("Host", host)
            if body is not None:
                connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body)
        else:
            connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        result = response.status, dict(response.getheaders()), data
        connection.close()
        return result

    def raw(self, port, payload):
        sock = socket.socket()
        sock.settimeout(0.9)
        try:
            sock.connect(("127.0.0.1", port))
            sock.sendall(payload)
            chunks = []
            while True:
                try:
                    chunk = sock.recv(65536)
                except (ConnectionResetError, socket.timeout):
                    break
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            sock.close()


class DashboardCommandTests(DashboardTestCase):
    def test_T_DB_01_start_serve_and_stop(self):
        """T-DB-01: command prints promptly, serves the page, and stops by saved PID."""
        self.require_dashboard_command()
        port = self.free_port()
        proc, lines, _ = self.start("--port", str(port))
        self.assertEqual(lines, ["Factory dashboard: http://127.0.0.1:%d/" % port])
        second = proc.stdout.readline().rstrip("\n")
        self.assertEqual(second, "It updates by itself while agents work. Press Ctrl-C to stop.")
        status, _, body = self.request(port, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'id="view-factory"', body)
        code, stdout, stderr = self.stop(proc)
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip().splitlines()[-1], "Factory dashboard stopped.")
        self.assertEqual(stderr, "")

    def test_T_DB_02_loopback_import_and_server_class(self):
        """T-DB-02: import is inert and bind is loopback-only without address reuse."""
        before = threading.active_count()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            server = self.load_server()
        self.assertEqual(threading.active_count(), before)
        self.assertEqual(stdout.getvalue(), "")
        httpd, _ = server.bind(0, tries=1)
        self.addCleanup(httpd.server_close)
        self.assertEqual(httpd.server_address[0], "127.0.0.1")
        self.assertIs(type(httpd).allow_reuse_address, False)
        self.assertIs(type(httpd).daemon_threads, True)
        source = (DASHBOARD / "server.py").read_text() + FACTORY_PY.read_text()
        for forbidden in ("0.0.0.0", '"::"', "INADDR_ANY"):
            self.assertNotIn(forbidden, source)

    def test_T_DB_03_system_selected_port(self):
        """T-DB-03: --port 0 uses a safe loopback ephemeral port."""
        proc, lines, address = self.start("--port", "0")
        match = re.fullmatch(r"http://127\.0\.0\.1:(\d+)/", address)
        self.assertIsNotNone(match, address)
        port = int(match.group(1))
        self.assertTrue(1024 <= port <= 65535)
        self.assertNotIn("is in use", "\n".join(lines))
        self.assertEqual(self.request(port, "GET", "/")[0], 200)
        self.stop(proc)

    def test_T_DB_04_flags_help_and_build_selection(self):
        """T-DB-04: exact validation errors, help flags, and selected-build URL."""
        self.require_dashboard_command()
        self.install_fixture("alpha")
        port = self.free_port()
        cases = [
            (("dashboard", "--port", "80"), 2,
             "factory: --port must be 0 or a number from 1024 to 65535.\n"),
            (("dashboard", "--port", "70000"), 2,
             "factory: --port must be 0 or a number from 1024 to 65535.\n"),
            (("dashboard", "--port", "abc"), 2,
             "factory: --port must be 0 or a number from 1024 to 65535.\n"),
            (("dashboard", "--build", "../x"), 2,
             "factory: --build must look like project/id, for example demo/alpha.\n"),
            (("dashboard", "--build", "demo"), 2,
             "factory: --build must look like project/id, for example demo/alpha.\n"),
            (("dashboard", "--build", "demo/zzz"), 3,
             "factory: no build called demo/zzz. See the builds with: factory status --all\n"),
        ]
        for args, code, error in cases:
            result = self.run_factory(*args)
            with self.subTest(args=args):
                self.assertEqual(result.returncode, code)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, error)
                self.assertNotIn("Traceback", result.stderr)
        unknown = self.run_factory("dashboard", "--foo")
        self.assertEqual(unknown.returncode, 2)
        self.assertTrue(unknown.stderr.startswith("factory: "))
        self.assertTrue(unknown.stderr.rstrip().endswith("(try: factory dashboard --help)"))
        help_result = self.run_factory("dashboard", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for flag in ("--port", "--no-open", "--build"):
            self.assertIn(flag, help_result.stdout)
        proc, _, address = self.start("--port", str(port), "--build", "demo/alpha")
        self.assertEqual(address, "http://127.0.0.1:%d/?build=demo/alpha" % port)
        self.stop(proc)

    def test_T_DB_05_fake_browser_success_failure_and_no_open(self):
        """T-DB-05: only the explicit command uses the configured fake browser."""
        self.require_dashboard_command()
        out = self.tmp / "browser-out"
        fake = self.fake_program(
            "fake-open", "import os, pathlib, sys\n"
            "pathlib.Path(os.environ['OUT']).write_text(' '.join(sys.argv[1:]))\n"
            "raise SystemExit(int(os.environ['CODE']))")
        for code in ("0", "1"):
            port = self.free_port()
            env = {"BROWSER": str(fake), "OUT": str(out), "CODE": code}
            if out.exists():
                out.unlink()
            proc, _, address = self.start("--port", str(port), env=env, open_browser=True)
            deadline = time.monotonic() + 0.95
            while time.monotonic() < deadline and not out.exists():
                time.sleep(0.01)
            self.assertEqual(out.read_text(), address)
            self.assertEqual(self.request(port, "GET", "/")[0], 200)
            _, _, stderr = self.stop(proc)
            expected = "" if code == "0" else (
                "factory: could not open a browser. Open the address above yourself.\n")
            self.assertEqual(stderr, expected)
        out.unlink()
        port = self.free_port()
        proc, _, _ = self.start("--port", str(port), env=env)
        self.assertEqual(self.request(port, "GET", "/")[0], 200)
        self.assertFalse(out.exists())
        self.stop(proc)

    def test_T_DB_06_taken_port_moves_without_sharing(self):
        """T-DB-06: a taken loopback port moves forward and remains owned by its holder."""
        self.require_dashboard_command()
        held = socket.socket()
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        self.addCleanup(held.close)
        port = held.getsockname()[1]
        self.assertNotIn(port, (BLOCKED_PORT, BLOCKED_PORT_NEXT))
        proc, lines, address = self.start("--port", str(port))
        self.assertRegex(lines[0], r"^Port %d is in use, so the dashboard is on port \d+\.$" % port)
        used = int(re.search(r":(\d+)/$", address).group(1))
        self.assertTrue(port < used <= port + 19)
        self.assertEqual(self.request(used, "GET", "/")[0], 200)
        probe = socket.create_connection(("127.0.0.1", port), timeout=0.9)
        probe.close()
        accepted, _ = held.accept()
        accepted.close()
        self.stop(proc)

    def _hold_consecutive(self, count):
        for _ in range(50):
            start = random.randint(20000, 60000 - count)
            if start <= 4243 <= start + count:
                continue
            held = []
            try:
                for port in range(start, start + count):
                    sock = socket.socket()
                    sock.bind(("127.0.0.1", port))
                    sock.listen(1)
                    held.append(sock)
                return start, held
            except OSError:
                for sock in held:
                    sock.close()
        self.fail("could not reserve consecutive loopback ports")

    def test_T_DB_07_no_free_port_ranges(self):
        """T-DB-07: finite bind ranges report their exact first and last ports."""
        server = self.load_server()
        start, held = self._hold_consecutive(3)
        self.addCleanup(lambda: [sock.close() for sock in held])
        with self.assertRaises(server.NoFreePort) as caught:
            server.bind(start, tries=3)
        self.assertEqual((caught.exception.first, caught.exception.last), (start, start + 2))
        start20, held20 = self._hold_consecutive(20)
        self.addCleanup(lambda: [sock.close() for sock in held20])
        result = self.run_factory("dashboard", "--no-open", "--port", str(start20))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr,
                         "factory: ports %d to %d are all in use. Pass a different --port.\n" %
                         (start20, start20 + 19))

    def test_T_DB_08_sigint_is_a_clean_stop(self):
        """T-DB-08: SIGINT stops only the saved process and exits zero."""
        proc, _, _ = self.start("--port", "0")
        code, stdout, stderr = self.stop(proc, signal.SIGINT)
        self.assertEqual(code, 0)
        self.assertEqual(stdout.strip().splitlines()[-1], "Factory dashboard stopped.")
        self.assertNotIn("Traceback", stderr)

    def test_T_DB_09_no_config_logs_or_home_creation(self):
        """T-DB-09: dashboard ignores project config and never creates Factory state."""
        (self.project / "factory.json").write_text("{")
        proc, _, _ = self.start("--port", "0")
        self.stop(proc)
        self.assertEqual(list(self.factory_home.rglob("log-errors.jsonl")), [])
        absent = self.tmp / "absent"
        proc, _, address = self.start("--port", "0", env={"FACTORY_HOME": str(absent)})
        port = int(re.search(r":(\d+)/$", address).group(1))
        status, _, body = self.request(port, "GET", "/api/factory")
        self.assertEqual(status, 200)
        self.assertEqual(body, b'{"ok": true, "builds": [], "selected": null, "board": null}')
        self.stop(proc)
        self.assertFalse(absent.exists())


class DashboardServerTests(DashboardTestCase):
    def test_T_DB_10_routes_get_head_and_not_found(self):
        """T-DB-10: fixed routes have exact types and traversal never reads a file."""
        self.install_fixture("alpha")
        _, _, port = self.serve_in_thread()
        routes = {
            "/": "text/html; charset=utf-8", "/index.html": "text/html; charset=utf-8",
            "/app.js": "text/javascript; charset=utf-8", "/style.css": "text/css; charset=utf-8",
            "/mark.svg": "image/svg+xml", "/api/factory": "application/json; charset=utf-8",
        }
        for path, content_type in routes.items():
            get = self.request(port, "GET", path)
            head = self.request(port, "HEAD", path)
            with self.subTest(path=path):
                self.assertEqual(get[0], 200)
                self.assertEqual(get[1]["Content-Type"], content_type)
                self.assertEqual(head[0], get[0])
                self.assertEqual(head[1]["Content-Length"], get[1]["Content-Length"])
                self.assertEqual(head[2], b"")
        self.assertEqual(self.request(port, "GET", "/")[2], (DASHBOARD / "index.html").read_bytes())
        self.assertEqual(self.request(port, "GET", "/index.html")[2],
                         (DASHBOARD / "index.html").read_bytes())
        favicon = self.request(port, "GET", "/favicon.ico")
        self.assertEqual((favicon[0], favicon[2]), (204, b""))
        for path in ("/nope", "/server.py", "/dashboard/server.py", "/../server.py",
                     "/%2e%2e/server.py", "/index.html/"):
            status, headers, body = self.request(port, "GET", path)
            self.assertEqual((status, headers["Content-Type"], body),
                             (404, "text/plain; charset=utf-8", b"Not found."))
        self.assertEqual(self.request(port, "GET", "/app.js?x=1")[0], 200)

    def test_T_DB_11_security_headers_on_every_answer(self):
        """T-DB-11: all response classes carry the exact no-store safety headers."""
        self.install_fixture("alpha")
        _, _, port = self.serve_in_thread()
        requests = [
            ("GET", "/", None), ("GET", "/favicon.ico", None),
            ("GET", "/api/factory?build=..%2Fx", None),
            ("GET", "/", "evil.example"), ("GET", "/nope", None),
            ("GET", "/api/factory?build=demo/zzz", None), ("POST", "/", None),
        ]
        for method, path, host in requests:
            _, headers, _ = self.request(port, method, path, host=host)
            for name, value in SECURITY_HEADERS.items():
                self.assertEqual(headers.get(name), value, (method, path, name))
            self.assertFalse(any(name.lower().startswith("access-control-") for name in headers))

    def test_T_DB_12_no_files_written_including_dashboard_cache(self):
        """T-DB-12: serving and hostile requests do not mutate homes or dashboard files."""
        self.assertTrue((DASHBOARD / "server.py").is_file(),
                        "planned module missing: skills/factory/dashboard/server.py")
        self.install_fixture("alpha")
        self.install_fixture("beta", build="beta")
        before = (tree_snapshot(self.factory_home), tree_snapshot(self.home),
                  snapshot_without_script_caches(KIT_DIR))
        env = dict(self.env)
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        env.pop("PYTHONPYCACHEPREFIX", None)
        port = self.free_port()
        proc, _, _ = self.start("--port", str(port), env=env)
        paths = ["/", "/index.html", "/app.js", "/style.css", "/mark.svg", "/favicon.ico",
                 "/api/factory", "/api/factory?build=demo/beta", "/nope",
                 "/api/factory?build=..%2Fx"]
        for index in range(30):
            method = "POST" if index == 28 else "GET"
            host = "evil.example" if index == 29 else None
            self.request(port, method, paths[index % len(paths)], host=host)
        self.stop(proc)
        after = (tree_snapshot(self.factory_home), tree_snapshot(self.home),
                 snapshot_without_script_caches(KIT_DIR))
        self.assertEqual(after, before)
        self.assertFalse((DASHBOARD / "__pycache__").exists())

    def test_T_DB_13_all_write_methods_are_read_only(self):
        """T-DB-13: known and unknown non-read methods return the same 405."""
        before = tree_snapshot(self.factory_home)
        _, _, port = self.serve_in_thread()
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "FOO"):
            for path in ("/", "/api/factory"):
                status, headers, body = self.request(port, method, path)
                self.assertEqual((status, headers.get("Allow"), body),
                                 (405, "GET, HEAD", b"Read only."))
        self.assertEqual(self.request(port, "POST", "/api/factory", body=b"x" * 10000)[0], 405)
        self.assertEqual(tree_snapshot(self.factory_home), before)

    def test_T_DB_14_host_header_is_exact(self):
        """T-DB-14: only loopback hostnames with the bound port are accepted."""
        _, _, port = self.serve_in_thread()
        accepted = ("127.0.0.1:%d" % port, "localhost:%d" % port, "LOCALHOST:%d" % port)
        refused = ("evil.example:%d" % port, "127.0.0.1:%d" % (port + 1), "127.0.0.1",
                   "127.0.0.1:%d.evil.example" % port)
        for host in accepted:
            self.assertEqual(self.request(port, "GET", "/api/factory", host=host)[0], 200)
        for host in refused:
            status, headers, body = self.request(port, "GET", "/api/factory", host=host)
            self.assertEqual((status, headers["Content-Type"], body),
                             (403, "text/plain; charset=utf-8", b"Forbidden."))
        raw = self.raw(port, b"GET / HTTP/1.0\r\n\r\n")
        self.assertIn(b" 403 ", raw.split(b"\r\n", 1)[0])
        self.assertTrue(raw.endswith(b"Forbidden."))

    def test_T_DB_15_never_5xx_for_internal_or_hostile_inputs(self):
        """T-DB-15: internal faults and malformed requests never produce a 5xx response."""
        server, _, port = self.serve_in_thread()
        with mock.patch.object(server, "api", side_effect=RuntimeError("boom")):
            status, _, body = self.request(port, "GET", "/api/factory")
        self.assertEqual((status, body), (200, b'{"ok": false, "error": "The factory view could not be loaded. Try again in a moment."}'))
        with mock.patch.object(Path, "read_bytes", side_effect=OSError("no")):
            status, _, body = self.request(port, "GET", "/")
        self.assertEqual((status, body), (404, b"Not found."))
        hostile = [
            b"hello\r\n\r\n", b"GET /" + b"x" * 70000 + b" HTTP/1.1\r\n\r\n",
            b"GET / HTTP/1.1\r\n" + b"X: y\r\n" * 150 + b"\r\n",
            b"GET / HTTP/1.1\r\nX: " + b"x" * 70000 + b"\r\n\r\n",
            b"GET /%ff%fe HTTP/1.1\r\nHost: x\r\n\r\n",
            b"GET /api/factory?build=%00 HTTP/1.1\r\nHost: x\r\n\r\n",
            b"GET http://evil/ HTTP/1.1\r\nHost: x\r\n\r\n", b"\r\n",
            b"GET / HTTP/9.9\r\nHost: x\r\n\r\n",
        ]
        hostile.extend(("M%d / HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n\r\n" % (n, port)).encode()
                       for n in range(31))
        for payload in hostile:
            answer = self.raw(port, payload)
            if answer.startswith(b"HTTP/"):
                status = int(answer.split(b" ", 2)[1])
                self.assertLess(status, 500, payload[:40])
        self.assertEqual(self.request(port, "GET", "/")[0], 200)

    def test_T_DB_16_query_validation_and_first_build_value(self):
        """T-DB-16: build query validation is bounded and repeats use the first value."""
        self.install_fixture("alpha")
        _, _, port = self.serve_in_thread()
        bad = ("..%2Fx", "demo/alpha/extra", "demo/.", "a%20b/c", "a/" + "b" * 299)
        for value in bad:
            status, _, body = self.request(port, "GET", "/api/factory?build=" + value)
            self.assertEqual(status, 400)
            self.assertEqual(body, b'{"ok": false, "error": "That build name is not valid."}')
        for suffix in ("build=demo/alpha&build=demo/zzz", "build=demo/alpha&other=1"):
            status, _, body = self.request(port, "GET", "/api/factory?" + suffix)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["selected"], "demo/alpha")
        status, _, body = self.request(port, "GET", "/api/factory?build=demo/zzz")
        self.assertEqual((status, body),
                         (404, b'{"ok": false, "error": "No build called demo/zzz."}'))

    def _load_lib(self):
        spec = importlib.util.spec_from_file_location("dashboard_test_factorylib", str(SCRIPTS_DIR / "factorylib.py"))
        lib = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, self.env, clear=True):
            spec.loader.exec_module(lib)
        return lib

    def test_T_DB_17_api_matches_the_kit_board(self):
        """T-DB-17: the endpoint is exactly list_builds plus board from factorylib."""
        alpha = self.install_fixture("alpha")
        self.install_fixture("beta", build="beta")
        lib = self._load_lib()
        _, _, port = self.serve_in_thread()
        payload = json.loads(self.request(port, "GET", "/api/factory?build=demo/alpha")[2])
        with mock.patch.dict(os.environ, self.env, clear=True):
            expected = {"ok": True, "builds": lib.list_builds(self.factory_home),
                        "selected": "demo/alpha", "board": lib.board(alpha)}
        self.assertEqual(payload, expected)
        automatic = json.loads(self.request(port, "GET", "/api/factory")[2])
        first = automatic["builds"][0]
        self.assertEqual(automatic["selected"], "%s/%s" % (first["project"], first["id"]))

    def test_T_DB_18_empty_and_unreadable_homes(self):
        """T-DB-18: empty or unreadable project folders remain successful responses."""
        _, _, port = self.serve_in_thread()
        self.assertEqual(self.request(port, "GET", "/api/factory")[2],
                         b'{"ok": true, "builds": [], "selected": null, "board": null}')
        demo = self.factory_home / "runs" / "demo"
        demo.mkdir(parents=True)
        demo.chmod(0)
        try:
            self.install_fixture("alpha", project="other")
            payload = json.loads(self.request(port, "GET", "/api/factory")[2])
            self.assertTrue(payload["ok"])
            keys = ["%s/%s" % (item["project"], item["id"])
                    for item in payload["builds"]]
            self.assertIn("other/alpha", keys)
            self.assertFalse(any(key.startswith("demo/") for key in keys))
        finally:
            demo.chmod(0o700)

    def test_T_DB_19_cache_never_hides_a_changed_trace(self):
        """T-DB-19: an immediate second read observes an appended activity line."""
        build = self.install_fixture("alpha")
        _, _, port = self.serve_in_thread()
        self.request(port, "GET", "/api/factory?build=demo/alpha")
        label = "Newest activity"
        with (build / "trace.jsonl").open("a") as stream:
            stream.write(json.dumps({
                "v": 1, "span_id": "new", "ts": "2026-01-10T12:12:00Z",
                "start": "2026-01-10T12:11:00Z", "end": "2026-01-10T12:12:00Z",
                "kind": "agent_call", "actor": "maker", "call": "new.maker.1",
                "node": "NEW", "node_label": label, "status": "done",
            }) + "\n")
        payload = json.loads(self.request(port, "GET", "/api/factory?build=demo/alpha")[2])
        self.assertEqual(payload["board"]["recent"][0]["plain"],
                         "A builder finished an attempt on Newest activity.")

    def test_T_DB_23_json_escapes_markup_and_ampersands(self):
        """T-DB-23: raw API bytes contain no HTML delimiters while JSON round-trips text."""
        build = self.factory_home / "runs" / "demo" / "hostile"
        build.mkdir(parents=True)
        title = '<img src=x onerror=alert(1)>"\'&'
        plain = "</script><script>alert(1)</script>"
        label = '" onmouseover="x'
        write_json(build / "build.json", {"project": "demo", "build": "hostile", "title": title})
        write_jsonl(build / "trace.jsonl", [
            {"v": 1, "span_id": "x", "ts": "2026-01-10T12:00:00Z",
             "start": "2026-01-10T12:00:00Z", "kind": "agent_call", "actor": "maker",
             "call": "X1.maker.1", "node": "X1", "status": "running",
             "node_label": label},
            {"v": 1, "span_id": "x", "ts": "2026-01-10T12:01:00Z",
             "end": "2026-01-10T12:01:00Z", "status": "done", "plain": plain,
             "plain_source": "agent"},
        ])
        _, _, port = self.serve_in_thread()
        status, _, body = self.request(port, "GET", "/api/factory?build=demo/hostile")
        self.assertEqual(status, 200)
        for byte in (b"<", b">", b"&"):
            self.assertNotIn(byte, body)
        decoded = json.loads(body)
        self.assertEqual(decoded["board"]["build"]["title"], title)
        strings = []

        def collect_strings(value):
            if isinstance(value, dict):
                for child in value.values():
                    collect_strings(child)
            elif isinstance(value, list):
                for child in value:
                    collect_strings(child)
            elif isinstance(value, str):
                strings.append(value)

        collect_strings(decoded)
        for value in (plain, label):
            self.assertIn(value, strings)


class DashboardFileTests(DashboardTestCase):
    def planned_text(self, name):
        path = DASHBOARD / name
        self.assertTrue(path.is_file(), "planned dashboard file missing: %s" % path.relative_to(KIT_DIR))
        return path.read_text()

    def test_T_DB_25_index_contract(self):
        """T-DB-25: index is the exact script-safe frame and watermark shell."""
        text = self.planned_text("index.html")
        required = ('<html lang="en">', '<title>factory</title>', '<main id="view-factory">',
                    '<div class="fd-wordmark">factory</div>', '<div id="fx-root"></div>',
                    "This page needs JavaScript to show the board. The same board is in the terminal: run factory status.",
                    "factory · by Nayan Kanaparthi", "https://github.com/NayanKanaparthi/nstack")
        for item in required:
            self.assertIn(item, text)
        scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", text, re.S | re.I)
        self.assertEqual(scripts, [""])
        self.assertIn('<script src="/app.js"></script>', text)
        self.assertNotIn(" defer", text)
        self.assertLess(text.index("data-fx=\"watermark\""), text.index('<script src="/app.js"'))
        for pattern in (r"<style", r"\sstyle=", r"\son[a-z]+=", r"<nav", r"<aside"):
            self.assertIsNone(re.search(pattern, text, re.I), pattern)
        without_link = text.replace("https://github.com/NayanKanaparthi/nstack", "")
        self.assertNotIn("http", without_link.lower())

    def test_T_DB_26_app_script_contract(self):
        """T-DB-26: application script has safe sinks, intro constants, URL state, and title."""
        text = self.planned_text("app.js")
        forbidden = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
                     "new Function", "setAttribute('style'", "cssText", "localStorage",
                     "http://", "https://", "nav a")
        for item in forbidden:
            self.assertNotIn(item, text)
        required = ("'factory-intro'", "INTRO_OUT_MS = 1150", "INTRO_END_MS = 1500",
                    "INTRO_MAX_MS = 2000", "INTRO_SKIP_MS = 150", "prefers-reduced-motion",
                    "by Nayan Kanaparthi", "'/api/factory'", "history.replaceState", "document.title",
                    "Reply in your Claude Code session", "Built, waiting for a check")
        for item in required:
            self.assertIn(item, text)

    def test_T_DB_27_style_contract(self):
        """T-DB-27: CSS is local, reduced-motion aware, and frame selectors stay scoped."""
        text = self.planned_text("style.css")
        self.assertGreaterEqual(len(re.findall(r"@media\s*\(prefers-reduced-motion:\s*reduce\)", text)), 2)
        for item in (".fd-intro", ".fd-mark", ".fd-wordmark",
                     "#view-factory .fx2-st-built{color:var(--fx2-orange)}"):
            self.assertIn(item, text)
        for item in ("@import", "url(http", ".shell", "aside.side", ".side{"):
            self.assertNotIn(item, text)
        marker = "/* ---------- dashboard frame, intro and watermark (.fd-) ---------- */"
        self.assertIn(marker, text)
        tail = text.split(marker, 1)[1]
        for block in re.findall(r"([^@{}]+)\{", re.sub(r"/\*.*?\*/", "", tail, flags=re.S)):
            for selector in block.split(","):
                selector = selector.strip()
                if not selector or selector.startswith(("from", "to", "0%", "100%")):
                    continue
                self.assertTrue(selector.startswith((".fd-", "#fd-", "html", "body", "#view-factory")), selector)

    def test_T_DB_28_svg_contract(self):
        """T-DB-28: mark is a tiny parsed SVG with no executable or external content."""
        path = DASHBOARD / "mark.svg"
        self.assertTrue(path.is_file(), "planned dashboard file missing: dashboard/mark.svg")
        data = path.read_bytes()
        self.assertLess(len(data), 1024)
        ET.fromstring(data)
        lower = data.lower()
        for item in (b"<script", b"href", b"<text"):
            self.assertNotIn(item, lower)
        self.assertNotIn(b"http", lower.replace(b"http://www.w3.org/2000/svg", b""))

    def test_T_DB_29_server_import_and_write_lint(self):
        """T-DB-29: server imports only allowed stdlib/local modules and has no write primitives."""
        path = DASHBOARD / "server.py"
        self.assertTrue(path.is_file(), "planned module missing: skills/factory/dashboard/server.py")
        text = path.read_text()
        tree = ast.parse(text)
        allowed = {"errno", "http.server", "importlib", "importlib.util", "json", "os", "re",
                   "signal", "socket", "socketserver", "sys", "threading", "time", "pathlib",
                   "urllib.parse", "webbrowser", "functools", "factorylib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertIn(alias.name, allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
        for item in ("unlink", "rmtree", "os.remove", "shutil.move", "subprocess",
                     "create_connection", "urllib.request", "mkdir"):
            self.assertNotIn(item, text)
        self.assertIsNone(re.search(r"open\([^\n]*(?:[\"'][wax][\"'])", text))
        target = self.tmp / "server.pyc"
        py_compile.compile(str(path), cfile=str(target), doraise=True)

    def test_T_DB_30_private_data_scan(self):
        """T-DB-30: all new dashboard test and product files exclude private identifiers."""
        roots = [DASHBOARD, KIT_DIR / "tests" / "browser", KIT_DIR / "tests" / "fixtures" / "dashboard"]
        files = [Path(__file__)]
        for root in roots:
            if root.exists():
                files.extend(path for path in root.rglob("*") if path.is_file())
        for path in files:
            text = path.read_text(errors="replace")
            lower = text.lower().replace("nayankanaparthi/nstack", "").replace(
                "by nayan kanaparthi", "")
            private_home = "/" + "users" + "/"
            long_dash = chr(0x2014)
            protected_port = str(4200 + 42)
            for item in (private_home, long_dash, protected_port):
                self.assertNotIn(item, text.lower() if item != "\u2014" else text, str(path))
            banned = ("ai" + "gis", "at" + "las", "na" + "yan", ".na" + "yanos",
                      "com." + "conductor.app")
            for item in banned:
                self.assertNotIn(item, lower, str(path))

    def test_T_DB_33_command_help_registration(self):
        """T-DB-33: dashboard appears immediately after status and its help binds nothing."""
        result = self.run_factory("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        dashboard_line = "  dashboard     open the board in your browser (this computer only, read-only)"
        self.assertIn(dashboard_line, lines)
        index = lines.index(dashboard_line)
        self.assertIn("status", lines[index - 1])
        port = self.free_port()
        help_result = self.run_factory("dashboard", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", port))
        finally:
            probe.close()

    def test_T_DB_35_documentation_contract(self):
        """T-DB-35: README, skill, and process document dashboard and finish exactly."""
        readme = (KIT_DIR / "README.md").read_text()
        skill = (KIT_DIR / "SKILL.md").read_text()
        process = (KIT_DIR / "PROCESS.md").read_text()
        for heading in ("## Commands", "## Dashboard", "## Evals"):
            self.assertIn(heading, readme, "planned documentation section missing: %s" % heading)
        self.assertTrue(readme.index("## Commands") < readme.index("## Dashboard") < readme.index("## Evals"))
        for item in ("updates by itself while agents work", "factory dashboard --no-open",
                     "factory dashboard --port 7878", "factory dashboard --build demo/alpha",
                     "`status`, `dashboard`, `finish`,", "- `dashboard/`: the local dashboard behind `factory dashboard`"):
            self.assertIn(item, readme)
        limit = ("6. The dashboard is read-only and local. It cannot answer decisions, it cannot be "
                 "reached from another computer, and it checks for changes every few seconds rather "
                 "than instantly. `factory status` shows the same board in a terminal.")
        self.assertIn(limit, readme)
        self.assertNotIn("No dashboard is included.", readme)
        self.assertNotIn("No dashboard ships with this kit", skill)
        for item in ("`factory dashboard` shows a build in the browser as a plan of stages and pieces",
                     "factory dashboard        the board in your browser", "factory finish           mark the build finished",
                     "Give each piece `plain_name`"):
            self.assertIn(item, skill)
        exact = (
            "After `factory new`, tell the owner they can run `factory dashboard` to watch the build; it updates by itself while agents work. Do not start it for them unless they ask: it opens their browser.",
            "A question opened with `factory gate open` shows at the top of the dashboard, but the owner answers it in this conversation, not on the page.",
            "- Views read, never write. `factory status` and `factory dashboard` read the log and `plan.json` and change nothing.",
            "Before GATE B, open `factory dashboard` once and check that what needs the owner and the plan read correctly.",
            "Last step: run `factory finish`. [on trust]",
        )
        combined = readme + skill + process
        for item in exact:
            self.assertIn(item, combined)
        for text in (readme, skill, process):
            self.assertNotIn("\u2014", text)

    def test_T_DB_56_browser_text_is_plain(self):
        """T-DB-56: the browser dump uses kit plain-word checks for every marked string."""
        dump = os.environ.get("FACTORY_DASHBOARD_TEXT_DUMP")
        if not dump:
            self.skipTest("browser text dump not given")
        path = Path(dump)
        self.assertTrue(path.is_file(), "browser text dump missing: %s" % path)
        data = json.loads(path.read_text())
        lib = self._load_lib_for_plain()
        pg1 = 0
        for item in data:
            check = lib.plain_check if item["kind"] == "plain" else lib.plain_label_check
            self.assertEqual(check(item["text"]), [], item)
            if item["build"] == "toy/pg1":
                pg1 += 1
        self.assertGreaterEqual(pg1, 40)

    def _load_lib_for_plain(self):
        spec = importlib.util.spec_from_file_location("dashboard_plain_factorylib", str(SCRIPTS_DIR / "factorylib.py"))
        lib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lib)
        return lib


if __name__ == "__main__":
    unittest.main()
