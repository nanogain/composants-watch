# composants-watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministic Pi-side watcher of PC-component listings (Dealabs RSS, Reddit Atom, eBay.fr API) that scores deals against a watchlist and 30-day medians and publishes `docs/data/deals.json` to a GitHub Pages site.

**Architecture:** One pass per run (`watch.py`): sources → `Listing` objects → normalize → SQLite store → score → JSON → git push if changed. Static page in `docs/` renders the JSON. systemd user timer every 30 min.

**Tech Stack:** Python 3.13 standard library only (urllib, xml.etree, sqlite3, json, re, statistics, fcntl, logging, unittest). Vanilla HTML/CSS/JS.

**Spec:** `design/specs/2026-11-03-composants-watch-design.md` (plan lives in `design/plans/` because `docs/` is the published Pages folder).

## Global Constraints

- No LLM, no third-party Python package; standard library only.
- No source without authorised access (no leboncoin, no HTML scraping of merchant sites).
- User-Agent: `composants-watch/0.1 (usage personnel)`; ≥ 2 s between requests to the same host; timeout 20 s; 2 retries on HTTP 5xx / network errors only.
- `discount_min` 0.15, `suspect_above` 0.70, `median_window_days` 30, `median_min_obs` 5 (and ≥ 2 distinct listings), eBay fallback ≥ 3 listings, `retention_days` 7, `down_after_failures` 5.
- Effective price = `price_eur + (shipping_eur or 0)`. USD listings: `price_eur=None`, never in medians.
- Median exclusion keywords (case-insensitive): `hs`, `pour pièces`, `défectueux`, `boîte vide`, `box only`, `lot de`, `mining`, `reconditionné`, `ne fonctionne pas` (`hs` matched as a whole word).
- Medians per `(model, condition)`.
- Canonical model ids: `GPU:RTX 4070 Super`, `CPU:Ryzen 7 7800X3D`, `RAM:DDR5-32Go-6000`, `SSD:NVMe-2To`, `MB:B650`, `PSU:850W-Gold`.
- Secrets only in `~/.config/composants-watch/` (`token`, `ebay.json`), mode 600, never in the repo, token never written into `.git/config`.
- Page: French UI, no tracker, no third-party request.
- `data/` and `logs/` are git-ignored; only `docs/data/deals.json` is published data.
- Tests: `python3 -m unittest discover -s tests -v`, no network.

## Review Focus

1. Odd price strings (`1 299,99€`, `1.299,99 €`, `1299€`, `Gratuit`, missing) → parsed or `None`, never an exception (test in Task 2).
2. Watchlist entry whose `model` is not canonical / never produced by `normalize` → shown on the page as "modèle jamais vu" rather than silently empty (test in Task 6).
3. Empty database on first run → page renders with empty lists and "sans référence", no crash (test in Task 9).
4. Network down or token missing at push time → pass still completes, `deals.json` written locally, error logged, retried next pass (test in Task 7).
5. Malformed / truncated feed XML from one source → that source counted as a failure, other sources still processed (test in Task 9).

---

### Task 1: Scaffold, models, HTTP helper, config

**Files:**
- Create: `composants_watch/__init__.py` (`__version__ = "0.1"`), `composants_watch/models.py`, `composants_watch/http.py`, `composants_watch/config.py`, `config.json`, `watchlist.json`
- Test: `tests/test_http.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass Listing(source: str, source_id: str, url: str, title: str, price_eur: float|None, price_raw: str, currency: str, shipping_eur: float|None, merchant: str, condition: str, posted_at: datetime, expired: bool = False, category: str|None = None, model: str|None = None, image_url: str|None = None)`; property `effective_eur -> float|None`.
  - `http_get(url: str, headers: dict|None = None, *, opener=None, sleep=time.sleep) -> bytes` — raises `FetchError` after retries.
  - `class FetchError(Exception)`.
  - `load_config(path="config.json") -> dict` (defaults merged with file), `load_watchlist(path="watchlist.json") -> list[dict]`.

