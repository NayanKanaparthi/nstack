#!/usr/bin/env python3
"""Smoke Test helper. Python standard library only.

Commands:
  fit      --belief B --customer C [--weeks N] [--budget USD]
  card     --in card.json --out DIR
  results  --plan smoke-test-plan.md --reached N --acted K
           [--warm-reached N --warm-acted K] [--variant NAME:REACHED:ACTED ...] --out DIR
  look     --in look.json [--page FILE ...]
           checks the chosen look before anything is designed, and that a page uses only its colours

Part of Leverage by BCE. Designed and built by Nayan Kanaparthi,
Berkley Center for Entrepreneurship, NYU Stern.
"""
import argparse
import colorsys
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys

VERSION = "0.2.2"
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "plan-template.html")

BELIEFS = {
    "problem": "Is the problem real and painful?",
    "who": "Who feels it most?",
    "want": "Do they want this solution?",
    "version": "Which design, message or price lands best?",
    "pay": "Will they pay?",
    "reach": "Can we reach them at all?",
}
CUSTOMERS = {
    "consumer_digital": "Consumer, digital product",
    "consumer_physical": "Consumer, physical product",
    "b2b": "Business customer (B2B)",
    "service": "Service",
    "marketplace": "Marketplace",
}

# strength: 1 said, 2 attention, 3 cheap action, 4 costly non-cash, 5 money
TESTS = {
    "T1": dict(name="Community post to learn", learning=True, strength="1 to 2",
               measures="How practitioners react: pushback, their own words, how they cope today",
               weeks=(0.2, 1), cost=(0, 0), cant="Demand or willingness to pay. Commenters skew loud.",
               needs="A community where these people already talk, whose rules allow the post",
               rules=[5, 6, 12, 15]),
    "T2": dict(name="Problem posts or reels", learning=True, strength="2",
               measures="Whether strangers recognise the pain, and the words they use in comments",
               weeks=(2, 3), cost=(0, 100), cant="Willingness to pay. The algorithm distorts reach.",
               needs="An account that can post 10 to 15 times in 2 to 3 weeks",
               rules=[5, 6, 9, 15]),
    "T3": dict(name="Explainer video plus one ask", learning=False, strength="2 to 3",
               measures="Whether people understand it and act on the ask",
               weeks=(0.6, 2.5), cost=(0, 600), cant="Willingness to pay. Polish inflates results.",
               needs="A 60 to 90 second video and a page or form for the ask",
               rules=[2, 5, 6, 7, 9, 10, 13, 15]),
    "T4": dict(name="Landing page with a costly second step", learning=False, strength="3 to 4",
               measures="Strangers converting to an act that costs something (email plus a short question, or booking a call)",
               weeks=(0.6, 2.5), cost=(0, 600), cant="Willingness to pay. Warm traffic overstates.",
               needs="A free page and form tool, and a way to send strangers to it",
               rules=[2, 6, 7, 10, 13, 15]),
    "T5": dict(name="Mock product or pricing page", learning=False, strength="3",
               measures="Add-to-cart or plan clicks at a shown price, followed by an honest 'not built yet' page",
               weeks=(0.6, 3), cost=(0, 600), cant="Real buying. No money moves.",
               needs="A mock page with a price and a cart button, and a way to send strangers to it",
               rules=[1, 2, 4, 6, 7, 9, 10, 13, 15]),
    "T6": dict(name="AI-designed ad campaign", learning=False, strength="3",
               measures="2 to 4 design or message variants shown to cold audiences, each leading to a mock page. Shows which variant wins and whether strangers carry on to a costly act.",
               weeks=(1, 2), cost=(0, 100), cant="Willingness to pay. Each variant needs its own sample, so the people needed multiply.",
               needs="An image tool for the visuals, a mock page per variant, and a channel to strangers (organic posts or a small paid ad)",
               rules=[1, 2, 4, 6, 7, 9, 10, 13, 15]),
    "T7": dict(name="Segment comparison", learning=False, strength="3",
               measures="The same offer shown to 2 or 3 audiences, with the act rate compared across them",
               weeks=(1, 2), cost=(0, 100), cant="Willingness to pay. Small samples rarely separate close segments.",
               needs="A way to reach each audience separately and count each one's acts",
               rules=[2, 6, 7, 10, 13, 15]),
    "T8": dict(name="Refundable deposit or pre-order", learning=False, strength="5",
               measures="Money committed",
               weeks=(3, 8), cost=(0, 50), cant="Whether you can deliver. Brings legal duties.",
               needs="A payment tool with refunds, a ship date you have grounds for, and a refund plan",
               rules=[3, 4, 6, 7, 9, 10, 13, 15]),
    "T9": dict(name="Concierge (done by hand, the customer knows)", learning=False, strength="3, or 5 if paid",
               measures="Whether hand-delivered value solves the problem, paid or not",
               weeks=(2, 12), cost=(0, 300), cant="Whether software will satisfy them. Personal-service halo.",
               needs="Time to deliver the service by hand to a few real customers",
               rules=[3, 4, 6, 7, 13, 15]),
    "T10": dict(name="Wizard of Oz (done by hand, hidden)", learning=False, strength="3 to 4",
                measures="Uptake of a defined solution",
                weeks=(2, 8), cost=(0, 300), cant="Whether the problem is real. Hard to run fully in a semester.",
                needs="A front end people use, with a person doing the work behind it",
                rules=[2, 4, 6, 7, 13, 15]),
    "T11": dict(name="Demo or consultation request page", learning=False, strength="4",
                measures="Booked meetings from the right roles",
                weeks=(0.5, 5), cost=(0, 0), cant="Whether the problem is real. Founder charm.",
                needs="A page with a booking form, and a list of people in the buying role to reach",
                rules=[2, 6, 7, 8, 10, 13, 15]),
    "T12": dict(name="Gated guide or white paper", learning=False, strength="3",
                measures="Downloads with contact details from target roles",
                weeks=(1, 3), cost=(0, 19), cant="Willingness to pay.",
                needs="A short useful guide on the problem, and a page and form to gate it",
                rules=[2, 6, 7, 8, 10, 13, 15]),
    "T13": dict(name="Pitch with a yes or no ask", learning=False, strength="4",
                measures="A buyer's yes or no, or a letter of intent with price, scope and date",
                weeks=(0.5, 5), cost=(0, 0), cant="Binding demand. Fewer than 10 pitches is directional only.",
                needs="At least 10 meetings with people who can buy",
                rules=[6, 8, 13, 15]),
    "T14": dict(name="One-side marketplace test", learning=False, strength="varies",
                measures="One side's behaviour, with the other side faked by hand",
                weeks=(1, 4), cost=(0, 100), cant="The other side's behaviour.",
                needs="A way to reach one side and fulfil the other side by hand",
                rules=[2, 4, 6, 7, 13, 15]),
}

