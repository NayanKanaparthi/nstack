#!/usr/bin/env node
'use strict';

const assert = require('assert');
const childProcess = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');

const ROOT = path.resolve(__dirname, '../../../..');
const FACTORY = path.join(ROOT, 'skills/factory/scripts/factory.py');
const FIXTURE = path.join(ROOT, 'skills/factory/tests/fixtures/dashboard/make_dashboard_fixtures.py');
const EVIDENCE = path.resolve(process.env.FACTORY_UI_SCREENSHOT_DIR || path.join(os.tmpdir(), 'factory-dashboard-evidence'));
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
const CLOCKS = {
  pg1: '2026-01-10T14:50:00Z',
  'pg-needs': '2026-01-10T15:44:00Z',
  'pg-done': '2026-01-10T15:44:00Z',
  'pg-stop': '2026-01-10T15:44:00Z',
  xss: '2026-01-10T15:44:00Z',
};
const textDump = [];
const results = [];
const liveServers = new Set();

function fail(message) { throw new Error(message); }
function check(value, message) { if (!value) fail(message); }
function equal(actual, expected, message) { assert.deepStrictEqual(actual, expected, message); }
function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
function shot(name) { return path.join(EVIDENCE, name); }

function runSync(command, args, env) {
  return childProcess.spawnSync(command, args, {
    cwd: ROOT,
    env: Object.assign({}, process.env, env || {}),
    encoding: 'utf8',
    timeout: 950,
  });
}

function warmHelp() {
  const result = runSync('/usr/bin/python3', [FACTORY, 'dashboard', '--help'], {
    HOME: os.tmpdir(), FACTORY_HOME: path.join(os.tmpdir(), 'factory-dashboard-help-home'),
    FACTORY_OSASCRIPT_BIN: '/usr/bin/false', PYTHONDONTWRITEBYTECODE: '1',
  });
  if (result.status !== 0) fail(`dashboard help warm-up failed: ${result.stdout}${result.stderr}`);
}

function makeFixtures(home) {
  const result = runSync('/usr/bin/python3', ['-I', FIXTURE, home]);
  if (result.status !== 0) fail(`fixture generation failed: ${result.stdout}${result.stderr}`);
  return `${home}-empty`;
}

async function startServer(home, now) {
  const env = {
    HOME: path.dirname(home), FACTORY_HOME: home, FACTORY_NOW: now,
    FACTORY_OSASCRIPT_BIN: '/usr/bin/false', TZ: 'America/New_York',
    PYTHONDONTWRITEBYTECODE: '1', PATH: process.env.PATH,
  };
  const child = childProcess.spawn('/usr/bin/python3',
    [FACTORY, 'dashboard', '--no-open', '--port', '0'],
    {cwd: ROOT, env, stdio: ['ignore', 'pipe', 'pipe']});
  const stderr = [];
  const record = {child, pid: child.pid, address: null, env, stderr};
  liveServers.add(record);
  child.stderr.on('data', (chunk) => stderr.push(String(chunk)));
  const reader = readline.createInterface({input: child.stdout});
  const address = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`dashboard address deadline: ${stderr.join('')}`)), 950);
    reader.on('line', (line) => {
      if (line.startsWith('Factory dashboard: ')) {
        clearTimeout(timer);
        resolve(line.slice('Factory dashboard: '.length));
      }
    });
    child.once('exit', (code) => {
      clearTimeout(timer);
      reject(new Error(`dashboard exited ${code}: ${stderr.join('')}`));
    });
  });
  record.address = address;
  return record;
}

async function stopServer(server) {
  if (!server) return;
  liveServers.delete(server);
  if (server.child.exitCode !== null) return;
  const exited = new Promise((resolve) => server.child.once('exit', resolve));
  process.kill(server.pid, 'SIGTERM');
  await Promise.race([exited, sleep(950).then(() => fail(`saved PID ${server.pid} did not stop`))]);
}

