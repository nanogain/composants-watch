"use strict";
const assert = require("assert");
const S = require("../docs/search.js");

const it = (title, o) => ({ title, model: null, category: "GPU", condition: "new", source: "dealabs",
  effective_eur: 100, ...o });
let n = 0;
function t(name, fn) { fn(); n++; }

t("normalize", () => {
  assert.strictEqual(S.normalizeText('Écran 27" QHD'), "ecran 27 qhd");
  assert.strictEqual(S.normalizeText(null), "");
});
t("accents et casse", () => assert.ok(S.matches(it("ÉCRAN Samsung"), ["ecran"])));
t("tous les mots", () => {
  assert.ok(S.matches(it("MSI RTX 4070 Super"), ["rtx", "4070"]));
  assert.ok(!S.matches(it("MSI RTX 4060"), ["rtx", "4070"]));
});
t("tiret", () => {
  const r = S.filterItems([it("RTX 4070 Super")], { text: "4070-super" });
  assert.strictEqual(r.total, 1);
});
t("modèle canonique", () => assert.ok(S.matches(it("Carte MSI Ventus", { model: "GPU:RTX 4070 Super" }), ["super"])));
t("texte vide renvoie tout", () => assert.strictEqual(S.filterItems([it("a"), it("b")], { text: "  " }).total, 2));
t("filtres", () => {
  const items = [it("a", { category: "CPU" }), it("b", { condition: "used" }), it("c", { source: "ebay" }),
    it("d", { effective_eur: 150 }), it("e", { effective_eur: 150.01 })];
  assert.deepStrictEqual(S.filterItems(items, { category: "CPU" }).rows.map((x) => x.title), ["a"]);
  assert.deepStrictEqual(S.filterItems(items, { condition: "used" }).rows.map((x) => x.title), ["b"]);
  assert.deepStrictEqual(S.filterItems(items, { source: "ebay" }).rows.map((x) => x.title), ["c"]);
  assert.strictEqual(S.filterItems(items, { maxPrice: 150 }).total, 4);
  assert.strictEqual(S.filterItems(items, { maxPrice: "" }).total, 5);
});
t("tri par prix puis titre", () => {
  const r = S.filterItems([it("z", { effective_eur: 50 }), it("b", { effective_eur: 10 }), it("a", { effective_eur: 50 })], {});
  assert.deepStrictEqual(r.rows.map((x) => x.title), ["b", "a", "z"]);
});
t("plafond", () => {
  const many = Array.from({ length: 250 }, (_, i) => it("x" + i, { effective_eur: i }));
  const r = S.filterItems(many, {});
  assert.strictEqual(r.total, 250);
  assert.strictEqual(r.rows.length, S.LIMIT);
  assert.strictEqual(S.LIMIT, 200);
});
t("entrée ne modifie pas la liste", () => {
  const items = [it("b", { effective_eur: 2 }), it("a", { effective_eur: 1 })];
  S.filterItems(items, {});
  assert.strictEqual(items[0].title, "b");
});
console.log("search: all " + n + " passed");
