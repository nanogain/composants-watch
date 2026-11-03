"""Source eBay.fr via l'API officielle Browse (optionnelle : clé développeur requise)."""
from __future__ import annotations

import base64
import json
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from ..http import TIMEOUT, USER_AGENT, http_get
from ..models import Listing
from ..score import is_excluded

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"
GENERIC_QUERIES = ["carte graphique", "processeur", "ddr5", "ssd nvme"]
NEW_WORDS = {"neuf", "new"}


def load_credentials(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if data.get("client_id") and data.get("client_secret") else None


def _post(url: str, body: bytes, headers: dict) -> bytes:
    req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT, **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def get_token(creds: dict, post=_post) -> str:
    basic = base64.b64encode(f"{creds['client_id']}:{creds['client_secret']}".encode()).decode()
    body = urlencode({"grant_type": "client_credentials", "scope": SCOPE}).encode()
    resp = post(TOKEN_URL, body, {"Authorization": f"Basic {basic}",
                                  "Content-Type": "application/x-www-form-urlencoded"})
    return json.loads(resp)["access_token"]


def _eur(amount: dict | None) -> float | None:
    if not amount or amount.get("currency") != "EUR":
        return None
    return round(float(amount["value"]), 2)


def parse_ebay(data: dict) -> list[Listing]:
    out = []
    for it in data.get("itemSummaries", []):
        ship = (it.get("shippingOptions") or [{}])[0].get("shippingCost")
        cond = (it.get("condition") or "").strip().lower()
        out.append(Listing(
            source="ebay", source_id=it["itemId"], url=it.get("itemWebUrl", ""),
            title=it.get("title", ""), price_eur=_eur(it.get("price")),
            price_raw=f"{it.get('price', {}).get('value', '')} {it.get('price', {}).get('currency', '')}".strip(),
            currency=it.get("price", {}).get("currency", ""), shipping_eur=_eur(ship),
            merchant=f"eBay · {it.get('seller', {}).get('username', '?')}",
            condition="new" if cond in NEW_WORDS else "used",
            posted_at=datetime.fromisoformat(it["itemCreationDate"].replace("Z", "+00:00")).astimezone(timezone.utc),
            image_url=(it.get("image") or {}).get("imageUrl"),
        ))
    return out


def fetch_ebay(queries: list[str], creds: dict,
               get=lambda url, headers: http_get(url, headers), post=_post) -> list[Listing]:
    token = get_token(creds, post=post)
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"}
    seen, out = set(), []
    for q in queries:
        url = SEARCH_URL + "?" + urlencode({"q": q, "filter": "buyingOptions:{FIXED_PRICE}", "limit": 50})
        for li in parse_ebay(json.loads(get(url, headers))):
            if li.source_id not in seen:
                seen.add(li.source_id)
                out.append(li)
    return out


def ebay_reference(listings: list[Listing], min_n: int = 3) -> dict[str, float]:
    groups: dict[str, list[float]] = {}
    for li in listings:
        if li.source == "ebay" and li.condition == "new" and li.model and li.effective_eur is not None \
                and not is_excluded(li.title):
            groups.setdefault(f"{li.model}|new", []).append(li.effective_eur)
    return {k: round(statistics.median(v), 2) for k, v in groups.items() if len(v) >= min_n}
