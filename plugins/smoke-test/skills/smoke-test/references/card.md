# Drafting the test card

Draft each field from the student's findings and choices. Propose numbers, explain each in one line, and let the student change them.

## The fields, in plain words

- **The line:** "At least X% of [group] will [act] by [date]." Narrow the group to a slice they can reach now ("renters in Brooklyn who make coffee at home daily", not "coffee lovers").
- **The act:** something that costs the person. An add-to-cart click on its own is a cheap action, so pair it with an email or a short question and call the cost `information`. Name the cost: `time` (a booked call, a survey), `reputation` (sharing, an intro), `information` (an email plus a phone number or a short question), `money` (a deposit). An email on its own costs almost nothing, so pair it with a second step.
- **Audience and channel:** who, and exactly where they'll see it. Strangers count. Friends, classmates and family are counted separately as an upper bound.
- **The number:** numerator / denominator, exact. Example: "add-to-cart clicks / people who reached the product page". Ad clicks are a separate number.
- **Pass line (X%):** the reason comes from their business, not a benchmark. Two ways to reason it:
  - customers needed / people you could reach (if you need 50 buyers from 1,000 reachable people, X is 5%);
  - the rate at which the channel's cost per act still pays back (at $0.70 a click and $15 profit a sale, you need at least 1 sale per 21 clicks, about 5%).
  The numbers in the reason are the team's when their file or their words gave them: set `"pass_reason_from": "team"`. When neither did, propose numbers, label the reason "AI's guess" on the card you show, and set `"pass_reason_from": "ai_guess"`. Never present your guess as the team's reasoning.
  Then show a benchmark beside it, with source and date, for the same channel and act only (below). It sanity-checks the line; it never sets it. If no row fits the channel and the act, leave `benchmark` out and say there isn't one. If the pass line is more than twice the benchmark's top, say so to the student in one line, before they lock.
- **Kill line (K%):** lower than X. Below it they drop or change the belief. A common choice is about half of X.
- **People needed:** the script works it out (about 1,000 / X, so about 10 people are expected to act). Tests with variants (T6, T7) need that many per variant.
- **Reach:** how many people the channel and budget will deliver by the date, counted at the denominator. If the number is counted on the page, reach is the people expected to land on the page, not everyone who sees the post or the flyer: say the step in the assumption ("about 400 will see the flyer, and we expect 1 in 5 to scan it"). Give the script either `budget` and `cost_per_person`, or `people_expected` with the assumption in words (for example "5 posts x about 300 views each, from past posts").
- **On pass / on kill / too few to tell:** what they'll do in each case, one line each.
- **How strong this is:** one honest line (for example "a click at a shown price is intent, not a purchase").
- **Next, stronger test:** what they'd run after a pass (often a refundable deposit).

## Benchmarks (sanity checks only; vary a lot by source)

| Channel and act | Typical | Source, date, vendor? |
|---|---|---|
| Landing page, any conversion, all traffic | median 6.6% | Unbounce 2024 report, 41k pages, vendor |
| Email signup from cold paid social | 2 to 5% | Kromatic, undated rule of thumb, consultancy (vendor: false) |
| Simulated buy click | 1 to 3% | Kromatic, undated rule of thumb, consultancy |
| Facebook traffic ads, click-through / cost per click | 1.71% / $0.70 | WordStream, US data Apr 2024 to Jun 2025, vendor |
| Instagram link click-through / cost per click | 1.19% / $0.69 | Gupta Media, Jun 2025, agency |
| TikTok ads, minimum spend | $20 a day per ad group | TikTok Ads help, Jul 2026 |
| Cold B2B email, replies | 0.45% to 3.43% | Belkins 2025 (7.5M emails) vs Instantly 2026, vendors, different bases |
| Demo request from a landing page | 1 to 5% | Leadpages 2026, vendor |
| Waitlist to paid | 5 to 25% | Lenny's Newsletter 2022, informal poll |

## card.json

Write it with every field below. Use the student's words for text fields.

```json
{
 "team": "Lease Buddy",
 "belief": "First-time renters want a lease-review checklist app enough to book a 15-minute walkthrough",
 "belief_type": "want",
 "customer_type": "consumer_digital",
 "test_id": "T4",
 "variants": 1,
 "group": "graduate students signing their first New York lease this spring",
 "act": "leave an email and book a 15-minute walkthrough",
 "act_cost": "time",
 "channel": "two student housing groups (rules read first) and a $40 Instagram boost to people near campus",
 "audience": "Strangers reached through the groups and the boost; friends and classmates counted separately",
 "numerator": "booked walkthroughs",
 "denominator": "people who reached the page",
 "pass_pct": 8,
 "pass_reason": "we need 20 early users from about 250 people we can reach before January",
 "pass_reason_from": "team",
 "kill_pct": 3,
 "benchmark": {"text": "email signup from cold paid social 2 to 5%", "source": "Kromatic", "date": "undated", "vendor": false},
 "reach": {"people_expected": 180, "assumption": "about 120 from the two groups plus about 60 from the $40 boost at $0.69 a click"},
 "start_date": "2026-11-16",
 "by_date": "2026-12-04",
 "budget_usd": 40,
 "on_pass": "Run a $5 refundable deposit test for the full checklist",
 "on_kill": "Go back to interviews on what first-time renters actually worry about",
 "on_unclear": "Run one more week in a third housing group",
 "strength_line": "A booked call costs time, which is stronger than an email but still not a purchase",
 "next_test": "A $5 refundable deposit",
 "interviews_behind": 6,
 "proviso_shown": true
}
```

- Learning tests (T1, T2) leave out numerator, denominator, pass_pct, pass_reason, pass_reason_from, kill_pct and reach, and add `"learn_questions": [...]` and `"target_replies": 20`.
- B2B tests add `"buyer_role"`: who can buy and how the test reaches them.
- A test not on the fit list needs `"off_table_reason"` in the student's words.
- If the preview says reach is NOT ENOUGH, ask the student before the lock stop whether to change the group, channel or budget, or to run a directional test (SKILL.md Step 4). If they accept a directional test, add `"directional_ok": true`.