FIT = {
    ("problem", "consumer_digital"): ["T1", "T2"],
    ("problem", "consumer_physical"): ["T1", "T2"],
    ("problem", "b2b"): ["T1", "T12"],
    ("problem", "service"): ["T1", "T9"],
    ("problem", "marketplace"): ["T1"],
    ("who", "consumer_digital"): ["T7"],
    ("who", "consumer_physical"): ["T7"],
    ("who", "b2b"): ["T7", "T11"],
    ("who", "service"): ["T7"],
    ("who", "marketplace"): ["T7"],
    ("want", "consumer_digital"): ["T4", "T5", "T3"],
    ("want", "consumer_physical"): ["T6", "T5"],
    ("want", "b2b"): ["T11", "T13"],
    ("want", "service"): ["T9", "T4"],
    ("want", "marketplace"): ["T14"],
    ("version", "consumer_digital"): ["T6", "T5"],
    ("version", "consumer_physical"): ["T6"],
    ("version", "b2b"): ["T6", "T12"],
    ("version", "service"): ["T6"],
    ("version", "marketplace"): ["T6"],
    ("pay", "consumer_digital"): ["T5", "T8"],
    ("pay", "consumer_physical"): ["T8", "T5"],
    ("pay", "b2b"): ["T13", "T11"],
    ("pay", "service"): ["T9", "T8"],
    ("pay", "marketplace"): ["T14"],
    ("reach", "consumer_digital"): ["T6", "T4"],
    ("reach", "consumer_physical"): ["T6"],
    ("reach", "b2b"): ["T11", "T12"],
    ("reach", "service"): ["T4"],
    ("reach", "marketplace"): ["T14"],
}
# Second-choice row used to top a short list up to 2 or 3 (same customer type, nearest belief).
NEAR = {
    "problem": ["who"], "who": ["want", "problem"], "want": ["version", "pay"],
    "version": ["want"], "pay": ["want"], "reach": ["want"],
}

RULES = {
    1: "No card details are ever collected in a fake checkout. The flow stops at add-to-cart or the checkout view.",
    2: "Every buy, demo or download button leads to a plain 'not built yet' page in the same flow.",
    3: "If money is taken: a ship date you have grounds for (or ship within 30 days), an offer to cancel, and a refund within 7 working days (FTC Mail Order Rule).",
    4: "No made-up testimonials, user counts, logos, press or reviews.",
    5: "Any post about your own idea says 'I'm building this'. Friends and classmates who share it disclose the connection.",
    6: "No claim without evidence. Outcomes are written as goals.",
    7: "Any form that collects an email or phone number shows a privacy note: what is collected, why, who sees it, how to be removed.",
    8: "Cold email has an accurate sender, an honest subject, a postal address and an opt-out honoured within 10 business days (CAN-SPAM).",
    9: "AI images and video are labelled where the platform requires it, show only what you could really make, and are never used on a Kickstarter hardware page.",
    10: "The ad's promise matches the page.",
    12: "Read each community's posting rules before posting. Some places ban landing pages.",
    13: "Pass and kill lines are locked before launch.",
    15: "Interviewees appear as roles, never names. No contact details or interview quotes in public materials without the person's OK.",
}
ALWAYS_FLAG = "If results will be published beyond class (a website, posts about the results, a conference), check with NYU whether IRB review is needed."

PROVISO = ("This is a condensed version of real discovery. A week and a handful of interviews is a start, "
           "not a pattern. In the real world you would keep talking to people until the answers repeat.")

LOCKED = ["line", "group", "act", "numerator", "denominator", "pass_pct", "kill_pct",
          "people_needed", "variants", "by_date", "test_id"]


def die(code, msg):
    print(f"REFUSED {code}: {msg}")
    sys.exit(2)


def wk(v):
    return f"{v:g} week" + ("" if v == 1 else "s")


def money(lo, hi):
    return f"${lo}" if lo == hi else f"${lo} to ${hi}"


