# Conseiller IA du configurateur — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bouton « Générer une configuration » dans le Configurateur : appel Claude depuis le navigateur avec la clé de l'utilisateur, proposition revérifiée par `compat.js`, appliquée sur clic.

**Architecture:** `docs/advisor.js` (UMD, sans DOM) porte toute la logique testable : catalogue compact, requête, lecture de la réponse, validation, boucle à 2 tentatives avec `fetch` injecté. `docs/config.js` ne fait que l'interface. Tests Node sans réseau, lancés par unittest.

**Tech Stack:** JavaScript vanilla (navigateur + Node pour les tests), Python 3.13 unittest comme lanceur. Aucune dépendance.

**Spec:** `design/specs/2026-11-04-conseiller-ia-design.md`

## Global Constraints

- Aucune dépendance, aucun script tiers dans la page ; texte inséré uniquement via `textContent`.
- Modèle `claude-opus-5-5`, `max_tokens` 16000, `fallbacks: "default"`, `output_config: {effort: "medium", format: {type: "json_schema", schema: SCHEMA}}`, pas de `thinking` ni `temperature`.
- En-têtes : `x-api-key`, `anthropic-version: 2023-06-01`, `anthropic-beta: server-side-fallback-2026-07-01`, `anthropic-dangerous-direct-browser-access: true`, `content-type: application/json`.
- Emplacements de la tour : `cpu mb ram gpu ssd psu case cool` → catégories `CPU MB RAM GPU SSD PSU CASE COOL`.
- Clés `localStorage` : `cw-ai-key` (clé API), `cw-ai-prefs` (`{budget, usage}`), la sélection reste `cw-config-v1`.
- Au plus 2 appels API par clic.
- Textes d'interface et messages d'erreur : exactement ceux de la spec.
- Node : `node` du PATH ou `~/.local/bin/node` ; tests ignorés (skip) si absent, comme les tests JS existants.

## Review Focus

1. **Réponse du modèle hostile ou fantaisiste** (id d'écran dans l'emplacement cpu, id inexistant, champ en trop) : refusée par `validate`, jamais appliquée telle quelle — test `validate: id mal placé`.
2. **Le total affiché vient du catalogue**, pas d'un prix que le modèle aurait écrit — test `validate: total recalculé`.
3. **Appliquer ne touche ni écran ni clavier** et retire une annonce disparue de la tour — scénario `ai_generate`.
4. **Clé absente / 401** : message clair, aucune requête sans clé — tests `generate: 401` et scénario `ai_no_key`.
5. **Deuxième tentative bornée** : jamais plus de 2 appels même si la 2ᵉ réponse est encore non conforme — test `generate: toujours non conforme`.

---

### Task 1: logique pure de `advisor.js`

**Files:**
- Create: `docs/advisor.js`, `tests/advisor.test.js`, `tests/test_advisor.py`

**Interfaces:**
- Produces (`module.exports` en Node, `window.Advisor` sinon) :
  - `TOWER_SLOTS: {cpu:"CPU", mb:"MB", ram:"RAM", gpu:"GPU", ssd:"SSD", psu:"PSU", case:"CASE", cool:"COOL"}`
  - `USAGES: [[code, libellé], …]` dans l'ordre de la spec (`office`, `game1080`, `game1440`, `game4k`, `create`, `dev`)
  - `SCHEMA` (objet de la spec)
  - `compactCatalog(items) -> string` : une ligne JSON par annonce de la tour à `effective_eur` numérique : `[id, category, model, title.slice(0,70), effective_eur, "n"|"o", attrs||{}, deal?1:0]` ; `"n"` si `condition === "new"`.
  - `buildRequest({budget, usage, items, previous=null, problems=[]}) -> {headers-free body object}` : `{model, max_tokens, fallbacks, output_config, system, messages}`. `messages[0].content` contient `"Budget maximum : <budget> €"`, le libellé d'usage et `compactCatalog(items)`. Si `previous` : `messages` = `[user, {role:"assistant", content: JSON.stringify(previous)}, {role:"user", content: "Ta proposition a ces problèmes, corrige-les :\n- " + problems.join("\n- ")}]`.
  - `parseResponse(data) -> {picks, rationale} | {error: "refusal"|"incomplete"}` : `refusal` si `stop_reason === "refusal"` ; `incomplete` si `stop_reason === "max_tokens"`, pas de bloc `text`, JSON illisible, ou `picks`/`rationale` absents.
  - `validate(result, catalogById: Map, budget: number, Compat) -> {selection, problems: string[], total: number}` : règles 1–4 de la spec ; `selection` ne contient que les pièces valides ; `total` arrondi au centime.

