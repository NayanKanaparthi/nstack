# How the factory skill was checked

This folder holds the record CONTRIBUTING.md asks for.

- `CHECKLIST.md`: the yes or no lines written before building.
- `reviews/round-N.md`: each independent review. The reviewer got only the skill folder, CONTRIBUTING.md, the checklist, the earlier rounds and the root README and CHANGELOG changes. It never saw how the skill was built.
- Round 1 was done by GPT 5.6. Rounds 2 and later were done by fresh Claude sessions, because GPT had reached its usage limit; each had the same isolated folder and never saw the build.

## Privacy scan

The maintainer's own scanner, which is not part of the skill, was run on every added line of this branch against main (this record itself is the only line added after the run):

```
privacy_scan.py --patterns <private list> --git-changed origin/main
privacy scan: 0 hits in 0 files (70 files scanned, 16352 added lines scanned)
exit 0
```
