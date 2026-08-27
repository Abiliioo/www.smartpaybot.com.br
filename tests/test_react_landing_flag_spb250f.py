from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app as app_module
import infrastructure.config as config_module


def _write_manifest(directory: Path, content: dict | None = None) -> Path:
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            content
            or {
                "index.html": {
                    "file": "assets/index-spb250f.js",
                    "css": ["assets/index-spb250f.css"],
                }
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


class ReactLandingFlagConfigTest(unittest.TestCase):
    def _settings_with_flag(self, value: str):
        with mock.patch.dict(os.environ, {"REACT_LANDING_ENABLED": value}, clear=False):
            importlib.reload(config_module)
            try:
                return config_module.get_settings()
            finally:
                importlib.reload(config_module)

    def test_react_landing_enabled_accepts_only_explicit_true_values(self) -> None:
        for value in ("1", "true", "yes", "on"):
            with self.subTest(value=value):
                self.assertTrue(self._settings_with_flag(value).REACT_LANDING_ENABLED)

    def test_react_landing_enabled_is_false_for_other_values(self) -> None:
        for value in ("", "0", "false", "off", "landing"):
            with self.subTest(value=value):
                self.assertFalse(self._settings_with_flag(value).REACT_LANDING_ENABLED)


class ReactLandingFlagRouteTest(unittest.TestCase):
    def _client(self, react_landing_enabled: bool, manifest_path: Path | None = None):
        app = app_module.create_app()
        app.config.update(
            TESTING=True,
            REACT_LANDING_ENABLED=react_landing_enabled,
        )
        if manifest_path is not None:
            app.config["VITE_MANIFEST_PATH"] = str(manifest_path)
        return app.test_client()

    def test_home_renders_jinja_when_flag_is_off(self) -> None:
        client = self._client(react_landing_enabled=False)

        response = client.get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("SmartPayBot", html)
        self.assertNotIn('<div id="root"></div>', html)

    def test_home_renders_react_shell_when_flag_is_on_and_manifest_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_manifest(Path(tmp))
            client = self._client(True, manifest_path)

            response = client.get("/")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="root"></div>', html)
        self.assertIn('data-page-mode="landing"', html)
        self.assertIn('content="index, follow"', html)
        self.assertIn("/static/dist/assets/index-spb250f.js", html)
        self.assertIn("/static/dist/assets/index-spb250f.css", html)

    def test_home_falls_back_to_jinja_when_flag_is_on_and_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_manifest = Path(tmp) / "missing.json"
            client = self._client(True, missing_manifest)

            response = client.get("/")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("SmartPayBot", html)
        self.assertNotIn('<div id="root"></div>', html)
        self.assertNotIn("React build nao encontrado", html)

    def test_ui_preview_contract_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_manifest(Path(tmp))
            client = self._client(False, manifest_path)

            response = client.get("/ui-preview")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-page-mode="preview"', html)
        self.assertIn('content="noindex, nofollow"', html)
        self.assertIn("/static/dist/assets/index-spb250f.js", html)

    def test_ui_preview_still_returns_503_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_manifest = Path(tmp) / "missing.json"
            client = self._client(False, missing_manifest)

            response = client.get("/ui-preview")

        self.assertEqual(response.status_code, 503)
        self.assertIn("React build nao encontrado", response.get_data(as_text=True))

    def test_existing_routes_are_preserved(self) -> None:
        client = self._client(react_landing_enabled=True)

        expected_statuses = {
            "/pro": 200,
            "/auth/login": 200,
            "/auth/register": 200,
            "/dashboard/": 302,
            "/admin/": 302,
        }
        for path, expected_status in expected_statuses.items():
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, expected_status)
        self.assertIn("/auth/login", client.get("/dashboard/").headers["Location"])
        self.assertIn("/auth/login", client.get("/admin/").headers["Location"])


if __name__ == "__main__":
    unittest.main()
