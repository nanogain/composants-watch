import unittest

from composants_watch.catalog import build_catalog
from composants_watch.store import Store
from tests.helpers import NOW, make_listing


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")

    def rows(self):
        return self.s.recent_listings(7, NOW)

    def add(self, sid, **kw):
        kw.setdefault("url", f"https://x/a-{sid}")
        self.s.upsert(make_listing(source_id=sid, **kw), NOW)

    def build(self, opps=(), medians=lambda m, c: None):
        return build_catalog(self.rows(), {"opportunities": list(opps)}, medians, NOW)

    def test_catalog_filters(self):
        self.add("ok", attrs={"tdp_w": 220})
        self.add("exp", expired=True)
        self.add("unk", model=None, category=None, title="Souris")
        self.add("usd", price_eur=None, source="reddit", currency="USD")
        self.add("zero", price_eur=0.0)
        self.add("hs", title="RTX 4070 Super HS pour pièces")
        cat = self.build()
        self.assertEqual([i["id"] for i in cat["items"]], ["dealabs:ok"])
        item = cat["items"][0]
        self.assertEqual(item["effective_eur"], 600.0)
        self.assertEqual(item["attrs"], {"tdp_w": 220})
        self.assertEqual(set(item), {"id", "category", "model", "title", "condition", "effective_eur",
                                     "median_eur", "deal", "discount_pct", "attrs", "merchant", "source",
                                     "url", "posted_at"})
        self.assertEqual(cat["version"], 1)
        self.assertEqual(cat["generated_at"], "2026-11-03T12:00:00Z")

    def test_category_without_model_kept(self):
        self.add("case", category="CASE", model=None, title="Boîtier PC DeepCool CG530")
        self.assertEqual([i["id"] for i in self.build()["items"]], ["dealabs:case"])

    def test_catalog_deal_flag(self):
        self.add("d")
        self.add("n")
        cat = self.build(opps=[{"url": "https://x/a-d", "discount_pct": 18.5}])
        by = {i["id"]: i for i in cat["items"]}
        self.assertTrue(by["dealabs:d"]["deal"])
        self.assertEqual(by["dealabs:d"]["discount_pct"], 18.5)
        self.assertFalse(by["dealabs:n"]["deal"])
        self.assertIsNone(by["dealabs:n"]["discount_pct"])

    def test_catalog_median(self):
        self.add("m", condition="used")
        seen = []
        cat = self.build(medians=lambda m, c: seen.append((m, c)) or 650.0)
        self.assertEqual(cat["items"][0]["median_eur"], 650.0)
        self.assertEqual(seen, [("GPU:RTX 4070 Super", "used")])


if __name__ == "__main__":
    unittest.main()
