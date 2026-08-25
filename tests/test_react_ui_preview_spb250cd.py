from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import app as app_module
from app.frontend_manifest import ViteManifestError, load_vite_assets


def _write_manifest(directory: Path, content: dict) -> Path:
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(content), encoding="utf-8")
    return manifest_path


class ViteManifestHelperTest(unittest.TestCase):
    def test_reads_index_html_entry_with_js_and_css(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_manifest(
                Path(tmp),
                {
                    "index.html": {
                        "file": "assets/index-abc123.js",
                        "css": ["assets/index-def456.css"],
                    }
                },
            )

            assets = load_vite_assets(manifest_path)

        self.assertEqual(assets.js_file, "dist/assets/index-abc123.js")
        self.assertEqual(assets.css_files, ("dist/assets/index-def456.css",))

    def test_uses_first_entry_when_index_html_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_manifest(
                Path(tmp),
                {
                    "src/main.tsx": {
                        "file": "assets/main-abc123.js",
                        "isEntry": True,
                        "css": ["assets/main-def456.css"],
                    }
                },
            )

            assets = load_vite_assets(manifest_path)

        self.assertEqual(assets.js_file, "dist/assets/main-abc123.js")
        self.assertEqual(assets.css_files, ("dist/assets/main-def456.css",))

    def test_includes_imported_css(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_manifest(
                Path(tmp),
                {
                    "index.html": {
                        "file": "assets/index.js",
                        "css": ["assets/index.css"],
                        "imports": ["_vendor"],
                    },
                    "_vendor": {
                        "file": "assets/vendor.js",
                        "css": ["assets/vendor.css"],
                    },
                },
            )

            assets = load_vite_assets(manifest_path)

        self.assertEqual(
            assets.css_files,
            ("dist/assets/index.css", "dist/assets/vendor.css"),
        )

    def test_missing_manifest_raises_controlled_error(self) -> None:
        with self.assertRaises(ViteManifestError):
            load_vite_assets("missing-manifest.json")


class ReactUiPreviewRouteTest(unittest.TestCase):
    def _client_with_manifest(self, manifest_path: Path | None):
        app = app_module.create_app()
        app.config["TESTING"] = True
        if manifest_path is not None:
            app.config["VITE_MANIFEST_PATH"] = str(manifest_path)
        return app.test_client()

    def test_ui_preview_renders_react_shell_with_manifest_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = _write_manifest(
                Path(tmp),
                {
                    "index.html": {
                        "file": "assets/index-abc123.js",
                        "css": ["assets/index-def456.css"],
                    }
                },
            )
            client = self._client_with_manifest(manifest_path)

            response = client.get("/ui-preview")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="root"></div>', html)
        self.assertIn('type="module"', html)
        self.assertIn("/static/dist/assets/index-abc123.js", html)
        self.assertIn("/static/dist/assets/index-def456.css", html)
        self.assertNotIn("cdn.tailwindcss.com", html)

    def test_ui_preview_returns_503_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_manifest = Path(tmp) / "missing.json"
            client = self._client_with_manifest(missing_manifest)

            response = client.get("/ui-preview")

        self.assertEqual(response.status_code, 503)
        self.assertIn("React build nao encontrado", response.get_data(as_text=True))

    def test_existing_public_routes_keep_responding(self) -> None:
        client = self._client_with_manifest(None)

        expected_statuses = {
            "/": 200,
            "/pro": 200,
            "/auth/login": 200,
            "/auth/register": 200,
            "/healthz": 200,
        }
        for path, expected_status in expected_statuses.items():
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, expected_status)

    def test_dashboard_stays_protected_and_does_not_render_react(self) -> None:
        client = self._client_with_manifest(None)

        response = client.get("/dashboard/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    def test_admin_stays_protected_and_does_not_render_react(self) -> None:
        client = self._client_with_manifest(None)

        response = client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