async function guardedContext(browser, options) {
  const context = await browser.newContext(Object.assign({
    viewport: {width: 1280, height: 900}, timezoneId: 'America/New_York',
  }, options || {}));
  const guard = {outside: [], requests: [], csp: [], console: [], page: []};
  await context.addInitScript(() => {
    window.__csp = [];
    document.addEventListener('securitypolicyviolation', (event) => {
      window.__csp.push({directive: event.violatedDirective, blocked: event.blockedURI});
    });
  });
  return {context, guard};
}

async function guardedPage(context, guard, address) {
  await context.route('**/*', async (route) => {
    const url = route.request().url();
    if (url.startsWith(address)) { guard.requests.push(url); await route.continue(); }
    else { guard.outside.push(url); await route.abort(); }
  });
  const page = await context.newPage();
  page.on('console', (message) => { if (message.type() === 'error') guard.console.push(message.text()); });
  page.on('pageerror', (error) => guard.page.push(String(error)));
  return page;
}

async function installClock(page, iso) {
  check(page.clock && typeof page.clock.install === 'function', 'Playwright page.clock is unavailable');
  await page.clock.install({time: new Date(iso)});
}

async function openState(browser, fixtureHome, build, options) {
  const now = CLOCKS[build] || CLOCKS.pg1;
  const home = options && options.empty ? `${fixtureHome}-empty` : fixtureHome;
  const server = await startServer(home, now);
  const made = await guardedContext(browser, options && options.context);
  if (options && options.seen) {
    await made.context.addInitScript(() => sessionStorage.setItem('factory-intro', 'seen'));
  }
  const page = await guardedPage(made.context, made.guard, server.address);
  if (!options || options.clock !== false) await installClock(page, now);
  const suffix = options && options.path !== undefined ? options.path : `/?build=toy/${build}`;
  const response = await page.goto(server.address + suffix, {waitUntil: 'domcontentloaded', timeout: 950});
  return {server, context: made.context, guard: made.guard, page, response, address: server.address};
}

async function cleanupState(state) {
  if (!state) return;
  await state.context.close();
  await stopServer(state.server);
}

async function settleData(page) {
  await page.locator('[data-fx=sentence], [data-fx=empty], [data-fx=banner]').first().waitFor({timeout: 950});
}

async function openCardFolds(page) {
  await page.locator('details[data-fx=plan-fold], details[data-fx=stage]').evaluateAll((nodes) => {
    for (const node of nodes) node.open = true;
  });
}

async function finishGuards(state, allowFetchErrors) {
  const csp = await state.page.evaluate(() => window.__csp || []);
  equal(state.guard.outside, [], 'outside request attempted');
  equal(csp, [], 'CSP violation recorded');
  equal(state.guard.page, [], 'page error recorded');
  if (!allowFetchErrors) equal(state.guard.console, [], 'console error recorded');
}

async function test(id, body, preserveServers) {
  try {
    await body();
    results.push({id, ok: true});
    console.log(`PASS ${id}`);
  } catch (error) {
    results.push({id, ok: false, error: error.stack || String(error)});
    console.error(`FAIL ${id}: ${error.message || error}`);
  } finally {
    if (!preserveServers) {
      for (const server of Array.from(liveServers)) await stopServer(server);
    }
  }
}

