# composants-watch

Veille **entièrement déterministe** (aucun LLM) du marché des composants PC : cartes
graphiques, processeurs, mémoire vive, SSD, cartes mères, alimentations. Elle tourne
sur un Raspberry Pi et publie les bonnes affaires sur une page GitHub Pages.

Une annonce est signalée si :
- **cible atteinte** : le composant est dans `watchlist.json` et son prix (port compris)
  est inférieur ou égal à ton prix cible ;
- **décote** : son prix est au moins 15 % sous la médiane des prix observés sur 30 jours
  pour le même modèle et le même état (neuf ou occasion). Il faut au moins 5 prix observés.

Une décote de plus de 70 % est marquée « à vérifier » (erreur de reconnaissance
probable, ou arnaque). Les annonces « HS », « pour pièces », « boîte vide », « lot de »,
« mining » ou « reconditionné » ne comptent jamais.

## Sources

| Source | Accès | Remarques |
|---|---|---|
| Dealabs | flux RSS publics par groupe | neuf, modéré par la communauté |
| Reddit r/buildapcsales | flux Atom public | marché US, prix en dollars, affichés à titre indicatif |
| eBay.fr | API officielle Browse | optionnelle, nécessite une clé développeur gratuite |

leboncoin n'est pas utilisé : ses CGU interdisent l'extraction automatique.

## Fonctionnement

```
python3 watch.py            une passe complète, avec publication git
python3 watch.py --no-push  une passe sans publication
python3 watch.py --dry      sources simulées (fixtures), base en mémoire, sans publication
python3 -m unittest discover -s tests -v
```

L'historique des prix est dans `data/watch.db` (SQLite, reste sur le Pi). Seul
`docs/data/deals.json` est publié. Le journal est dans `logs/watch.log`.
Les réglages (seuils, groupes Dealabs) sont dans `config.json`.

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

Un modèle mal écrit apparaît sur la page avec le badge « modèle jamais vu ».

## Mise en place de GitHub (une fois)

1. Sur GitHub, crée un dépôt **public** nommé `composants-watch`, vide.
2. Crée un jeton à droits réduits : *Settings → Developer settings → Personal access
   tokens → Fine-grained tokens*. Accès au seul dépôt `composants-watch`, permission
   **Contents : Read and write**, rien d'autre.
3. Sur le Pi :
   ```bash
   mkdir -p ~/.config/composants-watch
   ( umask 077; cat > ~/.config/composants-watch/token )   # colle le jeton, Entrée, puis Ctrl+D
   cd ~/composants-watch
   git remote add origin https://github.com/<ton-compte>/composants-watch.git
   python3 watch.py --verbose
   ```
   La première passe pousse la branche `main`.
4. Sur GitHub : *Settings → Pages → Build and deployment → Deploy from a branch*,
   branche `main`, dossier `/docs`. La page est ensuite disponible sur
   `https://<ton-compte>.github.io/composants-watch/`.

Le jeton n'est jamais écrit dans le dépôt ni dans `.git/config` : il est transmis à
`git push` par en-tête, à chaque passe.

## eBay (optionnel)

Crée une application sur <https://developer.ebay.com> (clés *Production*), puis :

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
