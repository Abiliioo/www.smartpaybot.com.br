#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Any, List
from urllib.parse import urljoin

import requests
from lxml import html as lx

from infrastructure.scraping import _DEFAULT_HEADERS  # reaproveita UA/idioma


BASE = "https://www.99freelas.com.br"


def _clean(s: str) -> str:
    return " ".join((s or "").split()).strip()


def _to_int_or_none(s: str) -> int | None:
    import re
    m = re.search(r"(\d+)", s or "")
    return int(m.group(1)) if m else None


def fetch_list(page: int) -> str | None:
    url = f"{BASE}/projects?page={page}"
    try:
        r = requests.get(url, headers=_DEFAULT_HEADERS, timeout=12, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def parse_list(html_text: str) -> List[Dict[str, Any]]:
    tree = lx.fromstring(html_text)
    items: List[Dict[str, Any]] = []

    lis = tree.xpath("//ul[contains(@class,'result-list')]/li[contains(@class,'result-item')]")
    for li in lis:
        try:
            pid = _clean(li.get("data-id") or "")
            pid_int = int(pid) if pid.isdigit() else None

            # título + link
            a = li.xpath(".//h1[@class='title']/a | .//h2[@class='title']/a")
            title = _clean(a[0].text) if a else ""
            href = a[0].get("href") if a else ""
            link = urljoin(BASE, href) if href else ""

            # bloco de informações
            info_p = li.xpath(".//p[contains(@class,'item-text') and contains(@class,'information')]")
            info_text = _clean(info_p[0].text_content()) if info_p else ""

            # categoria / nível (tokens antes de 'Publicado')
            category = level = None
            if "Publicado" in info_text:
                before = info_text.split("Publicado", 1)[0]
                tokens = [t.strip() for t in before.split("|") if t.strip()]
                if tokens:
                    category = tokens[0]
                if len(tokens) >= 2:
                    level = tokens[1]

            # publicado (epoch ms)
            pub_ms = None
            dt_b = li.xpath(".//p[contains(@class,'item-text')][contains(@class,'information')]//b[@class='datetime'][@cp-datetime]")
            if dt_b:
                try:
                    pub_ms = int(dt_b[0].get("cp-datetime"))
                except Exception:
                    pub_ms = None

            # propostas / interessados
            proposals = None
            interested = None
            prop_b = li.xpath("( .//p[contains(@class,'item-text')][contains(@class,'information')]//text()[contains(.,'Propostas')] )[1]/following::b[1]")
            if prop_b:
                proposals = _to_int_or_none(_clean(prop_b[0].text_content()))
            int_b = li.xpath("( .//p[contains(@class,'item-text')][contains(@class,'information')]//text()[contains(.,'Interessados')] )[1]/following::b[1]")
            if int_b:
                interested = _to_int_or_none(_clean(int_b[0].text_content()))

            # cliente (nome): tenta <a>; se não tiver, pega de span/strong; por fim, do texto cru
            client_name = None
            p_client = li.xpath(".//p[contains(@class,'item-text') and contains(@class,'client')]")
            if p_client:
                pc = p_client[0]

                # 1) <a>
                name_a = pc.xpath("normalize-space(.//a[1])")
                if name_a:
                    client_name = _clean(name_a)
                else:
                    # 2) <span> ou <strong>
                    name_el = pc.xpath("normalize-space(.//span[1])") or pc.xpath("normalize-space(.//strong[1])")
                    name_el = name_el if isinstance(name_el, str) else ""
                    if name_el:
                        client_name = _clean(name_el)
                    else:
                        # 3) texto cru do <p> (remove 'Cliente:' e pedaços de avaliações)
                        raw_text = " ".join([t for t in pc.xpath(".//text()") if t and t.strip()])
                        raw_text = _clean(raw_text)
                        if raw_text:
                            # remove prefixo 'Cliente:' se houver
                            raw_text = raw_text.replace("Cliente:", "").strip()
                            # remove sufixos típicos: "(Sem feedback)", "(12 avaliações)" etc.
                            import re
                            raw_text = re.sub(r"\(\s*Sem feedback\s*\)", "", raw_text, flags=re.I)
                            raw_text = re.sub(r"\(\s*\d+\s+avalia(?:ção|ções)\s*\)", "", raw_text, flags=re.I)
                            # tira possíveis estrelas/símbolos perdidos
                            raw_text = raw_text.replace("⭐", "").strip()
                            client_name = raw_text or None



            # rating + reviews
            client_rating = None
            star = li.xpath(".//span[contains(@class,'avaliacoes-star')][@data-score]")
            if star:
                try:
                    client_rating = float(star[0].get("data-score").replace(",", "."))
                except Exception:
                    client_rating = None

            client_reviews = None
            rev = li.xpath(".//span[contains(@class,'avaliacoes-text')]")
            if rev:
                txt = _clean(rev[0].text_content()).lower()
                if "sem feedback" in txt:
                    client_reviews = 0
                else:
                    client_reviews = _to_int_or_none(txt)

            items.append({
                "project_id": pid_int,
                "title": title,
                "link": link,
                "category": category,
                "level": level,
                "published_ms": pub_ms,
                "proposals": proposals,
                "interested": interested,
                "client_name": client_name,
                "client_rating": client_rating,
                "client_reviews": client_reviews,
            })
        except Exception:
            # segue para o próximo item
            continue

    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe: extrai campos da listagem /projects (sem login).")
    ap.add_argument("--pages", type=int, default=1, help="Qtde de páginas para varrer (default: 1)")
    ap.add_argument("--filter-id", type=int, help="Se informado, mostra só este project_id")
    ap.add_argument("--pretty", action="store_true", help="JSON identado")
    args = ap.parse_args()

    out: List[Dict[str, Any]] = []
    for p in range(1, max(1, args.pages) + 1):
        html = fetch_list(p)
        if not html:
            print(f"Página {p}: falhou o download; pulando…")
            continue
        out.extend(parse_list(html))

    if args.filter_id:
        out = [x for x in out if x.get("project_id") == args.filter_id]

    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))
    print(f"\nResumo: itens={len(out)} (páginas varridas={args.pages})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
