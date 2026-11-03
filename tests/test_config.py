import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from composants_watch.config import load_config, load_watchlist
from composants_watch.models import Listing


def make_listing(**kw):
    base = dict(source="dealabs", source_id="1", url="https://x", title="t",
                price_eur=100.0, price_raw="100€", currency="EUR",
                shipping_eur=None, merchant="m", condition="new",
                posted_at=datetime(2026, 11, 3, tzinfo=timezone.utc))
    base.update(kw)
    return Listing(**base)


class ConfigTest(unittest.TestCase):
    def test_config_defaults_merged(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.json"
            p.write_text(json.dumps({"discount_min": 0.2}))
            cfg = load_config(p)
        self.assertEqual(cfg["discount_min"], 0.2)
        self.assertEqual(cfg["suspect_above"], 0.70)
        self.assertEqual(cfg["median_min_obs"], 5)

    def test_missing_config_gives_defaults(self):
        cfg = load_config("/nonexistent/config.json")
        self.assertEqual(cfg["retention_days"], 7)

    def test_load_watchlist(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.json"
            p.write_text(json.dumps([{"model": "GPU:RTX 4070 Super", "label": "x", "target_eur": 550}]))
            self.assertEqual(load_watchlist(p)[0]["target_eur"], 550)

    def test_effective_eur(self):
        self.assertAlmostEqual(make_listing(shipping_eur=9.99).effective_eur, 109.99)
        self.assertEqual(make_listing().effective_eur, 100.0)
        self.assertIsNone(make_listing(price_eur=None).effective_eur)


if __name__ == "__main__":
    unittest.main()
