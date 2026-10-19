"""Despliegue (spec 002, RF-1, RF-3, RF-4, RF-8).

Tests de texto sobre `render.yaml` y los workflows de GitHub (sin red y
sin dependencias nuevas, RNF-2): crons, secretos, permisos y ausencia
de `ALLOW_LIVE_TRADING` o volcados de secretos (RF-4).
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
RENDER_YAML = REPO_ROOT / "render.yaml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_secure(test: unittest.TestCase, text: str) -> None:
    test.assertNotIn("ALLOW_LIVE_TRADING", text)
    test.assertNotIn("echo ${{ secrets", text)


class DailyReportWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(WORKFLOWS_DIR / "daily-report.yml")

    def test_triggers_schedule_and_manual(self) -> None:
        self.assertIn("0 8 * * *", self.text)
        self.assertIn("workflow_dispatch", self.text)

    def test_secrets_injected(self) -> None:
        for name in ("DATABASE_URL", "SMTP_USER", "SMTP_PASS", "REPORT_TO"):
            with self.subTest(secret=name):
                self.assertIn(f"secrets.{name}", self.text)

    def test_installs_requirements_and_runs_cli(self) -> None:
        self.assertIn("pip install -r requirements.txt", self.text)
        self.assertIn("send_daily_report.py", self.text)

    def test_permissions_read_only(self) -> None:
        self.assertIn("permissions:", self.text)
        self.assertIn("contents: read", self.text)

    def test_no_live_trading_and_no_secret_echo(self) -> None:
        _assert_secure(self, self.text)


class NoCloudDeployTests(unittest.TestCase):
    """Spec 014: el bot corre solo en la PC; Render y GitHub Pages se retiraron."""

    def test_render_and_pages_are_gone(self) -> None:
        self.assertFalse(RENDER_YAML.exists())
        self.assertFalse((WORKFLOWS_DIR / "pages.yml").exists())


if __name__ == "__main__":
    unittest.main()
