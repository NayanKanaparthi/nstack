#!/usr/bin/env python3
"""factory preflight: is the machine ready for a build today? (SPEC 5.3)

Every probe has its own time limit, runs with stdin closed, and runs in
parallel with the others. Nothing here deletes or rewrites a file: each run
adds a new stamped file under <factory home>/preflight/ and one index line.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import factorylib as lib

PROMPT = "Reply with exactly: OK"
NOTIFY_TEXT = "Factory preflight test. If you can read this, notifications work."
CREDIT_LINE = ("Remaining credit cannot be read by this tool. A model that answers now "
               "may still run out of credit later.")
CAFFEINATE_FIX = "run: caffeinate -dimsu -t 43200 &"

DEFAULT_LIMITS = {"claude": 90.0, "codex": 120.0, "opencode": 120.0, "cursor": 20.0, "ollama": 5.0}
SLEEP_LIMIT_S = 10.0
# The first start of a program can take a moment (the system may scan it). The
# probe limit counts from when the program is up, so this much is added on top.
START_ALLOWANCE_S = 0.25
OLLAMA_URL = "http://localhost:11434"

LOGIN_FIX = {
    "claude": "log in with: claude /login",
    "codex": "log in with: codex login",
    "opencode": "log in with: opencode auth login",
    "cursor": "log in with: cursor-agent login",
    "ollama": "start it with: ollama serve",
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_LOGIN_RE = re.compile(r"(?i)not logged in|not signed in|unauthorized|please log ?in|authentication required")
_CREDIT_RE = re.compile(r"(?i)usage limit|rate limit|quota|out of credit|insufficient credit|billing")
_NETWORK_RE = re.compile(r"(?i)ENOTFOUND|network is unreachable|could not resolve host")

GROUPS = ("config", "log-home", "model", "vendor", "role", "sleep", "release", "notify", "tools")


class Usage(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)

    def exit(self, status=0, message=None):
        if status == 0:
            raise SystemExit(0)
        raise Usage((message or "bad arguments").strip())


def _parser():
    parser = _Parser(prog="factory preflight", add_help=True,
                     description="Check that the machine is ready for a build.")
    parser.add_argument("--release", action="store_true", help="also run the release login checks")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    parser.add_argument("--only", action="append", default=[], metavar="NAME")
    parser.add_argument("--skip", action="append", default=[], metavar="NAME")
    parser.add_argument("--no-notify-test", action="store_true", help="do not send the test notification")
    return parser


# ---------------------------------------------------------------------------
# running programs with a limit
# ---------------------------------------------------------------------------

def _kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            proc.kill()
        except OSError:
            pass


def _run(argv_or_cmd, limit, cwd=None, shell=False):
    """Run once with stdin closed. Returns dict(state, code, out, err, seconds).

    state: ran | missing | timeout
    """
    started = time.monotonic()
    try:
        proc = subprocess.Popen(argv_or_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=cwd, shell=shell,
                                start_new_session=True, universal_newlines=True,
                                errors="replace")
    except (OSError, ValueError):
        return {"state": "missing", "code": None, "out": "", "err": "",
                "seconds": time.monotonic() - started}
    try:
        out, err = proc.communicate(timeout=limit + START_ALLOWANCE_S)
        return {"state": "ran", "code": proc.returncode, "out": out or "", "err": err or "",
                "seconds": time.monotonic() - started}
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        return {"state": "timeout", "code": None, "out": "", "err": "",
                "seconds": time.monotonic() - started}


def _normalize(text):
    """stdout only, no color codes, no empty lines, the last line, trimmed."""
    lines = [line.strip() for line in _ANSI_RE.sub("", text or "").splitlines()]
    lines = [line for line in lines if line]
    return lines[-1] if lines else ""


def _seconds_words(seconds):
    return "%d s" % int(round(seconds))


def _limit_words(limit):
    return "%gs" % limit


def _limit_for(cfg, runner):
    block = (cfg.get("preflight") or {}).get("limits") or {}
    value = block.get(runner)
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return DEFAULT_LIMITS.get(runner, 60.0)


# ---------------------------------------------------------------------------
# what a model may be sent
# ---------------------------------------------------------------------------

def _runner_entry(cfg, runner):
    return (cfg.get("runners") or {}).get(runner) or {}


def _is_local(cfg, runner, model):
    if runner == "ollama":
        return True
    prefixes = list(_runner_entry(cfg, runner).get("private_safe_prefixes") or [])
    prefixes += list(cfg.get("private_safe_prefixes") or [])
    return any(model.startswith(str(prefix)) for prefix in prefixes)


def _may_keep(cfg, runner, model):
    if not _runner_entry(cfg, runner).get("retains_data"):
        return False
    return not _is_local(cfg, runner, model)


def _class_words(cfg, runner, model):
    if _may_keep(cfg, runner, model):
        if runner == "opencode":
            return "free tier: may keep what it is sent, non-private material only"
        return "may keep what it is sent, non-private material only"
    if _is_local(cfg, runner, model):
        return "private ok, on this machine"
    return "private ok"


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------

def _classify_failure(runner, result, limit):
    """(reason, fix) for a probe that did not pass."""
    if result["state"] == "missing":
        return ("not installed",
                "install %s, or set runners.%s.bin in the factory settings" % (runner, runner))
    if result["state"] == "timeout":
        return ("no answer in %s (network down or service slow)" % _limit_words(limit + START_ALLOWANCE_S),
                "check the network connection, then run preflight again")
    text = (result["out"] or "") + "\n" + (result["err"] or "")
    if _LOGIN_RE.search(text):
        return ("not logged in", LOGIN_FIX.get(runner, "log in to %s" % runner))
    if _CREDIT_RE.search(text):
        return ("out of credits or rate limited",
                "add credit or wait for the limit to reset, then run preflight again")
    if _NETWORK_RE.search(text):
        return ("no network",
                "check the network connection, then run preflight again")
    return ("unexpected answer",
            "run %s by hand and read what it says, then run preflight again" % runner)


def _probe_cloud(cfg, runner, model):
    limit = _limit_for(cfg, runner)
    program = lib.find_runner(cfg, runner)
    started = time.monotonic()
    if not program:
        return {"ok": False, "reason": "not installed", "seconds": 0.0, "path": None,
                "fix": "install %s, or set runners.%s.bin in the factory settings" % (runner, runner)}
    with tempfile.TemporaryDirectory(prefix="factory-preflight-") as workdir:
        if runner == "claude":
            cmd = [program, "-p", PROMPT] + (["--model", model] if model else [])
        elif runner == "codex":
            cmd = [program, "exec", "--skip-git-repo-check"] + (["-m", model] if model else []) + [PROMPT]
        elif runner == "opencode":
            cmd = [program, "run"] + (["-m", model] if model else []) + [PROMPT]
        else:  # cursor: login check only
            cmd = [program, "status"]
        result = _run(cmd, limit, cwd=workdir)
    seconds = time.monotonic() - started
    passed = False
    if result["state"] == "ran" and result["code"] == 0:
        if runner == "cursor":
            text = _ANSI_RE.sub("", result["out"] + "\n" + result["err"])
            passed = "Logged in" in text and "Not logged in" not in text
        else:
            passed = _normalize(result["out"]) == "OK"
    if passed:
        return {"ok": True, "seconds": seconds, "path": program}
    reason, fix = _classify_failure(runner, result, limit)
    return {"ok": False, "reason": reason, "fix": fix, "seconds": seconds, "path": program}


def _ollama_tags_url():
    base = os.environ.get("FACTORY_OLLAMA_URL") or OLLAMA_URL
    base = base.rstrip("/")
    return base if base.endswith("/api/tags") else base + "/api/tags"


def _probe_ollama(cfg, model):
    import urllib.error
    import urllib.request
    limit = _limit_for(cfg, "ollama")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(_ollama_tags_url(), timeout=limit) as response:
            data = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, OSError) and "timed out" in str(reason) or "timed out" in str(exc):
            return {"ok": False, "reason": "no answer in %s (network down or service slow)" % _limit_words(limit),
                    "fix": LOGIN_FIX["ollama"], "seconds": time.monotonic() - started, "path": None}
        return {"ok": False, "reason": "not running", "fix": LOGIN_FIX["ollama"],
                "seconds": time.monotonic() - started, "path": None}
    names = set()
    for item in (data.get("models") or []) if isinstance(data, dict) else []:
        if isinstance(item, dict):
            for key in ("name", "model"):
                if isinstance(item.get(key), str):
                    names.add(item[key])
    wanted = model or ""
    listed = (wanted in names or (wanted + ":latest") in names or
              (wanted.endswith(":latest") and wanted[:-7] in names))
    if model and not listed:
        return {"ok": False, "reason": "model %s is not installed locally" % model,
                "fix": "install it with: ollama pull %s" % model,
                "seconds": time.monotonic() - started, "path": None}
    return {"ok": True, "seconds": time.monotonic() - started, "path": None}


def _probe(cfg, runner, model):
    try:
        if runner == "ollama":
            return _probe_ollama(cfg, model)
        return _probe_cloud(cfg, runner, model)
    except Exception as exc:  # a probe must never crash the command
        return {"ok": False, "reason": "could not be checked (%s)" % type(exc).__name__,
                "fix": "run preflight again", "seconds": 0.0, "path": None}


def _probe_key(runner, model):
    return (runner, None if runner == "cursor" else (model or None))


# ---------------------------------------------------------------------------
# local checks (each returns (result, detail, fix))
# ---------------------------------------------------------------------------

def _check_log_home():
    path = lib.home()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return ("FAIL", "cannot create the factory home %s (%s)" % (path, exc.strerror or "error"),
                "make that folder yourself, or set FACTORY_HOME to a folder you can write to")
    real = os.path.realpath(str(path))
    if os.access(real, os.W_OK | os.X_OK):
        return ("PASS", "%s is writable" % real, "")
    return ("FAIL", "%s is not writable" % real, "make that folder writable, or set FACTORY_HOME to another folder")


def _check_sleep():
    program = os.environ.get("FACTORY_PMSET_BIN")
    if not program:
        if sys.platform != "darwin":
            return ("WARN", "not checked on this system", "")
        program = "pmset"
    fix = CAFFEINATE_FIX
    first = _run([program, "-g", "assertions"], SLEEP_LIMIT_S)
    if first["state"] == "missing":
        return ("FAIL", "could not read the sleep settings (pmset is not available)", fix)
    if first["state"] == "timeout":
        return ("FAIL", "the sleep check did not answer in %s" % _limit_words(SLEEP_LIMIT_S), fix)
    if re.search(r"(?m)\b(PreventUserIdleSystemSleep|PreventSystemSleep)\s+1\b", first["out"]):
        return ("PASS", "the Mac will stay awake", "")
    second = _run([program, "-g"], SLEEP_LIMIT_S)
    if second["state"] == "ran" and re.search(r"(?m)\bSleepDisabled\s+1\b", second["out"]):
        return ("PASS", "the Mac will stay awake (sleep is switched off)", "")
    return ("FAIL", "nothing is keeping the Mac awake, so a long build could stop when it sleeps", fix)


def _check_tools(cfg):
    problems = []
    for tool in ("git", "python3"):
        if not shutil.which(tool):
            problems.append(tool)
    if problems:
        return ("FAIL", "%s not found on PATH" % " and ".join(problems),
                "install %s and make sure it is on PATH" % " and ".join(problems))
    fast = ((cfg.get("tests") or {}).get("fast") or {}).get("cmd")
    if not fast:
        return ("WARN", "git and python3 found; no fast test command is set (tests.fast.cmd)",
                "set tests.fast.cmd in factory.json so builds can run the quick tests")
    return ("PASS", "git and python3 found; the fast test command is set", "")


def _last_line(text):
    lines = [line.strip() for line in _ANSI_RE.sub("", text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _check_release(cfg, entry):
    limit = entry.get("timeout_s")
    limit = float(limit) if isinstance(limit, (int, float)) and limit > 0 else lib.timers_of(cfg)["default_cmd_timeout_s"]
    result = _run(str(entry.get("cmd", "")), limit, cwd=os.getcwd(), shell=True)
    if result["state"] == "timeout":
        return ("FAIL", "no answer in %s" % _limit_words(limit + START_ALLOWANCE_S),
                "check the login this step needs, then run preflight again")
    if result["state"] == "ran" and result["code"] == 0:
        return ("PASS", "passed", "")
    tail = _last_line(result["out"] + "\n" + result["err"]) or "no output"
    return ("FAIL", "failed: %s" % tail, "fix what the step says, then run preflight again")


def _run_notify(cfg):
    try:
        return lib.notify(cfg, NOTIFY_TEXT, NOTIFY_TEXT, "None.", test=True)
    except Exception as exc:
        return {"__error__": "failed: %s" % type(exc).__name__}


# ---------------------------------------------------------------------------
# the plan: which checks exist, what they need
# ---------------------------------------------------------------------------

class Check(object):
    def __init__(self, name, deps, compute):
        self.name = name
        self.deps = deps          # task keys this check needs
        self.compute = compute    # f(results) -> (result, detail, fix)


def _roles_models(cfg):
    """[(role, [(runner, model), ...main first then fallbacks])]"""
    out = []
    for role, entry in (cfg.get("roles") or {}).items():
        if not isinstance(entry, dict) or not entry.get("runner"):
            continue
        models = [(entry["runner"], str(entry.get("model") or ""))]
        fallback = entry.get("fallback")
        items = fallback if isinstance(fallback, list) else ([fallback] if fallback else [])
        for item in items:
            if isinstance(item, dict) and item.get("runner"):
                models.append((item["runner"], str(item.get("model") or "")))
        out.append((role, models))
    return out


def _bad_setting(cfg):
    """(key, what is wrong) for a settings value of the wrong shape, else None."""
    block = cfg.get("preflight")
    if block is not None and not isinstance(block, dict):
        return ("preflight", "it must be an object")
    limits = (block or {}).get("limits")
    if limits is not None and not isinstance(limits, dict):
        return ("preflight.limits", "it must be an object of seconds per runner")
    if cfg.get("private_safe_prefixes") is not None and not isinstance(cfg.get("private_safe_prefixes"), list):
        return ("private_safe_prefixes", "it must be a list of text")
    runners = cfg.get("runners")
    if runners is not None and not isinstance(runners, dict):
        return ("runners", "it must be an object")
    for name, entry in (runners or {}).items():
        if isinstance(entry, dict) and entry.get("private_safe_prefixes") is not None \
                and not isinstance(entry.get("private_safe_prefixes"), list):
            return ("runners.%s.private_safe_prefixes" % name, "it must be a list of text")
    return None


def _model_line(cfg, runner, model, probe):
    klass = _class_words(cfg, runner, model)
    if probe["ok"]:
        return ("PASS", "answered in %s, %s" % (_seconds_words(probe["seconds"]), klass), "")
    return ("FAIL", "%s, %s" % (probe["reason"], klass), probe["fix"])


def build_plan(cfg, release):
    checks = []
    tasks = {}  # key -> callable

    def need_probe(runner, model):
        key = ("probe",) + _probe_key(runner, model)
        if key not in tasks:
            tasks[key] = (lambda r=runner, m=model: _probe(cfg, r, m))
        return key

    def local_task(key, fn):
        tasks[key] = fn
        return key

    checks.append(Check("config", [], lambda res: ("PASS", "settings are valid", "")))
    checks.append(Check("log-home", [local_task(("local", "log-home"), _check_log_home)],
                        lambda res: res[("local", "log-home")]["value"]))

    roles = _roles_models(cfg)
    seen = []
    for _role, models in roles:
        for pair in models:
            if pair not in seen:
                seen.append(pair)
    for runner, model in seen:
        key = need_probe(runner, model)
        checks.append(Check(
            "model:%s:%s" % (runner, model), [key],
            (lambda res, r=runner, m=model, k=key: _model_line(cfg, r, m, res[k]["value"]))))

    # role lines: only when a main model fails
    def role_compute(role, models):
        keys = [("probe",) + _probe_key(r, m) for r, m in models]

        def compute(res):
            main_runner, main_model = models[0]
            main = res[keys[0]]["value"]
            if main["ok"]:
                if _may_keep(cfg, main_runner, main_model):
                    return ("WARN", "%s works, but it may keep what it is sent, so it only gets calls marked non-private"
                            % main_model, "use a model that keeps nothing for this role if it handles private material")
                return ("PASS", "%s works" % main_model, "")
            skipped, chosen = [], None
            for (runner, model), key in zip(models[1:], keys[1:]):
                if _may_keep(cfg, runner, model):
                    skipped.append(model)
                    continue
                if res[key]["value"]["ok"]:
                    chosen = (runner, model)
                    break
            notes = ["%s is only for calls marked non-private" % m for m in skipped]
            if chosen:
                where = " (on this machine)" if _is_local(cfg, *chosen) else ""
                detail = "%s did not answer; will use fallback %s%s" % (main_model, chosen[1], where)
                if notes:
                    detail += "; " + "; ".join(notes)
                return ("WARN", detail, "")
            detail = "no working model for the %s role: %s failed (%s)" % (role, main_model, main["reason"])
            if notes:
                detail += "; " + "; ".join(notes)
            return ("FAIL", detail, main["fix"])
        return keys, compute

    for role, models in roles:
        keys, compute = role_compute(role, models)
        checks.append(Check("role:%s" % role, keys, compute))

    # vendors
    vendors = cfg.get("vendors") or {}
    for status, names in (("required", vendors.get("required") or []), ("optional", vendors.get("optional") or [])):
        for name in names:
            role_keys = [("probe",) + _probe_key(r, m) for r, m in seen if r == name]
            vendor_only = None
            probe_model = _runner_entry(cfg, name).get("probe_model") or None
            if not role_keys:
                vendor_only = need_probe(name, probe_model)
                role_keys = [vendor_only]
            checks.append(Check(
                "vendor:%s" % name, role_keys,
                _vendor_compute(cfg, name, status, role_keys, vendor_only, probe_model)))

    checks.append(Check("sleep", [local_task(("local", "sleep"), _check_sleep)],
                        lambda res: res[("local", "sleep")]["value"]))

    # release logins
    if release:
        entries = ((cfg.get("release") or {}).get("preflight")) or []
        if not entries:
            checks.append(Check("release", [], lambda res: ("WARN", "no release checks configured",
                                                              "add release.preflight entries to factory.json")))
        for index, entry in enumerate(entries):
            name = str(entry.get("name") or "step %d" % (index + 1))
            key = local_task(("local", "release", index), (lambda e=entry: _check_release(cfg, e)))
            checks.append(Check("release:%s" % name, [key], (lambda res, k=key: res[k]["value"])))
    else:
        for index, entry in enumerate(((cfg.get("release") or {}).get("preflight")) or []):
            checks.append(Check("release:%s" % str(entry.get("name") or "step %d" % (index + 1)), [], None))

    # notifications
    channels = (cfg.get("notify") or {}).get("channels") or []
    if not channels:
        checks.append(Check("notify", [], lambda res: (
            "WARN", "no notification channel is configured, so you will not be told when a build waits on you",
            "set notify.channels in the factory settings")))
    else:
        key = local_task(("local", "notify"), lambda: _run_notify(cfg))
        for channel in channels:
            checks.append(Check("notify:%s" % channel, [key],
                                (lambda res, c=channel, k=key: _notify_compute(cfg, c, res[k]["value"]))))

    checks.append(Check("tools", [local_task(("local", "tools"), lambda: _check_tools(cfg))],
                        lambda res: res[("local", "tools")]["value"]))
    return checks, tasks


def _vendor_compute(cfg, name, status, keys, vendor_only, probe_model):
    def compute(res):
        probes = [res[k]["value"] for k in keys]
        passed = [p for p in probes if p["ok"]]
        if passed:
            if vendor_only:
                model = probe_model or ""
                where = passed[0].get("path")
                bits = ["answered in %s" % _seconds_words(passed[0]["seconds"])]
                if where:
                    bits.append("using %s" % where)
                if name != "cursor":
                    bits.append(_class_words(cfg, name, model))
                return ("PASS", ", ".join(bits), "")
            return ("PASS", "%d of %d models answered" % (len(passed), len(probes)), "")
        first = probes[0]
        if status == "optional":
            return ("WARN", "optional, not available (%s)" % first["reason"], first["fix"])
        return ("FAIL", "%s (required)" % first["reason"], first["fix"])
    return compute


def _notify_compute(cfg, channel, results):
    if "__error__" in results:
        return ("FAIL", lib.redact(results["__error__"]), "check the notification settings")
    if channel == "connector":
        connector = (cfg.get("notify") or {}).get("connector")
        if isinstance(connector, dict) and connector.get("name") and connector.get("account_confirmed") is True:
            return ("PASS", "configured and confirmed by the owner: %s. Send a test through it yourself."
                    % connector["name"], "")
        return ("FAIL", "the connector is not set up or its account is not confirmed",
                "set notify.connector with a name and account_confirmed true")
    outcome = results.get(channel)
    if outcome == "sent":
        return ("PASS", "sent at %s, check that you saw it" % time.strftime("%H:%M"), "")
    reason = lib.redact(str(outcome or "failed: nothing was sent"))
    if reason.startswith("failed: "):
        reason = reason[len("failed: "):]
    return ("FAIL", "the test message was not sent (%s)" % reason,
            "check the %s notification setting and try again" % channel)


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

def _matches(token, name):
    return token == name or token == name.split(":", 1)[0]


def _selected(name, only, skip):
    if only and not any(_matches(t, name) for t in only):
        return False
    return not any(_matches(t, name) for t in skip)


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def _problem_words(count):
    return "%d problem%s" % (count, "" if count == 1 else "s")


def _write_result(payload):
    folder = lib.home() / "preflight"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = payload["checked_at"].replace("-", "").replace(":", "")
    text = json.dumps(payload, indent=2) + "\n"
    name = "%s.json" % stamp
    counter = 1
    while True:
        try:
            with open(str(folder / name), "x", encoding="utf-8") as stream:
                stream.write(text)
            break
        except FileExistsError:
            counter += 1
            name = "%s-%d.json" % (stamp, counter)
    problems = sum(1 for c in payload["checks"] if c["result"] == "FAIL")
    warnings = sum(1 for c in payload["checks"] if c["result"] == "WARN")
    lib.append_jsonl_locked(folder / "index.jsonl", {
        "ts": payload["checked_at"], "file": name, "ok": payload["ok"],
        "problems": problems, "warnings": warnings}, mkdir=True)
    return folder / name


def _log_span(build, started_epoch, ok, summary):
    end = lib.now_epoch()
    fields = {
        "kind": "command", "actor": "orchestrator", "node": "preflight",
        "status": "done" if ok else "failed",
        "start": lib.from_epoch(started_epoch), "end": lib.from_epoch(end),
        "duration_s": max(0, int(round(end - started_epoch))),
        "cmd": "factory preflight", "notes": summary,
    }
    if not ok:
        fields["failure_class"] = "env-tooling"
    lib.append(build.dir, fields)


def main(argv):
    try:
        args = _parser().parse_args(list(argv))
    except Usage as exc:
        sys.stderr.write("factory: preflight: %s\n" % exc)
        return lib.EXIT.USAGE
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    started = lib.now_epoch()
    try:
        cfg, settings_from, settings_warnings = lib.load_config_full(Path(os.getcwd()))
    except lib.FactoryError as exc:
        sys.stderr.write(exc.line() + "\n")
        return exc.code

    bad = _bad_setting(cfg)
    if bad:
        sys.stderr.write("factory: preflight: the setting %s is not valid: %s\n" % bad)
        return lib.EXIT.USAGE

    checks, tasks = build_plan(cfg, args.release)
    known = [c.name for c in checks]
    for token in list(args.only) + list(args.skip):
        if token not in known and token not in GROUPS:
            sys.stderr.write("factory: preflight: no check is named \"%s\". Checks: %s\n"
                             % (token, ", ".join(known)))
            return lib.EXIT.USAGE

    chosen = [c for c in checks if c.compute is not None and _selected(c.name, args.only, args.skip)]
    if args.no_notify_test:
        chosen = [c for c in chosen if c.name != "notify" and not c.name.startswith("notify:")]

    if not chosen:
        release_named = any(c.name.startswith("release") and _selected(c.name, args.only, args.skip)
                            for c in checks)
        if not args.release and release_named:
            sys.stderr.write("factory: preflight: nothing was checked, because release checks only run with "
                             "--release. Add --release.\n")
        else:
            sys.stderr.write("factory: preflight: nothing was checked, because --only, --skip and "
                             "--no-notify-test left no check to run.\n")
        return lib.EXIT.USAGE

    needed = []
    for check in chosen:
        for key in check.deps:
            if key not in needed:
                needed.append(key)
    results = {}
    with ThreadPoolExecutor(max_workers=max(4, len(needed))) as pool:
        futures = {}
        for key in needed:
            def timed(fn=tasks[key]):
                t0 = time.monotonic()
                value = fn()
                return {"value": value, "seconds": time.monotonic() - t0}
            futures[key] = pool.submit(timed)
        for key, future in futures.items():
            try:
                results[key] = future.result()
            except Exception as exc:
                results[key] = {"value": ("FAIL", "could not be checked (%s)" % type(exc).__name__,
                                          "run preflight again"), "seconds": 0.0}

    rows = []
    for check in chosen:
        t0 = time.monotonic()
        try:
            result, detail, fix = check.compute(results)
        except Exception as exc:
            result, detail, fix = ("FAIL", "could not be checked (%s)" % type(exc).__name__, "run preflight again")
        seconds = max([results[k]["seconds"] for k in check.deps] or [0.0])
        if check.name == "config" and settings_warnings:
            for warning in settings_warnings:
                rows.append({"name": "config", "result": "WARN", "detail": lib.redact(str(warning)),
                             "fix": "", "seconds": 0.0})
            continue
        rows.append({"name": check.name, "result": result, "detail": lib.redact(detail),
                     "fix": lib.redact(fix), "seconds": round(seconds, 1)})

    failures = [r for r in rows if r["result"] == "FAIL"]
    ok = not failures
    payload = {"ok": ok, "checked_at": lib.now(), "checks": rows, "settings_from": settings_from}
    summary = "Ready." if ok else "Not ready: %s." % _problem_words(len(failures))

    out = []
    if args.json:
        out.append(json.dumps(payload, indent=2))
    else:
        width = max([len(r["name"]) for r in rows] or [0])
        for row in rows:
            out.append("%-4s  %-*s  %s" % (row["result"], width, row["name"], row["detail"]))
        out.append("")
        out.append(CREDIT_LINE)
        out.append(summary)
        seen = []
        fixed = [r for r in rows if r["result"] in ("FAIL", "WARN") and (r["fix"] or r["result"] == "FAIL")]
        fixed.sort(key=lambda r: r["result"] != "FAIL")
        for row in fixed:
            fix = row["fix"] or "see the line above"
            if fix not in [f for _n, f in seen]:
                seen.append((row["name"], fix))
        for number, (name, fix) in enumerate(seen, 1):
            out.append("%d. %s: %s" % (number, name, fix))
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()

    try:
        _write_result(payload)
    except OSError as exc:
        sys.stderr.write("factory: preflight: could not save the result (%s)\n" % (exc.strerror or "error"))
    try:
        build = lib.select_build(None)
    except lib.FactoryError:
        build = None
    if build is not None:
        try:
            _log_span(build, started, ok, summary)
        except lib.FactoryError as exc:
            sys.stderr.write(exc.line() + "\n")
    return lib.EXIT.OK if ok else lib.EXIT.NO


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
