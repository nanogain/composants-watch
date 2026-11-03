"""Source Dealabs : flux RSS publics par groupe."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

from ..http import FetchError, http_get
from ..models import Listing
from ..prices import parse_price

FEED = "https://www.dealabs.com/rss/groupe/{slug}"
PEPPER = "{http://www.pepper.com/rss}"
MEDIA = "{http://search.yahoo.com/mrss/}"
_STRONG = re.compile(r"<strong>\s*([^<]*?)\s*-\s*([^<]+?)\s*</strong>")
_ID = re.compile(r"-(\d+)/?$")


def parse_dealabs(xml: bytes) -> list[Listing]:
    out = []
    for it in ET.fromstring(xml).iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or it.findtext("guid") or "").strip()
        desc = it.findtext("description") or ""
        merchant, price_raw = "", ""
        m = it.find(f"{PEPPER}merchant")
        if m is not None:
            merchant, price_raw = m.get("name", ""), m.get("price", "")
        if not price_raw or not merchant:
            s = _STRONG.search(desc)
            if s:
                price_raw = price_raw or s.group(1)
                merchant = merchant or s.group(2)
        mid = _ID.search(link)
        pub = it.findtext("pubDate")
        thumb = it.find(f"{MEDIA}thumbnail")
        out.append(Listing(
            source="dealabs",
            source_id=mid.group(1) if mid else link,
            url=link, title=title,
            price_eur=parse_price(price_raw), price_raw=price_raw, currency="EUR",
            shipping_eur=None, merchant=merchant,
            condition="used" if "reconditionn" in title.lower() else "new",
            posted_at=parsedate_to_datetime(pub).astimezone(timezone.utc),
            expired=title.lower().startswith("[expiré]"),
            image_url=thumb.get("url") if thumb is not None else None,
        ))
    return out


def fetch_dealabs(groups: list[str], get=http_get) -> tuple[list[Listing], list[str]]:
    listings, failed, seen = [], [], set()
    for slug in groups:
        try:
            for li in parse_dealabs(get(FEED.format(slug=slug))):
                if li.source_id not in seen:
                    seen.add(li.source_id)
                    listings.append(li)
        except (FetchError, ET.ParseError):
            failed.append(slug)
    return listings, failed
