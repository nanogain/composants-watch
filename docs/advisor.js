/* Conseiller IA du configurateur : requête à l'API Anthropic et revérification (navigateur + Node). */
"use strict";
(function (root) {
  const TOWER_SLOTS = { cpu: "CPU", mb: "MB", ram: "RAM", gpu: "GPU", ssd: "SSD", psu: "PSU", case: "CASE", cool: "COOL" };
  const SLOT_LABEL = { cpu: "Processeur", mb: "Carte mère", ram: "Mémoire", gpu: "Carte graphique", ssd: "Stockage",
    psu: "Alimentation", case: "Boîtier", cool: "Ventirad" };
  const USAGES = [
    ["office", "Bureautique / multimédia"], ["game1080", "Jeu 1080p"], ["game1440", "Jeu 1440p"],
    ["game4k", "Jeu 4K"], ["create", "Création / montage"], ["dev", "Développement / calcul"],
  ];
  const MODEL = "claude-opus-5-5";
  const API_URL = "https://api.anthropic.com/v1/messages";
  const TOWER_CATS = new Set(Object.values(TOWER_SLOTS));

  const str = { type: "string" };
  const SCHEMA = {
    type: "object",
    properties: {
      picks: {
        type: "object",
        properties: { cpu: str, mb: str, ram: str, gpu: { anyOf: [str, { type: "null" }] }, ssd: str, psu: str, case: str, cool: str },
        required: Object.keys(TOWER_SLOTS),
        additionalProperties: false,
      },
      rationale: str,
    },
    required: ["picks", "rationale"],
    additionalProperties: false,
  };

  const SYSTEM = [
    "Tu es un conseiller en montage de PC pour un acheteur en France.",
    "On te donne un budget, un usage et une liste d'annonces, une ligne JSON par annonce :",
    "[id, catégorie, modèle, titre, prix en €, \"n\" neuf ou \"o\" occasion, caractéristiques connues, 1 si bonne affaire].",
    "Choisis une annonce par emplacement de la tour : cpu (CPU), mb (MB), ram (RAM), gpu (GPU), ssd (SSD), psu (PSU), case (CASE), cool (COOL).",
    "Règles :",
    "- utilise uniquement des id de la liste, chacun dans la catégorie de son emplacement ;",
    "- gpu peut être null seulement si le processeur a un graphique intégré (igpu différent de false) et que l'usage est bureautique ou développement ;",
    "- le total des prix doit rester inférieur ou égal au budget ;",
    "- priorités : compatibilité (même socket processeur/carte mère, même DDR mémoire/carte mère, format de carte mère accepté par le boîtier, ventirad compatible avec le socket, alimentation d'au moins 1,2 × (TDP processeur + TDP carte graphique + 100 W)), puis adéquation à l'usage, puis prix ;",
    "- à prix proche, préfère le neuf à l'occasion ; une bonne affaire est un plus ;",
    "- une caractéristique absente est inconnue : préfère une pièce dont les caractéristiques prouvent la compatibilité.",
    "Dans rationale, explique tes choix en français en 5 phrases au plus.",
  ].join("\n");

  const usageLabel = (code) => (USAGES.find(([c]) => c === code) || [code, code])[1];

  function compactCatalog(items) {
    return (items || [])
      .filter((it) => TOWER_CATS.has(it.category) && typeof it.effective_eur === "number")
      .map((it) => JSON.stringify([it.id, it.category, it.model || null, String(it.title || "").slice(0, 70),
        it.effective_eur, it.condition === "new" ? "n" : "o", it.attrs || {}, it.deal ? 1 : 0]))
      .join("\n");
  }

  function buildRequest({ budget, usage, items, previous = null, problems = [] }) {
    const ask = "Budget maximum : " + budget + " €\nUsage : " + usageLabel(usage) + "\n\nAnnonces :\n" + compactCatalog(items);
    const messages = [{ role: "user", content: ask }];
    if (previous) {
      messages.push({ role: "assistant", content: JSON.stringify(previous) });
      messages.push({ role: "user", content: "Ta proposition a ces problèmes, corrige-les :\n- " + problems.join("\n- ") });
    }
    return {
      model: MODEL,
      max_tokens: 16000,
      fallbacks: "default",
      output_config: { effort: "medium", format: { type: "json_schema", schema: SCHEMA } },
      system: SYSTEM,
      messages,
    };
  }

  function parseResponse(data) {
    if (!data || data.stop_reason === "refusal") return { error: data ? "refusal" : "incomplete" };
    if (data.stop_reason === "max_tokens") return { error: "incomplete" };
    const block = (data.content || []).find((b) => b && b.type === "text");
    if (!block) return { error: "incomplete" };
    let out;
    try { out = JSON.parse(block.text); } catch (e) { return { error: "incomplete" }; }
    if (!out || typeof out.picks !== "object" || !out.picks || typeof out.rationale !== "string") return { error: "incomplete" };
    return { picks: out.picks, rationale: out.rationale };
  }

  const eur = (v) => Number(v).toLocaleString("fr-FR", { style: "currency", currency: "EUR" });

  function validate(result, catalogById, budget, Compat) {
    const selection = {};
    const problems = [];
    const picks = (result && result.picks) || {};
    for (const [slot, cat] of Object.entries(TOWER_SLOTS)) {
      const id = picks[slot];
      if (id == null && slot === "gpu") continue;
      const it = typeof id === "string" ? catalogById.get(id) : undefined;
      if (!it || it.category !== cat || typeof it.effective_eur !== "number") {
        problems.push(SLOT_LABEL[slot] + " : annonce inconnue ou mal placée (" + String(id) + ").");
        continue;
      }
      selection[slot] = it;
    }
    const r = Compat.evaluate(selection);
    for (const c of r.checks) if (c.status === "ko") problems.push(c.message);
    const reported = new Set(Object.keys(TOWER_SLOTS).filter((s) => !(s in selection) && picks[s] != null));
    const missing = r.missing.filter((s) => !reported.has(s) && s !== "gpu");
    if (missing.length) problems.push("Il manque : " + missing.map((s) => SLOT_LABEL[s].toLowerCase()).join(", ") + ".");
    const total = Math.round(Object.values(selection).reduce((s, it) => s + it.effective_eur, 0) * 100) / 100;
    if (total > budget) problems.push("Budget dépassé : " + eur(total) + " pour " + eur(budget) + ".");
    return { selection, problems, total };
  }

  const api = { TOWER_SLOTS, SLOT_LABEL, USAGES, SCHEMA, MODEL, API_URL, compactCatalog, buildRequest, parseResponse, validate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Advisor = api;
})(typeof window !== "undefined" ? window : this);