def cmd_fit(a):
    if a.belief not in BELIEFS:
        die("F1", f"belief must be one of: {', '.join(BELIEFS)}")
    if a.customer not in CUSTOMERS:
        die("F2", f"customer must be one of: {', '.join(CUSTOMERS)}")
    first = list(FIT[(a.belief, a.customer)])
    extra = []
    for nb in NEAR[a.belief]:
        for t in FIT.get((nb, a.customer), []):
            if t not in first and t not in extra:
                extra.append(t)
    keep, dropped = [], []
    for t in first + extra:
        x = TESTS[t]
        why = []
        if x["weeks"][0] > a.weeks:
            why.append(f"needs at least {wk(x['weeks'][0])}, you have {wk(a.weeks)}")
        if x["cost"][0] > a.budget:
            why.append(f"needs at least ${x['cost'][0]}, your budget is ${a.budget:g}")
        (dropped if why else keep).append((t, why))
    shown = [t for t, _ in keep][:3]
    from_first = [t for t in shown if t in first]
    print(f"Belief type: {a.belief} ({BELIEFS[a.belief]})")
    print(f"Customer type: {a.customer} ({CUSTOMERS[a.customer]})")
    print(f"Limits: {wk(a.weeks)}, ${a.budget:g}")
    print()
    if len(shown) < 2:
        print("FEWER THAN 2 TESTS FIT. Tell the student what would open more options:")
        for t, why in dropped:
            print(f"  {TESTS[t]['name']}: {'; '.join(why)}")
        print("Options: more time, more budget, or test a narrower group.")
    for t in shown:
        x = TESTS[t]
        tag = "fits this belief" if t in from_first else f"fits a nearby belief ({'/'.join(NEAR[a.belief])}), shown to give a second option"
        print(f"{x['name']}  ({tag}; id for card.json only, never show it: {t})")
        print(f"   Measures: {x['measures']}")
        print(f"   How convincing: {strength_words(x['strength'])}" + ("  (a learning test: reports themes, not a pass rate)" if x["learning"] else ""))
        print(f"   Time: {x['weeks'][0]:g} to {wk(x['weeks'][1])}. Cost: {money(*x['cost'])}")
        print(f"   Can't tell you: {x['cant']}")
        print(f"   You need: {x['needs']}")
    if not any(TESTS[t]["cost"][0] == 0 for t in shown) and shown:
        print("NOTE: no $0 option fits. Say so to the student.")
    if dropped:
        print()
        print("Left out by the limits: " + "; ".join(f"{TESTS[t]['name']} ({'; '.join(w)})" for t, w in dropped))
    print()
    print("Later, not in a semester: crowdfunding (6 to 10 weeks; Kickstarter needs working prototypes and bans photorealistic renders), paid pilots (2 to 6 months).")


STRENGTH_WORDS = {
    "1 to 2": "Weak: opinions and attention only. Good for learning, not for proving demand.",
    "2": "Weak: attention (views, comments), not action.",
    "2 to 3": "Weak to medium: attention plus a cheap action.",
    "3": "Medium: a cheap action (a click, an email), not a purchase.",
    "3 to 4": "Medium to strong: an action that costs a little time or information.",
    "3, or 5 if paid": "Medium, or strongest if people pay.",
    "4": "Strong: people give time or put their name to it.",
    "5": "Strongest: people put money down.",
    "varies": "Depends on what the real side is asked to do.",
}


def strength_words(x):
    return STRENGTH_WORDS.get(x, x)


def people_needed(pass_pct):
    n = 1000.0 / pass_pct
    return int(math.ceil(n / 10.0) * 10)


