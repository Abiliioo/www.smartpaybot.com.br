# domain/services/keywords_service.py
from __future__ import annotations
import re
import unicodedata
from typing import Iterable, List

_LEXICAL_SEPARATORS_RE = re.compile(r"[\s\-/]+")
_LEXICAL_SEPARATOR_PATTERN = r"[\s\-/]+"
_WORD_CHAR_PATTERN = r"[a-z0-9]"

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

def keyword_matches_text(keyword: str, text: str) -> bool:
    """
    Casa keyword normalizada como palavra/frase completa, nao substring.
    Espaco, hifen e barra sao separadores equivalentes entre tokens.
    """
    nkw = clean_keyword(keyword)
    nt = normalize_text(text)
    if not nkw or not nt:
        return False

    tokens = [token for token in _LEXICAL_SEPARATORS_RE.split(nkw) if token]
    if not tokens:
        return False

    body = _LEXICAL_SEPARATOR_PATTERN.join(re.escape(token) for token in tokens)
    pattern = rf"(?<!{_WORD_CHAR_PATTERN}){body}(?!{_WORD_CHAR_PATTERN})"
    return re.search(pattern, nt) is not None

def any_keyword_in_text(text: str, keywords: Iterable[str]) -> List[str]:
    """
    Retorna a lista de keywords que ocorrem em 'text' (após normalização).
    Útil para debug/afinamento de ruído.
    """
    matched = []
    for kw in keywords:
        nkw = clean_keyword(kw)
        if nkw and keyword_matches_text(nkw, text):
            matched.append(nkw)
    return matched
