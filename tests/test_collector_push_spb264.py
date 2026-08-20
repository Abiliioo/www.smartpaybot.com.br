from __future__ import annotations

import asyncio
import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

import aiohttp
import requests

import scripts.local_collector_push as collector


PROJECT_HTML = """
<html><body>
  <ul class="result-list">
    <li class="result-item" data-id="123">
      <h1 class="title"><a href="/project/exemplo-123">Projeto exemplo</a></h1>
      <p class="item-text information">Dev | Pleno Publicado: há 1 minuto</p>
    </li>
  </ul>
</body></html>
"""

ZERO_PROJECTS_HTML = '<html><body><ul class="result-list"></ul></body></html>'
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


def _timeout() -> asyncio.TimeoutError:
    return asyncio.TimeoutError("read timeout")


def _connection_error() -> aiohttp.ClientConnectionError:
    return aiohttp.ClientConnectionError("dns failure")


class CollectorPushSpb264Tests(unittest.TestCase):
    def setUp(self) -> None:
        FakeHttpClient.responses = []
        FakeHttpClient.calls = 0
        self.env = {
            "SMARTPAYBOT_INGEST_URL": "https://smartpaybot.com.br/internal/ingest/projects?secret=raw",
            "INTERNAL_INGEST_TOKEN": "super-secret-token",
        }

    def _run_main(self, responses: list[object], push_result: dict | None = None) -> tuple[int, str]:
        FakeHttpClient.responses = list(responses)
        if push_result is None:
            push_result = {"received": 1, "inserted": 1, "updated": 0, "skipped": 0}
        out = io.StringIO()
        with mock.patch.dict(collector.os.environ, self.env, clear=False), \
             mock.patch.object(collector, "HttpClient", FakeHttpClient), \
             mock.patch.object(collector.asyncio, "sleep", side_effect=_no_sleep), \
             mock.patch.object(collector, "_push", return_value=push_result), \
             redirect_stdout(out):
            code = collector.main(["--pages", "1"])
        return code, out.getvalue()

    def test_http_500_non_2xx_does_not_reach_parser_as_success(self) -> None:
        with mock.patch.object(collector, "scrape_99freelas_list_items") as parser:
            code, _ = self._run_main([_http_error(500), _http_error(500)])

        self.assertEqual(collector.EXIT_COLLECT_FAILED, code)
        self.assertEqual(2, FakeHttpClient.calls)
        parser.assert_not_called()

    def test_timeout_connection_error_retries_limited(self) -> None:
        code, output = self._run_main([_timeout(), PROJECT_HTML])

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertEqual(2, FakeHttpClient.calls)
        self.assertIn("retry 1/1", output)

    def test_4xx_403_429_do_not_retry(self) -> None:
        for status in (403, 429):
            with self.subTest(status=status):
                FakeHttpClient.calls = 0
                code, _ = self._run_main([_http_error(status)])
                self.assertEqual(collector.EXIT_COLLECT_FAILED, code)
                self.assertEqual(1, FakeHttpClient.calls)

    def test_all_pages_failing_returns_exit_1(self) -> None:
        code, output = self._run_main([_connection_error(), _connection_error()])

        self.assertEqual(collector.EXIT_COLLECT_FAILED, code)
        self.assertIn("todas as páginas falharam", output)

    def test_partial_page_failure_pushes_collected_projects_and_returns_zero(self) -> None:
        FakeHttpClient.responses = [_http_error(500), PROJECT_HTML]
        out = io.StringIO()
        with mock.patch.dict(collector.os.environ, self.env, clear=False), \
             mock.patch.object(collector, "HttpClient", FakeHttpClient), \
             mock.patch.object(collector.asyncio, "sleep", side_effect=_no_sleep), \
             mock.patch.object(collector, "_push", return_value={"received": 1, "inserted": 1, "updated": 0, "skipped": 0}) as push, \
             redirect_stdout(out):
            code = collector.main(["--pages", "2"])

        self.assertEqual(collector.EXIT_SUCCESS, code)
        push.assert_called_once()
        self.assertEqual(1, len(push.call_args.args[0]))
        self.assertIn("pages_failed=1", out.getvalue())

    def test_parser_invalid_in_all_healthy_pages_returns_exit_4(self) -> None:
        code, output = self._run_main([INVALID_HTML])

        self.assertEqual(collector.EXIT_PARSER_HEALTH, code)
        self.assertIn("parser health falhou", output)

    def test_ingest_500_returns_exit_3(self) -> None:
        response = requests.Response()
        response.status_code = 500
        err = requests.HTTPError(response=response)
        code, output = self._run_main_with_push_exception(err)

        self.assertEqual(collector.EXIT_INGEST_FAILED, code)
        self.assertIn("ERRO DE INGEST: HTTP 500", output)

    def test_ingest_connection_timeout_returns_exit_3(self) -> None:
        code, output = self._run_main_with_push_exception(requests.Timeout("timeout"))

        self.assertEqual(collector.EXIT_INGEST_FAILED, code)
        self.assertIn("Timeout", output)

    def test_ingest_invalid_json_returns_exit_3(self) -> None:
        code, output = self._run_main_with_push_exception(ValueError("invalid json"))

        self.assertEqual(collector.EXIT_INGEST_FAILED, code)
        self.assertIn("resposta JSON inválida", output)

    def test_logs_do_not_include_token_sensitive_header_or_raw_body(self) -> None:
        response = requests.Response()
        response.status_code = 500
        response._content = b"corpo bruto com super-secret-token e X-Internal-Ingest-Token"
        err = requests.HTTPError(response=response)
        code, output = self._run_main_with_push_exception(err)

        self.assertEqual(collector.EXIT_INGEST_FAILED, code)
        self.assertNotIn("super-secret-token", output)
        self.assertNotIn("X-Internal-Ingest-Token", output)
        self.assertNotIn("corpo bruto", output)
        self.assertNotIn("secret=raw", output)

    def test_success_with_zero_projects_in_healthy_page_returns_zero(self) -> None:
        with mock.patch.object(collector, "_push") as push:
            code, output = self._run_main([ZERO_PROJECTS_HTML])

        self.assertEqual(collector.EXIT_SUCCESS, code)
        self.assertIn("Nada a enviar", output)
        push.assert_not_called()

    def test_missing_config_returns_exit_2(self) -> None:
        out = io.StringIO()
        with mock.patch.dict(collector.os.environ, {}, clear=True), redirect_stdout(out):
            code = collector.main(["--pages", "1"])

        self.assertEqual(collector.EXIT_CONFIG, code)
        self.assertIn("SMARTPAYBOT_INGEST_URL", out.getvalue())

    def _run_main_with_push_exception(self, exc: BaseException) -> tuple[int, str]:
        FakeHttpClient.responses = [PROJECT_HTML]
        out = io.StringIO()
        with mock.patch.dict(collector.os.environ, self.env, clear=False), \
             mock.patch.object(collector, "HttpClient", FakeHttpClient), \
             mock.patch.object(collector.asyncio, "sleep", side_effect=_no_sleep), \
             mock.patch.object(collector, "_push", side_effect=exc), \
             redirect_stdout(out):
            code = collector.main(["--pages", "1"])
        return code, out.getvalue()


if __name__ == "__main__":
    unittest.main()
