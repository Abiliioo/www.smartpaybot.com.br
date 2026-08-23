from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
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


class CollectorPushSpb266Tests(unittest.TestCase):
    def setUp(self) -> None:
        FakeHttpClient.responses = []
        FakeHttpClient.calls = 0
        self.env = {
            "SMARTPAYBOT_INGEST_URL": "https://smartpaybot.com.br/internal/ingest/projects?secret=raw",
            "INTERNAL_INGEST_TOKEN": "super-secret-token",
        }

    def test_missing_state_keeps_real_collection_and_disables_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "collector_state.json"
            code, output, push = self._run_main(
                state_path,
                pages=2,
                parser_side_effect=[
                    [self._project(1, "Primeiro")],
                    [self._project(2, "Segundo")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(2, FakeHttpClient.calls)
        self.assertEqual([1, 2], [item["project_id"] for item in push.call_args.args[0]])
        self.assertIsNone(telemetry["shadow_hypothetical_stop_page"])
        self.assertEqual("state_missing", telemetry["shadow_reason"])
        self.assertFalse(telemetry["shadow_cycle_usable"])

    def test_corrupt_and_incompatible_state_are_conservative(self) -> None:
        for content, expected_reason in (
            ("{invalid-json", "state_corrupt"),
            ('{"schema_version": 999}', "state_incompatible"),
        ):
            with self.subTest(expected_reason=expected_reason), tempfile.TemporaryDirectory() as tmp:
                state_path = Path(tmp) / "collector_state.json"
                state_path.write_text(content, encoding="utf-8")
                code, output, push = self._run_main(
                    state_path,
                    pages=1,
                    parser_side_effect=[[self._project(1, "Projeto")]],
                )
                telemetry = self._telemetry(output)

            self.assertEqual(collector.EXIT_SUCCESS, code)
            self.assertEqual([1], [item["project_id"] for item in push.call_args.args[0]])
            self.assertIsNone(telemetry["shadow_hypothetical_stop_page"])
            self.assertEqual(expected_reason, telemetry["shadow_reason"])

    def test_all_known_first_page_calculates_stop_and_saved_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1", "2", "3"])
            code, output, _push = self._run_main(
                state_path,
                pages=3,
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

    def test_unknown_after_known_page_counts_as_missed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1", "2"])
            _code, output, _push = self._run_main(
                state_path,
                pages=3,
                parser_side_effect=[
                    [self._project(1, "Conhecido")],
                    [self._project(99, "Novo depois")],
                    [self._project(2, "Conhecido depois")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(1, telemetry["shadow_hypothetical_stop_page"])
        self.assertEqual(1, telemetry["shadow_missed_new_if_active"])

    def test_unknown_before_known_page_is_not_missed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1", "2"])
            _code, output, _push = self._run_main(
                state_path,
                pages=2,
                parser_side_effect=[
                    [self._project(99, "Novo antes")],
                    [self._project(1, "Conhecido")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(2, telemetry["shadow_hypothetical_stop_page"])
        self.assertEqual(0, telemetry["shadow_missed_new_if_active"])

    def test_reorder_with_unknown_after_stop_counts_as_missed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1", "2"])
            _code, output, _push = self._run_main(
                state_path,
                pages=3,
                parser_side_effect=[
                    [self._project(1, "Conhecido")],
                    [self._project(2, "Conhecido")],
                    [self._project(77, "Reordenado desconhecido")],
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(1, telemetry["shadow_hypothetical_stop_page"])
        self.assertEqual(1, telemetry["shadow_missed_new_if_active"])

    def test_project_without_id_blocks_known_page_and_counts_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1"])
            _code, output, _push = self._run_main(
                state_path,
                pages=1,
                parser_side_effect=[[{"title": "Sem id", "link": "https://example.test/no-id"}]],
            )
            telemetry = self._telemetry(output)

        self.assertIsNone(telemetry["shadow_hypothetical_stop_page"])
        self.assertEqual(1, telemetry["shadow_unknown_projects"])
        self.assertEqual("project_without_id", telemetry["shadow_reason"])
        self.assertFalse(telemetry["shadow_cycle_usable"])

    def test_partial_page_or_parser_failure_makes_shadow_not_usable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1"])
            _code, output, _push = self._run_main(
                state_path,
                pages=2,
                responses=[_http_error(500), _http_error(500), PROJECT_HTML],
                parser_side_effect=[[self._project(1, "Conhecido")]],
            )
            telemetry = self._telemetry(output)
        self.assertEqual("page_failure", telemetry["shadow_reason"])
        self.assertFalse(telemetry["shadow_cycle_usable"])

        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1"])
            _code, output, _push = self._run_main(
                state_path,
                pages=1,
                responses=[INVALID_HTML],
                parser_side_effect=[],
            )
            telemetry = self._telemetry(output)
        self.assertEqual("parser_failure", telemetry["shadow_reason"])
        self.assertFalse(telemetry["shadow_cycle_usable"])

    def test_ingest_failure_preserves_exit_code_and_shadow_not_usable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1"])
            code, output, _push = self._run_main(
                state_path,
                pages=1,
                parser_side_effect=[[self._project(1, "Conhecido")]],
                push_side_effect=ValueError("invalid json"),
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_INGEST_FAILED, code)
        self.assertEqual("real_exit_code_not_success", telemetry["shadow_reason"])
        self.assertFalse(telemetry["shadow_cycle_usable"])

    def test_shadow_telemetry_is_safe_and_payload_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["1"])
            code, output, push = self._run_main(
                state_path,
                pages=1,
                parser_side_effect=[
                    [
                        {
                            "project_id": 1,
                            "title": "Titulo nao deve aparecer",
                            "link": "https://example.test/link-nao-deve-aparecer",
                            "published_ms": None,
                        }
                    ]
                ],
            )
            telemetry = self._telemetry(output)

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(["shadow_cycle_usable", "shadow_enabled"], sorted([
            key for key in telemetry if key in {"shadow_enabled", "shadow_cycle_usable"}
        ]))
        self.assertEqual([1], [item["project_id"] for item in push.call_args.args[0]])
        self.assertNotIn("super-secret-token", output)
        self.assertNotIn("X-Internal-Ingest-Token", output)
        self.assertNotIn("secret=raw", output)
        self.assertNotIn("Titulo nao deve aparecer", output)
        self.assertNotIn("link-nao-deve-aparecer", output)

    def test_collect_result_preserves_flattened_order_and_pages_attempted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(tmp, ["10"])
            code, _output, push = self._run_main(
                state_path,
                pages=2,
                parser_side_effect=[
                    [self._project(10, "Conhecido"), self._project(11, "Novo")],
                    [self._project(12, "Novo 2")],
                ],
            )

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(2, FakeHttpClient.calls)
        self.assertEqual([10, 11, 12], [item["project_id"] for item in push.call_args.args[0]])
        self.assertEqual(collector.settings.SCAN_PAGES, collector.settings.SCAN_PAGES)

    def _run_main(
        self,
        state_path: Path,
        *,
        pages: int,
        parser_side_effect: list[list[dict]],
        responses: list[object] | None = None,
        push_side_effect: BaseException | None = None,
    ):
        FakeHttpClient.calls = 0
        FakeHttpClient.responses = list(responses or ([PROJECT_HTML] * pages))
        out = io.StringIO()
        push_result = {"received": 1, "inserted": 1, "updated": 0, "skipped": 0}
        push_patch = mock.patch.object(collector, "_push", return_value=push_result)
        if push_side_effect is not None:
            push_patch = mock.patch.object(collector, "_push", side_effect=push_side_effect)

        with mock.patch.dict(collector.os.environ, self.env, clear=False), \
             mock.patch.object(collector, "HttpClient", FakeHttpClient), \
             mock.patch.object(collector.asyncio, "sleep", side_effect=_no_sleep), \
             mock.patch.object(
                 collector,
                 "scrape_99freelas_list_items",
                 side_effect=parser_side_effect,
             ), \
             push_patch as push, \
             redirect_stdout(out):
            code = collector.main(
                ["--pages", str(pages), "--state-file", str(state_path)]
            )
        return code, out.getvalue(), push

    def _write_state(self, directory: str, recent_ids: list[str]) -> Path:
        state_path = Path(directory) / "collector_state.json"
        state_path.write_text(
            json.dumps(
                {
                    "schema_version": collector.STATE_SCHEMA_VERSION,
                    "last_success_at": "2026-01-01T00:00:00Z",
                    "watermark_published_ms": 1000,
                    "recent_project_ids": recent_ids,
                    "anchors": {"first_project_id": recent_ids[0], "last_project_id": recent_ids[-1]},
                }
            ),
            encoding="utf-8",
        )
        return state_path

    def _project(self, project_id: int, title: str) -> dict:
        return {
            "project_id": project_id,
            "title": title,
            "link": f"https://example.test/project/{project_id}",
            "published_ms": project_id,
        }

    def _telemetry(self, output: str) -> dict:
        for line in output.splitlines():
            if line.startswith("COLLECTOR_TELEMETRY "):
                return json.loads(line.removeprefix("COLLECTOR_TELEMETRY "))
        raise AssertionError("COLLECTOR_TELEMETRY nao encontrada")


if __name__ == "__main__":
    unittest.main()
