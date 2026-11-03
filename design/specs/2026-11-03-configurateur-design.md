# composants-watch — Nouvelles catégories et configurateur

Date : 2026-11-03 · Statut : à valider par l'utilisateur
Complète : `design/specs/2026-11-03-composants-watch-design.md` (v1, en production).

## 1. Objectif

1. Ajouter les catégories **écran, clavier, ventirad (air + AIO), boîtier** (la carte
   mère existe déjà).
2. Ajouter un onglet **« Configurateur »** : composer une configuration à partir de
   **toutes les annonces récentes reconnues** (prix en euros), avec prix total et
   **contrôles de compatibilité sous forme d'alertes** (✅ / ❌ / ❔ / ⚠️).

### Décisions de l'utilisateur
- Choix parmi toutes les annonces récentes reconnues (opportunités mises en avant).
- Compatibilité en alertes : tout reste sélectionnable ; ❔ quand l'information manque.
- Design validé en trois parties (catégories/attributs, règles, onglet).

### Hypothèses
- Écran et clavier : aucune règle, ils s'ajoutent au total.
- Configuration gardée dans le navigateur (`localStorage`), pas de compte.
- Décote moins fiable pour les nouvelles catégories (prix très dispersés) : elles
  servent surtout au configurateur et à la watchlist.

## 2. Nouvelles catégories (normalize.py)

| Code | Modèle canonique | Exemple |
|---|---|---|
| `MON` | `MON:<pouces>-<déf>-<Hz>Hz`, déf ∈ FHD, QHD, UHD, UWQHD, UWFHD | `MON:27-QHD-165Hz` |
| `KBD` | `KBD:<Mécanique\|Membrane>-<Complet\|TKL\|75\|65\|60>` | `KBD:Mécanique-TKL` |
| `COOL` | `COOL:Air` ou `COOL:AIO-<120\|240\|280\|360\|420>` | `COOL:AIO-360` |
| `CASE` | `CASE:<ATX\|mATX\|ITX>` (plus grand format accepté) | `CASE:ATX` |

- Mots déclencheurs : écran/moniteur/monitor ; clavier/keyboard ; ventirad/
  refroidissement processeur/watercooling/AIO/cpu cooler ; boîtier/case/tour moyen.
- Définition : 1920×1080 / 1080p / Full HD → FHD ; 2560×1440 / 1440p / QHD / WQHD → QHD ;
  3840×2160 / 4K / UHD → UHD ; 3440×1440 → UWQHD ; 2560×1080 → UWFHD.
- Format clavier : TKL / tenkeyless / 80 % → TKL ; 75 % ; 65 % ; 60 % ; sinon Complet.
  Type : mécanique / mechanical / switch → Mécanique, sinon Membrane.
- Boîtier : E-ATX / ATX / moyen tour / grand tour → ATX ; micro-ATX / mATX / M-ATX → mATX ;
  mini-ITX / ITX → ITX ; inconnu → modèle `None`, catégorie `CASE`.
- Les exclusions existantes (PC complets, portables, accessoires…) restent prioritaires.
  « boîtier » n'est plus une exclusion ; un titre de PC complet contenant « boîtier »
  reste exclu par « pc gamer », « pc fixe »… Souris, casques, manettes restent ignorés.
- Ordre de reconnaissance : exclusions → GPU → CPU → RAM → SSD → PSU → COOL → MON → KBD →
  CASE → MB (la carte mère reste en dernier pour éviter ses faux positifs).
- Nouveaux groupes Dealabs (`config.json`) : `ecrans`, `claviers`, `claviers-gamer`,
  `ventirad`, `watercooling`, `boitiers-pc`.

## 3. Attributs techniques (specs.py + normalize.py)

`Listing` gagne `attrs: dict` (clé absente = inconnue). Calculé par
`normalize.attributes(category, model, title) -> dict`, tables dans
`composants_watch/specs.py` :

- **CPU** : `socket`, `tdp_w`, `igpu` (bool).
  - Ryzen 7000/8000/9000 → AM5 ; Ryzen 5000/3000 → AM4 ; Core i 12e–14e gén. → LGA1700 ;
    Core Ultra 2xx → LGA1851.
  - `tdp_w` : table par série/suffixe (ex. X3D 120, Ryzen 7/9 X 170, Ryzen 5 65 ; Core
    i9 K 253, i7 K 253, i5 K 181, non-K 65 ; Core Ultra K 250, sinon 65). Valeurs dans
    `specs.py`, testées.
  - `igpu` : False si suffixe F/KF (Intel) ou F (AMD), ou Ryzen 5000/3000 sans G ;
    True sinon.
- **MB** : `socket` (chipset → table : A620/B650/B650E/X670/X670E/B850/X870/X870E → AM5 ;
  A520/B450/B550/X570 → AM4 ; H610/B660/H670/Z690/B760/Z790 → LGA1700 ;
  H810/B860/Z890 → LGA1851), `ddr` (titre « DDR4 »/« D4 »/« DDR5 »/« D5 » ; sinon AM5 et
  LGA1851 → 5, AM4 → 4 ; sinon inconnu), `form` (titre : « -I »/« ITX » → ITX ;
  « M » collé au chipset ou « micro-ATX »/« mATX »/« M-ATX » → mATX ; « ATX »/« E-ATX » →
  ATX ; sinon inconnu).
- **RAM** : `ddr` (4 ou 5).
- **GPU** : `tdp_w` (table par modèle reconnu ; inconnu sinon).
- **PSU** : `watts`.
- **COOL** : `type` (air/aio), `sockets` (liste lue dans le titre parmi AM4, AM5,
  LGA1700, LGA1851, LGA1200 ; « LGA1700/1851 » étendu ; sinon inconnu).
