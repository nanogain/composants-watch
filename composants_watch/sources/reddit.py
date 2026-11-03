"""Source Reddit r/buildapcsales (flux Atom). Prix en USD : affichés, jamais comparés."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ..http import http_get
from ..models import Listing

FEED = "https://www.reddit.com/r/buildapcsales/new/.rss"
ATOM = "{http://www.w3.org/2005/Atom}"
_PREFIX = re.compile(r"^\s*\[([^\]]+)\]")
_USD = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?")
_CATS = {"RAM": "RAM", "MEMORY": "RAM", "GPU": "GPU", "CPU": "CPU", "SSD": "SSD",
         "NVME": "SSD", "MOTHERBOARD": "MB", "MOBO": "MB", "MB": "MB", "PSU": "PSU",
         "MONITOR": "MON", "KEYBOARD": "KBD", "COOLER": "COOL", "CASE": "CASE"}


def reddit_category(title: str) -> str | None:
    m = _PREFIX.match(title)
    return _CATS.get(m.group(1).strip().upper()) if m else None


def parse_reddit(xml: bytes) -> list[Listing]:
    out = []
    for e in ET.fromstring(xml).iter(f"{ATOM}entry"):
        title = (e.findtext(f"{ATOM}title") or "").strip()
        link = e.find(f"{ATOM}link")
        m = _USD.search(title)
        pub = e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated")
        out.append(Listing(
            source="reddit", source_id=(e.findtext(f"{ATOM}id") or "").strip(),
            url=link.get("href", "") if link is not None else "", title=title,
            price_eur=None, price_raw=m.group(0) if m else "", currency="USD",
            shipping_eur=None, merchant="", condition="new",
            posted_at=datetime.fromisoformat(pub).astimezone(timezone.utc),
            category=reddit_category(title),
        ))
    return out


def fetch_reddit(get=http_get) -> list[Listing]:
    return parse_reddit(get(FEED))
