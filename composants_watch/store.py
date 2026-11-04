"""Historique SQLite local : annonces, observations de prix, santé des sources."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings(
  source TEXT, source_id TEXT, url TEXT, title TEXT, model TEXT, category TEXT,
  condition TEXT, merchant TEXT, price_raw TEXT, currency TEXT, posted_at TEXT,
  first_seen TEXT, last_seen TEXT, expired INTEGER DEFAULT 0, attrs TEXT DEFAULT '{}',
  checked_at TEXT, attempted_at TEXT, PRIMARY KEY(source, source_id));
CREATE TABLE IF NOT EXISTS observations(
  source TEXT, source_id TEXT, ts TEXT, price_eur REAL, shipping_eur REAL);
CREATE INDEX IF NOT EXISTS obs_key ON observations(source, source_id, ts);
CREATE TABLE IF NOT EXISTS source_health(
  source TEXT PRIMARY KEY, consecutive_failures INTEGER, last_ok TEXT, last_error TEXT);
"""

_LATEST = """
SELECT o.price_eur, o.shipping_eur FROM observations o
WHERE o.source=? AND o.source_id=? ORDER BY o.ts DESC, o.rowid DESC LIMIT 1
"""


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(listings)")}
        if "attrs" not in cols:  # base v1 : migration en place, données conservées
            self.db.execute("ALTER TABLE listings ADD COLUMN attrs TEXT DEFAULT '{}'")
            from .normalize import attributes  # rétro-remplissage : pas de ❔ pendant 7 jours
            for r in self.db.execute("SELECT source, source_id, category, model, title FROM listings").fetchall():
                self.db.execute("UPDATE listings SET attrs=? WHERE source=? AND source_id=?",
                                (json.dumps(attributes(r["category"], r["model"], r["title"]), ensure_ascii=False),
                                 r["source"], r["source_id"]))
            self.db.commit()
        for col in ("checked_at", "attempted_at"):  # base v2 : jamais vérifiée
            if col not in cols:
                self.db.execute(f"ALTER TABLE listings ADD COLUMN {col} TEXT")
        self.db.commit()

    def upsert(self, li: Listing, now: datetime) -> None:
        ts = now.isoformat()
        self.db.execute(
            """INSERT INTO listings(source, source_id, url, title, model, category, condition,
                 merchant, price_raw, currency, posted_at, first_seen, last_seen, expired, attrs)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source, source_id) DO UPDATE SET
                 url=excluded.url, title=excluded.title, model=excluded.model,
                 category=excluded.category, condition=excluded.condition,
                 merchant=excluded.merchant, price_raw=excluded.price_raw,
                 last_seen=excluded.last_seen,
                 expired=CASE WHEN listings.source='dealabs'
                   THEN MAX(listings.expired, excluded.expired) ELSE excluded.expired END,
                 attrs=excluded.attrs""",
            (li.source, li.source_id, li.url, li.title, li.model, li.category,
             li.condition, li.merchant, li.price_raw, li.currency,
             li.posted_at.isoformat(), ts, ts, int(li.expired), json.dumps(li.attrs, ensure_ascii=False)))
        if li.price_eur is not None:
            last = self.db.execute(_LATEST, (li.source, li.source_id)).fetchone()
            if last is None or (last["price_eur"], last["shipping_eur"]) != (li.price_eur, li.shipping_eur):
                self.db.execute("INSERT INTO observations VALUES(?,?,?,?,?)",
                                (li.source, li.source_id, ts, li.price_eur, li.shipping_eur))
        self.db.commit()

    def recent_listings(self, days: int, now: datetime, visible_hours: float | None = None,
                        reddit_hours: float | None = None) -> list[dict]:
        """Annonces récentes ; visible_hours / reddit_hours appliquent la règle d'affichage v3."""
        since = (now - timedelta(days=days)).isoformat()
        sql = """SELECT * FROM listings WHERE
                 ((source IN ('dealabs','reddit') AND first_seen >= ? AND posted_at >= ?)
                 OR (source NOT IN ('dealabs','reddit') AND last_seen >= ?))"""
        args: list = [since, since, since]
        if visible_hours is not None:
            sql += " AND (source != 'dealabs' OR (expired = 0 AND checked_at >= ?))"
            args.append((now - timedelta(hours=visible_hours)).isoformat())
        if reddit_hours is not None:
            sql += " AND (source != 'reddit' OR posted_at >= ?)"
            args.append((now - timedelta(hours=reddit_hours)).isoformat())
        rows = self.db.execute(sql + " ORDER BY first_seen DESC", args)
        out = []
        for r in rows.fetchall():
            d = dict(r)
            d["expired"] = bool(d["expired"])
            d["attrs"] = json.loads(d.get("attrs") or "{}")
            last = self.db.execute(_LATEST, (d["source"], d["source_id"])).fetchone()
            d["price_eur"] = last["price_eur"] if last else None
            d["shipping_eur"] = last["shipping_eur"] if last else None
            out.append(d)
        return out

    def to_check(self, now: datetime, days: int, recheck_hours: float, limit: int) -> list[tuple[str, str]]:
        """Annonces Dealabs à (re)vérifier : jamais vérifiées (plus récentes d'abord), puis les plus anciennes."""
        rows = self.db.execute(
            """SELECT source_id, url FROM listings
               WHERE source='dealabs' AND expired=0 AND posted_at >= ?
                 AND (checked_at IS NULL OR checked_at < ?)
                 AND (attempted_at IS NULL OR attempted_at < ?)
               ORDER BY checked_at IS NOT NULL, CASE WHEN checked_at IS NULL THEN posted_at END DESC,
                        checked_at ASC
               LIMIT ?""",
            ((now - timedelta(days=days)).isoformat(),
             (now - timedelta(hours=recheck_hours)).isoformat(),
             (now - timedelta(hours=recheck_hours)).isoformat(), limit))
        return [(r["source_id"], r["url"]) for r in rows.fetchall()]

    def mark_checked(self, source: str, source_id: str, expired: bool, now: datetime) -> None:
        self.db.execute("UPDATE listings SET expired=?, checked_at=? WHERE source=? AND source_id=?",
                        (int(expired), now.isoformat(), source, source_id))
        self.db.commit()

    def mark_attempt(self, source: str, source_id: str, now: datetime) -> None:
        """Vérification sans conclusion : l'annonce repasse en fin de file jusqu'à la prochaine revérification."""
        self.db.execute("UPDATE listings SET attempted_at=? WHERE source=? AND source_id=?",
                        (now.isoformat(), source, source_id))
        self.db.commit()

    def expire_missing(self, source: str, seen_ids: set[str], now: datetime) -> int:
        """Marque expirées les annonces de `source` absentes de la dernière collecte réussie."""
        n = 0
        for r in self.db.execute("SELECT source_id FROM listings WHERE source=? AND expired=0",
                                 (source,)).fetchall():
            if r["source_id"] not in seen_ids:
                self.db.execute("UPDATE listings SET expired=1 WHERE source=? AND source_id=?",
                                (source, r["source_id"]))
                n += 1
        self.db.commit()
        return n

    def observations(self, model: str, condition: str, since: datetime,
                     exclude=None) -> list[tuple[str, str, float]]:
        rows = self.db.execute(
            """SELECT l.source, l.source_id, l.title FROM listings l
               WHERE l.model=? AND l.condition=? AND l.last_seen >= ?
                 AND (l.source NOT IN ('dealabs','reddit') OR l.posted_at >= ?)""",
            (model, condition, since.isoformat(), since.isoformat())).fetchall()
        out = []
        for r in rows:
            if exclude and exclude(r["title"]):
                continue
            last = self.db.execute(_LATEST, (r["source"], r["source_id"])).fetchone()
            if last:
                out.append((r["source"], r["source_id"],
                            round(last["price_eur"] + (last["shipping_eur"] or 0.0), 2)))
        return out

    def record_source(self, source: str, ok: bool, error: str | None, now: datetime) -> dict:
        cur = self.db.execute("SELECT * FROM source_health WHERE source=?", (source,)).fetchone()
        fails = 0 if ok else (cur["consecutive_failures"] if cur else 0) + 1
        last_ok = now.isoformat() if ok else (cur["last_ok"] if cur else None)
        self.db.execute("INSERT OR REPLACE INTO source_health VALUES(?,?,?,?)",
                        (source, fails, last_ok, None if ok else error))
        self.db.commit()
        return {"consecutive_failures": fails, "last_ok": last_ok, "last_error": None if ok else error}

    def source_health(self) -> dict[str, dict]:
        return {r["source"]: {"consecutive_failures": r["consecutive_failures"],
                              "last_ok": r["last_ok"], "last_error": r["last_error"]}
                for r in self.db.execute("SELECT * FROM source_health")}