async function introCases(browser, home) {
  let first;
  await test('T-DB-40', async () => {
    first = await openState(browser, home, 'pg1');
    const page = first.page;
    const intro = page.locator('#fd-intro');
    check(await intro.count() === 1, 'intro missing at DOMContentLoaded');
    equal(await intro.getAttribute('aria-hidden'), 'true');
    equal(await page.locator('body > :first-child').getAttribute('id'), 'fd-intro');
    equal(await page.locator('[data-fx=intro-word]').innerText(), 'factory');
    equal(await page.locator('.fd-intro-l').allInnerTexts(), ['f', 'a', 'c', 't', 'o', 'r', 'y']);
    equal(await page.locator('[data-fx=intro-by]').innerText(), 'by Nayan Kanaparthi');
    check(await page.locator('#view-factory').getAttribute('inert') !== null, 'page is not inert');
    equal(await page.locator('#view-factory').getAttribute('aria-hidden'), 'true');
    check(await page.locator('#view-factory').evaluate((el) => el.classList.contains('fd-pre')), 'fd-pre missing');
    check(await page.locator('[data-fx=watermark]').getAttribute('inert') !== null, 'watermark is not inert');
    equal(await page.evaluate(() => sessionStorage.getItem('factory-intro')), 'seen');
    const styles = await page.locator('.fd-intro-l').evaluateAll((nodes) => nodes.map((node) => {
      const style = getComputedStyle(node); return [style.animationDuration, style.animationDelay];
    }));
    equal(styles.map((x) => x[0]), Array(7).fill('0.6s'));
    const expected = [0.08, 0.125, 0.17, 0.215, 0.26, 0.305, 0.35];
    styles.forEach((style, index) => check(Math.abs(parseFloat(style[1]) - expected[index]) <= 0.005, 'letter delay mismatch'));
    equal(await page.locator('[data-fx=intro-word]').evaluate((el) => getComputedStyle(el).fontWeight), '600');
    await page.clock.runFor(1100);
    check(await intro.count() === 1, 'intro ended before 1100ms');
    check(!(await intro.evaluate((el) => el.classList.contains('fd-out'))), 'intro faded early');
    await page.clock.runFor(100);
    check(await intro.evaluate((el) => el.classList.contains('fd-out')), 'fd-out missing at 1200ms');
    check(!(await page.locator('#view-factory').evaluate((el) => el.classList.contains('fd-pre'))), 'page remained fd-pre');
    await page.clock.runFor(350);
    check(await intro.count() === 0, 'intro remains after 1550ms');
    equal(await page.locator('[data-fx=sentence]').innerText(), 'Building: 1 of 4 pieces done, 1 being checked, 1 being built.');
  }, true);
  await test('T-DB-45', async () => {
    check(first, 'T-DB-40 state unavailable');
    check(first.guard.requests.some((url) => url.includes('/api/factory?build=toy%2Fpg1')), 'data request did not start during intro');
    equal(await first.page.locator('[data-fx=sentence]').innerText(), 'Building: 1 of 4 pieces done, 1 being checked, 1 being built.');
  }, true);
  await test('T-DB-42', async () => {
    check(first, 'T-DB-40 state unavailable');
    await first.page.reload({waitUntil: 'domcontentloaded', timeout: 950});
    check(await first.page.locator('#fd-intro').count() === 0, 'intro replayed on reload');
    const tab = await guardedPage(first.context, first.guard, first.address);
    await installClock(tab, CLOCKS.pg1);
    await tab.goto(first.address + '/?build=toy/pg1', {waitUntil: 'domcontentloaded', timeout: 950});
    check(await tab.locator('#fd-intro').count() === 1, 'new tab did not show intro');
    const fresh = await openState(browser, home, 'pg1');
    check(await fresh.page.locator('#fd-intro').count() === 1, 'new context did not show intro');
    await cleanupState(fresh);
  });
  if (first) { await finishGuards(first); await cleanupState(first); }

  await test('T-DB-41', async () => {
    const server = await startServer(home, CLOCKS.pg1);
    const made = await guardedContext(browser);
    await made.context.addInitScript(() => Object.defineProperty(window, 'sessionStorage', {get() { throw new Error('blocked'); }}));
    const page = await guardedPage(made.context, made.guard, server.address);
    await installClock(page, CLOCKS.pg1);
    await page.goto(server.address + '/?build=toy/pg1', {waitUntil: 'domcontentloaded', timeout: 950});
    check(await page.locator('#fd-intro').count() === 1, 'intro absent when storage throws');
    await page.clock.runFor(1550);
    check(await page.locator('#fd-intro').count() === 0, 'intro remains');
    check(await page.locator('#view-factory').getAttribute('inert') === null, 'page remains inert');
    equal(made.guard.page, []);
    await made.context.close(); await stopServer(server);
  });

  await test('T-DB-43', async () => {
    const state = await openState(browser, home, 'pg1');
    await state.page.clock.runFor(300);
    await state.page.mouse.click(640, 450);
    check(await state.page.locator('#fd-intro').evaluate((el) => el.classList.contains('fd-skip')), 'fd-skip missing');
    await state.page.clock.runFor(160);
    check(await state.page.locator('#fd-intro').count() === 0, 'intro remains after click skip');
    equal(await state.page.locator('[data-fx=drawer]').getAttribute('aria-hidden'), 'true');
    check(!(await state.page.locator('[data-fx=picker-menu]').evaluate((el) => el.classList.contains('fx2-open'))), 'picker opened through intro');
    await cleanupState(state);
  });

  await test('T-DB-44', async () => {
    for (const key of ['Escape', 'Tab', 'Enter', 'a']) {
      const state = await openState(browser, home, 'pg1');
      const before = state.page.url();
      await state.page.clock.runFor(200);
      await state.page.keyboard.press(key);
      await state.page.clock.runFor(160);
      check(await state.page.locator('#fd-intro').count() === 0, `${key} did not skip`);
      check(await state.page.evaluate(() => document.activeElement === document.body), `${key} moved focus`);
      equal(state.page.url(), before);
      await cleanupState(state);
    }
  });

  await test('T-DB-46', async () => {
    const state = await openState(browser, home, 'pg1', {context: {reducedMotion: 'reduce'}});
    await state.page.screenshot({path: shot('T-DB-46-reduced-motion.png')});
    check(await state.page.locator('#fd-intro').count() === 0, 'reduced motion created intro');
    for (const attribute of ['inert', 'aria-hidden']) check(await state.page.locator('#view-factory').getAttribute(attribute) === null, `${attribute} present`);
    equal(await state.page.evaluate(() => sessionStorage.getItem('factory-intro')), null);
    equal(await state.page.locator('.fd-mark').evaluate((el) => getComputedStyle(el).transitionDuration), '0s');
    await cleanupState(state);
  });

  await test('T-DB-47', async () => {
    const state = await openState(browser, home, 'pg1', {context: {javaScriptEnabled: false}, clock: false, path: '/'});
    check(await state.page.locator('#fd-intro').count() === 0, 'no-script page has intro');
    check((await state.page.locator('#view-factory').innerText()).includes('This page needs JavaScript to show the board. The same board is in the terminal: run factory status.'), 'noscript sentence missing');
    equal(await state.page.locator('[data-fx=watermark]').innerText(), 'factory · by Nayan Kanaparthi');
    await state.page.screenshot({path: shot('T-DB-47-no-script.png')});
    await cleanupState(state);
  });

  await test('T-DB-48', async () => {
    const state = await openState(browser, home, 'pg1', {clock: false});
    const marks = [150, 300, 450, 400, 500];
    for (let index = 0; index < marks.length; index += 1) {
      await sleep(marks[index]);
      await state.page.screenshot({path: shot(`T-DB-48-intro-${index + 1}${index === 4 ? '-page' : ''}.png`)});
    }
    check(await state.page.locator('#fd-intro').count() === 0, 'real-time intro remains');
    await cleanupState(state);
  });
}

