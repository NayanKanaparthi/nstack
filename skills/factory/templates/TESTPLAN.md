# TESTPLAN: <build id>

Layers: L0 static, L1 unit, L2 contract (a command's output, errors, exit code, files written), L3 end to end, L4 agent evals (milestones only).

Conventions for the test writer:
- Every test runs with a temporary home and a temporary Factory home folder. No test touches the real ones.
- No test waits more than 1 second of real time. Every limit and wait is a setting, and tests set them to fractions of a second.
- Fake programs stand in for external tools. No test calls a real model or the network.
- A new test must fail before the feature exists because the behavior is missing (a failing assertion or a missing command), not because of a syntax error or a missing fixture.
- The fast suite runs in under 60 seconds.

## Cases

| Id | Layer | Input | Expected | Proves |
|---|---|---|---|---|
| T-AREA-01 | L2 | The exact command line and any files. | Exact stdout, stderr, exit code, files written. | AC1 |
| T-AREA-02 | L1 | A function call with a bad value. | The error and message. | AC2 |

## Fixtures

Name each fixture, say that it is synthetic, and give the numbers any test will compute by hand.

## Test-acceptance gate

- The existing suite is still green.
- Every new test fails for the expected reason.
- Every criterion maps to tests that encode it.
- Then the files are locked in `TESTLOCK` with commit and content hashes.
