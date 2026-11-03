import fcntl
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path
from unittest import mock

import watch
from composants_watch.config import DEFAULTS
from composants_watch.http import FetchError
from tests.helpers import NOW, make_listing

WL = [{"model": "GPU:RTX 4070 Super", "label": "4070S", "target_eur": 550}]


class RunPassTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def deals(self):
        return json.loads((self.root / "docs" / "data" / "deals.json").read_text())

    def test_first_run_empty_db_renders(self):
        p = watch.run_pass(dict(DEFAULTS), WL, self.root,
                           fetchers={"dealabs": lambda: [], "reddit": lambda: [], "ebay": None},
                           push=False, now=NOW)
        self.assertEqual(p["opportunities"], [])
        self.assertTrue(p["watchlist"][0]["never_seen"])
        self.assertEqual(self.deals()["sources"]["ebay"]["status"], "disabled")
        self.assertEqual(self.deals()["sources"]["dealabs"]["status"], "ok")

    def test_failing_source_isolated(self):
        def boom():
            raise FetchError("down")

        def bad_xml():
            raise ET.ParseError("truncated")

        p = watch.run_pass(dict(DEFAULTS), WL, self.root,
                           fetchers={"dealabs": boom, "reddit": bad_xml,
                                     "ebay": lambda: [make_listing(source="ebay", source_id="e1",
                                                                   title="RTX 4070 Super", price_eur=500.0,
                                                                   model=None, category=None)]},
                           push=False, now=NOW)
        self.assertEqual(p["sources"]["ebay"]["items"], 1)
        self.assertEqual(p["watchlist"][0]["best"]["price_eur"], 500.0)  # normalisé par la passe
        self.assertTrue(p["watchlist"][0]["target_hit"])

    def test_watch_writes_catalog(self):
        watch.run_pass(dict(DEFAULTS), WL, self.root,
                       fetchers={"dealabs": lambda: [make_listing(title="MSI RTX 4070 SUPER Ventus",
                                                                  model=None, category=None)]},
                       push=False, now=NOW)
        cat = json.loads((self.root / "docs" / "data" / "catalog.json").read_text())
        self.assertEqual(len(cat["items"]), 1)
        self.assertEqual(cat["items"][0]["attrs"], {"tdp_w": 220})

    def test_source_down_after_5(self):
        def boom():
            raise FetchError("down")
        for i in range(5):
            p = watch.run_pass(dict(DEFAULTS), WL, self.root, fetchers={"reddit": boom},
                               push=False, now=NOW + timedelta(minutes=30 * i))
        self.assertEqual(p["sources"]["reddit"]["status"], "down")

    def test_push_called_only_when_enabled(self):
        with mock.patch("watch.git_push", return_value=(False, "token absent")) as gp:
            watch.run_pass(dict(DEFAULTS), WL, self.root, fetchers={}, push=True, now=NOW)
            self.assertEqual(gp.call_count, 1)
            watch.run_pass(dict(DEFAULTS), WL, self.root, fetchers={}, push=False, now=NOW)
            self.assertEqual(gp.call_count, 1)
        self.assertTrue((self.root / "docs" / "data" / "deals.json").exists())


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lock_prevents_overlap(self):
        (self.root / "data").mkdir()
        with open(self.root / "data" / "watch.lock", "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with mock.patch("watch.run_pass") as rp:
                self.assertEqual(watch.main(["--no-push"], root=self.root), 0)
                rp.assert_not_called()
        self.assertIn("passe déjà en cours", (self.root / "logs" / "watch.log").read_text())

    def test_dry_end_to_end(self):
        with mock.patch("watch.git_push") as gp:
            self.assertEqual(watch.main(["--dry"], root=self.root), 0)
            gp.assert_not_called()
        d = json.loads((self.root / "docs" / "data" / "deals.json").read_text())
        self.assertEqual(d["sources"]["dealabs"]["status"], "ok")
        self.assertGreater(d["stats"]["listings_seen"], 0)
        self.assertFalse((self.root / "data" / "watch.db").exists())


if __name__ == "__main__":
    unittest.main()
