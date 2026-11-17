# Writing a skill for nstack

1. Make a folder in `wip/<skill-name>/`.
2. Write the checklist before anything else: what has to be true when the skill is done, one yes-or-no line each.
3. Write `SKILL.md` with a `name` matching the folder and a `description` under 1024 characters that says when Claude should use it. Keep the body short and put long material in files the skill reads only when it needs them.
4. Add a `README.md`: what it does, how to install it, how a run goes, known limits, version.
5. Get it reviewed by an agent that never saw the build, against the checklist. Fix, and review again until every line passes.
6. Move the skill to `skills/<skill-name>/`, its notes and review rounds to `notes/<skill-name>/`, and add it to the README table and CHANGELOG.

Plain words, no em dashes, no buzzwords. A number you picked is marked as picked, and a claim from a source names the source.
