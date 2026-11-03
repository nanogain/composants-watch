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


if __name__ == "__main__":
    unittest.main()
