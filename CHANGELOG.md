# Changelog

Every release of nstack gets an entry here. Each skill and plugin also keeps its own version in its own files.

## Unreleased

### Added
- Repo setup: README, MIT license, `setup` script, Claude Code marketplace files (`.claude-plugin/`), CLAUDE.md, AGENTS.md, CONTRIBUTING.md, docs/, notes/, issue templates and a check workflow.
- Skills: agent-memory-design 0.2.0 (0.1.0 was the first version), ai-pricing-strategy, evidence-check, venture-assessor.
- Plugins: discover 2.3.0, smoke-test 0.2.2.
- Marketplace entry `agent-memory-design`, to install that one skill on its own.

### Changed
- agent-memory-design 0.2.0: every number in a design says where it comes from (policy, requirement, data or default). Facts with no end date are kept true by evidence. A saved task keeps the premise it was scheduled on. A production part covers speed, volume, failures and measurements. The extraction prompt gets a test set and an offline optimizer script (GEPA). A new path reviews the memory of an agent that already exists. Line 25, where numbers come from, applies to every design; the checker enforces lines 26 to 39 only in a design that says the property applies. Designs written with 0.1 still pass once their numbers carry a source.

