import unittest

from composants_watch.prices import parse_price


class ParsePriceTest(unittest.TestCase):
    def test_parse_price_formats(self):
        cases = {"67,63€": 67.63, "1 299,99€": 1299.99, "1.299,99 €": 1299.99,
                 "1299€": 1299.0, "1 299,99 €": 1299.99, "Gratuit": 0.0,
                 "12.5€": 12.5, "$89.99": 89.99, "$1,299.99": 1299.99}
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_price(raw), want)

    def test_unparseable_is_none(self):
        for raw in ("", "abc", None):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_price(raw))


if __name__ == "__main__":
    unittest.main()
