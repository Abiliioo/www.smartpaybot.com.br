#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

from infrastructure.scraping import fetch_html, scrape_99freelas_detail
from lxml import html as lxml_html


def _load_urls(args: argparse.Namespace) -> List[str]:
    urls: List[str] = []
    urls.extend(args.urls or [])
    if args.file:
        p = Path(args.file)
        urls.extend([l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip()])
    return [u.strip() for u in urls if u.strip()]


def _extract_debug_snippets(page_html: str) -> Dict[str, str]:
    try:
        tree = lxml_html.fromstring(page_html)
        base_p = tree.xpath("(//p[contains(@class,'item-text')][contains(.,'Publicado')])[1]")
        client_p = tree.xpath("(//p[contains(@class,'item-text') and contains(@class,'client')])[1]")
        base_html = lxml_html.tostring(base_p[0], encoding="unicode") if base_p else ""
        client_html = lxml_html.tostring(client_p[0], encoding="unicode") if client_p else ""
        return {"p_info_html": base_html, "p_client_html": client_html}
    except Exception:
        return {"p_info_html": "", "p_client_html": ""}


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe de scraping 99Freelas.")
    ap.add_argument("urls", nargs="*", help="URLs de projetos (detalhe) do 99Freelas")
    ap.add_argument("-f", "--file", help="Arquivo .txt com uma URL por linha")
    ap.add_argument("--snippets", action="store_true", help="Imprimir trechos de HTML relevantes")
    ap.add_argument("--pretty", action="store_true", help="Imprimir JSON identado")
    args = ap.parse_args()

    urls = _load_urls(args)
    if not urls:
        print("Nenhuma URL informada.")
        return 2

    failures = 0
    for idx, url in enumerate(urls, 1):
        print(f"\n=== [{idx}/{len(urls)}] {url}")
        html_text = fetch_html(url)
        if not html_text:
            print("❌ fetch_html retornou None (timeout/403/erro).")
            failures += 1
            continue

        print(f"HTML baixado: {len(html_text)} bytes")
        extra: Dict[str, Any] = scrape_99freelas_detail(html_text)

        missing = [k for k, v in extra.items() if v in (None, "")]
        ok = [k for k, v in extra.items() if v not in (None, "")]
        print("Campos OK:     ", ", ".join(ok) if ok else "(nenhum)")
        print("Campos faltando:", ", ".join(missing) if missing else "(nenhum)")

        print(json.dumps(extra, ensure_ascii=False, indent=2 if args.pretty else None))

        if args.snippets:
            snips = _extract_debug_snippets(html_text)
            print("\n--- <p class='item-text information'> ---")
            print(snips.get("p_info_html", "")[:2000] or "(não encontrado)")
            print("\n--- <p class='item-text client'> ---")
            print(snips.get("p_client_html", "")[:2000] or "(não encontrado)")

        if extra.get("proposals") is None or extra.get("interested") is None:
            failures += 1

    print(f"\nResumo: testados={len(urls)}, falhas={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
