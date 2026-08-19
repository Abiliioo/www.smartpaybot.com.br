from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
import app as app_module
import app.routes.dashboard as dashboard_routes
from domain.models import Plan, User, UserKeyword
from infrastructure.db import Base

CSS_PATH = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "style.css"


class DashboardMarkupTest(unittest.TestCase):
    """
    Validacao estatica/unitaria do markup renderizado (via Flask test client,
    sem browser real). Cobre a parte semantica/servidor do SPB-254: o
    controle de remover keyword e um <button> com nome acessivel, e o switch
    de monitoramento e um <input type="checkbox"> real (nao uma div
    clicavel improvisada). O comportamento dependente de CSS/JS (visibilidade
    em touch, foco por teclado) e coberto separadamente em
    StyleSheetAccessibilityTest e exige validacao manual complementar no
    browser (ver relatorio da tarefa).
    """

    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)

        with self.Session() as db:
            free = Plan(slug="free", name="Gratuito", max_keywords=3, max_alerts_day=10)
            db.add(free)
            db.commit()

            user = User(
                username="chipuser",
                email="chipuser@example.test",
                password_hash="hash-chipuser",
                bot_active=True,
                chat_id="chat-chipuser",
                phone="555-chipuser",
                telegram_link_code="code-chipuser",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user_id = user.id

            db.add_all(
                UserKeyword(user_id=user.id, keyword=kw) for kw in ["excel", "python"]
            )
            db.commit()

        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        self.session_patches = [
            patch.object(app_module, "SessionLocal", self.Session),
            patch.object(dashboard_routes, "SessionLocal", self.Session),
        ]
        for session_patch in self.session_patches:
            session_patch.start()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        for session_patch in reversed(self.session_patches):
            session_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _login(self) -> None:
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def _dashboard_html(self) -> str:
        self._login()
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_chip_remove_control_is_a_real_button_with_accessible_name(self) -> None:
        html = self._dashboard_html()

        # Controle interativo real (<button>), nao uma <span>/<div> com
        # onclick -- funciona nativamente com mouse, toque e teclado.
        buttons = re.findall(
            r'<button type="button" class="chip-x"[^>]*>', html
        )
        self.assertEqual(len(buttons), 2, "esperado um chip-x por keyword")

        for btn in buttons:
            self.assertIn("aria-label=\"Remover ", btn)
            self.assertNotIn("onclick=", btn)

    def test_chip_remove_control_not_gated_by_hover_only_markup(self) -> None:
        html = self._dashboard_html()
        # O markup nao deve depender de atributos de exibicao condicionados
        # a hover (isso e resolvido em CSS, verificado separadamente) --
        # aqui garantimos que o botao em si nao esta escondido do DOM/AT
        # (sem hidden, sem aria-hidden, sem display inline).
        self.assertNotRegex(html, r'class="chip-x"[^>]*\bhidden\b')
        self.assertNotRegex(html, r'class="chip-x"[^>]*aria-hidden="true"')

    def test_monitoring_switch_is_a_real_checkbox(self) -> None:
        html = self._dashboard_html()

        match = re.search(r'<input id="bot-toggle"[^>]*>', html)
        self.assertIsNotNone(match, "checkbox #bot-toggle nao encontrado")
        tag = match.group(0)
        self.assertIn('type="checkbox"', tag)
        self.assertIn("checked", tag)  # bot_active=True neste teste

    def test_no_positive_tabindex_in_dashboard(self) -> None:
        html = self._dashboard_html()
        self.assertNotRegex(html, r'tabindex="[1-9]')


class StyleSheetAccessibilityTest(unittest.TestCase):
    """
    Validacao estatica do CSS (nao executa um browser real, apenas garante
    que as regras que tornam chip-x/switch acessiveis por toque/teclado
    estao presentes e que as regras antigas, que quebravam essa interacao,
    nao retornaram). Complementar a validacao manual documentada no
    relatorio da tarefa (Tab, foco visivel, Space, toque em ~390px).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.css = CSS_PATH.read_text(encoding="utf-8")

    def test_switch_input_is_not_display_none(self) -> None:
        # Regressao: display:none remove o elemento da ordem de tabulacao e
        # da arvore de acessibilidade -- torna o switch inalcancavel por
        # teclado. O input precisa continuar presente/focavel (ocultado
        # apenas visualmente via opacity, nunca display:none).
        switch_input_rule = re.search(r"\.switch input\{([^}]*)\}", self.css)
        self.assertIsNotNone(switch_input_rule)
        self.assertNotIn("display:none", switch_input_rule.group(1).replace(" ", ""))

    def test_switch_has_visible_focus_indicator(self) -> None:
        self.assertIn(".switch input:focus-visible + .slider", self.css)

    def test_chip_x_default_is_visible_and_tappable(self) -> None:
        # Fora de qualquer media query, o botao de remover deve ser
        # tocavel por padrao (pointer-events:auto), cobrindo dispositivos
        # sem hover real (a maioria dos touch/mobile).
        base_rule = re.search(r"\n\.chip-x\{([^}]*)\}", self.css)
        self.assertIsNotNone(base_rule)
        body = base_rule.group(1).replace(" ", "")
        self.assertIn("pointer-events:auto", body)
        self.assertIn("opacity:1", body)

    def test_hover_only_fade_is_scoped_to_fine_pointer_devices(self) -> None:
        # O comportamento visual antigo (esconder ate hover) e preservado,
        # mas restrito a dispositivos que de fato tem hover+ponteiro fino
        # (mouse) -- nunca aplicado globalmente, que e o que quebrava touch.
        self.assertIn("@media (hover: hover) and (pointer: fine)", self.css)
        media_block = self.css.split("@media (hover: hover) and (pointer: fine)", 1)[1]
        media_block = media_block[: media_block.index("\n}\n") + 3]
        self.assertIn("pointer-events:none", media_block)
        self.assertIn(".chip:hover .chip-x, .chip:focus-within .chip-x", media_block)

    def test_chip_x_touch_target_is_at_least_24px(self) -> None:
        base_rule = re.search(r"\n\.chip-x\{([^}]*)\}", self.css)
        self.assertIsNotNone(base_rule)
        body = base_rule.group(1)
        width = re.search(r"width:(\d+)px", body)
        height = re.search(r"height:(\d+)px", body)
        self.assertIsNotNone(width)
        self.assertIsNotNone(height)
        self.assertGreaterEqual(int(width.group(1)), 24)
        self.assertGreaterEqual(int(height.group(1)), 24)


if __name__ == "__main__":
    unittest.main()