def fingerprint(locked):
    blob = json.dumps({k: locked[k] for k in LOCKED}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def iso(d, code):
    try:
        return dt.date.fromisoformat(d)
    except Exception:
        die(code, f"'{d}' is not a date like 2026-12-01")


REQUIRED = ["team", "belief", "belief_type", "customer_type", "test_id", "group", "act", "act_cost",
            "by_date", "start_date", "channel", "audience", "budget_usd", "on_pass", "on_kill", "on_unclear",
            "strength_line", "next_test", "interviews_behind", "proviso_shown"]
DEMAND_REQUIRED = ["numerator", "denominator", "pass_pct", "pass_reason", "kill_pct", "reach"]
LEARN_REQUIRED = ["learn_questions", "target_replies"]


def cmd_card(a):
    if not a.preview and not a.out:
        die("C0", "give --out <download folder> to lock, or --preview to check the numbers first")
    with open(a.input, encoding="utf-8") as f:
        c = json.load(f)
    missing = [k for k in REQUIRED if c.get(k) in (None, "", [])]
    if missing:
        die("C1", "these card fields are empty: " + ", ".join(missing))
    if c["proviso_shown"] is not True:
        die("C2", "show the student the proviso first, then set proviso_shown to true")
    if c["belief_type"] not in BELIEFS:
        die("C3", f"belief_type must be one of {', '.join(BELIEFS)}")
    if c["customer_type"] not in CUSTOMERS:
        die("C4", f"customer_type must be one of {', '.join(CUSTOMERS)}")
    t = c["test_id"]
    if t not in TESTS:
        die("C5", f"test_id must be one of {', '.join(TESTS)}")
    if c["act_cost"] not in ("time", "reputation", "information", "money"):
        die("C6", "act_cost must be time, reputation, information or money")
    start, end = iso(c["start_date"], "C7"), iso(c["by_date"], "C7")
    if end <= start:
        die("C7", "by_date must be after start_date")
    x = TESTS[t]
    learning = x["learning"]
    on_table = t in FIT[(c["belief_type"], c["customer_type"])] or any(
        t in FIT.get((nb, c["customer_type"]), []) for nb in NEAR[c["belief_type"]])
    if not on_table and not c.get("off_table_reason"):
        die("C8", f"{t} is not on the fit table for {c['belief_type']} / {c['customer_type']}. "
                  "Add off_table_reason in the student's words, or pick a test from the fit list.")
    if c["customer_type"] == "b2b" and not c.get("buyer_role"):
        die("C9", "a B2B test must name buyer_role: the person with authority to buy, and how the test reaches them")
    variants = int(c.get("variants", 1) or 1)
    if variants < 1 or variants > 4:
        die("C10", "variants must be 1 to 4")
    if t in ("T6", "T7") and variants < 2:
        die("C10", f"{t} compares variants or audiences, so variants must be 2 to 4")
    out = dict(c)
    out["test_name"] = x["name"]
    out["strength"] = x["strength"]
    out["variants"] = variants
    out["learning"] = learning
    out["low_interviews"] = int(c["interviews_behind"]) < 5
    if learning and getattr(a, "preview", False):
        print("PREVIEW, NOT LOCKED. A learning test: read at least", c.get("target_replies"), "replies.")
        return
    if learning:
        missing = [k for k in LEARN_REQUIRED if c.get(k) in (None, "", [])]
        if missing:
            die("C11", "a learning test needs: " + ", ".join(missing))
        out.update(line=f"What {c['group']} say and do when we {c['act']}", numerator="themes", denominator="replies read",
                   pass_pct=0, kill_pct=0, people_needed=int(c["target_replies"]))
        out["reach_ok"] = True
        out["reach_text"] = f"Read at least {int(c['target_replies'])} replies before drawing themes."
    else:
        missing = [k for k in DEMAND_REQUIRED if c.get(k) in (None, "", [])]
        if missing:
            die("C12", "a demand test needs: " + ", ".join(missing))
        p, k = float(c["pass_pct"]), float(c["kill_pct"])
        if not (0 < p <= 100) or not (0 <= k < 100):
            die("C13", "pass_pct must be above 0 and at most 100, kill_pct 0 to under 100")
        if k >= p:
            die("C14", "kill_pct must be lower than pass_pct")
        if c.get("pass_reason_from") not in ("team", "ai_guess"):
            die("C18", "say where the numbers in pass_reason come from. Set pass_reason_from to \"team\" when the student's "
                       "file or their own words gave them, or to \"ai_guess\" when you proposed them. The plan says which, "
                       "so nobody reads an AI's guess as the team's own reasoning.")
        if c["act_cost"] == "information" and c["act"].strip().lower() in ("give an email", "leave an email", "sign up"):
            die("C15", "an email on its own costs almost nothing. Add a costly second step (a short question, a booked call) or say why email is enough")
        per = people_needed(p)
        need = per * variants
        r = c["reach"]
        if "budget" in r and "cost_per_person" in r:
            exp = int(float(r["budget"]) / float(r["cost_per_person"]))
            how = f"${float(r['budget']):g} / ${float(r['cost_per_person']):g} per person reached = about {exp} people"
        elif "people_expected" in r:
            exp = int(r["people_expected"])
            how = f"about {exp} people ({r.get('assumption', 'student estimate')})"
        else:
            die("C16", "reach needs either budget and cost_per_person, or people_expected with an assumption")
        out["people_per_variant"] = per
        out["line"] = f"At least {p:g}% of {c['group']} will {c['act']} by {c['by_date']}."
        out["people_needed"] = need
        out["reach_expected"] = exp
        out["reach_ok"] = exp >= need
        out["reach_text"] = (f"Needed: {need} people ({per} per variant x {variants}). Expected: {how}. "
                             + ("Enough." if exp >= need else
                                "NOT ENOUGH. Fix one: narrow the group, change the channel, raise the budget, or mark the test directional only."))
        if getattr(a, "preview", False):
            print("PREVIEW, NOT LOCKED.")
            print(out["line"])
            print(out["reach_text"])
            if not out["reach_ok"]:
                print("If the student accepts it, set directional_ok to true before locking; otherwise change the group, channel or budget.")
            return
        if not out["reach_ok"] and not c.get("directional_ok"):
            die("C17", out["reach_text"] + " If the student accepts a directional test, set directional_ok to true.")
        out["directional"] = not out["reach_ok"]
        if out["directional"]:
            out["reach_text"] = (f"Needed: {need} people ({per} per variant x {variants}). Expected: {how}. "
                                 "Short of that, so the student marked this test DIRECTIONAL ONLY: "
                                 "it can show a lean, not a pass or a kill.")
    out["rules"] = [RULES[i] for i in x["rules"]] + [ALWAYS_FLAG]
    out["locked_on"] = dt.date.today().isoformat()
    out["kit"] = VERSION
    out["fingerprint"] = fingerprint(out)
    os.makedirs(a.out, exist_ok=True)
    md = render_md(out)
    with open(os.path.join(a.out, "smoke-test-plan.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(a.out, "smoke-test-plan.html"), "w", encoding="utf-8") as f:
        f.write(render_html(out))
    print("LOCKED. Fingerprint " + out["fingerprint"])
    print(out["reach_text"])
    print("Wrote smoke-test-plan.md and smoke-test-plan.html in " + a.out)


def fmt_pct(v):
    return f"{v:g}%"


def card_rows(o):
    rows = [
        ("What we believe", o["belief"]),
        ("The test", o["test_name"]),
        ("The line we're testing", o["line"]),
        ("The act", f"{o['act']} (costs the person: {o['act_cost']})"),
        ("Audience", f"{o['audience']}. Channel: {o['channel']}."),
    ]
    if o.get("buyer_role"):
        rows.append(("Buyer reached", o["buyer_role"]))
    if o["learning"]:
        rows += [("What we want to learn", "; ".join(o["learn_questions"])),
                 ("Replies to read", str(o["people_needed"]))]
    else:
        bench = o.get("benchmark")
        btxt = ""
        if bench:
            btxt = (f" Benchmark beside it: {bench.get('text','')} ({bench.get('source','')}, {bench.get('date','')}"
                    + (", vendor figure" if bench.get("vendor") else "") + "). A benchmark never sets the line.")
        rows += [
            ("The number", f"{o['numerator']} / {o['denominator']}. If you run ads, ad clicks are counted separately from the page's act."),
            ("Pass", f"{fmt_pct(o['pass_pct'])} or more. Why this number"
                     + (" (an AI's guess the team accepted; their findings gave no number for it)"
                        if o.get("pass_reason_from") == "ai_guess" else "")
                     + f": {o['pass_reason']}.{btxt}"
                     + (" This test is directional only: with fewer people than it needs, it can show a lean toward"
                        " this line, not a pass." if o.get("directional") else "")),
            ("Kill", f"Under {fmt_pct(o['kill_pct'])}. Below this, drop or change the belief."),
            ("People needed", f"{o['people_needed']} ({o['people_per_variant']} per variant x {o['variants']}). Stop at this number or on {o['by_date']}, whichever comes first. No decisions from early peeks."),
            ("Reach", o["reach_text"]),
            ("Understanding check", "Before launch, at least 10 strangers (aim for 20) say what the page offers in their own words. 8 in 10 should get it right."),
        ]
    rows += [
        ("Dates and budget", f"{o['start_date']} to {o['by_date']}, ${float(o['budget_usd']):g}"),
        ("On pass", o["on_pass"]), ("On kill", o["on_kill"]), ("Too few to tell", o["on_unclear"]),
        ("How convincing", f"{strength_words(o['strength'])} {o['strength_line']}."), ("Next, stronger test", o["next_test"]),
    ]
    if o.get("off_table_reason"):
        rows.append(("Chosen off the table", o["off_table_reason"]))
    return rows


def thin_line(o):
    n = int(o["interviews_behind"])
    if n == 0:
        return "None of your interviews tested this belief yet, so the starting point is thin."
    return f"Only {n} interview{'s' if n != 1 else ''} back this belief, so treat the starting point as thin."


def render_md(o):
    lines = [f"# Smoke test plan: {o['team']}", "", "Your test on one page. Present this in class; it is locked so the result can't be reinterpreted later.", "",
             f"Locked on {o['locked_on']}. Fingerprint `{o['fingerprint']}`. Smoke Test {o['kit']}.", "",
             f"> {PROVISO}", ""]
    if o["low_interviews"]:
        lines += [f"> {thin_line(o)}", ""]
    for k, v in card_rows(o):
        lines.append(f"- **{k}:** {v}")
    lines += ["", "## Honesty checklist", ""] + [f"- [ ] {r}" for r in o["rules"]]
    lines += ["", "## Data (read by the check and results steps; do not edit)", "", "```json",
              json.dumps(o, indent=1, ensure_ascii=False), "```", "",
              "Leverage by BCE · Designed and built by Nayan Kanaparthi · Berkley Center for Entrepreneurship, NYU Stern · Smoke Test " + o["kit"], ""]
    return "\n".join(lines)


def render_html(o, extra_title=None, extra_rows=None):
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    e = html.escape
    rows = "".join(f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in (extra_rows or card_rows(o)))
    rules = "".join(f"<li>{e(r)}</li>" for r in o["rules"])
    warn = (f"<p class='warn'>{e(thin_line(o))}</p>" if o.get("low_interviews") else "")
    return (tpl.replace("{{TITLE}}", e(extra_title or f"{o['team']}: your test on one page"))
               .replace("{{META}}", e(f"Locked on {o['locked_on']} · Fingerprint {o['fingerprint']}"))
               .replace("{{PROVISO}}", e(PROVISO)).replace("{{WARN}}", warn)
               .replace("{{ROWS}}", rows).replace("{{RULES}}", rules)
               .replace("{{VERSION}}", e(o["kit"])))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def read_one(label, k, n, o):
    if n <= 0:
        die("R2", f"{label}: people reached must be above 0")
    if k < 0 or k > n:
        die("R3", f"{label}: acted must be between 0 and people reached")
    lo, hi = wilson(k, n)
    rate = k / n
    p, kl = o["pass_pct"] / 100.0, o["kill_pct"] / 100.0
    per = o["people_per_variant"]
    if n < per:
        verdict = "Too few to tell"
        lean = ("leaning pass" if rate >= p else "leaning kill" if rate < kl else "no lean either way")
        why = f"only {n} of the {per} people the card said were needed (directional reading: {lean})"
    elif rate >= p and lo > kl:
        verdict = "Pass"
        why = f"the rate reached the pass line and the bottom of the range ({lo*100:.1f}%) is above the kill line"
    elif hi < kl:
        verdict = "Kill"
        why = f"the top of the range ({hi*100:.1f}%) is below the kill line"
    else:
        verdict = "Too few to tell"
        why = "the range overlaps the lines, so this sample can't separate pass from kill"
    zero = f" With zero acts, the top of the range is about 3 / n = {300.0/n:.1f}%." if k == 0 else ""
    return (f"{label}: {k} of {n} ({rate*100:.1f}%). 95% range {lo*100:.1f}% to {hi*100:.1f}%.{zero} "
            f"Reading: {verdict}, because {why}."), verdict


def cmd_results(a):
    with open(a.plan, encoding="utf-8") as f:
        txt = f.read()
    try:
        blob = txt.split("```json", 1)[1].split("```", 1)[0]
        o = json.loads(blob)
    except Exception:
        die("R1", "this file has no plan data block. Upload the smoke-test-plan.md the plan step made")
    changed = fingerprint(o) != o.get("fingerprint")
    if o.get("learning"):
        die("R4", "this is a learning test. Read the replies for themes instead of counting a rate")
    lines = []
    if changed:
        lines.append("WARNING: the locked lines in this plan were changed after it was locked. The reading below uses the lines as they are now.")
    verdicts = []
    if a.variant:
        for v in a.variant:
            try:
                name, n, k = v.rsplit(":", 2)
                line, verdict = read_one(name, int(k), int(n), o)
            except ValueError:
                die("R5", "--variant must look like NAME:REACHED:ACTED")
            lines.append(line)
            verdicts.append((name, verdict))
    else:
        line, verdict = read_one("Strangers", a.acted, a.reached, o)
        lines.append(line)
        verdicts.append(("Strangers", verdict))
    if a.variant and len(a.variant) > 1:
        rates = []
        for v in a.variant:
            name, n, k = v.rsplit(":", 2)
            lo, hi = wilson(int(k), int(n))
            rates.append((int(k) / int(n), lo, hi, name))
        rates.sort(reverse=True)
        top, second = rates[0], rates[1]
        if top[1] > second[2]:
            lines.append(f"Variants: {top[3]} leads, and its range sits above {second[3]}'s, so the lead is real at this sample size.")
        else:
            lines.append(f"Variants: {top[3]} leads ({top[0]*100:.1f}% vs {second[0]*100:.1f}%), but their ranges overlap, so this sample can't say which design wins.")
    if a.warm_reached:
        lo, hi = wilson(a.warm_acted or 0, a.warm_reached)
        lines.append(f"Warm (friends, classmates, family): {a.warm_acted or 0} of {a.warm_reached}. "
                     "Shown as an upper bound only; it does not count toward the reading.")
    print(f"Plan: {o['team']}. Line: {o['line']}")
    print(f"Pass line {o['pass_pct']:g}%, kill line {o['kill_pct']:g}%, fingerprint {o['fingerprint']}" + (" (CHANGED)" if changed else " (matches)"))
    for l in lines:
        print(l)
    os.makedirs(a.out, exist_ok=True)
    rows = [("Belief", o["belief"]), ("The line", o["line"]), ("What happened", " ".join(lines))]
    rows.append(("Next step, from the card", "; ".join(
        f"{n}: " + {"Pass": o["on_pass"], "Kill": o["on_kill"]}.get(v, o["on_unclear"]) for n, v in verdicts)))
    md = [f"# Learning card: {o['team']}", ""] + [f"- **{k}:** {v}" for k, v in rows] + [
        "- **What it means (student's words):** ", "- **Decision (student's words):** ", ""]
    with open(os.path.join(a.out, "learning-card.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("Wrote learning-card.md in " + a.out)


# ---------------- the look (0.2.2) ----------------
# Why: in class tests, packs for different products came out looking alike, and asking for a look that
# suits a different audience changed almost nothing. So the look is written down first, from the
# student's own words and their audience's world, and checked here before anything is designed.
FONT_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts"))
LOOK_ROLES = ["background", "text", "accent", "support"]
HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
PAGE_HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
PAGE_FUNC = re.compile(r"\b(rgba?|hsla?)\(([^)]*)\)", re.I)
PAGE_COLOUR_PROP = re.compile(r"(?:^|[;{\s\"'])(?:color|background(?:-color)?|border(?:-[a-z]+)*|outline(?:-color)?|fill|stroke|"
                              r"box-shadow|text-decoration(?:-color)?|caret-color|accent-color)\s*[:=]\s*[\"']?([^;}\"'>]+)", re.I)
PAGE_FONT = re.compile(r"font-family\s*:\s*([^;}]+)", re.I)
PAGE_VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;}]+)")
PAGE_FACE = re.compile(r"@font-face\s*\{([^}]*)\}", re.I)
PAGE_URL = re.compile(r"url\(\s*[\"']?([^)\"']+?)[\"']?\s*\)", re.I)
PAGE_REMOTE_FONTS = re.compile(r"fonts\.(?:googleapis|gstatic)\.com", re.I)
# The bundled styles and the CSS weight and style each one is.
FONT_STYLES = {"Regular": (400, "normal"), "Bold": (700, "normal"), "Italic": (400, "italic"), "BoldItalic": (700, "italic")}
# The 18 basic CSS colour names (a table from the CSS standard, not a judgement).
CSS_NAMES = {"black": "#000000", "white": "#FFFFFF", "red": "#FF0000", "green": "#008000", "blue": "#0000FF",
             "yellow": "#FFFF00", "orange": "#FFA500", "purple": "#800080", "gray": "#808080", "grey": "#808080",
             "silver": "#C0C0C0", "maroon": "#800000", "navy": "#000080", "teal": "#008080", "olive": "#808000",
             "lime": "#00FF00", "aqua": "#00FFFF", "fuchsia": "#FF00FF"}


def bundled_fonts():
    try:
        return sorted({f[:-4].partition("-")[0] for f in os.listdir(FONT_DIR) if f.endswith(".ttf")})
    except OSError:
        return []


def norm_hex(c):
    c = c.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return "#" + c.upper()


def rgb01(c):
    c = norm_hex(c)
    return tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))


