#!/usr/bin/env python3
"""Mocked-HTTP tests for coros.py. No real network, ever."""

import contextlib
import email.message
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
import unittest
import unittest.mock
import urllib.error
import urllib.request

_COROS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "coros.py")
_SPEC = importlib.util.spec_from_file_location("coros", _COROS_PATH)
coros = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(coros)

EXPECTED_KEYS = list(coros.NULL_SNAPSHOT)
NULLS = dict(coros.NULL_SNAPSHOT)


class FakeResponse:
    def __init__(self, payload):
        if isinstance(payload, bytes):
            self._body = payload
        elif isinstance(payload, str):
            self._body = payload.encode("utf-8")
        else:
            self._body = json.dumps(payload).encode("utf-8")

    def read(self, n=-1):
        if n is None or n < 0:
            return self._body
        return self._body[:n]

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


def login_payload(token="tok", user_id=7, region_id=None, result=0):
    data = {"accessToken": token, "userId": user_id}
    if region_id is not None:
        data["regionId"] = region_id
    return {"result": result, "data": data}


def day_payload(**fields):
    entry = {
        "happenDay": 20260910,
        "avgSleepHrv": 42,
        "sleepHrvBase": 45,
        "sleepHrvIntervalList": [5, 17, 22, 30],
        "rhr": 48,
        "testRhr": 51,
        "trainingLoad": 85,
        "trainingLoadRatio": 0.8,
        "trainingLoadRatioState": 2,
        "t7d": 200,
        "t28d": 800,
        "ati": 40.0,
        "cti": 50.0,
        "tib": 10.0,
        "tiredRateNew": -5.0,
        "tiredRateStateNew": 2,
        "recomendTlMin": 210,
        "recomendTlMax": 315,
    }
    entry.update(fields)
    return {
        "result": 0,
        "data": {
            "dayList": [entry],
            "weekList": [{"trainingLoad": 120, "recomendTlMin": 210, "recomendTlMax": 315}],
        },
    }


def default_snapshot(**over):
    row = dict(NULLS)
    row.update(
        {
            "hrv": 42,
            "hrvBaseline": 45,
            "hrvBandLow": 22,
            "hrvBandHigh": 30,
            "rhr": 48,
            "testRhr": 51,
            "load": 85,
            "load7d": 200,
            "load28d": 800,
            "loadRatio": 0.8,
            "loadState": 2,
            "loadWeek": 120,
            "loadWeekMin": 210,
            "loadWeekMax": 315,
            "ati": 40.0,
            "cti": 50.0,
            "balance": 10.0,
            "fatigue": -5.0,
            "fatigueState": 2,
            "activity": "Run 10k",
            "activityDay": "2026-09-07",
            "day": "2026-09-10",
            "error": None,
        }
    )
    row.update(over)
    return row


