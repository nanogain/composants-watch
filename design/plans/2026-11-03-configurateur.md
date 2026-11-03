# Catégories + Configurateur Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MON/KBD/COOL/CASE categories with technical attributes, publish `docs/data/catalog.json`, and add a "Configurateur" tab with deterministic compatibility checks.

**Architecture:** Python extracts attributes per listing (`normalize.attributes` + tables in `specs.py`), stores them in SQLite, and publishes a catalog next to `deals.json`. Compatibility rules live in a pure JS module `docs/compat.js` (browser + Node), tested from the Python suite through Node. The page gains two tabs.

**Tech Stack:** Python 3.13 stdlib; vanilla JS; Node (already at `~/.local/bin/node`) for JS tests only.

**Spec:** `design/specs/2026-11-03-configurateur-design.md` (extends `design/specs/2026-11-03-composants-watch-design.md`).

## Global Constraints

- Work only in the worktree `~/composants-watch-dev` (branch `feat/configurateur`); never commit in `~/composants-watch` (production, timer pushes `HEAD:main`).
- Python stdlib only; no npm packages; Node used only by tests (`tests/test_compat.py` skips with a message if `node` is missing).
- New category codes: `MON`, `KBD`, `COOL`, `CASE`; canonical forms exactly as spec §2 (`MON:27-QHD-165Hz`, `KBD:Mécanique-TKL`, `COOL:AIO-360`, `COOL:Air`, `CASE:mATX`).
- Recognition order: exclusions → GPU → CPU → RAM → SSD → PSU → COOL → MON → KBD → CASE → MB.
- New Dealabs groups: `ecrans`, `claviers`, `claviers-gamer`, `ventirad`, `watercooling`, `boitiers-pc`.
- Power: need = CPU `tdp_w` + GPU `tdp_w` (0 if no GPU) + 100; `warn` if PSU watts < need × 1.2; recommended = ceil(need × 1.2 / 50) × 50.
- Statuses: `ok`, `ko`, `unknown`, `warn`. Rules: `socket`, `ddr`, `form`, `cooler`, `power`, `display`.
- Required slots: cpu, mb, ram, ssd, psu, case (+ gpu if CPU `igpu === false`).
- `localStorage` key `cw-config-v1`. Page: `textContent` only, only `https://` links, no third-party request.
- `git_push` publishes exactly `docs/data/deals.json` and `docs/data/catalog.json`.
- Tests: `python3 -m unittest discover -s tests`.

## Review Focus

