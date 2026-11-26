# How the factory skill was checked

This folder holds the record CONTRIBUTING.md asks for.

- `CHECKLIST.md`: the yes or no lines written before building.
- `reviews/round-N.md`: each independent review. The reviewer got only the skill folder, CONTRIBUTING.md, the checklist, the earlier rounds and the root README and CHANGELOG changes. It never saw how the skill was built.
- Round 1 and round 3 were done by GPT 5.6. Round 2 was done by a fresh Claude session because GPT had reached its usage limit; it had the same isolated folder.

## Privacy scan

The maintainer's own scanner, which is not part of the skill, was run on every added line of this branch against main:

```
privacy_scan.py --patterns <private list> --git-changed origin/main
notes/factory/reviews/round-1.md:88: secret: [12 chars]
privacy scan: 1 hits in 1 files (68 files scanned, 16241 added lines scanned)
exit 1
```
