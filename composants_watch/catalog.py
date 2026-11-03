"""Catalogue des annonces sélectionnables dans le configurateur (docs/data/catalog.json)."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from .publish import _iso
from .score import is_excluded


def build_catalog(listings: list[dict], scored: dict, medians: Callable[[str, str], float | None],
                  now: datetime, version: int = 1) -> dict:
    deals = {o["url"]: o.get("discount_pct") for o in scored.get("opportunities", [])}
    items = []
    for r in listings:
        if r["expired"] or r["category"] is None or r["price_eur"] is None:
            continue
        eff = round(r["price_eur"] + (r["shipping_eur"] or 0.0), 2)
        if eff <= 0 or is_excluded(r["title"]):
            continue
        items.append({
            "id": f"{r['source']}:{r['source_id']}", "category": r["category"], "model": r["model"],
            "title": r["title"], "condition": r["condition"], "effective_eur": eff,
            "median_eur": medians(r["model"], r["condition"]) if r["model"] else None,
            "deal": r["url"] in deals, "discount_pct": deals.get(r["url"]),
            "attrs": r.get("attrs") or {}, "merchant": r["merchant"], "source": r["source"],
            "url": r["url"], "posted_at": r["posted_at"],
        })
    items.sort(key=lambda i: (i["category"], i["effective_eur"]))
    return {"generated_at": _iso(now), "version": version, "items": items}
