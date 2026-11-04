# composants-watch

Veille **entièrement déterministe** (aucun LLM côté Pi) du marché des composants PC : cartes
graphiques, processeurs, mémoire vive, SSD, cartes mères, alimentations, ventirads et
AIO, boîtiers, écrans et claviers. Elle tourne
sur un Raspberry Pi et publie les bonnes affaires sur une page GitHub Pages. Seul le
configurateur propose, en option et dans ton navigateur, un conseiller IA (voir plus bas).

Une annonce est signalée si :
- **cible atteinte** : le composant est dans `watchlist.json` et son prix (port compris)
  est inférieur ou égal à ton prix cible ;
- **décote** : son prix est au moins 15 % sous la médiane des prix observés sur 30 jours
  pour le même modèle et le même état (neuf ou occasion). Il faut au moins 5 prix observés.

Pour les claviers, ventirads et boîtiers, seule la cible de `watchlist.json` compte : un
même modèle canonique (« clavier membrane complet », « ventirad ») couvre des produits trop
différents pour qu'une décote ait un sens.

Une décote de plus de 70 % est marquée « à vérifier » (erreur de reconnaissance
probable, ou arnaque). Les annonces « HS », « pour pièces », « boîte vide », « lot de »,
« mining » ou « reconditionné » ne comptent jamais.

## Sources

| Source | Accès | Remarques |
|---|---|---|
| Dealabs | flux RSS publics par groupe | neuf, modéré par la communauté |
| Reddit r/buildapcsales | flux Atom public | marché US, prix en dollars, affichés à titre indicatif |
| eBay.fr | API officielle Browse | annonces normales, filtrées (voir Fiabilité) ; clé développeur gratuite |

leboncoin n'est pas utilisé : ses CGU interdisent l'extraction automatique.

## Fiabilité des annonces affichées

- **Dealabs** : le flux RSS n'indique pas les bons plans expirés. À chaque passe, le Pi
  lit la page de l'annonce (indicateur `isExpired`) : au plus 80 pages et 240 s par
  passe, 2 s entre deux pages, arrêt après 3 échecs consécutifs. Chaque annonce est
  revérifiée toutes les 3 h. Une annonce n'est affichée que si elle a été **vérifiée
  active il y a moins de 6 h** ; une annonce supprimée (404) ou fusionnée dans une autre
  est retirée. L'état de cette vérification apparaît dans les sources (« Vérification
  Dealabs »).
- **eBay.fr** : une requête par catégorie (restreinte à la catégorie eBay) et une par
  composant de `watchlist.json`, 50 résultats chacune. Ne sont gardées que les annonces
  à prix fixe (sans enchère), hors « pour pièces », livrables en France et expédiées
  depuis l'Union européenne, d'un vendeur **professionnel** ou ayant **au moins 98 %
  d'avis positifs sur au moins 50 évaluations**. Une annonce absente du dernier passage
  réussi disparaît de la page.
- **Reddit** : aucune information d'expiration ; affiché 48 h après publication.

## Fonctionnement

```
python3 watch.py            une passe complète, avec publication git
python3 watch.py --no-push  une passe sans publication
python3 watch.py --dry      sources simulées (fixtures), base en mémoire, sans publication
python3 -m unittest discover -s tests -v
```

L'historique des prix est dans `data/watch.db` (SQLite, reste sur le Pi). Seul
`docs/data/deals.json` est publié. Le journal est dans `logs/watch.log`.
Les réglages sont dans `config.json` (valeurs par défaut dans `composants_watch/config.py`) :

| Clé | Défaut | Rôle |
|---|---|---|
| `discount_min` / `suspect_above` | 0,15 / 0,70 | décote minimale, décote « à vérifier » |
| `retention_days` | 7 | durée de vie d'une annonce |
| `verify_max_pages` / `verify_budget_s` | 80 / 240 | plafonds de vérification Dealabs par passe |
| `verify_recheck_hours` / `verify_visible_hours` | 3 / 6 | revérification, fraîcheur exigée pour l'affichage |
| `reddit_display_hours` | 48 | durée d'affichage Reddit |
| `ebay_enabled` / `ebay_limit` | true / 50 | source eBay, résultats par requête |

