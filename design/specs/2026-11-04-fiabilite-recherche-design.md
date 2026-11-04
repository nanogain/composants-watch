# v3 — Fiabilité des annonces et recherche élargie (eBay.fr)

Date : 2026-11-04. Statut : validé à l'oral (approche), spec à relire.

## 1. Demande

1. « Renforce la fiabilité des annonces affichées » : plusieurs annonces Dealabs
   affichées étaient expirées.
2. « Pour l'onglet principal étant la recherche, d'autres sites fiables, même si ce ne
   sont pas des bonnes affaires ».

Décisions de l'utilisateur :
- source ajoutée : **eBay.fr, API officielle Browse** (gratuite). Keepa et
  l'affiliation marchands sont écartés ;
- affichage : on garde « Ma liste » et « Opportunités » en haut. On ajoute une section
  **« Toutes les annonces »** : champ de recherche, filtres catégorie / neuf-occasion /
  source / prix max, tri par prix, bonnes affaires marquées ★.

## 2. Constats (mesurés le 04/11)

- **Dealabs**
  - Le flux RSS ne signale jamais l'expiration. Sur 343 annonces en base, 0 est
    marquée expirée : la règle actuelle (titre commençant par « [expiré] ») ne
    correspond à rien.
  - La page de l'annonce (`/bons-plans/…-<id>`, autorisée par robots.txt) contient
    exactement un `"isExpired":true|false`, lié au `"threadId":"<id>"`. Une annonce
    supprimée renvoie HTTP 404. Taille environ 70 Kio, réponse en 1 à 2 s.
  - L'expiration ne dépend pas de l'âge.
  - Volume : 196 annonces sur 7 jours, environ 60 nouvelles par jour.
- **eBay Browse**
  - `itemCreationDate` est **absent** des résultats de recherche. Le code actuel lève
    `KeyError` : toute la source eBay échouerait.
  - Sans filtre de catégorie, la recherche ramène des PC complets, des portables, des
    pièces de TV ou de téléphone. Avec `category_ids`, les résultats tombent
    quasiment tous dans la bonne catégorie.
  - `seller.feedbackPercentage` vaut parfois `"0.0"` même avec des centaines
    d'évaluations : la note est alors inconnue.
  - Une annonce peut combiner `FIXED_PRICE` et `AUCTION`. Son prix affiché n'est
    alors pas un vrai prix d'achat immédiat comparable.
  - Les annonces « Pour pièces détachées/ne fonctionne pas » représentent environ
    6 % des cartes graphiques.

## 3. Fiabilité

### 3.1 Vérification Dealabs (nouveau module `composants_watch/liveness.py`)

- À chaque passe, après la collecte, le Pi vérifie la page des annonces Dealabs
  **affichables** :
  - publiées depuis 7 jours au plus (même fenêtre que la rétention) ;
  - non expirées ;
  - classées ou non (la section « Non classées » les affiche aussi).
- Une annonce est **à vérifier** si elle n'a jamais été vérifiée, ou si sa dernière
  vérification réussie date de **3 h** ou plus.
- Ordre de vérification : d'abord les jamais vérifiées, de la plus récente à la plus
  ancienne ; ensuite la vérification la plus ancienne.
- Limites par passe :
  - au plus **80 pages** ;
  - au plus **240 s** de vérification ;
  - arrêt après **3 échecs consécutifs** (Dealabs indisponible ou bloquant).
- On garde l'espacement de 2 s par hôte et le User-Agent explicite de `http_get`.
- Résultat de chaque page :
  - `isExpired` vaut true → annonce marquée expirée, horodatée vérifiée ;
  - `isExpired` vaut false → annonce marquée active, horodatée vérifiée ;
  - HTTP 404 ou 410 → annonce marquée expirée (supprimée), horodatée vérifiée ;
  - autre erreur, ou page sans `isExpired` → rien ne change, ce n'est pas une
    vérification. L'échec compte pour l'arrêt après 3 échecs ; une page sans
    indicateur compte comme un échec.
- Règle d'affichage, appliquée à un seul endroit (`Store.recent_listings`) : une
  annonce Dealabs n'est affichée que si elle est **non expirée et vérifiée active
  depuis moins de 6 h**. Ça couvre la liste, les opportunités, les non classées, le
  catalogue et le configurateur.
  - Conséquence assumée : si Dealabs bloque les vérifications, ses annonces
    disparaissent de la page au bout de 6 h. On préfère rien à une annonce expirée.
