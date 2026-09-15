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
import app.routes.admin as admin_routes
import app.routes.dashboard as dashboard_routes
from domain.models import Plan, User
from infrastructure.db import Base

JS_PATH = Path(__file__).resolve().parent.parent / 'app' / 'static' / 'js' / 'script.js'


class ThemeToggleScopeSPB251ETest(unittest.TestCase):
    """
    PR #48 (finding IMPORTANT): o botao de tema so pode aparecer onde o
    design system claro/escuro foi de fato aplicado (dashboard principal).
    Admin e Oportunidades continuam LATER -- o controle nao pode parecer
    funcional la.
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
            db.add_all([
                Plan(slug="free", name="Gratuito", max_keywords=3, max_alerts_day=10),
                Plan(slug="pro", name="Pro", max_keywords=-1, max_alerts_day=-1),
            ])
            admin_user = User(
                username="scope_admin",
                email="scope_admin@example.test",
                password_hash="hash",
                is_admin=True,
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            self.admin_id = int(admin_user.id)

        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.patches = [
            patch.object(app_module, "SessionLocal", self.Session),
            patch.object(dashboard_routes, "SessionLocal", self.Session),
            patch.object(admin_routes, "SessionLocal", self.Session),
        ]
        for item in self.patches:
            item.start()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _login(self) -> None:
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.admin_id)
            session["_fresh"] = True

    def test_theme_toggle_present_on_dashboard_home(self) -> None:
        self._login()
        html = self.client.get("/dashboard/").get_data(as_text=True)
        self.assertIn('id="theme-toggle"', html)

    def test_theme_toggle_absent_on_opportunities_projects(self) -> None:
        self._login()
        html = self.client.get("/dashboard/projects").get_data(as_text=True)
        self.assertNotIn('id="theme-toggle"', html)

    def test_theme_toggle_absent_on_admin_for_admin_user(self) -> None:
        self._login()
        html = self.client.get("/admin/").get_data(as_text=True)
        self.assertNotIn('id="theme-toggle"', html)

    def test_theme_toggle_absent_when_unauthenticated(self) -> None:
        html = self.client.get("/auth/login").get_data(as_text=True)
        self.assertNotIn('id="theme-toggle"', html)

    def test_notification_avatar_name_and_logout_preserved_on_projects(self) -> None:
        # A correcao de escopo remove SO o theme-toggle -- sino, avatar,
        # nome e logout continuam presentes em todo lugar autenticado.
        self._login()
        html = self.client.get("/dashboard/projects").get_data(as_text=True)
        self.assertIn('class="notification-link"', html)
        self.assertIn('class="user-avatar"', html)
        self.assertIn('class="user-name"', html)
        self.assertIn('href="/auth/logout"', html)


class ThemeTogglePersistenceFailureStructuralTest(unittest.TestCase):
    """
    PR #48 (finding MINOR): sem runner JS neste projeto, esta e uma
    regressao ESTRUTURAL sobre o texto-fonte de initThemeToggle() -- prova
    que o handler guarda o estado anterior, checa res.ok e restaura
    data-theme em falha (HTTP 5xx e exception de rede). Isto NAO substitui
    QA de navegador; e uma rede de seguranca contra regressao textual.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = JS_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"function initThemeToggle\(\)\s*\{.*?\n\}\n",
            cls.script,
            re.DOTALL,
        )
        assert match, "initThemeToggle() nao encontrada em script.js"
        cls.handler = match.group(0)

    def test_guards_current_theme_before_switching(self) -> None:
        self.assertIn(
            "const current = root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';",
            self.handler,
        )

    def test_checks_response_ok_before_accepting_new_theme(self) -> None:
        self.assertIn("if (!res.ok)", self.handler)

    def test_restores_previous_theme_on_http_failure_and_on_network_error(self) -> None:
        restores = re.findall(r"root\.setAttribute\('data-theme', current\);", self.handler)
        # uma vez no ramo `if (!res.ok)`, outra vez no `catch` -- as duas
        # formas de falha (HTTP nao-2xx e exception de rede) restauram.
        self.assertEqual(len(restores), 2, self.handler)

    def test_shows_user_feedback_on_failure(self) -> None:
        self.assertIn("Não foi possível salvar a preferência de tema.", self.handler)
        self.assertIn("flashClient(", self.handler)

    def test_does_not_force_a_page_reload(self) -> None:
        self.assertNotIn("location.reload", self.handler)

    def test_success_path_keeps_new_theme_without_reverting(self) -> None:
        # No caminho de sucesso (res.ok truthy), nao ha nenhuma chamada
        # extra de setAttribute alem da otimista feita antes do POST.
        set_attr_calls = re.findall(r"setAttribute\('data-theme', \w+\);", self.handler)
        self.assertEqual(len(set_attr_calls), 3)  # otimista + 2 restauracoes (falha/catch)


if __name__ == "__main__":
    unittest.main()