- [ ] **Step 1: Write failing tests**
  - `test_retries_on_503_then_succeeds`: fake opener raising `HTTPError(503)` twice then returning `b"ok"` → result `b"ok"`, 3 calls, sleep called.
  - `test_no_retry_on_404`: fake opener raising `HTTPError(404)` → `FetchError`, 1 call.
  - `test_gives_up_after_two_retries`: always 503 → `FetchError`, 3 calls.
  - `test_user_agent_header`: request seen by opener has `User-Agent` == `composants-watch/0.1 (usage personnel)`.
  - `test_config_defaults_merged`: file with only `{"discount_min": 0.2}` → `discount_min` 0.2 and `suspect_above` 0.70.
  - `test_effective_eur`: price 100, shipping 9.99 → 109.99; price None → None.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_http tests.test_config -v` → FAIL (import errors).
- [ ] **Step 3: Implement** the modules above. `http_get` enforces per-host 2 s spacing with a module-level `dict[host, last_ts]`. `config.json` holds every key from Global Constraints plus `dealabs_groups: ["cartes-graphiques","processeurs","memoire-vive","ssd","cartes-meres","alimentations-pc","informatique"]`, `reddit_enabled: true`, `ebay_enabled: true`. `watchlist.json` = `[{"model": "GPU:RTX 4070 Super", "label": "RTX 4070 Super", "target_eur": 550}]` as an example.
- [ ] **Step 4: Run** same command → PASS.
- [ ] **Step 5: Commit** `feat: modèles, HTTP avec retries, configuration`.

### Task 2: Dealabs source

**Files:**
- Create: `composants_watch/sources/__init__.py`, `composants_watch/sources/dealabs.py`, `composants_watch/prices.py`
- Test: `tests/test_prices.py`, `tests/test_dealabs.py`, fixture `tests/fixtures/dealabs_gpu.xml` (record with `curl -sL -A "composants-watch/0.1 (usage personnel)" https://www.dealabs.com/rss/groupe/cartes-graphiques`)

**Interfaces:**
- Produces: `parse_price(text: str) -> float|None`; `parse_dealabs(xml: bytes) -> list[Listing]`; `fetch_dealabs(groups: list[str], get=http_get) -> tuple[list[Listing], list[str]]` (listings, failed group slugs).

- [ ] **Step 1: Write failing tests**
  - `test_parse_price_formats`: `"67,63€"`→67.63, `"1 299,99€"`→1299.99, `"1.299,99 €"`→1299.99, `"1299€"`→1299.0, `"Gratuit"`→0.0, `""`→None, `"abc"`→None.
  - `test_parse_dealabs_fixture`: ≥ 1 listing; first has `source=="dealabs"`, `currency=="EUR"`, `price_eur` float, `merchant` non-empty, `url` starting `https://www.dealabs.com/`, `condition=="new"`.
  - `test_reconditionne_is_used`: item title containing "Reconditionnée" → `condition=="used"`.
  - `test_missing_merchant_price_falls_back_to_strong`: synthetic item without `pepper:merchant` but description `<strong>89,90€ - Amazon</strong>` → 89.9, merchant "Amazon".
  - `test_expired_flag`: synthetic item whose title starts with `[Expiré]` (case-insensitive) → `expired True`; normal title → `False`.
  - `test_fetch_skips_404_group`: `get` raising `FetchError` for one slug → that slug in failed list, others parsed.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_prices tests.test_dealabs -v` → FAIL.
- [ ] **Step 3: Implement.** `source_id` = numeric id at end of the item `<link>` (fallback: guid). Namespace `pepper = http://www.pepper.com/rss`. `posted_at` from `pubDate` (UTC).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: source Dealabs (RSS)`.

### Task 3: Reddit source

