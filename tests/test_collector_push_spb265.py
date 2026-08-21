from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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


class CollectorPushSpb265Tests(unittest.TestCase):
    def setUp(self) -> None:
        FakeHttpClient.responses = []
        FakeHttpClient.calls = 0
        self.env = {
            "SMARTPAYBOT_INGEST_URL": "https://smartpaybot.com.br/internal/ingest/projects?secret=raw",
            "INTERNAL_INGEST_TOKEN": "super-secret-token",
        }

    def test_missing_corrupt_and_incompatible_state_load_as_safe_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "collector_state.json"

            self.assertEqual("missing", collector._load_collector_state(state_path).status)

            state_path.write_text("{invalid-json", encoding="utf-8")
            self.assertEqual("corrupt", collector._load_collector_state(state_path).status)

            state_path.write_text('{"schema_version": 999}', encoding="utf-8")
            result = collector._load_collector_state(state_path)

        self.assertEqual("incompatible", result.status)
        self.assertEqual(999, result.schema_version)

    def test_atomic_write_creates_valid_json_and_limits_recent_ids(self) -> None:
        projects = [
            {"project_id": index, "published_ms": index}
            for index in range(collector.STATE_RECENT_IDS_LIMIT + 5)
        ]
        metrics = collector.CollectorMetrics(
            pages_attempted=10,
            pages_ok=10,
            projects_collected=len(projects),
            projects_unique=len(projects),
            ingest_received=len(projects),
            ingest_inserted=1,
            ingest_updated=2,
            ingest_skipped=3,
        )

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "collector_state.json"
            now = collector._utc_now()
            state = collector._build_next_state(
                {},
                projects,
                metrics,
                collector.EXIT_SUCCESS,
                now,
                now,
            )
            status = collector._write_collector_state_atomic(state_path, state)
            written = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual("written", status)
        self.assertEqual(collector.STATE_SCHEMA_VERSION, written["schema_version"])
        self.assertEqual(collector.STATE_RECENT_IDS_LIMIT, len(written["recent_project_ids"]))
        self.assertEqual("5", written["recent_project_ids"][0])
        self.assertEqual(collector.STATE_RECENT_IDS_LIMIT + 4, written["watermark_published_ms"])

    def test_success_updates_state_telemetry_without_changing_pages_or_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "collector_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": collector.STATE_SCHEMA_VERSION,
                        "last_success_at": "2026-01-01T00:00:00Z",
                        "watermark_published_ms": 1,
                        "recent_project_ids": ["old"],
                        "anchors": {"first_project_id": "old", "last_project_id": "old"},
                    }
                ),
                encoding="utf-8",
            )
            projects_by_page = [
                [{"project_id": 1, "title": "Primeiro", "link": "https://example.test/a", "published_ms": 10}],
                [{"project_id": 2, "title": "Segundo", "link": "https://example.test/b", "published_ms": 30}],
                [{"project_id": 3, "title": "Terceiro", "link": "https://example.test/c", "published_ms": 20}],
            ]

            code, output, push = self._run_main(
                state_path,
                pages=3,
                parser_side_effect=projects_by_page,
            )
            written = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(3, FakeHttpClient.calls)
        push.assert_called_once()
        self.assertEqual([1, 2, 3], [item["project_id"] for item in push.call_args.args[0]])
        self.assertEqual(30, written["watermark_published_ms"])
        self.assertNotEqual("2026-01-01T00:00:00Z", written["last_success_at"])
        self.assertIn("COLLECTOR_TELEMETRY", output)
        self.assertIn('"state_status": "loaded"', output)
        self.assertIn('"state_write_status": "written"', output)

    def test_failed_ingest_preserves_previous_success_fields_and_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "collector_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": collector.STATE_SCHEMA_VERSION,
                        "last_success_at": "2026-01-01T00:00:00Z",
                        "watermark_published_ms": 123,
                        "recent_project_ids": ["123"],
                        "anchors": {"first_project_id": "123", "last_project_id": "123"},
                    }
                ),
                encoding="utf-8",
            )
            code, output, _push = self._run_main(
                state_path,
                pages=1,
                parser_side_effect=[
                    [{"project_id": 999, "title": "Falha", "link": "https://example.test/f", "published_ms": 999}]
                ],
                push_side_effect=ValueError("invalid json"),
            )
            written = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(collector.EXIT_INGEST_FAILED, code)
        self.assertEqual("2026-01-01T00:00:00Z", written["last_success_at"])
        self.assertEqual(123, written["watermark_published_ms"])
        self.assertEqual(collector.EXIT_INGEST_FAILED, written["last_exit_code"])
        self.assertIn('"exit_code": 3', output)

    def test_telemetry_does_not_include_token_header_payload_title_or_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "collector_state.json"
            code, output, _push = self._run_main(
                state_path,
                pages=1,
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
        self.assertNotIn("super-secret-token", output)
        self.assertNotIn("X-Internal-Ingest-Token", output)
        self.assertNotIn("secret=raw", output)
        self.assertNotIn("Titulo nao deve aparecer", output)
        self.assertNotIn("link-nao-deve-aparecer", output)

    def _run_main(
        self,
        state_path: Path,
        *,
        pages: int,
        parser_side_effect: list[list[dict]],
        push_side_effect: BaseException | None = None,
    ):
        FakeHttpClient.responses = [PROJECT_HTML] * pages
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


if __name__ == "__main__":
    unittest.main()
