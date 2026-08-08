from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from infrastructure.db import Base
from domain.models import ProjectGlobal, ProjectPerUser, User
import workers.notifier as notifier


class NotifierQueueTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, username: str, *, chat_id: str | None, bot_active: bool = True) -> User:
        with self.Session() as db:
            user = User(
                username=username,
                email=f"{username}@example.test",
                password_hash="hash",
                is_admin=True,
                bot_active=bot_active,
                chat_id=chat_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user

    def _project(self, project_id: int) -> ProjectGlobal:
        with self.Session() as db:
            project = ProjectGlobal(
                project_id=project_id,
                title=f"Projeto {project_id}",
                link=f"https://example.test/projects/{project_id}",
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            return project

    def _alert(
        self,
        user: User,
        project: ProjectGlobal,
        *,
        notified: bool = False,
        attempts: int = 0,
    ) -> int:
        with self.Session() as db:
            ppu = ProjectPerUser(
                user_id=user.id,
                global_project_id=project.id,
                link=project.link,
                title=project.title,
                matched_keyword="excel",
                notify_attempts=attempts,
                notified_at=datetime.now(timezone.utc) if notified else None,
            )
            db.add(ppu)
            db.commit()
            db.refresh(ppu)
            return ppu.id

    def _bulk_alerts(self, user: User, count: int, *, start_project_id: int) -> list[int]:
        ids = []
        for offset in range(count):
            ids.append(self._alert(user, self._project(start_project_id + offset)))
        return ids

    def _pending_count(self, user: User) -> int:
        with self.Session() as db:
            return int(
                db.scalar(
                    select(func.count())
                    .select_from(ProjectPerUser)
                    .where(
                        ProjectPerUser.user_id == user.id,
                        ProjectPerUser.notified_at.is_(None),
                    )
                )
                or 0
            )

    def _attempt_sum(self, user: User) -> int:
        with self.Session() as db:
            return int(
                db.scalar(
                    select(func.coalesce(func.sum(ProjectPerUser.notify_attempts), 0))
                    .where(ProjectPerUser.user_id == user.id)
                )
                or 0
            )

    def _notified_count(self, user: User) -> int:
        with self.Session() as db:
            return int(
                db.scalar(
                    select(func.count())
                    .select_from(ProjectPerUser)
                    .where(
                        ProjectPerUser.user_id == user.id,
                        ProjectPerUser.notified_at.is_not(None),
                    )
                )
                or 0
            )

    def _run_notify(self, send_result=True, *, max_batch=100, max_per_user=20, telegram_ready=True):
        with patch.object(notifier, "SessionLocal", self.Session), patch.object(
            notifier, "send_message", return_value=send_result
        ) as send, patch.object(notifier, "telegram_ready", return_value=telegram_ready) as ready:
            sent = notifier.notify_pending(max_batch=max_batch, max_per_user=max_per_user)
            return sent, send, ready

    def _run_notify_filtered(
        self,
        send_result=True,
        *,
        max_batch=100,
        max_per_user=20,
        only_user_id=None,
        only_project_ids=None,
        telegram_ready=True,
    ):
        with patch.object(notifier, "SessionLocal", self.Session), patch.object(
            notifier, "send_message", return_value=send_result
        ) as send, patch.object(notifier, "telegram_ready", return_value=telegram_ready) as ready:
            sent = notifier.notify_pending(
                max_batch=max_batch,
                max_per_user=max_per_user,
                only_user_id=only_user_id,
                only_project_ids=only_project_ids,
            )
            return sent, send, ready

    def test_user_without_chat_id_does_not_consume_limit(self) -> None:
        invalid = self._user("invalid", chat_id=None)
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(invalid, 150, start_project_id=1000)
        self._bulk_alerts(valid, 5, start_project_id=2000)

        sent, send, _ = self._run_notify(max_batch=5, max_per_user=5)

        self.assertEqual(sent, 5)
        self.assertEqual(send.call_count, 5)
        self.assertEqual(self._notified_count(valid), 5)
        self.assertEqual(self._attempt_sum(invalid), 0)
        self.assertEqual(self._pending_count(invalid), 150)

    def test_inactive_user_does_not_consume_limit(self) -> None:
        inactive = self._user("inactive", chat_id="chat-inactive", bot_active=False)
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(inactive, 150, start_project_id=3000)
        self._bulk_alerts(valid, 5, start_project_id=4000)

        sent, send, _ = self._run_notify(max_batch=5, max_per_user=5)

        self.assertEqual(sent, 5)
        self.assertEqual(send.call_count, 5)
        self.assertEqual(self._notified_count(valid), 5)
        self.assertEqual(self._attempt_sum(inactive), 0)
        self.assertEqual(self._pending_count(inactive), 150)

    def test_empty_chat_id_does_not_consume_limit(self) -> None:
        invalid = self._user("emptychat", chat_id="")
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(invalid, 150, start_project_id=4100)
        self._bulk_alerts(valid, 5, start_project_id=5000)

        sent, send, _ = self._run_notify(max_batch=5, max_per_user=5)

        self.assertEqual(sent, 5)
        self.assertEqual(send.call_count, 5)
        self.assertEqual(self._notified_count(valid), 5)
        self.assertEqual(self._attempt_sum(invalid), 0)

    def test_valid_user_with_five_pending_alerts_is_processed(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(valid, 5, start_project_id=4300)

        sent, send, _ = self._run_notify(max_batch=100)

        self.assertEqual(sent, 5)
        self.assertEqual(send.call_count, 5)
        self.assertEqual(self._notified_count(valid), 5)

    def test_alerts_at_max_attempts_do_not_consume_limit(self) -> None:
        exhausted = self._user("exhausted", chat_id="chat-exhausted")
        valid = self._user("valid", chat_id="chat-valid")
        for project_id in range(4400, 4550):
            self._alert(exhausted, self._project(project_id), attempts=notifier.MAX_ATTEMPTS)
        self._bulk_alerts(valid, 5, start_project_id=4600)

        sent, send, _ = self._run_notify(max_batch=5, max_per_user=5)

        self.assertEqual(sent, 5)
        self.assertEqual(send.call_count, 5)
        self.assertEqual(self._notified_count(valid), 5)
        self.assertEqual(self._attempt_sum(exhausted), 150 * notifier.MAX_ATTEMPTS)

    def test_notified_alert_is_not_resent(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        first = self._project(5000)
        second = self._project(5001)
        self._alert(valid, first, notified=True)
        self._alert(valid, second)

        sent, send, _ = self._run_notify(max_batch=10)

        self.assertEqual(sent, 1)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self._notified_count(valid), 2)

    def test_telegram_failure_increments_attempts(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(valid, 1, start_project_id=6000)

        sent, send, _ = self._run_notify(send_result=False, max_batch=10)

        self.assertEqual(sent, 0)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self._attempt_sum(valid), 1)
        self.assertEqual(self._pending_count(valid), 1)

    def test_telegram_not_ready_blocks_send_without_consuming_attempts(self) -> None:
        """
        Guardrail bloqueado (disabled/identidade invalida/rede indisponivel)
        e uma classe de falha DIFERENTE de falha real de entrega: nao pode
        consumir notify_attempts, nao pode marcar notified_at, nao pode
        chamar send_message.
        """
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(valid, 3, start_project_id=6100)

        sent, send, ready = self._run_notify(max_batch=10, telegram_ready=False)

        self.assertEqual(sent, 0)
        send.assert_not_called()
        ready.assert_called_once()
        self.assertEqual(self._attempt_sum(valid), 0)
        self.assertEqual(self._notified_count(valid), 0)
        self.assertEqual(self._pending_count(valid), 3)

    def test_no_eligible_alerts_does_not_check_telegram_readiness(self) -> None:
        """Sem nenhum alerta elegivel, o preflight de readiness nem deveria rodar."""
        sent, send, ready = self._run_notify(max_batch=10, telegram_ready=True)

        self.assertEqual(sent, 0)
        ready.assert_not_called()
        send.assert_not_called()

    def test_telegram_ready_true_preserves_current_success_behavior(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(valid, 2, start_project_id=6200)

        sent, send, ready = self._run_notify(max_batch=10, telegram_ready=True)

        ready.assert_called_once()
        self.assertEqual(sent, 2)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(self._notified_count(valid), 2)

    def test_success_sets_notified_at(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(valid, 1, start_project_id=7000)

        sent, _send, _ = self._run_notify(max_batch=10)

        self.assertEqual(sent, 1)
        self.assertEqual(self._notified_count(valid), 1)
        self.assertEqual(self._pending_count(valid), 0)

    def test_two_valid_users_are_processed_fairly(self) -> None:
        many = self._user("many", chat_id="chat-many")
        few = self._user("few", chat_id="chat-few")
        self._bulk_alerts(many, 100, start_project_id=8000)
        self._bulk_alerts(few, 5, start_project_id=9000)

        sent, send, _ = self._run_notify(max_batch=20, max_per_user=10)

        self.assertEqual(sent, 15)
        self.assertEqual(send.call_count, 15)
        self.assertEqual(self._notified_count(many), 10)
        self.assertEqual(self._notified_count(few), 5)
        self.assertEqual(self._pending_count(few), 0)

    def test_no_duplicate_send_on_second_run(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(valid, 2, start_project_id=10000)

        first_sent, first_send, _ = self._run_notify(max_batch=10)
        second_sent, second_send, _ = self._run_notify(max_batch=10)

        self.assertEqual(first_sent, 2)
        self.assertEqual(first_send.call_count, 2)
        self.assertEqual(second_sent, 0)
        self.assertEqual(second_send.call_count, 0)
        self.assertEqual(self._notified_count(valid), 2)

    def test_only_user_id_processes_only_requested_user(self) -> None:
        first = self._user("first", chat_id="chat-first")
        second = self._user("second", chat_id="chat-second")
        self._bulk_alerts(first, 3, start_project_id=11000)
        self._bulk_alerts(second, 4, start_project_id=12000)

        sent, send, _ = self._run_notify_filtered(only_user_id=second.id)

        self.assertEqual(sent, 4)
        self.assertEqual(send.call_count, 4)
        self.assertEqual(self._notified_count(first), 0)
        self.assertEqual(self._notified_count(second), 4)

    def test_only_user_id_does_not_send_other_eligible_user(self) -> None:
        requested = self._user("requested", chat_id="chat-requested")
        other = self._user("other", chat_id="chat-other")
        self._bulk_alerts(requested, 1, start_project_id=13000)
        self._bulk_alerts(other, 5, start_project_id=14000)

        sent, send, _ = self._run_notify_filtered(max_batch=10, only_user_id=requested.id)

        self.assertEqual(sent, 1)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self._notified_count(requested), 1)
        self.assertEqual(self._notified_count(other), 0)

    def test_only_project_ids_processes_only_requested_ids(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        ids = self._bulk_alerts(valid, 4, start_project_id=15000)

        sent, send, _ = self._run_notify_filtered(only_project_ids=[ids[1], ids[3]])

        self.assertEqual(sent, 2)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(self._notified_count(valid), 2)
        with self.Session() as db:
            notified_ids = {
                row[0]
                for row in db.execute(
                    select(ProjectPerUser.id).where(ProjectPerUser.notified_at.is_not(None))
                )
            }
        self.assertEqual(notified_ids, {ids[1], ids[3]})

    def test_empty_only_project_ids_sends_nothing(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        self._bulk_alerts(valid, 3, start_project_id=16000)

        sent, send, _ = self._run_notify_filtered(only_project_ids=[])

        self.assertEqual(sent, 0)
        self.assertEqual(send.call_count, 0)
        self.assertEqual(self._notified_count(valid), 0)

    def test_only_user_id_with_other_users_project_id_sends_nothing(self) -> None:
        requested = self._user("requested", chat_id="chat-requested")
        other = self._user("other", chat_id="chat-other")
        self._bulk_alerts(requested, 1, start_project_id=17000)
        other_ids = self._bulk_alerts(other, 1, start_project_id=18000)

        sent, send, _ = self._run_notify_filtered(
            only_user_id=requested.id,
            only_project_ids=[other_ids[0]],
        )

        self.assertEqual(sent, 0)
        self.assertEqual(send.call_count, 0)
        self.assertEqual(self._notified_count(requested), 0)
        self.assertEqual(self._notified_count(other), 0)

    def test_specific_recent_id_is_not_replaced_by_old_alert(self) -> None:
        valid = self._user("valid", chat_id="chat-valid")
        old_id = self._bulk_alerts(valid, 1, start_project_id=19000)[0]
        recent_ids = self._bulk_alerts(valid, 5, start_project_id=20000)
        target_id = recent_ids[2]

        sent, send, _ = self._run_notify_filtered(
            max_batch=1,
            max_per_user=1,
            only_user_id=valid.id,
            only_project_ids=[target_id],
        )

        self.assertEqual(sent, 1)
        self.assertEqual(send.call_count, 1)
        with self.Session() as db:
            old = db.get(ProjectPerUser, old_id)
            target = db.get(ProjectPerUser, target_id)
            self.assertIsNone(old.notified_at)
            self.assertIsNotNone(target.notified_at)

    def test_unfiltered_run_keeps_fair_strategy(self) -> None:
        many = self._user("many", chat_id="chat-many")
        few = self._user("few", chat_id="chat-few")
        self._bulk_alerts(many, 50, start_project_id=21000)
        self._bulk_alerts(few, 5, start_project_id=22000)

        sent, send, _ = self._run_notify_filtered(max_batch=20, max_per_user=10)

        self.assertEqual(sent, 15)
        self.assertEqual(send.call_count, 15)
        self.assertEqual(self._notified_count(many), 10)
        self.assertEqual(self._notified_count(few), 5)

    def test_admin_filters_still_respect_eligibility(self) -> None:
        inactive = self._user("inactive", chat_id="chat-inactive", bot_active=False)
        no_chat = self._user("nochat", chat_id=None)
        exhausted = self._user("exhausted", chat_id="chat-exhausted")
        valid = self._user("valid", chat_id="chat-valid")
        inactive_id = self._bulk_alerts(inactive, 1, start_project_id=23000)[0]
        no_chat_id = self._bulk_alerts(no_chat, 1, start_project_id=24000)[0]
        exhausted_id = self._alert(
            exhausted,
            self._project(25000),
            attempts=notifier.MAX_ATTEMPTS,
        )
        valid_id = self._bulk_alerts(valid, 1, start_project_id=26000)[0]

        sent, send, _ = self._run_notify_filtered(
            only_project_ids=[inactive_id, no_chat_id, exhausted_id, valid_id],
        )

        self.assertEqual(sent, 1)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self._notified_count(valid), 1)
        self.assertEqual(self._notified_count(inactive), 0)
        self.assertEqual(self._notified_count(no_chat), 0)
        self.assertEqual(self._notified_count(exhausted), 0)


if __name__ == "__main__":
    unittest.main()