def hue_sat_light(c):
    r, g, b = rgb01(c)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s, l


def contrast_ratio(fg, bg):
    """WCAG contrast ratio, the same sum postkit uses."""
    def lum(c):
        vals = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb01(c)]
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def page_colours(text):
    """Every colour a page file uses, as (hex, see_through) pairs, plus anything unreadable."""
    found, unreadable = set(), []
    for m in PAGE_HEX.findall(text):
        found.add((norm_hex(m), False))
    for kind, body in PAGE_FUNC.findall(text):
        parts = [x for x in re.split(r"[\s,/]+", body.strip()) if x]
        try:
            def num(v, scale=1.0):
                return float(v[:-1]) / 100 * scale if v.endswith("%") else float(v)
            if kind.lower().startswith("rgb"):
                r, g, b = (max(0, min(255, round(num(v, 255)))) for v in parts[:3])
            else:
                hue = float(parts[0].lower().replace("deg", "")) % 360 / 360
                sat, light = num(parts[1], 1.0), num(parts[2], 1.0)
                if not parts[1].endswith("%"):
                    sat, light = sat / 100, light / 100
                r, g, b = (round(v * 255) for v in colorsys.hls_to_rgb(hue, light, sat))
            alpha = num(parts[3], 1.0) if len(parts) > 3 else 1.0
            found.add(("#%02X%02X%02X" % (r, g, b), alpha < 1))
        except (ValueError, IndexError):
            unreadable.append(f"{kind}({body})")
    for value in PAGE_COLOUR_PROP.findall(text):
        # a colour name only counts as a value of its own: not inside var(--green), url(...) or a longer word
        value = re.sub(r"\b(?:var|url)\([^)]*\)", " ", value)
        for word in re.findall(r"(?<![-\w])[a-zA-Z]+(?![-\w(])", value):
            if word.lower() in CSS_NAMES:
                found.add((CSS_NAMES[word.lower()], False))
    return found, unreadable


