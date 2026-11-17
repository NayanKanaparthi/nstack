# AGENTS.md

For coding agents working in this repo.

- `skills/<name>/SKILL.md` are standalone skills in the Agent Skills format. Folder name equals the skill's `name`.
- `plugins/<name>/` are Claude Code plugins. Their skills live in `plugins/<name>/skills/`.
- `.claude-plugin/marketplace.json` lists what Claude Code can install from this repo. Keep entry names equal to the plugin names.
- `setup` installs `skills/` as plain folders. Keep it POSIX-friendly bash and shellcheck clean.
- Don't touch `third-party/` or `_review/`. Don't list anything in `wip/` as available.
- Plain words, no em dashes, no buzzwords. Sources for any claim about the world.
- A skill isn't done until an independent reviewer passes it against its checklist. See CONTRIBUTING.md.
