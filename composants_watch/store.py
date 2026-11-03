"""Historique SQLite local : annonces, observations de prix, santé des sources."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings(
  source TEXT, source_id TEXT, url TEXT, title TEXT, model TEXT, category TEXT,
  condition TEXT, merchant TEXT, price_raw TEXT, currency TEXT, posted_at TEXT,
  first_seen TEXT, last_seen TEXT, expired INTEGER DEFAULT 0,
  PRIMARY KEY(source, source_id));
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

    def upsert(self, li: Listing, now: datetime) -> None:
        ts = now.isoformat()
        self.db.execute(
            """INSERT INTO listings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source, source_id) DO UPDATE SET
                 url=excluded.url, title=excluded.title, model=excluded.model,
                 category=excluded.category, condition=excluded.condition,
                 merchant=excluded.merchant, price_raw=excluded.price_raw,
                 last_seen=excluded.last_seen, expired=excluded.expired""",
            (li.source, li.source_id, li.url, li.title, li.model, li.category,
             li.condition, li.merchant, li.price_raw, li.currency,
             li.posted_at.isoformat(), ts, ts, int(li.expired)))
        if li.price_eur is not None:
            last = self.db.execute(_LATEST, (li.source, li.source_id)).fetchone()
            if last is None or (last["price_eur"], last["shipping_eur"]) != (li.price_eur, li.shipping_eur):
                self.db.execute("INSERT INTO observations VALUES(?,?,?,?,?)",
                                (li.source, li.source_id, ts, li.price_eur, li.shipping_eur))
        self.db.commit()

    def recent_listings(self, days: int, now: datetime) -> list[dict]:
        since = (now - timedelta(days=days)).isoformat()
        rows = self.db.execute(
            """SELECT * FROM listings WHERE
                 (source IN ('dealabs','reddit') AND first_seen >= ? AND posted_at >= ?)
                 OR (source NOT IN ('dealabs','reddit') AND last_seen >= ?)
               ORDER BY first_seen DESC""", (since, since, since))
        out = []
        for r in rows.fetchall():
            d = dict(r)
            d["expired"] = bool(d["expired"])
            last = self.db.execute(_LATEST, (d["source"], d["source_id"])).fetchone()
            d["price_eur"] = last["price_eur"] if last else None
            d["shipping_eur"] = last["shipping_eur"] if last else None
            out.append(d)
        return out

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
