from __future__ import annotations

import json
from pathlib import Path

DEFAULTS = {
    "dealabs_groups": ["cartes-graphiques", "processeurs", "ram", "ssd",
                       "cartes-meres", "alimentation-pc", "informatique",
                       "ecrans", "claviers", "claviers-gamer", "ventirad", "watercooling",
                       "boitiers-pc"],
    "reddit_enabled": True,
    "ebay_enabled": True,
    "discount_min": 0.15,
    "suspect_above": 0.70,
    "median_window_days": 30,
    "median_min_obs": 5,
    "ebay_min_listings": 3,
    "retention_days": 7,
    "down_after_failures": 5,
    "verify_max_pages": 80,
    "verify_budget_s": 240,
    "verify_recheck_hours": 3,
    "verify_visible_hours": 6,
    "reddit_display_hours": 48,
    "ebay_limit": 50,
}


def load_config(path="config.json") -> dict:
    cfg = dict(DEFAULTS)
    p = Path(path)
    if p.exists():
        cfg.update(json.loads(p.read_text(encoding="utf-8")))
    return cfg


def load_watchlist(path="watchlist.json") -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))