**Files:**
- Create: `composants_watch/sources/reddit.py`
- Test: `tests/test_reddit.py`, fixture `tests/fixtures/reddit_bapcs.xml`

**Interfaces:**
- Produces: `parse_reddit(xml: bytes) -> list[Listing]`; `fetch_reddit(get=http_get) -> list[Listing]` (raises `FetchError`).

- [ ] **Step 1: Write failing tests**
  - `test_parse_reddit_fixture`: ≥ 1 listing, `source=="reddit"`, `currency=="USD"`, `price_eur is None`, `price_raw` starts with `$`.
  - `test_category_prefix`: title `"[RAM] Corsair 2x16GB DDR5-6000 - $89.99"` → `category=="RAM"`; `[GPU]`→`GPU`, `[CPU]`→`CPU`, `[SSD]`→`SSD`, `[Motherboard]`→`MB`, `[PSU]`→`PSU`, `[Cooler]`→`None`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (Atom namespace `http://www.w3.org/2005/Atom`; `source_id` = entry `<id>`). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: source Reddit r/buildapcsales`.

### Task 4: Normalisation

**Files:**
- Create: `composants_watch/normalize.py`
- Test: `tests/test_normalize.py` (table-driven, ≥ 40 real titles copied from the two fixtures plus hand-written FR titles)

**Interfaces:**
- Produces: `normalize(title: str, hint_category: str|None = None) -> tuple[str|None, str|None]` (category, model); `apply(listing: Listing) -> Listing` (fills `category`/`model`).

- [ ] **Step 1: Write failing tests** — required cases include:
  - `"Carte graphique MSI GeForce RTX 4070 SUPER Ventus 2X 12G"` → `("GPU","GPU:RTX 4070 Super")`
  - `"Gigabyte RTX 4060 Ti 16 Go"` → `GPU:RTX 4060 Ti`; `"RTX 5070 Ti"` → `GPU:RTX 5070 Ti`
  - `"Sapphire Pulse Radeon RX 7800 XT"` → `GPU:RX 7800 XT`; `"RX 7900 XTX"` → `GPU:RX 7900 XTX`; `"RX 580 8 Go"` → `GPU:RX 580`
  - `"AMD Ryzen 7 7800X3D"` → `CPU:Ryzen 7 7800X3D`; `"Ryzen 5 7600"` → `CPU:Ryzen 5 7600`
  - `"Intel Core i5-13600KF"` → `CPU:Core i5-13600KF`; `"Core Ultra 7 265K"` → `CPU:Core Ultra 7 265K`
  - `"Kit Corsair Vengeance 32 Go (2 x 16 Go) DDR5 6000 MHz CL30"` → `RAM:DDR5-32Go-6000`; `"G.Skill 2x16GB DDR5-6000 CL36"` → `RAM:DDR5-32Go-6000`; `"Crucial 16 Go DDR4 3200"` → `RAM:DDR4-16Go-3200`
  - `"Samsung 990 Pro 2 To NVMe M.2"` → `SSD:NVMe-2To`; `"Crucial MX500 1TB SATA"` → `SSD:SATA-1To`; `"WD SN770 500 Go"` (NVMe implied by `SN`) → `SSD:NVMe-500Go`
  - `"MSI MAG B650 Tomahawk WiFi"` → `MB:B650`; `"ASUS ROG Strix Z790-E"` → `MB:Z790`
  - `"Corsair RM850x 850W 80+ Gold"` → `PSU:850W-Gold`
  - `"Souris gamer Logitech"` → `(None, None)`; `"Câble HDMI 2.1"` → `(None, None)`
  - `hint_category="RAM"` with unparseable title → `("RAM", None)`
  - GPU priority: `"PC portable RTX 4060"` → `(None, None)` (laptops/prebuilt excluded: `pc portable`, `laptop`, `pc gamer`, `pc fixe`, `tour`)
- [ ] **Step 2: Run** `python3 -m unittest tests.test_normalize -v` → FAIL.
- [ ] **Step 3: Implement** ordered regex rules per category (exclusions first, then GPU, CPU, RAM, SSD, MB, PSU). RAM capacity = `n × size` when `n x size` present, else single size. Capacity units: `To/TB` → `NTo`, `Go/GB` ≥ 1000 → convert to To.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: reconnaissance déterministe des modèles`.

