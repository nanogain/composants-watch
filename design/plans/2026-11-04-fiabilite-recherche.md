# v3 — Fiabilité et recherche élargie : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ne plus afficher d'annonce Dealabs expirée, ajouter eBay.fr filtré comme source d'annonces normales, et ajouter une section « Toutes les annonces » avec recherche.

**Architecture:**
- Une nouvelle étape de passe (`liveness.verify_dealabs`) lit les pages Dealabs et écrit `expired`/`checked_at` en base.
- La règle d'affichage vit dans `Store.recent_listings`, ce qui fait que tout l'aval (score, catalogue) en hérite.
- eBay est filtré dans `parse_ebay` et interrogé par catégorie.
- La recherche est une fonction JS pure (`docs/search.js`) appliquée à `catalog.json`.

**Tech Stack:** Python 3.13 stdlib, SQLite, JS vanilla, node pour les tests JS.

**Spec:** `design/specs/2026-11-04-fiabilite-recherche-design.md`

## Global Constraints

- Python stdlib uniquement, aucun LLM. Tests : `python3 -m unittest discover -s tests`.
- HTTP uniquement via `http_get` : User-Agent `composants-watch/…`, 2 s par hôte. Pages Dealabs `/bons-plans/` seulement.
- Valeurs par défaut :
  - `verify_max_pages` 80, `verify_budget_s` 240, `verify_recheck_hours` 3, `verify_visible_hours` 6 ;
  - `reddit_display_hours` 48, `ebay_limit` 50.
