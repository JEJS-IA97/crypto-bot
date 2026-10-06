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


class PagesWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(WORKFLOWS_DIR / "pages.yml")

    def test_triggers_push_and_manual(self) -> None:
        self.assertIn("workflow_dispatch", self.text)
        self.assertIn("branches:", self.text)
        self.assertIn("frontend/**", self.text)

    def test_builds_frontend_with_api_url(self) -> None:
        self.assertIn("npm ci", self.text)
        self.assertIn("npm run build", self.text)
        self.assertIn("VITE_API_URL", self.text)

    def test_deploys_to_pages(self) -> None:
        self.assertIn("actions/configure-pages", self.text)
        self.assertIn("actions/upload-pages-artifact", self.text)
        self.assertIn("actions/deploy-pages", self.text)
        self.assertIn("frontend/dist", self.text)

    def test_permissions_for_pages_only(self) -> None:
        self.assertIn("pages: write", self.text)
        self.assertIn("id-token: write", self.text)

    def test_no_live_trading_and_no_secret_echo(self) -> None:
        _assert_secure(self, self.text)


class RenderBlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(RENDER_YAML)

    def test_free_python_web_service(self) -> None:
        self.assertIn("type: web", self.text)
        self.assertIn("plan: free", self.text)
        self.assertIn("runtime: python", self.text)
        self.assertIn("rootDir: backend", self.text)

    def test_build_and_start_commands(self) -> None:
        self.assertIn("pip install -r requirements.txt", self.text)
        self.assertIn(
            "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
            self.text,
        )
        self.assertIn("healthCheckPath: /health", self.text)

    def test_env_vars_for_render(self) -> None:
        self.assertIn("SIMULATION_BOT_ENABLED", self.text)
        self.assertIn('value: "true"', self.text)
        for name in ("DATABASE_URL", "API_TOKEN", "CORS_ORIGINS", "KEEPALIVE_URL"):
            with self.subTest(var=name):
                self.assertRegex(
                    self.text,
                    rf"- key: {name}\s*\n\s*sync: false",
                )

    def test_no_live_trading_and_no_secret_echo(self) -> None:
        _assert_secure(self, self.text)


if __name__ == "__main__":
    unittest.main()
