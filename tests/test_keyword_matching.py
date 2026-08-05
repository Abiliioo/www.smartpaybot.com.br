from __future__ import annotations

import unittest

from domain.services.projects_service import match_users_for_title


class KeywordMatchingTest(unittest.TestCase):
    def keyword_matches_text(self, keyword: str, text: str) -> bool:
        return bool(match_users_for_title(text, {1: [keyword]}))

    def assertMatch(self, keyword: str, text: str) -> None:
        self.assertTrue(self.keyword_matches_text(keyword, text), f"{keyword!r} should match {text!r}")

    def assertNoMatch(self, keyword: str, text: str) -> None:
        self.assertFalse(self.keyword_matches_text(keyword, text), f"{keyword!r} should not match {text!r}")

    def test_simple_words_match_with_lexical_boundaries(self) -> None:
        cases = [
            ("excel", "Excel avancado", True),
            ("excel", "Planilha em Excel", True),
            ("excel", "Excel/VBA", True),
            ("excel", "Excel-VBA", True),
            ("excel", "excelente", False),
            ("excel", "excelencia", False),
            ("excel", "macroexcel", False),
            ("python", "Desenvolvedor Python", True),
            ("python", "Python/Django", True),
            ("python", "Python-Django", True),
            ("python", "pythonista", False),
            ("python", "cpythonista", False),
        ]
        for keyword, text, expected in cases:
            with self.subTest(keyword=keyword, text=text):
                self.assertEqual(self.keyword_matches_text(keyword, text), expected)

    def test_short_terms_do_not_match_inside_larger_words(self) -> None:
        cases = [
            ("ia", "IA generativa", True),
            ("ia", "IA/ML", True),
            ("ia", "Projeto de IA", True),
            ("ia", "secretaria", False),
            ("ia", "diagrama", False),
            ("ia", "especialista", False),
            ("api", "API REST", True),
            ("api", "API/REST", True),
            ("api", "Integracao com API", True),
            ("api", "capital", False),
            ("api", "capilar", False),
        ]
        for keyword, text, expected in cases:
            with self.subTest(keyword=keyword, text=text):
                self.assertEqual(self.keyword_matches_text(keyword, text), expected)

    def test_phrases_accept_space_hyphen_and_slash_between_tokens(self) -> None:
        cases = [
            ("mercado livre", "Gestao de Mercado Livre", True),
            ("mercado livre", "Especialista em mercado livre", True),
            ("mercado livre", "Mercado  Livre", True),
            ("mercado livre", "Mercado-Livre", True),
            ("mercado livre", "mercado/livre", True),
            ("mercado livre", "mercado livreiro", False),
            ("mercado livre", "livreiro de mercado", False),
            ("power bi", "Dashboard em Power BI", True),
            ("power bi", "Power-BI", True),
            ("power bi", "Power  BI", True),
            ("power bi", "powerbi", False),
        ]
        for keyword, text, expected in cases:
            with self.subTest(keyword=keyword, text=text):
                self.assertEqual(self.keyword_matches_text(keyword, text), expected)

    def test_case_accents_and_punctuation(self) -> None:
        for text in ("excel,", "excel.", "(excel)", "[excel]", "excel:", "excel;", "excel!"):
            with self.subTest(text=text):
                self.assertMatch("excel", text)

        self.assertMatch("acao", "Plano de a\u00e7\u00e3o")
        self.assertMatch("a\u00e7\u00e3o", "Plano de acao")
        self.assertMatch("EXCEL", "curso de excel")
        self.assertNoMatch("excel", "Excelencia operacional")

    def test_special_regex_characters_are_literal(self) -> None:
        cases = [
            ("c++", "Desenvolvedor C++", True),
            ("c#", "Projeto C#", True),
            (".net", "API .NET", True),
            ("node.js", "Node.js backend", True),
            ("a+b", "Formula a+b", True),
            ("node.js", "nodejs backend", False),
        ]
        for keyword, text, expected in cases:
            with self.subTest(keyword=keyword, text=text):
                self.assertEqual(self.keyword_matches_text(keyword, text), expected)

    def test_match_users_for_title_uses_lexical_matching(self) -> None:
        users_keywords = {
            1: ["excel"],
            2: ["api"],
            3: ["mercado livre"],
        }

        self.assertEqual(match_users_for_title("excelente oportunidade", users_keywords), [])
        self.assertEqual(match_users_for_title("Integracao com API", users_keywords), [(2, "api")])
        self.assertEqual(match_users_for_title("Gestao de Mercado-Livre", users_keywords), [(3, "mercado livre")])


if __name__ == "__main__":
    unittest.main()
