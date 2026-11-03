# composants-watch — Spécification de conception

Date : 2026-11-03 · Statut : à valider par l'utilisateur

## 1. Objectif

Algorithme **entièrement déterministe** (aucun LLM) qui tourne sur le Raspberry Pi,
écoute le marché des composants informatiques (GPU, CPU, RAM, SSD, carte mère,
alimentation) sur des sources fiables et autorisées, et repère des **opportunités
d'achat pour usage personnel**. Résultat publié sur une page **GitHub Pages**.

Critère de succès : la page affiche, mise à jour toutes les ~30 min, (a) l'état de ma
liste de composants suivis vs mes prix cibles, (b) les annonces nettement sous le prix
habituel de leur modèle, sans faux positifs grossiers (pièces HS, boîtes vides, lots).

### Décisions de l'utilisateur
- Usage : achat personnel (pas de calcul de marge de revente).
- Sources : Dealabs (RSS), eBay.fr (API officielle Browse), Reddit r/buildapcsales (Atom).
  leboncoin exclu (CGU interdisant l'extraction automatique, anti-robots).
- Référence de prix : mixte — watchlist avec prix cible + découverte automatique par
  décote vs médiane observée.
- Publication : dépôt **public** sur le compte GitHub de l'utilisateur ; la watchlist
  et les prix cibles sont publics.
- Alertes : aucune (page web seulement).
- Architecture : approche 1 — le Pi collecte, GitHub Pages affiche.

### Hypothèses (validées implicitement, modifiables)
- Prix en euros ; les annonces Reddit (USD) sont affichées à titre indicatif et
  n'alimentent pas les médianes. Pas de conversion USD→EUR.
- Cadence : une passe toutes les 30 min.
- eBay désactivé tant qu'aucune clé n'est configurée ; le reste fonctionne sans.

## 2. Architecture

```
systemd --user timer (30 min)
  └─ watch.py  (une passe, verrou fichier)
       ├─ sources/dealabs.py ─┐
       ├─ sources/reddit.py  ─┼─► annonces brutes normalisées (Listing)
       ├─ sources/ebay.py    ─┘
       ├─ normalize.py   → catégorie + modèle canonique + état (neuf/occasion)
       ├─ store.py       → SQLite local (data/watch.db) : annonces + observations
       ├─ score.py       → cibles watchlist, médianes 30 j, décotes, drapeaux
       └─ publish.py     → docs/data/deals.json → git commit + push (si changé)
GitHub Pages (dossier /docs) : index.html + app.js + style.css lisent deals.json
```

Python 3.13, **bibliothèque standard uniquement** (urllib, xml.etree, sqlite3, json,
re, statistics, unittest). Pas de dépendance externe.

### Arborescence
```
composants-watch/
  watch.py               point d'entrée (--dry, --no-push, --verbose)
  composants_watch/
    __init__.py
    http.py              GET avec timeout, User-Agent explicite, 2 retries 5xx/réseau
    models.py            dataclass Listing
    sources/dealabs.py   flux RSS par groupe
    sources/reddit.py    flux Atom r/buildapcsales
    sources/ebay.py      API Browse (OAuth client credentials) — optionnel
    normalize.py         reconnaissance catégorie/modèle par règles
    store.py             SQLite
    score.py             calculs déterministes
    publish.py           génération JSON + git
  config.json            seuils, sources, cadence (versionné)
  watchlist.json         composants suivis + prix cibles (versionné, public)
  docs/                  site GitHub Pages (index.html, app.js, style.css, data/deals.json)
  tests/                 unittest + fixtures (échantillons RSS/Atom/JSON réels)
  deploy/composants-watch.service, .timer   (installés par l'utilisateur)
  design/specs/          ce document (hors /docs pour ne pas être publié comme page)
  data/  logs/           non versionnés (.gitignore)
```

## 3. Composants

### 3.1 Listing (models.py)
`source, source_id, url, title, price_eur | None, price_raw, currency, shipping_eur | None,
merchant, condition ("new"|"used"|"unknown"), posted_at (UTC), expired (bool),
category | None, model | None, image_url | None`.

### 3.2 Sources
- **Dealabs** : `https://www.dealabs.com/rss/groupe/<slug>` pour les groupes listés
  dans `config.json` (ex. `cartes-graphiques`, `ssd`, `processeurs`, `memoire-vive`,
  `cartes-meres`, `alimentations-pc`, `informatique`). Prix et marchand lus dans
  `<pepper:merchant name=".." price="67,63€">` ; repli sur le `<strong>` de la
  description. État = `new` (sauf « reconditionné » → `used`). Les slugs sont
  vérifiés à l'implémentation ; un slug en 404 est journalisé et ignoré.
- **Reddit** : `https://www.reddit.com/r/buildapcsales/new/.rss`. Catégorie lue dans
  le préfixe `[GPU]`, `[RAM]`… ; prix `$…` → `currency="USD"`, `price_eur=None`.
- **eBay.fr** : API Browse `item_summary/search`, marketplace `EBAY_FR`, catégories
  composants, filtre `buyingOptions:{FIXED_PRICE}`, requêtes = modèles de la
  watchlist + catégories génériques. Jeton OAuth « client credentials » à partir de
  `~/.config/composants-watch/ebay.json` (`client_id`, `client_secret`). Absent →
  source « désactivée ». Neuf/occasion via `condition`.
- Politesse : 1 requête / 2 s par hôte, timeout 20 s, User-Agent
  `composants-watch/<version> (usage personnel)`.

### 3.3 Normalisation (normalize.py)
Règles ordonnées, déterministes, testées :
- **GPU** : `RTX 3060..5090 (Ti|Super)?`, `RX 6600..9070 (XT|XTX)?`, `Arc A/B…` →
  `GPU:RTX 4070 Super`.
- **CPU** : `Ryzen [3579] \d{4}(X3D|X|G|F)?`, `Core i[3579]-\d{4,5}[KFS]*`,
  `Core Ultra [579] \d{3}[KF]*` → `CPU:Ryzen 7 7800X3D`.
- **RAM** : type `DDR4|DDR5`, capacité totale (`2x16 Go` → 32), fréquence →
  `RAM:DDR5-32Go-6000` (CL non discriminant).
- **SSD** : interface `NVMe|SATA`, capacité `To/Go/TB/GB` → `SSD:NVMe-2To`.
- **Carte mère** : chipset `B650|X670|B760|Z790|…` → `MB:B650`.
- **Alimentation** : puissance + certification → `PSU:850W-Gold`.
- Non reconnu → `category` éventuellement connue, `model=None` (« non classée »).

### 3.4 Stockage (store.py) — SQLite `data/watch.db`
- `listings(source, source_id, url, title, model, category, condition, merchant,
  first_seen, last_seen, expired, PRIMARY KEY(source, source_id))`
- `observations(source, source_id, ts, price_eur, shipping_eur)` — une ligne
  seulement si le prix change (pas de doublon à prix identique).
- `source_health(source, consecutive_failures, last_ok, last_error)`.

### 3.5 Scores (score.py)
- **Prix effectif** = `price_eur + (shipping_eur or 0)`.
- **Exclusions des médianes** (titre, insensible à la casse) : `hs`, `pour pièces`,
  `défectueux`, `boîte vide`, `box only`, `lot de`, `mining`, `reconditionné`,
  `ne fonctionne pas`. Ces annonces restent visibles mais sans décote.
- **Médiane de référence** par `(model, condition)` sur 30 jours : dernier prix
  effectif de chaque annonce distincte. Valide si ≥ 5 observations et ≥ 2 annonces
  distinctes. Sinon, si eBay est actif, médiane des annonces eBay neuves « achat
  immédiat » du jour (≥ 3) ; sinon « sans référence ».
- **Opportunité** si :
  - *Cible* : modèle dans la watchlist et prix effectif ≤ prix cible ;
  - *Décote* : prix effectif ≤ médiane × (1 − `discount_min`), `discount_min` = 0,15.
- **Suspect** : décote > `suspect_above` (0,70) → drapeau, non classé en tête.
- **Tri** : cible d'abord, puis décote décroissante ; suspects en fin.
- **Rétention** : annonces de moins de 7 jours ; deals Dealabs expirés retirés.

### 3.6 Publication (publish.py)
- Écrit `docs/data/deals.json` (schéma §4). Écriture atomique (fichier temporaire
  + rename).
- Si le contenu (hors horodatage) a changé : `git add docs/data/deals.json` →
  commit « data: mise à jour <UTC> » → `git push` via HTTPS avec le jeton à droits
  réduits (`~/.config/composants-watch/token`, mode 600, jamais versionné, transmis
  par en-tête et non dans l'URL enregistrée).
- Échec du push : journalisé, retenté à la passe suivante.

### 3.7 Page (docs/)
HTML/CSS/JS statique, en français, mobile, sans traceur ni appel tiers :
- En-tête : dernière mise à jour, état de chaque source, nombre d'annonces.
- « Ma liste » : par composant suivi, meilleur prix actuel, prix cible, médiane 30 j,
  badge vert si cible atteinte.
- « Opportunités » : tableau triable et filtrable (catégorie, neuf/occasion) —
  décote, prix, marchand, source, âge, lien.
- « Non classées récentes » : liste repliée.

## 4. Schéma `deals.json`
```json
{
  "generated_at": "2026-11-03T18:00:00Z",
  "version": 1,
  "sources": {"dealabs": {"status": "ok|down|disabled", "items": 0, "last_ok": "..."}},
  "watchlist": [{"model": "GPU:RTX 4070 Super", "label": "...", "target_eur": 550,
                 "best": {"price_eur": 0, "url": "...", "merchant": "...", "source": "..."} ,
                 "median_30d": 0, "target_hit": false}],
  "opportunities": [{"title": "...", "model": "...", "category": "GPU", "condition": "new",
                     "price_eur": 0, "shipping_eur": 0, "effective_eur": 0, "median_eur": 0,
                     "discount_pct": 0, "target_hit": false, "suspect": false,
                     "merchant": "...", "source": "dealabs", "url": "...", "posted_at": "..."}],
  "unclassified": [{"title": "...", "price_raw": "...", "source": "...", "url": "...", "posted_at": "..."}],
  "stats": {"listings_seen": 0, "models_with_reference": 0}
}
```

## 5. Configuration
- `config.json` : `dealabs_groups[]`, `reddit_enabled`, `ebay_enabled`,
  `discount_min` (0,15), `suspect_above` (0,70), `median_window_days` (30),
  `median_min_obs` (5), `retention_days` (7), `down_after_failures` (5).
- `watchlist.json` : `[{"model": "GPU:RTX 4070 Super", "label": "RTX 4070 Super",
  "target_eur": 550}]` — `model` doit suivre la forme canonique de §3.3.

## 6. Gestion des erreurs
- Timeout + 2 retries (5xx / réseau) par requête ; jamais de crash de la passe à
  cause d'une source.
- 5 échecs consécutifs → source « en panne » sur la page.
- Verrou fichier (`data/watch.lock`, `fcntl.flock`) : deux passes ne se chevauchent pas.
- Journal `logs/watch.log` avec rotation (`logging.handlers.RotatingFileHandler`).
- Annonce mal formée : ignorée et comptée, jamais bloquante.

## 7. Tests (unittest, sans réseau)
- Parsing Dealabs/Reddit/eBay sur fixtures réelles enregistrées.
- Normalisation : table de titres réels → modèle attendu (≥ 40 cas, toutes catégories).
- Scores : médianes, seuils min d'observations, exclusions, cible, suspects, tri.
- Store : dédoublonnage à prix identique, nouvelle observation à prix changé.
- Publication : JSON conforme au schéma, pas de commit si contenu inchangé.
- Bout-en-bout `--dry --no-push` avec sources simulées.

## 8. Exploitation
- `deploy/composants-watch.service` + `.timer` (OnCalendar `*:07,37`), à installer par
  l'utilisateur dans `~/.config/systemd/user/`.
- Mise en place GitHub par l'utilisateur : créer le dépôt public `composants-watch`,
  activer Pages sur `main:/docs`, créer le jeton à droits réduits (Contents: write,
  ce dépôt seulement).
- Optionnel : clé développeur eBay.

## 9. Hors périmètre (v1)
leboncoin et toute source sans accès autorisé ; alertes ; graphiques d'historique
long terme ; conversion USD→EUR ; calcul de marge de revente.
