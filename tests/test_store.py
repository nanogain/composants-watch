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

    def test_old_ebay_listing_still_live(self):
        self.s.upsert(make_listing(source="ebay", source_id="e", posted_at=NOW - timedelta(days=60)), NOW)
        self.assertEqual([r["source_id"] for r in self.s.recent_listings(7, NOW)], ["e"])
        obs = self.s.observations("GPU:RTX 4070 Super", "new", NOW - timedelta(days=30))
        self.assertEqual([o[1] for o in obs], ["e"])

    def test_ebay_listing_not_seen_recently_dropped(self):
        self.s.upsert(make_listing(source="ebay", source_id="e"), NOW - timedelta(days=10))
        self.assertEqual(self.s.recent_listings(7, NOW), [])

    def test_attrs_round_trip(self):
        self.s.upsert(make_listing(attrs={"socket": "AM5"}), NOW)
        self.assertEqual(self.s.recent_listings(7, NOW)[0]["attrs"], {"socket": "AM5"})
        self.s.upsert(make_listing(attrs={"socket": "AM4", "ddr": 4}), NOW)
        self.assertEqual(self.s.recent_listings(7, NOW)[0]["attrs"], {"socket": "AM4", "ddr": 4})

    def test_migrates_v1_database(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "v1.db")
            db = sqlite3.connect(path)
            db.executescript("""
CREATE TABLE listings(source TEXT, source_id TEXT, url TEXT, title TEXT, model TEXT, category TEXT,
  condition TEXT, merchant TEXT, price_raw TEXT, currency TEXT, posted_at TEXT,
  first_seen TEXT, last_seen TEXT, expired INTEGER DEFAULT 0, PRIMARY KEY(source, source_id));
CREATE TABLE observations(source TEXT, source_id TEXT, ts TEXT, price_eur REAL, shipping_eur REAL);
CREATE TABLE source_health(source TEXT PRIMARY KEY, consecutive_failures INTEGER, last_ok TEXT, last_error TEXT);""")
            db.execute("INSERT INTO listings VALUES('dealabs','1','u','t','GPU:RTX 4070 Super','GPU','new','m',"
                       "'600€','EUR',?,?,?,0)", (NOW.isoformat(),) * 3)
            db.execute("INSERT INTO observations VALUES('dealabs','1',?,600.0,NULL)", (NOW.isoformat(),))
            db.commit(); db.close()
            s = Store(path)
            rows = s.recent_listings(7, NOW)
            self.assertEqual(rows[0]["attrs"], {"tdp_w": 220})  # rempli à la migration
            s.upsert(make_listing(source_id="2", attrs={"tdp_w": 220}), NOW)
            self.assertEqual({r["source_id"]: r["attrs"] for r in s.recent_listings(7, NOW)},
                             {"1": {"tdp_w": 220}, "2": {"tdp_w": 220}})
            s.db.close()

    def test_expired_flag_updated(self):
        self.s.upsert(make_listing(), NOW)
        self.s.upsert(make_listing(expired=True), NOW)
        self.assertTrue(self.s.recent_listings(7, NOW)[0]["expired"])



class V3StoreTest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")

    def ids(self, **kw):
        return [r["source_id"] for r in self.s.recent_listings(7, NOW, **kw)]

    def test_migration_adds_checked_at(self):
        import sqlite3, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.db")
            db = sqlite3.connect(path)
            db.executescript("""CREATE TABLE listings(source TEXT, source_id TEXT, url TEXT, title TEXT,
              model TEXT, category TEXT, condition TEXT, merchant TEXT, price_raw TEXT, currency TEXT,
              posted_at TEXT, first_seen TEXT, last_seen TEXT, expired INTEGER DEFAULT 0,
              attrs TEXT DEFAULT '{}', PRIMARY KEY(source, source_id));""")
            db.execute("INSERT INTO listings(source, source_id, url, title, posted_at, first_seen, last_seen)"
                       " VALUES('dealabs','1','u','t',?,?,?)", (NOW.isoformat(),) * 3)
            db.commit(); db.close()
            s = Store(path)
            self.assertIsNone(s.recent_listings(7, NOW)[0]["checked_at"])
            s.db.close()

    def test_dealabs_expired_survives_upsert(self):
        self.s.upsert(make_listing(), NOW)
        self.s.mark_checked("dealabs", "1", True, NOW)
        self.s.upsert(make_listing(expired=False), NOW + timedelta(minutes=30))
        self.assertIs(self.s.recent_listings(7, NOW)[0]["expired"], True)

    def test_ebay_reappears(self):
        self.s.upsert(make_listing(source="ebay", source_id="e1"), NOW)
        self.assertEqual(self.s.expire_missing("ebay", set(), NOW), 1)
        self.assertIs(self.s.recent_listings(7, NOW)[0]["expired"], True)
        self.s.upsert(make_listing(source="ebay", source_id="e1"), NOW)
        self.assertIs(self.s.recent_listings(7, NOW)[0]["expired"], False)

    def test_expire_missing_keeps_seen(self):
        for i in ("e1", "e2"):
            self.s.upsert(make_listing(source="ebay", source_id=i), NOW)
        self.s.upsert(make_listing(source_id="d1"), NOW)
        self.assertEqual(self.s.expire_missing("ebay", {"e1"}, NOW), 1)
        exp = {r["source_id"]: r["expired"] for r in self.s.recent_listings(7, NOW)}
        self.assertEqual(exp, {"e1": False, "e2": True, "d1": False})

    def test_to_check_order_and_recheck(self):
        h = lambda n: NOW - timedelta(hours=n)
        for sid, posted in (("a", h(1)), ("b", h(5)), ("c", h(2)), ("d", h(3)), ("e", h(1)), ("f", h(8 * 24))):
            self.s.upsert(make_listing(source_id=sid, url=f"https://www.dealabs.com/bons-plans/x-{sid}",
                                       posted_at=posted), NOW)
        self.s.mark_checked("dealabs", "c", False, h(4))
        self.s.mark_checked("dealabs", "d", False, h(1))
        self.s.mark_checked("dealabs", "e", True, h(1))
        got = self.s.to_check(NOW, 7, 3, 10)
        self.assertEqual([i for i, _ in got], ["a", "b", "c"])
        self.assertEqual(got[0][1], "https://www.dealabs.com/bons-plans/x-a")
        self.assertEqual([i for i, _ in self.s.to_check(NOW, 7, 3, 2)], ["a", "b"])

    def test_visibility_rule(self):
        h = lambda n: NOW - timedelta(hours=n)
        for sid in ("ok", "old", "never"):
            self.s.upsert(make_listing(source_id=sid), NOW)
        self.s.mark_checked("dealabs", "ok", False, h(2))
        self.s.mark_checked("dealabs", "old", False, h(7))
        self.s.upsert(make_listing(source="reddit", source_id="r30", posted_at=h(30)), NOW)
        self.s.upsert(make_listing(source="reddit", source_id="r50", posted_at=h(50)), NOW)
        self.s.upsert(make_listing(source="ebay", source_id="e"), NOW)
        self.assertEqual(sorted(self.ids(visible_hours=6, reddit_hours=48)), ["e", "ok", "r30"])
        self.assertEqual(len(self.ids()), 6)

if __name__ == "__main__":
    unittest.main()