def activity_payload(name="Run 10k", date=20260907):
    item = {"name": name}
    if date is not None:
        item["date"] = date
    return {"result": 0, "data": {"dataList": [item]}}


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
                "XDG_CONFIG_HOME": self.tmp.name,
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
        deny_open = unittest.mock.patch.object(coros, "http_open", deny_http)
        deny_open.start()
        self.addCleanup(deny_open.stop)

    def fake(self, routes):
        http = FakeHttp(routes)
        patcher = unittest.mock.patch.object(coros, "http_open", http)
        patcher.start()
        self.addCleanup(patcher.stop)
        return http

    def run_cli(self, argv, stdin_text=""):
        out = io.StringIO()
        err = io.StringIO()
        stdin = io.StringIO(stdin_text)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), unittest.mock.patch.object(sys, "stdin", stdin):
            code = coros.main(argv)
        out_text, err_text = out.getvalue(), err.getvalue()
        self.assertNotIn("secret", out_text)
        self.assertNotIn("secret", err_text)
        return code, out_text, err_text

    def creds_path(self):
        return os.path.join(self.tmp.name, "omarchy-coros", "credentials")

    def token_cache(self):
        path = os.path.join(self.tmp.name, "omarchy-coros", "token.json")
        with open(path) as handle:
            return path, json.load(handle)

    def test_login_and_snapshot_parse(self):
        self.fake(full_routes())
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), default_snapshot())
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

    def test_cached_resolved_region_reused_on_later_polls(self):
        http = self.fake(
            [
                ("teameuapi.coros.com/account/login", [{"result": 1001, "message": "login failed"}]),
                ("teamapi.coros.com/account/login", [login_payload("us-tok")]),
                ("dayDetail", [day_payload(), day_payload()]),
                ("activity/query", [activity_payload(), activity_payload()]),
            ]
        )
        for _ in range(2):
            code, out, _ = self.run_cli(["snapshot", "--region", "eu"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["hrv"], 42)
        logins = [url for url in http.calls if "account/login" in url]
        self.assertEqual(len(logins), 2)
        self.assertEqual(len([url for url in logins if "teameuapi" in url]), 1)
        self.assertNotIn("teameuapi", [url for url in http.calls if "dayDetail" in url])

    def test_world_readable_cache_refused(self):
        cache_dir = os.path.join(self.tmp.name, "omarchy-coros")
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        path = os.path.join(cache_dir, "token.json")
        with open(path, "w") as handle:
            json.dump(
                {
                    "access_token": "stale",
                    "user_id": 7,
                    "region": "eu",
                    "timestamp_ms": int(time.time() * 1000),
                },
                handle,
            )
        os.chmod(path, 0o644)
        http = self.fake(full_routes())
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)
        self.assertTrue(any("account/login" in url for url in http.calls))
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_credentials_file_fallback(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            conf = os.path.join(self.tmp.name, "omarchy-coros")
            os.makedirs(conf, mode=0o700, exist_ok=True)
            path = os.path.join(conf, "credentials")
            with open(path, "w") as handle:
                handle.write("COROS_EMAIL=user@example.com\nCOROS_PASSWORD=secret\nCOROS_REGION=eu\n")
            os.chmod(path, 0o600)
            self.fake(full_routes())
            code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)

    def test_double_login_failure_cools_down(self):
        fail = [{"result": 1001, "message": "bad"}, {"result": 1002, "message": "bad"}]
        http = self.fake([("account/login", fail)])
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")
        self.assertEqual(len([url for url in http.calls if "account/login" in url]), 2)
        http2 = self.fake([])
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")
        self.assertEqual(http2.calls, [])

    def test_snapshot_uses_latest_day_with_recovery_metrics(self):
        payload = {
            "result": 0,
            "data": {
                "dayList": [
                    {
                        "happenDay": 20260907,
                        "avgSleepHrv": 26,
                        "sleepHrvBase": 27,
                        "rhr": 67,
                        "trainingLoad": 18,
                        "tib": 432,
                    },
                    {
                        "happenDay": 20260910,
                        "avgSleepHrv": 24,
                        "sleepHrvBase": 26,
                        "rhr": 61,
                        "trainingLoad": 0,
                        "tib": 450,
                    },
                    {"happenDay": 20260912, "trainingLoad": 0, "tib": 26.0},
                ]
            },
        }
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [payload]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(out),
            default_snapshot(
                hrv=24,
                hrvBaseline=26,
                hrvBandLow=None,
                hrvBandHigh=None,
                rhr=61,
                testRhr=None,
                load=0,
                load7d=None,
                load28d=None,
                loadRatio=None,
                loadState=None,
                loadWeek=None,
                loadWeekMin=None,
                loadWeekMax=None,
                ati=None,
                cti=None,
                balance=450,
                fatigue=None,
                fatigueState=None,
            ),
        )

    def test_last_activity_picks_newest(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [day_payload()]),
                (
                    "activity/query",
                    [
                        {
                            "result": 0,
                            "data": {
                                "dataList": [
                                    {"name": "Old Ride", "date": 20260906, "startTime": 1},
                                    {"name": "New Ride", "date": 20260907, "startTime": 2},
                                ]
                            },
                        }
                    ],
                ),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        snap = json.loads(out)
        self.assertEqual(snap["activity"], "New Ride")
        self.assertEqual(snap["activityDay"], "2026-09-07")

    def test_tib_is_impact_balance_not_sleep(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [day_payload(tib=25.0)]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        snap = json.loads(out)
        self.assertEqual(snap["balance"], 25.0)
        self.assertNotIn("sleepH", snap)

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
        expected = dict(NULLS)
        expected["error"] = "auth"
        self.assertEqual(json.loads(out), expected)
        self.assertIn("COROS_", err)

    def test_watch_streams_ndjson(self):
        line = default_snapshot(activity="Run")
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

    def test_login_stdin_writes_creds_and_snapshots(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            self.fake(full_routes())
            payload = json.dumps({"email": "user@example.com", "password": "secret", "region": "eu"})
            code, out, err = self.run_cli(["login"], stdin_text=payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)
        self.assertIsNone(json.loads(out)["error"])
        self.assertNotIn("secret", out)
        self.assertNotIn("secret", err)
        path = os.path.join(self.tmp.name, "omarchy-coros", "credentials")
        with open(path) as handle:
            text = handle.read()
        self.assertIn(coros.CREDS_MARK, text)
        self.assertIn("COROS_EMAIL=user@example.com", text)
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_login_empty_body_is_auth_error(self):
        code, out, _ = self.run_cli(["login"], stdin_text="{}")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")

    def test_login_one_json_line_does_not_read_rest_of_stdin(self):
        class LineStdin:
            def readline(self):
                return json.dumps({"email": "user@example.com", "password": "secret", "region": "eu"}) + "\n"

            def read(self, *args):
                raise AssertionError("login must not wait for EOF after one JSON line")

        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            self.fake(
                [
                    ("teameuapi.coros.com/account/login", [login_payload("us-tok", region_id=1)]),
                    ("dayDetail", [day_payload()]),
                    ("activity/query", [activity_payload()]),
                ]
            )
            out = io.StringIO()
            err = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), unittest.mock.patch.object(sys, "stdin", LineStdin()):
                code = coros.main(["login"])
        self.assertEqual(code, 0)
        self.assertIsNone(json.loads(out.getvalue())["error"])
        _, entry = self.token_cache()
        self.assertEqual(entry["region"], "us")
        cred_path = os.path.join(self.tmp.name, "omarchy-coros", "credentials")
        with open(cred_path) as handle:
            self.assertIn("COROS_REGION=us", handle.read())

    def test_login_result_0000_string_is_success(self):
        self.fake(
            [
                ("account/login", [login_payload(result="0000")]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)

    def test_region_id_from_eu_login_routes_to_us(self):
        http = self.fake(
            [
                ("teameuapi.coros.com/account/login", [login_payload("us-tok", region_id=1)]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot", "--region", "eu"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)
        day_calls = [url for url in http.calls if "dayDetail" in url]
        self.assertEqual(len(day_calls), 1)
        self.assertIn("teamapi.coros.com", day_calls[0])
        self.assertNotIn("teameuapi", day_calls[0])
        _, entry = self.token_cache()
        self.assertEqual(entry["region"], "us")
        self.assertEqual(entry["access_token"], "us-tok")

    def test_region_id_3_stays_on_eu(self):
        http = self.fake(
            [
                ("teamapi.coros.com/account/login", [login_payload("eu-tok", region_id=3)]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot", "--region", "us"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)
        self.assertIn("teameuapi.coros.com", [url for url in http.calls if "dayDetail" in url][0])
        _, entry = self.token_cache()
        self.assertEqual(entry["region"], "eu")

    def test_html_daydetail_is_network_without_cooldown(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", ["<html>"]),
            ]
        )
        code, out, err = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "network")
        self.assertFalse(os.path.exists(coros.cooldown_file()))
        self.assertNotIn("secret", out)
        self.assertNotIn("secret", err)

    def test_urlerror_is_network(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [urllib.error.URLError("timed out")]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "network")
        self.assertFalse(os.path.exists(coros.cooldown_file()))

    def test_world_readable_creds_ignored(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            conf = os.path.join(self.tmp.name, "omarchy-coros")
            os.makedirs(conf, mode=0o700, exist_ok=True)
            path = os.path.join(conf, "credentials")
            with open(path, "w") as handle:
                handle.write("COROS_EMAIL=user@example.com\nCOROS_PASSWORD=secret\nCOROS_REGION=eu\n")
            os.chmod(path, 0o644)
            http = self.fake([])
            code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")
        self.assertEqual(http.calls, [])

    def test_login_does_not_write_creds_if_both_regions_fail(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            self.fake(
                [
                    ("account/login", [{"result": 1001, "message": "bad"}, {"result": 1002, "message": "bad"}]),
                ]
            )
            payload = json.dumps({"email": "user@example.com", "password": "secret", "region": "eu"})
            code, out, err = self.run_cli(["login"], stdin_text=payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")
        self.assertFalse(os.path.exists(self.creds_path()))
        self.assertNotIn("secret", out)
        self.assertNotIn("secret", err)

    def test_login_failure_does_not_overwrite_good_creds(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            conf = os.path.join(self.tmp.name, "omarchy-coros")
            os.makedirs(conf, mode=0o700, exist_ok=True)
            path = self.creds_path()
            before = "# Written by omarchy-coros\nCOROS_EMAIL=user@example.com\nCOROS_PASSWORD=secret\nCOROS_REGION=eu\n"
            with open(path, "w") as handle:
                handle.write(before)
            os.chmod(path, 0o600)
            self.fake(
                [
                    ("account/login", [{"result": 1001, "message": "bad"}, {"result": 1002, "message": "bad"}]),
                ]
            )
            payload = json.dumps({"email": "user@example.com", "password": "secret", "region": "us"})
            code, out, _ = self.run_cli(["login"], stdin_text=payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")
        with open(path) as handle:
            self.assertEqual(handle.read(), before)

    def test_redirect_off_host_does_not_follow_or_send_token(self):
        class Rec(urllib.request.BaseHandler):
            handler_order = 100

            def __init__(self):
                self.urls = []

            def default_open(self, req):
                self.urls.append(req.full_url)
                headers = email.message.Message()
                headers["Location"] = "https://evil.example/steal"
                fp = io.BytesIO(b"")
                fp.url = req.full_url
                fp.code = 302
                fp.msg = "Found"
                fp.headers = headers
                fp.info = lambda: headers
                fp.geturl = lambda: req.full_url
                fp.getcode = lambda: 302
                return fp

        rec = Rec()
        opener = urllib.request.build_opener(coros.NoRedirectHandler(), rec)
        req = urllib.request.Request(
            "https://teameuapi.coros.com/analyse/dayDetail/query",
            headers={"accessToken": "tok-secret"},
            method="GET",
        )
        with self.assertRaises(coros.NetworkError):
            opener.open(req, timeout=1)
        self.assertEqual(rec.urls, ["https://teameuapi.coros.com/analyse/dayDetail/query"])
        self.assertTrue(any(isinstance(handler, coros.NoRedirectHandler) for handler in coros._OPENER.handlers))

    def test_nonzero_daydetail_after_1019_is_network(self):
        self.fake(
            [
                ("account/login", [login_payload("tok-A"), login_payload("tok-B")]),
                ("dayDetail", [{"result": 1019, "message": "token expired"}, {"result": 1001, "message": "nope"}]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "network")
        self.assertFalse(os.path.exists(coros.cooldown_file()))

    def test_logout_removes_creds_token_and_cooldown(self):
        with tempfile.TemporaryDirectory() as cfg, tempfile.TemporaryDirectory() as cache:
            with unittest.mock.patch.dict(
                os.environ,
                {
                    "XDG_CONFIG_HOME": cfg,
                    "XDG_CACHE_HOME": cache,
                    "COROS_EMAIL": "",
                    "COROS_PASSWORD": "",
                },
            ):
                cred_dir = os.path.join(cfg, "omarchy-coros")
                cache_dir = os.path.join(cache, "omarchy-coros")
                os.makedirs(cred_dir, mode=0o700)
                os.makedirs(cache_dir, mode=0o700)
                creds = os.path.join(cred_dir, "credentials")
                token = os.path.join(cache_dir, "token.json")
                cooldown = os.path.join(cache_dir, "auth_cooldown")
                with open(creds, "w") as handle:
                    handle.write(
                        "# Written by omarchy-coros\nCOROS_EMAIL=user@example.com\nCOROS_PASSWORD=secret\nCOROS_REGION=eu\n"
                    )
                os.chmod(creds, 0o600)
                with open(token, "w") as handle:
                    json.dump(
                        {
                            "access_token": "tok",
                            "user_id": 7,
                            "region": "eu",
                            "timestamp_ms": int(time.time() * 1000),
                        },
                        handle,
                    )
                with open(cooldown, "w"):
                    pass
                http = self.fake([])
                code, out, err = self.run_cli(["logout"])
            self.assertEqual(code, 0)
            snap = json.loads(out)
            self.assertEqual(snap["error"], "auth")
            self.assertEqual(snap["hrv"], None)
            self.assertTrue(out.endswith("\n"))
            self.assertEqual(out.count("\n"), 1)
            self.assertFalse(os.path.exists(creds))
            self.assertFalse(os.path.exists(token))
            self.assertFalse(os.path.exists(cooldown))
            self.assertEqual(http.calls, [])
            self.assertNotIn("secret", out)
            self.assertNotIn("secret", err)

    def test_logout_without_files_is_auth(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            code, out, _ = self.run_cli(["logout"])
        self.assertEqual(code, 0)
        expected = dict(NULLS)
        expected["error"] = "auth"
        self.assertEqual(json.loads(out), expected)

    def test_activity_name_is_capped(self):
        long_name = "R" * 200
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload(name=long_name)]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["activity"], "R" * 120)


if __name__ == "__main__":
    unittest.main()
