from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ViteManifestError(RuntimeError):
    pass


@dataclass(frozen=True)
class ViteAssets:
    js_file: str
    css_files: tuple[str, ...]


def default_manifest_path(static_folder: str | None) -> Path:
    if not static_folder:
        raise ViteManifestError("Static folder nao configurado.")
    return Path(static_folder) / "dist" / ".vite" / "manifest.json"


def load_vite_assets(
    manifest_path: str | Path,
    entry_name: str = "index.html",
) -> ViteAssets:
    path = Path(manifest_path)
    if not path.is_file():
        raise ViteManifestError("React build nao encontrado.")

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ViteManifestError("Manifest Vite invalido.") from exc

    if not isinstance(manifest, dict):
        raise ViteManifestError("Manifest Vite invalido.")

    entry = _select_entry(manifest, entry_name)
    js_file = _asset_path(entry.get("file"))
    css_files = _collect_css(manifest, entry)
    return ViteAssets(js_file=js_file, css_files=css_files)


def _select_entry(manifest: dict[str, Any], entry_name: str) -> dict[str, Any]:
    candidate = manifest.get(entry_name)
    if isinstance(candidate, dict):
        return candidate

    for value in manifest.values():
        if isinstance(value, dict) and value.get("isEntry") is True:
            return value

    raise ViteManifestError("Entrada principal do Vite nao encontrada.")


def _collect_css(manifest: dict[str, Any], entry: dict[str, Any]) -> tuple[str, ...]:
    css_files: list[str] = []
    seen_entries: set[str] = set()

    def add_css(value: Any) -> None:
        if not isinstance(value, list):
            return
        for item in value:
            css_path = _asset_path(item)
            if css_path not in css_files:
                css_files.append(css_path)

    def visit(node: dict[str, Any]) -> None:
        add_css(node.get("css"))
        imports = node.get("imports")
        if not isinstance(imports, list):
            return
        for import_name in imports:
            if not isinstance(import_name, str) or import_name in seen_entries:
                continue
            seen_entries.add(import_name)
            imported = manifest.get(import_name)
            if isinstance(imported, dict):
                visit(imported)

    visit(entry)
    return tuple(css_files)


def _asset_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ViteManifestError("Asset Vite invalido.")
    normalized = value.replace("\\", "/").lstrip("/")
    if normalized.startswith("dist/") or normalized.startswith("../"):
        raise ViteManifestError("Asset Vite fora do diretorio esperado.")
    return f"dist/{normalized}"
