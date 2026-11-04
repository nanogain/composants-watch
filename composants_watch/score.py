"""Calcul déterministe des opportunités : cibles de la watchlist et décotes vs médiane."""
from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta

EXCLUDE_RE = re.compile(
    r"\bhs\b|pour\s*pi[eè]ces|d[ée]fectueu|bo[iî]te\s*vide|box\s*only|\blot\s*de\b|"
    r"\bmining\b|reconditionn|ne\s*fonctionne\s*pas", re.IGNORECASE)

UNCLASSIFIED_MAX = 50
IMPLAUSIBLE_VS_TARGET = 0.30   # cible « atteinte » à moins de 30 % du prix cible = accessoire probable


BROAD_CATEGORIES = {"KBD", "COOL", "CASE"}  # pas de décote : seule la cible de la liste compte


def is_excluded(title: str) -> bool:
    return bool(EXCLUDE_RE.search(title or ""))


def reference_median(obs: list[tuple[str, str, float]], min_obs: int) -> float | None:
    obs = [o for o in obs if o[2] > 0]
    if len(obs) < min_obs or len({(s, i) for s, i, _ in obs}) < 2:
        return None
    return round(statistics.median(p for _, _, p in obs), 2)


def _scorable(eff: float | None) -> bool:
    return eff is not None and eff > 0


def _effective(row: dict) -> float | None:
    if row["price_eur"] is None:
        return None
    return round(row["price_eur"] + (row["shipping_eur"] or 0.0), 2)


def make_ref(store, cfg: dict, now: datetime, ebay_ref: dict[str, float] | None = None):
    """Médiane de référence (model, condition) mise en cache : locale, sinon eBay."""
    since = now - timedelta(days=cfg["median_window_days"])
    refs: dict[tuple[str, str], float | None] = {}

    def ref(model: str, condition: str) -> float | None:
        key = (model, condition)
        if key not in refs:
            local = reference_median(store.observations(model, condition, since, exclude=is_excluded),
                                     cfg["median_min_obs"])
            refs[key] = local if local is not None else (ebay_ref or {}).get(f"{model}|{condition}")
        return refs[key]

    ref.cache = refs
    return ref


def score(listings: list[dict], store, cfg: dict, watchlist: list[dict], now: datetime,
          ebay_ref: dict[str, float] | None = None, ref=None) -> dict:
    since = now - timedelta(days=cfg["median_window_days"])
    targets = {w["model"]: float(w["target_eur"]) for w in watchlist}
    ref = ref or make_ref(store, cfg, now, ebay_ref)
    refs = ref.cache

    live = [r for r in listings if not r["expired"]]
    opportunities, unclassified = [], []
    for r in live:
        if r["model"] is None or r["price_eur"] is None:
            unclassified.append({"title": r["title"], "price_raw": r["price_raw"], "source": r["source"],
                                 "url": r["url"], "posted_at": r["posted_at"]})
            continue
        eff = _effective(r)
        if not _scorable(eff) or is_excluded(r["title"]):
            continue
        median = ref(r["model"], r["condition"])
        discount = round((1 - eff / median) * 100, 1) if median else None
        target = targets.get(r["model"])
        target_hit = target is not None and eff <= target
        if r["category"] in BROAD_CATEGORIES:  # même modèle canonique, produits trop différents
            discount = None
        if not target_hit and (discount is None or discount < cfg["discount_min"] * 100):
            continue
        suspect = ((discount is not None and discount > cfg["suspect_above"] * 100)
                   or (target_hit and eff < IMPLAUSIBLE_VS_TARGET * target))
        opportunities.append({
            "title": r["title"], "model": r["model"], "category": r["category"],
            "condition": r["condition"], "price_eur": r["price_eur"], "shipping_eur": r["shipping_eur"],
            "effective_eur": eff, "median_eur": median, "discount_pct": discount,
            "target_hit": target_hit,
            "suspect": suspect,
            "merchant": r["merchant"], "source": r["source"], "url": r["url"], "posted_at": r["posted_at"],
        })
    opportunities.sort(key=lambda o: (o["suspect"], not o["target_hit"], -(o["discount_pct"] or 0)))

    wl = []
    for w in watchlist:
        model = w["model"]
        target = float(w["target_eur"])
        cands = [r for r in live if r["model"] == model and _scorable(_effective(r))
                 and not is_excluded(r["title"]) and _effective(r) >= IMPLAUSIBLE_VS_TARGET * target]
        best = min(cands, key=_effective, default=None)
        median = ref(model, "new")
        wl.append({
            "model": model, "label": w.get("label", model), "target_eur": float(w["target_eur"]),
            "best": None if best is None else {"price_eur": _effective(best), "url": best["url"],
                                               "merchant": best["merchant"], "source": best["source"]},
            "median_30d": median,
            "target_hit": best is not None and _effective(best) <= float(w["target_eur"]),
            "never_seen": best is None and not store.observations(model, "new", since)
                          and not store.observations(model, "used", since),
        })

    return {
        "watchlist": wl,
        "opportunities": opportunities,
        "unclassified": unclassified[:UNCLASSIFIED_MAX],
        "stats": {"listings_seen": len(listings),
                  "models_with_reference": len({m for (m, _), v in refs.items() if v is not None})},
    }
