"use strict";
const assert = require("assert");
const Compat = require("../docs/compat.js");

const cpu = (a) => ({ category: "CPU", attrs: { socket: "AM5", tdp_w: 120, igpu: true, ...a } });
const mb = (a) => ({ category: "MB", attrs: { socket: "AM5", ddr: 5, form: "ATX", ...a } });
const ram = (ddr) => ({ category: "RAM", attrs: { ddr } });
const gpu = (tdp) => ({ category: "GPU", attrs: tdp == null ? {} : { tdp_w: tdp } });
const psu = (w) => ({ category: "PSU", attrs: { watts: w } });
const kase = (f) => ({ category: "CASE", attrs: f ? { max_form: f } : {} });
const cool = (s) => ({ category: "COOL", attrs: s ? { type: "air", sockets: s } : { type: "air" } });
const check = (sel, rule) => Compat.evaluate(sel).checks.find((c) => c.rule === rule);
let n = 0;
function t(name, fn) { fn(); n++; }

t("socket ok", () => assert.equal(check({ cpu: cpu(), mb: mb() }, "socket").status, "ok"));
t("socket ko", () => {
  const c = check({ cpu: cpu(), mb: mb({ socket: "AM4" }) }, "socket");
  assert.equal(c.status, "ko"); assert.ok(c.message.includes("AM5") && c.message.includes("AM4"));
});
t("socket unknown", () => assert.equal(check({ cpu: cpu(), mb: mb({ socket: undefined }) }, "socket").status, "unknown"));
t("ddr ok", () => assert.equal(check({ ram: ram(5), mb: mb() }, "ddr").status, "ok"));
t("ddr ko", () => assert.equal(check({ ram: ram(4), mb: mb() }, "ddr").status, "ko"));
t("ddr unknown", () => assert.equal(check({ ram: ram(5), mb: mb({ ddr: undefined }) }, "ddr").status, "unknown"));
t("form ok", () => assert.equal(check({ mb: mb({ form: "mATX" }), case: kase("ATX") }, "form").status, "ok"));
t("form ko", () => assert.equal(check({ mb: mb({ form: "ATX" }), case: kase("ITX") }, "form").status, "ko"));
t("form itx in matx", () => assert.equal(check({ mb: mb({ form: "ITX" }), case: kase("mATX") }, "form").status, "ok"));
t("form unknown", () => assert.equal(check({ mb: mb({ form: undefined }), case: kase("ATX") }, "form").status, "unknown"));
t("form unknown case", () => assert.equal(check({ mb: mb(), case: kase(null) }, "form").status, "unknown"));
t("cooler ok", () => assert.equal(check({ cpu: cpu(), cool: cool(["AM4", "AM5"]) }, "cooler").status, "ok"));
t("cooler ko", () => assert.equal(check({ cpu: cpu(), cool: cool(["LGA1700"]) }, "cooler").status, "ko"));
t("cooler unknown", () => assert.equal(check({ cpu: cpu(), cool: cool(null) }, "cooler").status, "unknown"));
t("power numbers", () => {
  const r = Compat.evaluate({ cpu: cpu(), gpu: gpu(220), psu: psu(750) });
  assert.deepEqual(r.power, { need_w: 440, recommended_w: 550, psu_w: 750 });
  assert.equal(r.checks.find((c) => c.rule === "power").status, "ok");
});
t("power warn", () => assert.equal(check({ cpu: cpu(), gpu: gpu(220), psu: psu(500) }, "power").status, "warn"));
t("power ko", () => assert.equal(check({ cpu: cpu(), gpu: gpu(220), psu: psu(400) }, "power").status, "ko"));
t("power unknown gpu", () => assert.equal(check({ cpu: cpu(), gpu: gpu(null), psu: psu(750) }, "power").status, "unknown"));
t("power unknown cpu", () => assert.equal(check({ cpu: cpu({ tdp_w: undefined }), psu: psu(750) }, "power").status, "unknown"));
t("power no gpu", () => assert.equal(Compat.evaluate({ cpu: cpu(), psu: psu(300) }).power.need_w, 220));
t("display ko", () => assert.equal(check({ cpu: cpu({ igpu: false }) }, "display").status, "ko"));
t("display with gpu", () => assert.equal(check({ cpu: cpu({ igpu: false }), gpu: gpu(200) }, "display"), undefined));
t("display igpu", () => assert.equal(check({ cpu: cpu() }, "display"), undefined));
t("missing empty", () => assert.deepEqual(Compat.evaluate({}).missing, ["cpu", "mb", "ram", "ssd", "psu", "case"]));
t("missing gpu required", () => assert.ok(Compat.evaluate({ cpu: cpu({ igpu: false }) }).missing.includes("gpu")));
t("missing gpu optional", () => assert.ok(!Compat.evaluate({ cpu: cpu() }).missing.includes("gpu")));
t("no check one side", () => assert.deepEqual(Compat.evaluate({ cpu: cpu(), psu: null }).checks.map((c) => c.rule), []));
t("power null without psu", () => assert.equal(Compat.evaluate({ cpu: cpu() }).power, null));
t("compatibleWith false", () => assert.equal(Compat.compatibleWith(mb({ socket: "AM4" }), "mb", { cpu: cpu() }), false));
t("compatibleWith true", () => assert.equal(Compat.compatibleWith(mb(), "mb", { cpu: cpu() }), true));
t("compatibleWith unknown", () => assert.equal(Compat.compatibleWith(mb({ socket: undefined }), "mb", { cpu: cpu() }), true));
t("compatibleWith replaces slot", () =>
  assert.equal(Compat.compatibleWith(cpu(), "cpu", { cpu: cpu({ socket: "AM4" }), mb: mb() }), true));
t("slots", () => assert.deepEqual(Compat.SLOTS, ["cpu", "mb", "ram", "gpu", "ssd", "psu", "case", "cool", "mon", "kbd"]));
console.log("compat: all " + n + " passed");
