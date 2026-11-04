import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node") or str(Path.home() / ".local/bin/node")


def run(scenario):
    r = subprocess.run([NODE, "tests/dom_stub.js", scenario], cwd=ROOT, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])


@unittest.skipUnless(Path(NODE).exists(), "node absent : tests de l'interface non exécutés")
class ConfigUiTest(unittest.TestCase):
    def test_render(self):
        r = run("render")
        self.assertEqual(r["rows"], 10)
        self.assertFalse(r["configHidden"])
        # bonnes affaires d'abord, puis prix croissant (le 5600X sans iGPU reste choisissable)
        self.assertEqual(r["cpuOpts"], ["", "dealabs:2", "dealabs:3", "dealabs:1"])
        self.assertIn("0,00", r["total"])
        for name in ("processeur", "carte mère", "mémoire", "stockage", "alimentation", "boîtier"):
            self.assertIn(name, r["missing"].lower())

    def test_select_incompatible(self):
        r = run("select")
        self.assertIn(["socket", "ko"], r["checks"])
        texts = dict(r["mbTexts"])
        self.assertTrue(texts["dealabs:5"].startswith("❌"))
        self.assertFalse(texts["dealabs:4"].startswith("❌"))
        self.assertEqual(r["mbTexts"][-1][0], "dealabs:5")  # incompatibles en fin de liste

    def test_full_config(self):
        r = run("full")
        self.assertEqual(sorted(r["checks"]), sorted([["socket", "ok"], ["ddr", "ok"], ["form", "ok"],
                                                       ["cooler", "ok"], ["power", "ok"]]))
        self.assertEqual(re.sub(r"\D", "", r["total"]), "144400")  # 1 444,00 €
        self.assertIn("complète", r["missing"].lower())
        self.assertIn("440", r["power"])
        self.assertIn("https://www.dealabs.com/bons-plans/x-7", r["copied"])

    def test_persist(self):
        r = run("persist")
        self.assertEqual(r["saved"]["cpu"]["id"], "dealabs:2")
        self.assertEqual(r["restored"], "dealabs:2")

    def test_stale(self):
        r = run("stale")
        self.assertIn("Annonce disparue", r["staleRow"])
        self.assertIn("RTX 4070 Super disparue", r["staleRow"])
        self.assertIn("189", r["total"])
        self.assertNotIn("738", r["total"])
        self.assertNotIn("gpu", r["afterReplace"])

    def test_corrupt_storage(self):
        r = run("corrupt")
        self.assertIn("0,00", r["total"])

    def test_catalog_missing(self):
        r = run("catalog_missing")
        self.assertIn("Catalogue indisponible", r["msg"])
        self.assertFalse(r["dealsHiddenAfterClick"])

    def test_tabs_lazy_load(self):
        r = run("tabs")
        self.assertEqual(r["before"], {"calls": 0, "configHidden": True})
        self.assertEqual(r["after"], {"calls": 1, "hash": "#config", "configHidden": False, "dealsHidden": True})

    def test_search_filters_options(self):
        self.assertEqual(run("search")["opts"], ["", "dealabs:3"])


    def test_all_listings_search(self):
        r = run("all_search")
        self.assertEqual(r["rowsAll"], r["total"])
        self.assertGreater(r["rows"], 0)
        self.assertLess(r["rows"], r["total"])
        self.assertTrue(all("ryzen" in t.lower() for t in r["titles"]), r["titles"])
        self.assertRegex(r["count"], r"^\d+ résultats?$")
        self.assertIn("indisponibles", r["meta"])
    def test_ai_generate(self):
        r = run("ai_generate")
        self.assertEqual(r["usageOpts"], ["office", "game1080", "game1440", "game4k", "create", "dev"])
        self.assertEqual(r["apiCalls"], 1)
        self.assertEqual(r["key"], "sk-test")
        self.assertTrue(r["applyExists"])
        self.assertIn("Total", r["resultText"])
        self.assertIn("Bon équilibre pour le 1440p.", r["resultText"])
        self.assertIn("284,00", r["resultText"])
        self.assertNotIn("non conforme", r["resultText"])
        self.assertEqual(r["selected"], {"cpu": "dealabs:2", "mb": "dealabs:4", "ram": "dealabs:6", "gpu": "dealabs:7",
                                         "ssd": "dealabs:8", "psu": "dealabs:9", "case": "dealabs:10", "cool": "dealabs:11",
                                         "mon": "dealabs:12"})
        self.assertEqual(r["resultAfter"], "")
        self.assertEqual(r["saved"]["cpu"]["id"], "dealabs:2")
        self.assertEqual(r["saved"]["mon"]["id"], "dealabs:12")
        self.assertEqual(json.loads(r["prefs"]), {"budget": 1500, "usage": "game1440"})

    def test_ai_no_key(self):
        r = run("ai_no_key")
        self.assertEqual(r["apiCalls"], 0)
        self.assertIn("Colle ta clé API Anthropic", r["status"])

    def test_ai_key_saved_and_forgotten(self):
        r = run("ai_key_saved")
        self.assertEqual(r["after"]["stored"], "sk-new")
        self.assertEqual(r["after"]["field"], "")
        self.assertIn("Clé API refusée", r["after"]["status"])
        self.assertIsNone(r["forgotten"])
        self.assertIn("Clé oubliée", r["statusForget"])


if __name__ == "__main__":
    unittest.main()
