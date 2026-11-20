# Memory gaps: <fill: name of the agent>

> Written by Claude with the agent-memory-design skill, from the code as it was on <fill: date> at <fill: commit or folder>. Nothing in the project was changed. `MEMORY-DESIGN.md` beside this file is the design as built.

## 1. The checklist
| # | Check | Result | Evidence |
|---|---|---|---|
| <fill: line number> | <fill: the check in a few words> | <fill: yes, no, unknown or n/a> | <fill: file and line, or the test and what it showed. For n/a, the checker's reason and how you confirmed it> |

## 2. Gaps, worst first
| # | Gap | Line | Applies because | If it bites once | Where | Fix |
|---|---|---|---|---|---|---|
| <fill: 1, 2, 3, the gaps the code has today first, then those marked works today, untested> | <fill: what happens, in one sentence> | <fill: checklist line or lines> | <fill: the property of the agent that makes the line apply> | <fill: cannot be undone, costs money, leaks data, sends something out, corrupts memory, misses a promised action or harmless, then what that means here. For a rule the code enforces that no test would catch, start with works today, untested:> | <fill: file and line, or what was searched for and where> | <fill: the smallest change, and the test that would show it closed> |

## 3. Not known
- <fill: each thing marked unknown, and what would settle it. Or: nothing>

<fill: one line: how many checklist lines are yes, no, unknown and n/a, and how many gaps>

## 4. The checker's output
<fill: the command as run from the project folder, its RESULT line, and every list it printed>
