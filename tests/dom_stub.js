"use strict";
// DOM minimal pour exécuter docs/compat.js + docs/config.js dans Node, sans dépendance.
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");

class El {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.parent = null; this.attrs = {};
    this._text = ""; this.hidden = false; this.value = ""; this.dataset = {}; this.listeners = {};
    const cls = new Set(); this._cls = cls;
    this.classList = { add: (...c) => c.forEach((x) => cls.add(x)), remove: (...c) => c.forEach((x) => cls.delete(x)),
      toggle: (c, on) => { (on ?? !cls.has(c)) ? cls.add(c) : cls.delete(c); }, contains: (c) => cls.has(c) };
  }
  set className(v) { this._cls.clear(); String(v).split(/\s+/).filter(Boolean).forEach((c) => this._cls.add(c)); }
  get className() { return [...this._cls].join(" "); }
  set id(v) { this.attrs.id = v; } get id() { return this.attrs.id; }
  setAttribute(k, v) { if (k === "class") this.className = v; else if (k.startsWith("data-")) this.dataset[k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] = String(v); else { this.attrs[k] = String(v); if (k === "value") this.value = String(v); } }
  getAttribute(k) { return this.attrs[k] ?? null; }
  append(...cs) { for (const c of cs) { const n = typeof c === "string" ? new Text(c) : c; n.parent = this; this.children.push(n); } }
  appendChild(c) { this.append(c); return c; }
  replaceChildren(...cs) { this.children = []; this.append(...cs); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this); }
  set textContent(v) { this.children = []; this._text = String(v); }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(""); }
  addEventListener(t, f) { (this.listeners[t] ||= []).push(f); }
  dispatch(t) { for (const f of this.listeners[t] || []) f({ target: this, preventDefault() {} }); }
  get options() { return this.children.filter((c) => c.tagName === "OPTION"); }
  walk(fn, out = []) { if (fn(this)) out.push(this); for (const c of this.children) if (c instanceof El) c.walk(fn, out); return out; }
  querySelectorAll(sel) {
    const m = sel.match(/^(\w+)?(?:\.([\w-]+))?(?:\[data-([\w-]+)(?:="([^"]*)")?\])?$/);
    if (!m) throw new Error("sélecteur non supporté : " + sel);
    const [, tag, cls, dk, dv] = m;
    const key = dk && dk.replace(/-(\w)/g, (_, c) => c.toUpperCase());
    return this.walk((e) => e !== this && (!tag || e.tagName === tag.toUpperCase()) && (!cls || e.classList.contains(cls))
      && (!key || (key in e.dataset && (dv === undefined || e.dataset[key] === dv))));
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
class Text { constructor(t) { this.text = t; } get textContent() { return this.text; } }

function makeEnv({ storage = {}, fetchImpl, hash = "#config" } = {}) {
  const body = new El("body");
  const mk = (tag, id, parent = body, cls) => { const e = new El(tag); if (id) e.id = id; if (cls) e.className = cls; parent.append(e); return e; };
  const nav = mk("nav", "tabs");
  for (const t of ["deals", "config"]) { const b = mk("button", null, nav, "tab"); b.setAttribute("data-tab", t); }
  const deals = mk("main", "tab-deals"); mk("p", "meta", deals);
  const cfg = mk("main", "tab-config"); cfg.hidden = true;
  mk("p", "cfg-msg", cfg); mk("div", "cfg-slots", cfg); mk("aside", "cfg-recap", cfg);
  const listeners = {};
  const store = { ...storage };
  const env = {
    document: { body, createElement: (t) => new El(t), createTextNode: (t) => new Text(t),
      getElementById: (id) => body.walk((e) => e.id === id)[0] || null,
      querySelectorAll: (s) => body.querySelectorAll(s), querySelector: (s) => body.querySelector(s) },
    location: { hash },
    localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; } },
    navigator: { clipboard: { writeText: (t) => { env.copied = t; return Promise.resolve(); } } },
    fetch: fetchImpl,
    addEventListener: (t, f) => { (listeners[t] ||= []).push(f); },
    store,
  };
  env.window = env;
  return env;
}

function load(env) {
  for (const k of ["document", "location", "localStorage", "navigator", "fetch", "window"]) {
    Object.defineProperty(global, k, { value: env[k], configurable: true, writable: true });
  }
  global.addEventListener = env.addEventListener;
  delete require.cache[require.resolve(path.join(ROOT, "docs/compat.js"))];
  global.window.Compat = require(path.join(ROOT, "docs/compat.js"));
  global.Compat = global.window.Compat;
  const src = fs.readFileSync(path.join(ROOT, "docs/config.js"), "utf8");
  new Function(src)();
}

const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures/catalog_demo.json"), "utf8"));
const okFetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(JSON.stringify(catalog))) });
const tick = () => new Promise((r) => setTimeout(r, 20));
const sel = (env, slot) => env.document.querySelector('select[data-slot="' + slot + '"]');
const choose = (env, slot, id) => { const s = sel(env, slot); s.value = id; s.dispatch("change"); };
const recap = (env) => ({
  total: env.document.getElementById("cfg-total").textContent,
  checks: env.document.querySelectorAll("li[data-rule]").map((l) => [l.dataset.rule, l.dataset.status]),
  missing: env.document.getElementById("cfg-missing").textContent,
});

