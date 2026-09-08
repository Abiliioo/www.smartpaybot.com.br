from __future__ import annotations

import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
import app as app_module
import app.routes.dashboard as dashboard_routes
import domain.services.dashboard_metrics_service as dashboard_metrics_service
from domain.models import Plan, ProjectGlobal, ProjectPerUser, Subscription, User, UserAlertDaily, UserKeyword
from infrastructure.db import Base

NOW = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)


class DashboardMetricsUiSPB251DTest(unittest.TestCase):
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
            pro = Plan(slug="pro", name="Pro", max_keywords=-1, max_alerts_day=-1)
            db.add_all([free, pro])
            db.commit()
            user = User(
                username="metricsui",
                email="metricsui@example.test",
                password_hash="hash",
                bot_active=True,
                chat_id="chat-1",
                telegram_link_code="link-code-1",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user_id = int(user.id)
            db.add_all(UserKeyword(user_id=self.user_id, keyword=kw, created_at=NOW - timedelta(days=10)) for kw in ["excel", "python"])
            db.add(UserAlertDaily(user_id=self.user_id, date=NOW.date(), alerts_sent=4))
            db.commit()

        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        self.patches = [
            patch.object(app_module, "SessionLocal", self.Session),
            patch.object(dashboard_routes, "SessionLocal", self.Session),
            patch.object(dashboard_routes, "datetime", _FrozenDateTime),
            patch.object(dashboard_metrics_service, "datetime", _FrozenDateTime),
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
            session["_user_id"] = str(self.user_id)
            session["_fresh"] = True

    def _project(
        self,
        project_id: int,
        *,
        keyword: str = "excel",
        created_at: datetime | None = None,
        published_at: datetime | None = None,
        notified_at: datetime | None = None,
        won: bool = False,
        won_cents: int = 0,
        won_at: datetime | None = None,
    ) -> None:
        created_at = created_at or NOW
        with self.Session() as db:
            gp = ProjectGlobal(
                project_id=project_id,
                title=f"Projeto {project_id}",
                link=f"https://example.test/{project_id}",
                published_at=published_at,
            )
            db.add(gp)
            db.commit()
            db.refresh(gp)
            db.add(
                ProjectPerUser(
                    user_id=self.user_id,
                    global_project_id=gp.id,
                    title=gp.title,
                    link=gp.link,
                    matched_keyword=keyword,
                    created_at=created_at,
                    notified_at=notified_at,
                    won=won,
                    won_cents=won_cents,
                    won_at=won_at,
                )
            )
            db.commit()

    def _dashboard_html(self) -> str:
        self._login()
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_review_count_and_open_wording_do_not_appear_on_dashboard(self) -> None:
        self._project(1)
        html = self._dashboard_html()
        self.assertNotIn("review_count", html)
        self.assertNotIn("em aberto", html.lower())

    def test_next_best_action_removed(self) -> None:
        html = self._dashboard_html()
        self.assertNotIn("Próxima melhor ação", html)

    def test_four_main_kpis_render(self) -> None:
        html = self._dashboard_html()
        self.assertEqual(html.count('class="metric-kpi-card"'), 4)

    def test_opportunities_today_render(self) -> None:
        self._project(1, created_at=NOW)
        html = self._dashboard_html()
        self.assertIn("Hoje", html)
        self.assertRegex(html, r'id="count-today">\s*1\s*</div>')

    def test_seven_days_render(self) -> None:
        self._project(1, created_at=NOW - timedelta(days=2))
        html = self._dashboard_html()
        self.assertIn("7 dias", html)
        self.assertRegex(html, r'id="count-week">\s*1\s*</div>')

    def test_pct_none_has_no_fake_percentage(self) -> None:
        self._project(1, created_at=NOW)
        html = self._dashboard_html()
        self.assertIn("Sem comparação anterior", html)
        self.assertNotIn("100% vs. período anterior", html)

    def test_latency_none_renders_empty_state(self) -> None:
        html = self._dashboard_html()
        self.assertIn("Sem dados", html)

    def test_latency_sub_minute_renders_less_than_one_minute(self) -> None:
        self._project(1, published_at=NOW, notified_at=NOW + timedelta(seconds=30))
        html = self._dashboard_html()
        self.assertIn("&lt; 1 min", html)

    def test_productive_keywords_render(self) -> None:
        self._project(1, keyword="excel")
        html = self._dashboard_html()
        self.assertIn("Keywords produtivas", html)
        self.assertIn("1 / 2", html)

    def test_chart_has_real_7d_and_30d_data(self) -> None:
        self._project(1, created_at=NOW)
        html = self._dashboard_html()
        match = re.search(r"data-series='([^']+)'", html)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(len(data["7d"]), 7)
        self.assertEqual(len(data["30d"]), 30)
        self.assertEqual(data["7d"][-1]["count"], 1)

    def test_results_use_registered_wording(self) -> None:
        self._project(1, won=True, won_cents=12345, won_at=NOW)
        html = self._dashboard_html()
        self.assertIn("Resultados registrados", html)
        self.assertIn("Projetos ganhos registrados", html)
        self.assertIn("Valor registrado em projetos ganhos", html)

    def test_no_generated_revenue_wording(self) -> None:
        html = self._dashboard_html()
        self.assertNotIn("receita gerada", html.lower())

    def test_recent_projects_limited_to_three(self) -> None:
        for idx in range(5):
            self._project(idx + 1, created_at=NOW + timedelta(minutes=idx))
        html = self._dashboard_html()
        self.assertEqual(html.count('class="opportunity-item opportunity-item--metric"'), 3)

    def test_recent_projects_do_not_show_open_state(self) -> None:
        self._project(1)
        html = self._dashboard_html()
        self.assertNotIn("Em aberto", html)

    def test_navbar_contains_dashboard_opportunities_settings(self) -> None:
        html = self._dashboard_html()
        self.assertIn(">Dashboard<", html)
        self.assertIn(">Oportunidades<", html)
        self.assertIn(">Configurações<", html)

    def test_notification_bell_links_to_opportunities_without_unread_claim(self) -> None:
        html = self._dashboard_html()
        self.assertRegex(html, r'class="notification-link" href="/dashboard/projects" aria-label="Ver oportunidades"')
        self.assertNotIn("não lidas", html.lower())
        self.assertNotIn("unread", html.lower())

    def test_telegram_link_unlink_present(self) -> None:
        html = self._dashboard_html()
        self.assertIn("Desvincular Telegram", html)
        with self.Session() as db:
            user = db.get(User, self.user_id)
            user.chat_id = None
            db.commit()
        html = self._dashboard_html()
        self.assertIn("Abrir @", html)
        self.assertIn("Gerar novo código", html)

    def test_monitoring_toggle_present(self) -> None:
        html = self._dashboard_html()
        self.assertRegex(html, r'<input id="bot-toggle" type="checkbox"')

    def test_keyword_add_remove_present(self) -> None:
        html = self._dashboard_html()
        self.assertIn('id="keywords-form"', html)
        self.assertIn('aria-label="Remover excel"', html)

    def test_admin_webhook_conditioned(self) -> None:
        html = self._dashboard_html()
        self.assertNotIn("Admin webhook", html)
        with self.Session() as db:
            user = db.get(User, self.user_id)
            user.is_admin = True
            db.commit()
        admin_settings = SimpleNamespace(
            SHOW_WEBHOOK_PANEL=True,
            TELEGRAM_BOT_USERNAME="smartpaybot_test",
            PUBLIC_BASE_URL="https://smartpaybot.test",
        )
        webhook_info = {"result": {"url": "https://smartpaybot.test/webhook/telegram", "pending_update_count": 0}}
        with patch.object(dashboard_routes, "settings", admin_settings), patch.object(
            dashboard_routes, "get_webhook_info", return_value=webhook_info
        ):
            html = self._dashboard_html()
        self.assertIn("Admin webhook", html)
        self.assertIn("Configurar webhook", html)

    def test_csrf_preserved(self) -> None:
        html = self._dashboard_html()
        self.assertIn('name="csrf_token"', html)
        self.assertIn('meta name="csrf-token"', html)

    def test_empty_dashboard_renders(self) -> None:
        html = self._dashboard_html()
        self.assertIn("Painel de oportunidades", html)
        self.assertIn("Nenhuma oportunidade por enquanto", html)

    def test_user_without_telegram_renders(self) -> None:
        with self.Session() as db:
            user = db.get(User, self.user_id)
            user.chat_id = None
            db.commit()
        html = self._dashboard_html()
        self.assertIn("Telegram desconectado", html)
        self.assertIn("Vincule seu Telegram para ativar.", html)

    def test_user_without_keywords_renders(self) -> None:
        with self.Session() as db:
            db.query(UserKeyword).filter(UserKeyword.user_id == self.user_id).delete()
            db.commit()
        html = self._dashboard_html()
        self.assertIn("Nenhuma keyword cadastrada", html)
        self.assertIn("0", html)

    def test_user_without_projects_renders(self) -> None:
        html = self._dashboard_html()
        self.assertIn("Nenhuma oportunidade por enquanto", html)

    def test_free_limit_and_upgrade_are_preserved(self) -> None:
        with self.Session() as db:
            db.add(UserKeyword(user_id=self.user_id, keyword="wordpress", created_at=NOW - timedelta(days=10)))
            db.commit()
        html = self._dashboard_html()
        self.assertIn("3 / 3", html)
        self.assertIn("Remover limites", html)


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return NOW.replace(tzinfo=None)
        return NOW.astimezone(tz)


if __name__ == "__main__":
    unittest.main()
