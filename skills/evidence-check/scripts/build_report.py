#!/usr/bin/env python3
"""Build the one-page evidence report.

Usage:
    python build_report.py report.json [evidence-report.html]

Reads the report data, checks it, works out the label for each assumption
from the items (so the label never depends on anyone's judgement), and writes
one self-contained HTML page.

If the data has problems, nothing is written and the problems are listed.
"""
import json
import pathlib
import re
import sys

SIDES = {"for", "against", "context"}
RESULTS = {"counts", "set aside", "removed"}
KINDS = {"own words", "number", "organisation fact"}
REASONS = {
    "second_hand", "stake", "not_original", "vague_amount", "indirect",
    "group_not_shown", "old", "could_not_open", "pasted", "not_on_page",
    "off_target",
}
LABELS = {
    "supported": "The web backs this up",
    "contradicted": "The web points the other way",
    "mixed": "People are split",
    "thin": "Too little to tell",
    "nothing": "Nothing solid found",
}


def is_link(value):
    return isinstance(value, str) and re.match(r"https?://\S+$", value) is not None


def page_of(link):
    """Two links to the same page (ignoring #fragment and ?query) are one page."""
    return re.sub(r"[#?].*$", "", link).rstrip("/").lower()


def text(value):
    return isinstance(value, str) and value.strip() != ""


def check(data):
    problems = []

    def need(cond, message):
        if not cond:
            problems.append(message)

    for key in ("idea", "date", "who_counts", "talk_to"):
        need(text(data.get(key)), f'"{key}" is missing or empty.')

    assumptions = data.get("assumptions")
    need(isinstance(assumptions, list) and 1 <= len(assumptions) <= 3,
         '"assumptions" must be a list of 1 to 3.')
    for a_index, a in enumerate(assumptions or [], 1):
        where = f"Assumption {a_index}"
        need(text(a.get("statement")), f"{where}: no statement.")
        need(isinstance(a.get("needs_number"), bool),
             f'{where}: "needs_number" must be true or false.')
        for i_index, item in enumerate(a.get("items") or [], 1):
            spot = f"{where}, item {i_index}"
            need(item.get("side") in SIDES, f'{spot}: "side" must be one of {sorted(SIDES)}.')
            need(item.get("result") in RESULTS,
                 f'{spot}: "result" must be one of {sorted(RESULTS)}.')
            need(item.get("kind") in KINDS, f'{spot}: "kind" must be one of {sorted(KINDS)}.')
            need(text(item.get("quote")), f"{spot}: no quote.")
            need(is_link(item.get("link")), f"{spot}: the link must start with http:// or https://.")
            need(text(item.get("who")), f'{spot}: "who" is empty.')
            need(text(item.get("voice")), f'{spot}: "voice" is empty.')
            if item.get("result") in ("set aside", "removed"):
                need(item.get("reason") in REASONS,
                     f'{spot}: a set aside or removed item needs a "reason" from {sorted(REASONS)}.')
            if item.get("result") == "counts" and item.get("side") in ("for", "against"):
                need(not item.get("reason"),
                     f'{spot}: an item that counts must not carry a "reason". Use "note" for a caveat.')

    questions = data.get("questions")
    need(isinstance(questions, list) and len(questions) == 5, "There must be exactly 5 interview questions.")
    for q_index, q in enumerate(questions or [], 1):
        q_text = q.get("text", "") if isinstance(q, dict) else ""
        need(text(q_text), f"Question {q_index}: empty.")
        need(text(q.get("tests") if isinstance(q, dict) else ""), f'Question {q_index}: say what it "tests".')
        if re.search(r"\bwould you\b|\bwill you\b|\bwould your\b", q_text, re.I):
            problems.append(
                f"Question {q_index}: ask what the person did, not what they would do.")

    for p_index, product in enumerate(data.get("products") or [], 1):
        need(text(product.get("name")), f"Product {p_index}: no name.")
        need(is_link(product.get("link")), f"Product {p_index}: the link must start with http.")
        need(text(product.get("fact")), f"Product {p_index}: no fact.")
    need(len(data.get("products") or []) <= 4, "List at most 4 products.")

    for i_index, entry in enumerate(data.get("interviews_only") or [], 1):
        need(text(entry.get("statement")), f"Interview-only item {i_index}: no statement.")
        need(text(entry.get("reason")), f"Interview-only item {i_index}: no reason.")

    unread = data.get("unread_pages") or {}
    for u_index, page in enumerate(unread.get("wouldnt_open") or [], 1):
        need(is_link(page.get("link")), f"Unread page {u_index}: the link must start with http.")

    checked = data.get("checked") or {}
    for key in ("searches", "pages_read"):
        need(isinstance(checked.get(key), int), f'"checked.{key}" must be a whole number.')
    return problems


def grade(assumption):
    """Work out the label from the items. Mechanical on purpose."""
    sides = {}
    for side in ("for", "against"):
        counted = [i for i in assumption.get("items", [])
                   if i["side"] == side and i["result"] == "counts"]
        sides[side] = {
            "voices": len({i["voice"].strip().lower() for i in counted}),
            "pages": len({page_of(i["link"]) for i in counted}),
            "acted": any(text(i.get("did")) or i["kind"] != "own words" for i in counted),
            "number": any(i["kind"] == "number" for i in counted),
        }
    f, a = sides["for"], sides["against"]
    why = ""
    if f["voices"] == 0 and a["voices"] == 0:
        status = "nothing"
    elif f["voices"] > 0 and a["voices"] > 0:
        status = "mixed"
    else:
        name, side = ("supported", f) if f["voices"] else ("contradicted", a)
        if side["voices"] < 2:
            status, why = "thin", "one_voice"
        elif side["pages"] < 2:
            status, why = "thin", "one_page"
        elif not side["acted"]:
            status, why = "thin", "opinions_only"
        elif assumption.get("needs_number") and not side["number"]:
            status, why = "thin", "needs_number"
        else:
            status = name
    all_counted = [i for i in assumption.get("items", [])
                   if i["result"] == "counts" and i["side"] in ("for", "against")]
    assumption["_grade"] = {
        "status": status,
        "why": why,
        "for": f["voices"],
        "against": a["voices"],
        "voices": len({i["voice"].strip().lower() for i in all_counted}),
        "pages": len({page_of(i["link"]) for i in all_counted}),
    }
    return assumption["_grade"]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    source = pathlib.Path(sys.argv[1])
    target = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("evidence-report.html")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"Could not read {source}: {error}")
        return 1

    problems = check(data)
    if problems:
        print("The report was NOT built. Fix these in the data and run again:")
        for problem in problems:
            print(" -", problem)
        return 1

    for index, assumption in enumerate(data["assumptions"], 1):
        g = grade(assumption)
        print(f'Assumption {index}: {LABELS[g["status"]]} '
              f'({g["for"]} for, {g["against"]} against, on {g["pages"]} page(s))')

    template = (pathlib.Path(__file__).resolve().parent.parent / "assets" / "report-template.html")
    page = template.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    if "__REPORT_DATA__" not in page:
        print("The template has no __REPORT_DATA__ marker.")
        return 1
    target.write_text(page.replace("__REPORT_DATA__", payload), encoding="utf-8")
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