async function pageCases(browser, home) {
  await test('T-DB-50', async () => {
    for (const build of ['pg1', 'pg-needs', 'pg-done']) {
      const state = await openState(browser, home, build, {seen: true});
      await settleData(state.page);
      equal(await state.page.locator('nav, aside, .side, .shell, .top, .crumb').count(), 0);
      const visible = await state.page.locator('#view-factory').innerText();
      const privateWords = [['Agentic', ' OS'], ['Mini', 'stry'], ['Mem', 'ory'], ['Con', 'ductor']]
        .map((parts) => parts.join(''));
      for (const word of privateWords) check(!visible.includes(word), `${word} leaked`);
      equal(await state.page.locator('.fd-wordmark').innerText(), 'factory');
      check((await state.page.title()).endsWith(' · factory'), 'document title suffix missing');
      await cleanupState(state);
    }
    const empty = await openState(browser, home, 'pg1', {seen: true, empty: true, path: '/'});
    await settleData(empty.page); equal(await empty.page.title(), 'factory'); await cleanupState(empty);
  });

  await test('T-DB-51', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); await settleData(state.page);
    check((await state.page.locator('[data-fx=calm]').innerText()).includes('Nothing needs you'), 'calm panel missing');
    equal(await state.page.locator('[data-fx=sentence]').innerText(), 'Building: 1 of 4 pieces done, 1 being checked, 1 being built.');
    equal(await state.page.locator('[data-fx=stage-name]').allInnerTexts(), ['Groundwork', 'Two options', 'Final check']);
    const progress = state.page.locator('[data-fx=progress]');
    equal(await progress.getAttribute('aria-valuemin'), '0'); equal(await progress.getAttribute('aria-valuemax'), '4'); equal(await progress.getAttribute('aria-valuenow'), '1');
    equal(await state.page.locator('[data-piece=B1]').getAttribute('data-state'), 'building');
    equal(await state.page.locator('[data-piece=B2]').getAttribute('data-state'), 'checking');
    equal(await state.page.locator('[data-piece=C1]').getAttribute('data-state'), 'waiting');
    await cleanupState(state);
  });

  await test('T-DB-52', async () => {
    const state = await openState(browser, home, 'pg-needs', {seen: true}); await settleData(state.page);
    equal(await state.page.locator('[data-fx=needs]').count(), 1);
    const text = await state.page.locator('[data-fx=needs]').innerText();
    for (const phrase of ['Needs you · Release decision', 'Suggested answer', 'Asked at', 'Reply in your Claude Code session']) check(text.includes(phrase), `${phrase} missing`);
    equal(await state.page.locator('[data-fx=needs] button, [data-fx=needs] input, [data-fx=needs] textarea, [data-fx=needs] select, [data-fx=needs] a[href]').count(), 0);
    equal(await state.page.locator('[data-fx=sentence]').innerText(), '3 of 4 pieces are done. Your answer is needed: release decision.');
    await cleanupState(state);
  });

  await test('T-DB-53', async () => {
    const state = await openState(browser, home, 'pg-done', {seen: true}); await settleData(state.page);
    equal(await state.page.locator('[data-fx=needs]').count(), 0);
    check((await state.page.locator('[data-fx=plan-fold]').innerText()).match(/The plan: \d+ pieces, all finished/), 'finished plan fold missing');
    equal(await state.page.locator('[data-fx=sentence]').innerText(), 'Finished. All 4 pieces are done.');
    await state.page.locator('[data-fx=picker]').click();
    check((await state.page.locator('[data-fx=picker-menu]').innerText()).includes('Finished'), 'picker state is not Finished');
    await cleanupState(state);
  });

  await test('T-DB-54', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); await settleData(state.page);
    await state.page.locator('[data-piece=B1]').click();
    const drawer = state.page.locator('[data-fx=drawer]');
    equal(await drawer.getAttribute('aria-hidden'), 'false');
    const toggle = state.page.locator('[data-fx=tech-switch]');
    check(!(await toggle.isChecked()), 'technical details defaulted on');
    let text = await drawer.innerText(); check(!text.includes('B1.maker.1') && !text.includes('piece id'), 'technical text leaked');
    await toggle.check(); text = await drawer.innerText(); check(text.includes('piece id: B1') && text.includes('B1.maker.1'), 'technical text missing');
    await state.page.keyboard.press('Escape'); equal(await drawer.getAttribute('aria-hidden'), 'true');
    await openCardFolds(state.page);
    await state.page.locator('[data-piece=A1]').click(); check(await toggle.isChecked(), 'switch did not persist in memory');
    await state.page.reload({waitUntil: 'domcontentloaded', timeout: 950}); await settleData(state.page);
    await state.page.locator('[data-piece=B1]').click(); check(!(await toggle.isChecked()), 'switch persisted across reload');
    await cleanupState(state);
  });

  await test('T-DB-55', async () => {
    for (const build of ['pg1', 'pg-needs', 'pg-done', 'pg-stop']) {
      const state = await openState(browser, home, build, {seen: true}); await settleData(state.page);
      async function collect(where) {
        for (const kind of ['plain', 'label']) {
          const entries = await state.page.locator(`[data-${kind}="1"]`).allInnerTexts();
          entries.forEach((text) => textDump.push({build: `toy/${build}`, where, kind, text}));
        }
      }
      await collect('page');
      await openCardFolds(state.page);
      for (const card of await state.page.locator('[data-piece]').all()) {
        const id = await card.getAttribute('data-piece'); await card.click(); await collect(`piece:${id}`); await state.page.keyboard.press('Escape');
      }
      if (await state.page.locator('[data-fx=activity]').count()) {
        await state.page.locator('[data-fx=activity]').click(); await collect('activity');
      }
      await cleanupState(state);
    }
    fs.writeFileSync(path.join(EVIDENCE, 'dashboard-text.json'), `${JSON.stringify(textDump, null, 2)}\n`);
  });

  await test('T-DB-57', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); await settleData(state.page);
    const text = (await state.page.locator('body').innerText()).replace("Didn't finish (shown as 'failed' in technical details)", '');
    const forbidden = /\b[A-Z]\d\b|\bs\d{3,}\b|sonnet-5-5|opus-5-5|fable-5-2|gpt-5\.6|\bspan\b|iteration|agent_call|rubric|\bnode\b|jsonl|\bloop\b|\bfailed\b/;
    check(!forbidden.test(text), `technical word visible: ${text.match(forbidden)}`);
    await state.page.locator('[data-piece=B1]').click(); await state.page.locator('[data-fx=tech-switch]').check();
    check((await state.page.locator('[data-fx=drawer]').innerText()).includes('piece id:'), 'technical switch did not reveal ids');
    await cleanupState(state);
  });

  await test('T-DB-58', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); await settleData(state.page);
    await state.page.getByText('What do these words mean?', {exact: true}).click();
    equal(await state.page.locator('[data-fx=legend-row]').count(), 10);
    equal(await state.page.locator('[data-fx=legend-title]').allInnerTexts(), ['Waiting', 'Building', 'Checking', 'Sent back', 'Done', 'Stopped', "Didn't finish (shown as 'failed' in technical details)", 'Waiting for you', 'Attempt 2 of this piece', 'Built, waiting for a check']);
    await cleanupState(state);
  });

  await test('T-DB-59', async () => {
    const state = await openState(browser, home, 'pg-needs', {seen: true, path: '/'}); await settleData(state.page);
    await state.page.locator('[data-fx=picker]').click(); equal(await state.page.locator('[data-fx=picker-item]').count(), 5);
    await state.page.locator('[data-fx=picker-item]').filter({hasText: 'Finish the greeting tool'}).click();
    equal(new URL(state.page.url()).search, '?build=toy%2Fpg-done');
    await state.page.reload({waitUntil: 'domcontentloaded', timeout: 950}); await settleData(state.page);
    check((await state.page.locator('[data-fx=picker]').innerText()).includes('Finish the greeting tool'), 'choice did not survive reload');
    equal(await state.page.locator('#fd-intro').count(), 0);
    await cleanupState(state);
  });
}

