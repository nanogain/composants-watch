import re
import unittest
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.html = (DOCS / "index.html").read_text(encoding="utf-8")
        self.js = (DOCS / "app.js").read_text(encoding="utf-8")

    def test_assets_are_relative(self):
        self.assertRegex(self.html, r'<script[^>]+src="app\.js"')
        self.assertRegex(self.html, r'<link[^>]+href="style\.css"')

    def test_no_third_party_requests(self):
        for tag in re.findall(r"<(?:script|link|img|iframe)[^>]*>", self.html):
            self.assertNotRegex(tag, r"(src|href)=\"(https?:)?//", tag)
        self.assertNotRegex(self.js, r"fetch\(\s*['\"]https?://")

    def test_fetches_relative_deals_json(self):
        self.assertRegex(self.js, r"fetch\(\s*['\"]data/deals\.json")

    def test_no_innerhtml_from_data(self):
        self.assertNotIn("innerHTML", self.js)
        self.assertNotIn("insertAdjacentHTML", self.js)

    def test_tabs_and_scripts(self):
        self.assertIn("Bonnes affaires", self.html)
        self.assertIn("Configurateur", self.html)
        self.assertRegex(self.html, r'<script[^>]+src="compat\.js"')
        self.assertRegex(self.html, r'<script[^>]+src="config\.js"')
        cfg = (DOCS / "config.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", cfg)
        self.assertNotIn("insertAdjacentHTML", cfg)
        self.assertRegex(cfg, r"fetch\(\s*['\"]data/catalog\.json")
        self.assertNotRegex(cfg, r"fetch\(\s*['\"]https?://")

    def test_french_and_nojekyll(self):
        self.assertIn('lang="fr"', self.html)
        self.assertTrue((DOCS / ".nojekyll").exists())
        for section in ("Ma liste", "Opportunités", "Non classées"):
            self.assertIn(section, self.html)


    def test_verif_source_label(self):
        self.assertIn('dealabs_verif: "Vérification Dealabs"', (DOCS / "app.js").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