- Santé de la vérification : elle est enregistrée comme une source à part,
  `dealabs_verif`, dans `source_health` (OK si au moins une page a été vérifiée, ou
  s'il n'y avait rien à vérifier). Elle est affichée dans la liste des sources sous
  le nom « Vérification Dealabs ».
  - Son compteur `items` donne le nombre de pages vérifiées pendant la passe.

### 3.2 Base de données

- Nouvelle colonne `listings.checked_at TEXT` (NULL par défaut), ajoutée par migration
  en place, comme `attrs` en v2.
- `upsert` ne doit plus remettre à zéro une expiration Dealabs posée par la
  vérification : pour `dealabs`, `expired = MAX(listings.expired, excluded.expired)`.
  Pour les autres sources, `expired` prend la valeur collectée, comme aujourd'hui :
  une annonce eBay qui réapparaît redevient active.
- Nouvelles méthodes :
  - `Store.to_check(now, days, recheck_hours, limit) -> list[tuple[source_id, url]]` ;
  - `Store.mark_checked(source, source_id, expired, now)`, qui écrit `expired` dans
    les deux sens ;
  - `Store.expire_missing(source, seen_ids, now)` (§ 3.3).

### 3.3 eBay : seulement ce qui est en ligne

- Après une passe eBay **entièrement réussie** (toutes les requêtes OK), toute
  annonce eBay non expirée absente des résultats est marquée expirée.
- Si une requête échoue, toute la source est en échec et on n'expire rien. C'est le
  comportement actuel : l'exception remonte.
- Une annonce sortie des résultats sans être terminée (poussée hors du top par de
  nouvelles annonces) disparaît aussi. C'est voulu : on n'affiche que ce qu'on a vu
  au dernier passage.
- Si elle réapparaît, `upsert` la réactive (`expired = 0`, cf. § 3.2).

### 3.4 Reddit

- Le flux ne signale pas la fin d'un bon plan. Reddit n'est plus affiché que
  **48 h** après sa publication (contre 7 jours).
- Clé de configuration `reddit_display_hours: 48`.

## 4. eBay.fr comme source d'annonces normales

### 4.1 Requêtes

Une requête par catégorie, restreinte par `category_ids`, `limit` 50 :

| Catégorie | Requête (`q`) | `category_ids` |
|---|---|---|
| GPU | carte graphique | 27386 |
| CPU | processeur | 164 |
| RAM | ddr4 ddr5 → deux requêtes : `ddr4`, `ddr5` | 170083 |
| SSD | ssd | 175669 |
| MB | carte mère | 1244 |
| PSU | alimentation pc | 42017 |
| CASE | boitier pc | 42014 |
| COOL | ventirad | 131486 |
| COOL | watercooling | 131503 |
| MON | écran pc | 80053 |
| KBD | clavier | 33963 |

- S'y ajoute une requête par entrée de `watchlist.json` (son `label`), avec le
  `category_ids` de la catégorie du modèle (préfixe `GPU:` → 27386, etc.).
- Total : 12 requêtes plus la liste, toutes les 30 minutes, soit environ 700 appels
  par jour. Le quota gratuit est de 5 000 par jour.
- Filtre API : `buyingOptions:{FIXED_PRICE},deliveryCountry:FR`.

### 4.2 Annonces gardées (`parse_ebay`)

Une annonce est gardée seulement si toutes ces conditions sont réunies :
- `buyingOptions` ne contient pas `AUCTION` ;
- prix en EUR ;
- `conditionId` différent de 7000 (pour pièces) ;
- `itemLocation.country` dans l'Union européenne (les 27 codes ISO) ;
- vendeur fiable : `sellerAccountType == "BUSINESS"`, ou
  `feedbackPercentage >= 98` **et** `feedbackScore >= 50`. Un pourcentage `"0.0"`
  ou absent est une note inconnue : le vendeur est refusé, sauf s'il est
  professionnel.

Autres règles :
- `posted_at` : `itemCreationDate` s'il est présent, sinon l'heure de la passe.
  L'upsert garde la première valeur, car `posted_at` n'est pas mis à jour en conflit.
- État :
  - `conditionId` 1000 → `new` ;
  - tous les autres → `used`. Le texte d'état reconditionné reste soumis aux
    exclusions de score existantes, qui portent sur le titre.
- Marchand :
  - `"eBay · <vendeur> (pro)"` pour un professionnel ;
  - `"eBay · <vendeur> (99,2 %, 1 234 avis)"` sinon.

### 4.3 Effets sur le score

- Les prix eBay entrent dans l'historique et les médianes, comme les autres sources.
  Les références se construisent plus vite, surtout en occasion.