def page_fonts(text):
    """The first typeface of every font-family line, as written. A var(--name) is looked up in the same file."""
    variables = dict(PAGE_VAR.findall(text))
    out = []
    for value in PAGE_FONT.findall(text):
        first = value.split(",")[0].strip()
        named = re.match(r"var\(\s*(--[\w-]+)", first, re.I)
        if named:
            first = variables.get(named.group(1), "").split(",")[0].strip()
        first = first.strip("\"'").strip()
        if first and not first.lower().startswith("var(") and first.lower() not in ("inherit", "initial", "unset", "revert"):
            out.append(first)
    return out


def font_files(family):
    """The bundled files of one typeface, as (file name, CSS weight, CSS style)."""
    return [(f"{family}-{style}.ttf", weight, slant) for style, (weight, slant) in FONT_STYLES.items()
            if os.path.exists(os.path.join(FONT_DIR, f"{family}-{style}.ttf"))]


def font_face_lines(families):
    return [f'@font-face {{ font-family: "{fam}"; src: url("fonts/{name}") format("truetype"); '
            f'font-weight: {weight}; font-style: {slant}; font-display: swap; }}'
            for fam in families for name, weight, slant in font_files(fam)]


def page_typeface_gaps(text, folder, families):
    """Which of the look's typefaces a visitor would not get from this page: every one that has no @font-face
    pointing at a file that is really there, next to the page."""
    loaded = set()
    for block in PAGE_FACE.findall(text):
        fam = PAGE_FONT.search(block)
        if not fam:
            continue
        name = fam.group(1).split(",")[0].strip().strip("\"'").strip().lower().replace(" ", "")
        for url in PAGE_URL.findall(block):
            url = url.strip()
            local = url.split("?")[0].split("#")[0]
            if url.startswith("data:") or ("://" not in url and os.path.exists(os.path.join(folder, local))):
                loaded.add(name)
    return [f for f in families if f.lower() not in loaded]