async function watermarkAndLiveCases(browser, home) {
  await test('T-DB-60', async () => {
    for (const build of ['pg1', 'pg-needs', 'pg-done']) {
      const state = await openState(browser, home, build, {seen: true}); await settleData(state.page);
      const mark = state.page.locator('a[data-fx=watermark]'); equal(await mark.count(), 1); check(await mark.isVisible(), 'watermark hidden');
      equal(await mark.innerText(), 'factory · by Nayan Kanaparthi');
      equal(await mark.getAttribute('href'), 'https://github.com/NayanKanaparthi/nstack'); equal(await mark.getAttribute('target'), '_blank');
      const rel = (await mark.getAttribute('rel')).split(/\s+/); check(rel.includes('noopener') && rel.includes('noreferrer'), 'rel safety tokens missing');
      const style = await mark.evaluate((el) => { const s = getComputedStyle(el); return [s.position, parseFloat(s.opacity), parseFloat(s.fontSize)]; });
      equal(style[0], 'fixed'); check(style[1] >= 0.5 && style[1] <= 0.7, 'watermark opacity'); check(style[2] <= 12, 'watermark font size');
      await cleanupState(state);
    }
  });

  await test('T-DB-61', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true, context: {reducedMotion: 'reduce'}}); await settleData(state.page);
    const mark = state.page.locator('[data-fx=watermark]'); await mark.hover();
    let style = await mark.evaluate((el) => getComputedStyle(el)); check(parseFloat(style.opacity) >= 0.9, 'hover opacity'); equal(style.textDecorationLine, 'underline');
    await mark.focus(); style = await mark.evaluate((el) => getComputedStyle(el)); check(style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2, 'focus outline');
    await cleanupState(state);
  });

  await test('T-DB-62', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); await settleData(state.page);
    await state.page.evaluate(() => scrollTo(0, document.body.scrollHeight));
    const boxes = await Promise.all([state.page.locator('[data-fx=watermark]').boundingBox(), state.page.locator('[data-fx=footer]').boundingBox()]);
    check(boxes[0].y + boxes[0].height <= boxes[1].y || boxes[1].y + boxes[1].height <= boxes[0].y, 'watermark overlaps footer');
    await state.page.locator('[data-piece=B1]').click(); const drawer = await state.page.locator('[data-fx=drawer]').boundingBox();
    check(boxes[0].x + boxes[0].width <= drawer.x, 'watermark overlaps drawer'); await cleanupState(state);
  });

  await test('T-DB-63', async () => {
    const state = await openState(browser, home, 'xss', {seen: true}); await settleData(state.page);
    await state.page.locator('[data-fx=picker]').click();
    await openCardFolds(state.page);
    for (const card of await state.page.locator('[data-piece]').all()) { await state.page.keyboard.press('Escape'); await card.click(); }
    if (await state.page.locator('[data-fx=tech-switch]').count()) await state.page.locator('[data-fx=tech-switch]').check();
    equal(await state.page.evaluate(() => window.__x), undefined); equal(await state.page.locator('img').count(), 0);
    check((await state.page.locator('body').innerText()).includes('<img src=x onerror=window.__x=1>'), 'hostile title not shown as text');
    check((await state.page.title()).includes('<img'), 'hostile document title missing'); await finishGuards(state); await cleanupState(state);
  });

  await test('T-DB-64', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); await settleData(state.page); await stopServer(state.server);
    await state.page.clock.runFor(3100);
    equal(await state.page.locator('[data-fx=banner]').innerText(), "Can't reach the dashboard. Trying again.");
    check(await state.page.locator('.fx2-stale').count() > 0, 'old data not marked stale'); await state.page.screenshot({path: shot('T-DB-64-unreachable.png')});
    await state.context.close();
    const missing = await openState(browser, home, 'pg1', {seen: true, path: '/?build=toy/zzz'}); await settleData(missing.page);
    equal(await missing.page.locator('[data-fx=banner]').innerText(), 'No build called toy/zzz.'); await cleanupState(missing);
  });

  await test('T-DB-65', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true, empty: true, path: '/'}); await settleData(state.page);
    equal(await state.page.locator('[data-fx=empty]').innerText(), 'No factory builds yet. Start one with /factory in Claude Code.');
    equal(await state.page.title(), 'factory'); await state.page.screenshot({path: shot('T-DB-65-empty.png')}); await cleanupState(state);
  });

  await test('T-DB-66', async () => {
    for (const [build, duration, min, max] of [['pg1', 12000, 3, 5], ['pg-done', 25000, 2, 4]]) {
      const state = await openState(browser, home, build, {seen: true}); let count = 0;
      state.page.on('request', (request) => { if (new URL(request.url()).pathname.startsWith('/api/factory')) count += 1; });
      const begin = Date.now(); await state.page.clock.runFor(duration); check(Date.now() - begin < 1000, 'fake clock took real time');
      check(count >= min && count <= max, `${build} polling count ${count}`); await cleanupState(state);
    }
  });

  await test('T-DB-67', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); equal(state.response.headers()['content-security-policy'], CSP); await finishGuards(state); await cleanupState(state);
  });

  await test('T-DB-68', async () => {
    const state = await openState(browser, home, 'pg1', {seen: true}); await settleData(state.page); await state.page.evaluate(() => { window.__mark = 1; });
    const result = runSync('/usr/bin/python3', [FACTORY, 'log', 'end', 'b2c1', '--build', 'toy/pg1', '--verdict', 'approved', '--plain', 'The checker approved the quiet option. This piece is finished.'], state.server.env);
    equal(result.status, 0, result.stderr); await state.page.clock.runFor(3100);
    await state.page.locator('[data-piece=B2][data-state=done]').waitFor({state: 'attached', timeout: 950});
    equal(await state.page.locator('[data-piece=B2]').getAttribute('data-state'), 'done'); equal(await state.page.evaluate(() => window.__mark), 1); await cleanupState(state);
  });
}