const scenarios = {
  async render() {
    const env = makeEnv({ fetchImpl: okFetch }); load(env); await tick();
    const rows = env.document.querySelectorAll("div.cfg-row");
    const cpuOpts = sel(env, "cpu").options.map((o) => o.value);
    return { rows: rows.length, cpuOpts, ...recap(env), configHidden: env.document.getElementById("tab-config").hidden };
  },
  async select() {
    const env = makeEnv({ fetchImpl: okFetch }); load(env); await tick();
    choose(env, "cpu", "dealabs:1"); choose(env, "mb", "dealabs:5");
    const mbTexts = sel(env, "mb").options.map((o) => [o.value, o.textContent]);
    return { ...recap(env), mbTexts };
  },
  async full() {
    const env = makeEnv({ fetchImpl: okFetch }); load(env); await tick();
    for (const [s, id] of [["cpu", "dealabs:1"], ["mb", "dealabs:4"], ["ram", "dealabs:6"], ["gpu", "dealabs:7"],
      ["ssd", "dealabs:8"], ["psu", "dealabs:9"], ["case", "dealabs:10"], ["cool", "dealabs:11"]]) choose(env, s, id);
    env.document.getElementById("cfg-copy").dispatch("click"); await tick();
    return { ...recap(env), power: env.document.getElementById("cfg-power").textContent, copied: env.copied || "" };
  },
  async persist() {
    const env = makeEnv({ fetchImpl: okFetch }); load(env); await tick();
    choose(env, "cpu", "dealabs:2");
    const saved = env.store["cw-config-v1"];
    const env2 = makeEnv({ fetchImpl: okFetch, storage: env.store }); load(env2); await tick();
    return { saved: JSON.parse(saved), restored: sel(env2, "cpu").value, ...recap(env2) };
  },
  async stale() {
    const storage = { "cw-config-v1": JSON.stringify({ gpu: { id: "dealabs:999", title: "RTX 4070 Super disparue", effective_eur: 549 },
      cpu: { id: "dealabs:2", title: "x", effective_eur: 189 } }) };
    const env = makeEnv({ fetchImpl: okFetch, storage }); load(env); await tick();
    const staleRow = env.document.querySelector('div.cfg-row[data-slot="gpu"]').textContent;
    const btn = env.document.querySelector('button.cfg-replace');
    btn.dispatch("click");
    return { staleRow, ...recap(env), afterReplace: JSON.parse(env.store["cw-config-v1"]) };
  },
  async corrupt() {
    const env = makeEnv({ fetchImpl: okFetch, storage: { "cw-config-v1": "{not json" } }); load(env); await tick();
    return recap(env);
  },
  async catalog_missing() {
    const env = makeEnv({ fetchImpl: () => Promise.resolve({ ok: false, status: 404 }) }); load(env); await tick();
    const msg = env.document.getElementById("cfg-msg").textContent;
    env.document.querySelector('button[data-tab="deals"]').dispatch("click");
    return { msg, dealsHiddenAfterClick: env.document.getElementById("tab-deals").hidden };
  },
  async tabs() {
    const env = makeEnv({ fetchImpl: okFetch, hash: "" }); let calls = 0;
    env.fetch = () => { calls++; return okFetch(); }; load(env); await tick();
    const before = { calls, configHidden: env.document.getElementById("tab-config").hidden };
    env.document.querySelector('button[data-tab="config"]').dispatch("click"); await tick();
    return { before, after: { calls, hash: env.location.hash, configHidden: env.document.getElementById("tab-config").hidden,
      dealsHidden: env.document.getElementById("tab-deals").hidden } };
  },
  async search() {
    const env = makeEnv({ fetchImpl: okFetch }); load(env); await tick();
    const input = env.document.querySelector('input[data-slot="cpu"]');
    input.value = "5600"; input.dispatch("input");
    return { opts: sel(env, "cpu").options.map((o) => o.value) };
  },
  async all_search() {
    const env = makeEnv({ fetchImpl: (url) => (url === "data/catalog.json" ? okFetch() : Promise.resolve({ ok: false, status: 404 })) });
    const deals = env.document.getElementById("tab-deals");
    const add = (tag, id) => { const e = new El(tag); e.id = id; deals.append(e); return e; };
    for (const id of ["s-text", "s-max"]) add("input", id);
    for (const id of ["s-cat", "s-cond", "s-src"]) add("select", id);
    add("p", "s-count"); add("tbody", "all-body"); add("p", "all-empty");
    loadApp(env); await tick();
    const rowsAll = env.document.getElementById("all-body").children.length;
    const t = env.document.getElementById("s-text"); t.value = "ryzen"; t.dispatch("input");
    const body = env.document.getElementById("all-body");
    return { rowsAll, total: catalog.items.length, rows: body.children.length, count: env.document.getElementById("s-count").textContent,
      titles: body.children.map((r) => r.children[1].children[0].textContent), meta: env.document.getElementById("meta").textContent };
  },
};

function loadApp(env) {
  for (const k of ["document", "location", "localStorage", "navigator", "fetch", "window"]) {
    Object.defineProperty(global, k, { value: env[k], configurable: true, writable: true });
  }
  delete require.cache[require.resolve(path.join(ROOT, "docs/search.js"))];
  global.Search = require(path.join(ROOT, "docs/search.js"));
  global.Node = El;
  new Function(fs.readFileSync(path.join(ROOT, "docs/app.js"), "utf8"))();
}

(async () => {
  const name = process.argv[2];
  try { console.log(JSON.stringify(await scenarios[name]())); }
  catch (e) { console.error(e && e.stack || e); process.exit(1); }
})();
