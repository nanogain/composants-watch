import base64
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs

from composants_watch.sources.ebay import (ebay_reference, fetch_ebay, get_token,
                                           load_credentials, parse_ebay)
from tests.helpers import make_listing

FIX = Path(__file__).parent / "fixtures" / "ebay_search.json"


class EbayTest(unittest.TestCase):
    def test_no_credentials_returns_none(self):
        self.assertIsNone(load_credentials(Path("/nonexistent/ebay.json")))

    def test_credentials_loaded(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ebay.json"
            p.write_text(json.dumps({"client_id": "a", "client_secret": "b"}))
            self.assertEqual(load_credentials(p)["client_id"], "a")

    def test_parse_ebay_fixture(self):
        ls = parse_ebay(json.loads(FIX.read_text()))
        self.assertEqual(len(ls), 3)
        a, b, c = ls
        self.assertEqual((a.source, a.source_id, a.currency), ("ebay", "v1|1111|0", "EUR"))
        self.assertEqual((a.price_eur, a.shipping_eur, a.condition), (589.9, 9.9, "new"))
        self.assertEqual((b.condition, b.shipping_eur), ("used", None))
        self.assertEqual(c.condition, "new")
        self.assertEqual(a.merchant, "eBay · vendeur1")
        self.assertEqual(a.url, "https://www.ebay.fr/itm/1111")

    def test_non_eur_price_is_none(self):
        data = {"itemSummaries": [{"itemId": "x", "title": "t", "price": {"value": "10", "currency": "USD"},
                                   "condition": "New", "itemWebUrl": "u",
                                   "itemCreationDate": "2026-11-02T12:00:00.000Z"}]}
        self.assertIsNone(parse_ebay(data)[0].price_eur)

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

    def test_fetch_uses_marketplace_and_dedups(self):
        calls = []

        def get(url, headers):
            calls.append((url, headers))
            return FIX.read_bytes()

        post = lambda url, body, headers: b'{"access_token": "TOK"}'
        ls = fetch_ebay(["rtx 4070 super", "carte graphique"], {"client_id": "i", "client_secret": "s"},
                        get=get, post=post)
        self.assertEqual(len(ls), 3)
        self.assertEqual(len(calls), 2)
        url, headers = calls[0]
        self.assertIn("filter=buyingOptions%3A%7BFIXED_PRICE%7D", url)
        self.assertIn("q=rtx+4070+super", url)
        self.assertEqual(headers["X-EBAY-C-MARKETPLACE-ID"], "EBAY_FR")
        self.assertEqual(headers["Authorization"], "Bearer TOK")


if __name__ == "__main__":
    unittest.main()
