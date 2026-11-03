"use strict";
(function () {
  const CAT = { GPU: "Carte graphique", CPU: "Processeur", RAM: "Mémoire", SSD: "SSD", MB: "Carte mère", PSU: "Alimentation",
    COOL: "Ventirad", CASE: "Boîtier", MON: "Écran", KBD: "Clavier" };
  const SRC = { dealabs: "Dealabs", reddit: "Reddit", ebay: "eBay" };
  const STATUS = { ok: "OK", down: "en panne", disabled: "désactivée" };
  const eur = (v) => (v == null ? "—" : v.toLocaleString("fr-FR", { style: "currency", currency: "EUR" }));
  let data = null, sortKey = null, sortAsc = false;

  function el(tag, attrs, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") n.className = v; else n.setAttribute(k, v);
    }
    for (const c of children) if (c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
    return n;
  }
  function link(url, text) {
    const safe = /^https:\/\//.test(url || "") ? url : "#";
    return el("a", { href: safe, target: "_blank", rel: "noopener noreferrer" }, text);
  }
  function age(iso) {
    const h = (Date.now() - new Date(iso).getTime()) / 36e5;
    if (!isFinite(h)) return "—";
    if (h < 1) return "< 1 h";
    if (h < 48) return Math.round(h) + " h";
    return Math.round(h / 24) + " j";
  }

  function renderHeader() {
    const d = new Date(data.generated_at);
    const n = data.stats.listings_seen, r = data.stats.models_with_reference;
    document.getElementById("meta").textContent =
      "Données modifiées le " + d.toLocaleString("fr-FR") + " · " + n + " annonces récentes · " + r + " modèles avec prix de référence";
    const ul = document.getElementById("sources");
    ul.replaceChildren();
    for (const [name, s] of Object.entries(data.sources)) {
      ul.append(el("li", { class: "st-" + s.status }, (SRC[name] || name) + " : " + (STATUS[s.status] || s.status) +
        (s.status === "ok" ? " (" + s.items + ")" : "")));
    }
  }

  function renderWatchlist() {
    const box = document.getElementById("watchlist");
    box.replaceChildren();
    if (!data.watchlist.length) { box.append(el("p", { class: "empty" }, "Aucun composant suivi (voir watchlist.json).")); return; }
    for (const w of data.watchlist) {
      const card = el("div", { class: "card" + (w.target_hit ? " hit" : "") });
      const h = el("h3", {}, w.label);
      if (w.target_hit) h.append(el("span", { class: "badge hit" }, "cible atteinte"));
      if (w.never_seen) h.append(el("span", { class: "badge warn" }, "modèle jamais vu"));
      card.append(h,
        el("div", { class: "row" }, el("span", {}, "Meilleur prix"),
          w.best ? link(w.best.url, eur(w.best.price_eur)) : el("span", {}, "—")),
        el("div", { class: "row" }, el("span", {}, "Ma cible"), el("span", {}, eur(w.target_eur))),
        el("div", { class: "row" }, el("span", {}, "Médiane 30 j"), el("span", {}, eur(w.median_30d))));
      if (w.best) card.append(el("div", { class: "row" }, el("span", {}, "Chez"), el("span", {}, w.best.merchant || SRC[w.best.source] || w.best.source)));
      box.append(card);
    }
  }

  function renderOpps() {
    const cat = document.getElementById("f-cat").value, cond = document.getElementById("f-cond").value;
    let rows = data.opportunities.filter((o) => (!cat || o.category === cat) && (!cond || o.condition === cond));
    if (sortKey) {
      rows = rows.slice().sort((a, b) => {
        const x = a[sortKey], y = b[sortKey];
        if (x == null) return 1; if (y == null) return -1;
        return (x < y ? -1 : x > y ? 1 : 0) * (sortAsc ? 1 : -1);
      });
    }
    const tb = document.querySelector("#opps tbody");
    tb.replaceChildren();
    for (const o of rows) {
      const title = el("td", {}, link(o.url, o.title));
      const tags = el("div", {}, (CAT[o.category] || "") + " · " + (o.condition === "used" ? "occasion" : "neuf"));
      if (o.target_hit) tags.append(el("span", { class: "badge hit" }, "cible atteinte"));
      if (o.suspect) tags.append(el("span", { class: "badge warn" }, "à vérifier"));
      title.append(tags);
      tb.append(el("tr", { class: (o.suspect ? "suspect " : "") + (o.target_hit ? "hit" : "") },
        el("td", { class: "num" }, o.discount_pct == null ? "—" : "−" + o.discount_pct.toLocaleString("fr-FR") + " %"),
        title,
        el("td", { class: "num" }, eur(o.effective_eur)),
        el("td", { class: "num" }, eur(o.median_eur)),
        el("td", {}, o.merchant || "—"),
        el("td", {}, SRC[o.source] || o.source),
        el("td", {}, age(o.posted_at))));
    }
    document.getElementById("opps-empty").hidden = rows.length > 0;
  }

  function renderUnclassified() {
    const ul = document.getElementById("unclassified");
    ul.replaceChildren();
    for (const u of data.unclassified) {
      ul.append(el("li", {}, link(u.url, u.title), " — " + (u.price_raw || "prix ?") + " · " + (SRC[u.source] || u.source) + " · " + age(u.posted_at)));
    }
    if (!data.unclassified.length) ul.append(el("li", { class: "empty" }, "Rien pour le moment."));
  }

  function bind() {
    document.getElementById("f-cat").addEventListener("change", renderOpps);
    document.getElementById("f-cond").addEventListener("change", renderOpps);
    for (const th of document.querySelectorAll("#opps th")) {
      th.addEventListener("click", () => {
        const k = th.dataset.key;
        sortAsc = sortKey === k ? !sortAsc : k === "effective_eur" || k === "title";
        sortKey = k;
        for (const o of document.querySelectorAll("#opps th")) o.classList.remove("sorted", "asc");
        th.classList.add("sorted"); if (sortAsc) th.classList.add("asc");
        renderOpps();
      });
    }
  }

  fetch("data/deals.json", { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((d) => { data = d; renderHeader(); renderWatchlist(); renderOpps(); renderUnclassified(); bind(); })
    .catch((e) => { document.getElementById("meta").textContent = "Données indisponibles (" + e.message + ")."; });
})();
