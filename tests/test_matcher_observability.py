from __future__ import annotations

import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import workers.matcher as matcher
import domain.services.projects_service as projects_service


class _SessionFactory:
    def __call__(self):
        return self

    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _Project:
    def __init__(self, title: str):
        self.title = title


def _result(
    *,
    created: int,
    match_pairs: int,
    blocked_by_daily_limit: int = 0,
    duplicates_or_existing: int = 0,
):
    return SimpleNamespace(
        created=created,
        match_pairs=match_pairs,
        blocked_by_daily_limit=blocked_by_daily_limit,
        duplicates_or_existing=duplicates_or_existing,
    )


class MatcherObservabilityTest(unittest.TestCase):
    def _run_cycle(self, *, users_keywords, projects, results):
        with patch.object(matcher, "SessionLocal", _SessionFactory()), patch.object(
            matcher, "get_keywords_by_user", return_value=users_keywords
        ), patch.object(
            matcher, "iter_new_global_projects_since", return_value=projects
        ), patch.object(
            matcher,
            "fanout_project_to_users",
            side_effect=[r.created for r in results],
            create=True,
        ) as legacy_fanout, patch.object(
            matcher, "fanout_project_to_users_result", side_effect=results, create=True
        ) as stats_fanout, self.assertLogs("workers.matcher", level="INFO") as logs:
            created = matcher.match_recent_projects()

        return created, " ".join(logs.output), legacy_fanout, stats_fanout

    def test_cycle_without_users_or_keywords_logs_zero_summary(self) -> None:
        created, log_text, _legacy, stats_fanout = self._run_cycle(
            users_keywords={},
            projects=[],
            results=[],
        )

        self.assertEqual(created, 0)
        self.assertIn("rule=lexical_boundaries_v1", log_text)
        self.assertIn("users_with_keywords=0", log_text)
        self.assertIn("keywords_total=0", log_text)
        self.assertIn("projects_scanned=0", log_text)
        self.assertIn("projects_with_matches=0", log_text)
        self.assertIn("match_pairs_total=0", log_text)
        self.assertIn("projections_created=0", log_text)
        stats_fanout.assert_not_called()

    def test_cycle_with_projects_and_no_matches_logs_aggregate_counts(self) -> None:
        created, log_text, _legacy, _stats = self._run_cycle(
            users_keywords={1: ["excel"]},
            projects=[_Project("Projeto A"), _Project("Projeto B")],
            results=[_result(created=0, match_pairs=0), _result(created=0, match_pairs=0)],
        )

        self.assertEqual(created, 0)
        self.assertIn("users_with_keywords=1", log_text)
        self.assertIn("keywords_total=1", log_text)
        self.assertIn("projects_scanned=2", log_text)
        self.assertIn("projects_with_matches=0", log_text)
        self.assertIn("match_pairs_total=0", log_text)
        self.assertIn("projections_created=0", log_text)

    def test_cycle_with_one_match_preserves_return_value(self) -> None:
        created, log_text, _legacy, _stats = self._run_cycle(
            users_keywords={1: ["excel"]},
            projects=[_Project("Planilha em Excel")],
            results=[_result(created=1, match_pairs=1)],
        )

        self.assertEqual(created, 1)
        self.assertIn("projects_scanned=1", log_text)
        self.assertIn("projects_with_matches=1", log_text)
        self.assertIn("match_pairs_total=1", log_text)
        self.assertIn("projections_created=1", log_text)

    def test_cycle_counts_multiple_pairs_and_existing_projections(self) -> None:
        created, log_text, _legacy, _stats = self._run_cycle(
            users_keywords={1: ["excel", "vba"], 2: ["api"]},
            projects=[_Project("Excel VBA"), _Project("API REST")],
            results=[
                _result(created=1, match_pairs=2, duplicates_or_existing=1),
                _result(created=0, match_pairs=1, blocked_by_daily_limit=1),
            ],
        )

        self.assertEqual(created, 1)
        self.assertIn("users_with_keywords=2", log_text)
        self.assertIn("keywords_total=3", log_text)
        self.assertIn("projects_with_matches=2", log_text)
        self.assertIn("match_pairs_total=3", log_text)
        self.assertIn("projections_created=1", log_text)
        self.assertIn("blocked_by_daily_limit=1", log_text)
        self.assertIn("duplicates_or_existing=1", log_text)

    def test_matcher_does_not_call_legacy_fanout_when_collecting_stats(self) -> None:
        _created, _log_text, legacy_fanout, stats_fanout = self._run_cycle(
            users_keywords={1: ["excel"]},
            projects=[_Project("Excel"), _Project("Outro")],
            results=[_result(created=1, match_pairs=1), _result(created=0, match_pairs=0)],
        )

        self.assertEqual(stats_fanout.call_count, 2)
        legacy_fanout.assert_not_called()

    def test_duration_is_present_and_non_negative(self) -> None:
        _created, log_text, _legacy, _stats = self._run_cycle(
            users_keywords={1: ["excel"]},
            projects=[],
            results=[],
        )

        match = re.search(r"duration_ms=(\d+)", log_text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 0)

    def test_summary_does_not_log_project_titles_keywords_or_user_data(self) -> None:
        _created, log_text, _legacy, _stats = self._run_cycle(
            users_keywords={7: ["secretkeyword"]},
            projects=[_Project("Sensitive Project Title")],
            results=[_result(created=1, match_pairs=1)],
        )

        self.assertIn("rule=lexical_boundaries_v1", log_text)
        self.assertNotIn("Sensitive Project Title", log_text)
        self.assertNotIn("secretkeyword", log_text)
        self.assertNotIn("user_id=7", log_text)


class FanoutProjectResultTest(unittest.TestCase):
    def test_result_counts_created_blocked_and_existing_without_extra_logs(self) -> None:
        project = SimpleNamespace(title="Planilha Excel", project_id=123)

        with self.assertNoLogs(
            "domain.services.projects_service", level="INFO"
        ), patch.object(
            projects_service,
            "match_users_for_title",
            return_value=[(1, "excel"), (2, "excel"), (3, "excel")],
        ), patch.object(
            projects_service,
            "can_receive_alert_today",
            side_effect=[True, False, True],
        ), patch.object(
            projects_service,
            "create_user_project_if_absent",
            side_effect=[object(), None],
        ) as create_projection:
            result = projects_service.fanout_project_to_users_result(
                object(),
                global_project=project,
                users_keywords={1: ["excel"], 2: ["excel"], 3: ["excel"]},
            )

        self.assertEqual(result.match_pairs, 3)
        self.assertEqual(result.created, 1)
        self.assertEqual(result.blocked_by_daily_limit, 1)
        self.assertEqual(result.duplicates_or_existing, 1)
        self.assertEqual(create_projection.call_count, 2)


if __name__ == "__main__":
    unittest.main()