1. Production `data/watch.db` has no `attrs` column → opening it must migrate (ALTER TABLE) instead of crashing (test in Task 4).
2. Peripheral titles containing exclusion words — "Clavier mécanique pour PC gamer", "Écran PC gamer 27\" 165 Hz" — must still be recognised as KBD/MON, while "PC gamer … RTX 4070" stays excluded (test in Task 2).
3. `catalog.json` missing (first page load before the Pi's next pass) or malformed → configurator shows a message, other tab unaffected (test in Task 7).
4. Corrupted or stale `localStorage` (invalid JSON, unknown slot, id no longer in catalog) → no crash; stale ids shown as "Annonce disparue" (test in Task 7).
5. Monitor/keyboard titles mentioning a GPU or CPU ("Écran 27\" compatible G-Sync pour RTX 4070") must not become GPU listings (test in Task 2).

---

### Task 1: Spec tables and `Listing.attrs`

**Files:**
- Create: `composants_watch/specs.py`
- Modify: `composants_watch/models.py` (add `attrs: dict = field(default_factory=dict)`)
- Test: `tests/test_specs.py`

**Interfaces:**
- Produces: `CHIPSET_SOCKET: dict[str, str]`; `cpu_socket(model: str) -> str | None`; `cpu_tdp(model: str) -> int | None`; `cpu_igpu(model: str) -> bool | None`; `gpu_tdp(model: str) -> int | None`; `chipset_socket(chipset: str) -> str | None`; `socket_ddr(socket: str) -> int | None` (AM5/LGA1851 → 5, AM4 → 4, else None).

- [ ] **Step 1: Write failing tests** `tests/test_specs.py`:
  - `cpu_socket`: `CPU:Ryzen 7 7800X3D`→AM5, `CPU:Ryzen 5 9600X`→AM5, `CPU:Ryzen 5 8600G`→AM5, `CPU:Ryzen 5 5600X`→AM4, `CPU:Core i5-13600KF`→LGA1700, `CPU:Core i3-12100F`→LGA1700, `CPU:Core Ultra 7 265K`→LGA1851, `CPU:Core i7-9700K`→None.
  - `cpu_tdp`: 7800X3D→120, `Ryzen 9 9950X`→170, `Ryzen 5 7600`→65, `Core i9-14900K`→253, `Core i5-13600KF`→181, `Core i5-12400F`→65, `Core Ultra 7 265K`→250, unknown→None.
  - `cpu_igpu`: 7600F→False, 13600KF→False, 12400F→False, `Ryzen 5 5600X`→False, `Ryzen 5 5600G`→True, `Ryzen 7 7800X3D`→True, `Core Ultra 5 245K`→True, `Core Ultra 5 245KF`→False.
  - `chipset_socket`: B650/B650E/X870E/A620→AM5, B550/A520→AM4, B760/Z790/H610→LGA1700, B860/Z890→LGA1851, `H150`→None.
  - `gpu_tdp`: `GPU:RTX 4070 Super`→220, `GPU:RTX 5090`→575, `GPU:RX 9070 XT`→304, `GPU:RX 580`→185, unknown→None.
  - `socket_ddr`: AM5→5, LGA1851→5, AM4→4, LGA1700→None.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_specs -v` → FAIL (import error).
- [ ] **Step 3: Implement** tables (GPU TDP table covering every GPU model the normaliser can emit for RTX 3050–5090, RX 6600–9070 XT, Arc A750/A770/B570/B580; CPU TDP by series/suffix rules of spec §3) and `Listing.attrs`.
- [ ] **Step 4: Run** → PASS; full suite still PASS.
- [ ] **Step 5: Commit** `feat: tables de spécifications (sockets, TDP, iGPU)`.

### Task 2: New categories in `normalize`

**Files:**
- Modify: `composants_watch/normalize.py`, `composants_watch/config.py` (DEFAULTS groups), `config.json`
- Test: `tests/test_normalize.py` (new table `NEW_CASES`), fixtures `tests/fixtures/dealabs_ecrans.xml`, `dealabs_claviers.xml`, `dealabs_ventirad.xml`, `dealabs_boitiers.xml` (recorded with curl like v1)

**Interfaces:**
- Produces: `normalize()` returns new categories/models; unchanged signature.

- [ ] **Step 1: Write failing tests** — at least 8 cases per category from the recorded fixtures plus:
  - `"Écran PC gamer 27\" Samsung Odyssey G5 - QHD 2560x1440, 165 Hz, 1 ms"` → `("MON","MON:27-QHD-165Hz")`; `"Moniteur LG 24GS60F 24\" Full HD 180 Hz IPS"` → `MON:24-FHD-180Hz`; `"Écran 34\" UWQHD 3440x1440 144Hz"` → `MON:34-UWQHD-144Hz`; `"Écran 4K 32 pouces 60 Hz"` → `MON:32-UHD-60Hz`; `"Écran 27\" compatible G-Sync pour RTX 4070"` (no Hz) → `("MON", None)`.
  - `"Clavier mécanique Keychron K8 TKL"` → `KBD:Mécanique-TKL`; `"Clavier gamer mécanique pour PC gamer 75%"` → `KBD:Mécanique-75`; `"Clavier Logitech K120 filaire"` → `KBD:Membrane-Complet`; `"Clavier 60% switch rouges"` → `KBD:Mécanique-60`.
  - `"Ventirad Thermalright Peerless Assassin 120 SE - AM4/AM5/LGA1700"` → `COOL:Air`; `"Watercooling AIO Arctic Liquid Freezer III 360"` → `COOL:AIO-360`; `"Kit watercooling 240 mm"` → `COOL:AIO-240`; `"[Cooler] Zalman CNPS20X Dual-Tower AM5"` → `COOL:Air`.
  - `"Boîtier PC Montech XR - ATX moyen tour"` → `CASE:ATX`; `"Boîtier micro-ATX Jonsbo D31"` → `CASE:mATX`; `"Boîtier Mini-ITX Fractal Terra"` → `CASE:ITX`; `"Boitier PC ASUS Prime AP303 Mesh - ATX"` → `CASE:ATX`; `"Boîtier PC MSI MPG Velox 100R - ATX, Support Vertical pour Carte Graphique"` → `CASE:ATX`.
  - Still excluded: `"PC gamer Ryzen 7 7800X3D RTX 4070 Super boîtier ATX"` → `(None, None)`; `"Souris gamer Logitech G502"` → `(None, None)`; `"Casque gamer HyperX"` → `(None, None)`.
  - Regression: all v1 `CASES` unchanged except the two `Boîtier…` rows, which now map to `CASE:ATX`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_normalize -v` → FAIL.
- [ ] **Step 3: Implement.** Peripheral detection (MON, KBD, COOL, CASE) runs on titles whose trigger word is present; "pc gamer"/"pc fixe" exclusions apply only when no peripheral trigger word starts the title (`^\s*(écran|moniteur|clavier|ventirad|watercooling|boîtier|boitier)` or Reddit prefix `[Monitor]|[Keyboard]|[Cooler]|[Case]`). Remove `bo[iî]tier` and `case\]` from `EXCLUDE`. Map Reddit prefixes `MONITOR→MON`, `KEYBOARD→KBD`, `COOLER→COOL`, `CASE→CASE` in `reddit_category`. Add Dealabs groups.
- [ ] **Step 4: Run** → PASS, full suite PASS.
- [ ] **Step 5: Commit** `feat: catégories écran, clavier, ventirad, boîtier`.

### Task 3: `normalize.attributes`

**Files:**
- Modify: `composants_watch/normalize.py` (`attributes()`, and `apply()` fills `listing.attrs`)
- Test: `tests/test_attributes.py`

**Interfaces:**
- Consumes: `specs.py` (Task 1).
- Produces: `attributes(category: str|None, model: str|None, title: str) -> dict` with keys per spec §3 (`socket`, `tdp_w`, `igpu`, `ddr`, `form`, `watts`, `type`, `sockets`, `max_form`, `inches`, `res`, `hz`, `layout`).

- [ ] **Step 1: Write failing tests:**
  - CPU `Ryzen 7 7800X3D` → `{"socket": "AM5", "tdp_w": 120, "igpu": True}`.
  - MB: `"MSI MAG B650 Tomahawk WiFi"` → `{"socket": "AM5", "ddr": 5, "form": "ATX"}`; `"ASRock B650M Pro RS"` → form mATX; `"Gigabyte B650I Aorus Ultra"` → form ITX; `"MSI PRO B760M-A DDR4"` → `{"socket": "LGA1700", "ddr": 4, "form": "mATX"}`; `"ASUS TUF Z790-Plus WiFi D4"` → ddr 4; `"MSI Z790 Tomahawk"` → no `ddr`, no `form`; `"ASRock B550 Phantom Gaming 4"` → ddr 4.
  - RAM `RAM:DDR5-32Go-6000` → `{"ddr": 5}`.
  - GPU `GPU:RTX 4070 Super` → `{"tdp_w": 220}`.
  - PSU `PSU:850W-Gold` → `{"watts": 850}`.
  - COOL: `"Ventirad … AM4/AM5/LGA1700"` → `{"type": "air", "sockets": ["AM4","AM5","LGA1700"]}`; `"LGA1700/1851"` → sockets include `LGA1851`; no sockets in title → no `sockets` key; AIO → `type "aio"`.
  - CASE `CASE:mATX` → `{"max_form": "mATX"}`.
  - MON `MON:27-QHD-165Hz` → `{"inches": 27, "res": "QHD", "hz": 165}`; KBD `KBD:Mécanique-TKL` → `{"type": "Mécanique", "layout": "TKL"}`.
  - `apply(listing)` sets `listing.attrs`; unrecognised → `{}`.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_attributes -v` → FAIL.
- [ ] **Step 3: Implement.** MB form from title: `-I\b|\bitx\b` → ITX; chipset immediately followed by `M` (`B650M`) or `micro-?atx|m-?atx|\bmatx\b` → mATX; `\be?-?atx\b` → ATX. DDR from title: `ddr4|\bd4\b` → 4, `ddr5|\bd5\b` → 5, else `socket_ddr(socket)`.
- [ ] **Step 4: Run** → PASS, full suite PASS.
- [ ] **Step 5: Commit** `feat: attributs techniques par annonce`.

### Task 4: Store `attrs` with migration

**Files:**
- Modify: `composants_watch/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Produces: `recent_listings()` rows gain `attrs: dict`.

- [ ] **Step 1: Write failing tests:**
  - `test_attrs_round_trip`: upsert listing with `attrs={"socket": "AM5"}` → `recent_listings` row `attrs == {"socket": "AM5"}`; update with new attrs → updated.
  - `test_migrates_v1_database`: create a temp DB with the exact v1 `listings` schema (no `attrs` column) and one row → `Store(path)` opens without error, row readable with `attrs == {}`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** column `attrs TEXT DEFAULT '{}'`, migration via `PRAGMA table_info(listings)` + `ALTER TABLE listings ADD COLUMN attrs TEXT DEFAULT '{}'`, JSON (de)serialisation. **Step 4: Run** → PASS, full suite PASS.
- [ ] **Step 5: Commit** `feat: attributs stockés en SQLite (migration v1)`.

### Task 5: Catalog generation and publication

**Files:**
- Create: `composants_watch/catalog.py`
- Modify: `composants_watch/publish.py` (`git_push(repo, rel_paths: list[str], token_path, now)`), `watch.py` (build + write catalog, push both)
- Test: `tests/test_catalog.py`, `tests/test_publish.py`, `tests/test_watch.py`

**Interfaces:**
- Consumes: `Store.recent_listings` (with attrs), `score()` result (opportunities), `score.is_excluded`.
- Produces: `build_catalog(listings: list[dict], scored: dict, medians: Callable[[str, str], float|None], now: datetime) -> dict` (spec §4 schema); `write_json` reused; `CATALOG_REL = "docs/data/catalog.json"` in `watch.py`.

- [ ] **Step 1: Write failing tests:**
  - `test_catalog_filters`: expired, `model None`, `price_eur None`, price 0, excluded title → absent; valid listing present with `id == "dealabs:<source_id>"`, `effective_eur`, `attrs`.
  - `test_catalog_deal_flag`: listing whose url is in `scored["opportunities"]` → `deal True` and `discount_pct` copied; other → `deal False`, `discount_pct None`.
  - `test_catalog_median`: `median_eur` from the `medians(model, condition)` callable.
  - `test_git_push_publishes_both_files_only` (publish): both files committed, a staged unrelated file is not.
  - `test_watch_writes_catalog` (watch): `run_pass` with a fetcher returning one recognised listing → `docs/data/catalog.json` exists with 1 item.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Move the `ref()` closure of `score()` to a module-level `make_ref(store, cfg: dict, now: datetime, ebay_ref: dict|None) -> Callable[[str, str], float|None]` (cached), used by `score()` and passed by `watch.run_pass` to `build_catalog` as `medians`. `git_push` runs `add`/`diff --cached --quiet`/`commit` with `-- <all paths>`.
- [ ] **Step 4: Run** → PASS, full suite PASS.
- [ ] **Step 5: Commit** `feat: catalogue publié pour le configurateur`.

### Task 6: Compatibility module `docs/compat.js`

**Files:**
- Create: `docs/compat.js`, `tests/compat.test.js`, `tests/test_compat.py`

**Interfaces:**
- Produces (JS): `Compat.evaluate(selection) -> {checks: [{rule, status, message}], missing: [slot], power: {need_w, recommended_w, psu_w} | null}`; `Compat.compatibleWith(item, slot, selection) -> boolean`; `Compat.SLOTS` = `["cpu","mb","ram","gpu","ssd","psu","case","cool","mon","kbd"]`.

- [ ] **Step 1: Write failing tests** in `tests/compat.test.js` (plain `assert`, exits non-zero on failure), launched by `tests/test_compat.py` (`subprocess.run(["node", "tests/compat.test.js"])`, `skipTest` if `shutil.which("node")` is None):
  - socket: AM5/AM5 ok; AM5/AM4 ko with message containing `AM5` and `AM4`; MB socket missing → unknown.
  - ddr: 5/5 ok; RAM 4 + MB 5 ko; MB ddr missing → unknown.
  - form: mATX in ATX ok; ATX in ITX ko; ITX in mATX ok; missing form → unknown.
  - cooler: sockets include CPU socket ok; not included ko; sockets missing → unknown.
  - power: CPU 120 + GPU 220 → need 440, recommended 550; PSU 750 ok; PSU 500 warn; PSU 400 ko; GPU chosen with unknown tdp → unknown; no GPU → need = cpu + 100.
  - display: igpu false + no gpu → ko; igpu false + gpu → no display check; igpu true + no gpu → no display check.
  - missing: empty selection → `["cpu","mb","ram","ssd","psu","case"]`; with igpu-false CPU → includes `gpu`.
  - no check emitted when one side is null.
  - `compatibleWith`: AM4 MB with AM5 CPU selected → false; same socket → true; unknown → true.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_compat -v` → FAIL.
- [ ] **Step 3: Implement** as an IIFE exporting to `module.exports` when defined, else `window.Compat`. Messages in French.
- [ ] **Step 4: Run** → PASS, full suite PASS.
- [ ] **Step 5: Commit** `feat: règles de compatibilité (compat.js)`.

### Task 7: Tabs and configurator UI

**Files:**
- Modify: `docs/index.html`, `docs/app.js`, `docs/style.css`
- Create: `docs/config.js` (configurator UI, uses `Compat`), `tests/fixtures/catalog_demo.json`, `tests/dom_stub.js`, `tests/test_config_ui.py`
- Modify: `tests/test_site.py`

**Interfaces:**
- Consumes: `catalog.json` schema (Task 5), `Compat` (Task 6).

- [ ] **Step 1: Write failing tests:**
  - `test_site.py`: `index.html` has tab buttons "Bonnes affaires" and "Configurateur", loads `compat.js` and `config.js` relatively; no `innerHTML`/`insertAdjacentHTML` in `config.js`; `config.js` fetches `data/catalog.json` relatively.
  - `test_config_ui.py` runs `node tests/dom_stub.js <scenario>` (skip if no node) for scenarios, each printing JSON that the test asserts on:
    - `render`: demo catalog → 10 slot rows, CPU options sorted deals first then price; total 0; missing list has 6 entries.
    - `select`: choose AM5 CPU + AM4 MB → a `socket` check with status `ko`; AM4 MB option in the list prefixed `❌`.
    - `persist`: selection saved under `cw-config-v1`; reload restores it.
    - `stale`: `localStorage` holds an id absent from catalog → row shows "Annonce disparue", total excludes it.
    - `corrupt`: `localStorage` value `"{not json"` → renders empty config, no exception.
    - `catalog_missing`: fetch rejects / 404 → message "Catalogue indisponible", deals tab still rendered.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_site tests.test_config_ui -v` → FAIL.
- [ ] **Step 3: Implement** per spec §6 (tabs with `#config` hash, lazy catalog load, per-slot select + search + link, recap with total / savings / checks / missing / power / GPU-length reminder, "Vider", "Copier la liste" via `navigator.clipboard.writeText` with fallback message). Extend the DOM stub from the v1 check into `tests/dom_stub.js` (createElement, append, replaceChildren, value/options, events, localStorage, fetch).
- [ ] **Step 4: Run** → PASS, full suite PASS.
- [ ] **Step 5: Commit** `feat: onglet Configurateur`.

### Task 8: Real pass, README, merge

**Files:**
- Modify: `README.md` (categories table, configurator section)

- [ ] **Step 1:** In the worktree, `python3 watch.py --no-push --verbose` with a temp copy of the production DB (`cp ~/composants-watch/data/watch.db data/`) → all sources ok, new categories present in `catalog.json`, migration applied; inspect 20 catalog items per new category for false positives and add regression cases to `tests/test_normalize.py` for any found (RED→GREEN).
- [ ] **Step 2:** Update README (new categories and canonical forms, configurator usage and its limits).
- [ ] **Step 3:** Full suite PASS; commit `docs: README configurateur`.
- [ ] **Step 4:** Final review (whole branch), fixes, then merge `feat/configurateur` into `main` from `~/composants-watch` between two timer runs, run the suite there, push `main`, remove the worktree.