Au démarrage, la base est vide : les décotes n'apparaissent qu'une fois l'historique
construit (quelques jours selon les modèles). Les prix cibles fonctionnent dès la
première passe.

## Ma liste (`watchlist.json`)

```json
[{"model": "GPU:RTX 4070 Super", "label": "RTX 4070 Super", "target_eur": 550}]
```

`model` doit suivre la forme canonique produite par l'algorithme :

| Catégorie | Exemple |
|---|---|
| Carte graphique | `GPU:RTX 4070 Super`, `GPU:RTX 5070 Ti`, `GPU:RX 9070 XT`, `GPU:Arc B580` |
| Processeur | `CPU:Ryzen 7 7800X3D`, `CPU:Core i5-13600KF`, `CPU:Core Ultra 7 265K` |
| Mémoire | `RAM:DDR5-32Go-6000`, `RAM:DDR4-16Go-3200` |
| SSD | `SSD:NVMe-2To`, `SSD:SATA-1To`, `SSD:NVMe-500Go` |
| Carte mère | `MB:B650`, `MB:Z790`, `MB:X870E` |
| Alimentation | `PSU:850W-Gold`, `PSU:1000W-Platinum` |
| Ventirad / AIO | `COOL:Air`, `COOL:AIO-360` |
| Boîtier | `CASE:ATX`, `CASE:mATX`, `CASE:ITX` (plus grand format accepté) |
| Écran | `MON:27-QHD-165Hz` (pouces, FHD/QHD/UHD/UWQHD/UWFHD/DQHD, fréquence) |
| Clavier | `KBD:Mécanique-TKL`, `KBD:Membrane-Complet` (Complet, TKL, 75, 65, 60) |

Pour les ventirads, boîtiers, écrans et claviers, les prix d'une même description varient
beaucoup : la détection de décote y est moins fiable, ces catégories servent surtout au
configurateur et à la liste.

Un modèle mal écrit apparaît sur la page avec le badge « modèle jamais vu ».

## Toutes les annonces

Sous « Opportunités », la section **Toutes les annonces** permet de chercher dans toutes
les annonces fiables reconnues (`docs/data/catalog.json`), bonnes affaires ou non :
texte libre (sans accents ni majuscules, tous les mots doivent apparaître), catégorie,
neuf/occasion, source et prix maximum. Tri par prix croissant, 200 lignes au plus ;
les bonnes affaires sont marquées ★.

## Configurateur

L'onglet **Configurateur** de la page permet de composer une configuration avec toutes les
annonces récentes reconnues (`docs/data/catalog.json`, publié à chaque passe). Les bonnes
affaires sont marquées « ★ » en tête de liste. Les contrôles sont déterministes :

| Contrôle | Règle |
|---|---|
| Socket | processeur et carte mère (chipset → socket : B650 → AM5, B550 → AM4, Z790 → LGA1700…) |
| Mémoire | DDR4/DDR5 de la RAM = celle de la carte mère (titre, sinon AM5/LGA1851 → DDR5, AM4 → DDR4) |
| Format | carte mère (ATX, mATX, ITX) ≤ format maximal du boîtier |
| Ventirad | sockets indiqués dans le titre du ventirad |
| Alimentation | besoin ≈ TDP processeur + TDP carte graphique + 100 W ; ⚠️ si marge < 20 % |
| Affichage | processeur sans graphique intégré (F, KF, Ryzen 5000 sans G) sans carte graphique |

❔ signale une information absente du titre : à vérifier sur la fiche du produit, comme la
longueur de la carte graphique et la hauteur du ventirad (non vérifiées). Les tables de
sockets et de consommation sont dans `composants_watch/specs.py`. La configuration est
gardée dans le navigateur ; une annonce disparue est signalée et exclue du total.

### Conseiller IA (option)

