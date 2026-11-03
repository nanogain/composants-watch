/* Règles de compatibilité déterministes du configurateur (navigateur + Node). */
"use strict";
(function (root) {
  const SLOTS = ["cpu", "mb", "ram", "gpu", "ssd", "psu", "case", "cool", "mon", "kbd"];
  const REQUIRED = ["cpu", "mb", "ram", "ssd", "psu", "case"];
  const FORM_RANK = { ITX: 1, mATX: 2, ATX: 3 };
  const BASE_W = 100;
  const MARGIN = 1.2;

  const a = (item) => (item && item.attrs) || {};
  const known = (v) => v !== undefined && v !== null;

  function rules(sel) {
    const out = [];
    const { cpu, mb, ram, gpu, psu, cool } = sel;
    const kase = sel.case;
    if (cpu && mb) {
      const x = a(cpu).socket, y = a(mb).socket;
      out.push(!known(x) || !known(y)
        ? { rule: "socket", status: "unknown", message: "Socket du processeur ou de la carte mère inconnu : à vérifier." }
        : x === y
          ? { rule: "socket", status: "ok", message: "Processeur et carte mère : socket " + x + "." }
          : { rule: "socket", status: "ko", message: "Processeur " + x + " incompatible avec une carte mère " + y + "." });
    }
    if (ram && mb) {
      const x = a(ram).ddr, y = a(mb).ddr;
      out.push(!known(x) || !known(y)
        ? { rule: "ddr", status: "unknown", message: "Type de mémoire supporté par la carte mère inconnu (DDR4 ou DDR5) : à vérifier." }
        : x === y
          ? { rule: "ddr", status: "ok", message: "Mémoire DDR" + x + " supportée par la carte mère." }
          : { rule: "ddr", status: "ko", message: "Mémoire DDR" + x + " sur une carte mère DDR" + y + "." });
    }
    if (mb && kase) {
      const x = a(mb).form, y = a(kase).max_form;
      out.push(!known(x) || !known(y)
        ? { rule: "form", status: "unknown", message: "Format de la carte mère ou du boîtier inconnu : à vérifier." }
        : FORM_RANK[x] <= FORM_RANK[y]
          ? { rule: "form", status: "ok", message: "Carte mère " + x + " dans un boîtier " + y + "." }
          : { rule: "form", status: "ko", message: "Carte mère " + x + " trop grande pour un boîtier " + y + "." });
    }
    if (cool && cpu) {
      const s = a(cool).sockets, x = a(cpu).socket;
      out.push(!known(s) || !known(x)
        ? { rule: "cooler", status: "unknown", message: "Sockets supportés par le ventirad non indiqués : à vérifier." }
        : s.includes(x)
          ? { rule: "cooler", status: "ok", message: "Ventirad compatible " + x + "." }
          : { rule: "cooler", status: "ko", message: "Ventirad sans support " + x + " (supporte " + s.join(", ") + ")." });
    }
    if (cpu && !gpu && a(cpu).igpu === false) {
      out.push({ rule: "display", status: "ko", message: "Processeur sans graphique intégré et aucune carte graphique : pas d'affichage." });
    }
    return out;
  }

  function power(sel) {
    const { cpu, gpu, psu } = sel;
    if (!psu || !cpu) return { check: null, power: null };
    const c = a(cpu).tdp_w, g = gpu ? a(gpu).tdp_w : 0, w = a(psu).watts;
    if (!known(c) || !known(g) || !known(w)) {
      return { check: { rule: "power", status: "unknown", message: "Consommation du processeur ou de la carte graphique inconnue : à vérifier." }, power: null };
    }
    const need = c + g + BASE_W;
    const rec = Math.ceil((need * MARGIN) / 50) * 50;
    const p = { need_w: need, recommended_w: rec, psu_w: w };
    let check;
    if (w < need) check = { rule: "power", status: "ko", message: "Alimentation " + w + " W insuffisante : besoin estimé ≈ " + need + " W." };
    else if (w < need * MARGIN) check = { rule: "power", status: "warn", message: "Alimentation " + w + " W juste : " + rec + " W conseillés (besoin ≈ " + need + " W)." };
    else check = { rule: "power", status: "ok", message: "Alimentation " + w + " W suffisante (besoin estimé ≈ " + need + " W)." };
    return { check, power: p };
  }

  function evaluate(selection) {
    const sel = selection || {};
    const checks = rules(sel);
    const pw = power(sel);
    if (pw.check) checks.push(pw.check);
    const missing = REQUIRED.filter((s) => !sel[s]);
    if (sel.cpu && a(sel.cpu).igpu === false && !sel.gpu) missing.push("gpu");
    return { checks, missing, power: pw.power };
  }

  function compatibleWith(item, slot, selection) {
    const sel = Object.assign({}, selection, { [slot]: item });
    return !evaluate(sel).checks.some((c) => c.status === "ko" && c.rule !== "display");
  }

  const api = { SLOTS, REQUIRED, evaluate, compatibleWith };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Compat = api;
})(typeof window !== "undefined" ? window : this);