- Page : textContent uniquement (jamais d'insertion HTML), liens https uniquement, textes en français.
- Commits : auteur inchangé, lignes `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` et `Claude-Session: https://claude.ai/code/session_018NCTqhd6opwnP365FQoQ6G`.
- Développer uniquement dans `~/composants-watch-dev` (branche `v3-fiabilite-recherche`), jamais dans `~/composants-watch`.

## Review Focus

1. **Base existante en production (343 annonces, aucune `checked_at`)** : après la migration, rien de Dealabs n'est visible avant la première vérification. La première passe doit vérifier en priorité les plus récentes, et la page doit se remplir progressivement sans planter. Test : migration d'une base v2 puis `to_check` qui ordonne les jamais vérifiées par `posted_at` décroissant (Task 1).
2. **Dealabs qui répond 403 ou 429 en boucle** : arrêt après 3 échecs, `dealabs_verif` en échec, aucune annonce marquée expirée par erreur. Test `test_stops_after_three_failures_without_marking` (Task 2).
3. **Annonce eBay qui réapparaît après avoir été expirée par absence** : elle redevient visible. Test `test_ebay_reappears` (Task 1).
4. **Recherche avec caractères spéciaux ou vide** (« rtx 4070 », « écran », « » , « 4070-super ») : pas d'exception, la requête vide renvoie tout (dans la limite du plafond). Tests dans `tests/search.test.js` (Task 5).
5. **Note vendeur absente ou malformée** (`feedbackPercentage` manquant, `"abc"`, `feedbackScore` absent) : vendeur refusé sauf s'il est professionnel, sans exception. Test `test_seller_filter` (Task 3).

---

### Task 1: Base — `checked_at`, expiration, règle d'affichage, configuration

**Files:**
- Modify: `composants_watch/store.py`, `composants_watch/config.py`
- Test: `tests/test_store.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `Store.to_check(now: datetime, days: int, recheck_hours: float, limit: int) -> list[tuple[str, str]]` renvoie des `(source_id, url)`, Dealabs uniquement. Sélection : `expired = 0`, `posted_at >= now-days` et (`checked_at IS NULL` ou `checked_at < now-recheck_hours`). Ordre : jamais vérifiées d'abord, `posted_at` décroissant, puis `checked_at` croissant.
  - `Store.mark_checked(source: str, source_id: str, expired: bool, now: datetime) -> None`.
  - `Store.expire_missing(source: str, seen_ids: set[str], now: datetime) -> int` renvoie le nombre d'annonces marquées.
  - `Store.recent_listings(days, now, visible_hours: float | None = None, reddit_hours: float | None = None)` : `None` veut dire pas de filtre, ce qui garde le comportement actuel.
    - Avec `visible_hours`, une ligne Dealabs n'est gardée que si `expired = 0` et `checked_at >= now-visible_hours`.
    - Avec `reddit_hours`, une ligne Reddit n'est gardée que si `posted_at >= now-reddit_hours`.
    - Chaque dict renvoyé porte `checked_at`.
  - `DEFAULTS` : les 6 clés de la Global Constraints.

- [ ] **Step 1: Tests** dans `tests/test_store.py` :
  - `test_migration_adds_checked_at` : crée une base avec l'ancien schéma, sans `checked_at`, avec une annonce. `Store(path)` réussit, et `recent_listings(7, NOW)[0]["checked_at"]` vaut `None`.
  - `test_dealabs_expired_survives_upsert` : `mark_checked("dealabs","1",True,NOW)`, puis `upsert` de la même annonce avec `expired=False` → toujours expirée (`recent_listings(7,NOW)[0]["expired"] is True`).
  - `test_ebay_reappears` : annonce `ebay` e1, `expire_missing("ebay", set(), NOW)` → 1. `upsert` de e1 → `expired is False`.
  - `test_expire_missing_keeps_seen` : e1 et e2, `expire_missing("ebay", {"e1"}, NOW)` → 1, seule e2 est expirée. Les annonces Dealabs ne sont jamais touchées.
  - `test_to_check_order_and_recheck` :
    - a : jamais vérifiée, posted NOW-1h ;
    - b : jamais vérifiée, NOW-5h ;
    - c : vérifiée NOW-4h ;
    - d : vérifiée NOW-1h ;
    - e : expirée ;
    - f : posted NOW-8j.
    - `to_check(NOW, 7, 3, 10)` → ids `["a","b","c"]` ; `limit=2` → `["a","b"]`.
  - `test_visibility_rule` :
    - Dealabs vérifiée NOW-2h : visible ;
    - vérifiée NOW-7h : cachée ;
    - jamais vérifiée : cachée ;
    - Reddit posted NOW-30h : visible ; NOW-50h : caché ;
    - eBay non expirée : visible.
    - Le tout avec `recent_listings(7, NOW, visible_hours=6, reddit_hours=48)`.
  - `tests/test_config.py::test_v3_defaults` : les 6 valeurs par défaut.
- [ ] **Step 2:** `python3 -m unittest tests.test_store tests.test_config`. Expected: FAIL (AttributeError `to_check` / KeyError).
- [ ] **Step 3: Implémenter.**
  - `checked_at TEXT` dans `SCHEMA`, et migration `ALTER TABLE` si la colonne manque (même motif que `attrs`).
  - Dans `upsert`, le conflit fait `expired = CASE WHEN listings.source='dealabs' THEN MAX(listings.expired, excluded.expired) ELSE excluded.expired END`.
  - Ajouter les 6 clés dans `DEFAULTS`.
- [ ] **Step 4:** `python3 -m unittest discover -s tests`. Expected: tout passe, y compris les anciens tests (comportement par défaut inchangé).
- [ ] **Step 5: Commit** `store: checked_at, expiration Dealabs durable, règle d'affichage`.

### Task 2: Vérification Dealabs (`composants_watch/liveness.py`)

**Files:**
- Create: `composants_watch/liveness.py`, `tests/test_liveness.py`, `tests/fixtures/dealabs_page_expired.html`, `tests/fixtures/dealabs_page_active.html`
- Fixtures : extraits réels d'environ 3 Kio autour de `"threadId"`, coupés à partir de pages téléchargées. Par exemple https://www.dealabs.com/bons-plans/x-3401429 (expirée) et une annonce active récente.

**Interfaces:**
- Consumes: `Store.to_check`, `Store.mark_checked` (Task 1).
- Produces:
  - `parse_expired(html: str, thread_id: str) -> bool | None` : `None` si aucun `"isExpired"` n'est trouvé, ou si le `"threadId":"<id>"` est absent de la page.
  - `verify_dealabs(store, now: datetime, cfg: dict, get=http_get, clock=time.monotonic) -> dict` renvoie `{"checked": int, "expired": int, "failures": int, "stopped": str | None}`. `stopped` vaut `"pages"`, `"budget"`, `"failures"` ou `None`.

- [ ] **Step 1: Tests** :
  - `test_parse_expired_true_false` : sur les deux fixtures, `True` puis `False`.
  - `test_parse_missing` : `parse_expired("<html></html>", "1")` vaut `None`, et un id différent donne `None`.
  - `test_verify_marks_active_and_expired` : base avec trois annonces Dealabs non vérifiées.
    - Faux `get` qui renvoie la page active, la page expirée, puis lève `FetchError("HTTP 404 …")`.
    - Résultat : `checked == 3`, `expired == 2`.
    - Ensuite, `recent_listings(7, NOW, visible_hours=6)` ne contient que l'active.
  - `test_stops_after_three_failures_without_marking` : `get` lève toujours `FetchError("HTTP 429 …")`, avec 5 annonces → `failures == 3`, `stopped == "failures"`, aucun `checked_at` posé, aucune expiration.
  - `test_page_cap_and_budget` :
    - `cfg verify_max_pages=2` avec 5 annonces → `checked == 2`, `stopped == "pages"` ;
    - horloge injectée qui avance de 100 s par appel, `verify_budget_s=240` → au plus 3 pages, `stopped == "budget"`.
  - `test_page_without_flag_is_failure` : `get` renvoie `b"<html>"` → non vérifiée, `failures == 1`.
- [ ] **Step 2:** `python3 -m unittest tests.test_liveness`. Expected: FAIL (ModuleNotFoundError).
- [ ] **Step 3: Implémenter.**
  - 404 ou 410 : détecter `"HTTP 404"` ou `"HTTP 410"` dans le message de `FetchError` → `mark_checked(…, True, now)`.
  - Le compteur d'échecs est remis à 0 après chaque succès.
  - La vérification du budget se fait avant chaque page : `clock() - start >= verify_budget_s` → arrêt.
- [ ] **Step 4:** `python3 -m unittest discover -s tests`. Expected: PASS.
- [ ] **Step 5: Commit** `liveness: vérification isExpired des pages Dealabs`.

### Task 3: eBay — vraie forme, filtres de fiabilité, requêtes par catégorie

**Files:**
- Modify: `composants_watch/sources/ebay.py`, `tests/test_ebay.py`
- Replace: `tests/fixtures/ebay_search.json`. Construite à partir d'une vraie réponse (structure réelle, sans `itemCreationDate`), noms de vendeurs remplacés par `vendeurN`. Six annonces :
  1. pro, neuf (`conditionId` 1000), FR, livraison 0 ;
  2. particulier, 99.2 % / 1234, occasion 3000, DE ;
  3. particulier `"0.0"` / 695 → refusé ;
  4. `buyingOptions` `["FIXED_PRICE","AUCTION"]` → refusé ;
  5. `conditionId` 7000 → refusé ;
  6. pro, `itemLocation.country` `"CN"` → refusé.

**Interfaces:**
- Produces:
  - `CATEGORY_QUERIES: list[tuple[str, str]]`, les 12 couples `(q, category_id)` du tableau du spec § 4.1 (RAM en deux requêtes `ddr4`, `ddr5`).
  - `CATEGORY_IDS: dict[str, str]` : `{"GPU":"27386","CPU":"164","RAM":"170083","SSD":"175669","MB":"1244","PSU":"42017","CASE":"42014","COOL":"131486","MON":"80053","KBD":"33963"}`.
  - `EU: frozenset[str]` : les 27 codes ISO.
  - `reliable_seller(seller: dict) -> bool`.
  - `parse_ebay(data: dict, now: datetime) -> list[Listing]` : les filtres du spec § 4.2 sont appliqués ici.
  - `fetch_ebay(queries: list[tuple[str, str | None]], creds, now, limit=50, get=…, post=…) -> list[Listing]`.
    - URL : `q`, `limit`, `filter=buyingOptions:{FIXED_PRICE},deliveryCountry:FR`, plus `category_ids` s'il n'est pas `None`.
  - `ebay_queries(watchlist: list[dict]) -> list[tuple[str, str | None]]` : `CATEGORY_QUERIES` plus `(label, CATEGORY_IDS.get(préfixe du model))`.

- [ ] **Step 1: Tests** (remplacent `test_parse_ebay_fixture`, `test_non_eur_price_is_none`, `test_fetch_uses_marketplace_and_dedups`) :
  - `test_parse_real_shape` : la fixture donne 2 annonces, dans l'ordre 1 et 2.
    - Annonce 1 : `condition "new"`, `shipping_eur 0.0`, `merchant "eBay · vendeur1 (pro)"`, `posted_at == NOW`.
    - Annonce 2 : `condition "used"`, `merchant "eBay · vendeur2 (99,2 %, 1 234 avis)"`.
  - `test_seller_filter` :
    - acceptés : `{"sellerAccountType":"BUSINESS"}` ; `{"feedbackPercentage":"98.0","feedbackScore":50}` ;
    - refusés : `{"feedbackPercentage":"97.9","feedbackScore":500}` ; `{"feedbackPercentage":"99.0","feedbackScore":49}` ; `{"feedbackPercentage":"0.0","feedbackScore":695}` ; `{"feedbackPercentage":"abc"}` ; `{}`.
  - `test_creation_date_used_when_present` : avec `itemCreationDate` `"2026-11-01T10:00:00.000Z"`, `posted_at` vaut cette date.
  - `test_fetch_urls_have_category_and_filter` : faux `get`, `fetch_ebay([("carte graphique","27386"),("4070S",None)], …)` → deux appels.
    - Le premier contient `category_ids=27386`, `limit=50`, `deliveryCountry%3AFR`. Le second n'a pas de `category_ids`.
    - En-tête `X-EBAY-C-MARKETPLACE-ID: EBAY_FR`.
    - Dédoublonnage : 2 annonces au total.
  - `test_ebay_queries_from_watchlist` : `ebay_queries([{"model":"GPU:RTX 4070 Super","label":"RTX 4070 Super"}])` se termine par `("RTX 4070 Super","27386")` et contient 13 éléments.
  - `test_reference_needs_3` et `test_token_request_shape` restent inchangés.
- [ ] **Step 2:** `python3 -m unittest tests.test_ebay`. Expected: FAIL.
- [ ] **Step 3: Implémenter.**
  - Format du pourcentage : `f"{pct:.1f}".replace(".", ",")` ; nombre d'avis en `f"{n:,}".replace(",", " ")`.
  - Supprimer `GENERIC_QUERIES` et `NEW_WORDS`.
- [ ] **Step 4:** `python3 -m unittest discover -s tests`. Expected: échec attendu seulement dans `watch.py` (import `GENERIC_QUERIES`) s'il est importé par `test_watch`. Si c'est le cas, faire la Task 4 avant de committer, et ajouter une ligne `Ruling` au ledger.
- [ ] **Step 5: Commit** `ebay: forme réelle, vendeurs fiables, UE, requêtes par catégorie`.

### Task 4: Passe — vérification, expiration eBay, santé, configuration réelle

**Files:**
- Modify: `watch.py`, `tests/test_watch.py`, `tests/helpers.py`, `docs/app.js` (libellé de source uniquement)

**Interfaces:**
- Consumes: Tasks 1 à 3.
- Produces:
  - `run_pass(cfg, watchlist, root, *, fetchers, push, now, db_path=None, token_path=…, verify=None)`, où `verify: Callable[[Store, datetime], dict] | None`. Comportement :
    1. Après la collecte, si `fetchers["ebay"]` a réussi : `store.expire_missing("ebay", ids collectés, now)`.
    2. Si `verify` n'est pas `None`, appeler `verify(store, now)` dans un `try`.
       - Santé `dealabs_verif` OK si `checked > 0`, ou s'il n'y avait rien à vérifier (`stopped is None` et `failures == 0`).
       - Sinon, en échec avec un message `"N échecs"`.
       - `items = checked`.
       - Une exception donne un échec avec `str(e)[:200]`.
    3. `recent_listings(cfg["retention_days"], now, visible_hours=cfg["verify_visible_hours"], reddit_hours=cfg["reddit_display_hours"])`.
  - `tests/helpers.py::verify_all_active(store, now) -> dict` : marque actives toutes les Dealabs de `to_check(now, 3650, 0, 10**6)` et renvoie le dict de résultat.
  - `dry_fetchers()` est inchangé. `main --dry` passe `verify=lambda s, n: verify_all_active-like`, défini dans `watch.py` sous le nom `_dry_verify`, avec le même comportement que le helper de test. `real` passe `verify=lambda s, n: verify_dealabs(s, n, cfg)`.
  - `real_fetchers` utilise `ebay_queries(watchlist)` et `cfg["ebay_limit"]`.
  - `docs/app.js` : `SRC.dealabs_verif = "Vérification Dealabs"`.

- [ ] **Step 1: Tests** :
  - Mettre à jour les tests existants de `test_watch.py` qui attendent des annonces Dealabs visibles : passer `verify=verify_all_active`.
  - `test_unverified_dealabs_hidden` : un `run_pass` avec une annonce Dealabs et `verify=None` donne `catalog.items == []`. Avec `verify=verify_all_active`, on a 1 annonce.
  - `test_ebay_missing_expired_only_when_ok` :
    - passe 1 : eBay renvoie e1, e2 ;
    - passe 2 : eBay renvoie e1 → e2 n'est plus dans le catalogue ;
    - passe 3 : eBay lève `FetchError` → e1 est toujours présent.
  - `test_verify_health` :
    - `verify` renvoie `{"checked":0,"expired":0,"failures":3,"stopped":"failures"}` → `sources["dealabs_verif"]["status"]` vaut `"ok"` tant que `down_after` n'est pas atteint. Il faut vérifier `consecutive_failures == 1` dans la base.
    - `verify` qui lève une exception → la passe publie quand même.
  - `test_dry_end_to_end` doit toujours montrer des opportunités ou annonces issues des fixtures.
  - `tests/test_site.py` ou un test JS : `docs/app.js` contient `dealabs_verif`.
- [ ] **Step 2:** `python3 -m unittest tests.test_watch`. Expected: FAIL sur les nouveaux tests.
- [ ] **Step 3: Implémenter** comme dans les Interfaces.
- [ ] **Step 4:** `python3 -m unittest discover -s tests`, puis `python3 watch.py --dry --verbose`. Expected: PASS, et la passe à blanc se termine sans erreur.
- [ ] **Step 5: Commit** `watch: vérification Dealabs, expiration eBay, règle d'affichage`.

### Task 5: Section « Toutes les annonces »

**Files:**
- Create: `docs/search.js`, `tests/search.test.js`, `tests/test_search.py` (lanceur node sur le modèle de `test_compat.py`)
- Modify: `docs/index.html`, `docs/app.js`, `docs/style.css`, `tests/test_site.py`

**Interfaces:**
- Produces (`docs/search.js`, export UMD comme `compat.js`, global `Search`) :
  - `normalizeText(s) -> string` : minuscules, sans accents (NFD puis suppression de `̀-ͯ`), toute suite non alphanumérique remplacée par une espace, puis trim.
  - `matches(item, words) -> bool` : chaque mot apparaît dans `normalizeText(item.title + " " + (item.model || ""))`.
  - `filterItems(items, q) -> {total: number, rows: item[]}`, avec `q = {text, category, condition, source, maxPrice}`. Les champs vides sont ignorés. Tri `effective_eur` croissant, puis `title`. `rows` est limité à `LIMIT = 200`.
- Page :
  - section `<section id="all">` après Opportunités, contenant :
    - `<h2>Toutes les annonces</h2>` ;
    - la phrase de garantie du spec § 5 ;
    - `input#s-text` (type search) ;
    - `select#s-cat` (mêmes options que `f-cat`) ;
    - `select#s-cond` ;
    - `select#s-src` (Dealabs, eBay, Reddit) ;
    - `input#s-max` (type number, min 0) ;
    - `p#s-count` ;
    - `table#all-table` avec les colonnes du spec ;
    - `p#all-empty`.
  - `app.js` charge `data/catalog.json` (`cache: "no-store"`) et fait le rendu à chaque `input`/`change`.
  - ★ dans la première colonne si `deal`.
  - Le compteur affiche `"N résultats"`, ou `"N résultats, 200 affichés : affine la recherche"`.
  - Si le catalogue n'est pas disponible, la section affiche « Annonces indisponibles. » sans casser le reste.
  - `index.html` charge `search.js` avant `app.js`.

- [ ] **Step 1: Tests** :
  - `tests/search.test.js` (affiche `search: all N passed`) :
    - `normalizeText("Écran 27\" QHD")` vaut `"ecran 27 qhd"` ;
    - le texte `"ecran"` trouve « Écran » ;
    - `"rtx 4070"` exige les deux mots ;
    - `"4070-super"` trouve « RTX 4070 Super » ;
    - le texte vide renvoie tout ;
    - les filtres catégorie, état, source et `maxPrice` (inclusif) fonctionnent ;
    - le tri par prix croissant fonctionne ;
    - avec 250 items, `total` vaut 250 et `rows.length` vaut 200 ;
    - un item sans `model` ne provoque pas d'exception.
  - `tests/test_search.py` lance node et vérifie `"search: all"`.
  - `tests/test_site.py::test_all_listings_section` : `index.html` contient `id="all"`, `id="s-text"`, `id="s-max"` et `src="search.js"` avant `src="app.js"`. Le test existant `test_no_innerhtml_from_data` couvre `search.js`.
- [ ] **Step 2:** `python3 -m unittest tests.test_search tests.test_site`. Expected: FAIL.
- [ ] **Step 3: Implémenter.**
- [ ] **Step 4:** `python3 -m unittest discover -s tests`. Expected: PASS. Puis faire un contrôle visuel avec le dom_stub si nécessaire : un scénario dans `tests/dom_stub.js` qui charge `index.html` et `catalog_demo.json`, saisit `"rtx"` et vérifie le nombre de lignes.
- [ ] **Step 5: Commit** `page: section Toutes les annonces avec recherche`.

### Task 6: Documentation et vérification réelle

**Files:**
- Modify: `README.md`
- Modify: `tests/` seulement si la passe réelle révèle un défaut, avec un test RED→GREEN.

- [ ] **Step 1:** README :
  - section Sources : eBay filtré (catégories, vendeurs fiables, UE, prix fixe) ;
  - nouvelle section « Fiabilité » : vérification Dealabs moins de 6 h, Reddit 48 h, eBay vu au dernier passage ;
  - section « Toutes les annonces » ;
  - tableau des nouvelles clés de `config.json`.
- [ ] **Step 2:** Passe réelle sans publication, sur une copie de la base de production :
  `cp ~/composants-watch/data/watch.db data/watch.db && python3 watch.py --no-push --verbose`.
  Expected :
  - `source ebay : N annonces` avec N > 100 ;
  - `dealabs_verif` OK avec 80 pages vérifiées au plus ;
  - durée totale < 600 s ;
  - `catalog.json` contient des annonces eBay dont le marchand finit par `(pro)` ou `avis)`.
  Contrôler à la main 5 annonces Dealabs affichées (`isExpired` false) et 3 expirées.
- [ ] **Step 3:** `python3 -m unittest discover -s tests`. Expected: PASS.
- [ ] **Step 4: Commit** `docs: README v3`.

### Fusion (après la revue finale)

- Dans `~/composants-watch`, remettre `config.json` comme dans le dépôt (`git checkout config.json`) : eBay avait été mis en pause localement.
- Ensuite, faire la fusion de `v3-fiabilite-recherche` dans `main`. Le timer publie à la passe suivante.
