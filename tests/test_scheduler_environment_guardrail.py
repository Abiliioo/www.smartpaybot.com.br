from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

import workers.scheduler as scheduler


def _settings(app_env: str, scheduler_enabled: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        APP_ENV=app_env,
        SCAN_PAGES=10,
        SCAN_MIN_SECONDS=180,
        SCAN_MAX_SECONDS=360,
        TZ_NAME="America/Sao_Paulo",
        SCHEDULER_ENABLED=scheduler_enabled,
    )


class SchedulerStartGuardrailTest(unittest.TestCase):
    def tearDown(self) -> None:
        scheduler.stop()

    def test_homologation_start_returns_false_without_creating_scheduler(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("homologation")), \
             mock.patch.object(scheduler, "BackgroundScheduler") as mocked_bg:
            result = scheduler.start()

        self.assertFalse(result)
        mocked_bg.assert_not_called()
        self.assertIsNone(scheduler._scheduler)
        self.assertFalse(scheduler.is_running())

    def test_homologation_start_scheduler_with_scheduler_enabled_does_not_start(self) -> None:
        with mock.patch.object(
            scheduler, "get_settings", return_value=_settings("homologation", scheduler_enabled=True)
        ), mock.patch.object(scheduler, "BackgroundScheduler") as mocked_bg:
            result = scheduler.start_scheduler()

        self.assertFalse(result)
        mocked_bg.assert_not_called()

    def test_homologation_start_scheduler_with_scheduler_disabled_stays_inactive(self) -> None:
        with mock.patch.object(
            scheduler, "get_settings", return_value=_settings("homologation", scheduler_enabled=False)
        ), mock.patch.object(scheduler, "BackgroundScheduler") as mocked_bg:
            result = scheduler.start_scheduler()

        self.assertFalse(result)
        mocked_bg.assert_not_called()

    def test_production_start_keeps_current_behavior(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("production")), \
             mock.patch.object(scheduler, "BackgroundScheduler") as mocked_bg:
            mocked_instance = mocked_bg.return_value
            result = scheduler.start()

        self.assertTrue(result)
        mocked_bg.assert_called_once()
        mocked_instance.add_job.assert_called_once()
        mocked_instance.start.assert_called_once()

    def test_development_start_keeps_current_behavior(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("development")), \
             mock.patch.object(scheduler, "BackgroundScheduler") as mocked_bg:
            result = scheduler.start()

        self.assertTrue(result)
        mocked_bg.assert_called_once()


class SchedulerCrawlerGuardrailTest(unittest.TestCase):
    def test_homologation_pipeline_tick_never_calls_crawl_once(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("homologation")), \
             mock.patch.object(scheduler, "crawl_once") as mocked_crawl, \
             mock.patch.object(scheduler, "match_recent_projects") as mocked_match, \
             mock.patch.object(scheduler, "notify_pending") as mocked_notify:
            scheduler._pipeline_tick()

        mocked_crawl.assert_not_called()
        mocked_match.assert_called_once()
        mocked_notify.assert_called_once()

    def test_homologation_run_once_never_calls_crawl_once(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("homologation")), \
             mock.patch.object(scheduler, "crawl_once") as mocked_crawl, \
             mock.patch.object(scheduler, "match_recent_projects"), \
             mock.patch.object(scheduler, "notify_pending"):
            scheduler.run_once()

        mocked_crawl.assert_not_called()

    def test_production_pipeline_tick_still_calls_crawl_once(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("production")), \
             mock.patch.object(scheduler, "crawl_once") as mocked_crawl, \
             mock.patch.object(scheduler, "match_recent_projects"), \
             mock.patch.object(scheduler, "notify_pending"):
            scheduler._pipeline_tick()

        mocked_crawl.assert_called_once()

    def test_development_pipeline_tick_still_calls_crawl_once(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("development")), \
             mock.patch.object(scheduler, "crawl_once") as mocked_crawl, \
             mock.patch.object(scheduler, "match_recent_projects"), \
             mock.patch.object(scheduler, "notify_pending"):
            scheduler._pipeline_tick()

        mocked_crawl.assert_called_once()


class BotToggleSchedulerGuardrailTest(unittest.TestCase):
    """
    Representa o efeito de POST /dashboard/bot-toggle chamando sched_start()
    (workers.scheduler.start, importado em app/routes/dashboard.py). O ponto
    de bloqueio real e start() -- ja coberto diretamente aqui, evitando
    duplicar a fixture pesada de usuario/DB ja usada em
    tests/test_admin_user_list.py apenas para provar o mesmo guardrail.
    """

    def tearDown(self) -> None:
        scheduler.stop()

    def test_bot_toggle_enabled_in_homologation_does_not_start_crawler(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("homologation")), \
             mock.patch.object(scheduler, "BackgroundScheduler") as mocked_bg:
            ok = scheduler.start()  # exatamente o que dashboard.bot_toggle chama via sched_start()

        self.assertFalse(ok)
        mocked_bg.assert_not_called()
        self.assertFalse(scheduler.is_running())


class SchedulerProductionRegressionTest(unittest.TestCase):
    def tearDown(self) -> None:
        scheduler.stop()

    def test_production_scheduler_still_starts_and_schedules_job(self) -> None:
        with mock.patch.object(scheduler, "get_settings", return_value=_settings("production")), \
             mock.patch.object(scheduler, "BackgroundScheduler") as mocked_bg:
            mocked_instance = mocked_bg.return_value
            ok = scheduler.start()

        self.assertTrue(ok)
        mocked_instance.add_job.assert_called_once()


if __name__ == "__main__":
    unittest.main()
