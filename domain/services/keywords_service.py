# domain/services/keywords_service.py
from __future__ import annotations
from typing import Iterable, List
import unicodedata

def normalize_text(s: str) -> str:
    """
    Normaliza para comparação: lower + remove acentos + strip duplo.
    (Somente stdlib.)
    """
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())

def clean_keyword(raw: str) -> str:
    """
    Higieniza keyword antes de salvar/usar.
    """
    return normalize_text(raw)

def parse_keywords_input(raw: str) -> List[str]:
    """
    Converte "python, flask,  dados" -> ["python","flask","dados"] (limpas).
    """
    parts = [p for p in (raw or "").split(",") if p.strip()]
    return [clean_keyword(p) for p in parts]

def any_keyword_in_text(text: str, keywords: Iterable[str]) -> List[str]:
    """
    Retorna a lista de keywords que ocorrem em 'text' (após normalização).
    Útil para debug/afinamento de ruído.
    """
    nt = normalize_text(text)
    matched = []
    for kw in keywords:
        nkw = clean_keyword(kw)
        if nkw and nkw in nt:
            matched.append(nkw)
    return matched
