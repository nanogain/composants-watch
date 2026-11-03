import unittest
from pathlib import Path

from composants_watch.http import FetchError
from composants_watch.sources.dealabs import fetch_dealabs, parse_dealabs

FIX = Path(__file__).parent / "fixtures" / "dealabs_gpu.xml"


def rss(item_xml: str) -> bytes:
    return ('<?xml version="1.0"?><rss xmlns:pepper="http://www.pepper.com/rss" '
            'version="2.0"><channel>' + item_xml + "</channel></rss>").encode()


def item(title="RTX 4070 Super", merchant='<pepper:merchant name="LDLC" price="549,99€"/>',
         desc="<![CDATA[<strong>549,99€ - LDLC</strong>]]>", link="https://www.dealabs.com/bons-plans/x-123"):
    return (f"<item>{merchant}<title><![CDATA[{title}]]></title><description>{desc}</description>"
            f"<link>{link}</link><pubDate>Sun, 01 Nov 2026 08:19:46 +0100</pubDate></item>")


class DealabsTest(unittest.TestCase):
    def test_parse_dealabs_fixture(self):
        ls = parse_dealabs(FIX.read_bytes())
        self.assertGreaterEqual(len(ls), 1)
        first = ls[0]
        self.assertEqual(first.source, "dealabs")
        self.assertEqual(first.currency, "EUR")
        self.assertIsInstance(first.price_eur, float)
        self.assertTrue(first.merchant)
        self.assertTrue(first.url.startswith("https://www.dealabs.com/"))
        self.assertEqual(first.source_id, "3443093")
        self.assertEqual(first.posted_at.utcoffset().total_seconds(), 0)

    def test_new_by_default_reconditionne_is_used(self):
        self.assertEqual(parse_dealabs(rss(item()))[0].condition, "new")
        ls = parse_dealabs(rss(item(title="RX 580 8 Go (Puce Reconditionnée)")))
        self.assertEqual(ls[0].condition, "used")

    def test_missing_merchant_price_falls_back_to_strong(self):
        ls = parse_dealabs(rss(item(merchant="", desc="<![CDATA[<strong>89,90€ - Amazon</strong>]]>")))
        self.assertEqual(ls[0].price_eur, 89.9)
        self.assertEqual(ls[0].merchant, "Amazon")

    def test_no_price_at_all_is_none(self):
        ls = parse_dealabs(rss(item(merchant="", desc="<![CDATA[Code promo -10%]]>")))
        self.assertIsNone(ls[0].price_eur)

    def test_expired_flag(self):
        self.assertTrue(parse_dealabs(rss(item(title="[Expiré] RTX 4070")))[0].expired)
        self.assertTrue(parse_dealabs(rss(item(title="[expiré] RTX 4070")))[0].expired)
        self.assertFalse(parse_dealabs(rss(item()))[0].expired)

    def test_fetch_skips_failing_group(self):
        def get(url):
            if url.endswith("/ssd"):
                raise FetchError("404")
            return rss(item())
        listings, failed = fetch_dealabs(["cartes-graphiques", "ssd"], get=get)
        self.assertEqual(failed, ["ssd"])
        self.assertEqual(len(listings), 1)


if __name__ == "__main__":
    unittest.main()
