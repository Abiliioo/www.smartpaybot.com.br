from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
import app as app_module
import app.routes.dashboard as dashboard_routes
from domain.models import Plan, ProjectGlobal, ProjectPerUser, User, UserKeyword
from domain.services.dashboard_metrics_service import build_dashboard_metrics
from infrastructure.db import Base


NOW = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)


class DashboardMetricsSPB251DTest(unittest.TestCase):
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
            self.plan = Plan(slug="free", name="Gratuito", max_keywords=3, max_alerts_day=10)
            db.add(self.plan)
            self.user = User(
                username="metrics",
                email="metrics@example.test",
                password_hash="hash",
                bot_active=True,
                chat_id="chat-1",
            )
            db.add(self.user)
            db.commit()
            db.refresh(self.user)
            self.user_id = int(self.user.id)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _keyword(self, keyword: str, created_at: datetime) -> None:
        with self.Session() as db:
            db.add(UserKeyword(user_id=self.user_id, keyword=keyword, created_at=created_at))
            db.commit()

    def _project(
        self,
        *,
        project_id: int,
        keyword: str = "excel",
        created_at: datetime,
        published_at: datetime | None = None,
        notified_at: datetime | None = None,
        won: bool = False,
        won_cents: int = 0,
        won_at: datetime | None = None,
    ) -> int:
        with self.Session() as db:
            global_project = ProjectGlobal(
                project_id=project_id,
                title=f"Projeto {project_id}",
                link=f"https://example.test/{project_id}",
                published_at=published_at,
            )
            db.add(global_project)
            db.commit()
            db.refresh(global_project)
            ppu = ProjectPerUser(
                user_id=self.user_id,
                global_project_id=global_project.id,
                title=global_project.title,
                link=global_project.link,
                matched_keyword=keyword,
                created_at=created_at,
                notified_at=notified_at,
                won=won,
                won_cents=won_cents,
                won_at=won_at,
            )
            db.add(ppu)
            db.commit()
            db.refresh(ppu)
            return int(ppu.id)

    def _metrics(self) -> dict:
        with self.Session() as db:
            user = db.get(User, self.user_id)
            return build_dashboard_metrics(
                db,
                user=user,
                plan={"slug": "free", "name": "Gratuito"},
                now=NOW,
            )

    def test_timezone_0030_utc_belongs_to_previous_br_day(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 8, 0, 30, tzinfo=timezone.utc))
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["opportunities_today"], 0)
        self.assertEqual(metrics["kpis"]["opportunities_yesterday"], 1)

    def test_timezone_sao_paulo_midnight_boundary(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 8, 2, 59, tzinfo=timezone.utc))
        self._project(project_id=2, created_at=datetime(2026, 9, 8, 3, 0, tzinfo=timezone.utc))
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["opportunities_today"], 1)
        self.assertEqual(metrics["kpis"]["opportunities_yesterday"], 1)

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 8, 3, 30))
        self.assertEqual(self._metrics()["kpis"]["opportunities_today"], 1)

    def test_series_contains_zero_days(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        series = self._metrics()["series"]["7d"]
        self.assertEqual(len(series), 7)
        self.assertIn({"date": "2026-09-07", "count": 0}, series)
        self.assertEqual(series[-1], {"date": "2026-09-08", "count": 1})

    def test_opportunities_today_correct(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(self._metrics()["kpis"]["opportunities_today"], 1)

    def test_yesterday_separated_correctly(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc))
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["opportunities_today"], 0)
        self.assertEqual(metrics["kpis"]["opportunities_yesterday"], 1)

    def test_current_7d_count(self) -> None:
        for i in range(3):
            self._project(project_id=i + 1, created_at=datetime(2026, 9, 8 - i, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(self._metrics()["kpis"]["opportunities_7d"], 3)

    def test_previous_7d_count(self) -> None:
        for i in range(2):
            self._project(project_id=i + 1, created_at=datetime(2026, 8, 31 - i, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(self._metrics()["kpis"]["opportunities_prev_7d"], 2)

    def test_pct_normal(self) -> None:
        for project_id in (1, 2, 3):
            self._project(project_id=project_id, created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        for project_id in (10, 11):
            self._project(project_id=project_id, created_at=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(self._metrics()["kpis"]["opportunities_7d_pct"], 50)

    def test_previous_zero_returns_pct_none(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self.assertIsNone(self._metrics()["kpis"]["opportunities_7d_pct"])

    def test_zero_zero_returns_pct_none(self) -> None:
        self.assertIsNone(self._metrics()["kpis"]["opportunities_7d_pct"])

    def test_latency_valid_sample(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 10, 12, tzinfo=timezone.utc),
        )
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["alert_latency_median_seconds"], 720)
        self.assertEqual(metrics["kpis"]["alert_latency_median_minutes"], 12.0)

    def test_latency_ignores_null_published_at(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 12, 5, tzinfo=timezone.utc),
        )
        metrics = self._metrics()
        self.assertIsNone(metrics["kpis"]["alert_latency_median_minutes"])
        self.assertEqual(metrics["kpis"]["alert_latency_sample_count"], 0)

    def test_latency_ignores_null_notified_at(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 8, 11, 0, tzinfo=timezone.utc),
        )
        self.assertIsNone(self._metrics()["kpis"]["alert_latency_median_minutes"])

    def test_latency_ignores_negative_delta(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
        )
        metrics = self._metrics()
        self.assertIsNone(metrics["kpis"]["alert_latency_median_minutes"])
        self.assertEqual(metrics["kpis"]["alert_latency_sample_count"], 0)

    def test_latency_odd_median(self) -> None:
        for idx, minutes in enumerate((5, 15, 20), start=1):
            self._project(
                project_id=idx,
                created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
                published_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
                notified_at=datetime(2026, 9, 8, 10, minutes, tzinfo=timezone.utc),
            )
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["alert_latency_median_seconds"], 900)
        self.assertEqual(metrics["kpis"]["alert_latency_median_minutes"], 15.0)

    def test_latency_even_median(self) -> None:
        for idx, minutes in enumerate((10, 20), start=1):
            self._project(
                project_id=idx,
                created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
                published_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
                notified_at=datetime(2026, 9, 8, 10, minutes, tzinfo=timezone.utc),
            )
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["alert_latency_median_seconds"], 900)
        self.assertEqual(metrics["kpis"]["alert_latency_median_minutes"], 15.0)

    def test_latency_without_samples_returns_none(self) -> None:
        metrics = self._metrics()
        self.assertIsNone(metrics["kpis"]["alert_latency_median_minutes"])
        self.assertEqual(metrics["kpis"]["alert_latency_sample_count"], 0)

    def test_latency_coverage(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 10, 10, tzinfo=timezone.utc),
        )
        self._project(
            project_id=2,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 12, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(self._metrics()["kpis"]["alert_latency_coverage_pct"], 50)

    def test_latency_sub_minute_preserves_seconds(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 10, 0, 30, tzinfo=timezone.utc),
        )
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["alert_latency_median_seconds"], 30)
        self.assertEqual(metrics["kpis"]["alert_latency_median_minutes"], 0.5)

    def test_latency_even_seconds_median(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 10, 0, 30, tzinfo=timezone.utc),
        )
        self._project(
            project_id=2,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            published_at=datetime(2026, 9, 8, 10, 0, 0, tzinfo=timezone.utc),
            notified_at=datetime(2026, 9, 8, 10, 1, 30, tzinfo=timezone.utc),
        )
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["alert_latency_median_seconds"], 60)
        self.assertEqual(metrics["kpis"]["alert_latency_median_minutes"], 1.0)

    def test_active_keyword_productive(self) -> None:
        self._keyword("excel", datetime(2026, 8, 1, tzinfo=timezone.utc))
        self._project(project_id=1, keyword="excel", created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["productive_keywords"], 1)
        self.assertEqual(metrics["kpis"]["keywords_total"], 1)

    def test_active_keyword_without_match(self) -> None:
        self._keyword("excel", datetime(2026, 8, 1, tzinfo=timezone.utc))
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["productive_keywords"], 0)
        self.assertEqual(metrics["kpis"]["keywords_total"], 1)

    def test_removed_keyword_not_in_main_kpi(self) -> None:
        self._keyword("excel", datetime(2026, 8, 1, tzinfo=timezone.utc))
        self._project(project_id=1, keyword="python", created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(self._metrics()["kpis"]["productive_keywords"], 0)

    def test_removed_keyword_can_appear_in_ranking_inactive(self) -> None:
        self._project(project_id=1, keyword="python", created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(
            self._metrics()["keywords"]["ranking_30d"][0],
            {"keyword": "python", "matches": 1, "active": False},
        )

    def test_new_keyword_not_mature_zero_result(self) -> None:
        self._keyword("excel", datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(self._metrics()["keywords"]["zero_result_mature_count"], 0)

    def test_mature_keyword_without_match_enters_zero_result(self) -> None:
        self._keyword("excel", datetime(2026, 8, 1, tzinfo=timezone.utc))
        metrics = self._metrics()
        self.assertEqual(metrics["keywords"]["zero_result_mature_count"], 1)
        self.assertEqual(metrics["keywords"]["zero_result_mature"], ["excel"])

    def test_ranking_order(self) -> None:
        self._project(project_id=1, keyword="python", created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self._project(project_id=2, keyword="excel", created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self._project(project_id=3, keyword="excel", created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self.assertEqual([item["keyword"] for item in self._metrics()["keywords"]["ranking_30d"][:2]], ["excel", "python"])

    def test_won_true_counted(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            won=True,
            won_at=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(self._metrics()["results"]["won_total"], 1)

    def test_won_false_not_counted(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            won=False,
            won_cents=10000,
            won_at=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(self._metrics()["results"]["won_total"], 0)

    def test_won_cents_summed(self) -> None:
        for idx, cents in enumerate((10000, 25000), start=1):
            self._project(
                project_id=idx,
                created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
                won=True,
                won_cents=cents,
                won_at=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc),
            )
        self.assertEqual(self._metrics()["results"]["won_value_total_cents"], 35000)

    def test_won_30d_uses_won_at(self) -> None:
        self._project(
            project_id=1,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            won=True,
            won_cents=10000,
            won_at=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc),
        )
        self._project(
            project_id=2,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            won=True,
            won_cents=10000,
            won_at=datetime(2026, 7, 1, 13, 0, tzinfo=timezone.utc),
        )
        self._project(
            project_id=3,
            created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
            won=True,
            won_cents=10000,
            won_at=datetime(2026, 9, 9, 13, 0, tzinfo=timezone.utc),
        )
        metrics = self._metrics()
        self.assertEqual(metrics["results"]["won_total"], 3)
        self.assertEqual(metrics["results"]["won_30d"], 1)
        self.assertEqual(metrics["results"]["won_value_30d_cents"], 10000)

    def test_recent_projects_limited_to_three(self) -> None:
        for idx in range(5):
            self._project(project_id=idx + 1, created_at=datetime(2026, 9, 8, 12, idx, tzinfo=timezone.utc))
        self.assertEqual(len(self._metrics()["recent_projects"]), 3)

    def test_recent_projects_most_recent_first(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
        self._project(project_id=2, created_at=datetime(2026, 9, 8, 13, 0, tzinfo=timezone.utc))
        self.assertEqual(self._metrics()["recent_projects"][0]["title"], "Projeto 2")

    def test_recent_projects_returns_historical_projects_outside_30d(self) -> None:
        self._project(project_id=1, created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc))
        self._project(project_id=2, created_at=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc))
        self._project(project_id=3, created_at=datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc))
        titles = [item["title"] for item in self._metrics()["recent_projects"]]
        self.assertEqual(titles, ["Projeto 3", "Projeto 2", "Projeto 1"])

    def test_recent_projects_query_selects_three_most_recent_historical(self) -> None:
        for idx, day in enumerate((1, 2, 3, 4, 5), start=1):
            self._project(project_id=idx, created_at=datetime(2026, 7, day, 12, 0, tzinfo=timezone.utc))
        titles = [item["title"] for item in self._metrics()["recent_projects"]]
        self.assertEqual(len(titles), 3)
        self.assertEqual(titles, ["Projeto 5", "Projeto 4", "Projeto 3"])

    def test_status_monitoring_telegram_preserved(self) -> None:
        metrics = self._metrics()
        self.assertTrue(metrics["status"]["monitoring_active"])
        self.assertTrue(metrics["status"]["telegram_connected"])

    def test_plan_preserved(self) -> None:
        metrics = self._metrics()
        self.assertEqual(metrics["status"]["plan_name"], "Gratuito")
        self.assertEqual(metrics["status"]["plan_slug"], "free")

    def test_dashboard_continues_rendering_with_empty_database(self) -> None:
        app = create_app()
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with patch.object(app_module, "SessionLocal", self.Session), patch.object(dashboard_routes, "SessionLocal", self.Session):
            with app.test_client() as client:
                with client.session_transaction() as session:
                    session["_user_id"] = str(self.user_id)
                    session["_fresh"] = True
                response = client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_user_without_telegram(self) -> None:
        with self.Session() as db:
            user = db.get(User, self.user_id)
            user.chat_id = None
            db.add(user)
            db.commit()
        self.assertFalse(self._metrics()["status"]["telegram_connected"])

    def test_user_without_keywords(self) -> None:
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["keywords_total"], 0)
        self.assertEqual(metrics["keywords"]["total_active"], 0)

    def test_user_without_projects(self) -> None:
        metrics = self._metrics()
        self.assertEqual(metrics["kpis"]["opportunities_7d"], 0)
        self.assertEqual(metrics["recent_projects"], [])


if __name__ == "__main__":
    unittest.main()