- **CASE** : `max_form` (ATX ⊃ mATX ⊃ ITX).
- **MON / KBD** : attributs du modèle (`inches`, `res`, `hz` / `type`, `layout`).

## 4. Catalogue (`docs/data/catalog.json`)

Publié à chaque passe avec `deals.json` (même logique : réécrit et commité seulement
si le contenu change) :

```json
{"generated_at": "…Z", "version": 1,
 "items": [{"id": "dealabs:3443093", "category": "GPU", "model": "GPU:RX 9070 XT",
            "title": "…", "condition": "new", "effective_eur": 649.0, "median_eur": 699.0,
            "deal": true, "discount_pct": 7.2, "attrs": {"tdp_w": 304},
            "merchant": "LDLC", "source": "dealabs", "url": "https://…", "posted_at": "…"}]}
```

- Contenu : annonces récentes (rétention v1), non expirées, `model` reconnu, prix
  effectif > 0 en euros, titre non exclu. `deal` = présente dans les opportunités.
- `attrs` persistés en SQLite (colonne `attrs` JSON dans `listings`).
- `publish.git_push` publie les deux fichiers (`docs/data/deals.json`,
  `docs/data/catalog.json`) et rien d'autre.

## 5. Règles de compatibilité (`docs/compat.js`)

Module JS pur, sans DOM, exporté pour le navigateur (`window.Compat`) et Node
(`module.exports`). `evaluate(selection) -> {checks: [...], missing: [...], power: {...}}`.
`selection` : `{cpu, mb, ram, gpu, ssd, psu, case, cool, mon, kbd}` (items du catalogue
ou `null`). Chaque contrôle : `{rule, status: "ok"|"ko"|"unknown"|"warn", message}`,
évalué seulement si les deux pièces concernées sont choisies.

| Règle | ko | unknown |
|---|---|---|
| `socket` CPU ↔ MB | sockets différents | socket inconnu d'un côté |
| `ddr` RAM ↔ MB | DDR différents | DDR carte mère inconnu |
| `form` MB ↔ CASE | format MB > `max_form` | format inconnu d'un côté |
| `cooler` COOL ↔ CPU | socket CPU absent de `sockets` | `sockets` inconnu |
| `power` PSU ↔ (CPU, GPU) | watts < besoin ; `warn` si watts < besoin × 1,2 | TDP CPU ou GPU (si GPU choisi) inconnu |
| `display` CPU sans GPU | `igpu` false et pas de GPU | — |

- Besoin = `tdp_w` CPU + `tdp_w` GPU (0 sans GPU) + 100 W ; recommandé = besoin × 1,2
  arrondi aux 50 W supérieurs.
- `missing` : parmi cpu, mb, ram, ssd, psu, case (+ gpu si `igpu` false) les
  emplacements vides.
- `power` : `{need_w, recommended_w, psu_w}`.
- `compatibleWith(item, selection) -> boolean` : faux si l'ajout de `item` produirait au
  moins un `ko` (sert à marquer ❌ dans les listes).

## 6. Onglet « Configurateur » (docs/)

- Onglets « Bonnes affaires » / « Configurateur » ; onglet actif dans le hash
  (`#config`). `catalog.json` chargé à la première ouverture.
- Emplacements : Processeur, Carte mère, Mémoire, Carte graphique, Stockage,
  Alimentation, Boîtier, Ventirad, Écran (option), Clavier (option).
- Par emplacement : liste déroulante (bonnes affaires « ★ −x % » d'abord, puis prix
  croissant ; incompatibles préfixées ❌ et en fin), champ de recherche, lien « Voir
  l'annonce ».
- Récapitulatif : total, économie vs médianes (somme de `median_eur − effective_eur`
  quand `median_eur` connu), contrôles avec icône et message, pièces manquantes,
  puissance, rappel longueur GPU / hauteur ventirad.
- Persistance `localStorage` (clé `cw-config-v1`, map emplacement → `{id, title,
  effective_eur}`) ; annonce absente du catalogue → « Annonce disparue : … (ancien prix) »
  + bouton remplacer, exclue du total.
- Boutons « Vider la configuration », « Copier la liste » (presse-papiers, texte).
- Mêmes règles de sécurité que v1 : `textContent` uniquement, liens `https://` seuls,
  aucun appel tiers.

## 7. Tests

- Python : table de titres réels par nouvelle catégorie (≥ 8 cas chacune, dont des
  non-composants), `attributes()` pour chaque catégorie, tables `specs.py`, colonne
  `attrs` en SQLite, `catalog.json` (contenu, filtres, `deal`), publication des deux
  fichiers seulement.
- Node (lancé par `tests/test_compat.py`, ignoré avec message si `node` absent) : chaque
  règle × chaque statut, puissance, `missing`, `compatibleWith`.
- Page : test statique (onglets, `compat.js` relatif, pas d'`innerHTML`, pas d'appel
  tiers) + exécution d'`app.js` sur DOM simulé avec un catalogue de démonstration.

## 8. Déploiement

Développement dans le worktree `~/composants-watch-dev` (branche
`feat/configurateur`) : le dossier de production `~/composants-watch` reste sur `main`,
car le timer y publie `HEAD:main` toutes les 30 min. Fusion dans `main` à la fin.

## 9. Hors périmètre

Partage par lien, plusieurs configurations, longueur GPU / hauteur ventirad, souris et
casques, détection de cartes mères DDR4/DDR5 au-delà du titre et du chipset.
