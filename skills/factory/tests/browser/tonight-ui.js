#!/usr/bin/env node
/* Headless contracts T-TN-30 through T-TN-33. */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

const REQUIRED_VERSION = '1.49.1';
let playwright;
let installed;
try {
  playwright = require('playwright');
  installed = require('playwright/package.json').version;
} catch (error) {
  process.stderr.write('tonight-ui: install playwright@1.49.1 under /tmp/factory-playwright\n');
  process.exit(2);
}

if (installed !== REQUIRED_VERSION) {
  process.stderr.write(`tonight-ui: expected playwright@${REQUIRED_VERSION}, found ${installed}\n`);
  process.exit(2);
}

const ROOT = path.resolve(__dirname, '..', '..', '..', '..');
const FACTORY = path.join(ROOT, 'skills', 'factory', 'scripts', 'factory.py');
const FIXTURE_MAKER = path.join(ROOT, 'skills', 'factory', 'tests', 'fixtures',
  'tonight', 'make_tonight_fixtures.py');
const SCREENSHOTS = process.env.FACTORY_UI_SCREENSHOT_DIR;
const HOSTILE_TAGS = [
  // API-only next-step and deadline values are covered by T-TN-21, not rendered here.
  'f-title', 'f-piece', 'f-purpose', 'f-stage', 'f-actor', 'f-model', 'f-call',
  'f-node-label', 'f-plain', 'f-notes', 'f-question', 'f-answer',
];

function check(condition, message) {
  if (!condition) throw new Error(message);
}