def default_look(background, others):
    """The two AI-default looks that colour alone can show (frontend-design's calibration list).
    `others` is every colour but the background and the text. Returns a plain name, or None."""
    accents = others
    r, g, b = rgb01(background)
    h, s, l = hue_sat_light(background)
    chroma = max(r, g, b) - min(r, g, b)
    cream = l >= 0.85 and 20 <= h <= 65 and chroma >= 0.015
    if cream:
        for a in accents:
            ah, as_, al = hue_sat_light(a)
            if (ah <= 30 or ah >= 345) and as_ >= 0.35 and 0.25 <= al <= 0.65:
                return "a cream background with a rust, terracotta or brick-red accent"
    # near-black with a single colour, and that colour bright: greys beside it don't count as a second colour
    coloured = [a for a in accents if hue_sat_light(a)[1] >= 0.25 and 0.20 <= hue_sat_light(a)[2] <= 0.85]
    if l <= 0.12 and len(coloured) == 1:
        _, as_, al = hue_sat_light(coloured[0])
        if as_ >= 0.75 and 0.40 <= al <= 0.70:
            return "a near-black background with one bright accent"
    return None


def cmd_look(a):
    try:
        with open(a.input, encoding="utf-8") as f:
            look = json.load(f)
    except (OSError, ValueError) as e:
        die("L0", f"can't read {a.input}: {e}")
    if not isinstance(look, dict):
        die("L0", "look.json must be one JSON object.")

    words = look.get("student_words")
    if not isinstance(words, str) or not words.strip():
        die("L1", "student_words is empty. Ask the brand question first (launch-pack section 1), and write the "
                  "student's answer here in their own words, or \"pick for me\" if that is what they said.")
    drawn = look.get("drawn_from")
    things = [d.strip() for d in drawn if isinstance(d, str) and len(d.split()) >= 3] if isinstance(drawn, list) else []
    if len(things) < 2:
        die("L2", "drawn_from needs at least 2 real things from the customers' world or the product's world, each named "
                  "in 3 words or more: an object, a document or a place someone from that world would know at a glance, "
                  "taken from the findings file or the student's words. One-word qualities (\"modern\", \"clean\") "
                  "aren't things. A look that comes from nowhere in particular comes out the same for every product.")

    colours = look.get("colours")
    if not isinstance(colours, list) or not 4 <= len(colours) <= 8:
        die("L3", "colours needs 4 to 8 entries, each {\"name\", \"hex\", \"role\"}.")
    seen = {}
    for c in colours:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not c["name"].strip():
            die("L3", "every colour needs a name in plain words.")
        if not isinstance(c.get("hex"), str) or not HEX.match(c["hex"].strip()):
            die("L3", f"colour \"{c.get('name')}\" needs a hex value like #1F4D3A.")
        if c.get("role") not in LOOK_ROLES:
            die("L3", f"colour \"{c['name']}\" needs a role: background, text, accent or support.")
        key = norm_hex(c["hex"])
        if key in seen:
            die("L3", f"\"{c['name']}\" and \"{seen[key]}\" are the same colour.")
        seen[key] = c["name"]
    by_role = {r: [norm_hex(c["hex"]) for c in colours if c["role"] == r] for r in LOOK_ROLES}
    if len(by_role["background"]) != 1 or len(by_role["text"]) != 1 or not by_role["accent"]:
        die("L3", "the look needs exactly one background colour, exactly one text colour and at least one accent.")
    bg, ink = by_role["background"][0], by_role["text"][0]
    # A rust called "support" is still on the page, so every colour but the background and the text is looked at.
    common = default_look(bg, by_role["accent"] + by_role["support"])
    if common:
        asked = look.get("student_confirmed_default") is True and words.strip().lower() != "pick for me"
        if not asked:
            die("L7", f"this is {common}: the look AI tools produce for any product, and the one students' packs kept "
                      "coming out in. Choose colours from drawn_from instead. Only if the student asked for these "
                      "colours in their own words: tell them it is a very common AI look, ask if they still want it, "
                      "and on a yes set \"student_confirmed_default\": true.")
    text_ratio = contrast_ratio(ink, bg)
    if text_ratio < 4.5:
        die("L4", f"the text colour on the background has a contrast of {text_ratio:.1f}; it needs 4.5 to be readable. "
                  "Darken or lighten one of them. If the student asked for these colours, keep them as accents and "
                  "tell the student why.")
    accent_ratios = [contrast_ratio(x, bg) for x in by_role["accent"]]
    if max(accent_ratios) < 3:
        die("L4", f"no accent stands out from the background (best contrast {max(accent_ratios):.1f}, needs 3), "
                  "so a button in it would be hard to see.")

    kinds = look.get("type")
    families = bundled_fonts()
    if not isinstance(kinds, list) or not 1 <= len(kinds) <= 2:
        die("L5", "type needs 1 or 2 typefaces, each {\"family\", \"role\"}.")
    names = []
    for k in kinds:
        fam = k.get("family") if isinstance(k, dict) else None
        if families and fam not in families:
            die("L5", f"\"{fam}\" isn't one of the bundled typefaces. Pick from: {', '.join(families)}.")
        if not isinstance(k.get("role"), str) or not k["role"].strip():
            die("L5", f"say what \"{fam}\" is used for (for example \"headlines\").")
        names.append(fam)
    if len(set(names)) != len(names):
        die("L5", "the two typefaces are the same one. Use one, or pick two that are clearly different.")
    if not isinstance(look.get("memorable"), str) or not look["memorable"].strip():
        die("L6", "memorable is empty. Name the one memorable element, taken from the product's own world.")

    pages = a.page or []
    off = []
    allowed = set(seen)
    look_fonts = [n.lower() for n in names]
    for path in pages:
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            die("L0", f"can't read {path}: {e}")
        colours_used, unreadable = page_colours(text)
        # a see-through colour (an alpha under 1) is fine when it is a tint of one of the look's colours
        stray = sorted({c for c, _ in colours_used if c not in allowed}) + unreadable
        fonts = sorted({f for f in page_fonts(text)
                        if not any(f.lower().replace(" ", "").replace("-", "").startswith(n) for n in look_fonts)})
        if stray:
            off.append(f"{os.path.basename(path)}: colours {', '.join(stray)}")
        if fonts:
            off.append(f"{os.path.basename(path)}: typefaces {', '.join(fonts)} (put the look's typeface first in each font-family)")
    if off:
        die("L8", "these are used but aren't in the chosen look: " + "; ".join(off) +
                  ". Use the look's colours and typefaces, or add the colour to look.json (8 at most) and run this again.")
    # A page that names a typeface without carrying its file shows visitors a fallback, and nothing warns anyone.
    for path in pages:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if not re.search(r"<html|<body|font-family", text, re.I):
            continue
        base = os.path.basename(path)
        folder = os.path.dirname(os.path.abspath(path))
        if PAGE_REMOTE_FONTS.search(text):
            die("L9", f"{base} loads typefaces from Google Fonts by name. A wrong name or weight there drops the typeface "
                      "with no error, so a visitor sees a fallback. Remove that link. The files in fonts/ are the same faces: "
                      f"python3 scripts/smoke.py fonts --in {a.input} --to <the page's folder>")
        gaps = page_typeface_gaps(text, folder, names)
        if gaps:
            die("L9", f"{base} doesn't carry {' or '.join(gaps)}, so a visitor would see a fallback typeface. Run: "
                      f"python3 scripts/smoke.py fonts --in {a.input} --to <the page's folder>, then paste the lines "
                      "it prints at the top of the page's <style>.")

    if common:
        print(f"NOTE: this is {common}, a very common AI look. Kept because the student asked for it and confirmed.")
    print(f"LOOK OK. {look.get('name') or 'The chosen look'}: {len(colours)} colours, {' and '.join(names)}.")
    print("Drawn from: " + "; ".join(things) + ".")
    print(f"Text on background contrast {text_ratio:.1f} (needs 4.5). Best accent on background {max(accent_ratios):.1f} (needs 3).")
    if pages:
        print(f"{len(pages)} page file(s) use only the look's colours and typefaces, and carry the typeface files.")


