import io
import unittest
import urllib.error

from composants_watch import http
from composants_watch.http import FetchError, http_get


class FakeOpener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return io.BytesIO(out)


def err(code):
    return urllib.error.HTTPError("http://x", code, "e", {}, None)


class HttpGetTest(unittest.TestCase):
    def setUp(self):
        http._last_hit.clear()
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)

    def test_retries_on_503_then_succeeds(self):
        op = FakeOpener([err(503), err(503), b"ok"])
        self.assertEqual(http_get("http://a/x", opener=op, sleep=self.sleep), b"ok")
        self.assertEqual(len(op.requests), 3)
        self.assertTrue(self.sleeps)

    def test_no_retry_on_404(self):
        op = FakeOpener([err(404)])
        with self.assertRaises(FetchError):
            http_get("http://a/x", opener=op, sleep=self.sleep)
        self.assertEqual(len(op.requests), 1)

    def test_gives_up_after_two_retries(self):
        op = FakeOpener([err(503)] * 3)
        with self.assertRaises(FetchError):
            http_get("http://a/x", opener=op, sleep=self.sleep)
        self.assertEqual(len(op.requests), 3)

    def test_network_error_retried(self):
        op = FakeOpener([urllib.error.URLError("down"), b"ok"])
        self.assertEqual(http_get("http://a/x", opener=op, sleep=self.sleep), b"ok")

    def test_user_agent_header(self):
        op = FakeOpener([b"ok"])
        http_get("http://a/x", opener=op, sleep=self.sleep)
        self.assertEqual(op.requests[0].get_header("User-agent"),
                         "composants-watch/0.1 (usage personnel)")

    def test_same_host_spacing(self):
        op = FakeOpener([b"1", b"2"])
        http_get("http://a/x", opener=op, sleep=self.sleep)
        http_get("http://a/y", opener=op, sleep=self.sleep)
        self.assertTrue(any(s > 0 for s in self.sleeps))


if __name__ == "__main__":
    unittest.main()
