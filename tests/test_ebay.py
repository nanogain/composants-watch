import base64
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs

from composants_watch.sources.ebay import (ebay_queries, ebay_reference, fetch_ebay, get_token,
                                           load_credentials, parse_ebay, reliable_seller)
from tests.helpers import NOW, make_listing

FIX = Path(__file__).parent / "fixtures" / "ebay_search.json"


class EbayTest(unittest.TestCase):
    def test_no_credentials_returns_none(self):
        self.assertIsNone(load_credentials(Path("/nonexistent/ebay.json")))

    def test_credentials_loaded(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ebay.json"
            p.write_text(json.dumps({"client_id": "a", "client_secret": "b"}))
            self.assertEqual(load_credentials(p)["client_id"], "a")

    def test_parse_real_shape(self):
        ls = parse_ebay(json.loads(FIX.read_text()), NOW)
        self.assertEqual([li.source_id for li in ls], ["v1|100001|0", "v1|100002|0"])
        a, b = ls
        self.assertEqual((a.source, a.currency, a.price_eur, a.shipping_eur), ("ebay", "EUR", 79.0, 0.0))
        self.assertEqual((a.condition, a.merchant, a.posted_at), ("new", "eBay · vendeur1 (pro)", NOW))
        self.assertEqual(a.url, "https://www.ebay.fr/itm/100001")
        self.assertEqual((b.condition, b.merchant), ("used", "eBay · vendeur2 (99,2 %, 1 234 avis)"))

    def test_seller_filter(self):
        ok = [{"sellerAccountType": "BUSINESS"}, {"feedbackPercentage": "98.0", "feedbackScore": 50}]
        ko = [{"feedbackPercentage": "97.9", "feedbackScore": 500}, {"feedbackPercentage": "99.0", "feedbackScore": 49},
              {"feedbackPercentage": "0.0", "feedbackScore": 695}, {"feedbackPercentage": "abc"}, {},
              {"feedbackPercentage": None, "feedbackScore": "x"}]
        self.assertEqual([reliable_seller(x) for x in ok], [True, True])
        self.assertEqual([reliable_seller(x) for x in ko], [False] * len(ko))

    def test_creation_date_used_when_present(self):
        data = json.loads(FIX.read_text())
        data["itemSummaries"][0]["itemCreationDate"] = "2026-11-01T10:00:00.000Z"
        self.assertEqual(parse_ebay(data, NOW)[0].posted_at.isoformat(), "2026-11-01T10:00:00+00:00")

    def test_non_eur_price_dropped(self):
        data = json.loads(FIX.read_text())
        data["itemSummaries"][0]["price"] = {"value": "10", "currency": "USD"}
        self.assertEqual([li.source_id for li in parse_ebay(data, NOW)], ["v1|100002|0"])

    def test_fetch_urls_have_category_and_filter(self):
        calls = []

        def get(url, headers):
            calls.append((url, headers))
            return FIX.read_bytes()

        post = lambda url, body, headers: b'{"access_token": "TOK"}'
        ls = fetch_ebay([("carte graphique", "27386"), ("4070S", None)], {"client_id": "i", "client_secret": "s"},
                        NOW, get=get, post=post)
        self.assertEqual(len(ls), 2)
        self.assertEqual(len(calls), 2)
        url, headers = calls[0]
        q = parse_qs(url.split("?", 1)[1])
        self.assertEqual(q["category_ids"], ["27386"])
        self.assertEqual(q["limit"], ["50"])
        self.assertEqual(q["filter"], ["buyingOptions:{FIXED_PRICE},deliveryCountry:FR"])
        self.assertNotIn("category_ids", parse_qs(calls[1][0].split("?", 1)[1]))
        self.assertEqual(headers["X-EBAY-C-MARKETPLACE-ID"], "EBAY_FR")
        self.assertEqual(headers["Authorization"], "Bearer TOK")

    def test_ebay_queries_from_watchlist(self):
        qs = ebay_queries([{"model": "GPU:RTX 4070 Super", "label": "RTX 4070 Super"}])
        self.assertEqual(len(qs), 13)
        self.assertEqual(qs[-1], ("RTX 4070 Super", "27386"))
        self.assertIn(("ddr5", "170083"), qs)
        self.assertEqual(ebay_queries([{"model": "XYZ:foo"}])[-1], ("foo", None))

    def test_reference_needs_3(self):
        m = "GPU:RTX 4070 Super"
        two = [make_listing(source="ebay", source_id=str(i), price_eur=p) for i, p in enumerate([600.0, 620.0])]
        self.assertEqual(ebay_reference(two), {})
        three = two + [make_listing(source="ebay", source_id="9", price_eur=580.0, shipping_eur=10.0)]
        self.assertEqual(ebay_reference(three), {f"{m}|new": 600.0})
        used = three + [make_listing(source="ebay", source_id="u", condition="used", price_eur=1.0)]
        self.assertEqual(ebay_reference(used), {f"{m}|new": 600.0})
        hs = two + [make_listing(source="ebay", source_id="h", price_eur=5.0, title="RTX 4070 Super HS")]
        self.assertEqual(ebay_reference(hs), {})

    def test_token_request_shape(self):
        seen = {}

        def post(url, body, headers):
            seen.update(url=url, body=body, headers=headers)
            return b'{"access_token": "TOK", "expires_in": 7200}'

        tok = get_token({"client_id": "id", "client_secret": "sec"}, post=post)
        self.assertEqual(tok, "TOK")
        self.assertEqual(seen["url"], "https://api.ebay.com/identity/v1/oauth2/token")
        q = parse_qs(seen["body"].decode())
        self.assertEqual(q["grant_type"], ["client_credentials"])
        self.assertEqual(q["scope"], ["https://api.ebay.com/oauth/api_scope"])
        self.assertEqual(seen["headers"]["Authorization"],
                         "Basic " + base64.b64encode(b"id:sec").decode())

    def test_category_hint_from_query(self):
        from composants_watch.normalize import apply
        data = json.loads(FIX.read_text())
        data["itemSummaries"][0]["title"] = "Carte graphique Nvidia RTX A400 4gb GDDR6"
        li = parse_ebay(data, NOW, "GPU")[0]
        self.assertEqual(li.category, "GPU")
        self.assertEqual((apply(li).category, li.model), ("GPU", None))
        calls = []

        def get(url, headers):
            calls.append(url)
            return json.dumps(data).encode()

        ls = fetch_ebay([("watercooling", "131503")], {"client_id": "i", "client_secret": "s"}, NOW,
                        get=get, post=lambda u, b, h: b'{"access_token": "T"}')
        self.assertEqual(ls[0].category, "COOL")
        ls = fetch_ebay([("x", None)], {"client_id": "i", "client_secret": "s"}, NOW,
                        get=get, post=lambda u, b, h: b'{"access_token": "T"}')
        self.assertIsNone(ls[0].category)

if __name__ == "__main__":
    unittest.main()
