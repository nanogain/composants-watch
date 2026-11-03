import unittest
from datetime import timedelta

from composants_watch.config import DEFAULTS
from composants_watch.score import is_excluded, reference_median, score
from composants_watch.store import Store
from tests.helpers import NOW, make_listing

M = "GPU:RTX 4070 Super"


class ScoreTest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        self.cfg = dict(DEFAULTS)

    def seed(self, prices, condition="new", prefix="ref"):
        for i, p in enumerate(prices):
            self.s.upsert(make_listing(source_id=f"{prefix}{condition}{i}", price_eur=p,
                                       condition=condition), NOW - timedelta(days=2))

    def run_score(self, watchlist=(), ebay_ref=None):
        return score(self.s.recent_listings(7, NOW), self.s, self.cfg, list(watchlist), NOW, ebay_ref)

    def add(self, sid, price, **kw):
        self.s.upsert(make_listing(source_id=sid, price_eur=price, **kw), NOW)

    def opp_ids(self, res):
        return [o["url"].rsplit("-", 1)[-1] for o in res["opportunities"]]

    def test_excluded_keywords(self):
        self.assertTrue(is_excluded("RTX 3080 HS pour pièces"))
        self.assertTrue(is_excluded("Lot de 4 barrettes DDR4"))
        self.assertTrue(is_excluded("Boîte vide RTX 4090"))
        self.assertTrue(is_excluded("RX 580 reconditionnée mining"))
        self.assertFalse(is_excluded("RTX 4070 Super neuve"))
        self.assertFalse(is_excluded("Kit HSF ventirad"))

    def test_median_needs_5_obs_2_listings(self):
        self.assertIsNone(reference_median([("d", "a", 1.0)] * 4, 5))
        self.assertIsNone(reference_median([("d", "a", 1.0)] * 5, 5))
        obs = [("d", "a", 600.0), ("d", "b", 610.0), ("d", "c", 590.0), ("d", "e", 620.0), ("d", "f", 580.0)]
        self.assertEqual(reference_median(obs, 5), 600.0)

    def test_discount_opportunity(self):
        self.seed([600] * 5)
        self.add("cheap", 500.0, url="https://x/a-cheap")
        self.add("meh", 520.0, url="https://x/a-meh")
        res = self.run_score()
        ids = self.opp_ids(res)
        self.assertIn("cheap", ids)
        self.assertNotIn("meh", ids)
        cheap = next(o for o in res["opportunities"] if o["url"].endswith("cheap"))
        self.assertAlmostEqual(cheap["discount_pct"], 16.7, places=1)
        self.assertEqual(cheap["median_eur"], 600.0)

    def test_target_hit_first(self):
        self.seed([600] * 5)
        self.add("tgt", 549.0, url="https://x/a-tgt")
        self.add("big", 420.0, url="https://x/a-big")
        res = self.run_score([{"model": M, "label": "4070S", "target_eur": 548}])
        # 549 > 548 : pas de cible ; 420 <= 548 : cible
        self.assertEqual(self.opp_ids(res)[0], "big")
        self.assertTrue(res["opportunities"][0]["target_hit"])

    def test_target_sorted_before_bigger_discount(self):
        self.seed([600] * 5)
        other = "GPU:RTX 5080"
        for i in range(5):
            self.s.upsert(make_listing(source_id=f"o{i}", model=other, price_eur=1000.0), NOW - timedelta(days=2))
        self.add("tgt", 560.0, url="https://x/a-tgt")             # 6.7 % mais cible 570
        self.add("deep", 650.0, url="https://x/a-deep", model=other)  # 35 %
        res = self.run_score([{"model": M, "label": "4070S", "target_eur": 570}])
        self.assertEqual(self.opp_ids(res)[:2], ["tgt", "deep"])

    def test_suspect_over_70(self):
        self.seed([600] * 5)
        self.add("scam", 150.0, url="https://x/a-scam")
        self.add("good", 480.0, url="https://x/a-good")
        res = self.run_score()
        self.assertEqual(self.opp_ids(res), ["good", "scam"])
        self.assertTrue(res["opportunities"][1]["suspect"])
        self.assertFalse(res["opportunities"][0]["suspect"])

    def test_shipping_included(self):
        self.add("ship", 540.0, shipping_eur=15.0, url="https://x/a-ship")
        res = self.run_score([{"model": M, "label": "4070S", "target_eur": 550}])
        self.assertEqual(res["opportunities"], [])
        self.assertFalse(res["watchlist"][0]["target_hit"])
        self.assertEqual(res["watchlist"][0]["best"]["price_eur"], 555.0)

    def test_usd_never_scored(self):
        self.seed([600] * 5)
        self.add("usd", None, source="reddit", currency="USD", price_raw="$100", url="https://x/a-usd")
        self.add("usdu", None, source="reddit", currency="USD", price_raw="$5", model=None,
                 category=None, title="[Cooler] thing", url="https://x/a-usdu")
        res = self.run_score()
        self.assertEqual(self.opp_ids(res), [])
        self.assertEqual(len(self.s.observations(M, "new", NOW - timedelta(days=30))), 5)
        self.assertEqual(sorted(u["title"] for u in res["unclassified"]), ["MSI RTX 4070 Super", "[Cooler] thing"])

    def test_new_and_used_separate_medians(self):
        self.seed([600] * 5)
        self.seed([300] * 5, condition="used")
        self.add("usedcheap", 250.0, condition="used", url="https://x/a-usedcheap")
        self.add("newok", 590.0, url="https://x/a-newok")
        res = self.run_score()
        self.assertEqual(self.opp_ids(res), ["usedcheap"])
        self.assertEqual(res["opportunities"][0]["median_eur"], 300.0)

    def test_excluded_listing_never_opportunity(self):
        self.seed([600] * 5)
        self.add("hs", 200.0, title="RTX 4070 Super HS pour pièces", url="https://x/a-hs")
        res = self.run_score([{"model": M, "label": "4070S", "target_eur": 550}])
        self.assertEqual(self.opp_ids(res), [])
        self.assertEqual(res["watchlist"][0]["median_30d"], 600.0)

    def test_ebay_fallback_reference(self):
        self.add("e", 500.0, url="https://x/a-e")
        res = self.run_score(ebay_ref={f"{M}|new": 600.0})
        self.assertEqual(self.opp_ids(res), ["e"])
        self.assertEqual(res["opportunities"][0]["median_eur"], 600.0)

    def test_no_reference_no_discount(self):
        self.add("lonely", 100.0, url="https://x/a-lonely")
        res = self.run_score()
        self.assertEqual(res["opportunities"], [])
        self.assertEqual(res["stats"]["models_with_reference"], 0)

    def test_watchlist_unknown_model(self):
        res = self.run_score([{"model": "GPU:RTX 4070 Supr", "label": "typo", "target_eur": 500}])
        w = res["watchlist"][0]
        self.assertIsNone(w["best"])
        self.assertIsNone(w["median_30d"])
        self.assertTrue(w["never_seen"])
        self.assertFalse(w["target_hit"])

    def test_expired_removed(self):
        self.seed([600] * 5)
        self.add("exp", 400.0, expired=True, url="https://x/a-exp")
        self.assertEqual(self.opp_ids(self.run_score()), [])

    def test_item_fields(self):
        self.seed([600] * 5)
        self.add("cheap", 500.0, url="https://x/a-cheap")
        o = self.run_score()["opportunities"][0]
        self.assertEqual(set(o), {"title", "model", "category", "condition", "price_eur", "shipping_eur",
                                  "effective_eur", "median_eur", "discount_pct", "target_hit", "suspect",
                                  "merchant", "source", "url", "posted_at"})


if __name__ == "__main__":
    unittest.main()