function equal(actual, expected, message) {
  const same = (actual && typeof actual === 'object') || (expected && typeof expected === 'object')
    ? JSON.stringify(actual) === JSON.stringify(expected) : actual === expected;
  check(same, `${message || 'values differ'}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}

function contains(text, wanted, message) {
  check(String(text).includes(wanted), message || `expected text to contain ${JSON.stringify(wanted)}`);
}

function makeHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'factory-tonight-ui-'));
  const result = spawnSync('/usr/bin/python3', ['-I', FIXTURE_MAKER, home], {
    cwd: ROOT, encoding: 'utf8', timeout: 900,
    env: Object.assign({}, process.env, { PYTHONPYCACHEPREFIX: '/tmp/factory-test-pycache' }),
  });
  check(result.status === 0, `fixture maker failed: ${result.stdout}\n${result.stderr}`);
  const fake = path.join(home, 'fake-osascript');
  fs.writeFileSync(fake, '#!/bin/sh\nexit 99\n');
  fs.chmodSync(fake, 0o700);
  return { home, fake };
}

function warmDashboard(env) {
  const result = spawnSync('/usr/bin/python3', [FACTORY, 'dashboard', '--help'], {
    cwd: ROOT, env, encoding: 'utf8', timeout: 900,
  });
  check(result.status === 0, `dashboard warm start failed: ${result.stdout}\n${result.stderr}`);
}

function addressFrom(child) {
  return new Promise((resolve, reject) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const deadline = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new Error(`dashboard address did not arrive within 0.95 s\n${stdout}\n${stderr}`));
    }, 950);
    function inspect() {
      const match = stdout.match(/^Factory dashboard: (http:\/\/127\.0\.0\.1:\d+\/)/m);
      if (match && !settled) {
        settled = true;
        clearTimeout(deadline);
        resolve(match[1]);
      }
    }
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); inspect(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.once('exit', (code) => {
      if (!settled) {
        settled = true;
        clearTimeout(deadline);
        reject(new Error(`dashboard exited before its address (code ${code})\n${stdout}\n${stderr}`));
      }
    });
  });
}

async function stopServer(server) {
  if (!server || server.child.exitCode !== null) return;
  const pid = server.pid;
  try { process.kill(pid, 'SIGTERM'); } catch (error) {
    if (error.code !== 'ESRCH') throw error;
  }
  await Promise.race([
    new Promise((resolve) => server.child.once('exit', resolve)),
    new Promise((resolve) => setTimeout(resolve, 900)),
  ]);
  if (server.child.exitCode === null) {
    try { process.kill(pid, 'SIGKILL'); } catch (error) {
      if (error.code !== 'ESRCH') throw error;
    }
  }
}

async function startServer(fixture, now) {
  const browserHome = path.join(fixture.home, `.home-${Date.now()}-${Math.random()}`);
  fs.mkdirSync(browserHome);
  const env = Object.assign({}, process.env, {
    HOME: browserHome,
    FACTORY_HOME: fixture.home,
    FACTORY_NOW: now,
    FACTORY_OSASCRIPT_BIN: fixture.fake,
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONPYCACHEPREFIX: '/tmp/factory-test-pycache',
    TZ: 'America/New_York',
  });
  warmDashboard(env);
  const child = spawn('/usr/bin/python3', [FACTORY, 'dashboard', '--no-open', '--port', '0'], {
    cwd: ROOT, env, stdio: ['ignore', 'pipe', 'pipe'],
  });
  const server = { child, pid: child.pid, env, base: '' };
  try {
    server.base = await addressFrom(child);
    return server;
  } catch (error) {
    await stopServer(server);
    throw error;
  }
}

function screenshotPath(name) {
  check(SCREENSHOTS, 'FACTORY_UI_SCREENSHOT_DIR is required');
  fs.mkdirSync(SCREENSHOTS, { recursive: true });
  return path.join(SCREENSHOTS, name);
}

async function openPage(browser, server, build, now) {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }, timezoneId: 'America/New_York',
  });
  const page = await context.newPage();
  const problems = { outside: [], csp: [], page: [], console: [] };
  await page.addInitScript(() => {
    try { window.sessionStorage.setItem('factory-intro', 'seen'); } catch (error) { /* test guard */ }
    window.__tnCsp = [];
    document.addEventListener('securitypolicyviolation', (event) => {
      window.__tnCsp.push(`${event.violatedDirective}: ${event.blockedURI}`);
    });
  });
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    const base = new URL(server.base);
    if (url.origin !== base.origin) {
      problems.outside.push(route.request().url());
      await route.abort();
    } else {
      await route.continue();
    }
  });
  page.on('pageerror', (error) => problems.page.push(String(error)));
  page.on('console', (message) => {
    if (message.type() === 'error') problems.console.push(message.text());
  });
  check(page.clock && typeof page.clock.install === 'function',
    'tonight-ui: page.clock is missing; install playwright@1.49.1');
  await page.clock.install({ time: new Date(now) });
  await page.goto(`${server.base}?build=${encodeURIComponent(build)}`, {
    waitUntil: 'domcontentloaded', timeout: 900,
  });
  await page.locator('[data-fx="sentence"]').waitFor({ state: 'visible', timeout: 900 });
  return { context, page, problems };
}

async function closePage(opened) {
  opened.problems.csp = await opened.page.evaluate(() => window.__tnCsp || []);
  await opened.context.close();
  check(opened.problems.outside.length === 0,
    `outside requests: ${opened.problems.outside.join(' | ')}`);
  check(opened.problems.csp.length === 0, `CSP violations: ${opened.problems.csp.join(' | ')}`);
  check(opened.problems.page.length === 0, `page errors: ${opened.problems.page.join(' | ')}`);
  check(opened.problems.console.length === 0,
    `console errors: ${opened.problems.console.join(' | ')}`);
}

async function openCardFolds(page) {
  await page.locator('details[data-fx="plan-fold"], details[data-fx="stage"]').evaluateAll((nodes) => {
    for (const node of nodes) node.open = true;
  });
}

async function T_TN_30(browser, fixture) {
  const server = await startServer(fixture, '2026-01-10T14:37:00Z');
  try {
    const opened = await openPage(browser, server, 'tn/built', '2026-01-10T14:37:00Z');
    try {
      const { page } = opened;
      equal(await page.locator('[data-fx="sentence"]').innerText(),
        'Building: 1 of 4 pieces done, 1 waiting for a check, none running right now.',
        'T-TN-30 built sentence');
      const card = page.locator('[data-piece="B1"]');
      equal(await card.getAttribute('data-state'), 'built', 'B1 state');
      const state = card.locator('.fx2-st').first();
      check((await state.innerText()).startsWith('Built, waiting for a check'), 'built state text');
      check(await state.evaluate((node) => node.classList.contains('fx2-st-built')),
        'built state color class missing');
      const colors = await state.evaluate((node) => {
        const probe = document.createElement('span');
        probe.className = 'fx2-st fx2-st-sentback';
        node.after(probe);
        const value = [getComputedStyle(node).color, getComputedStyle(probe).color];
        probe.remove();
        return value;
      });
      equal(colors[0], colors[1], 'built and sent-back colors');
      contains(await card.innerText(), 'Built. Waiting for a check. No checker has started yet.');
      equal(await card.locator('.fx2-on').count(), 0, 'built card running ring');
      await page.getByText('What do these words mean?', { exact: true }).click();
      const rows = page.locator('[data-fx="legend-row"]');
      equal(await rows.count(), 10, 'legend row count');
      equal(await rows.nth(9).locator('[data-fx="legend-title"]').innerText(),
        'Built, waiting for a check', 'tenth legend title');
      await page.keyboard.press('Escape');
      await card.click();
      contains(await page.locator('[data-fx="drawer"]').innerText(),
        'The builder finished this piece. No checker has started on it yet.');
      check(!(await page.locator('body').innerText()).includes('Being checked'),
        'built page still says Being checked');
      await page.screenshot({ path: screenshotPath('T-TN-30-built.png'), fullPage: true });
      await page.goto(`${server.base}?build=${encodeURIComponent('tn/checking')}`, {
        waitUntil: 'domcontentloaded', timeout: 900,
      });
      const checking = page.locator('[data-piece="B1"]');
      equal(await checking.getAttribute('data-state'), 'checking', 'checking state');
      equal(await page.locator('[data-fx="sentence"]').innerText(),
        'Building: 1 of 4 pieces done, 1 being checked.', 'checking sentence');
    } finally {
      await closePage(opened);
    }
  } finally {
    await stopServer(server);
  }
}

async function T_TN_31(browser, fixture) {
  let server = await startServer(fixture, '2026-01-11T05:35:00Z');
  try {
    const quiet = await openPage(browser, server, 'tn/quiet', '2026-01-11T05:35:00Z');
    try {
      equal(await quiet.page.locator('[data-fx="sentence"]').innerText(),
        'Nothing is running. Last activity Jan 10, 9:35 am. 1 of 4 pieces done, 1 waiting for a check.',
        'quiet sentence');
      contains((await quiet.page.locator('[data-fx="calm"]').innerText()).toLowerCase(),
        'nothing is running either');
      await quiet.page.screenshot({ path: screenshotPath('T-TN-31-quiet.png'), fullPage: true });
    } finally {
      await closePage(quiet);
    }
  } finally {
    await stopServer(server);
  }

  server = await startServer(fixture, '2026-01-10T15:44:00Z');
  try {
    const done = await openPage(browser, server, 'tn/alldone', '2026-01-10T15:44:00Z');
    try {
      equal(await done.page.locator('[data-fx="sentence"]').innerText(),
        'All 4 pieces are done. The build has not been closed yet.', 'pre-finish sentence');
      await done.page.evaluate(() => { window.__mark = 1; });
      const result = spawnSync('/usr/bin/python3', [FACTORY, 'finish', '--build', 'tn/alldone'], {
        cwd: ROOT, env: server.env, encoding: 'utf8', timeout: 900,
      });
      check(result.status === 0, `factory finish failed: ${result.stdout}\n${result.stderr}`);
      await done.page.clock.runFor(10100);
      await done.page.locator('[data-fx="sentence"]')
        .filter({ hasText: 'Finished. All 4 pieces are done.' })
        .waitFor({ state: 'visible', timeout: 900 });
      equal(await done.page.locator('[data-fx="sentence"]').innerText(),
        'Finished. All 4 pieces are done.', 'finished sentence');
      contains(await done.page.locator('[data-fx="calm"]').innerText(),
        'This build is finished. Nothing is left to decide.');
      equal(await done.page.evaluate(() => window.__mark), 1, 'finish reloaded the page');
      await done.page.screenshot({ path: screenshotPath('T-TN-31-finished.png'), fullPage: true });
    } finally {
      await closePage(done);
    }
  } finally {
    await stopServer(server);
  }
}

async function T_TN_32(browser, fixture) {
  const server = await startServer(fixture, '2026-01-10T14:37:00Z');
  try {
    const opened = await openPage(browser, server, 'tn/hostile', '2026-01-10T14:37:00Z');
    try {
      const { page } = opened;
      const collected = [];
      await page.locator('[data-fx="picker"]').click();
      collected.push(await page.locator('[data-fx="picker-menu"]').innerText());
      await page.keyboard.press('Escape');
      await openCardFolds(page);
      const cards = page.locator('[data-fx="piece"]');
      const count = await cards.count();
      for (let index = 0; index < count; index += 1) {
        await cards.nth(index).click();
        const drawer = page.locator('[data-fx="drawer"]');
        const toggle = drawer.locator('[data-fx="tech-switch"]');
        if (!(await toggle.isChecked())) await toggle.check();
        collected.push(await drawer.innerText());
        await page.keyboard.press('Escape');
      }
      await page.locator('[data-fx="activity"]').click();
      const activityToggle = page.locator('[data-fx="drawer"] [data-fx="tech-switch"]');
      if (!(await activityToggle.isChecked())) await activityToggle.check();
      collected.push(await page.locator('[data-fx="drawer"]').innerText());
      collected.push(await page.locator('body').innerText());
      const all = collected.join('\n');
      equal(await page.evaluate(() => window.__tn), undefined, 'hostile script executed');
      equal(await page.locator('img').count(), 0, 'hostile text created an image');
      equal(await page.locator('script').count(), 1, 'hostile text created a script');
      for (const tag of HOSTILE_TAGS) {
        contains(all, tag, `hostile field not visible: ${tag}`);
      }
      contains(all, '<img');
      contains(all, '</script>');
      contains(await page.title(), '<img');
      await page.screenshot({ path: screenshotPath('T-TN-32-hostile.png'), fullPage: true });
    } finally {
      await closePage(opened);
    }
  } finally {
    await stopServer(server);
  }
}

async function T_TN_33(browser, fixture) {
  const server = await startServer(fixture, '2026-01-10T14:37:00Z');
  try {
    const opened = await openPage(browser, server, 'tn/other', '2026-01-10T14:37:00Z');
    try {
      const { page } = opened;
      equal(await page.locator('[data-fx="sentence"]').innerText(),
        'Building: 0 of 7 pieces done, 1 waiting for a check. 1 other task running.',
        'other-work sentence');
      equal(await page.locator('[data-fx="progress"]').getAttribute('aria-valuemax'), '7',
        'planned progress maximum');
      const stages = page.locator('[data-fx="stage-name"]');
      equal(await stages.last().innerText(), 'Other work', 'last stage name');
      contains(await page.locator('[data-piece="P1"]').innerText(), 'Plan piece one');
      check(!(await page.locator('body').innerText()).includes('Planner model rule overridden'),
        'event note renamed the planned piece');
    } finally {
      await closePage(opened);
    }
  } finally {
    await stopServer(server);
  }
}

const CASES = {
  'T-TN-30': T_TN_30,
  'T-TN-31': T_TN_31,
  'T-TN-32': T_TN_32,
  'T-TN-33': T_TN_33,
};

async function main() {
  check(SCREENSHOTS, 'FACTORY_UI_SCREENSHOT_DIR is required');
  const requested = process.argv.slice(2);
  const names = requested.length ? requested : Object.keys(CASES);
  for (const name of names) check(CASES[name], `unknown browser case ${name}`);
  const browser = await playwright.chromium.launch({ headless: true, timeout: 900 });
  const fixture = makeHome();
  try {
    const probe = await browser.newPage();
    check(probe.clock && typeof probe.clock.install === 'function',
      'tonight-ui: page.clock is missing; install playwright@1.49.1');
    await probe.close();
    for (const name of names) {
      await CASES[name](browser, fixture);
      process.stdout.write(`PASS ${name}\n`);
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
