import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SiteContractTests(unittest.TestCase):
    def test_site_shell_contains_required_sections(self):
        html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="ranking-tabs"', html)
        self.assertIn('id="category-list"', html)
        self.assertIn('id="category-table"', html)
        self.assertIn('id="data-date"', html)
        self.assertIn("具体主力合约公开行情", html)
        self.assertNotIn("连续合约公开行情", html)

    def test_frontend_loads_static_payload_and_draws_required_averages(self):
        script = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        self.assertIn("data/latest.json", script)
        self.assertIn("intradayPeriod", script)
        self.assertIn("ma60", script)
        self.assertIn("ma10", script)
        self.assertIn("drawChart", script)
        self.assertIn("member.contract", script)


if __name__ == "__main__":
    unittest.main()
