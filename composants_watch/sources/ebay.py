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
CATEGORY_IDS = {"GPU": "27386", "CPU": "164", "RAM": "170083", "SSD": "175669", "MB": "1244",
                "PSU": "42017", "CASE": "42014", "COOL": "131486", "MON": "80053", "KBD": "33963"}
CATEGORY_QUERIES = [("carte graphique", "27386"), ("processeur", "164"), ("ddr4", "170083"),
                    ("ddr5", "170083"), ("ssd", "175669"), ("carte mère", "1244"),
                    ("alimentation pc", "42017"), ("boitier pc", "42014"), ("ventirad", "131486"),
                    ("watercooling", "131503"), ("écran pc", "80053"), ("clavier", "33963")]
ID_CATEGORY = {v: k for k, v in CATEGORY_IDS.items()} | {"131503": "COOL"}
EU = frozenset("AT BE BG CY CZ DE DK EE ES FI FR GR HR HU IE IT LT LU LV MT NL PL PT RO SE SI SK".split())
FILTER = "buyingOptions:{FIXED_PRICE},deliveryCountry:FR"
FOR_PARTS = "7000"


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


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def reliable_seller(seller: dict) -> bool:
    """Professionnel, ou au moins 98 % d'avis positifs sur au moins 50 évaluations ("0.0" = note inconnue)."""
    if seller.get("sellerAccountType") == "BUSINESS":
        return True
    pct, n = _num(seller.get("feedbackPercentage")), _num(seller.get("feedbackScore"))
    return pct is not None and n is not None and pct >= 98 and n >= 50


def _merchant(seller: dict) -> str:
    name = seller.get("username", "?")
    if seller.get("sellerAccountType") == "BUSINESS":
        return f"eBay · {name} (pro)"
    pct = f"{_num(seller.get('feedbackPercentage')):.1f}".replace(".", ",")
    n = f"{int(_num(seller.get('feedbackScore'))):,}".replace(",", " ")
    return f"eBay · {name} ({pct} %, {n} avis)"


def _keep(it: dict) -> bool:
    return ("AUCTION" not in (it.get("buyingOptions") or [])
            and (it.get("price") or {}).get("currency") == "EUR"
            and str(it.get("conditionId")) != FOR_PARTS
            and (it.get("itemLocation") or {}).get("country") in EU
            and reliable_seller(it.get("seller") or {}))


def parse_ebay(data: dict, now: datetime, category: str | None = None) -> list[Listing]:
    out = []
    for it in data.get("itemSummaries", []):
        if not _keep(it):
            continue
        ship = (it.get("shippingOptions") or [{}])[0].get("shippingCost")
        created = it.get("itemCreationDate")
        out.append(Listing(
            source="ebay", source_id=it["itemId"], url=it.get("itemWebUrl", ""),
            title=it.get("title", ""), price_eur=_eur(it.get("price")),
            price_raw=f"{it['price'].get('value', '')} EUR",
            currency="EUR", shipping_eur=_eur(ship), merchant=_merchant(it["seller"]),
            condition="new" if str(it.get("conditionId")) == "1000" else "used",
            posted_at=(datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(timezone.utc)
                       if created else now),
            image_url=(it.get("image") or {}).get("imageUrl"),
            category=category,  # indice : la catégorie eBay interrogée, si le titre ne suffit pas
        ))
    return out


def ebay_queries(watchlist: list[dict]) -> list[tuple[str, str | None]]:
    extra = [(w.get("label") or w["model"].split(":", 1)[-1], CATEGORY_IDS.get(w["model"].split(":", 1)[0]))
             for w in watchlist]
    return CATEGORY_QUERIES + extra


def fetch_ebay(queries: list[tuple[str, str | None]], creds: dict, now: datetime, limit: int = 50,
               get=lambda url, headers: http_get(url, headers), post=_post) -> list[Listing]:
    token = get_token(creds, post=post)
    headers = {"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"}
    seen, out = set(), []
    for q, cat in queries:
        params = {"q": q, "limit": limit, "filter": FILTER}
        if cat:
            params["category_ids"] = cat
        for li in parse_ebay(json.loads(get(SEARCH_URL + "?" + urlencode(params), headers)), now,
                              ID_CATEGORY.get(cat or "")):
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