- [ ] **Step 1: écrire `tests/advisor.test.js`** (même style que `tests/search.test.js` : `assert`, fonction `t`, affiche `ok <n>` à la fin). Données : les items de `tests/fixtures/catalog_demo.json` (dealabs:1…13, voir attrs dans la fixture). Tests :
  - `compact: tour seulement` : 11 lignes (pas de MON/KBD), première ligne parsée `[ "dealabs:1", "CPU", …, 349, "n", {socket:"AM5",…}, 0|1 ]`, titre ≤ 70 caractères.
  - `request: forme` : `model === "claude-opus-5-5"`, `fallbacks === "default"`, `output_config.format.schema === SCHEMA`, `messages.length === 1`, contenu inclut `"1000 €"` et `"Jeu 1440p"`.
  - `request: 2e tentative` : avec `previous` et `problems:["Budget dépassé"]`, 3 messages, rôles `user/assistant/user`, dernier contient `"Budget dépassé"`.
  - `parse: ok` / `parse: refus` / `parse: max_tokens` / `parse: json illisible` → valeurs attendues.
  - `validate: conforme` : picks `cpu dealabs:2, mb dealabs:4, ram dealabs:6, gpu dealabs:7, ssd dealabs:8, psu dealabs:9, case dealabs:10, cool dealabs:11`, budget 1500 → `problems` vide, `total === 1284`.
  - `validate: id mal placé` : `cpu: "dealabs:12"` → un problème commençant par `"Processeur"` ou `"cpu"` (libellé choisi : celui de `SLOT_LABEL` interne, ex. « Processeur : annonce inconnue ou mal placée »), `selection.cpu` absent.
  - `validate: id inconnu` : `ssd: "x:1"` → problème.
  - `validate: gpu null` : avec cpu dealabs:2 (igpu true) → aucun problème lié au gpu ; avec cpu dealabs:3 (igpu false) + mb dealabs:5 + ram … → problème.
  - `validate: socket ko` : cpu dealabs:3 (AM4) + mb dealabs:4 (AM5) → problème contenant le message `ko` de Compat.
  - `validate: budget dépassé` : picks conformes, budget 1000 → problème `"Budget dépassé : 1 284,00 € pour 1 000,00 €"` (format `toLocaleString("fr-FR", {style:"currency", currency:"EUR"})`; comparer avec `includes("Budget dépassé")`).
  - `validate: total recalculé` : `result` contenant un champ `total: 1` ignoré → `total === 1284`.
- [ ] **Step 2: écrire `tests/test_advisor.py`** sur le modèle de `tests/test_search.py` (lance `node tests/advisor.test.js`, assert code 0). Lancer `python3 -m unittest tests.test_advisor -v` → FAIL (module introuvable).
- [ ] **Step 3: implémenter `docs/advisor.js`** (en-tête `"use strict"`, IIFE UMD comme `compat.js`). Prompt système : texte de la spec (règles de choix), en français.
- [ ] **Step 4:** `python3 -m unittest tests.test_advisor -v` → PASS.
- [ ] **Step 5: commit** `feat(conseiller): logique de requête et de validation`.

### Task 2: `Advisor.generate`

**Files:**
- Modify: `docs/advisor.js`, `tests/advisor.test.js`

