import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class DeploymentTests(unittest.TestCase):
    def test_external_dispatch_preserves_freshness_guard(self):
        workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        freshness = (ROOT / "generator" / "freshness.py").read_text(encoding="utf-8")
        self.assertNotIn("  schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && 'schedule' || github.event_name", workflow)
        self.assertIn("GITHUB_EVENT_NAME=", workflow)
        self.assertIn("Check snapshot freshness", workflow)
        self.assertIn("Asia/Shanghai", freshness)
        self.assertIn("python3 -m generator.freshness", workflow)
        self.assertIn("steps.freshness.outputs.needs_update == 'true'", workflow)
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
        self.assertIn("75/78", readme)
        self.assertIn("具体主力合约", readme)
        self.assertIn("GitHub Pages", readme)
        self.assertIn("无人访问", readme)
        self.assertIn("中位数", readme)

if __name__ == "__main__":
    unittest.main()