### Task 5: SQLite store

**Files:**
- Create: `composants_watch/store.py`
- Test: `tests/test_store.py` (uses `:memory:`)

**Interfaces:**
- Consumes: `Listing`.
- Produces: `class Store(path: str)` with `upsert(listing: Listing, now: datetime) -> None`, `recent_listings(days: int, now: datetime) -> list[dict]` (one row per listing with its latest `price_eur`, `shipping_eur`, plus `title, model, category, condition, merchant, url, source, posted_at, expired, first_seen`), `observations(model: str, condition: str, since: datetime) -> list[tuple[str, str, float]]` (source, source_id, effective price — latest per listing), `record_source(source: str, ok: bool, error: str|None, now: datetime) -> dict` (returns `{"consecutive_failures": int, "last_ok": str|None}`), `source_health() -> dict[str, dict]`.

- [ ] **Step 1: Write failing tests**
  - `test_same_price_no_new_observation`: upsert twice same price → 1 observation row.
  - `test_price_change_adds_observation`: 100 then 90 → 2 rows; `recent_listings` shows 90.
  - `test_observations_latest_per_listing`: two listings same model → 2 tuples with their latest prices.
  - `test_source_failures_counter`: 3 failures then 1 ok → counter 3 then 0, `last_ok` set.
  - `test_retention`: listing first_seen 8 days ago → absent from `recent_listings(7, now)`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** schema from spec §3.4. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: stockage SQLite des annonces et observations`.

### Task 6: Scoring

**Files:**
- Create: `composants_watch/score.py`
- Test: `tests/test_score.py`

**Interfaces:**
- Consumes: `Store.recent_listings`, `Store.observations`, config dict, watchlist list.
- Produces: `is_excluded(title: str) -> bool`; `reference_median(obs: list[tuple[str,str,float]], min_obs: int) -> float|None`; `score(listings: list[dict], store: Store, cfg: dict, watchlist: list[dict], now: datetime, ebay_ref: dict[str, float] | None = None) -> dict` returning `{"watchlist": [...], "opportunities": [...], "unclassified": [...], "stats": {...}}` with exactly the item fields of spec §4.

- [ ] **Step 1: Write failing tests**
  - `test_excluded_keywords`: `"RTX 3080 HS pour pièces"` True; `"Lot de 4 barrettes"` True; `"RTX 4070 Super neuve"` False; `"Kit HSF"` False (`hs` whole word only).
  - `test_median_needs_5_obs_2_listings`: 4 obs → None; 5 obs from 1 listing → None; 5 obs from 2 listings → median.
  - `test_discount_opportunity`: median 600, listing 500 → opportunity with `discount_pct` ≈ 16.7; listing 520 (13.3 %) → not an opportunity.
  - `test_target_hit_first`: watchlist target 550, listing 549 with 5 % discount and another listing 30 % discount → target one first.
  - `test_suspect_over_70`: median 600, listing 150 → `suspect True`, sorted after non-suspects.
  - `test_shipping_included`: price 540 + shipping 15 vs target 550 → `target_hit False`.
  - `test_usd_never_scored`: reddit listing with `price_eur None` and a recognised model → absent from opportunities and from the median observations; same listing with `model None` → present in `unclassified`.
  - `test_new_and_used_separate_medians`: used listings don't affect new median.
  - `test_ebay_fallback_reference`: no local median, `ebay_ref={"GPU:RTX 4070 Super|new": 600}` → reference 600 used.
  - `test_watchlist_unknown_model`: watchlist model never seen → entry with `best None`, `median_30d None`, field `"never_seen": true`.
  - `test_expired_removed`: expired listing absent from opportunities.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (sort key: `(not target_hit, suspect, -discount_pct)`). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: calcul déterministe des opportunités`.

