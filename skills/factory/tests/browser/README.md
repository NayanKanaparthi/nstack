# Dashboard browser acceptance runner

This runner is orchestrator-only. It is not part of the standard Python test command. It opens headless Chromium only, creates disposable Factory homes under the system temporary folder, starts dashboard servers with port `0`, and stops each server by the PID it started.

Install the pinned browser tools:

```sh
npm install --prefix /tmp/factory-playwright playwright@1.49.1 --no-save --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH=/tmp/factory-playwright/browsers NODE_PATH=/tmp/factory-playwright/node_modules /tmp/factory-playwright/node_modules/.bin/playwright install chromium
```

Run from the repository root with an evidence folder chosen by the orchestrator:

```sh
FACTORY_UI_SCREENSHOT_DIR=/tmp/factory-dashboard-evidence \
PLAYWRIGHT_BROWSERS_PATH=/tmp/factory-playwright/browsers \
NODE_PATH=/tmp/factory-playwright/node_modules \
node skills/factory/tests/browser/dashboard-ui.js
```

The runner checks Playwright is exactly `1.49.1` before launching Chromium. It warms the dashboard help command without binding a socket, generates its fixture home, blocks outside requests, records CSP and page errors, writes the screenshots named in the test plan, and writes `dashboard-text.json` for Python case T-DB-56.