**Interfaces:**
- Consumes: Task 1 (`buildRequest`, `parseResponse`, `validate`).
- Produces: `generate({key, budget, usage, items, catalogById, Compat, fetch}) -> Promise<{selection, problems, total, rationale, attempts} | {error: string}>` ; `error` = message exact de la table « Erreurs » de la spec. Constante `API_URL = "https://api.anthropic.com/v1/messages"`.

Algorithme : appel 1 → si erreur, la renvoyer ; `validate` ; si `problems` non vide, appel 2 avec `previous = {picks, rationale}` et ces problèmes ; une erreur à l'appel 2 renvoie le résultat 1 (non conforme) plutôt que l'erreur ; renvoyer le dernier résultat validé avec `attempts` (1 ou 2). Réponse HTTP non ok : lire `json().error.message` si possible (sinon `""`), tronquer à 200. Exception de `fetch` → message réseau.

- [ ] **Step 1: tests** (faux `fetch` qui enregistre `(url, init)` et renvoie des réponses en file ; helper `apiReply(obj)` = `{ok:true, status:200, json:()=>Promise.resolve({stop_reason:"end_turn", content:[{type:"text", text: JSON.stringify(obj)}]})}`) :
  - `generate: conforme` : 1 appel ; URL = `API_URL` ; en-têtes `x-api-key`, `anthropic-dangerous-direct-browser-access: "true"`, `anthropic-beta: "server-side-fallback-2026-07-01"` ; corps JSON parsable avec `model` ; résultat `attempts 1`, `problems []`.
  - `generate: corrigé` : 1ʳᵉ réponse socket ko, 2ᵉ conforme → 2 appels, dernier corps a 3 messages, résultat conforme `attempts 2`.
  - `generate: toujours non conforme` : 2 réponses ko → exactement 2 appels, `problems` non vide.
  - `generate: 401` → `{error: "Clé API refusée. Vérifie-la sur console.anthropic.com."}`, 1 appel.
  - `generate: 429` et `529` → message « API saturée… ».
  - `generate: 500` avec `{error:{message:"boom"}}` → `"Erreur de l'API (500) : boom"`.
  - `generate: réseau` (fetch rejette) → « Réseau indisponible ou requête bloquée. ».
  - `generate: refus` → « Le modèle a refusé la demande. » ; `generate: illisible` → « Réponse incomplète, réessaie. ».
  - `generate: 2e appel en erreur` : 1ʳᵉ non conforme, 2ᵉ 500 → résultat 1 avec ses problèmes, pas d'`error`.
- [ ] **Step 2:** `node tests/advisor.test.js` → FAIL (`generate` absent).
- [ ] **Step 3:** implémenter `generate` (async ; tests JS : `t` doit accepter des fonctions async — adapter le petit harnais en `await`).
- [ ] **Step 4:** `python3 -m unittest tests.test_advisor -v` → PASS.
- [ ] **Step 5: commit** `feat(conseiller): appel API avec une seconde tentative`.

### Task 3: interface, page et documentation

**Files:**
- Modify: `docs/config.js`, `docs/index.html`, `docs/style.css`, `README.md`, `tests/dom_stub.js`, `tests/test_config_ui.py`, `tests/test_site.py`

**Interfaces:**
- Consumes: `window.Advisor` (Tasks 1–2), `window.Compat`.
- Produces (DOM) : ids `ai`, `ai-budget`, `ai-usage`, `ai-key`, `ai-forget`, `ai-go`, `ai-status`, `ai-result`, `ai-apply`, `ai-dismiss`.

