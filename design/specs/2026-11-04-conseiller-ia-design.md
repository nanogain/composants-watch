# Conseiller IA du configurateur — design

Date : 2026-11-04. Statut : approuvé en conversation, spec à relire.

## Objectif

Dans l'onglet **Configurateur**, un bouton « Générer une configuration » demande à un LLM
(Claude) une configuration **compatible, économique et adaptée à l'usage**, choisie
**uniquement parmi les annonces du catalogue publié** (`docs/data/catalog.json`). La
proposition est revérifiée par les règles déterministes existantes (`compat.js`) avant
d'être affichée, et n'est chargée dans le configurateur que sur clic « Appliquer ».

Ce qui a été décidé avec l'utilisateur :
- appel **depuis le navigateur**, avec **sa propre clé API Anthropic** gardée dans le
  `localStorage` ; rien sur le Pi, la clé n'est jamais publiée ;
- entrées : **budget max (€)** + **usage** ;
- périmètre : **la tour seule** (cpu, mb, ram, gpu, ssd, psu, case, cool) ; écran et
  clavier restent ceux choisis à la main.

Hors périmètre (YAGNI) : historique des générations, plusieurs propositions comparées,
champ de texte libre, écran/clavier, appel depuis le Pi, streaming.

## Interface

Un bloc « Générer avec l'IA » (`<section id="ai">`) en tête de l'onglet Configurateur,
au-dessus de `cfg-grid` :

| Élément | id | Détail |
|---|---|---|
| Budget max | `ai-budget` | `input type=number`, min 300, pas 50, défaut 1000 |
| Usage | `ai-usage` | `select` : `office` Bureautique / multimédia, `game1080` Jeu 1080p, `game1440` Jeu 1440p, `game4k` Jeu 4K, `create` Création / montage, `dev` Développement / calcul ; défaut `game1440` |
| Clé API | `ai-key` | `input type=password autocomplete=off`, placeholder `sk-ant-…` ; affichée vide si une clé est déjà enregistrée, avec le texte « clé enregistrée dans ce navigateur » |
| Oublier la clé | `ai-forget` | supprime la clé du `localStorage` |
| Générer | `ai-go` | désactivé pendant l'appel et tant que le catalogue n'est pas chargé |
| État | `ai-status` | `aria-live=polite` : « Génération… (≈ 30 s) », messages d'erreur |
| Proposition | `ai-result` | liste des pièces, total, contrôles, justification, boutons |

Mention sous le bouton : « Appel direct de ton navigateur à l'API Anthropic avec ta clé.
Coût ≈ 0,10 à 0,30 € par génération. La clé reste dans ce navigateur. »

Clé : enregistrée sous `cw-ai-key` au premier clic sur Générer avec un champ non vide ;
un champ vide réutilise la clé enregistrée ; aucune clé → message « Colle ta clé API
Anthropic (console.anthropic.com). ». Budget et usage enregistrés sous `cw-ai-prefs`.

## Requête au LLM

Appel `fetch` direct (le site n'a ni npm ni bundler, le SDK n'y est pas chargeable) :

```
POST https://api.anthropic.com/v1/messages
x-api-key: <clé>
anthropic-version: 2023-06-01
anthropic-beta: server-side-fallback-2026-07-01
anthropic-dangerous-direct-browser-access: true
content-type: application/json
```

Corps :
- `model: "claude-opus-5-5"`, `max_tokens: 16000`, `fallbacks: "default"`,
  `output_config: {effort: "medium", format: {type: "json_schema", schema: SCHEMA}}` ;
  pas de `thinking` (adaptatif par défaut), pas de `temperature`.
- `system` : rôle (conseiller montage PC France), règles : choisir uniquement des `id`
  de la liste, une pièce par emplacement de la tour, `gpu` peut être `null` seulement si
  le processeur a un graphique intégré et que l'usage est `office` ou `dev`, respecter le
  budget (total des `effective_eur`), privilégier compatibilité puis adéquation à l'usage
  puis prix ; préférer le neuf à l'occasion à prix proche ; une annonce ★ est une bonne
  affaire ; les attributs manquants signifient « inconnu », préférer une pièce dont les
  attributs prouvent la compatibilité. Répondre en français.
