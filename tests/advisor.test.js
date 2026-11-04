"use strict";
const assert = require("assert");
const path = require("path");
const fs = require("fs");
const A = require("../docs/advisor.js");
const Compat = require("../docs/compat.js");

const catalog = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures/catalog_demo.json"), "utf8"));
const items = catalog.items;
const byId = new Map(items.map((i) => [i.id, i]));
const GOOD = { cpu: "dealabs:2", mb: "dealabs:4", ram: "dealabs:6", gpu: "dealabs:7", ssd: "dealabs:8",
  psu: "dealabs:9", case: "dealabs:10", cool: "dealabs:11" };
const res = (picks) => ({ picks: { ...GOOD, ...picks }, rationale: "ok" });

const tests = [];
function t(name, fn) { tests.push([name, fn]); }

t("compact: tour seulement", () => {
  const lines = A.compactCatalog(items).split("\n");
  assert.strictEqual(lines.length, 11);
  const first = JSON.parse(lines[0]);
  assert.strictEqual(first[0], "dealabs:1");
  assert.strictEqual(first[1], "CPU");
  assert.strictEqual(first[4], 349);
  assert.strictEqual(first[5], "n");
  assert.deepStrictEqual(first[6], { socket: "AM5", tdp_w: 120, igpu: true });
  assert.ok([0, 1].includes(first[7]));
  const long = A.compactCatalog([{ ...items[0], title: "x".repeat(200) }]);
  assert.strictEqual(JSON.parse(long)[3].length, 70);
});
t("request: forme", () => {
  const r = A.buildRequest({ budget: 1000, usage: "game1440", items });
  assert.strictEqual(r.model, "claude-opus-5-5");
  assert.strictEqual(r.fallbacks, "default");
  assert.strictEqual(r.output_config.effort, "medium");
  assert.strictEqual(r.output_config.format.schema, A.SCHEMA);
  assert.strictEqual(r.messages.length, 1);
  assert.ok(r.messages[0].content.includes("1000 €"));
  assert.ok(r.messages[0].content.includes("Jeu 1440p"));
  assert.ok(r.messages[0].content.includes("dealabs:11"));
  assert.ok(!("thinking" in r) && !("temperature" in r));
});
t("request: 2e tentative", () => {
  const r = A.buildRequest({ budget: 1000, usage: "office", items, previous: res({}), problems: ["Budget dépassé"] });
  assert.deepStrictEqual(r.messages.map((m) => m.role), ["user", "assistant", "user"]);
  assert.ok(r.messages[2].content.includes("Budget dépassé"));
});
const reply = (text, stop = "end_turn") => ({ stop_reason: stop, content: [{ type: "thinking", thinking: "" }, { type: "text", text }] });
t("parse: ok", () => {
  const p = A.parseResponse(reply(JSON.stringify(res({}))));
  assert.strictEqual(p.picks.cpu, "dealabs:2");
  assert.strictEqual(p.rationale, "ok");
});
t("parse: refus", () => assert.deepStrictEqual(A.parseResponse({ stop_reason: "refusal", content: [] }), { error: "refusal" }));
t("parse: max_tokens", () => assert.deepStrictEqual(A.parseResponse(reply("{", "max_tokens")), { error: "incomplete" }));
t("parse: json illisible", () => {
  assert.deepStrictEqual(A.parseResponse(reply("pas du json")), { error: "incomplete" });
  assert.deepStrictEqual(A.parseResponse(reply('{"rationale":"x"}')), { error: "incomplete" });
  assert.deepStrictEqual(A.parseResponse({ stop_reason: "end_turn", content: [] }), { error: "incomplete" });
});
t("validate: conforme", () => {
  const v = A.validate(res({}), byId, 1500, Compat);
  assert.deepStrictEqual(v.problems, []);
  assert.strictEqual(v.total, 1284);
  assert.strictEqual(v.selection.cpu.id, "dealabs:2");
});
t("validate: id mal placé", () => {
  const v = A.validate(res({ cpu: "dealabs:12" }), byId, 5000, Compat);
  assert.ok(v.problems.some((p) => p.startsWith("Processeur : annonce inconnue ou mal placée")), v.problems);
  assert.ok(!v.selection.cpu);
});
t("validate: id inconnu", () => {
  const v = A.validate(res({ ssd: "x:1" }), byId, 5000, Compat);
  assert.ok(v.problems.some((p) => p.startsWith("Stockage")), v.problems);
});
t("validate: gpu null", () => {
  assert.deepStrictEqual(A.validate(res({ gpu: null }), byId, 5000, Compat).problems, []);
  const v = A.validate(res({ gpu: null, cpu: "dealabs:3", mb: "dealabs:5", ram: "dealabs:6" }), byId, 5000, Compat);
  assert.ok(v.problems.some((p) => p.includes("graphique")), v.problems);
});
t("validate: socket ko", () => {
  const v = A.validate(res({ cpu: "dealabs:3" }), byId, 5000, Compat);
  assert.ok(v.problems.some((p) => p.includes("incompatible")), v.problems);
});
t("validate: budget dépassé", () => {
  const v = A.validate(res({}), byId, 1000, Compat);
  assert.ok(v.problems.some((p) => p.includes("Budget dépassé")), v.problems);
});
t("validate: total recalculé", () => {
  const v = A.validate({ ...res({}), total: 1 }, byId, 1500, Compat);
  assert.strictEqual(v.total, 1284);
});

(async () => {
  for (const [name, fn] of tests) {
    try { await fn(); } catch (e) { console.error("ÉCHEC " + name + "\n" + (e.stack || e)); process.exit(1); }
  }
  console.log("advisor: all " + tests.length + " passed");
})();
