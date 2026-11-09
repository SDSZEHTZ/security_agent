import io
import unittest
from email.message import Message
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler

from pydantic import ValidationError

from models.tool import ToolContext
from tools.controlled_http import (
    HTTP_TIMEOUT_SECONDS, MAX_HTTP_RESPONSE_BYTES, ControlledHttpArgs,
    ControlledHttpCheckTool, NoRedirectHandler,
)


class FakeResponse:
    status = 200

    def __init__(self, body=b"ok"):
        self.headers = Message()
        self.headers["Content-Type"] = "text/plain"
        self.body = io.BytesIO(body)
        self.read_sizes = []

    def read(self, size=-1):
        self.read_sizes.append(size)
        return self.body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.body.close()


class ControlledHttpTests(unittest.TestCase):
    def setUp(self):
        self.context = ToolContext(
            task_id="T1", agent="CodeAnalysisAgent", action="analyze_code",
            authorized_origin="https://example.com",
        )
        self.tool = ControlledHttpCheckTool()
        self.response = FakeResponse()
        self.addCleanup(self.response.body.close)
        self.opener = Mock()
        self.opener.open.return_value = self.response
        patcher = patch("tools.controlled_http.build_opener", return_value=self.opener)
        self.addCleanup(patcher.stop)
        self.build_opener = patcher.start()

    def test_get_uses_fixed_origin_and_returns_only_bounded_metadata(self):
        result = self.tool.execute(ControlledHttpArgs(path="/health"), self.context)
        self.assertEqual(result, {
            "url": "https://example.com/health", "method": "GET", "status_code": 200,
            "content_type": "text/plain", "body_bytes_read": 2,
            "truncated": False, "redirect_not_followed": False,
        })
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.com/health")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(self.opener.open.call_args.kwargs, {"timeout": HTTP_TIMEOUT_SECONDS})
        self.assertEqual(self.response.read_sizes, [MAX_HTTP_RESPONSE_BYTES + 1])
        self.assertTrue(self.response.body.closed)

    def test_proxy_and_redirect_handlers_are_disabled(self):
        self.tool.execute(ControlledHttpArgs(), self.context)
        handlers = self.build_opener.call_args.args
        proxy = next(handler for handler in handlers if isinstance(handler, ProxyHandler))
        self.assertEqual(proxy.proxies, {})
        redirect = next(handler for handler in handlers if isinstance(handler, NoRedirectHandler))
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code):
                self.assertIsNone(redirect.redirect_request(None, None, code, "redirect", {}, "http://127.0.0.1/"))

    def test_head_never_reads_body(self):
        result = self.tool.execute(ControlledHttpArgs(method="HEAD"), self.context)
        self.assertEqual(self.response.read_sizes, [])
        self.assertEqual(result["body_bytes_read"], 0)
        self.assertFalse(result["truncated"])
        self.assertEqual(self.opener.open.call_args.args[0].get_method(), "HEAD")
        self.assertTrue(self.response.body.closed)

    def test_large_response_is_bounded_and_marked_truncated(self):
        self.response.body.close()
        self.response.body = io.BytesIO(b"x" * (MAX_HTTP_RESPONSE_BYTES + 10))
        result = self.tool.execute(ControlledHttpArgs(), self.context)
        self.assertEqual(self.response.read_sizes, [MAX_HTTP_RESPONSE_BYTES + 1])
        self.assertEqual(result["body_bytes_read"], MAX_HTTP_RESPONSE_BYTES)
        self.assertTrue(result["truncated"])
        self.assertTrue(self.response.body.closed)

    def test_exact_response_size_limit_is_not_truncated(self):
        self.response.body.close()
        self.response.body = io.BytesIO(b"x" * MAX_HTTP_RESPONSE_BYTES)
        result = self.tool.execute(ControlledHttpArgs(), self.context)
        self.assertFalse(result["truncated"])

    def test_read_failure_still_closes_response(self):
        self.response.read = Mock(side_effect=OSError("read failure"))
        with self.assertRaises(OSError):
            self.tool.execute(ControlledHttpArgs(), self.context)
        self.assertTrue(self.response.body.closed)

    def test_http_errors_return_status_and_close_response_without_following_redirect(self):
        for code in (302, 307, 404, 500):
            with self.subTest(code=code):
                headers = Message()
                headers["Content-Type"] = "text/plain"
                headers["Location"] = "http://127.0.0.1/private"
                body = io.BytesIO(b"sensitive response")
                self.addCleanup(body.close)
                error = HTTPError("https://example.com/", code, "error", headers, body)
                self.opener.open.side_effect = error
                result = self.tool.execute(ControlledHttpArgs(), self.context)
                self.assertEqual(result["status_code"], code)
                self.assertEqual(result["redirect_not_followed"], 300 <= code < 400)
                self.assertEqual(result["body_bytes_read"], 0)
                self.assertNotIn("sensitive", str(result))
                self.assertTrue(body.closed)
        self.assertEqual(self.opener.open.call_count, 4)

    def test_network_timeout_is_propagated_to_executor(self):
        self.opener.open.side_effect = TimeoutError("private network details")
        with self.assertRaises(TimeoutError):
            self.tool.execute(ControlledHttpArgs(), self.context)
        self.opener.open.assert_called_once()

    def test_only_get_and_head_and_declared_arguments_are_accepted(self):
        for arguments in ({"method": "POST"}, {"method": "get"}, {"url": "http://other.example/"}):
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                ControlledHttpArgs(**arguments)

    def test_unsafe_paths_are_rejected(self):
        for path in (
            "", "health", "http://other.example/", "//other.example/", "/a\\b",
            "/a?b=1", "/a#b", "/a\r\nb", "/a\x00b", "/../private", "/./health",
            "/%2e%2e/private", "/%252e%252e/private", "/%2fother.example/",
            "/%5cother.example/", "/%0d%0aX-Test:value", "/%2500", "/%7f",
            "/health%3fkey=value", "/health%23fragment", "/" + "a" * 200,
        ):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                ControlledHttpArgs(path=path)
        self.build_opener.assert_not_called()

    def test_excessive_encoding_depth_is_rejected(self):
        path = "/%2e"
        for _ in range(11):
            path = path.replace("%", "%25")
        with self.assertRaises(ValidationError):
            ControlledHttpArgs(path=path)

    def test_safe_encoded_path_is_preserved(self):
        path = "/%E4%BD%A0%E5%A5%BD"
        result = self.tool.execute(ControlledHttpArgs(path=path), self.context)
        self.assertEqual(result["url"], "https://example.com" + path)

    def test_authorized_origin_is_required_before_any_request(self):
        context = self.context.model_copy(update={"authorized_origin": None})
        with self.assertRaisesRegex(PermissionError, "^AUTHORIZED_ORIGIN_REQUIRED$"):
            self.tool.execute(ControlledHttpArgs(), context)
        self.build_opener.assert_not_called()

    def test_invalid_origin_is_rejected_before_any_request(self):
        for origin in (
            "ftp://example.com", "https://", "https://user:password@example.com",
            "https://example.com/private", "https://example.com?x=1", "https://example.com#x",
            "https://example.com:bad", "https://example.com:99999", "https://[bad",
            "https://exam ple.com", "https://example.com\n", "https://exam\tple.com",
            "https://example.com\x00",
        ):
            with self.subTest(origin=origin):
                context = self.context.model_copy(update={"authorized_origin": origin})
                with self.assertRaises(ValueError):
                    self.tool.execute(ControlledHttpArgs(), context)
        self.build_opener.assert_not_called()

    def test_origin_with_port_or_ipv6_is_supported(self):
        for origin, expected in (
            ("https://example.com:8443/", "https://example.com:8443/health"),
            ("http://[::1]:8080", "http://[::1]:8080/health"),
        ):
            with self.subTest(origin=origin):
                self.opener.open.return_value = FakeResponse()
                context = self.context.model_copy(update={"authorized_origin": origin})
                result = self.tool.execute(ControlledHttpArgs(path="/health"), context)
                self.assertEqual(result["url"], expected)


if __name__ == "__main__":
    unittest.main()
