import unittest
from datetime import timedelta
from pathlib import Path

from composants_watch.config import DEFAULTS
from composants_watch.http import FetchError
from composants_watch.liveness import parse_expired, verify_dealabs
from composants_watch.store import Store
from tests.helpers import NOW, make_listing

FX = Path(__file__).parent / "fixtures"
EXPIRED = (FX / "dealabs_page_expired.html").read_text()   # thread 3401429
ACTIVE = (FX / "dealabs_page_active.html").read_text()     # thread 3446028


def store_with(*ids):
    s = Store(":memory:")
    for n, sid in enumerate(ids):
        s.upsert(make_listing(source_id=sid, url=f"https://www.dealabs.com/bons-plans/x-{sid}",
                              posted_at=NOW - timedelta(hours=n)), NOW)
    return s


class LivenessTest(unittest.TestCase):
    def test_parse_expired_true_false(self):
        self.assertIs(parse_expired(EXPIRED, "3401429"), True)
        self.assertIs(parse_expired(ACTIVE, "3446028"), False)

    def test_parse_missing(self):
        self.assertIsNone(parse_expired("<html></html>", "1"))
        self.assertIsNone(parse_expired(ACTIVE, "999"))

    def test_verify_marks_active_and_expired(self):
        s = store_with("3446028", "3401429", "404")
        pages = {"3446028": ACTIVE.encode(), "3401429": EXPIRED.encode()}

        def get(url):
            sid = url.rsplit("-", 1)[1]
            if sid not in pages:
                raise FetchError(f"HTTP 404 {url}")
            return pages[sid]

        r = verify_dealabs(s, NOW, dict(DEFAULTS), get=get)
        self.assertEqual((r["checked"], r["expired"], r["failures"], r["stopped"]), (3, 2, 0, None))
        self.assertEqual([x["source_id"] for x in s.recent_listings(7, NOW, visible_hours=6)], ["3446028"])

    def test_stops_after_three_failures_without_marking(self):
        s = store_with("1", "2", "3", "4", "5")
        calls = []

        def get(url):
            calls.append(url)
            raise FetchError(f"HTTP 429 {url}")

        r = verify_dealabs(s, NOW, dict(DEFAULTS), get=get)
        self.assertEqual((r["checked"], r["failures"], r["stopped"]), (0, 3, "failures"))
        self.assertEqual(len(calls), 3)
        rows = s.recent_listings(7, NOW)
        self.assertTrue(all(x["checked_at"] is None and not x["expired"] for x in rows))

    def test_page_cap_and_budget(self):
        s = store_with("1", "2", "3", "4", "5")
        page = lambda url: ACTIVE.replace("3446028", url.rsplit("-", 1)[1]).encode()
        r = verify_dealabs(s, NOW, {**DEFAULTS, "verify_max_pages": 2}, get=page)
        self.assertEqual((r["checked"], r["stopped"]), (2, "pages"))

        s = store_with("1", "2", "3", "4", "5")
        t = [0.0]

        def clock():
            t[0] += 100
            return t[0]

        r = verify_dealabs(s, NOW, dict(DEFAULTS), get=page, clock=clock)
        self.assertLessEqual(r["checked"], 3)
        self.assertEqual(r["stopped"], "budget")

    def test_page_without_flag_is_failure(self):
        s = store_with("1")
        r = verify_dealabs(s, NOW, dict(DEFAULTS), get=lambda url: b"<html>")
        self.assertEqual((r["checked"], r["failures"]), (0, 1))
        self.assertIsNone(s.recent_listings(7, NOW)[0]["checked_at"])

    def test_nothing_to_check(self):
        r = verify_dealabs(Store(":memory:"), NOW, dict(DEFAULTS), get=lambda url: b"")
        self.assertEqual(r, {"checked": 0, "expired": 0, "failures": 0, "stopped": None})


if __name__ == "__main__":
    unittest.main()
