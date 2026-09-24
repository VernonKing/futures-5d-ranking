import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def test_workflow_retries_until_2000_and_skips_after_a_complete_daily_snapshot(self):
        workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        freshness = (ROOT / "generator" / "freshness.py").read_text(encoding="utf-8")
        self.assertIn("0 8 * * 1-5", workflow)
        self.assertIn("25 8 * * 1-5", workflow)
        self.assertIn("0 9 * * 1-5", workflow)
        self.assertIn("0 10 * * 1-5", workflow)
        self.assertIn("0 12 * * 1-5", workflow)
        self.assertIn("Check snapshot freshness", workflow)
        self.assertIn("Asia/Shanghai", freshness)
        self.assertIn("needs_update", workflow)
        self.assertIn("python3 -m generator.freshness", workflow)
        self.assertIn("steps.freshness.outputs.needs_update == 'true'", workflow)
        self.assertNotIn("40 7 * * 1-5", workflow)
        self.assertNotIn("20 9 * * 1-5", workflow)
        self.assertIn("workflow_dispatch", workflow)
        self.assertIn("python -m generator.build", workflow)
        self.assertIn("actions/upload-pages-artifact@v4", workflow)
        self.assertIn("actions/deploy-pages@v4", workflow)
        self.assertIn("pages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("git commit", workflow)
        self.assertIn("git push", workflow)

    def test_readme_explains_public_unattended_operation(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("16:00", readme)
        self.assertIn("16:25", readme)
        self.assertIn("20:00", readme)
        self.assertIn("75/78", readme)
        self.assertIn("具体主力合约", readme)
        self.assertIn("GitHub Pages", readme)
        self.assertIn("无人访问", readme)
        self.assertIn("中位数", readme)


if __name__ == "__main__":
    unittest.main()
