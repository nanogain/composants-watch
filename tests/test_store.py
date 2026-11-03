import unittest
from datetime import timedelta

from composants_watch.store import Store
from tests.helpers import NOW, make_listing


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")

    def count_obs(self):
        return self.s.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    def test_same_price_no_new_observation(self):
        self.s.upsert(make_listing(), NOW)
        self.s.upsert(make_listing(), NOW + timedelta(minutes=30))
        self.assertEqual(self.count_obs(), 1)

    def test_price_change_adds_observation(self):
        self.s.upsert(make_listing(price_eur=100.0), NOW)
        self.s.upsert(make_listing(price_eur=90.0), NOW + timedelta(minutes=30))
        self.assertEqual(self.count_obs(), 2)
        rows = self.s.recent_listings(7, NOW + timedelta(hours=1))
        self.assertEqual(rows[0]["price_eur"], 90.0)

    def test_null_price_not_observed(self):
        self.s.upsert(make_listing(source="reddit", price_eur=None, currency="USD"), NOW)
        self.assertEqual(self.count_obs(), 0)
        self.assertEqual(len(self.s.recent_listings(7, NOW)), 1)

    def test_observations_latest_per_listing(self):
        self.s.upsert(make_listing(source_id="a", price_eur=600.0), NOW)
        self.s.upsert(make_listing(source_id="a", price_eur=580.0), NOW + timedelta(minutes=5))
        self.s.upsert(make_listing(source_id="b", price_eur=620.0, shipping_eur=10.0), NOW)
        obs = sorted(self.s.observations("GPU:RTX 4070 Super", "new", NOW - timedelta(days=30)))
        self.assertEqual(obs, [("dealabs", "a", 580.0), ("dealabs", "b", 630.0)])

    def test_observations_filtered_by_condition_and_window(self):
        self.s.upsert(make_listing(source_id="u", condition="used", price_eur=400.0), NOW)
        self.s.upsert(make_listing(source_id="old", price_eur=700.0), NOW - timedelta(days=40))
        self.assertEqual(self.s.observations("GPU:RTX 4070 Super", "new", NOW - timedelta(days=30)), [])

    def test_observations_exclude_callback(self):
        self.s.upsert(make_listing(source_id="hs", title="RTX 4070 Super HS"), NOW)
        self.s.upsert(make_listing(source_id="ok"), NOW)
        obs = self.s.observations("GPU:RTX 4070 Super", "new", NOW - timedelta(days=30),
                                  exclude=lambda t: "HS" in t)
        self.assertEqual([o[1] for o in obs], ["ok"])

    def test_source_failures_counter(self):
        for _ in range(3):
            h = self.s.record_source("dealabs", False, "boom", NOW)
        self.assertEqual(h["consecutive_failures"], 3)
        self.assertIsNone(h["last_ok"])
        h = self.s.record_source("dealabs", True, None, NOW)
        self.assertEqual(h["consecutive_failures"], 0)
        self.assertEqual(h["last_ok"], NOW.isoformat())
        self.assertIn("dealabs", self.s.source_health())

    def test_retention(self):
        self.s.upsert(make_listing(source_id="old"), NOW - timedelta(days=8))
        self.s.upsert(make_listing(source_id="new"), NOW)
        ids = [r["source_id"] for r in self.s.recent_listings(7, NOW)]
        self.assertEqual(ids, ["new"])

    def test_retention_uses_posting_date(self):
        self.s.upsert(make_listing(source_id="oldpost", posted_at=NOW - timedelta(days=20)), NOW)
        self.s.upsert(make_listing(source_id="fresh"), NOW)
        self.assertEqual([r["source_id"] for r in self.s.recent_listings(7, NOW)], ["fresh"])

    def test_observations_ignore_old_postings(self):
        self.s.upsert(make_listing(source_id="oldpost", posted_at=NOW - timedelta(days=40)), NOW)
        self.s.upsert(make_listing(source_id="fresh"), NOW)
        obs = self.s.observations("GPU:RTX 4070 Super", "new", NOW - timedelta(days=30))
        self.assertEqual([o[1] for o in obs], ["fresh"])

    def test_expired_flag_updated(self):
        self.s.upsert(make_listing(), NOW)
        self.s.upsert(make_listing(expired=True), NOW)
        self.assertTrue(self.s.recent_listings(7, NOW)[0]["expired"])


if __name__ == "__main__":
    unittest.main()