Comportement : `index.html` porte la section statique `#ai` (champs + bouton + mention de coût, textes de la spec) au-dessus de `.cfg-grid`, `ai-usage` rempli par `config.js` depuis `Advisor.USAGES`. `config.js` : `bindAi()` appelé une fois si `#ai` existe ; préférences lues/écrites `cw-ai-prefs` ; `ai-go` désactivé tant que `catalog` est nul ; au clic : clé = champ ou `cw-ai-key` (champ non vide → enregistrée, champ vidé), sans clé → message de la spec et aucun `fetch` ; statut « Génération… (≈ 30 s) » ; `Advisor.generate({..., items: catalog.items, catalogById: byId, Compat: C, fetch: (u, i) => fetch(u, i)})` ; rendu dans `#ai-result` : une ligne par emplacement (libellé `SLOT_INFO`, `label(it)`, prix, lien), « Total : », contrôles `Compat.evaluate` avec `ICON`, justification, bandeau « ⚠️ Proposition non conforme : » + problèmes joints par « ; » s'il y en a, boutons Appliquer/Ignorer. Appliquer : pour chaque emplacement de `Advisor.TOWER_SLOTS`, `delete stale[slot]`, puis `selection[slot] = pick` ou `delete selection[slot]` ; `save(); render();` vide `#ai-result`. Ignorer : vide `#ai-result`. Oublier : `removeItem("cw-ai-key")`, statut « Clé oubliée. ».

- [ ] **Step 1: tests UI.** Dans `tests/dom_stub.js` : `makeEnv` crée aussi dans `tab-config` la section `ai` avec `input#ai-budget` (value "1500"), `select#ai-usage`, `input#ai-key`, `button#ai-forget`, `button#ai-go`, `p#ai-status`, `div#ai-result` ; `load()` charge `docs/advisor.js` comme `compat.js` (`window.Advisor`). Nouveaux scénarios :
  - `ai_generate` : storage `cw-config-v1` avec `mon: dealabs:12` et `cw-ai-key: "sk-test"` ; `fetch` = catalogue pour `data/catalog.json`, réponse API conforme (picks de Task 1) sinon ; clic `ai-go`, attendre ; renvoie `{apiCalls, key: headers x-api-key, resultText, applyExists}`, puis clic `ai-apply` → `{selected: valeurs des selects cpu…cool, mon: select mon, saved: JSON de cw-config-v1}`.
  - `ai_no_key` : pas de clé, clic → `{status, apiCalls: 0}`.
  - `ai_key_saved` : saisie `sk-new` dans `ai-key`, clic → `store["cw-ai-key"] === "sk-new"`, champ vidé ; clic `ai-forget` → clé absente.
  Dans `tests/test_config_ui.py` : assertions — `ai_generate` : `apiCalls 1`, `key "sk-test"`, `resultText` contient « Total » et le libellé d'au moins une pièce, après Appliquer `selected.cpu === "dealabs:2"`, `mon === "dealabs:12"` ; `ai_no_key` : `apiCalls 0`, status contient « Colle ta clé API » ; `ai_key_saved` comme décrit.
  Dans `tests/test_site.py` : `index.html` contient `id="ai"`, `id="ai-go"`, et `advisor.js` apparaît avant `config.js` ; `docs/advisor.js` n'utilise pas `innerHTML`.
- [ ] **Step 2:** `python3 -m unittest tests.test_config_ui tests.test_site -v` → FAIL.
- [ ] **Step 3:** implémenter `index.html`, `config.js`, `style.css` (règles `#ai` sobres, cohérentes avec `.cfg-*`).
- [ ] **Step 4:** `python3 -m unittest discover -s tests` → tout PASS.
- [ ] **Step 5: README** : intro « Veille **entièrement déterministe** (aucun LLM) » → la veille reste déterministe ; le configurateur propose en option un conseiller IA dans le navigateur. Sous-section « Conseiller IA » dans Configurateur : clé personnelle Anthropic (console.anthropic.com), gardée dans le navigateur, coût ≈ 0,10–0,30 € par génération, données envoyées (annonces de la tour : id, modèle, titre court, prix, état, caractéristiques ; budget ; usage), revérification par les mêmes contrôles, au plus 2 appels, Appliquer ne touche pas écran/clavier. Ligne « Sources » du pied de page inchangée ; ajouter à la note « Aucune donnée personnelle, aucun traceur » : « Le conseiller IA n'appelle l'API Anthropic qu'à ta demande, avec ta clé. ».
- [ ] **Step 6: commit** `feat(conseiller): bouton Générer dans le configurateur`.
