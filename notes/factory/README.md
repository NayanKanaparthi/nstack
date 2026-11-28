# How the factory skill was checked

This folder holds the record CONTRIBUTING.md asks for.

- `CHECKLIST.md`: the yes or no lines written before building.
- `reviews/round-N.md`: each independent review. The reviewer got only the skill folder, CONTRIBUTING.md, the checklist, the earlier rounds and the root README and CHANGELOG changes. It never saw how the skill was built.
- Round 1 was done by GPT 5.6. Rounds 2 and later were done by fresh Claude sessions, because GPT had reached its usage limit; each had the same isolated folder and never saw the build.

## Privacy scan

The maintainer's own scanner, which is not part of the skill, was run on every added line of this branch against main (this record itself is the only line added after the run):

```
privacy_scan.py --patterns <private list> --git-changed origin/main
privacy scan: 0 hits in 0 files (72 files scanned, 16546 added lines scanned)
exit 0
```

### Privacy scan, dashboard update

Run again on every added line of the dashboard update against main (this record is the only line added after the run). The credit line with the author's name and the link to this repo are there by the author's choice and are allowed by name in the private list. A first run flagged random bytes inside one screenshot that happened to look like an email address; that image was saved again and the run repeated (the same happened once more after the small fixes):

```
privacy_scan.py --patterns <private list> --git-changed origin/main
privacy scan: 0 hits in 0 files (37 files scanned, 13170 added lines scanned)
exit 0
```
