# Installing nstack

Every way to install, with what I've checked and what I haven't.

## Claude Code, as a plugin

nstack is a Claude Code plugin marketplace: the repo has a `.claude-plugin/marketplace.json` that lists four plugins.

| Install id | What you get |
|---|---|
| `nstack@nstack` | Every standalone skill in `skills/`, as one plugin |
| `discover@nstack` | The discover plugin |
| `smoke-test@nstack` | The smoke-test plugin |

In a session:

```text
/plugin marketplace add NayanKanaparthi/nstack
/plugin install nstack@nstack
```

`/plugin install` in a session opens the plugin's details first, where you pick a scope: you, this repo for everyone, or this repo for you only.

From your shell:

```bash
claude plugin marketplace add NayanKanaparthi/nstack
claude plugin install nstack@nstack
```

Plugin skills show up with the plugin's name in front, for example `/nstack:evidence-check` or `/discover:discover`.

To update: `claude plugin update nstack@nstack`, or in `/plugin` go to Marketplaces, pick nstack, and turn on auto-update. Marketplaces that aren't Anthropic's start with auto-update off.

To remove everything: `claude plugin marketplace remove nstack`. That also uninstalls the plugins you installed from it.

Checked against Claude Code's plugin docs (marketplace reference, create a marketplace, manifest reference, install and manage plugins). One thing I couldn't run here is `claude plugin validate .`, so if an install fails, run that in the repo and it will say which field is wrong.

## The setup script

```bash
git clone https://github.com/NayanKanaparthi/nstack.git ~/nstack
cd ~/nstack
./setup
```

| Command | What it does |
|---|---|
| `./setup` | Links each folder in `skills/` into `~/.claude/skills/` |
| `./setup --project <path>` | Links them into `<path>/.claude/skills/` instead |
| `./setup --copy` | Copies the folders instead of linking. Use this for a project you commit |
| `./setup --uninstall` | Removes only the links and copies it made |

It never overwrites a folder it didn't install. It prints what it skipped and why. Links point at your clone, so keep the clone where it is and run `git pull` there to update. Copies carry a small `.nstack-installed` file so the script knows which folders are its own.

Tested on Linux with bash 5.1 against a temporary home and project folder: install, rerun, a clashing folder, copy, update, uninstall.

## Team mode

**Copy the skills into the repo and commit them.** This works for everyone with no install step:

```bash
~/nstack/setup --project /path/to/repo --copy
cd /path/to/repo
git add .claude/skills
git commit -m "Add nstack skills"
```

**Or enable the plugin at project scope:**

```bash
claude plugin marketplace add NayanKanaparthi/nstack
claude plugin install nstack@nstack --scope project
git add .claude/settings.json
git commit -m "Enable nstack for this repo"
```

Per Claude Code's docs, committing the project setting turns the plugin on for collaborators but doesn't download it. Each collaborator runs `claude plugin install nstack@nstack --scope project` once. There is also a public report that no install prompt appears for collaborators ([anthropics/claude-code#32606](https://github.com/anthropics/claude-code/issues/32606)); I couldn't confirm whether it's been fixed.

## Claude.ai

Zip one skill folder from `skills/` and upload it under Settings, Capabilities, Skills. The plugins don't install this way. Not checked against the current Claude.ai settings page.

## Other agents

Skills here are Agent Skills folders, so the [skills CLI](https://github.com/vercel-labs/skills) can install them into Codex, Cursor, OpenCode and other agents:

```bash
npx skills add NayanKanaparthi/nstack --skill evidence-check -a codex
```

Its README says it supports OpenCode, Claude Code, Codex and Cursor plus many more, installs into the current project by default, and takes `-g` to install globally. I haven't run it against this repo, and I don't know yet whether it finds skills in `skills/` or also picks up the ones inside `plugins/`.
