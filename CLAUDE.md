# Working in nstack

Rules for Claude when it works inside this repo.

- Never edit anything in `third-party/`. Those are other people's skills, kept locally and never pushed.
- `_review/` holds skills whose authorship isn't settled. Don't move them into `skills/` without asking.
- Work in `wip/` isn't installable. Don't add it to the README's skill tables, the marketplace files or `setup` until it passes its review.
- A skill moves from `wip/` to `skills/` only after an independent review against its checklist passes. Whoever built it can't sign it off.
- Every skill in `skills/` has a `README.md` with what it does, how to install it, how a run goes, known limits and its version. Check this before calling a skill finished.
- The folder name, the `name` in `SKILL.md`, and any marketplace entry name must match.
- Check claims before stating them. A fact about the world gets a source you actually opened, or it doesn't go in.
- Write in plain words. No em dashes. No buzzwords.
- Don't commit or push. Nayan does that.
