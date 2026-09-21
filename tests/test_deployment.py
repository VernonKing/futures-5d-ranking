import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def test_workflow_runs_weekdays_at_1540_china_time_and_deploys_pages(self):
        workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn("40 7 * * 1-5", workflow)
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
        self.assertIn("15:40", readme)
        self.assertIn("GitHub Pages", readme)
        self.assertIn("无人访问", readme)
        self.assertIn("中位数", readme)


if __name__ == "__main__":
    unittest.main()
