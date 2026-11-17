#!/usr/bin/env python3
"""The evidence log for the discover kit (version 2).

Searchers, checkers and the audit write what they find to plain JSON Lines files, one line per
search, page, candidate, item or verdict, the moment it happens. This script reads and writes
those files, so nobody has to re-read long notes to know where a step stands.

Run it only as a command, never import it:

    python3 log_tool.py <command> --folder <student folder> --step <step> [options]

Steps: find-problems, evidence, topup-1, topup-2, ...
Files: <folder>/discover-work/log/<step>/

Commands
    clock       start a phase clock                    --phase P [--minutes M]
    left        minutes left in a phase                --phase P
    add         add lines from stdin (JSON)            --source S
    candidates  the shared candidate list (find-problems)
    status      budget used, time left, enough or not  --source S
    shard       split find-problems items for checkers [--max 4] [--extra]
    thin        list one-page candidates for the extra round (find-problems)
    ledger      write one evidence ledger per assumption
    result      add checker verdicts from stdin        --shard X
    merge       join items and verdicts                (find-problems)
    pairs       list pairs for the audit to compare
    apply       apply the audit's corrections          (find-problems)
    assemble    build evidence.json from the verdicts  (evidence and top-ups)

Standard library only. The rules it applies are published in shared/evidence-log.md.
"""

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.dont_write_bytecode = True

# ---------------------------------------------------------------- settings (published in evidence-log.md)

PHASE_MINUTES = {
    "find-problems": {"search": 3.5, "check": 3.5, "build": 2.5,
                      # the extra round, only when fewer than 3 problems hold up (contract v2.1 point 2)
                      "extra-search": 3.0, "extra-check": 2.5, "extra-build": 2.5},
    "evidence": {"research": 3.5, "check": 3.5, "audit": 2.5},
    "topup": {"research": 3.5, "check": 3.5, "audit": 2.5},
}
WRAP_UP_MINUTES = 1.0  # at or below this, an agent stops opening pages and saves

LIMITS = {
    # per searcher
    "find-problems": {"searches": 6, "pages": 8},
    # per assumption researcher; the first researcher also runs the two extra searches
    "evidence": {"searches": 5, "pages": 5},
    # per second-pages searcher in the extra round of find-problems
    "second-pages": {"searches": 4, "pages": 5},
}
EXTRA_SEARCHERS = 2       # at most this many second-pages searchers
EXTRA_TARGETS = 6         # at most this many one-page candidates in the extra round
EXTRA_SHARDS = 2          # at most this many checkers in the extra round
THIN_LIST = 3             # the extra round runs when fewer problems than this hold up
EXTRA_FIRST_RESEARCHER = {"searches": 2, "pages": 3}

# find-problems: a candidate is strong when it has this many "for" items, voices and pages
STRONG = {"items": 4, "voices": 3, "pages": 2}
ENOUGH_STRONG_CANDIDATES = 6
# a candidate is checked only if it can still reach the bar of 2 counted "for" items on 2 pages
CHECK_BAR = {"items": 2, "pages": 2}
# evidence: one side is well covered when it has this many voices on this many pages
EVIDENCE_SIDE_COVERED = {"voices": 3, "pages": 2}

SIDES = {"for", "against", "context"}
KINDS = {"own words", "number", "organisation fact"}
SIGNALS = ["complaint", "money spent", "time spent", "workaround", "switched",
           "asked for recommendations", "none"]
RESULTS = {"counts", "set aside", "removed"}
REASONS = {"second_hand", "stake", "not_original", "vague_amount", "indirect", "group_not_shown",
           "old", "could_not_open", "pasted", "not_on_page", "off_target", "author_not_shown"}
PRODUCT_KINDS = {"competitor", "workaround", "general AI assistant", "person or agency", "do nothing"}
PAGE_OUTCOMES = {"opened", "failed", "nothing useful"}
SEARCH_SIDES = {"for", "against", "extra", "any"}
UNREAD_SIDES = {"for", "against", "unclear"}
CONCEDING = re.compile(r"doesn't say|does not say|not shown|leaves room|unclear whether|isn't clear|"
                       r"is not clear|may not|might not|can't tell|cannot tell|no date", re.I)
OLD_YEARS = 5

ITEM_FIELDS_FP = ["candidate", "side", "kind", "quote", "link", "who", "when", "where",
                  "group_shown", "action", "signal"]
ITEM_FIELDS_EV = ["assumption", "side", "kind", "quote", "link", "who", "when", "where",
                  "group_shown", "action", "signal"]
PREFIX_FP = {"complaints": "K", "workarounds": "W", "counts": "N", "second-1": "S1", "second-2": "S2"}
SECOND_SOURCE = re.compile(r"second-[1-9]")


class Refused(Exception):
    pass


# ---------------------------------------------------------------- helpers

def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text):
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def page_of(link):
    """Two links that differ only after # or ?, in letter case or by a trailing / are one page."""
    return re.sub(r"[#?].*$", "", link or "").rstrip("/").lower()


