/* Recherche déterministe dans le catalogue (navigateur + Node). */
"use strict";
(function (root) {
  const LIMIT = 200;

  function normalizeText(s) {
    return String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
      .replace(/[^a-z0-9]+/g, " ").trim();
  }

  function matches(item, words) {
    const hay = " " + normalizeText((item.title || "") + " " + (item.model || "")) + " ";
    return words.every((w) => hay.includes(w));
  }

  function filterItems(items, q) {
    q = q || {};
    const words = normalizeText(q.text).split(" ").filter(Boolean);
    const max = q.maxPrice === "" || q.maxPrice == null ? null : Number(q.maxPrice);
    const all = items.filter((i) => (!q.category || i.category === q.category) &&
      (!q.condition || i.condition === q.condition) && (!q.source || i.source === q.source) &&
      (max == null || isNaN(max) || i.effective_eur <= max) && matches(i, words));
    all.sort((a, b) => a.effective_eur - b.effective_eur || String(a.title).localeCompare(String(b.title), "fr"));
    return { total: all.length, rows: all.slice(0, LIMIT) };
  }

  const api = { LIMIT, normalizeText, matches, filterItems };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Search = api;
})(typeof window !== "undefined" ? window : this);
