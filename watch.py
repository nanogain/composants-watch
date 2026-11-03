#!/usr/bin/env python3
"""composants-watch — une passe : collecte → normalisation → historique → scores → publication.

Usage : python3 watch.py [--dry] [--no-push] [--verbose]
  --dry      sources simulées (fixtures), base en mémoire, aucune publication
  --no-push  écrit docs/data/deals.json sans git push
"""
from __future__ import annotations

import argparse
import fcntl
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from composants_watch.catalog import build_catalog
from composants_watch.config import load_config, load_watchlist
from composants_watch.http import FetchError
from composants_watch.models import Listing
from composants_watch.normalize import apply
from composants_watch.publish import build_payload, git_push, write_json
from composants_watch.score import make_ref, score
from composants_watch.sources.dealabs import fetch_dealabs, parse_dealabs
from composants_watch.sources.ebay import (GENERIC_QUERIES, ebay_reference, fetch_ebay,
                                           load_credentials)
from composants_watch.sources.reddit import fetch_reddit, parse_reddit
from composants_watch.store import Store

HERE = Path(__file__).resolve().parent
SECRETS = Path.home() / ".config" / "composants-watch"
DEALS_REL = "docs/data/deals.json"
CATALOG_REL = "docs/data/catalog.json"
log = logging.getLogger("composants-watch")


def run_pass(cfg: dict, watchlist: list[dict], root: Path, *,
             fetchers: dict[str, Callable[[], list[Listing]] | None], push: bool,
             now: datetime, db_path: str | None = None,
             token_path: Path = SECRETS / "token") -> dict:
    root = Path(root)
    if db_path is None:
        (root / "data").mkdir(parents=True, exist_ok=True)
        db_path = str(root / "data" / "watch.db")
    store = Store(db_path)
    health: dict[str, dict] = {}
    collected: list[Listing] = []
    for name, fetch in fetchers.items():
        if fetch is None:
            health[name] = {"disabled": True}
            continue
        try:
            items = [apply(li) for li in fetch()]
        except Exception as e:  # une source ne fait jamais tomber la passe
            log.warning("source %s en échec : %s", name, e)
            health[name] = {**store.record_source(name, False, str(e)[:200], now), "items": 0}
            continue
        for li in items:
            store.upsert(li, now)
        collected += items
        health[name] = {**store.record_source(name, True, None, now), "items": len(items)}
        log.info("source %s : %d annonces", name, len(items))

    recent = store.recent_listings(cfg["retention_days"], now)
    ref = make_ref(store, cfg, now, ebay_reference(collected, cfg["ebay_min_listings"]))
    scored = score(recent, store, cfg, watchlist, now, ref=ref)
    catalog = build_catalog(recent, scored, ref, now)
    payload = build_payload(scored, health, now, down_after=cfg["down_after_failures"])
    changed = write_json(payload, root / DEALS_REL)
    write_json(catalog, root / CATALOG_REL)
    log.info("deals.json %s — %d opportunités", "mis à jour" if changed else "inchangé",
             len(payload["opportunities"]))
    if push:
        ok, msg = git_push(root, [DEALS_REL, CATALOG_REL], token_path, now)
        (log.info if ok else log.error)("publication : %s", msg)
    return payload


def real_fetchers(cfg: dict, watchlist: list[dict]) -> dict:
    def dealabs():
        listings, failed = fetch_dealabs(cfg["dealabs_groups"])
        if failed:
            log.warning("dealabs : groupes en échec %s", failed)
            if len(failed) == len(cfg["dealabs_groups"]):
                raise FetchError("tous les groupes Dealabs en échec")
        return listings

    creds = load_credentials(SECRETS / "ebay.json") if cfg["ebay_enabled"] else None
    queries = [w.get("label", w["model"].split(":", 1)[-1]) for w in watchlist] + GENERIC_QUERIES
    return {
        "dealabs": dealabs,
        "reddit": fetch_reddit if cfg["reddit_enabled"] else None,
        "ebay": (lambda: fetch_ebay(queries, creds)) if creds else None,
    }


def dry_fetchers() -> dict:
    fx = HERE / "tests" / "fixtures"
    return {"dealabs": lambda: parse_dealabs((fx / "dealabs_gpu.xml").read_bytes()),
            "reddit": lambda: parse_reddit((fx / "reddit_bapcs.xml").read_bytes()),
            "ebay": None}


def setup_logging(root: Path, verbose: bool) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    log.handlers.clear()
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    fh = logging.handlers.RotatingFileHandler(root / "logs" / "watch.log", maxBytes=1_000_000,
                                              backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    if verbose:
        log.addHandler(logging.StreamHandler(sys.stderr))


def main(argv: list[str] | None = None, root: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description="Veille des composants informatiques")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    root = Path(root or HERE)
    setup_logging(root, args.verbose)
    (root / "data").mkdir(parents=True, exist_ok=True)
    with open(root / "data" / "watch.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.info("passe déjà en cours — abandon")
            return 0
        cfg = load_config(root / "config.json")
        watchlist = load_watchlist(root / "watchlist.json")
        now = datetime.now(timezone.utc)
        if args.dry:
            run_pass(cfg, watchlist, root, fetchers=dry_fetchers(), push=False, now=now,
                     db_path=":memory:")
        else:
            run_pass(cfg, watchlist, root, fetchers=real_fetchers(cfg, watchlist),
                     push=not args.no_push, now=now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
