#!/usr/bin/env python3
"""Mocked-HTTP tests for coros.py. No real network, ever."""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
import unittest.mock
import urllib.request

_COROS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "coros.py")
_SPEC = importlib.util.spec_from_file_location("coros", _COROS_PATH)
coros = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(coros)

EXPECTED_KEYS = ["hrv", "hrvBaseline", "rhr", "load", "sleepH", "activity"]
NULLS = {key: None for key in EXPECTED_KEYS}


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def deny_http(req, timeout=None):
    url = req.full_url if isinstance(req, urllib.request.Request) else req
    raise AssertionError("network blocked in tests: " + str(url))


class FakeHttp:
    def __init__(self, routes):
        self.routes = [(marker, list(items)) for marker, items in routes]
        self.calls = []

    def __call__(self, req, timeout=None):
        url = req.full_url if isinstance(req, urllib.request.Request) else req
        self.calls.append(url)
        for marker, items in self.routes:
            if marker in url:
                if not items:
                    raise AssertionError("no more queued responses for " + marker)
                item = items.pop(0)
                if isinstance(item, Exception):
                    raise item
                return FakeResponse(item)
        raise AssertionError("unexpected url: " + url)


def login_payload(token="tok", user_id=7):
    return {"result": 0, "data": {"accessToken": token, "userId": user_id}}


def day_payload(**fields):
    entry = {
        "avgSleepHrv": 42,
        "sleepHrvBase": 45,
        "rhr": 48,
        "trainingLoad": 85,
        "tib": 432,
    }
    entry.update(fields)
    return {"result": 0, "data": {"dayList": [entry]}}


def activity_payload(name="Run 10k"):
    return {"result": 0, "data": {"dataList": [{"name": name}]}}


def full_routes():
    return [
        ("account/login", [login_payload()]),
        ("dayDetail", [day_payload()]),
        ("activity/query", [activity_payload()]),
    ]


class CorosTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = unittest.mock.patch.dict(
            os.environ,
            {
                "XDG_CACHE_HOME": self.tmp.name,
                "COROS_EMAIL": "user@example.com",
                "COROS_PASSWORD": "secret",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("COROS_REGION", None)
        deny = unittest.mock.patch.object(urllib.request, "urlopen", deny_http)
        deny.start()
        self.addCleanup(deny.stop)

    def fake(self, routes):
        http = FakeHttp(routes)
        patcher = unittest.mock.patch.object(urllib.request, "urlopen", http)
        patcher.start()
        self.addCleanup(patcher.stop)
        return http

    def run_cli(self, argv):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = coros.main(argv)
        return code, out.getvalue(), err.getvalue()

    def token_cache(self):
        path = os.path.join(self.tmp.name, "omarchy-coros", "token.json")
        with open(path) as handle:
            return path, json.load(handle)

    def test_login_and_snapshot_parse(self):
        self.fake(full_routes())
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(out),
            {"hrv": 42, "hrvBaseline": 45, "rhr": 48, "load": 85, "sleepH": 7.2, "activity": "Run 10k"},
        )
        path, entry = self.token_cache()
        self.assertEqual(entry["access_token"], "tok")
        self.assertEqual(entry["user_id"], 7)
        self.assertEqual(entry["region"], "eu")
        self.assertIn("timestamp_ms", entry)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_rhr_falls_back_to_test_rhr(self):
        payload = day_payload()
        del payload["data"]["dayList"][0]["rhr"]
        payload["data"]["dayList"][0]["testRhr"] = 51
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [payload]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["rhr"], 51)

    def test_relogin_on_1019(self):
        http = self.fake(
            [
                ("account/login", [login_payload("tok-A"), login_payload("tok-B")]),
                ("dayDetail", [{"result": 1019, "message": "token expired"}, day_payload()]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)
        logins = [url for url in http.calls if "account/login" in url]
        self.assertEqual(len(logins), 2)
        _, entry = self.token_cache()
        self.assertEqual(entry["access_token"], "tok-B")

    def test_region_fallback(self):
        http = self.fake(
            [
                ("teameuapi.coros.com/account/login", [{"result": 1001, "message": "login failed"}]),
                ("teamapi.coros.com/account/login", [login_payload("us-tok")]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot", "--region", "eu"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["activity"], "Run 10k")
        day_calls = [url for url in http.calls if "dayDetail" in url]
        self.assertEqual(len(day_calls), 1)
        self.assertIn("teamapi.coros.com", day_calls[0])
        self.assertNotIn("teameuapi", day_calls[0])
        _, entry = self.token_cache()
        self.assertEqual(entry["region"], "us")

    def test_nulls_on_empty(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [{"result": 0, "data": {"dayList": []}}]),
                ("activity/query", [{"result": 0, "data": {"dataList": []}}]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), NULLS)

    def test_snapshot_stdout_is_single_line_json(self):
        self.fake(full_routes())
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertTrue(out.endswith("\n"))
        self.assertEqual(out.count("\n"), 1)
        self.assertEqual(sorted(json.loads(out.strip())), sorted(EXPECTED_KEYS))

    def test_missing_credentials_prints_nulls(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_PASSWORD": ""}):
            code, out, err = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), NULLS)
        self.assertIn("COROS_", err)

    def test_watch_streams_ndjson(self):
        line = {"hrv": 42, "hrvBaseline": 45, "rhr": 48, "load": 85, "sleepH": 7.2, "activity": "Run"}
        with (
            unittest.mock.patch.object(coros, "get_snapshot", return_value=dict(line)),
            unittest.mock.patch("time.sleep", side_effect=[None, KeyboardInterrupt]),
        ):
            code, out, _ = self.run_cli(["watch", "--interval", "1"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        for raw in lines:
            self.assertEqual(json.loads(raw), line)


if __name__ == "__main__":
    unittest.main()