async function screenshotCases(browser, home) {
  await test('T-DB-70', async () => {
    const scenarios = [
      ['pg-needs', 'T-DB-70-1-needs.png'], ['pg1', 'T-DB-70-2-working.png'], ['pg-done', 'T-DB-70-3-done.png'],
      ['pg1', 'T-DB-70-4-drawer-off.png', 'drawer'], ['pg1', 'T-DB-70-5-drawer-on.png', 'tech'],
      ['pg1', 'T-DB-70-6-activity.png', 'activity'], ['pg1', 'T-DB-70-7-legend.png', 'legend'],
      ['pg1', 'T-DB-70-8-picker.png', 'picker'], ['pg1', 'T-DB-70-9-empty.png', 'empty'],
      ['pg1', 'T-DB-70-10-narrow.png', 'narrow'],
    ];
    for (const [build, name, action] of scenarios) {
      const state = await openState(browser, home, build, {seen: true, empty: action === 'empty', path: action === 'empty' ? '/' : undefined,
        context: action === 'narrow' ? {viewport: {width: 900, height: 900}} : undefined});
      await settleData(state.page);
      if (action === 'drawer' || action === 'tech') await state.page.locator('[data-piece=B1]').click();
      if (action === 'tech') await state.page.locator('[data-fx=tech-switch]').check();
      if (action === 'activity') await state.page.locator('[data-fx=activity]').click();
      if (action === 'legend') await state.page.getByText('What do these words mean?', {exact: true}).click();
      if (action === 'picker') await state.page.locator('[data-fx=picker]').click();
      if (action === 'narrow') check(await state.page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), 'narrow page overflows');
      await state.page.screenshot({path: shot(name), fullPage: false}); await cleanupState(state);
      check(fs.statSync(shot(name)).size >= 20000, `${name} is too small`);
    }
  });
}

