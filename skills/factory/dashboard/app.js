/* factory dashboard: the plain-words board page. No dependencies.
   Every string from the board goes in through textContent or a fixed-name attribute,
   never through markup. The board computes everything; this file only draws it. */
(function () {
  'use strict';

  var ROOT_ID = 'fx-root', VIEW_ID = 'view-factory';
  var FAST_MS = 3000, SLOW_MS = 10000, RETRY_MS = 3000;
  var ASK_POINTER = 'Answer at the top of this page.';

  /* The ten words of the legend (fixed text, same as the approved mockup). */
  var LEGEND = [
    ['Waiting', 'This piece cannot start yet because it needs other pieces to finish first.'],
    ['Building', 'A builder is making this piece right now.'],
    ['Being checked', "A different AI is reading the builder's work and looking for problems."],
    ['Sent back', 'The checker found problems. The builder will fix them in a new attempt.'],
    ['Done', 'The checker is satisfied. Nothing more is needed on this piece.'],
    ['Stopped', 'This attempt ended early, on purpose or because something ran out or got stuck. The note says which and what happens next.'],
    ["Didn't finish (shown as 'failed' in technical details)", 'This attempt ended with a problem it could not fix by itself, such as hitting a usage limit. The note says why, and another attempt follows.'],
    ['Waiting for you', 'A decision only you can make. It appears at the top of the page.'],
    ['Attempt 2 of this piece', 'How many times a builder has taken a turn at this piece. A piece sent back gets a new attempt.'],
    ['Built, waiting for a check', 'The builder finished this piece. No checker has started on it yet.']
  ];
  var MEANING = {waiting: 0, building: 1, checking: 2, sent_back: 3, done: 4, stopped: 5, needs_you: 7, built: 9};
  var STATE_WORD = {
    waiting: 'Waiting', building: 'Building', checking: 'Being checked', built: 'Built, waiting for a check',
    sent_back: 'Sent back for fixes', stopped: 'Stopped', done: 'Done', needs_you: 'Waiting for you'
  };

  var st = {
    chosen: null,       // build the person picked (null: follow the most recent)
    builds: [],
    selected: null,
    board: null,        // last good board
    boardKey: '',
    banner: '',
    stale: false,
    empty: false,
    goodAt: 0,
    nextAt: 0,
    inflight: false,
    seq: 0,
    built: false,
    tech: false,        // technical details switch (memory only)
    menuOpen: false,
    legendOpen: false,
    folds: {},          // open state of folded stages, by key
    drawer: null,       // {kind: 'piece'|'activity', id}
    drawerKey: ''
  };
  var el = {};

  /* ---------- small helpers ---------- */
  function h(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function add(parent) {
    for (var i = 1; i < arguments.length; i++) if (arguments[i]) parent.appendChild(arguments[i]);
    return parent;
  }
  function attr(n, name, value) { n.setAttribute(name, String(value)); return n; }
  function plain(n) { return n.textContent ? attr(n, 'data-plain', '1') : n; }        // one owner-facing sentence
  function label(n) { return n.textContent ? attr(n, 'data-label', '1') : n; }        // a short label
  function exempt(n, kind) { attr(n, 'data-plain-exempt', '1'); return attr(n, 'data-exempt-kind', kind); }
  function fx(n, name) { return attr(n, 'data-fx', name); }
  function str(v, fallback) { return (typeof v === 'string' && v) ? v : fallback; }
  function num(v) { return (typeof v === 'number' && isFinite(v)) ? v : null; }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function obj(v) { return (v && typeof v === 'object' && !Array.isArray(v)) ? v : {}; }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function text(parent, value) { parent.appendChild(document.createTextNode(value)); }
  function sep() { return h('span', 'fx2-dot', ' · '); }

  /* A build name is project/id: letters, digits, dot, underscore and dash, no . or .. part. */
  function validBuild(key) {
    if (typeof key !== 'string' || key.length > 200 || !/^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(key)) return false;
    var parts = key.split('/');
    return parts[0] !== '.' && parts[0] !== '..' && parts[1] !== '.' && parts[1] !== '..';
  }

  function visible() {
    var v = document.getElementById(VIEW_ID);
    return !!v && !v.classList.contains('hidden') && !document.hidden;
  }

  function running() {
    var s = st.board && st.board.build && st.board.build.state;
    return s === 'running' || s === 'waiting';
  }

  function clockOf(when) {
    var d = new Date(when);
    if (isNaN(d.getTime())) return '';
    var hr = d.getHours(), mn = d.getMinutes();
    var ap = hr >= 12 ? 'pm' : 'am';
    hr = hr % 12 || 12;
    return hr + ':' + (mn < 10 ? '0' : '') + mn + ' ' + ap;
  }

  /* ---------- page skeleton (built once) ---------- */
  function build() {
    var root = document.getElementById(ROOT_ID);
    if (!root || st.built) return !!root;
    st.built = true;
    el.root = root;
    el.page = h('div', 'fx2-page');
    el.data = h('div', 'fx2-data');
    el.emptyMsg = fx(h('div', 'fx2-empty', 'No factory builds yet. Start one with /factory in Claude Code.'), 'empty');
    el.emptyMsg.style.display = 'none';
    el.warn = fx(h('div', 'fx2-warn'), 'warnings');
    el.warn.style.display = 'none';
    el.foot = fx(h('div', 'fx2-foot'), 'footer');
    el.footMsg = h('div', 'fx2-foot-msg', 'Select any piece to see what each attempt did and why.');
    el.footAge = h('div', 'fx2-foot-age', '');
    add(el.foot, el.footMsg, el.footAge);
    add(el.page, el.data, el.emptyMsg, el.foot);
    root.appendChild(el.page);
    buildDrawer();
    return true;
  }

  function buildDrawer() {
    if (el.drawer) return;
    el.scrim = fx(h('div', 'fx2-scrim'), 'scrim');
    el.scrim.addEventListener('click', function () { closeDrawer(false); });
    el.drawer = fx(h('div', 'fx2-drawer'), 'drawer');
    attr(el.drawer, 'aria-hidden', 'true');
    attr(el.drawer, 'role', 'dialog');
    attr(el.drawer, 'aria-label', 'Details');
    el.close = h('button', 'fx2-pill fx2-x', 'Close');
    el.close.type = 'button';
    el.close.addEventListener('click', function () { closeDrawer(false); });
    el.dhead = h('div', 'fx2-dhead');
    var tg = h('label', 'fx2-tgl');
    el.tech = fx(h('input'), 'tech-switch');
    el.tech.type = 'checkbox';
    el.tech.checked = st.tech;
    el.tech.addEventListener('change', function () {
      st.tech = el.tech.checked;
      el.drawer.classList.toggle('fx2-showtech', st.tech);
    });
    add(tg, el.tech, h('span', '', 'Show technical details'));
    el.dbody = h('div', 'fx2-dbody');
    add(el.drawer, el.close, el.dhead, tg, el.dbody);
    document.body.appendChild(el.scrim);
    document.body.appendChild(el.drawer);
    el.drawer.addEventListener('keydown', trapTab);
  }

  function trapTab(ev) {
    if (ev.key !== 'Tab' || !st.drawer) return;
    var items = el.drawer.querySelectorAll('button, input, [tabindex="0"]');
    var list = [];
    for (var i = 0; i < items.length; i++) {
      var n = items[i];
      if (n.offsetParent !== null || n === document.activeElement) list.push(n);
    }
    if (!list.length) return;
    var first = list[0], last = list[list.length - 1];
    if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
  }

  function setBanner(msg) {
    st.banner = msg || '';
    if (el.banner && el.banner.parentNode) el.banner.parentNode.removeChild(el.banner);
    el.banner = null;
    if (st.banner) {
      el.banner = fx(h('div', 'fx2-banner', st.banner), 'banner');
      el.banner.setAttribute('role', 'alert');
      el.page.insertBefore(el.banner, el.page.firstChild);
    }
  }

  function setStale(on) {
    st.stale = !!on;
    el.data.classList.toggle('fx2-stale', st.stale);
  }

  /* ---------- header and picker ---------- */
  function buildKey(b) { return b.project + '/' + b.id; }

  function currentEntry() {
    for (var i = 0; i < st.builds.length; i++) if (buildKey(st.builds[i]) === st.selected) return st.builds[i];
    return null;
  }

  function header() {
    var box = h('div', 'fx2-head');
    var wrap = h('div', 'fx2-picker');
    var entry = currentEntry();
    var titleText = entry ? str(entry.title_plain, str(entry.title, st.selected)) :
      str(obj(obj(st.board).build).title, 'Factory build');
    var btn = fx(h('button', 'fx2-pick-btn'), 'picker');
    btn.type = 'button';
    attr(btn, 'aria-haspopup', 'true');
    attr(btn, 'aria-expanded', st.menuOpen ? 'true' : 'false');
    attr(btn, 'data-build', st.selected || '');
    var title = exempt(h('div', 'fx2-h1', titleText), 'build-title');
    add(title, h('span', 'fx2-chev', '⌄'));
    add(btn, h('div', 'fx2-kick', 'Build'), title);
    btn.addEventListener('click', function (ev) {
      ev.stopPropagation();
      setMenu(!st.menuOpen);
    });
    var menu = fx(h('div', 'fx2-glass fx2-menu' + (st.menuOpen ? ' fx2-open' : '')), 'picker-menu');
    st.builds.forEach(function (b) {
      var key = buildKey(b);
      var item = fx(h('button', 'fx2-mi' + (key === st.selected ? ' fx2-sel' : '')), 'picker-item');
      item.type = 'button';
      attr(item, 'data-build', key);
      var left = h('div', 'fx2-mi-l');
      add(left, exempt(fx(h('div', 'fx2-mi-t', str(b.title_plain, str(b.title, key))), 'picker-title'), 'build-title'),
          exempt(fx(h('div', 'fx2-mi-id', key), 'picker-id'), 'build-id'));
      var word = str(b.state_word, 'Quiet');
      add(item, left, label(h('div', 'fx2-mi-s' + (word === 'Needs you' ? ' fx2-needs' : ''), word)));
      item.addEventListener('click', function (ev) {
        ev.stopPropagation();
        choose(key);
      });
      menu.appendChild(item);
    });
    add(wrap, btn, menu);
    var act = fx(h('button', 'fx2-pill fx2-act', 'Activity'), 'activity');
    act.type = 'button';
    act.addEventListener('click', function () { openDrawer('activity', '', act); });
    add(box, wrap, act);
    return box;
  }

  function setMenu(on) {
    st.menuOpen = !!on;
    var menu = el.data.querySelector('[data-fx="picker-menu"]');
    var btn = el.data.querySelector('[data-fx="picker"]');
    if (menu) menu.classList.toggle('fx2-open', st.menuOpen);
    if (btn) btn.setAttribute('aria-expanded', st.menuOpen ? 'true' : 'false');
  }

  function choose(key) {
    st.menuOpen = false;
    var same = key === st.selected && !!st.board;
    st.chosen = key;
    try { history.replaceState(null, '', '?build=' + encodeURIComponent(key)); } catch (e) { /* keep going */ }
    if (same) { setMenu(false); return; }
    st.nextAt = 0;
    closeDrawer(true);
    st.folds = {};
    load();
    setMenu(false);
  }

  /* ---------- needs-you or calm panel ---------- */
  function needsPanels(owner) {
    var out = [];
    arr(owner.items).forEach(function (it) {
      var p = fx(h('section', 'fx2-mat fx2-need fx2-yes'), 'needs');
      var tag = h('div', 'fx2-tag', 'Needs you · ' + str(it.gate_label, 'Decision'));
      var q = exempt(h('div', 'fx2-q', str(it.question, 'A decision is needed (question not recorded)')), 'gate-question');
      add(p, tag, q);
      if (str(it.recommend, '')) {
        var sug = h('div', 'fx2-sug');
        add(sug, h('div', 'fx2-sug-l', 'Suggested answer'),
            exempt(h('div', 'fx2-sug-a', it.recommend), 'gate-suggestion'));
        p.appendChild(sug);
      }
      var how = h('div', 'fx2-how');
      var pillText = 'Reply in your Claude Code session';
      var when = '';
      if (str(it.asked_label, '')) when = 'Asked at ' + it.asked_label + '.';
      if (str(it.waiting_label, '')) when += (when ? ' ' : '') + 'Waiting ' + it.waiting_label + ' so far.';
      add(how, h('span', 'fx2-cta', pillText), when ? h('span', 'fx2-how-m', when) : null);
      p.appendChild(how);
      out.push(p);
    });
    return out;
  }

  function calmPanel(owner) {
    var calm = obj(owner.calm);
    var p = fx(h('section', 'fx2-mat fx2-need fx2-no'), 'calm');
    var body = h('div', 'fx2-calm-b');
    add(body, h('div', 'fx2-calm-h', str(calm.title, 'Nothing needs you')),
        plain(h('div', 'fx2-calm-p', str(calm.text, ''))));
    add(p, h('div', 'fx2-okc', '✓'), body);
    return p;
  }

  /* ---------- status block ---------- */
  function statusBlock(owner) {
    var box = h('section', 'fx2-status');
    var counts = obj(owner.counts);
    var total = num(counts.total) || 0, done = num(counts.done) || 0;
    var flight = (num(counts.building) || 0) + (num(counts.checking) || 0) + (num(counts.built) || 0) +
      (num(counts.sent_back) || 0) + (num(counts.stopped) || 0) + (num(counts.needs_you) || 0);
    add(box, plain(fx(h('div', 'fx2-sent', str(owner.sentence, '')), 'sentence')));
    var bar = fx(h('div', 'fx2-bar'), 'progress');
    attr(bar, 'role', 'progressbar');
    attr(bar, 'aria-valuemin', 0);
    attr(bar, 'aria-valuemax', total);
    attr(bar, 'aria-valuenow', done);
    var pd = h('i', 'fx2-bar-d'), pa = h('i', 'fx2-bar-a');
    pd.style.width = (total ? done / total * 100 : 0) + '%';
    pa.style.width = (total ? flight / total * 100 : 0) + '%';
    add(bar, pd, pa);
    box.appendChild(bar);
    var meta = h('div', 'fx2-meta');
    var left = h('span', 'fx2-meta-l');
    if (str(owner.started_label, '')) {
      var finished = st.board && st.board.build && st.board.build.state === 'done';
      text(left, 'Started at ' + owner.started_label + '. ');
      if (str(owner.elapsed_label, '')) add(left, document.createTextNode(finished ? 'Took ' : ''), h('b', '', owner.elapsed_label), document.createTextNode(finished ? '.' : ' so far.'));
    }
    add(meta, left);
    if (str(owner.deadline_text, '')) add(meta, plain(fx(h('span', 'fx2-deadline', owner.deadline_text), 'deadline')));
    box.appendChild(meta);
    return box;
  }

  /* ---------- the plan ---------- */
  function legendBlock() {
    var d = fx(h('details', 'fx2-legend'), 'legend');
    if (st.legendOpen) d.open = true;
    d.addEventListener('toggle', function () { st.legendOpen = d.open; });
    d.appendChild(h('summary', '', 'What do these words mean?'));
    var box = h('div', 'fx2-glass fx2-legend-box');
    LEGEND.forEach(function (row) {
      var r = fx(h('div', 'fx2-lg'), 'legend-row');
      add(r, exempt(fx(h('b', '', row[0]), 'legend-title'), 'legend-title'), plain(h('span', '', row[1])));
      box.appendChild(r);
    });
    d.appendChild(box);
    return d;
  }

  function stageHead(s, folded) {
    var hd = h('div', 'fx2-shd');
    var nm = h('span', 'fx2-t', str(s.name, 'Stage'));
    add(hd, h('span', 'fx2-n', s.n), label(folded ? nm : fx(nm, 'stage-name')));
    if (str(s.purpose, '')) hd.appendChild(plain(h('span', 'fx2-w', s.purpose)));
    var count = arr(s.pieces).length;
    if (s.parallel === true || count > 1) {
      hd.appendChild(label(h('span', 'fx2-par', count + ' pieces side by side')));
    }
    return hd;
  }

  function stageAttrs(n, s) {
    attr(n, 'data-stage', s.n);
    attr(n, 'data-stage-state', str(s.state, ''));
    return fx(n, 'stage');
  }

  function stageBody(s, byId) {
    var cards = h('div', 'fx2-cards');
    arr(s.pieces).forEach(function (id) {
      var p = byId[id];
      if (p) cards.appendChild(card(p));
    });
    return cards;
  }

  function foldOpen(d, key) {
    if (st.folds[key]) d.open = true;
    d.addEventListener('toggle', function () { st.folds[key] = d.open; });
  }

  function stageNode(s, byId, inFold) {
    var allDone = s.state === 'done';
    if (allDone && !inFold) {
      var d = stageAttrs(h('details', 'fx2-mat fx2-fold'), s);
      foldOpen(d, 'stage:' + s.n);
      var sm = h('summary');
      var count = str(s.count_label, arr(s.pieces).length + ' pieces');
      /* The folded stage's name stays on the visible summary line, so the hook is readable while folded. */
      var sumt = add(h('span', 'fx2-sumt'), document.createTextNode(s.n + '. '),
        fx(h('span', '', str(s.name, 'Stage')), 'stage-name'));
      add(sm, h('span', 'fx2-ck', '✓'), label(sumt),
          label(h('span', 'fx2-sumd', count + ' done · Show')));
      add(d, sm, add(h('div', 'fx2-foldbody'), stageHead(s, true), stageBody(s, byId)));
      return d;
    }
    return add(stageAttrs(h('section', 'fx2-stage'), s), stageHead(s), stageBody(s, byId));
  }

  function flow(stages, byId, inFold) {
    var box = h('div', 'fx2-flow');
    stages.forEach(function (s, i) {
      if (i) box.appendChild(h('div', 'fx2-conn'));
      box.appendChild(stageNode(s, byId, inFold));
    });
    return box;
  }

  function planBlock(board) {
    var plan = obj(board.plan), owner = obj(board.owner), counts = obj(owner.counts);
    var stages = arr(plan.stages), pieces = arr(plan.pieces);
    var byId = {};
    pieces.forEach(function (p) { byId[p.id] = p; });
    var total = num(counts.total) || pieces.length;
    var finished = total > 0 && !owner.needs_you && (num(counts.done) === total);
    var box = h('section', 'fx2-plan');
    if (!stages.length) {
      add(box, h('div', 'fx2-h2', 'The plan'), h('div', 'fx2-none', 'No pieces yet.'));
      return box;
    }
    if (finished) {
      var d = fx(h('details', 'fx2-mat fx2-fold'), 'plan-fold');
      foldOpen(d, 'plan');
      var sm = h('summary');
      add(sm, h('span', 'fx2-ck', '✓'),
          label(h('span', 'fx2-sumt', 'The plan: ' + total + (total === 1 ? ' piece' : ' pieces') + ', all finished')),
          label(h('span', 'fx2-sumd', 'Show')));
      add(d, sm, add(h('div', 'fx2-foldbody'), flow(stages, byId, true)));
      box.appendChild(d);
      return box;
    }
    var ph = h('div', 'fx2-plan-h');
    add(ph, h('div', 'fx2-h2', 'The plan'), legendBlock());
    add(box, ph, plain(h('div', 'fx2-sub', 'Pieces run top to bottom. Pieces in the same row run side by side. Each piece is built by one AI and checked by another.')),
        flow(stages, byId, false));
    return box;
  }

  /* ---------- a piece card ---------- */
  function stateLine(p, cls) {
    var state = str(p.state, 'waiting');
    var line = h('div', cls + ' fx2-st-' + state.replace(/_/g, ''));
    add(line, label(h('span', 'fx2-st-w', str(p.state_label, STATE_WORD[state] || 'Status not recorded'))));
    var att = str(p.attempt_label, '');
    if (att && state !== 'waiting' && state !== 'done' && state !== 'needs_you') {
      add(line, sep(), label(h('span', 'fx2-try', att)));
    }
    return line;
  }

  function rolesBlock(p) {
    var roles = obj(p.roles), names = ['builder', 'checker'], box = h('div', 'fx2-roles');
    var any = false;
    names.forEach(function (k) {
      var r = roles[k];
      if (!r) return;
      any = true;
      var state = p.state;
      var on = (k === 'builder' && state === 'building') || (k === 'checker' && state === 'checking');
      var row = h('div', 'fx2-role' + (on ? ' fx2-on' : ''));
      add(row, label(h('b', '', str(r.name, k))), label(h('span', 'fx2-role-n', str(r.note, ''))));
      box.appendChild(row);
    });
    return any ? box : null;
  }

  function chipsBlock(p) {
    var c = obj(p.chips), items = arr(c.items);
    if (!items.length) return null;
    var box = h('div', 'fx2-chips');
    var earlier = num(c.earlier) || 0;
    if (earlier > 0) add(box, h('span', 'fx2-ar', '+' + earlier + ' earlier ›'));
    items.forEach(function (it, i) {
      if (i) box.appendChild(h('span', 'fx2-ar', '›'));
      var tone = str(it.tone, '');
      box.appendChild(label(h('span', 'fx2-chip' + (tone ? ' fx2-chip-' + tone : ''), str(it.text, ''))));
    });
    return box;
  }

  function card(p) {
    var state = str(p.state, 'waiting');
    var cls = {needs_you: 'fx2-act', building: 'fx2-act', checking: 'fx2-act', sent_back: 'fx2-sb',
      stopped: 'fx2-sb', waiting: 'fx2-wt', built: 'fx2-wt', done: 'fx2-dn'}[state] || '';
    var c = h('div', 'fx2-mat fx2-pc ' + cls);
    fx(c, 'piece');
    attr(c, 'data-piece', p.id);
    attr(c, 'data-state', state);
    attr(c, 'data-call-count', arr(p.calls).length);
    attr(c, 'role', 'button');
    attr(c, 'tabindex', '0');
    add(c, stateLine(p, 'fx2-st'),
        label(h('div', 'fx2-nm', str(p.name, 'A piece without a plain name'))),
        plain(h('div', 'fx2-ds', str(p.purpose, ''))));
    var now = str(p.now, '');
    if (state === 'waiting') {
      if (now) c.appendChild(plain(h('div', 'fx2-after', now)));
    } else if (state === 'done') {
      if (str(p.summary, '')) c.appendChild(label(h('div', 'fx2-after', p.summary)));
    } else if (state === 'needs_you') {
      if (now) c.appendChild(plain(h('div', 'fx2-now', now)));
      c.appendChild(h('div', 'fx2-after fx2-ask', ASK_POINTER));
    } else {
      if (now) c.appendChild(plain(h('div', 'fx2-now', now)));
      var last = obj(p.last);
      if (str(last.text, '')) {
        var lb = h('div', 'fx2-last'), inner = h('span', 'fx2-last-in');
        add(inner, label(h('b', '', str(last.label, 'Last') + ':')), document.createTextNode(' '),
            plain(h('span', 'fx2-last-t', last.text)));
        c.appendChild(add(lb, inner));
      }
      add(c, rolesBlock(p), chipsBlock(p));
      if (str(p.quiet_text, '')) c.appendChild(plain(h('div', 'fx2-quiet', p.quiet_text)));
    }
    c.addEventListener('click', function () { openDrawer('piece', p.id, c); });
    c.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ' || ev.key === 'Spacebar') {
        ev.preventDefault();
        openDrawer('piece', p.id, c);
      }
    });
    return c;
  }

  /* ---------- the drawer ---------- */
  function findPiece(id) {
    var list = arr(obj(obj(st.board).plan).pieces);
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  }

  function techLine(text) { return fx(h('div', 'fx2-techline', text), 'tech'); }

  function callBlock(c) {
    var state = str(c.state, '');
    var b = fx(h('div', 'fx2-call'), 'call');
    var res = state === 'done' ? 'fx2-ok' : (state === 'running' ? 'fx2-go' : 'fx2-warn-t');
    var top = h('div', 'fx2-call-a');
    add(top, label(h('b', '', str(c.label, 'Attempt'))), label(h('span', 'fx2-res ' + res, str(c.result, ''))));
    var who = str(c.role_name, 'Worker') + ' · ' + str(c.model_name, 'Model not recorded');
    var start = str(c.start_label, '');
    if (start) {
      if (state === 'running') who += ' · ' + start + ' to now';
      else if (str(c.end_label, '')) who += ' · ' + start + ' to ' + c.end_label +
        (str(c.duration_label, '') ? ' (' + c.duration_label + ')' : '');
      else who += ' · ' + start;
    }
    add(b, top, exempt(h('div', 'fx2-who', who), 'who-line'),
        plain(h('div', 'fx2-pn', str(c.plain, ''))));
    var then = str(c.then, '');
    if (then) b.appendChild(plain(h('div', 'fx2-th', /^Next:/.test(then) ? then : 'Then: ' + then)));
    b.appendChild(techLine('entry: ' + str(c.key, '(none)') + ' · call: ' + str(c.call, '(none)')));
    b.appendChild(techLine('role: ' + str(c.role, '(none)') + ' · model: ' + str(c.model, '(none)') +
      ' · loop: ' + (c.loop === null || c.loop === undefined ? 'none' : c.loop) +
      ' · state: ' + str(c.state, '(none)')));
    if (str(c.stop_reason, '')) b.appendChild(techLine('stop reason: ' + c.stop_reason));
    b.appendChild(techLine('plain source: ' + str(c.plain_source, '(none)')));
    b.appendChild(techLine('raw note: ' + str(c.raw_note, '(empty)')));
    return b;
  }

  function fillPieceDrawer(p) {
    var state = str(p.state, 'waiting');
    attr(el.drawer, 'data-piece', p.id);
    add(el.dhead, label(h('h2', '', str(p.name, 'A piece without a plain name'))),
        plain(h('div', 'fx2-pur', str(p.purpose, ''))));
    var dst = stateLine(p, 'fx2-st fx2-dst-line');
    var wrap = h('div', 'fx2-dst');
    wrap.appendChild(dst);
    el.dhead.appendChild(wrap);
    if (MEANING[state] !== undefined) el.dhead.appendChild(plain(h('div', 'fx2-mean', LEGEND[MEANING[state]][1])));
    var calls = arr(p.calls);
    var tech = h('div', 'fx2-techblock');
    fx(tech, 'tech');
    var deps = arr(p.depends_on);
    add(tech, h('div', '', 'piece id: ' + p.id),
        h('div', '', 'waits for: ' + (deps.length ? deps.join(', ') : 'nothing')),
        h('div', '', 'name in the log: ' + str(p.tech_name, '(none)')));
    el.dbody.appendChild(tech);
    if (!calls.length) {
      el.dbody.appendChild(h('div', 'fx2-sec', 'Nobody has started on this piece yet.'));
      var names = arr(p.waits_for_names);
      if (!names.length && deps.length) names = [];
      if (names.length) el.dbody.appendChild(plain(h('div', 'fx2-mean', 'It starts after: ' + names.join(', ') + '.')));
    } else {
      el.dbody.appendChild(h('div', 'fx2-sec', 'What happened, in order'));
      calls.forEach(function (c) { el.dbody.appendChild(callBlock(c)); });
    }
  }

  function fillActivityDrawer() {
    el.drawer.removeAttribute('data-piece');
    add(el.dhead, h('h2', '', 'Activity'),
        plain(h('div', 'fx2-pur', 'The latest things that happened in this build.')));
    var list = arr(obj(st.board).recent).slice(0, 15);
    el.dbody.appendChild(h('div', 'fx2-sec', ''));
    list.forEach(function (r) {
      var row = fx(h('div', 'fx2-rec'), 'activity-line');
      var when = str(r && r.when_label, '') || clockOf(r && r.when);
      var body = h('div', 'fx2-rec-b');
      body.appendChild(plain(h('div', '', str(r && r.plain, 'Something happened in this build.'))));
      body.appendChild(techLine('raw: ' + str(r && r.text, '(empty)')));
      add(row, h('span', 'fx2-rec-t', when), body);
      el.dbody.appendChild(row);
    });
    if (!list.length) el.dbody.appendChild(h('div', 'fx2-none', 'Nothing has happened yet.'));
  }

  function renderDrawer() {
    if (!st.drawer) return;
    var key = JSON.stringify([st.drawer, st.drawer.kind === 'piece' ? findPiece(st.drawer.id) :
      arr(obj(st.board).recent).slice(0, 15)]);
    if (key === st.drawerKey) return;
    if (st.drawer.kind === 'piece' && !findPiece(st.drawer.id)) { closeDrawer(true); return; }
    st.drawerKey = key;
    clear(el.dhead);
    clear(el.dbody);
    if (st.drawer.kind === 'activity') fillActivityDrawer();
    else fillPieceDrawer(findPiece(st.drawer.id));
  }

  function openDrawer(kind, id) {
    buildDrawer();
    st.drawer = {kind: kind, id: id};
    st.drawerKey = '';
    renderDrawer();
    el.drawer.classList.toggle('fx2-showtech', st.tech);
    el.tech.checked = st.tech;
    el.drawer.setAttribute('aria-hidden', 'false');
    el.drawer.classList.add('fx2-open');
    el.scrim.classList.add('fx2-open');
    el.close.focus();
  }

  function closeDrawer(quiet) {
    if (!el.drawer) return;
    var was = st.drawer;
    st.drawer = null;
    st.drawerKey = '';
    el.drawer.setAttribute('aria-hidden', 'true');
    el.drawer.removeAttribute('data-piece');
    el.drawer.classList.remove('fx2-open');
    el.scrim.classList.remove('fx2-open');
    if (was && !quiet) focusOpener(was);
  }

  function focusOpener(was) {
    var target = null;
    if (was.kind === 'piece') {
      var cards = document.querySelectorAll('[data-fx="piece"]');
      for (var i = 0; i < cards.length; i++) if (cards[i].getAttribute('data-piece') === was.id) target = cards[i];
    } else {
      target = document.querySelector('[data-fx="activity"]');
    }
    if (target) target.focus();
  }

  /* ---------- rendering ---------- */
  function render(force) {
    if (!build()) return;
    el.emptyMsg.style.display = st.empty ? '' : 'none';
    el.data.style.display = st.board && !st.empty ? '' : 'none';
    if (st.board && !st.empty) {
      var b = st.board;
      var warns = arr(b.warnings);
      clear(el.warn);
      warns.forEach(function (w) { el.warn.appendChild(h('div', '', w)); });
      el.warn.style.display = warns.length ? '' : 'none';
      if (force || el.renderedKey !== st.boardKey) {
        el.renderedKey = st.boardKey;
        var active = document.activeElement, keep = null;
        if (active && active.getAttribute && active.getAttribute('data-fx') === 'piece' && el.data.contains(active)) {
          keep = active.getAttribute('data-piece');
        }
        var owner = obj(b.owner);
        var frag = document.createDocumentFragment();
        frag.appendChild(header());
        if (owner.needs_you === true && arr(owner.items).length) needsPanels(owner).forEach(function (n) { frag.appendChild(n); });
        else if (b.owner) frag.appendChild(calmPanel(owner));
        if (b.owner) frag.appendChild(statusBlock(owner));
        frag.appendChild(el.warn);
        frag.appendChild(planBlock(b));
        clear(el.data);
        el.data.appendChild(frag);
        if (keep !== null) {
          var cards = el.data.querySelectorAll('[data-fx="piece"]');
          for (var i = 0; i < cards.length; i++) if (cards[i].getAttribute('data-piece') === keep) cards[i].focus();
        }
        renderDrawer();
      }
    } else {
      el.warn.style.display = 'none';
    }
    footer();
    setTitle();
  }

  function setTitle() {
    var entry = (st.board && !st.empty) ? currentEntry() : null;
    var name = entry ? str(entry.title_plain, str(entry.title, st.selected)) :
      ((st.board && !st.empty) ? str(obj(obj(st.board).build).title, '') : '');
    document.title = name ? name + ' · factory' : 'factory';
  }

  function footer() {
    if (!el.foot) return;
    el.foot.style.display = st.board && !st.empty ? '' : 'none';
    if (!st.goodAt) { el.footAge.textContent = ''; return; }
    var s = Math.max(0, Math.round((Date.now() - st.goodAt) / 1000));
    el.footAge.textContent = 'Updated ' + s + ' s ago';
  }

  /* ---------- talking to the server ---------- */
  function good(p) {
    st.empty = !p.builds || !p.builds.length;
    st.builds = p.builds || [];
    st.selected = p.selected;
    st.board = p.board || null;
    st.boardKey = JSON.stringify([st.builds, st.selected, st.board]);
    st.goodAt = Date.now();
    setBanner('');
    setStale(false);
  }

  function schedule(ms) { st.nextAt = Date.now() + ms; }

  function load() {
    if (!build()) return;
    // A request that is still waiting when the next one is due is dropped, so a slow
    // answer never blocks the page from asking again.
    if (st.ctl) { try { st.ctl.abort(); } catch (e) { /* already done */ } }
    st.ctl = (typeof AbortController === 'function') ? new AbortController() : null;
    st.inflight = true;
    var mine = ++st.seq;
    schedule(st.board ? (running() ? FAST_MS : SLOW_MS) : RETRY_MS);
    var q = st.chosen ? '?build=' + encodeURIComponent(st.chosen) : '';
    var opts = {cache: 'no-store'};
    if (st.ctl) opts.signal = st.ctl.signal;
    fetch('/api/factory' + q, opts).then(function (r) {
      return r.json();
    }).then(function (p) {
      if (mine !== st.seq) return;
      if (p && p.ok === true) {
        good(p);
        schedule(running() ? FAST_MS : SLOW_MS);
      } else {
        setBanner(str(p && p.error, 'Something went wrong while loading this build.'));
        setStale(!!st.board);
        schedule(running() ? FAST_MS : SLOW_MS);
      }
      render(false);
    }).catch(function () {
      if (mine !== st.seq) return;
      setBanner("Can't reach the dashboard. Trying again.");
      setStale(!!st.board);
      schedule(RETRY_MS);
      render(false);
    }).then(function () {
      if (mine === st.seq) st.inflight = false;
    });
  }

  function tick() {
    if (!visible()) return;
    footer();
    if (Date.now() >= st.nextAt) load();
  }

  function wake() {
    if (!visible()) {
      closeDrawer(true);
      return;
    }
    build();
    render(false);
    if (Date.now() >= st.nextAt) st.nextAt = 0;
    tick();
  }

  function onKey(ev) {
    if (ev.key !== 'Escape' || !visible()) return;
    if (st.drawer) { closeDrawer(false); return; }
    if (st.legendOpen) {
      var lg = el.data && el.data.querySelector('[data-fx="legend"]');
      st.legendOpen = false;
      if (lg) lg.open = false;
      return;
    }
    if (st.menuOpen) {
      var btn = el.data && el.data.querySelector('[data-fx="picker"]');
      setMenu(false);
      if (btn) btn.focus();
    }
  }

  function onClick(ev) {
    if (!visible()) return;
    var t = ev.target;
    if (st.menuOpen && !(t.closest && t.closest('.fx2-picker'))) setMenu(false);
    if (st.legendOpen && !(t.closest && t.closest('.fx2-legend'))) {
      var lg = el.data && el.data.querySelector('[data-fx="legend"]');
      st.legendOpen = false;
      if (lg) lg.open = false;
    }
  }

  function buildFromUrl() {
    try {
      var q = new URLSearchParams(location.search).get('build');
      if (q && validBuild(q)) st.chosen = q;
    } catch (e) { /* no URL state: follow the most recent build */ }
  }

  function start() {
    if (!build()) return;
    buildFromUrl();
    document.addEventListener('visibilitychange', wake);
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', onClick);
    load();
    setInterval(tick, 500);
  }

  /* ---------- intro (dashboard only) ---------- */
  var INTRO_OUT_MS = 1150, INTRO_END_MS = 1500, INTRO_MAX_MS = 2000, INTRO_SKIP_MS = 150;
  var INTRO_SHEEN_MS = 500;
  var INTRO_KEY = 'factory-intro';

  /* Plays once per browser tab: the word, one line under it, then the page fades in.
     Decoration only: any failure removes the overlay and shows the page. */
  function intro() {
    var over = null, view = null, mark = null, timers = [], ended = false, skipped = false;

    function later(fn, ms) { timers.push(setTimeout(fn, ms)); }

    function lock(on) {
      [view, mark].forEach(function (n) {
        if (!n) return;
        if (on) { n.setAttribute('inert', ''); n.setAttribute('aria-hidden', 'true'); }
        else { n.removeAttribute('inert'); n.removeAttribute('aria-hidden'); }
      });
    }

    function reveal() { if (view) view.classList.remove('fd-pre'); }

    function finish() {
      if (ended) return;
      ended = true;
      timers.forEach(function (t) { clearTimeout(t); });
      timers = [];
      document.removeEventListener('keydown', onIntroKey, true);
      if (over) {
        over.removeEventListener('pointerdown', skip);
        over.removeEventListener('click', skip);
        if (over.parentNode) over.parentNode.removeChild(over);
      }
      reveal();
      lock(false);
    }

    function skip(ev) {
      if (ev && ev.stopPropagation) ev.stopPropagation();
      if (ended || skipped) return;
      skipped = true;
      timers.forEach(function (t) { clearTimeout(t); });
      timers = [];
      if (over) over.classList.add('fd-skip');
      reveal();
      later(finish, INTRO_SKIP_MS);
    }

    function onIntroKey(ev) {
      if (ended) return;
      ev.preventDefault();
      ev.stopPropagation();
      skip();
    }

    try {
      if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
      var seen = false;
      try { seen = window.sessionStorage.getItem(INTRO_KEY) === 'seen'; } catch (e) { seen = false; }
      if (seen) return;
      try { window.sessionStorage.setItem(INTRO_KEY, 'seen'); } catch (e) { /* not remembered */ }

      view = document.getElementById(VIEW_ID);
      mark = document.querySelector('[data-fx="watermark"]');
      over = fx(h('div', 'fd-intro'), 'intro');
      over.id = 'fd-intro';
      attr(over, 'aria-hidden', 'true');
      var word = fx(h('div', 'fd-intro-word'), 'intro-word');
      'factory'.split('').forEach(function (ch) { word.appendChild(h('span', 'fd-intro-l', ch)); });
      var by = fx(h('div', 'fd-intro-by', 'by Nayan Kanaparthi'), 'intro-by');
      add(over, word, by);
      if (view) { view.classList.add('fd-pre'); }
      lock(true);
      document.body.insertBefore(over, document.body.firstChild);

      /* Each letter learns where it sits in the word, so one light can cross all of them together. */
      var width = word.offsetWidth;
      var letters = word.childNodes;
      for (var i = 0; i < letters.length; i++) {
        letters[i].style.setProperty('--fd-lx', letters[i].offsetLeft + 'px');
        letters[i].style.setProperty('--fd-ww', width + 'px');
      }

      over.addEventListener('pointerdown', skip);
      over.addEventListener('click', skip);
      document.addEventListener('keydown', onIntroKey, true);

      later(function () { if (over) over.classList.add('fd-sheen'); }, INTRO_SHEEN_MS);
      later(function () { if (over) over.classList.add('fd-out'); reveal(); }, INTRO_OUT_MS);
      later(finish, INTRO_END_MS);
      later(finish, INTRO_MAX_MS);
    } catch (e) {
      finish();
    }
  }
  intro();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
