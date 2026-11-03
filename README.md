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

Chaque passe publie uniquement `docs/data/deals.json`, sur `main`, et seulement si
son contenu a changé.

Variante sans SSH : un remote `https://` avec un jeton à droits réduits (*Fine-grained
token*, permission *Contents: Read and write* sur ce seul dépôt) dans
`~/.config/composants-watch/token` (mode 600). Le jeton est transmis à `git push` par
l'environnement, jamais écrit dans le dépôt ni dans `.git/config`.

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
