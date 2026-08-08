from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import create_app
import app as app_module
import app.routes.admin as admin_routes
from domain.models import (
    Plan,
    ProjectGlobal,
    ProjectPerUser,
    Subscription,
    User,
    UserAlertDaily,
    UserKeyword,
)
from domain.repositories import list_admin_users_paginated
from infrastructure.db import Base


class AdminUserListTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)
        self._seed_base()

        self.app = create_app()
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
        self.session_patches = [
            patch.object(app_module, "SessionLocal", self.Session),
            patch.object(admin_routes, "SessionLocal", self.Session),
        ]
        for session_patch in self.session_patches:
            session_patch.start()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        for session_patch in reversed(self.session_patches):
            session_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _seed_base(self) -> None:
        with self.Session() as db:
            free = Plan(slug="free", name="Gratuito", max_keywords=3, max_alerts_day=10)
            pro = Plan(slug="pro", name="Pro", max_keywords=-1, max_alerts_day=-1)
            db.add_all([free, pro])
            db.commit()
            self.free_id = free.id
            self.pro_id = pro.id

        self.admin = self._user("admin", "admin@example.test", is_admin=True)
        self.free_user = self._user("anafree", "ana@example.test", bot_active=True)
        self.pro_user = self._user(
            "brunopro",
            "bruno@example.test",
            bot_active=False,
            chat_id="chat-pro",
            plan_slug="pro",
        )
        self.canceled_user = self._user(
            "canceled",
            "cancel@example.test",
            chat_id="chat-canceled",
            plan_slug="pro",
            subscription_status="canceled",
        )
        self.underscore_user = self._user("under_score", "under_score@example.test")
        self.keywordless = self._user("semkw", "semkw@example.test", chat_id="")

        self._keywords(self.free_user.id, ["excel", "python"])
        self._keywords(self.pro_user.id, ["api"])
        self._alerts_today(self.free_user.id, 2)
        self._projects(self.free_user.id, 3, start_project_id=1000)
        self._projects(self.pro_user.id, 1, start_project_id=2000)

    def _user(
        self,
        username: str,
        email: str,
        *,
        is_admin: bool = False,
        bot_active: bool = True,
        chat_id: str | None = None,
        plan_slug: str | None = None,
        subscription_status: str = "active",
    ) -> User:
        with self.Session() as db:
            user = User(
                username=username,
                email=email,
                password_hash=f"hash-{username}",
                is_admin=is_admin,
                is_subscriber=plan_slug == "pro" and subscription_status == "active",
                bot_active=bot_active,
                chat_id=chat_id,
                phone=f"555-{username}",
                telegram_link_code=f"code-{username}",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            if plan_slug:
                plan_id = self.pro_id if plan_slug == "pro" else self.free_id
                db.add(
                    Subscription(
                        user_id=user.id,
                        plan_id=plan_id,
                        status=subscription_status,
                    )
                )
                db.commit()
            return user

    def _keywords(self, user_id: int, keywords: list[str]) -> None:
        with self.Session() as db:
            db.add_all(UserKeyword(user_id=user_id, keyword=kw) for kw in keywords)
            db.commit()

    def _alerts_today(self, user_id: int, count: int) -> None:
        with self.Session() as db:
            db.add(UserAlertDaily(user_id=user_id, date=date.today(), alerts_sent=count))
            db.commit()

    def _projects(self, user_id: int, count: int, *, start_project_id: int) -> None:
        with self.Session() as db:
            for offset in range(count):
                project = ProjectGlobal(
                    project_id=start_project_id + offset,
                    title=f"Project {start_project_id + offset}",
                    link=f"https://example.test/{start_project_id + offset}",
                )
                db.add(project)
                db.flush()
                db.add(
                    ProjectPerUser(
                        user_id=user_id,
                        global_project_id=project.id,
                        link=project.link,
                        title=project.title,
                        matched_keyword="excel",
                    )
                )
            db.commit()

    def _login(self, user: User) -> None:
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def _get_admin(self, query_string: dict | None = None):
        return self.client.get("/admin/", query_string=query_string or {})

    def _html(self, response) -> str:
        return response.get_data(as_text=True)

    def test_admin_can_access_listing(self) -> None:
        self._login(self.admin)

        response = self._get_admin()

        self.assertEqual(response.status_code, 200)
        html = self._html(response)
        self.assertIn("Painel Admin", html)
        self.assertIn("anafree", html)

    def test_common_user_cannot_access_listing(self) -> None:
        self._login(self.free_user)

        response = self._get_admin()

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_cannot_access_listing(self) -> None:
        response = self._get_admin()

        self.assertIn(response.status_code, (302, 401))
        self.assertNotIn("anafree", self._html(response))

    def test_search_by_username(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "anafree"})

        html = self._html(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("anafree", html)
        self.assertNotIn("brunopro", html)

    def test_search_by_email(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "bruno@example.test"})

        html = self._html(response)
        self.assertIn("brunopro", html)
        self.assertNotIn("anafree", html)

    def test_search_is_case_insensitive(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "BRUNO@EXAMPLE.TEST"})

        self.assertIn("brunopro", self._html(response))

    def test_search_without_results_shows_empty_state(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "nobody"})

        html = self._html(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nenhum usuario encontrado", html)
        self.assertIn("Limpar filtros", html)

    def test_plan_free_filter_includes_implicit_free_and_inactive_subscription(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"plan": "free"})

        html = self._html(response)
        self.assertIn("anafree", html)
        self.assertIn("canceled", html)
        self.assertNotIn("brunopro", html)

    def test_plan_pro_filter(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"plan": "pro"})

        html = self._html(response)
        self.assertIn("brunopro", html)
        self.assertNotIn("anafree", html)
        self.assertNotIn("canceled", html)

    def test_plan_free_filter_excludes_admin_without_pro(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        response = self._get_admin({"plan": "free"})

        html = self._html(response)
        self.assertIn("anafree", html)
        self.assertNotIn("adminzero", html)
        self.assertNotIn("adminpro", html)

    def test_plan_pro_filter_excludes_admin_with_pro(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        response = self._get_admin({"plan": "pro"})

        html = self._html(response)
        self.assertIn("brunopro", html)
        self.assertNotIn("adminpro", html)
        self.assertNotIn("adminzero", html)

    def test_plan_admin_filter_returns_only_admins(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        response = self._get_admin({"plan": "admin"})

        html = self._html(response)
        self.assertIn("adminzero", html)
        self.assertNotIn("anafree", html)
        self.assertNotIn("brunopro", html)

    def test_plan_admin_with_pro_stays_admin_only(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        admin_response = self._get_admin({"plan": "admin"})
        pro_response = self._get_admin({"plan": "pro"})

        self.assertIn("adminpro", self._html(admin_response))
        self.assertNotIn("adminpro", self._html(pro_response))

    def test_plan_all_includes_free_pro_and_admin(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        response = self._get_admin({"plan": "all"})

        html = self._html(response)
        self.assertIn("anafree", html)
        self.assertIn("brunopro", html)
        self.assertIn("adminzero", html)
        self.assertIn("adminpro", html)

    def test_plan_admin_combined_with_monitoring_active(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        response = self._get_admin({"plan": "admin", "monitoring": "active"})

        html = self._html(response)
        self.assertIn("adminzero", html)
        self.assertNotIn("adminpro", html)

    def test_plan_admin_combined_with_telegram_linked(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        response = self._get_admin({"plan": "admin", "telegram": "linked"})

        html = self._html(response)
        self.assertIn("adminpro", html)
        self.assertNotIn("adminzero", html)

    def test_plan_admin_pagination_matches_row_filter(self) -> None:
        self._seed_admin_pair()
        self._seed_many_admins(25)
        self._login(self.admin)

        response = self._get_admin({"plan": "admin", "page": "1"})

        html = self._html(response)
        self.assertIn("Pagina 1 de 2", html)
        self.assertIn("admbulk00", html)
        self.assertNotIn("admbulk24", html)

    def test_plan_invalid_value_behaves_as_all(self) -> None:
        self._seed_admin_pair()
        self._login(self.admin)

        response = self._get_admin({"plan": "qualquer_coisa"})

        html = self._html(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn('option value="all" selected>Todos</option>', html)
        self.assertIn("anafree", html)
        self.assertIn("brunopro", html)
        self.assertIn("adminzero", html)

    def test_plan_admin_filter_is_preserved_in_pagination_links(self) -> None:
        self._seed_admin_pair()
        self._seed_many_admins(25)
        self._login(self.admin)

        response = self._get_admin({"plan": "admin", "page": "1"})

        html = self._html(response)
        self.assertIn("plan=admin", html)
        self.assertNotIn("next=", html)
        self.assertNotIn("return_url", html)

    def test_monitoring_active_filter(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"monitoring": "active"})

        html = self._html(response)
        self.assertIn("anafree", html)
        self.assertNotIn("brunopro", html)

    def test_monitoring_inactive_filter(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"monitoring": "inactive"})

        html = self._html(response)
        self.assertIn("brunopro", html)
        self.assertNotIn("anafree", html)

    def test_telegram_linked_filter(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"telegram": "linked"})

        html = self._html(response)
        self.assertIn("brunopro", html)
        self.assertIn("canceled", html)
        self.assertNotIn("anafree", html)

    def test_telegram_unlinked_filter(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"telegram": "unlinked"})

        html = self._html(response)
        self.assertIn("anafree", html)
        self.assertNotIn("brunopro", html)

    def test_combined_filters_use_intersection(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"plan": "pro", "monitoring": "inactive", "telegram": "linked"})

        html = self._html(response)
        self.assertIn("brunopro", html)
        self.assertNotIn("anafree", html)
        self.assertNotIn("canceled", html)

    def test_first_page_pagination(self) -> None:
        self._seed_many_users(25)
        self._login(self.admin)

        response = self._get_admin({"page": "1"})

        html = self._html(response)
        self.assertIn("Pagina 1 de 2", html)
        self.assertIn("bulk00", html)
        self.assertNotIn("bulk24", html)

    def test_second_page_pagination(self) -> None:
        self._seed_many_users(25)
        self._login(self.admin)

        response = self._get_admin({"page": "2"})

        html = self._html(response)
        self.assertIn("Pagina 2 de 2", html)
        self.assertIn("bulk24", html)

    def test_invalid_page_falls_back_to_one(self) -> None:
        self._seed_many_users(25)
        self._login(self.admin)

        response = self._get_admin({"page": "bad"})

        self.assertIn("Pagina 1 de 2", self._html(response))

    def test_page_beyond_total_is_clamped_without_500(self) -> None:
        self._seed_many_users(25)
        self._login(self.admin)

        response = self._get_admin({"page": "99"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Pagina 2 de 2", self._html(response))

    def test_query_params_are_preserved_in_pagination_links(self) -> None:
        self._seed_many_users(25)
        self._login(self.admin)

        response = self._get_admin(
            {"q": "bulk", "plan": "free", "monitoring": "active", "telegram": "unlinked"}
        )

        html = self._html(response)
        self.assertIn("q=bulk", html)
        self.assertIn("plan=free", html)
        self.assertIn("monitoring=active", html)
        self.assertIn("telegram=unlinked", html)

    def test_aggregate_counters_are_correct(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "anafree"})

        html = self._html(response)
        self.assertRegex(html, r'data-testid="keywords-count"[^>]*>\s*2\s*<')
        self.assertRegex(html, r'data-testid="alerts-today"[^>]*>\s*2\s*<')
        self.assertRegex(html, r'data-testid="total-projects"[^>]*>\s*3\s*<')

    def test_invalid_filters_fall_back_without_500(self) -> None:
        self._login(self.admin)

        response = self._get_admin(
            {"plan": "enterprise", "monitoring": "paused", "telegram": "maybe", "page": "nope"}
        )

        html = self._html(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Pagina 1 de 1", html)
        self.assertIn('option value="all" selected>Todos</option>', html)

    def test_sensitive_fields_are_not_rendered(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "anafree"})

        html = self._html(response)
        self.assertNotIn("hash-anafree", html)
        self.assertNotIn("chat-pro", html)
        self.assertNotIn("555-anafree", html)
        self.assertNotIn("code-anafree", html)

    def test_repository_items_expose_only_explicit_user_fields(self) -> None:
        with self.Session() as db:
            page = list_admin_users_paginated(db, q="anafree")

        self.assertEqual(page.total, 1)
        item = page.items[0]
        self.assertEqual(item.user_id, self.free_user.id)
        self.assertEqual(item.username, "anafree")
        self.assertEqual(item.email, "ana@example.test")
        self.assertFalse(hasattr(item, "user"))
        self.assertFalse(hasattr(item, "password_hash"))
        self.assertFalse(hasattr(item, "phone"))
        self.assertFalse(hasattr(item, "chat_id"))
        self.assertFalse(hasattr(item, "telegram_link_code"))

    def test_percent_search_is_literal_not_wildcard_all(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "%"})

        html = self._html(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Nenhum usuario encontrado", html)
        self.assertNotIn("anafree", html)

    def test_underscore_search_is_literal_not_wildcard_all(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "_"})

        html = self._html(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("under_score", html)
        self.assertNotIn("anafree", html)

    def test_username_with_underscore_can_be_found_literally(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "under_"})

        html = self._html(response)
        self.assertIn("under_score", html)
        self.assertNotIn("anafree", html)

    def test_backslash_search_does_not_error(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "\\"})

        self.assertEqual(response.status_code, 200)

    def test_plan_actions_are_still_available(self) -> None:
        self._login(self.admin)

        response = self._get_admin({"q": "anafree"})

        html = self._html(response)
        self.assertIn("/admin/users/", html)
        self.assertIn("/activate-pro", html)
        self.assertIn('name="csrf_token"', html)

    def test_post_plan_action_still_requires_csrf(self) -> None:
        self._login(self.admin)

        response = self.client.post(f"/admin/users/{self.free_user.id}/activate-pro")

        self.assertEqual(response.status_code, 400)

    def test_repository_query_count_does_not_grow_by_user(self) -> None:
        self._seed_many_users(30)
        counts: list[int] = []

        def before_cursor_execute(*_args):
            counts.append(1)

        event.listen(self.engine, "before_cursor_execute", before_cursor_execute)
        try:
            with self.Session() as db:
                page = list_admin_users_paginated(db, page=1)
        finally:
            event.remove(self.engine, "before_cursor_execute", before_cursor_execute)

        self.assertEqual(len(page.items), 20)
        self.assertLessEqual(len(counts), 4)

    def _seed_admin_pair(self) -> tuple[User, User]:
        admin_no_pro = self._user(
            "adminzero",
            "adminzero@example.test",
            is_admin=True,
            bot_active=True,
            chat_id=None,
        )
        admin_with_pro = self._user(
            "adminpro",
            "adminpro@example.test",
            is_admin=True,
            bot_active=False,
            chat_id="chat-adminpro",
            plan_slug="pro",
        )
        return admin_no_pro, admin_with_pro

    def _seed_many_admins(self, count: int, prefix: str = "admbulk") -> None:
        for index in range(count):
            self._user(f"{prefix}{index:02d}", f"{prefix}{index:02d}@example.test", is_admin=True)

    def _seed_many_users(self, count: int) -> None:
        existing = self._count_users()
        for index in range(count):
            self._user(f"bulk{index:02d}", f"bulk{index:02d}@example.test")
        self.assertEqual(self._count_users(), existing + count)

    def _count_users(self) -> int:
        with self.Session() as db:
            return db.query(User).count()


if __name__ == "__main__":
    unittest.main()