Le bloc **Générer avec l'IA** demande à Claude une configuration pour
un budget et un usage (bureautique, jeu 1080p/1440p/4K, création, développement),
choisie **uniquement parmi les annonces du catalogue**, pour la tour : processeur, carte
mère, mémoire, carte graphique, stockage, alimentation, boîtier, ventirad. L'écran et le
clavier restent ceux que tu as choisis.

- **Ta clé, ton navigateur** : l'appel part directement de la page vers l'API Anthropic
  avec ta clé personnelle (<https://console.anthropic.com>). Elle est gardée dans le
  `localStorage` de ton navigateur (bouton « Oublier la clé »), jamais publiée ni envoyée
  au Pi. La page ne charge aucun script tiers.
- **Modèle et coût** (à la charge de ta clé, estimation par génération) : Opus 5.5 par
  défaut (≈ 0,10 à 0,30 €), Sonnet 5.5 (≈ 0,05 à 0,15 €) ou Haiku 5.5 (≈ 0,01 €, choix
  moins sûrs, donc plus souvent une seconde demande). Le choix est retenu dans le
  navigateur.
- **Données envoyées** : le budget, l'usage et, pour chaque annonce de la tour, son
  identifiant, son modèle, un titre court, son prix, son état et ses caractéristiques
  connues.
- **Revérification** : la proposition passe par les mêmes contrôles que le configurateur
  (annonce existante et dans la bonne catégorie, socket, DDR, format, alimentation,
  budget, total recalculé depuis le catalogue). En cas de problème, une seconde et
  dernière demande est faite avec la liste des problèmes ; une proposition encore non
  conforme est affichée avec un avertissement.
- Rien ne change dans ta configuration tant que tu ne cliques pas sur **Appliquer**.

## Mise en place de GitHub (une fois)

Dépôt : <https://github.com/nanogain/composants-watch> (public).

Le Pi publie avec une **clé de déploiement** SSH limitée à ce seul dépôt :

1. Clé dédiée sur le Pi :
   ```bash
   ssh-keygen -t ed25519 -N "" -C "composants-watch deploy" -f ~/.ssh/composants_watch_deploy
   cat ~/.ssh/composants_watch_deploy.pub
   ```
2. Sur GitHub : *Settings → Deploy keys → Add deploy key*, coller la clé publique,
   cocher **Allow write access**.
3. Dans le dépôt local :
   ```bash
   cd ~/composants-watch
   git remote add origin git@github.com:nanogain/composants-watch.git
   git config core.sshCommand "ssh -i ~/.ssh/composants_watch_deploy -o IdentitiesOnly=yes -o BatchMode=yes"
   python3 watch.py --verbose
   ```
4. Sur GitHub : *Settings → Pages → Build and deployment → Deploy from a branch*,
   branche `main`, dossier `/docs`. La page est ensuite disponible sur
   <https://nanogain.github.io/composants-watch/>.

Chaque passe publie uniquement `docs/data/deals.json` et `docs/data/catalog.json`, sur
`main`, et seulement si leur contenu a changé.

Variante sans SSH : un remote `https://` avec un jeton à droits réduits (*Fine-grained
token*, permission *Contents: Read and write* sur ce seul dépôt) dans
`~/.config/composants-watch/token` (mode 600). Le jeton est transmis à `git push` par
l'environnement, jamais écrit dans le dépôt ni dans `.git/config`.

## eBay

Crée une application sur <https://developer.ebay.com> et des clés **Production** (pas
*Sandbox*) ; pour activer le jeu de clés, déclare l'exemption de la notification de
suppression de compte (« I do not persist eBay data »). Puis :

```bash
( umask 077; cat > ~/.config/composants-watch/ebay.json <<'JSON'
{"client_id": "TON-APP-ID", "client_secret": "TON-CERT-ID"}
JSON
)
```

La source eBay s'active à la passe suivante.

## Exécution automatique (toutes les 30 minutes)

```bash
mkdir -p ~/.config/systemd/user
cp ~/composants-watch/deploy/composants-watch.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now composants-watch.timer
systemctl --user list-timers composants-watch.timer
```

Arrêt : `systemctl --user disable --now composants-watch.timer`.