- Une annonce eBay peut devenir une opportunité selon les règles actuelles (−15 %,
  suspect au-delà de −70 %).
- `ebay_reference` reste la référence de secours pour le neuf.

## 5. Section « Toutes les annonces »

- Données : `docs/data/catalog.json`, déjà publié et utilisé par le configurateur.
  Pas de nouveau fichier.
  - Le catalogue contient les annonces **classées** dans une catégorie, déjà
    filtrées par la règle d'affichage du § 3.1.
  - Aucun horodatage de vérification n'y est publié, pour ne pas changer le fichier
    à chaque passe. La page explique la règle dans une phrase sous le titre :
    « Annonces Dealabs vérifiées actives il y a moins de 6 h ; eBay : vendeurs
    fiables, expédition depuis l'UE. »
- Emplacement : onglet principal, après « Opportunités », avant « Non classées ».
- Contrôles :
  - texte libre ;
  - catégorie ;
  - neuf / occasion ;
  - source (Dealabs, eBay, Reddit) ;
  - prix maximum en €.
- Recherche :
  - insensible à la casse et aux accents ;
  - tous les mots saisis doivent apparaître dans le titre ou le modèle canonique.
- Tri : prix effectif croissant. Les bonnes affaires sont marquées ★.
- Affichage :
  - au plus **200 lignes**, avec « N résultats, 200 affichés : affine la
    recherche » au-delà ;
  - colonnes : ★, titre (lien), catégorie et état, prix (port compris), médiane,
    marchand, source, âge.
- Logique pure dans `docs/search.js` (`normalizeText`, `matches`, `filterItems`),
  testée sous node comme `compat.js`. Le rendu (`docs/app.js`) utilise textContent
  uniquement et des liens https uniquement, comme aujourd'hui.

## 6. Configuration (nouvelles clés, avec valeurs par défaut)

| Clé | Défaut |
|---|---|
| `verify_max_pages` | 80 |
| `verify_budget_s` | 240 |
| `verify_recheck_hours` | 3 |
| `verify_visible_hours` | 6 |
| `reddit_display_hours` | 48 |
| `ebay_limit` | 50 |

## 7. Erreurs et limites

- Durée d'une passe :
  - collecte Dealabs environ 30 s ;
  - eBay environ 12 requêtes (un autre hôte, sans attente croisée) ;
  - vérification ≤ 240 s.
  Le total reste sous le `TimeoutStartSec=600` du service.
- La vérification n'est jamais fatale : toute exception est journalisée et marque
  `dealabs_verif` en échec. La passe publie quand même.
- Si les identifiants eBay sont absents ou refusés (401), la source est en échec,
  comme aujourd'hui. Le reste continue.
- La taille de `catalog.json` passe d'environ 100 à environ 700 annonces, soit à peu
  près 300 Kio. C'est acceptable pour GitHub Pages. Le fichier n'est réécrit que si
  son contenu change.

## 8. Tests

- `liveness` :
  - extraction de `isExpired` (vrai, faux, absent) sur des extraits de pages réelles
    dans les fixtures ;
  - 404 donne une expiration ;
  - autres erreurs ignorées ;
  - arrêt après 3 échecs ;
  - plafond de pages et de durée (horloge injectée) ;
  - ordre de priorité.
- `store` :
  - migration `checked_at` ;
  - `MAX` sur `expired` pour Dealabs, remise à 0 pour eBay ;
  - `to_check` ;
  - `mark_checked` ;
  - `expire_missing` ;
  - règle d'affichage (Dealabs vérifiée moins de 6 h, Reddit 48 h).
- `ebay` :
  - fixture refaite à partir d'une **vraie réponse** (anonymisée), sans
    `itemCreationDate` ;
  - filtres enchère, pour pièces, pays, vendeur (pro, 98 %/50, `"0.0"`) ;
  - libellé marchand ;
  - requêtes avec `category_ids`.
- `watch` :
  - passe complète avec vérification simulée ;
  - expiration des eBay absents seulement si eBay est OK ;
  - santé `dealabs_verif`.
- `search.js` (node) :
  - accents et casse ;
  - tous les mots ;
  - filtres ;
  - prix max ;
  - tri ;
  - plafond de 200.
- Page :
  - section présente ;
  - aucune insertion HTML brute ;
  - script chargé.

## 9. Hors périmètre

- Autres sites marchands (pas d'API publique, ou API réservée aux partenaires).
- Vérification des annonces Reddit (pas d'information disponible).
- Pagination eBay au-delà de 50 résultats par requête.