- `messages[0]` (user) : budget, usage (libellé), puis le catalogue compact, une ligne
  JSON par annonce : `[id, catégorie, modèle, titre (70 car. max), prix €, "n"|"o", attrs, ★ 0|1]`,
  seulement les catégories de la tour et les annonces à prix numérique (≈ 350 lignes,
  ≈ 15 k tokens aujourd'hui).
- Deuxième tentative (voir plus bas) : on ajoute la réponse JSON précédente (assistant) et un
  message user listant les problèmes trouvés.

`SCHEMA` (tous les objets avec `additionalProperties: false`, tous les champs requis) :

```json
{"type":"object","properties":{
  "picks":{"type":"object","properties":{
    "cpu":{"type":"string"},"mb":{"type":"string"},"ram":{"type":"string"},
    "gpu":{"anyOf":[{"type":"string"},{"type":"null"}]},
    "ssd":{"type":"string"},"psu":{"type":"string"},"case":{"type":"string"},"cool":{"type":"string"}},
   "required":["cpu","mb","ram","gpu","ssd","psu","case","cool"],"additionalProperties":false},
  "rationale":{"type":"string"}},
 "required":["picks","rationale"],"additionalProperties":false}
```

## Validation (le LLM n'est pas cru sur parole)

`validate(response, bySlotIds, catalogById, budget)` renvoie
`{selection, problems: [texte], total}` :
1. chaque `id` doit exister dans le catalogue **et** appartenir à la catégorie de son
   emplacement, sinon problème « <emplacement> : annonce inconnue ou mal placée » ;
2. `gpu: null` accepté seulement si l'`igpu` du processeur n'est pas `false` ;
3. `Compat.evaluate(selection)` : chaque contrôle `ko` (et `missing` non vide) devient un
   problème, avec le message du contrôle ;
4. total recalculé à partir des `effective_eur` du catalogue ; total > budget → problème
   « Budget dépassé : X € pour Y € ».

`❔` et `⚠️` ne sont pas des problèmes : ils sont affichés tels quels.

## Déroulé

1. Clic Générer → requête 1 → validation.
2. Problèmes non vides → **une seule** deuxième tentative avec les problèmes →
   validation.
3. Affichage de la dernière proposition : pièces (libellé, prix, lien), total, contrôles
   avec icônes, justification, et si des problèmes restent, bandeau
   « ⚠️ Proposition non conforme : … ». Boutons « Appliquer » (`ai-apply`) et « Ignorer »
   (`ai-dismiss`).
4. « Appliquer » remplace les emplacements de la tour dans la sélection (gpu supprimé si
   `null`), garde écran et clavier, efface les annonces disparues de ces emplacements,
   enregistre et réaffiche. Rien ne change sans ce clic.

## Erreurs

| Cas | Message |
|---|---|
| 401 | « Clé API refusée. Vérifie-la sur console.anthropic.com. » (la clé enregistrée est conservée, l'utilisateur peut l'oublier) |
| 429 / 529 | « API saturée ou limite atteinte, réessaie dans une minute. » |
| autre HTTP | « Erreur de l'API (<code>) : <message de l'API, 200 car. max> » |
| réseau | « Réseau indisponible ou requête bloquée. » |
| `stop_reason` `refusal` | « Le modèle a refusé la demande. » |
| `stop_reason` `max_tokens` ou JSON illisible | « Réponse incomplète, réessaie. » |

Le texte du modèle n'est inséré qu'avec `textContent` (comme le reste de la page).

## Code

- **`docs/advisor.js`** (nouveau, UMD `window.Advisor` / `module.exports`, sans DOM) :
  `USAGES`, `TOWER_SLOTS`, `SCHEMA`, `compactCatalog(items)`,
  `buildRequest({budget, usage, items, previous, problems})`,
  `parseResponse(json) -> {picks, rationale} | {error}`,
  `validate(result, catalogById, budget, Compat) -> {selection, problems, total}`,
  `generate({key, budget, usage, items, catalogById, Compat, fetch}) -> Promise<{selection, problems, total, rationale, attempts} | {error}>`.
- **`docs/config.js`** : bloc IA (rendu, préférences, clé, Appliquer/Ignorer) ; expose
  le catalogue chargé à `Advisor.generate`.
- **`docs/index.html`** : section `#ai`, `advisor.js` chargé avant `config.js`.
- **`docs/style.css`** : quelques règles pour `#ai`.
- **`README.md`** : l'introduction précise que la **veille** est déterministe et que le
  conseiller IA est une option du navigateur ; nouvelle sous-section « Conseiller IA » du
  Configurateur (clé personnelle, coût, ce qui est envoyé, revérification).

## Tests

- `tests/advisor.test.js` (Node, sans réseau, faux `fetch`) : compactage (catégories de la
  tour seulement, titre tronqué), forme de la requête (en-têtes, modèle, schéma, budget et
  usage présents), `validate` (id inconnu, id mal placé, gpu null avec/sans igpu, socket
  ko, budget dépassé, proposition conforme), `generate` (conforme en 1 appel ; non conforme
  → 2 appels dont le second contient les problèmes ; toujours non conforme → résultat avec
  problèmes ; 401 ; refus ; JSON illisible).
- `tests/dom_stub.js` : nouveau scénario `ai_generate` (catalogue + faux `fetch` → clic
  Générer → proposition affichée → Appliquer → sélection de la tour remplacée, écran
  conservé) ; lancé depuis `tests/test_site.py` comme les autres scénarios.
- `tests/test_site.py` : `index.html` contient `#ai` et charge `advisor.js` avant
  `config.js`.

## Risques

- Coût à la charge de l'utilisateur, ≈ 0,10–0,30 € par génération (×2 si deuxième
  tentative). Affiché sous le bouton.
- Clé dans le `localStorage` : lisible par tout script de la page ; la page ne charge
  aucun script tiers. Documenté dans le README.
- Les attributs du catalogue sont incomplets (❔) : le LLM peut proposer une pièce dont la
  compatibilité n'est pas prouvée ; elle est affichée avec ❔ comme dans le configurateur
  manuel.
