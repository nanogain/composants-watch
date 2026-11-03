import unittest
from pathlib import Path

from composants_watch.sources.reddit import parse_reddit, reddit_category

FIX = Path(__file__).parent / "fixtures" / "reddit_bapcs.xml"


class RedditTest(unittest.TestCase):
    def test_parse_reddit_fixture(self):
        ls = parse_reddit(FIX.read_bytes())
        self.assertGreaterEqual(len(ls), 1)
        first = ls[0]
        self.assertEqual(first.source, "reddit")
        self.assertEqual(first.currency, "USD")
        self.assertIsNone(first.price_eur)
        self.assertTrue(first.price_raw.startswith("$"))
        self.assertEqual(first.source_id, "t3_1xmkxkc")
        self.assertTrue(first.url.startswith("https://www.reddit.com/r/buildapcsales/"))
        self.assertEqual(first.category, "RAM")

    def test_category_prefix(self):
        cases = {"[RAM] Corsair 2x16GB DDR5-6000 - $89.99": "RAM",
                 "[GPU] RTX 5070 - $549": "GPU", "[CPU] 9800X3D $449": "CPU",
                 "[SSD] 2TB NVMe $99": "SSD", "[Motherboard] B650 $129": "MB",
                 "[MOBO] B650 $129": "MB", "[PSU] 850W $79": "PSU",
                 "[Cooler] Sudokoo $69.99": "COOL", "[Monitor] x": "MON",
                 "[Keyboard] x": "KBD", "[Case] x": "CASE", "[Headphones] x": None, "no prefix $5": None}
        for title, want in cases.items():
            with self.subTest(title=title):
                self.assertEqual(reddit_category(title), want)

    def test_price_missing_is_empty_raw(self):
        ls = parse_reddit(FIX.read_bytes())
        self.assertTrue(all(li.price_raw == "" or li.price_raw.startswith("$") for li in ls))


if __name__ == "__main__":
    unittest.main()
