# nstack

Nayan's Claude setup: the skills and plugins I use to plan, build, check and ship my work. New ones land as I build them.

Claude skills and plugins I build and use. Each one does one job, and the ones that make claims check them before showing you anything.

Built by [Nayan Kanaparthi](https://nayankanaparthi.dev). MIT licensed.

## Quick start

In a Claude Code session:

```text
/plugin marketplace add NayanKanaparthi/nstack
/plugin install nstack@nstack
```

That gives you every standalone skill below. Then just work. Tell Claude about a product idea and the assumptions behind it and evidence-check kicks in, or ask it to help price an AI feature and ai-pricing-strategy does. You can also call a skill by name, for example `/nstack:evidence-check`.

The plugins install the same way: `/plugin install discover@nstack` and `smoke-test@nstack`. To get only agent-memory-design, it has its own entry: `/plugin install agent-memory-design@nstack`.

## Install

### Step 1: on your machine

You have two ways. Pick one.

**As a Claude Code plugin (recommended).** Run the two commands from Quick start. From your shell instead of a session:

```bash
claude plugin marketplace add NayanKanaparthi/nstack
claude plugin install nstack@nstack
```

Updates: `claude plugin update nstack@nstack`, or turn on auto-update for the nstack marketplace in `/plugin` under Marketplaces. Third-party marketplaces start with auto-update off.

**With the setup script.** If you'd rather have the skills as plain folders:

```bash
git clone https://github.com/NayanKanaparthi/nstack.git ~/nstack
cd ~/nstack
./setup
```

`./setup` links every folder in `skills/` into `~/.claude/skills/`. It never overwrites a folder it didn't put there. `git pull` in `~/nstack` updates everything, and `./setup --uninstall` removes only what it added. The plugins in `plugins/` aren't installed this way; use the plugin route for those.

**On Claude.ai.** Zip one skill folder from `skills/`, the folder itself, so the zip opens to `<skill-name>/SKILL.md`. Then go to Customize, Skills, press +, pick Create skill, then Upload a skill. Code execution and file creation has to be on.

### Step 2: team mode

Two ways to give a whole repo the same skills.

**Commit the skills into the project.** Everyone gets them on their next pull, nothing to install:

```bash
~/nstack/setup --project /path/to/your/repo --copy
cd /path/to/your/repo && git add .claude/skills && git commit -m "Add nstack skills"
```

Run the same command again later to update the copies.

**Enable the plugin for the project.** From inside your repo:

```bash
claude plugin marketplace add NayanKanaparthi/nstack
claude plugin install nstack@nstack --scope project
git add .claude/settings.json && git commit -m "Enable nstack for this repo"
```

Committing that file turns the plugin on for everyone in the repo but doesn't download it to their machines. Each teammate runs `claude plugin install nstack@nstack --scope project` once. Don't count on Claude Code prompting them to install it: there's a public report that the prompt never shows up ([anthropics/claude-code#32606](https://github.com/anthropics/claude-code/issues/32606)).

### Other AI agents

Every skill here is a folder with a `SKILL.md`, the open Agent Skills format. The [skills CLI](https://github.com/vercel-labs/skills) installs skills from a GitHub repo into Codex, Cursor, OpenCode and many other agents:

```bash
npx skills add NayanKanaparthi/nstack --skill evidence-check -a codex
```

I haven't tested that command against nstack yet, so treat it as a starting point. The plugins in `plugins/` are Claude Code plugins and only run there. `AGENTS.md` tells coding agents how this repo is laid out.

## What's in it

### Skills

| Skill | What it does |
|---|---|
| [agent-memory-design](skills/agent-memory-design) | When you plan or build an agent with Claude, works out the agent's memory system (what gets saved, how it comes back, when it expires, what wakes the agent later, and how nothing happens twice), writes the design into your project and builds it with tests. |
| [ai-pricing-strategy](skills/ai-pricing-strategy) | Runs a staged pricing session for an AI product or feature, grounded in value created and willingness to pay. Ends in a defensible price range and model, the risks, and what to validate first. |
| [evidence-check](skills/evidence-check) | Checks the assumptions behind a product or startup idea against evidence on the web, for and against, without judging the idea. Built for entrepreneurship classes at the Berkley Center. |
| [venture-assessor](skills/venture-assessor) | Takes a startup idea to a founder-grade decision memo: evidence-first problem framing, competitor mapping, beachhead selection, beachhead TAM, validation design and go-to-market options. |

### Plugins

Made for the AI Build Lab for Founders at the Berkley Center for Entrepreneurship, NYU Stern (Leverage by BCE).

| Plugin | What it does |
|---|---|
| [discover](plugins/discover) | Takes a founder from a vague idea, or only an area of interest, to a checked evidence report and a plan to interview real people. Never judges the idea. |
| [smoke-test](plugins/smoke-test) | Turns interview findings into one smoke test and a launch pack (page, posts, print pieces, tracking sheet), then reads results against lines set in advance. |

## How each one gets checked

I build these the way I want agents to build things:

1. Write the checklist first: what has to be true when the skill is done.
2. Build against it.
3. Hand it to a reviewer agent that never saw the build. It checks every line and tries to break things.
4. Fix what failed, and review again.

Nothing gets called done by whoever built it.

## Notes

`notes/` holds the research and the review record behind each skill: what I read, what I decided and why, and every review round with what it found. If you want to know why a skill works the way it does, start there.

## Layout

```
skills/          standalone skills, one folder each
plugins/         multi-skill Claude Code plugins
notes/           research and review records behind each skill
docs/            install details and how to write a skill
wip/             work in progress, not installable
.claude-plugin/  makes this repo a Claude Code plugin marketplace
setup            installs the skills as plain folders
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: a skill gets in when it passes an independent review against a checklist written before it was built.

## License

[MIT](LICENSE).
