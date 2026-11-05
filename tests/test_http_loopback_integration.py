"""Real local socket tests: no public internet, API keys, or external hosts."""

import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from main import build_runtime
from models.task import Task
from planner.demo_planner import DemoPlanner
from state import AgentState
from tools.controlled_http import MAX_HTTP_RESPONSE_BYTES


class _Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.server.received.append(("HEAD", self.path))
        self.send_response(204)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()

    def do_GET(self):
        self.server.received.append(("GET", self.path))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/should-not-be-requested")
            self.end_headers()
            return
        body = b"X" * (MAX_HTTP_RESPONSE_BYTES + 20) if self.path == "/large" else b"ready"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass  # Keep tests quiet.


class LoopbackHttpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        Path(self.directory.name, "sample.py").write_text("print('safe')\n", encoding="utf-8")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.received = []
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        # Cleanup runs in reverse order: shutdown, join, close.
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.shutdown)
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.runtime = build_runtime(DemoPlanner())

    def run_baseline(self, arguments=None, origin=None):
        state = AgentState(self.directory.name, authorized_origin=self.origin if origin is None else origin)
        state.phase = "VERIFY"
        task = Task("T1", "VerificationAgent", "check_http_baseline",
                    state.target, arguments=arguments or {}, phase="VERIFY")
        state.tasks.append(task)
        result = self.runtime.supervisor.delegate(task, state)
        return task, state, result

    def test_get_and_head_observe_real_local_http_without_findings(self):
        for args, expected_status in (({"method": "GET", "path": "/health"}, 200),
                                      ({"method": "HEAD", "path": "/health"}, 204)):
            with self.subTest(args=args):
                task, state, result = self.run_baseline(args)
                self.assertEqual(task.status, "COMPLETED")
                self.assertEqual(result.execution_status, "SUCCESS")
                baseline = result.data["http_baseline"]
                self.assertEqual(baseline["status_code"], expected_status)
                self.assertEqual(baseline["method"], args["method"])
                self.assertEqual(state.evidence, [])
                self.assertEqual(state.findings, [])
        self.assertEqual(self.server.received, [("GET", "/health"), ("HEAD", "/health")])

    def test_redirect_is_observed_but_not_followed(self):
        task, state, result = self.run_baseline({"method": "GET", "path": "/redirect"})
        self.assertEqual(task.status, "COMPLETED")
        self.assertEqual(result.data["http_baseline"]["status_code"], 302)
        self.assertTrue(result.data["http_baseline"]["redirect_not_followed"])
        self.assertEqual(self.server.received, [("GET", "/redirect")])
        self.assertFalse(state.evidence)

    def test_bounded_response_and_invalid_path_has_no_http_side_effects(self):
        _task, _state, result = self.run_baseline({"method": "GET", "path": "/large"})
        baseline = result.data["http_baseline"]
        self.assertTrue(baseline["truncated"])
        self.assertEqual(baseline["body_bytes_read"], MAX_HTTP_RESPONSE_BYTES)
        before = list(self.server.received)
        for path in ("//evil.invalid/", "/../secret", "http://evil.invalid/"):
            with self.subTest(path=path):
                task, state, denied = self.run_baseline({"method": "GET", "path": path})
                self.assertEqual(task.status, "FAILED")
                self.assertEqual(denied.execution_status, "FAILED")
                self.assertEqual(state.evidence, [])
                self.assertEqual(self.server.received, before)


if __name__ == "__main__":
    unittest.main()