def site_of(link):
    host = urlparse(link or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def norm(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_link(value):
    return isinstance(value, str) and re.match(r"^https?://\S+$", value, re.I) is not None


def step_family(step):
    if step == "find-problems":
        return "find-problems"
    if step == "evidence":
        return "evidence"
    if re.fullmatch(r"topup-[1-9]\d*", step):
        return "topup"
    raise Refused(f'Unknown step "{step}". Use find-problems, evidence or topup-<n>.')


def log_dir(folder, step):
    return Path(folder) / "discover-work" / "log" / step


def read_lines(path):
    rows = []
    if not path.is_file():
        return rows
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            raise Refused(f"{path.name} line {number} is not valid JSON. Fix or remove that line.")
    return rows


def append_lines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_stdin_rows():
    raw = sys.stdin.read().strip()
    if not raw:
        raise Refused("Nothing came in on stdin. Send one JSON object, a JSON list, or one object per line.")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else [data]
    except ValueError:
        rows = []
        for number, line in enumerate(raw.splitlines(), 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError as error:
                    raise Refused(f"Line {number} of the input is not valid JSON: {error}")
        return rows


def source_logs(folder, step):
    directory = log_dir(folder, step)
    return sorted(directory.glob("source-*.jsonl")) if directory.is_dir() else []


def all_rows(folder, step):
    rows = []
    for path in source_logs(folder, step):
        rows.extend(read_lines(path))
    return rows


def discovery(folder):
    path = Path(folder) / "discovery.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise Refused("discovery.json is not valid JSON.")


def year_of(when):
    match = re.search(r"\b(19|20)\d{2}\b", when or "")
    return int(match.group(0)) if match else None


# ---------------------------------------------------------------- clock

def cmd_clock(args):
    family = step_family(args.step)
    minutes = args.minutes if args.minutes is not None else PHASE_MINUTES[family].get(args.phase)
    if minutes is None:
        raise Refused(f'No default budget for phase "{args.phase}" of {args.step}. '
                      f"Phases: {', '.join(PHASE_MINUTES[family])}.")
    path = log_dir(args.folder, args.step) / "clock.json"
    clock = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    clock[args.phase] = {"started": iso(now()), "minutes": minutes}
    write_json(path, clock)
    print(f"{args.phase}: clock started, {minutes:g} minutes.")


def minutes_left(folder, step, phase):
    path = log_dir(folder, step) / "clock.json"
    if not path.is_file():
        return None
    clock = json.loads(path.read_text(encoding="utf-8"))
    entry = clock.get(phase)
    if not entry:
        return None
    used = (now() - parse_iso(entry["started"])).total_seconds() / 60
    return entry["minutes"] - used


def left_line(folder, step, phase):
    left = minutes_left(folder, step, phase)
    if left is None:
        return f"{phase}: no clock started."
    if left <= 0:
        return f"{phase}: time is up. Stop now and save what you have."
    if left <= WRAP_UP_MINUTES:
        return f"{phase}: {left:.1f} minutes left. Wrap up: open no more pages, save what you have."
    return f"{phase}: {left:.1f} minutes left."


def cmd_left(args):
    step_family(args.step)
    print(left_line(args.folder, args.step, args.phase))


# ---------------------------------------------------------------- add

def check_item(row, family):
    fields = ITEM_FIELDS_FP if family == "find-problems" else ITEM_FIELDS_EV
    missing = [f for f in fields if not isinstance(row.get(f), str) or row.get(f, "").strip() == ""]
    if missing:
        raise Refused(f"item is missing: {', '.join(missing)}.")
    if row["side"] not in SIDES:
        raise Refused(f'item side "{row["side"]}" must be for, against or context.')
    if row["kind"] not in KINDS:
        raise Refused(f'item kind "{row["kind"]}" must be own words, number or organisation fact.')
    if row["signal"] not in SIGNALS:
        raise Refused(f'item signal "{row["signal"]}" must be one of: {", ".join(SIGNALS)}.')
    if not is_link(row["link"]):
        raise Refused("item link must start with http:// or https://.")
    opened = row.get("opened", "yes")
    if opened not in ("yes", "snippet only", "pasted by student"):
        raise Refused('item "opened" must be yes, snippet only or pasted by student.')


def cmd_add(args):
    family = step_family(args.step)
    if not re.fullmatch(r"[a-z0-9-]+", args.source or ""):
        raise Refused("--source must be a short name in lower case: complaints, workarounds, counts, second-1, "
                      "second-2, or an assumption id in lower case such as a1.")
    rows = read_stdin_rows()
    path = log_dir(args.folder, args.step) / f"source-{args.source}.jsonl"
    existing = all_rows(args.folder, args.step)
    own = read_lines(path)
    candidates = {norm(r["statement"]): r["id"] for r in existing if r.get("type") == "candidate"}
    prefix = PREFIX_FP.get(args.source, args.source.upper()) if family == "find-problems" else args.source.upper()
    item_n = sum(1 for r in own if r.get("type") == "item")
    cand_n = sum(1 for r in own if r.get("type") == "candidate")
    out, messages = [], []
    stamp = iso(now())
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or "type" not in row:
            raise Refused(f"Input {index} needs a \"type\": search, page, candidate, item, option, "
                          "nothing_found or not_opened.")
        kind = row["type"]
        row = dict(row)
        row["source"] = args.source
        row["ts"] = stamp
        try:
            if kind == "search":
                if not isinstance(row.get("words"), str) or not row["words"].strip():
                    raise Refused("search needs its words.")
                if family != "find-problems":
                    if row.get("side") not in SEARCH_SIDES:
                        raise Refused('search "side" must be for, against, extra or any.')
                messages.append(f'search logged: "{row["words"]}"')
            elif kind == "page":
                if not is_link(row.get("link")):
                    raise Refused("page needs a link starting with http:// or https://.")
                if row.get("outcome") not in PAGE_OUTCOMES:
                    raise Refused('page "outcome" must be opened, failed or nothing useful.')
                if family != "find-problems" and (not row.get("assumption") or row.get("side") not in SEARCH_SIDES):
                    raise Refused('an evidence page needs "assumption" and a "side": for, against, extra or any.')
                messages.append(f"page logged: {row['outcome']}")
            elif kind == "candidate":
                if family != "find-problems":
                    raise Refused("candidates belong to find-problems only.")
                if SECOND_SOURCE.fullmatch(args.source):
                    raise Refused("the extra round looks for second pages for listed candidates only. Log the item "
                                  "under the listed candidate it fits, or leave it out.")
                if not row.get("statement") or not row.get("who"):
                    raise Refused("candidate needs a statement and who.")
                key = norm(row["statement"])
                if key in candidates:
                    messages.append(f"candidate already listed as {candidates[key]}; use that id")
                    continue
                cand_n += 1
                row["id"] = f"{prefix}{cand_n}"
                candidates[key] = row["id"]
                messages.append(f"candidate {row['id']}: {row['statement']}")
            elif kind == "item":
                check_item(row, family)
                if family == "find-problems":
                    known = {r["id"] for r in existing + out if r.get("type") == "candidate"}
                    if row["candidate"] not in known:
                        raise Refused(f'item candidate "{row["candidate"]}" is not on the candidate list. '
                                      "Add the candidate first, or run the candidates command.")
                item_n += 1
                row["id"] = f"{prefix}-E{item_n}"
                messages.append(f"item {row['id']} ({row['side']}, {row.get('candidate') or row.get('assumption')})")
            elif kind == "option":
                if row.get("kind") not in PRODUCT_KINDS or not row.get("name") or not row.get("fact") \
                        or not is_link(row.get("link")):
                    raise Refused("option needs name, link, fact and a kind: "
                                  "competitor, workaround, general AI assistant, person or agency, do nothing.")
                messages.append(f"option logged: {row['name']}")
            elif kind == "nothing_found":
                if not row.get("tried"):
                    raise Refused("nothing_found needs what was tried.")
                messages.append("nothing found logged")
            elif kind == "not_opened":
                if not is_link(row.get("link")) or not row.get("why") or not row.get("held"):
                    raise Refused("not_opened needs link, why (blocked, or over the page limit) and held.")
                if family != "find-problems" and row.get("side") not in UNREAD_SIDES:
                    raise Refused('not_opened "side" must be for, against or unclear.')
                messages.append("not opened logged")
            else:
                raise Refused(f'Unknown type "{kind}".')
        except Refused as error:
            raise Refused(f"Input {index} ({kind}): {error} Nothing was saved.")
        out.append(row)
    append_lines(path, out)
    for message in messages:
        print(message)
    print(status_text(args.folder, args.step, args.source))


# ---------------------------------------------------------------- candidates and status

def fp_table(rows):
    candidates = {}
    for row in rows:
        if row.get("type") == "candidate":
            candidates.setdefault(row["id"], {"id": row["id"], "statement": row["statement"],
                                               "who": row["who"], "items": []})
    for row in rows:
        if row.get("type") == "item" and row.get("candidate") in candidates:
            candidates[row["candidate"]]["items"].append(row)
    for cand in candidates.values():
        fors = [i for i in cand["items"] if i["side"] == "for"]
        cand["for_items"] = len(fors)
        cand["voices"] = len({norm(i["who"]) for i in fors})
        cand["pages"] = len({page_of(i["link"]) for i in fors})
    return candidates


def strong(cand):
    return (cand["for_items"] >= STRONG["items"] and cand["voices"] >= STRONG["voices"]
            and cand["pages"] >= STRONG["pages"])


def cmd_candidates(args):
    if step_family(args.step) != "find-problems":
        raise Refused("candidates is for find-problems only.")
    table = fp_table(all_rows(args.folder, args.step))
    if not table:
        print("No candidates yet.")
        return
    for cand in table.values():
        print(f"{cand['id']}: {cand['statement']} | for items {cand['for_items']}, voices {cand['voices']}, "
              f"pages {cand['pages']}{' | strong' if strong(cand) else ''}")


def usage(rows, source):
    mine = [r for r in rows if r.get("source") == source]
    return (sum(1 for r in mine if r.get("type") == "search"),
            sum(1 for r in mine if r.get("type") == "page"))


def status_text(folder, step, source):
    family = step_family(step)
    rows = all_rows(folder, step)
    searches, pages = usage(rows, source)
    lines = []
    if family == "find-problems" and SECOND_SOURCE.fullmatch(source):
        limit = LIMITS["second-pages"]
        lines.append(f"{source}: searches {searches} of {limit['searches']}, pages {pages} of {limit['pages']}.")
        lines.append(left_line(folder, step, "extra-search"))
        mine = [t for t in extra_targets(folder, step) if t.get("searcher") == source]
        todo = [t["id"] for t in mine if not new_pages(rows, t)]
        if not mine:
            lines.append("No candidates were given to this source. Run thin, or check your source name.")
        elif not todo:
            lines.append("ENOUGH: yes. Every candidate you were given has a second page now. Stop and save.")
        else:
            lines.append("ENOUGH: no. Still on one page only: " + ", ".join(todo) + ".")
        if searches >= limit["searches"] and pages >= limit["pages"]:
            lines.append("Your budget is used. Stop and save.")
    elif family == "find-problems":
        limit = LIMITS["find-problems"]
        lines.append(f"{source}: searches {searches} of {limit['searches']}, pages {pages} of {limit['pages']}.")
        lines.append(left_line(folder, step, "search"))
        table = fp_table(rows)
        strong_ones = [c["id"] for c in table.values() if strong(c)]
        one_page = [c["id"] for c in table.values() if c["for_items"] >= 2 and c["pages"] == 1]
        if len(strong_ones) >= ENOUGH_STRONG_CANDIDATES:
            lines.append(f"ENOUGH: yes. {len(strong_ones)} candidates have {STRONG['items']}+ items from "
                         f"{STRONG['voices']}+ people on {STRONG['pages']}+ pages. Stop searching and save.")
        else:
            lines.append(f"ENOUGH: no. {len(strong_ones)} of {ENOUGH_STRONG_CANDIDATES} strong candidates so far"
                         f"{' (' + ', '.join(strong_ones) + ')' if strong_ones else ''}.")
            if one_page:
                lines.append("Candidates on one page only, worth a search for a second page: " + ", ".join(one_page) + ".")
        if searches >= limit["searches"] and pages >= limit["pages"]:
            lines.append("Your budget is used. Stop and save.")
    else:
        limit = LIMITS["evidence"]
        lines.append(f"{source}: searches {searches} of {limit['searches']}, pages {pages} of {limit['pages']} "
                     f"(the first researcher has {EXTRA_FIRST_RESEARCHER['searches']} extra searches and "
                     f"{EXTRA_FIRST_RESEARCHER['pages']} extra pages).")
        lines.append(left_line(folder, step, "research"))
        lines.append(evidence_enough(rows, source.upper()))
    return "\n".join(lines)


def evidence_enough(rows, assumption):
    searched = {r.get("side") for r in rows if r.get("type") == "search" and r.get("assumption") == assumption}
    opened = {r.get("side") for r in rows if r.get("type") == "page" and r.get("assumption") == assumption
              and r.get("outcome") == "opened"}
    items = [r for r in rows if r.get("type") == "item" and r.get("assumption") == assumption]
    covered = []
    for side in ("for", "against"):
        mine = [i for i in items if i["side"] == side]
        if (len({norm(i["who"]) for i in mine}) >= EVIDENCE_SIDE_COVERED["voices"]
                and len({page_of(i["link"]) for i in mine}) >= EVIDENCE_SIDE_COVERED["pages"]):
            covered.append(side)
    missing = []
    for side in ("for", "against"):
        if side not in searched:
            missing.append(f"no {side} search yet")
        if side not in opened:
            missing.append(f"no page opened for the {side} side yet")
    if not covered:
        missing.append(f"neither side has items from {EVIDENCE_SIDE_COVERED['voices']}+ people on "
                       f"{EVIDENCE_SIDE_COVERED['pages']}+ pages")
    if missing:
        return f"ENOUGH for {assumption}: no. " + "; ".join(missing) + "."
    return (f"ENOUGH for {assumption}: yes. Both sides searched and opened, and the {' and '.join(covered)} "
            f"side{'s are' if len(covered) > 1 else ' is'} well covered. Stop and save.")


def cmd_status(args):
    print(status_text(args.folder, args.step, args.source))


# ---------------------------------------------------------------- find-problems: the extra round

def checked_table(folder, step):
    """The checked items after the audit (checked-audited.json), or before it (checked-all.json)."""
    directory = log_dir(folder, step)
    for name in ("checked-audited.json", "checked-all.json"):
        path = directory / name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    raise Refused("No checked-all.json yet: run merge first.")


def extra_targets(folder, step):
    path = log_dir(folder, step) / "extra-targets.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("targets", [])


def new_pages(rows, target):
    """Pages, other than the target's one page, that now hold a "for" item for it."""
    return {page_of(r["link"]) for r in rows if r.get("type") == "item" and r.get("candidate") == target["id"]
            and r.get("side") == "for"} - {page_of(target["page"])}


def problems_on_list(folder):
    """(how many problems the built list holds, the (page, quote) of every item on it)."""
    path = Path(folder) / "discover-work" / "problems-audited.json"
    if not path.is_file():
        raise Refused("No discover-work/problems-audited.json yet: the list must be built before the extra round.")
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = {(page_of(i.get("link")), norm(i.get("quote"))) for p in data.get("problems", [])
            for i in p.get("items", []) if isinstance(i, dict)}
    return len(data.get("problems", [])), keys


def cmd_thin(args):
    """List the candidates that sit on one page, for the extra round (contract v2.1 point 2)."""
    if step_family(args.step) != "find-problems":
        raise Refused("thin is for find-problems only.")
    rows = all_rows(args.folder, args.step)
    table = checked_table(args.folder, args.step)
    n_problems, on_list = problems_on_list(args.folder)
    checked_ids = {i.get("id") for i in table.get("items", [])}
    targets = []
    for cand in fp_table(rows).values():
        counted_for = [i for i in table.get("items", []) if i.get("candidate") == cand["id"]
                       and i.get("result") == "counts" and i.get("side") == "for"]
        if any((page_of(i["link"]), norm(i["quote"])) in on_list for i in counted_for):
            continue  # already part of a problem on the list
        unchecked_for = [i for i in cand["items"] if i["side"] == "for" and i["id"] not in checked_ids]
        pool = counted_for + unchecked_for
        pages = {page_of(i["link"]) for i in pool}
        if len(pages) != 1:
            continue
        targets.append({"id": cand["id"], "statement": cand["statement"], "who": cand["who"],
                        "page": pool[0]["link"], "for_items": len(pool),
                        "voices": len({norm(i.get("voice") or i.get("who")) for i in pool})})
    targets.sort(key=lambda t: (-t["voices"], -t["for_items"], t["id"]))
    targets = targets[:EXTRA_TARGETS]
    searchers = min(EXTRA_SEARCHERS, len(targets))
    for index, target in enumerate(targets):
        target["searcher"] = f"second-{index % searchers + 1}"
    write_json(log_dir(args.folder, args.step) / "extra-targets.json",
               {"problems_on_list": n_problems, "searchers": searchers, "targets": targets})
    print(f"{n_problems} problem{'s' if n_problems != 1 else ''} on the list. "
          f"{'The list is thin: fewer than ' + str(THIN_LIST) + '.' if n_problems < THIN_LIST else 'The list is not thin.'}")
    if not targets:
        print("No candidate sits on one page, so an extra round has nothing to look for.")
        return
    print(f"{len(targets)} candidate{'s' if len(targets) != 1 else ''} on one page, for {searchers} "
          f"second-pages searcher{'s' if searchers != 1 else ''}:")
    for target in targets:
        print(f"  {target['searcher']}: {target['id']} {target['statement']} (on {target['page']})")


# ---------------------------------------------------------------- find-problems: shard, result, merge, apply

def fp_item_md(item):
    lines = [f"### {item['id']}", f"- Candidate: {item['candidate']}", f"- Side: {item['side']}",
             f"- Kind: {item['kind']}", f"- Quote: \"{item['quote']}\"", f"- Link: {item['link']}",
             f"- Who: {item['who']}", f"- When: {item['when']}", f"- Where: {item['where']}",
             f"- Group shown: {item['group_shown']}", f"- Action: {item['action']}", f"- Signal: {item['signal']}",
             f"- Opened: {item.get('opened', 'yes')}"]
    if item.get("also_on_page"):
        lines.append(f"- Also on this page: {item['also_on_page']}")
    if item.get("note"):
        lines.append(f"- Note: {item['note']}")
    return "\n".join(lines)


def cmd_shard(args):
    if step_family(args.step) != "find-problems":
        raise Refused("shard is for find-problems. For evidence, use ledger.")
    if args.extra:
        return shard_extra(args)
    rows = all_rows(args.folder, args.step)
    table = fp_table(rows)
    if not table:
        raise Refused("No candidates were logged, so there is nothing to check.")
    eligible = [c for c in table.values() if c["for_items"] >= CHECK_BAR["items"] and c["pages"] >= CHECK_BAR["pages"]]
    skipped = [c for c in table.values() if c not in eligible]
    total = sum(len(c["items"]) for c in eligible)
    shards_n = max(1, min(args.max, math.ceil(total / 10))) if eligible else 0
    shards = [[] for _ in range(shards_n)]
    for cand in sorted(eligible, key=lambda c: -len(c["items"])):
        target = min(range(shards_n), key=lambda i: sum(len(c["items"]) for c in shards[i]))
        shards[target].append(cand)
    data = discovery(args.folder)
    area = data.get("area", {}) if isinstance(data.get("area"), dict) else {}
    not_opened = [r for r in rows if r.get("type") == "not_opened"]
    directory = log_dir(args.folder, args.step)
    for old in directory.glob("shard-*"):
        old.unlink()
    for old in ("extra-targets.json", "checked-audited.json"):
        if (directory / old).is_file():
            (directory / old).unlink()
    summary = {"shards": [], "skipped": [{"id": c["id"], "statement": c["statement"], "for_items": c["for_items"],
                                          "pages": c["pages"]} for c in skipped]}
    for index, group in enumerate(shards, 1):
        items = [i for c in group for i in c["items"]]
        md = [f"# Problem candidates, shard {index} of {shards_n}", "", "Made with: /discover-find-problems",
              f"Date: {dt.date.today().isoformat()}", f"Area: {area.get('text', '')}",
              f"People: {area.get('people') or 'not given'}", "Status: not yet checked", "",
              "## Candidate problems"]
        for cand in group:
            md += [f"### {cand['id']}", f"- Statement: {cand['statement']}", f"- Who: {cand['who']}"]
        md += ["", "## Items"] + [fp_item_md(i) for i in items]
        md += ["", "## Not opened (all shards)"] + [f"- {r['link']} | {r['why']} | {r['held']}" for r in not_opened]
        (directory / f"shard-{index}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        write_json(directory / f"shard-{index}.json", {"candidates": [{k: c[k] for k in ("id", "statement", "who")}
                                                                       for c in group], "items": items})
        summary["shards"].append({"shard": index, "candidates": [c["id"] for c in group], "items": len(items)})
    write_json(directory / "shard-summary.json", summary)
    print(f"{shards_n} shard{'s' if shards_n != 1 else ''} for {len(eligible)} candidates, {total} items.")
    for entry in summary["shards"]:
        print(f"  shard {entry['shard']}: {', '.join(entry['candidates'])} ({entry['items']} items)")
    if skipped:
        print(f"Not checked, because they can't reach {CHECK_BAR['items']} counted items on {CHECK_BAR['pages']} "
              f"pages: {', '.join(c['id'] for c in skipped)}.")


def shard_extra(args):
    """The extra round's check: only items with no verdict yet, for candidates that can now reach the bar."""
    directory = log_dir(args.folder, args.step)
    summary_path = directory / "shard-summary.json"
    if not summary_path.is_file() or not (directory / "extra-targets.json").is_file():
        raise Refused("shard --extra needs the first round's shard-summary.json and extra-targets.json (run thin).")
    rows = all_rows(args.folder, args.step)
    table = checked_table(args.folder, args.step)
    checked_ids = {i.get("id") for i in table.get("items", [])}
    eligible, skipped = [], []
    for cand in fp_table(rows).values():
        fresh = [i for i in cand["items"] if i["id"] not in checked_ids]
        if not fresh:
            continue
        counted_for = [i for i in table.get("items", []) if i.get("candidate") == cand["id"]
                       and i.get("result") == "counts" and i.get("side") == "for"]
        pool = counted_for + [i for i in fresh if i["side"] == "for"]
        if len(pool) >= CHECK_BAR["items"] and len({page_of(i["link"]) for i in pool}) >= CHECK_BAR["pages"]:
            eligible.append({"cand": cand, "fresh": fresh, "counted_for": counted_for})
        else:
            skipped.append({"id": cand["id"], "statement": cand["statement"], "new_items": len(fresh)})
    total = sum(len(e["fresh"]) for e in eligible)
    shards_n = max(1, min(EXTRA_SHARDS, math.ceil(total / 10))) if eligible else 0
    shards = [[] for _ in range(shards_n)]
    for entry in sorted(eligible, key=lambda e: -len(e["fresh"])):
        target = min(range(shards_n), key=lambda i: sum(len(e["fresh"]) for e in shards[i]))
        shards[target].append(entry)
    data = discovery(args.folder)
    area = data.get("area", {}) if isinstance(data.get("area"), dict) else {}
    for old in directory.glob("shard-x*"):
        old.unlink()
    extra = []
    for index, group in enumerate(shards, 1):
        name = f"x{index}"
        items = [i for e in group for i in e["fresh"]]
        md = [f"# Problem candidates, extra round, shard {name}", "", "Made with: /discover-find-problems (extra round)",
              f"Date: {dt.date.today().isoformat()}", f"Area: {area.get('text', '')}",
              f"People: {area.get('people') or 'not given'}", "Status: not yet checked", "",
              "Only the items below need a verdict. The ones already counted are listed for reference: "
              "don't judge them again.", "", "## Candidate problems"]
        for e in group:
            cand = e["cand"]
            md += [f"### {cand['id']}", f"- Statement: {cand['statement']}", f"- Who: {cand['who']}",
                   "- Already counted for it (first round):"]
            md += [f"  - {i['id']} | {i.get('who', '')} | {i['link']}" for i in e["counted_for"]] or ["  - none"]
        md += ["", "## Items"] + [fp_item_md(i) for i in items]
        (directory / f"shard-{name}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
        write_json(directory / f"shard-{name}.json",
                   {"candidates": [{k: e["cand"][k] for k in ("id", "statement", "who")} for e in group],
                    "items": items})
        extra.append({"shard": name, "candidates": [e["cand"]["id"] for e in group], "items": len(items)})
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["extra"] = extra
    summary["extra_skipped"] = skipped
    write_json(summary_path, summary)
    print(f"Extra round: {shards_n} shard{'s' if shards_n != 1 else ''} for {len(eligible)} candidates, {total} new items.")
    for entry in extra:
        print(f"  shard {entry['shard']}: {', '.join(entry['candidates'])} ({entry['items']} items)")
    if skipped:
        print(f"Not checked, because they still can't reach {CHECK_BAR['items']} counted items on "
              f"{CHECK_BAR['pages']} pages: {', '.join(e['id'] for e in skipped)}.")


def check_result(row, family):
    if row.get("type") in ("done", "summary"):
        return
    if row.get("result") not in RESULTS:
        raise Refused('result must be counts, set aside or removed.')
    if row["result"] == "counts" and row.get("reason"):
        raise Refused("a counted item has an empty reason.")
    if row["result"] != "counts" and row.get("reason") not in REASONS:
        raise Refused(f'reason must be one of: {", ".join(sorted(REASONS))}.')
    if row.get("side") not in SIDES:
        raise Refused("side must be for, against or context.")
    if row.get("signal") not in SIGNALS:
        raise Refused(f'signal must be one of: {", ".join(SIGNALS)}.')
    if row.get("found_in_check"):
        fields = ITEM_FIELDS_FP if family == "find-problems" else ITEM_FIELDS_EV
        missing = [f for f in fields if f not in ("action", "group_shown") and not row.get(f)]
        if missing:
            raise Refused(f"an item found in the check needs: {', '.join(missing)}.")
        if not is_link(row["link"]):
            raise Refused("an item found in the check needs a link starting with http:// or https://.")
    elif not row.get("id"):
        raise Refused('a verdict names the item it is about, by "id".')


def cmd_result(args):
    family = step_family(args.step)
    rows = read_stdin_rows()
    path = log_dir(args.folder, args.step) / f"check-{args.shard}.jsonl"
    known = {r["id"] for r in all_rows(args.folder, args.step) if r.get("type") == "item"}
    stamp = iso(now())
    out = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise Refused(f"Input {index} is not a JSON object. Nothing was saved.")
        try:
            check_result(row, family)
            if row.get("id") and row.get("type") not in ("done", "summary") and not row.get("found_in_check") \
                    and row["id"] not in known:
                raise Refused(f'there is no item "{row["id"]}" in the log.')
        except Refused as error:
            raise Refused(f"Input {index}: {error} Nothing was saved.")
        row = dict(row)
        row["ts"] = stamp
        out.append(row)
    append_lines(path, out)
    done = read_lines(path)
    verdicts = sum(1 for r in done if r.get("type") not in ("done", "summary"))
    print(f"check {args.shard}: {verdicts} verdicts saved.")
    phase = "extra-check" if family == "find-problems" and args.shard.startswith("x") else "check"
    print(left_line(args.folder, args.step, phase))


def verdicts(folder, step):
    directory = log_dir(folder, step)
    out, done, summaries = {}, set(), []
    for path in sorted(directory.glob("check-*.jsonl")):
        shard = path.stem.split("-", 1)[1]
        for row in read_lines(path):
            if row.get("type") == "done":
                done.add(shard)
            elif row.get("type") == "summary":
                summaries.append(row)
            else:
                key = row.get("id") or f"check-{shard}-{len(out) + 1}"
                row.setdefault("id", key)
                out[key] = row  # a later verdict on the same item wins
    return out, done, summaries


def full_item(log_item, verdict, family):
    item = {
        "id": verdict.get("id") or log_item.get("id"),
        "side": verdict.get("side", log_item.get("side")),
        "result": verdict["result"],
        "reason": verdict.get("reason", "") if verdict["result"] != "counts" else "",
        "kind": verdict.get("kind", log_item.get("kind")),
        "quote": verdict.get("quote", log_item.get("quote")),
        "who": verdict.get("who", log_item.get("who")),
        "when": verdict.get("when", log_item.get("when")),
        "where": verdict.get("where", log_item.get("where")),
        "did": verdict.get("did", "" if norm(log_item.get("action")) in ("", "none") else log_item.get("action")),
        "note": verdict.get("note", ""),
        "link": verdict.get("link", log_item.get("link")),
        "voice": verdict.get("voice") or log_item.get("who") or "",
        "found_in_check": bool(verdict.get("found_in_check")),
        "signal": verdict.get("signal", log_item.get("signal")),
    }
    group = "candidate" if family == "find-problems" else "assumption"
    item[group] = verdict.get(group) or log_item.get(group)
    return item


def cmd_merge(args):
    family = step_family(args.step)
    if family != "find-problems":
        raise Refused("merge is for find-problems. For evidence, use assemble.")
    directory = log_dir(args.folder, args.step)
    summary_path = directory / "shard-summary.json"
    if not summary_path.is_file():
        raise Refused("No shard-summary.json: run shard first.")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    rows = all_rows(args.folder, args.step)
    log_items = {r["id"]: r for r in rows if r.get("type") == "item"}
    candidates = {r["id"]: r for r in rows if r.get("type") == "candidate"}
    to_check = set()
    for entry in summary["shards"] + summary.get("extra", []):
        shard = json.loads((directory / f"shard-{entry['shard']}.json").read_text(encoding="utf-8"))
        to_check |= {i["id"] for i in shard["items"]}
    found, done, _ = verdicts(args.folder, args.step)
    items, unchecked = [], []
    for item_id in sorted(to_check, key=lambda x: (x.split("-")[0], int(re.sub(r"\D", "", x.split("-E")[-1]) or 0))):
        if item_id in found:
            items.append(full_item(log_items[item_id], found[item_id], family))
        else:
            unchecked.append(item_id)
    for key, verdict in found.items():
        if verdict.get("found_in_check"):
            items.append(full_item({}, verdict, family))
    write_json(directory / "checked-all.json", {
        "candidates": [{k: c[k] for k in ("id", "statement", "who")} for c in candidates.values()],
        "skipped_candidates": summary.get("skipped", []),
        "items": items,
        "not_checked_in_time": unchecked,
        "shards_done": sorted(done),
        "shards": [e["shard"] for e in summary["shards"] + summary.get("extra", [])],
    })
    counted = sum(1 for i in items if i["result"] == "counts")
    print(f"{len(items)} items with a verdict: {counted} counted, "
          f"{sum(1 for i in items if i['result'] == 'set aside')} set aside, "
          f"{sum(1 for i in items if i['result'] == 'removed')} removed.")
    if unchecked:
        print(f"{len(unchecked)} items were not checked in time and stay out: {', '.join(unchecked)}.")
    missing = [str(e["shard"]) for e in summary["shards"] + summary.get("extra", []) if str(e["shard"]) not in done]
    if missing:
        print(f"Shards without a done line: {', '.join(missing)}.")


def cmd_apply(args):
    if step_family(args.step) != "find-problems":
        raise Refused("apply is for find-problems. Evidence corrections follow audit.md.")
    directory = log_dir(args.folder, args.step)
    table_path = directory / "checked-all.json"
    work = Path(args.folder) / "discover-work"
    audit_paths = [work / f"audit-find-problems-{n}.json" for n in (1, 2)
                   if (work / f"audit-find-problems-{n}.json").is_file()]
    if not table_path.is_file() or not (work / "audit-find-problems-1.json").is_file():
        raise Refused("apply needs checked-all.json (run merge) and discover-work/audit-find-problems-1.json.")
    table = json.loads(table_path.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in table["items"]}
    fixes = []
    for path in audit_paths:  # the first audit, then the extra round's audit, in that order
        fixes += [(path.stem[-1], fix) for fix in json.loads(path.read_text(encoding="utf-8")).get("corrections", [])]
    changed = 0
    for index, (audit_n, fix) in enumerate(fixes, 1):
        item = by_id.get(fix.get("id"))
        if item is None:
            raise Refused(f'Correction {index} (audit {audit_n}): no item "{fix.get("id")}" in checked-all.json. '
                          f"Nothing was applied.")
        for key in ("result", "reason", "side", "signal", "note", "candidate"):
            if key in fix:
                item[key] = fix[key]
        if item["result"] == "counts":
            item["reason"] = ""
        try:
            check_result(dict(item, type="item", found_in_check=False, id=item["id"]), "find-problems")
        except Refused as error:
            raise Refused(f"Correction {index} (audit {audit_n}, {item['id']}): {error} Nothing was applied.")
        changed += 1
    write_json(directory / "checked-audited.json", table)
    print(f"{changed} corrections applied from {len(audit_paths)} audit{'s' if len(audit_paths) != 1 else ''}. "
          f"Saved checked-audited.json.")


# ---------------------------------------------------------------- pairs for the audit

def group_key(item):
    return item.get("candidate") or item.get("assumption") or ""


def cmd_pairs(args):
    family = step_family(args.step)
    directory = log_dir(args.folder, args.step)
    extra_ids = set()
    if family == "find-problems":
        path = directory / "checked-all.json"
        if not path.is_file():
            raise Refused("Run merge first.")
        items = json.loads(path.read_text(encoding="utf-8"))["items"]
        summary_path = directory / "shard-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
        for entry in summary.get("extra", []):
            shard = json.loads((directory / f"shard-{entry['shard']}.json").read_text(encoding="utf-8"))
            extra_ids.update(i["id"] for i in shard["items"])
            extra_ids.update(i["id"] for i in items if str(i.get("id", "")).startswith(f"check-{entry['shard']}-"))
    else:
        name = "evidence.json" if family == "evidence" else f"evidence-{args.step}.json"
        path = Path(args.folder) / "discover-work" / name
        if not path.is_file():
            raise Refused(f"Run assemble first: {name} is missing.")
        evidence = json.loads(path.read_text(encoding="utf-8"))
        items = []
        for result in evidence.get("results", []):
            for n, item in enumerate(result.get("items", []), 1):
                items.append(dict(item, assumption=result["assumption"], id=f"{result['assumption']}#{n}"))
    pairs = []
    lookup = {i["id"]: i for i in items}

    def show(item_id):
        i = lookup[item_id]
        return {"id": item_id, "under": group_key(i), "side": i["side"], "result": i["result"],
                "reason": i.get("reason", ""), "who": i.get("who", ""), "link": i["link"],
                "quote_starts": " ".join((i.get("quote") or "").split()[:8])}

    def add(kind, ids, hint):
        entry = {"n": len(pairs) + 1, "kind": kind, "items": [show(x) for x in ids], "hint": hint}
        if extra_ids:
            entry["extra_round"] = any(x in extra_ids for x in ids)
        pairs.append(entry)

    this_year = dt.date.today().year
    for item in items:
        year = year_of(item.get("when"))
        if item["result"] == "counts" and year and this_year - year > OLD_YEARS:
            add("old but counted", [item["id"]], f"dated {year}, more than {OLD_YEARS} years ago, yet counted")
        if item["result"] != "counts" and item.get("reason") == "old" and year and this_year - year <= OLD_YEARS:
            add("recent but set aside as old", [item["id"]], f"dated {year}, within {OLD_YEARS} years")
        if item["result"] == "counts" and CONCEDING.search(item.get("note") or ""):
            add("counted, but its note sounds like a reason", [item["id"]], item.get("note", "")[:160])
    by = {}
    for item in items:
        by.setdefault(("page", group_key(item), page_of(item["link"])), []).append(item)
        by.setdefault(("voice", norm(item.get("voice") or item.get("who"))), []).append(item)
        by.setdefault(("site", site_of(item["link"])), []).append(item)
    for key, group in by.items():
        results = {(i["result"], i.get("reason", "")) for i in group}
        if len(group) < 2 or len(results) < 2:
            continue
        ids = [i["id"] for i in group]
        if key[0] == "page":
            add("same page, different results", ids, f"{key[2]} under {key[1]}")
        elif key[0] == "voice" and key[1]:
            add("same person, different results", ids, key[1])
        elif key[0] == "site":
            reasons = {i.get("reason") for i in group if i["result"] != "counts"}
            if reasons & {"stake", "not_original", "second_hand", "author_not_shown", "group_not_shown"}:
                add("same site, judged differently", ids, f"{key[1]}: {', '.join(sorted(r for r in reasons if r))}")
    groups = {}
    for item in items:
        groups.setdefault(group_key(item), []).append(item)
    for name, group in groups.items():
        for reason in sorted({i.get("reason") for i in group if i["result"] != "counts" and i.get("reason")}):
            sides = {i["side"] for i in group if i.get("reason") == reason and i["result"] != "counts"}
            for side in ("for", "against"):
                other = "against" if side == "for" else "for"
                if side in sides and other not in sides and any(i["side"] == other and i["result"] == "counts"
                                                                 for i in group):
                    add("reason used on one side only", [i["id"] for i in group if i.get("reason") == reason
                                                         or (i["side"] == other and i["result"] == "counts")],
                        f'{name}: "{reason}" sets aside {side} items; check the counted {other} items against it')
        set_aside = [i for i in group if i["result"] != "counts"]
        if group and len(set_aside) / len(group) > 0.75:
            add("more than 75% set aside", [i["id"] for i in set_aside],
                f"{name}: {len(set_aside)} of {len(group)} set aside; write a reason line for each, restore any without one")
    out_path = directory / "pairs.json"
    write_json(out_path, {"step": args.step, "pairs": pairs})
    print(f"{len(pairs)} pairs or groups for the audit to look at first. Saved {out_path.name}.")


# ---------------------------------------------------------------- evidence: ledger and assemble

def cmd_ledger(args):
    family = step_family(args.step)
    if family == "find-problems":
        raise Refused("ledger is for evidence and top-ups. For find-problems, use shard.")
    rows = all_rows(args.folder, args.step)
    data = discovery(args.folder)
    by_id = {a.get("id"): a for a in data.get("assumptions", []) if isinstance(a, dict)}
    run_on = args.run_on.split(",") if args.run_on else [s.upper() for s in
                                                          sorted({r["source"] for r in rows if r.get("source")})]
    work = Path(args.folder) / "discover-work"
    options = [r for r in rows if r.get("type") == "option"]
    written = []
    for index, aid in enumerate(run_on):
        a = by_id.get(aid, {})
        items = [r for r in rows if r.get("type") == "item" and r.get("assumption") == aid]
        searches = [r for r in rows if r.get("type") == "search"
                    and (r.get("assumption") == aid or (index == 0 and r.get("side") == "extra"))]
        md = ["# Evidence ledger", "", f"Made with: /discover-evidence ({args.step})",
              f"Date: {dt.date.today().isoformat()}", "Status: not yet checked", "",
              "## Idea", (data.get("idea") or {}).get("sentence", ""), "", "## Who counts",
              data.get("who_counts", ""), "", "## Assumptions", f"### {aid} ({a.get('kind', '')})",
              a.get("statement", ""), f"- If true, we'd expect to find: {a.get('if_true', '')}",
              f"- If false, we'd expect to find: {a.get('if_false', '')}",
              f"- Needs a count: {'yes' if a.get('needs_number') else 'no'}", "", "## Searches",
              "| # | Assumption | Side | Kind | Search words | What came back |", "|---|---|---|---|---|---|"]
        for n, s in enumerate(searches, 1):
            md.append(f"| S{n} | {s.get('assumption', 'all')} | {s.get('side', '')} | {s.get('kind', '')} | "
                      f"{s['words']} | {s.get('came_back', '')} |")
        md += ["", "## Evidence"]
        for item in items:
            md += [f"### {item['id']}", f"- Assumption: {aid}", f"- Side: {item['side']}", f"- Kind: {item['kind']}",
                   f"- Quote: \"{item['quote']}\"", f"- Link: {item['link']}", f"- Who: {item['who']}",
                   f"- When: {item['when']}", f"- Where: {item['where']}", f"- Group shown: {item['group_shown']}",
                   f"- Action: {item['action']}", f"- Signal: {item['signal']}",
                   f"- Opened: {item.get('opened', 'yes')}"]
            if item.get("also_on_page"):
                md.append(f"- Also on this page: {item['also_on_page']}")
            if item.get("note"):
                md.append(f"- Note: {item['note']}")
        md += ["", "## Existing options that came up"]
        if index == 0:
            md += [f"- {o['name']} | {o['link']} | {o['kind']} | {o['fact']}"
                   + (f" | {o['date']}" if o.get("date") else "") for o in options]
        else:
            md.append(f"- (checked by the {run_on[0]} checker)")
        md += ["", "## Nothing found"]
        md += [f"- {aid}, {r.get('side', '')}, {r.get('kind', '')}: tried {r['tried']}"
               for r in rows if r.get("type") == "nothing_found" and r.get("assumption") == aid]
        md += ["", "## Not opened"]
        md += [f"- {r['link']} | {r['why']} | {aid} | {r['side']} | {r['held']}"
               for r in rows if r.get("type") == "not_opened" and r.get("assumption") == aid]
        name = f"evidence-ledger-{aid}.md" if family == "evidence" else f"evidence-{args.step}-ledger-{aid}.md"
        (work / name).write_text("\n".join(md) + "\n", encoding="utf-8")
        written.append(f"{name} ({len(items)} items)")
    print("Wrote " + "; ".join(written) + ".")


def cmd_assemble(args):
    family = step_family(args.step)
    if family == "find-problems":
        raise Refused("assemble is for evidence and top-ups.")
    if not args.run_on:
        raise Refused("assemble needs --run-on, for example A1,A2,A4.")
    run_on = args.run_on.split(",")
    rows = all_rows(args.folder, args.step)
    found, done, summaries = verdicts(args.folder, args.step)
    by_assumption = {s.get("assumption"): s for s in summaries}
    earlier = {}
    if family == "topup":
        section = discovery(args.folder).get("evidence") or {}
        earlier = {r.get("assumption"): r for r in section.get("results", []) if isinstance(r, dict)}
    results, problems = [], []
    unread_total = sum(1 for r in rows if r.get("type") == "not_opened")
    checker_searches = sum(int(s.get("searches", 0)) for s in summaries)
    checker_pages = sum(int(s.get("pages_opened", 0)) for s in summaries)
    for aid in run_on:
        log_items = [r for r in rows if r.get("type") == "item" and r.get("assumption") == aid]
        items, unchecked_pages = [], {"for": set(), "against": set()}
        for log_item in log_items:
            verdict = found.get(log_item["id"])
            if verdict:
                items.append(full_item(log_item, verdict, family))
            elif log_item["side"] in unchecked_pages:
                unchecked_pages[log_item["side"]].add(page_of(log_item["link"]))
        for verdict in found.values():
            if verdict.get("found_in_check") and verdict.get("assumption") == aid:
                items.append(full_item({}, verdict, family))
        base = earlier.get(aid)
        if base:
            # a top-up refreshes an earlier result: keep its items, apply changed verdicts, add the new ones
            kept = [dict(i) for i in base.get("items", [])]
            index = {(page_of(i["link"]), norm(i["quote"])): i for i in kept}
            fresh = []
            for i in items:
                match = index.get((page_of(i["link"]), norm(i["quote"])))
                if match is not None:
                    for key in ("side", "result", "reason", "signal", "note", "did", "voice"):
                        match[key] = i[key]
                else:
                    fresh.append(i)
            items = kept + fresh
        checked_pages = {page_of(i["link"]) for i in items}
        unread = {}
        for side in ("for", "against"):
            lines = sum(1 for r in rows if r.get("type") == "not_opened" and r.get("assumption") == aid
                        and r.get("side") == side)
            unread[side] = lines + len(unchecked_pages[side] - checked_pages)
            if base:
                unread[side] += int((base.get("unread") or {}).get(side, 0))
        # Contract v1.7 point 8 (built in v2.2): unread pages whose side wasn't clear get their own count.
        unclear = sum(1 for r in rows if r.get("type") == "not_opened" and r.get("assumption") == aid
                      and r.get("side") == "unclear")
        if base:
            unclear += int((base.get("unread") or {}).get("unclear", 0))
        if unclear:
            unread["unclear"] = unclear
        unread_total += sum(len(unchecked_pages[s] - checked_pages) for s in unchecked_pages)
        summary = by_assumption.get(aid)
        if summary is None and base:
            summary = {"still_open": base.get("still_open"), "not_found": base.get("not_found")}
        elif summary is None:
            problems.append(f"{aid}: the checker saved no summary, so a plain line was used.")
        still_open = (summary or {}).get("still_open") or "This assumption wasn't fully checked within the time limit."
        not_found = list((summary or {}).get("not_found") or [])
        if unread["for"] or unread["against"] or unread.get("unclear"):
            not_found = [line if "in the pages read" in line else line.rstrip(".") + " in the pages read."
                         for line in not_found]
        clean = [{k: i.get(k, "" if k != "found_in_check" else False)
                  for k in ("side", "result", "reason", "kind", "quote", "who", "when", "where", "did",
                            "note", "link", "voice", "found_in_check", "signal")} for i in items]
        results.append({"assumption": aid, "still_open": still_open, "not_found": not_found,
                        "unread": unread, "items": clean})
    counted_quotes = " ".join(norm(i["quote"]) for r in results for i in r["items"]
                              if i["result"] == "counts" and i["kind"] == "own words" and i["side"] in ("for", "against"))
    language = []
    for s in summaries:
        for phrase in s.get("language", []) or []:
            if norm(phrase) and norm(phrase) in counted_quotes and phrase not in language:
                language.append(phrase)
    products = []
    for s in summaries:
        for p in s.get("products", []) or []:
            if p.get("link") not in {q.get("link") for q in products}:
                products.append(p)
    lanes = []
    for r in results:
        counted = [i for i in r["items"] if i["result"] == "counts" and i["side"] in ("for", "against")]
        counted.sort(key=lambda i: (i["kind"] != "own words", i["did"] == ""))
        lanes.append([i["link"] for i in counted])
    suggested = []
    while any(lanes) and len(suggested) < 5:
        for lane in lanes:
            while lane and lane[0] in suggested:
                lane.pop(0)
            if lane and len(suggested) < 5:
                suggested.append(lane.pop(0))
    wouldnt = [{"site": site_of(r["link"]), "link": r["link"]} for r in rows
               if r.get("type") == "not_opened" and "block" in norm(r.get("why"))]
    wouldnt += [{"site": site_of(r["link"]), "link": r["link"]} for r in rows
                if r.get("type") == "page" and r.get("outcome") == "failed"]
    seen, wouldnt_open = set(), []
    for w in wouldnt:
        if w["link"] not in seen and len(wouldnt_open) < 3:
            seen.add(w["link"])
            wouldnt_open.append(w)
    evidence = {
        "run_on": run_on,
        "results": results,
        "products": products[:4],
        "language": language[:8],
        "unread_pages": {"count": max(unread_total, sum(r["unread"]["for"] + r["unread"]["against"]
                                                        + r["unread"].get("unclear", 0) for r in results)),
                         "wouldnt_open": wouldnt_open},
        "checked": {"searches": sum(1 for r in rows if r.get("type") == "search") + checker_searches,
                    "pages_read": sum(1 for r in rows if r.get("type") == "page") + checker_pages},
        "suggested_checks": suggested,
        "checked_in_fresh_context": True,
    }
    name = "evidence.json" if family == "evidence" else f"evidence-{args.step}.json"
    write_json(Path(args.folder) / "discover-work" / name, evidence)
    print(f"Saved {name}: {len(results)} assumptions, "
          f"{sum(len(r['items']) for r in results)} items with a verdict, "
          f"{sum(1 for r in results for i in r['items'] if i['result'] == 'counts')} counted.")
    for line in problems:
        print(line)


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(description="The discover kit's evidence log. Run as a command only.")
    sub = parser.add_subparsers(dest="command", required=True)

    def command(name, func, **extra):
        p = sub.add_parser(name)
        p.add_argument("--folder", default=".")
        p.add_argument("--step", required=True)
        for flag, options in extra.items():
            p.add_argument(flag, **options)
        p.set_defaults(func=func)

    command("clock", cmd_clock, **{"--phase": {"required": True}, "--minutes": {"type": float}})
    command("left", cmd_left, **{"--phase": {"required": True}})
    command("add", cmd_add, **{"--source": {"required": True}})
    command("candidates", cmd_candidates)
    command("status", cmd_status, **{"--source": {"required": True}})
    command("shard", cmd_shard, **{"--max": {"type": int, "default": 4}, "--extra": {"action": "store_true"}})
    command("thin", cmd_thin)
    command("ledger", cmd_ledger, **{"--run-on": {"default": ""}})
    command("result", cmd_result, **{"--shard": {"required": True}})
    command("merge", cmd_merge)
    command("pairs", cmd_pairs)
    command("apply", cmd_apply)
    command("assemble", cmd_assemble, **{"--run-on": {"default": ""}})
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Refused as error:
        print(f"Not done: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