def cmd_fonts(a):
    """Put the look's typeface files next to the page, so the page shows the same faces as the posts."""
    try:
        with open(a.input, encoding="utf-8") as f:
            look = json.load(f)
    except (OSError, ValueError) as e:
        die("L0", f"can't read {a.input}: {e}")
    kinds = look.get("type") if isinstance(look, dict) else None
    names = [k.get("family") for k in kinds if isinstance(k, dict)] if isinstance(kinds, list) else []
    if not names or any(n not in bundled_fonts() for n in names):
        die("L5", f"the look's typefaces aren't set yet. Run first: python3 scripts/smoke.py look --in {a.input}")
    dest = os.path.join(a.to, "fonts")
    os.makedirs(dest, exist_ok=True)
    copied = 0
    for fam in names:
        for name, _, _ in font_files(fam):
            shutil.copyfile(os.path.join(FONT_DIR, name), os.path.join(dest, name))
            copied += 1
        licence = os.path.join(FONT_DIR, fam + "-OFL.txt")
        if os.path.exists(licence):
            shutil.copyfile(licence, os.path.join(dest, fam + "-OFL.txt"))
    print(f"FONTS OK. {copied} typeface files are in {dest}, with their licence files. Publish that folder with the page.")
    print("Paste these lines at the top of the page's <style>:")
    for line in font_face_lines(names):
        print(line)
    print("Then name them exactly like this, first in each font-family, with a system fallback after:")
    for fam in names:
        weights = ", ".join(f"{w}{' italic' if sl == 'italic' else ''}" for _, w, sl in font_files(fam))
        print(f'  font-family: "{fam}", <fallback>;   weights in the folder: {weights}')


def main():
    ap = argparse.ArgumentParser(description="Smoke Test helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--belief", required=True)
    f.add_argument("--customer", required=True)
    f.add_argument("--weeks", type=float, default=3)
    f.add_argument("--budget", type=float, default=50)
    c = sub.add_parser("card")
    c.add_argument("--in", dest="input", required=True)
    c.add_argument("--out")
    c.add_argument("--preview", action="store_true", help="compute people needed and reach without locking or writing files")
    r = sub.add_parser("results")
    r.add_argument("--plan", required=True)
    r.add_argument("--reached", type=int, default=0)
    r.add_argument("--acted", type=int, default=0)
    r.add_argument("--warm-reached", type=int, default=0)
    r.add_argument("--warm-acted", type=int, default=0)
    r.add_argument("--variant", action="append")
    r.add_argument("--out", required=True)
    lk = sub.add_parser("look")
    lk.add_argument("--in", dest="input", required=True)
    lk.add_argument("--page", action="append", help="an HTML or CSS file that must use only the look's colours")
    fo = sub.add_parser("fonts")
    fo.add_argument("--in", dest="input", required=True)
    fo.add_argument("--to", required=True, help="the page's folder; the files go in its fonts/ folder")
    a = ap.parse_args()
    {"fit": cmd_fit, "card": cmd_card, "results": cmd_results, "look": cmd_look, "fonts": cmd_fonts}[a.cmd](a)


if __name__ == "__main__":
    main()
