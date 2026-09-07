from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
from unittest import mock

import aiohttp

import scripts.local_collector_push as collector


PROJECT_HTML = """
<html><body>
  <ul class="result-list">
    <li class="result-item" data-id="123">
      <h1 class="title"><a href="/project/exemplo-123">Projeto exemplo</a></h1>
    </li>
  </ul>
</body></html>
"""

INVALID_HTML = "<html><body><div>challenge sem listagem</div></body></html>"


class FakeHttpClient:
    responses: list[object] = []
    calls: int = 0

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "FakeHttpClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get_text(self, url: str) -> str:
        type(self).calls += 1
        if not type(self).responses:
            raise AssertionError("FakeHttpClient sem respostas configuradas")
        item = type(self).responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return str(item)


async def _no_sleep(_seconds: float) -> None:
    return None


def _http_error(status: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=None,
        history=(),
        status=status,
        message=f"HTTP {status}",
        headers=None,
    )


class CollectorPushSpb268Tests(unittest.TestCase):
    def setUp(self) -> None:
        FakeHttpClient.responses = []
        FakeHttpClient.calls = 0
        self.env = {
            "SMARTPAYBOT_INGEST_URL": "https://smartpaybot.com.br/internal/ingest/projects?secret=raw",
            "INTERNAL_INGEST_TOKEN": "super-secret-token",
        }
        self.started_at = collector._utc_now().replace(microsecond=0)
        self.finished_at = self.started_at + timedelta(seconds=8)

    def test_pages_n_compatibility_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, output, push, _state_path = self._run_main(
                ["--pages", "3", "--state-file", str(Path(tmp) / "state.json")],
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                    [self._project(3, "Terceiro")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(3, FakeHttpClient.calls)
        self.assertEqual([1, 2, 3], [item["project_id"] for item in push.call_args.args[0]])
        self.assertEqual("pages", telemetry["collector_mode_requested"])
        self.assertEqual("pages", telemetry["collector_mode_resolved"])

    def test_mode_deep_collects_deep_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, output, _push, _state_path = self._run_main(
                [
                    "--mode", "deep",
                    "--deep-pages", "4",
                    "--state-file", str(Path(tmp) / "state.json"),
                ],
                parser_side_effect=[[self._project(i, f"Projeto {i}")] for i in range(1, 5)],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(4, FakeHttpClient.calls)
        self.assertEqual("deep", telemetry["collector_mode_resolved"])
        self.assertEqual(4, telemetry["pages_attempted"])

    def test_mode_fast_collects_fast_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, last_deep_age_seconds=60)
            code, output, _push, _state_path = self._run_main(
                ["--mode", "fast", "--fast-pages", "2", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(2, FakeHttpClient.calls)
        self.assertEqual("fast", telemetry["collector_mode_resolved"])
        self.assertEqual(2, telemetry["pages_attempted"])

    def test_auto_first_cycle_missing_state_resolves_deep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, output, _push, _state_path = self._run_main(
                ["--mode", "auto", "--deep-pages", "2", "--state-file", str(Path(tmp) / "missing.json")],
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual("deep", telemetry["collector_mode_resolved"])

    def test_auto_corrupt_state_resolves_deep(self) -> None:
        self._assert_auto_state_content_resolves_deep("{invalid-json")

    def test_auto_incompatible_state_resolves_deep(self) -> None:
        self._assert_auto_state_content_resolves_deep('{"schema_version": 999}')

    def test_auto_previous_exit_failure_resolves_deep(self) -> None:
        state = self._state_dict(last_exit_code=collector.EXIT_INGEST_FAILED)
        self.assertEqual("deep", self._resolve_auto_for_state(state))

    def test_auto_previous_page_failure_resolves_deep(self) -> None:
        state = self._state_dict(last_pages_failed=1)
        self.assertEqual("deep", self._resolve_auto_for_state(state))

    def test_auto_previous_parser_failure_resolves_deep(self) -> None:
        state = self._state_dict(last_parser_failed=1)
        self.assertEqual("deep", self._resolve_auto_for_state(state))

    def test_auto_age_below_threshold_resolves_fast(self) -> None:
        state = self._state_dict(last_deep_started_at=self._timestamp(self.started_at - timedelta(seconds=539)))
        self.assertEqual("fast", self._resolve_auto_for_state(state))

    def test_auto_age_at_threshold_resolves_deep(self) -> None:
        state = self._state_dict(last_deep_started_at=self._timestamp(self.started_at - timedelta(seconds=540)))
        self.assertEqual("deep", self._resolve_auto_for_state(state))

    def test_auto_decision_uses_deep_start_not_finish(self) -> None:
        state_path = None
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, last_deep_age_seconds=539)
            code, output, _push, _state_path = self._run_main(
                ["--mode", "auto", "--fast-pages", "2", "--deep-pages", "10", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                ],
                finished_at=self.started_at + timedelta(seconds=30),
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual("fast", telemetry["collector_mode_resolved"])

    def test_deep_partial_does_not_advance_last_deep_started_at(self) -> None:
        old_deep = self._timestamp(self.started_at - timedelta(seconds=1000))
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, last_deep_started_at=old_deep)
            code, output, _push, _state_path = self._run_main(
                ["--mode", "deep", "--deep-pages", "2", "--state-file", str(state_path)],
                responses=[PROJECT_HTML, INVALID_HTML],
                parser_side_effect=[[self._project(1, "Primeiro")]],
            )
            telemetry = self._telemetry(output)
            written = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertFalse(telemetry["collector_deep_complete"])
        self.assertEqual(old_deep, written["last_deep_started_at"])

    def test_deep_complete_advances_last_deep_started_at_to_cycle_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, last_deep_age_seconds=1000)
            code, output, _push, _state_path = self._run_main(
                ["--mode", "deep", "--deep-pages", "2", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                ],
            )
            telemetry = self._telemetry(output)
            written = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertTrue(telemetry["collector_deep_complete"])
        self.assertEqual(self._timestamp(self.started_at), written["last_deep_started_at"])

    def test_fast_does_not_advance_last_deep_started_at(self) -> None:
        old_deep = self._timestamp(self.started_at - timedelta(seconds=60))
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, last_deep_started_at=old_deep)
            code, _output, _push, _state_path = self._run_main(
                ["--mode", "fast", "--fast-pages", "2", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(99, "Primeiro")],
                    [self._project(100, "Segundo")],
                ],
            )
            written = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(old_deep, written["last_deep_started_at"])

    def test_fast_does_not_overwrite_shadow_snapshot(self) -> None:
        old_deep = self._timestamp(self.started_at - timedelta(seconds=60))
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(
                tmp,
                recent_ids=["deep1", "deep2"],
                anchors={"first_project_id": "deep1", "last_project_id": "deep2"},
                last_deep_started_at=old_deep,
            )
            code, _output, _push, _state_path = self._run_main(
                ["--mode", "fast", "--fast-pages", "2", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(99, "Novo fast")],
                    [self._project(100, "Novo fast 2")],
                ],
            )
            written = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(["deep1", "deep2"], written["recent_project_ids"])
        self.assertEqual({"first_project_id": "deep1", "last_project_id": "deep2"}, written["anchors"])

    def test_fast_shadow_is_unusable_with_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, last_deep_age_seconds=60)
            code, output, _push, _state_path = self._run_main(
                ["--mode", "fast", "--fast-pages", "2", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertFalse(telemetry["shadow_cycle_usable"])
        self.assertEqual("fast_cycle_not_full_scan", telemetry["shadow_reason"])
        self.assertIsNone(telemetry["shadow_missed_new_if_active"])

    def test_deep_complete_preserves_spb266_shadow_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, recent_ids=["1", "2", "3"], last_deep_age_seconds=1000)
            code, output, _push, _state_path = self._run_main(
                ["--mode", "deep", "--deep-pages", "3", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(1, "Conhecido 1")],
                    [self._project(2, "Conhecido 2")],
                    [self._project(3, "Conhecido 3")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(1, telemetry["shadow_hypothetical_stop_page"])
        self.assertEqual(2, telemetry["shadow_pages_saved_hypothetical"])
        self.assertEqual(0, telemetry["shadow_missed_new_if_active"])
        self.assertTrue(telemetry["shadow_cycle_usable"])

    def test_telemetry_remains_safe_without_pii_or_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_deep_state(tmp, last_deep_age_seconds=60)
            code, output, _push, _state_path = self._run_main(
                ["--mode", "fast", "--fast-pages", "1", "--state-file", str(state_path)],
                parser_side_effect=[
                    [
                        {
                            "project_id": 1,
                            "title": "Titulo nao deve aparecer",
                            "link": "https://example.test/link-nao-deve-aparecer",
                            "published_ms": 10,
                        }
                    ]
                ],
            )

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertIn("COLLECTOR_TELEMETRY", output)
        self.assertNotIn("super-secret-token", output)
        self.assertNotIn("X-Internal-Ingest-Token", output)
        self.assertNotIn("secret=raw", output)
        self.assertNotIn("Titulo nao deve aparecer", output)
        self.assertNotIn("link-nao-deve-aparecer", output)

    def test_pages_and_mode_together_fail_closed(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = collector.main(["--pages", "10", "--mode", "auto"])

        self.assertEqual(collector.EXIT_CONFIG, code)
        self.assertIn("não deve ser combinado", out.getvalue())

    def _run_main(
        self,
        args: list[str],
        *,
        parser_side_effect: list[list[dict]],
        responses: list[object] | None = None,
        push_side_effect: BaseException | None = None,
        finished_at=None,
    ):
        pages_expected = self._expected_pages(args)
        FakeHttpClient.calls = 0
        FakeHttpClient.responses = list(responses or ([PROJECT_HTML] * pages_expected))
        out = io.StringIO()
        push_result = {"received": 1, "inserted": 1, "updated": 0, "skipped": 0}
        push_patch = mock.patch.object(collector, "_push", return_value=push_result)
        if push_side_effect is not None:
            push_patch = mock.patch.object(collector, "_push", side_effect=push_side_effect)
        finish = finished_at or self.finished_at

        with mock.patch.dict(collector.os.environ, self.env, clear=False), \
             mock.patch.object(collector, "HttpClient", FakeHttpClient), \
             mock.patch.object(collector.asyncio, "sleep", side_effect=_no_sleep), \
             mock.patch.object(collector, "_utc_now", side_effect=[self.started_at, finish]), \
             mock.patch.object(
                 collector,
                 "scrape_99freelas_list_items",
                 side_effect=parser_side_effect,
             ), \
             push_patch as push, \
             redirect_stdout(out):
            code = collector.main(args)
        state_path = self._state_path_from_args(args)
        return code, out.getvalue(), push, state_path

    def _assert_auto_state_content_resolves_deep(self, content: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(content, encoding="utf-8")
            code, output, _push, _state_path = self._run_main(
                ["--mode", "auto", "--deep-pages", "2", "--state-file", str(state_path)],
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual("deep", telemetry["collector_mode_resolved"])

    def _resolve_auto_for_state(self, state: dict) -> str:
        return collector._resolve_auto_mode(
            collector.StateLoadResult(status="loaded", data=state, schema_version=collector.STATE_SCHEMA_VERSION),
            self.started_at,
        )

    def _state_dict(self, **overrides) -> dict:
        state = {
            "schema_version": collector.STATE_SCHEMA_VERSION,
            "last_exit_code": collector.EXIT_SUCCESS,
            "last_pages_failed": 0,
            "last_parser_failed": 0,
            "last_deep_started_at": self._timestamp(self.started_at - timedelta(seconds=60)),
            "last_success_at": self._timestamp(self.started_at - timedelta(seconds=60)),
            "watermark_published_ms": 1000,
            "recent_project_ids": ["1", "2"],
            "anchors": {"first_project_id": "1", "last_project_id": "2"},
        }
        state.update(overrides)
        return state

    def _write_deep_state(
        self,
        directory: str,
        *,
        recent_ids: list[str] | None = None,
        anchors: dict | None = None,
        last_deep_age_seconds: int | None = 60,
        last_deep_started_at: str | None = None,
    ) -> Path:
        ids = recent_ids or ["1", "2"]
        if last_deep_started_at is None:
            assert last_deep_age_seconds is not None
            last_deep_started_at = self._timestamp(
                self.started_at - timedelta(seconds=last_deep_age_seconds)
            )
        state = self._state_dict(
            recent_project_ids=ids,
            anchors=anchors or {"first_project_id": ids[0], "last_project_id": ids[-1]},
            last_deep_started_at=last_deep_started_at,
        )
        state_path = Path(directory) / "collector_state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return state_path

    def _project(self, project_id: int, title: str) -> dict:
        return {
            "project_id": project_id,
            "title": title,
            "link": f"https://example.test/project/{project_id}",
            "published_ms": project_id,
        }

    def _timestamp(self, value) -> str:
        return value.isoformat(timespec="seconds").replace("+00:00", "Z")

    def _telemetry(self, output: str) -> dict:
        for line in output.splitlines():
            if line.startswith("COLLECTOR_TELEMETRY "):
                return json.loads(line.removeprefix("COLLECTOR_TELEMETRY "))
        raise AssertionError("COLLECTOR_TELEMETRY nao encontrada")

    def _state_path_from_args(self, args: list[str]) -> Path | None:
        if "--state-file" not in args:
            return None
        return Path(args[args.index("--state-file") + 1])

    def _expected_pages(self, args: list[str]) -> int:
        if "--mode" not in args:
            if "--pages" in args:
                return int(args[args.index("--pages") + 1])
            return collector.settings.SCAN_PAGES
        mode = args[args.index("--mode") + 1]
        fast_pages = int(args[args.index("--fast-pages") + 1]) if "--fast-pages" in args else collector.DEFAULT_FAST_PAGES
        deep_pages = int(args[args.index("--deep-pages") + 1]) if "--deep-pages" in args else collector.DEFAULT_DEEP_PAGES
        if mode == "fast":
            return fast_pages
        if mode == "deep":
            return deep_pages
        state_path = self._state_path_from_args(args)
        if state_path is None or not state_path.exists():
            return deep_pages
        state_load = collector._load_collector_state(state_path)
        resolved = collector._resolve_auto_mode(state_load, self.started_at)
        return fast_pages if resolved == "fast" else deep_pages


if __name__ == "__main__":
    unittest.main()
