import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class AdvisorJsTest(unittest.TestCase):
    def test_advisor_in_node(self):
        node = shutil.which("node") or str(Path.home() / ".local/bin/node")
        if not Path(node).exists():
            self.skipTest("node absent : tests JS non exécutés")
        r = subprocess.run([node, "tests/advisor.test.js"], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("advisor: all", r.stdout)


if __name__ == "__main__":
    unittest.main()