### Task 7: Publication (JSON + git)

**Files:**
- Create: `composants_watch/publish.py`
- Test: `tests/test_publish.py` (temp git repo via `git init` in `tempfile.TemporaryDirectory`, bare remote also local)

**Interfaces:**
- Consumes: `score()` result, source health dict.
- Produces: `build_payload(scored: dict, health: dict, now: datetime, version: int = 1) -> dict`; `write_json(payload: dict, path: Path) -> bool` (True if content excluding `generated_at` changed; atomic write); `git_push(repo: Path, rel_path: str, token_path: Path, now: datetime, run=subprocess.run) -> tuple[bool, str]`.

- [ ] **Step 1: Write failing tests**
  - `test_payload_schema`: keys `generated_at, version, sources, watchlist, opportunities, unclassified, stats`; source status `ok|down|disabled` mapping (`consecutive_failures >= 5` → `down`).
  - `test_write_json_unchanged_returns_false`: write same payload twice with different `generated_at` → second returns False.
  - `test_git_push_commits_and_pushes_to_local_remote`: changed file → commit message starts `data: mise à jour`, remote has the commit.
  - `test_git_push_missing_token_fails_cleanly`: token file absent and remote is https → returns `(False, "token absent")`, no exception, local commit kept.
  - `test_token_not_written_to_git_config`: after push, `.git/config` does not contain the token string.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** For https remotes pass the token per command only: `git -c http.extraHeader="Authorization: Basic <base64(x-access-token:TOKEN)>" push origin main`. Local-path remotes (tests) skip the token.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: génération deals.json et publication git`.

### Task 8: eBay source (optional)

**Files:**
- Create: `composants_watch/sources/ebay.py`
- Test: `tests/test_ebay.py`, fixture `tests/fixtures/ebay_search.json` (hand-written from eBay Browse API docs shape: `itemSummaries[].{itemId,title,price{value,currency},shippingOptions[].shippingCost.value,condition,itemWebUrl,seller.username,itemCreationDate}`)

**Interfaces:**
- Produces: `load_credentials(path: Path) -> dict|None`; `get_token(creds: dict, post=...) -> str`; `parse_ebay(data: dict) -> list[Listing]`; `fetch_ebay(queries: list[str], creds: dict, get=..., post=...) -> list[Listing]`; `ebay_reference(listings: list[Listing], min_n: int = 3) -> dict[str, float]` (key `"model|new"`, median of new FIXED_PRICE effective prices).

- [ ] **Step 1: Write failing tests**
  - `test_no_credentials_returns_none`: missing file → None.
  - `test_parse_ebay_fixture`: `source=="ebay"`, EUR price, shipping parsed, `condition` "new" for `"Neuf"`/`"New"`, "used" otherwise.
  - `test_reference_needs_3`: 2 new listings same model → no key; 3 → median.
  - `test_token_request_shape`: fake post receives `grant_type=client_credentials`, scope `https://api.ebay.com/oauth/api_scope`, Basic auth header.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (endpoint `https://api.ebay.com/buy/browse/v1/item_summary/search?q=...&filter=buyingOptions:{FIXED_PRICE}&limit=50`, header `X-EBAY-C-MARKETPLACE-ID: EBAY_FR`; queries = watchlist labels + `["carte graphique","processeur","ddr5","ssd nvme"]`). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: source eBay.fr (API Browse, optionnelle)`.

### Task 9: Orchestration `watch.py`

