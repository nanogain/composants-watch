"""Vérification des annonces Dealabs : lit "isExpired" sur la page de chaque annonce affichable."""
from __future__ import annotations

import re
import time
from datetime import datetime

from .http import FetchError, http_get

_EXPIRED = re.compile(r'"isExpired":(true|false)')
_GONE = ("HTTP 404", "HTTP 410")
_CANONICAL = re.compile(r'<link rel="canonical" href="[^"]*-(\d+)"')


def parse_expired(html: str, thread_id: str) -> bool | None:
    """True/False si la page est celle de l'annonce `thread_id` et porte l'indicateur ;
    True aussi si l'annonce a été fusionnée dans une autre ; None si on ne peut pas conclure."""
    if f'"threadId":"{thread_id}"' not in html:
        c = _CANONICAL.search(html)  # doublon fusionné : Dealabs redirige vers une autre annonce
        return True if c and c.group(1) != thread_id else None
    m = _EXPIRED.search(html)
    return None if m is None else m.group(1) == "true"


def verify_dealabs(store, now: datetime, cfg: dict, get=http_get, clock=time.monotonic) -> dict:
    todo = store.to_check(now, cfg["retention_days"], cfg["verify_recheck_hours"], 10**6)
    res = {"checked": 0, "expired": 0, "failures": 0, "stopped": None}
    start, streak = clock(), 0
    for n, (sid, url) in enumerate(todo):
        if n >= cfg["verify_max_pages"]:
            res["stopped"] = "pages"
            break
        if clock() - start >= cfg["verify_budget_s"]:
            res["stopped"] = "budget"
            break
        try:
            expired = parse_expired(get(url).decode("utf-8", "replace"), sid)
        except FetchError as e:
            expired = True if any(g in str(e) for g in _GONE) else None
        if expired is None:
            store.mark_attempt("dealabs", sid, now)
            res["failures"] += 1
            streak += 1
            if streak >= 3:
                res["stopped"] = "failures"
                break
            continue
        streak = 0
        store.mark_checked("dealabs", sid, expired, now)
        res["checked"] += 1
        res["expired"] += int(expired)
    return res
