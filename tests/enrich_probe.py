#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import Dict, Any

from infrastructure.scraping import fetch_html, scrape_99freelas_detail
from workers.notifier import _render_rich_message  # reaproveita o render do card


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Probe de enrichment: monta o CARD do notifier (sem enviar)."
    )
    ap.add_argument("url", help="URL do projeto (detalhe) do 99Freelas")
    ap.add_argument("--title", default="Projeto (teste)", help="Título a exibir no card")
    ap.add_argument("--kw", default="keyword", help="Matched keyword simulada")
    args = ap.parse_args()

    html = fetch_html(args.url)
    if not html:
        print("ERROR: fetch_html retornou None (timeout/403/erro).")
        return 1

    extra: Dict[str, Any] = scrape_99freelas_detail(html)
    print(">>> extra:", extra)

    card = _render_rich_message(
        title=args.title,
        link=args.url,
        matched_kw=args.kw,
        extra=extra
    )
    print("\n===== CARD GERADO =====\n")
    print(card)
    print("\n=======================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