async function main() {
  let version;
  try { version = require('playwright/package.json').version; }
  catch (error) { console.error('dashboard-ui: install playwright@1.49.1 as the README says'); return 2; }
  if (version !== '1.49.1') { console.error('dashboard-ui: install playwright@1.49.1 as the README says'); return 2; }
  const {chromium} = require('playwright');
  fs.mkdirSync(EVIDENCE, {recursive: true});
  warmHelp();
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'factory-dashboard-ui-'));
  const home = path.join(temp, 'factory-home');
  makeFixtures(home);
  const browser = await chromium.launch({headless: true});
  try {
    const probe = await browser.newPage();
    if (!probe.clock || typeof probe.clock.install !== 'function') {
      console.error('dashboard-ui: install playwright@1.49.1 as the README says');
      return 2;
    }
    await probe.close();
    await introCases(browser, home);
    await pageCases(browser, home);
    await watermarkAndLiveCases(browser, home);
    await screenshotCases(browser, home);
  } finally {
    for (const server of Array.from(liveServers)) await stopServer(server);
    await browser.close();
  }
  return results.some((result) => !result.ok) ? 1 : 0;
}

main().then((code) => { process.exitCode = code; }).catch((error) => {
  console.error(`dashboard-ui: ${error.stack || error}`); process.exitCode = 1;
});
