/* Onglets + configurateur. Dépend de compat.js (window.Compat) et advisor.js (window.Advisor). Texte inséré uniquement via textContent. */
"use strict";
(function () {
  const C = window.Compat;
  const AI = window.Advisor;
  const KEY = "cw-config-v1";
  const SLOT_INFO = {
    cpu: ["Processeur", "CPU"], mb: ["Carte mère", "MB"], ram: ["Mémoire", "RAM"], gpu: ["Carte graphique", "GPU"],
    ssd: ["Stockage", "SSD"], psu: ["Alimentation", "PSU"], case: ["Boîtier", "CASE"], cool: ["Ventirad", "COOL"],
    mon: ["Écran (option)", "MON"], kbd: ["Clavier (option)", "KBD"],
  };
  const ICON = { ok: "✅", ko: "❌", unknown: "❔", warn: "⚠️" };
  const eur = (v) => (v == null ? "—" : Number(v).toLocaleString("fr-FR", { style: "currency", currency: "EUR" }));

  let catalog = null, loading = false;
  const byId = new Map();
  const bySlot = {};
  let selection = {};   // slot -> item du catalogue
  let stale = {};       // slot -> {id, title, effective_eur} absent du catalogue
  const query = {};     // slot -> texte de recherche

  function el(tag, attrs, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") n.className = v; else n.setAttribute(k, v);
    }
    for (const c of children) if (c != null) n.append(c);
    return n;
  }
  function link(url, text) {
    return el("a", { href: /^https:\/\//.test(url || "") ? url : "#", target: "_blank", rel: "noopener noreferrer" }, text);
  }
  const label = (it) => (it.model ? it.model.split(":").slice(1).join(":") : it.title).slice(0, 60);

  // ── persistance ──────────────────────────────────────────────────────────
  function readSaved() {
    try {
      const raw = JSON.parse(localStorage.getItem(KEY) || "{}");
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
      const out = {};
      for (const [slot, v] of Object.entries(raw)) {
        if (SLOT_INFO[slot] && v && typeof v.id === "string") out[slot] = v;
      }
      return out;
    } catch (e) { return {}; }
  }
  function save() {
    const out = {};
    for (const [slot, it] of Object.entries(selection)) out[slot] = { id: it.id, title: it.title, effective_eur: it.effective_eur };
    for (const [slot, v] of Object.entries(stale)) out[slot] = v;
    try { localStorage.setItem(KEY, JSON.stringify(out)); } catch (e) { /* stockage plein ou interdit */ }
  }

  // ── listes de choix ──────────────────────────────────────────────────────
  function optionsFor(slot) {
    const q = (query[slot] || "").toLowerCase();
    const items = (bySlot[slot] || []).filter((it) => !q || (it.title + " " + (it.model || "")).toLowerCase().includes(q));
    const others = Object.assign({}, selection); delete others[slot];
    const scored = items.map((it) => ({ it, ok: C.compatibleWith(it, slot, others) }));
    scored.sort((a, b) => (b.ok - a.ok) || (b.it.deal - a.it.deal) || (a.it.effective_eur - b.it.effective_eur));
    return scored;
  }

  function renderRow(slot) {
    const [name] = SLOT_INFO[slot];
    const row = el("div", { class: "cfg-row", "data-slot": slot });
    row.append(el("label", { class: "cfg-label" }, name));
    if (stale[slot]) {
      const s = stale[slot];
      const btn = el("button", { class: "cfg-replace", type: "button" }, "Remplacer");
      btn.addEventListener("click", () => { delete stale[slot]; save(); render(); });
      row.append(el("div", { class: "cfg-stale" }, "Annonce disparue : " + s.title + " (" + eur(s.effective_eur) + ", ancien prix) ", btn));
      return row;
    }
    const search = el("input", { class: "cfg-search", type: "search", placeholder: "Rechercher…", "data-slot": slot });
    search.value = query[slot] || "";
    search.addEventListener("input", () => { query[slot] = search.value; fillSelect(select, slot); });
    const select = el("select", { class: "cfg-select", "data-slot": slot });
    fillSelect(select, slot);
    select.addEventListener("change", () => {
      const it = byId.get(select.value);
      if (it) selection[slot] = it; else delete selection[slot];
      save(); render();
    });
    row.append(el("div", { class: "cfg-controls" }, search, select));
    if (selection[slot]) row.append(link(selection[slot].url, "Voir l'annonce"));
    return row;
  }

  function fillSelect(select, slot) {
    const cur = selection[slot] ? selection[slot].id : "";
    select.replaceChildren(el("option", { value: "" }, "— choisir —"));
    for (const { it, ok } of optionsFor(slot)) {
      const prefix = (ok ? "" : "❌ ") + (it.deal && it.discount_pct != null ? "★ −" + it.discount_pct.toLocaleString("fr-FR") + " % · " : "");
      select.append(el("option", { value: it.id }, prefix + label(it) + " · " + eur(it.effective_eur) + " · " + (it.merchant || it.source)));
    }
    if (cur && selection[slot] && !optionsFor(slot).some((o) => o.it.id === cur)) {
      select.append(el("option", { value: cur }, label(selection[slot]) + " · " + eur(selection[slot].effective_eur)));
    }
    select.value = cur;
  }

  // ── récapitulatif ────────────────────────────────────────────────────────
  function renderRecap() {
    const box = document.getElementById("cfg-recap");
    const items = Object.values(selection);
    const total = items.reduce((s, it) => s + it.effective_eur, 0);
    const saving = items.reduce((s, it) => s + (it.median_eur != null ? it.median_eur - it.effective_eur : 0), 0);
    const r = C.evaluate(selection);
    const checks = el("ul", { id: "cfg-checks", class: "plain" });
    for (const c of r.checks) checks.append(el("li", { "data-rule": c.rule, "data-status": c.status }, ICON[c.status] + " " + c.message));
    if (!r.checks.length) checks.append(el("li", { class: "empty" }, "Choisis des pièces pour voir les contrôles de compatibilité."));
    const missing = r.missing.length
      ? "Il manque : " + r.missing.map((s) => SLOT_INFO[s][0].toLowerCase()).join(", ") + "."
      : "Configuration complète.";
    const pw = r.power
      ? "Puissance : besoin ≈ " + r.power.need_w + " W, " + r.power.recommended_w + " W conseillés, alimentation " + r.power.psu_w + " W."
      : "Puissance : choisis un processeur et une alimentation.";
    const clear = el("button", { id: "cfg-clear", type: "button" }, "Vider la configuration");
    clear.addEventListener("click", () => { selection = {}; stale = {}; save(); render(); });
    const copy = el("button", { id: "cfg-copy", type: "button" }, "Copier la liste");
    const copied = el("span", { class: "sub" });
    copy.addEventListener("click", () => {
      const lines = Object.entries(selection).map(([s, it]) => SLOT_INFO[s][0] + " : " + it.title + " — " + eur(it.effective_eur) + " — " + it.url);
      lines.push("Total : " + eur(total));
      const done = () => { copied.textContent = " Copié."; };
      try { navigator.clipboard.writeText(lines.join("\n")).then(done, () => { copied.textContent = " Copie impossible."; }); }
      catch (e) { copied.textContent = " Copie impossible."; }
    });
    box.replaceChildren(
      el("h2", {}, "Récapitulatif"),
      el("p", { class: "cfg-total" }, "Total : ", el("strong", { id: "cfg-total" }, eur(total))),
      el("p", { id: "cfg-saving", class: "sub" }, saving > 0 ? "Économie vs prix médians : " + eur(saving) : ""),
      checks,
      el("p", { id: "cfg-missing" }, missing),
      el("p", { id: "cfg-power", class: "sub" }, pw),
      el("p", { class: "sub" }, "Vérifie la longueur de la carte graphique et la hauteur du ventirad sur la fiche du produit."),
      el("div", { class: "cfg-buttons" }, clear, copy, copied));
  }

  function render() {
    const slots = document.getElementById("cfg-slots");
    slots.replaceChildren(...C.SLOTS.map(renderRow));
    renderRecap();
  }

  // ── chargement ───────────────────────────────────────────────────────────
  function loadCatalog() {
    if (catalog || loading) return;
    loading = true;
    const msg = document.getElementById("cfg-msg");
    msg.textContent = "Chargement du catalogue…";
    fetch("data/catalog.json", { cache: "no-store" })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then((data) => {
        catalog = data;
        const catSlot = {};
        for (const [slot, [, cat]] of Object.entries(SLOT_INFO)) { catSlot[cat] = slot; bySlot[slot] = []; }
        for (const it of data.items || []) {
          const slot = catSlot[it.category];
          if (!slot || typeof it.effective_eur !== "number") continue;
          byId.set(it.id, it); bySlot[slot].push(it);
        }
        for (const [slot, v] of Object.entries(readSaved())) {
          const it = byId.get(v.id);
          if (it && bySlot[slot].includes(it)) selection[slot] = it; else stale[slot] = v;
        }
        msg.textContent = (data.items || []).length + " annonces disponibles · catalogue du " + new Date(data.generated_at).toLocaleString("fr-FR");
        render();
        const go = document.getElementById("ai-go");
        if (go) go.disabled = false;
      })
      .catch((e) => { loading = false; msg.textContent = "Catalogue indisponible (" + e.message + "). Il sera publié au prochain passage du Pi."; });
  }

  // ── conseiller IA ────────────────────────────────────────────────────────
  const AI_KEY = "cw-ai-key", AI_PREFS = "cw-ai-prefs";
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* stockage plein ou interdit */ } },
    del: (k) => { try { localStorage.removeItem(k); } catch (e) { /* idem */ } },
  };

  function renderProposal(box, r) {
    const list = el("ul", { class: "ai-picks" });
    for (const slot of Object.keys(AI.TOWER_SLOTS)) {
      const it = r.selection[slot];
      list.append(it
        ? el("li", {}, SLOT_INFO[slot][0] + " : " + label(it) + " · " + eur(it.effective_eur) + " · ", link(it.url, "Voir l'annonce"))
        : el("li", {}, SLOT_INFO[slot][0] + " : —"));
    }
    const checks = el("ul", { class: "plain" });
    for (const c of C.evaluate(r.selection).checks) checks.append(el("li", { "data-status": c.status }, ICON[c.status] + " " + c.message));
    const apply = el("button", { id: "ai-apply", type: "button" }, "Appliquer");
    apply.addEventListener("click", () => {
      for (const slot of Object.keys(AI.TOWER_SLOTS)) {
        delete stale[slot];
        if (r.selection[slot]) selection[slot] = r.selection[slot]; else delete selection[slot];
      }
      save(); render(); box.replaceChildren();
    });
    const dismiss = el("button", { id: "ai-dismiss", type: "button" }, "Ignorer");
    dismiss.addEventListener("click", () => box.replaceChildren());
    box.replaceChildren(
      r.problems.length ? el("p", { class: "ai-warn" }, "⚠️ Proposition non conforme : " + r.problems.join(" ; ")) : "",
      list,
      el("p", { class: "cfg-total" }, "Total : ", el("strong", {}, eur(r.total))),
      checks,
      el("p", { class: "sub" }, r.rationale || ""),
      el("div", { class: "cfg-buttons" }, apply, dismiss));
  }

  function bindAi() {
    const go = document.getElementById("ai-go");
    if (!go || !AI) return;
    const budget = document.getElementById("ai-budget"), usage = document.getElementById("ai-usage");
    const model = document.getElementById("ai-model"), cost = document.getElementById("ai-cost");
    const keyInput = document.getElementById("ai-key"), status = document.getElementById("ai-status");
    const box = document.getElementById("ai-result");
    for (const [code, name] of AI.USAGES) usage.append(el("option", { value: code }, name));
    usage.value = "game1440";
    for (const [id, name] of AI.MODELS) model.append(el("option", { value: id }, name));
    model.value = AI.MODEL;
    const showCost = () => { cost.textContent = (AI.MODELS.find((m) => m[0] === model.value) || AI.MODELS[0])[2]; };
    model.addEventListener("change", showCost);
    try {
      const p = JSON.parse(store.get(AI_PREFS) || "{}");
      if (p && Number(p.budget) > 0) budget.value = String(p.budget);
      if (p && AI.USAGES.some(([c]) => c === p.usage)) usage.value = p.usage;
      if (p && AI.MODELS.some(([m]) => m === p.model)) model.value = p.model;
    } catch (e) { /* préférences illisibles : valeurs par défaut */ }
    showCost();
    const keyHint = () => { keyInput.placeholder = store.get(AI_KEY) ? "clé enregistrée dans ce navigateur" : "sk-ant-…"; };
    keyHint();
    document.getElementById("ai-forget").addEventListener("click", () => { store.del(AI_KEY); keyHint(); status.textContent = "Clé oubliée."; });
    go.addEventListener("click", async () => {
      if (!catalog || go.dataset.busy === "1") return;
      const typed = (keyInput.value || "").trim();
      if (typed) { store.set(AI_KEY, typed); keyInput.value = ""; keyHint(); }
      const key = typed || store.get(AI_KEY);
      if (!key) { status.textContent = "Colle ta clé API Anthropic (console.anthropic.com)."; return; }
      const b = Number(budget.value);
      if (!(b > 0)) { status.textContent = "Indique un budget en euros."; return; }
      store.set(AI_PREFS, JSON.stringify({ budget: b, usage: usage.value, model: model.value }));
      go.disabled = true; go.dataset.busy = "1";
      status.textContent = "Génération… (≈ 30 s)";
      box.replaceChildren();
      try {
        const r = await AI.generate({ key, budget: b, usage: usage.value, items: catalog.items || [], catalogById: byId,
          Compat: C, fetch: (u, i) => fetch(u, i), model: model.value });
        if (r.error) { status.textContent = r.error; return; }
        status.textContent = r.attempts > 1 ? "Proposition corrigée après une seconde demande." : "";
        renderProposal(box, r);
      } finally { go.disabled = false; go.dataset.busy = ""; }
    });
  }
  bindAi();

  // ── onglets ──────────────────────────────────────────────────────────────
  function show(tab) {
    document.getElementById("tab-deals").hidden = tab !== "deals";
    document.getElementById("tab-config").hidden = tab !== "config";
    for (const b of document.querySelectorAll("button.tab")) b.classList.toggle("active", b.dataset.tab === tab);
    if (tab === "config") loadCatalog();
  }
  for (const b of document.querySelectorAll("button.tab")) {
    b.addEventListener("click", () => {
      location.hash = b.dataset.tab === "config" ? "#config" : "";
      show(b.dataset.tab);
    });
  }
  addEventListener("hashchange", () => show(location.hash === "#config" ? "config" : "deals"));
  show(location.hash === "#config" ? "config" : "deals");
})();
