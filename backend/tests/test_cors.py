"""CORS configurable por entorno (spec 002, RF-8)."""

import os
import unittest
from unittest.mock import patch

from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.middleware import Middleware

import app.main as main_module
from app.config import Settings

PAGES_ORIGIN = "https://jejs-ia97.github.io"


def _apply_origins(origins_csv: str) -> None:
    """Reconstruye el stack de middleware igual que en el arranque."""
    main_module.app.user_middleware = [
        Middleware(
            CORSMiddleware,
            **main_module._cors_kwargs(origins_csv),
        )
    ]
    main_module.app.middleware_stack = None


class CorsSettingsTests(unittest.TestCase):
    def test_cors_kwargs_parses_csv(self) -> None:
        kwargs = main_module._cors_kwargs(
            " http://localhost:5173 , https://pages.example , "
        )
        self.assertEqual(
            kwargs["allow_origins"],
            ["http://localhost:5173", "https://pages.example"],
        )
        self.assertIs(kwargs["allow_credentials"], True)
        self.assertEqual(kwargs["allow_methods"], ["*"])
        self.assertEqual(kwargs["allow_headers"], ["*"])

    def test_cors_kwargs_strips_path_to_origin(self) -> None:
        # El navegador sólo manda scheme://host: una entrada con ruta
        # ("/crypto-bot/") se normaliza al origen real (RF-8).
        kwargs = main_module._cors_kwargs(
            "https://jejs-ia97.github.io/crypto-bot/,http://localhost:5173/"
        )
        self.assertEqual(
            kwargs["allow_origins"],
            ["https://jejs-ia97.github.io", "http://localhost:5173"],
        )

    def test_cors_origins_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(_env_file=None)
        self.assertIn("http://localhost:5173", settings.cors_origins)

    def test_cors_origins_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": f"{PAGES_ORIGIN},http://localhost:5173"},
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(
            settings.cors_origins,
            f"{PAGES_ORIGIN},http://localhost:5173",
        )


class CorsHeaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_middleware = list(main_module.app.user_middleware)
        self._original_stack = main_module.app.middleware_stack
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        main_module.app.user_middleware = self._original_middleware
        main_module.app.middleware_stack = self._original_stack

    def test_allowed_origin_gets_header(self) -> None:
        _apply_origins(f"{PAGES_ORIGIN},http://localhost:5173")
        client = TestClient(main_module.app)
        response = client.get(
            "/health",
            headers={"Origin": PAGES_ORIGIN},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            PAGES_ORIGIN,
        )

    def test_disallowed_origin_gets_no_header(self) -> None:
        _apply_origins("http://localhost:5173")
        client = TestClient(main_module.app)
        response = client.get(
            "/health",
            headers={"Origin": "https://evil.example"},
        )
        self.assertIsNone(
            response.headers.get("access-control-allow-origin")
        )

    def test_stored_value_with_path_matches_browser_origin(self) -> None:
        # Valor guardado con la ruta de Pages: el Origin real del
        # navegador (sin ruta) sigue siendo permitido.
        _apply_origins("https://jejs-ia97.github.io/crypto-bot/")
        client = TestClient(main_module.app)
        response = client.get(
            "/health",
            headers={"Origin": PAGES_ORIGIN},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            PAGES_ORIGIN,
        )

    def test_preflight_allows_authorization_header(self) -> None:
        _apply_origins(PAGES_ORIGIN)
        client = TestClient(main_module.app)
        response = client.options(
            "/health",
            headers={
                "Origin": PAGES_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        allow_headers = response.headers.get(
            "access-control-allow-headers",
            "",
        ).lower()
        self.assertIn("authorization", allow_headers)


if __name__ == "__main__":
    unittest.main()
