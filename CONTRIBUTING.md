# Contributing

This is my personal setup, so I'm picky about what gets in. Issues and ideas are welcome. If you send a skill, this is how it gets in.

## How a skill gets in

1. **Write the checklist first.** Before any building, write down what has to be true when the skill is done. Every line is yes or no, and someone who never saw the work can check it.
2. **Build against the checklist.**
3. **Get it reviewed by an agent that never saw the build.** It gets the skill folder and the checklist, nothing else. It checks every line, runs the skill on cases you didn't try, and tries to break it.
4. **Fix what failed, then review again.** Repeat until every line passes. The builder never gets to call it done.

Put the checklist and the review rounds in `notes/<skill-name>/` so anyone can see how it was checked.

## What every skill folder has

- One folder per skill under `skills/`, named the same as the `name` in its `SKILL.md`.
- A `SKILL.md` with a `name` and a `description` under 1024 characters that says when to use it.
- A `README.md` with: what it does, how to install it, how a run goes, known limits, and its version.
- Anything else it needs (step files, references, scripts, assets) inside its own folder.

## Writing rules

- Plain words. If a term needs explaining, explain it with an example the first time it shows up.
- No em dashes, no buzzwords.
- A number you picked is marked as one you picked. A claim from a source names the source.
- If a skill makes claims about the world, it shows where each one came from.

## Work in progress

Unfinished work goes in `wip/`. Nothing in `wip/` is installable or listed as available.