**Files:**
- Create: `watch.py`
- Test: `tests/test_watch.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `run_pass(cfg: dict, watchlist: list[dict], root: Path, *, fetchers: dict[str, Callable[[], list[Listing]]], push: bool, now: datetime) -> dict` (returns payload); CLI `python3 watch.py [--dry] [--no-push] [--verbose]` (`--dry` = fake fetchers from fixtures, implies `--no-push`).

- [ ] **Step 1: Write failing tests**
  - `test_first_run_empty_db_renders`: fetchers returning `[]` → payload with empty lists, all watchlist entries `never_seen`, file written.
  - `test_failing_source_isolated`: one fetcher raises `FetchError`, another raises `xml.etree.ElementTree.ParseError` → both counted as failures, third source's listings present.
  - `test_source_down_after_5`: 5 consecutive failing passes → that source `down` in payload.
  - `test_lock_prevents_overlap`: lock held by another fd → `run_pass` via CLI exits 0 with log "passe déjà en cours" and does nothing.
  - `test_dry_end_to_end`: `--dry` on fixtures → `docs/data/deals.json` valid, no git command run.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Lock `data/watch.lock` via `fcntl.flock(LOCK_EX|LOCK_NB)`; logging to `logs/watch.log` with `RotatingFileHandler(maxBytes=1_000_000, backupCount=3)`; eBay fetcher only if credentials exist (else source `disabled`).
- [ ] **Step 4: Run** full suite `python3 -m unittest discover -s tests -v` → PASS.
- [ ] **Step 5: Commit** `feat: passe complète watch.py (verrou, journal, santé des sources)`.

### Task 10: Static page

**Files:**
- Create: `docs/index.html`, `docs/app.js`, `docs/style.css`, `docs/data/deals.json` (generated by `python3 watch.py --dry`), `docs/.nojekyll`
- Test: manual check + `tests/test_site.py`

**Interfaces:**
- Consumes: `deals.json` schema (spec §4).

- [ ] **Step 1: Write failing test** `tests/test_site.py`: `docs/index.html` exists, references `app.js` and `style.css` relatively, contains no `http://`/`https://` `<script src>` or `<link href>` (no third-party request); `app.js` fetches `data/deals.json` relatively.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** sections from spec §3.7 in French: header (update time in local time, source states, counts), "Ma liste" (badge vert cible atteinte, "modèle jamais vu"), "Opportunités" (sortable columns, filters catégorie + neuf/occasion, suspect rows greyed with "à vérifier"), "Non classées récentes" (`<details>`). All text inserted with `textContent` (no `innerHTML` from data); links `rel="noopener noreferrer"`.
- [ ] **Step 4: Run** test → PASS; then `python3 -m http.server -d docs 8080` and check the page renders the dry-run data on desktop and narrow viewport.
- [ ] **Step 5: Commit** `feat: page GitHub Pages`.

### Task 11: Deployment and README

**Files:**
- Create: `deploy/composants-watch.service`, `deploy/composants-watch.timer`, `README.md`

- [ ] **Step 1: Write** the service (`Type=oneshot`, `WorkingDirectory=%h/composants-watch`, `ExecStart=/usr/bin/python3 %h/composants-watch/watch.py`) and timer (`OnCalendar=*:07,37`, `Persistent=true`).
- [ ] **Step 2: Verify** `systemd-analyze --user verify deploy/composants-watch.service deploy/composants-watch.timer` → no error.
- [ ] **Step 3: Write README** (French): purpose, sources and their limits, how to edit `watchlist.json` (canonical model forms), GitHub setup (create public repo `composants-watch`, Pages on `main` `/docs`, fine-grained token Contents: write on this repo only → `~/.config/composants-watch/token` chmod 600, `git remote add origin https://github.com/<user>/composants-watch.git`), optional eBay key (`ebay.json`), timer install commands (`cp deploy/* ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now composants-watch.timer`).
- [ ] **Step 4: Run** one real pass `python3 watch.py --no-push --verbose` → Dealabs and Reddit `ok`, eBay `disabled`, `docs/data/deals.json` updated.
- [ ] **Step 5: Commit** `docs: déploiement et README`.
