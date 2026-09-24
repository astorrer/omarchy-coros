#!/usr/bin/env python3
"""Mocked-HTTP tests for coros.py. No real network, ever."""

import contextlib
import email.message
import importlib.util
import io
import json
import os
import runpy
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
            "readiness": 82,
            "recoveryHours": 6.5,
            "race5k": 1172,
            "race10k": 2458,
            "raceHalf": 5464,
            "raceMarathon": 12084,
            "plan": "Tempo Run",
            "planKm": 8.0,
            "planMin": 46,
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


def dashboard_payload(summary=None, **fields):
    base = {
        "recoveryPct": 82,
        "fullRecoveryHours": 6.5,
        "runScoreList": [
            {"type": 5, "duration": 1172},
            {"type": 4, "predictSecond": 2458},
            {"type": 2, "time": 5464},
            {"type": 1, "predictTime": 12084},
        ],
    }
    if isinstance(summary, dict):
        base = summary
    base.update(fields)
    return {"result": 0, "data": {"summaryInfo": base}}


def schedule_payload(entities="default", programs="default"):
    if entities == "default":
        entities = [
            {
                "happenDay": 20260923,
                "idInPlan": 11,
                "planId": 3,
                "planProgramId": 71,
                "status": 1,
                "sortNoInSchedule": 1,
                "sportData": {"name": "Tempo Run", "distance": 800000},
            }
        ]
    if programs == "default":
        programs = [{"id": 71, "idInPlan": 11, "planId": 3, "name": "Library Tempo", "sportType": 1, "planDuration": 2760}]
    return {"result": 0, "data": {"entities": entities, "programs": programs}}


def extras_routes(count=1):
    return [
        ("dashboard/query", [dashboard_payload()] * count),
        ("training/schedule/query", [schedule_payload()] * count),
    ]


def full_routes():
    return [
        ("account/login", [login_payload()]),
        ("dayDetail", [day_payload()]),
        ("activity/query", [activity_payload()]),
    ] + extras_routes()


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
        self.real_http_open = coros.http_open
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

    def write_cache(self, entry):
        cache = os.path.join(self.tmp.name, "omarchy-coros")
        os.makedirs(cache, mode=0o700, exist_ok=True)
        path = os.path.join(cache, "token.json")
        with open(path, "w") as handle:
            json.dump(entry, handle)
        os.chmod(path, 0o600)
        return path

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
            ] + extras_routes()
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
            ] + extras_routes()
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
            ] + extras_routes()
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
            ] + extras_routes(2)
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
            ] + extras_routes()
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
            ] + extras_routes()
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
            ] + extras_routes()
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        snap = json.loads(out)
        self.assertEqual(snap["balance"], 25.0)
        self.assertNotIn("sleepH", snap)

    def test_dashboard_fields_race_sources_and_edges(self):
        fields = coros.dashboard_fields(
            dashboard_payload(
                runScoreList=[
                    {"type": 5, "duration": 1172},
                    {"raceType": 4, "predictSecond": 2458},
                    {"type": 2, "predictTime": 5464},
                    {"type": 1, "time": 12084},
                    {"type": 9, "duration": 999},
                    {"type": 3, "duration": 0},
                    {"type": 1, "duration": -5},
                    {"type": 2},
                    "junk",
                ],
                recoveryPct="82",
                fullRecoveryHours=None,
            )
        )
        self.assertEqual(fields["race5k"], 1172)
        self.assertEqual(fields["race10k"], 2458)
        self.assertEqual(fields["raceHalf"], 5464)
        self.assertEqual(fields["raceMarathon"], 12084)
        self.assertIsNone(fields["readiness"])  # numeric strings are not numbers
        self.assertIsNone(fields["recoveryHours"])
        nulls = {key: None for key in fields}
        self.assertEqual(coros.dashboard_fields({"result": 0, "data": "x"}), nulls)
        self.assertEqual(coros.dashboard_fields({"data": {"summaryInfo": "junk"}}), nulls)
        self.assertEqual(coros.dashboard_fields(None), nulls)

    def test_plan_program_matching(self):
        programs = [
            "junk",
            {"id": 71, "idInPlan": 11, "planId": 3, "name": "ByIdInPlan"},
            {"id": 72, "name": "ByPlanProgramId"},
            {"id": 73, "idInPlan": 99, "planId": 9, "name": "WrongPlan"},
        ]
        self.assertEqual(coros.plan_program({"idInPlan": 11, "planId": 3}, programs)["name"], "ByIdInPlan")
        self.assertEqual(coros.plan_program({"idInPlan": 11}, programs)["name"], "ByIdInPlan")
        self.assertEqual(coros.plan_program({"planProgramId": 72}, programs)["name"], "ByPlanProgramId")
        self.assertEqual(
            coros.plan_program({"planProgramId": 72, "idInPlan": 11, "planId": 3}, programs)["name"],
            "ByIdInPlan",
        )
        self.assertIsNone(coros.plan_program({"idInPlan": 11, "planId": 9}, programs))
        self.assertIsNone(coros.plan_program({"idInPlan": 42, "planId": 3}, programs))
        self.assertIsNone(coros.plan_program({}, programs))

    def test_plan_fields_variants(self):
        self.assertEqual(coros.plan_fields(schedule_payload(entities=[], programs=[])), (None, None, None))
        self.assertEqual(coros.plan_fields(None), (None, None, None))
        self.assertEqual(coros.plan_fields({"result": 5, "data": "x"}), (None, None, None))
        self.assertEqual(coros.plan_fields(schedule_payload(entities=[{"idInPlan": 1}], programs=[])), (None, None, None))
        # distance and duration come from the program when the entity is bare
        resp = schedule_payload(
            entities=[{"idInPlan": 12, "planId": 3, "name": "Plain Entity"}],
            programs=[{"id": 72, "idInPlan": 12, "planId": 3, "planDistance": 500000, "estimatedTime": 3600}],
        )
        self.assertEqual(coros.plan_fields(resp), ("Plain Entity", 5.0, 60))
        # entity duration only when the program has none
        resp = schedule_payload(
            entities=[{"idInPlan": 12, "planId": 3, "duration": 1800}],
            programs=[{"id": 72, "idInPlan": 12, "planId": 3, "estimatedDistance": 700000}],
        )
        self.assertEqual(coros.plan_fields(resp), (None, 7.0, 30))
        # sportData distance wins over the program's
        resp = schedule_payload(
            entities=[{"idInPlan": 12, "planId": 3, "sportData": {"distance": 800000}}],
            programs=[{"id": 72, "idInPlan": 12, "planId": 3, "planDistance": 999999, "name": "Library Tempo"}],
        )
        self.assertEqual(coros.plan_fields(resp), ("Library Tempo", 8.0, None))
        # zero distance and zero planDuration fall through to the next source
        resp = schedule_payload(
            entities=[{"idInPlan": 12, "planId": 3, "sportData": {"distance": 0}}],
            programs=[{"id": 72, "idInPlan": 12, "planId": 3, "planDistance": 500000, "planDuration": 0, "duration": 2700}],
        )
        self.assertEqual(coros.plan_fields(resp), (None, 5.0, 45))
        # a non-string sportData name is skipped, not stringified
        resp = schedule_payload(
            entities=[{"idInPlan": 11, "planId": 3, "sportData": {"name": 42}}],
            programs=[{"id": 71, "idInPlan": 11, "planId": 3, "name": "Library Tempo"}],
        )
        self.assertEqual(coros.plan_fields(resp)[0], "Library Tempo")

    def test_plan_sort_order_fallbacks(self):
        # sortNo stands in when sortNoInSchedule is absent; missing sort keys sort first
        resp = schedule_payload(
            entities=[
                {"idInPlan": 11, "sortNo": 9, "sportData": {"name": "Later"}},
                {"idInPlan": 12, "sortNo": 2, "sportData": {"name": "Earlier"}},
            ],
            programs=[],
        )
        self.assertEqual(coros.plan_fields(resp)[0], "Earlier")
        resp = schedule_payload(
            entities=[
                {"idInPlan": 11, "sortNoInSchedule": 3, "sportData": {"name": "Sorted"}},
                {"idInPlan": 12, "sportData": {"name": "Unsorted"}},
            ],
            programs=[],
        )
        self.assertEqual(coros.plan_fields(resp)[0], "Unsorted")

    def test_plan_name_fallbacks(self):
        resp = schedule_payload(entities=[{"idInPlan": 11, "planId": 3}])
        self.assertEqual(coros.plan_fields(resp)[0], "Library Tempo")
        resp = schedule_payload(entities=[{"name": "Solo Entity"}], programs=[])
        self.assertEqual(coros.plan_fields(resp)[0], "Solo Entity")
        resp = schedule_payload(entities=[{"name": "P" * 200}], programs=[])
        self.assertEqual(coros.plan_fields(resp)[0], "P" * 120)

    def test_plan_skips_deleted_and_picks_earliest(self):
        resp = schedule_payload(
            entities=[
                {"idInPlan": 10, "status": 3, "sortNoInSchedule": 0, "sportData": {"name": "Deleted"}},
                {"idInPlan": 11, "sortNoInSchedule": 5, "sportData": {"name": "Later"}},
                {"idInPlan": 12, "sortNoInSchedule": 1, "sportData": {"name": "Earlier"}},
            ],
            programs=[],
        )
        self.assertEqual(coros.plan_fields(resp)[0], "Earlier")

    def test_optional_fetches_never_sink_snapshot(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
                ("dashboard/query", [urllib.error.URLError("down")]),
                ("training/schedule/query", [{"result": 1001, "message": "no schedule"}]),
            ]
        )
        code, out, err = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        snap = json.loads(out)
        self.assertEqual(snap["hrv"], 42)
        self.assertIsNone(snap["readiness"])
        self.assertIsNone(snap["plan"])
        self.assertIn("optional fetch failed", err)

    def test_optional_fetches_accept_resultless_bodies(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
                ("dashboard/query", [{"data": {"summaryInfo": {"recoveryPct": 71}}}]),
                ("training/schedule/query", [{"data": {"entities": [], "programs": []}}]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        snap = json.loads(out)
        self.assertEqual(snap["readiness"], 71)
        self.assertIsNone(snap["plan"])

    def test_schedule_query_uses_camel_case_dates(self):
        http = self.fake(full_routes())
        self.run_cli(["snapshot"])
        url = [u for u in http.calls if "schedule/query" in u][0]
        self.assertIn("startDate=", url)
        self.assertIn("endDate=", url)
        self.assertIn("supportRestExercise=1", url)
        self.assertNotIn("startDay", url)

    def test_nulls_on_empty(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", [{"result": 0, "data": {"dayList": []}}]),
                ("activity/query", [{"result": 0, "data": {"dataList": []}}]),
                ("dashboard/query", [dashboard_payload(summary={})]),
                ("training/schedule/query", [schedule_payload(entities=[], programs=[])]),
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
            def readline(self, size=-1):
                return json.dumps({"email": "user@example.com", "password": "secret", "region": "eu"}) + "\n"

            def read(self, *args):
                raise AssertionError("login must not wait for EOF after one JSON line")

        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            self.fake(
                [
                    ("teameuapi.coros.com/account/login", [login_payload("us-tok", region_id=1)]),
                    ("dayDetail", [day_payload()]),
                    ("activity/query", [activity_payload()]),
                ] + extras_routes()
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
            ] + extras_routes()
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
            ] + extras_routes()
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
            ] + extras_routes()
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
            ] + extras_routes()
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["activity"], "R" * 120)

    def test_login_refuses_credentials_symlink(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            conf = os.path.join(self.tmp.name, "omarchy-coros")
            os.makedirs(conf, mode=0o700, exist_ok=True)
            victim = os.path.join(conf, "victim")
            with open(victim, "w") as handle:
                handle.write("sentinel")
            os.symlink(victim, self.creds_path())
            self.fake(full_routes())
            payload = json.dumps({"email": "user@example.com", "password": "secret", "region": "eu"})
            code, out, err = self.run_cli(["login"], stdin_text=payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], None)
        with open(victim) as handle:
            self.assertEqual(handle.read(), "sentinel")
        self.assertFalse(os.path.islink(self.creds_path()))
        with open(self.creds_path()) as handle:
            self.assertIn(coros.CREDS_MARK, handle.read())
        self.assertEqual(os.stat(self.creds_path()).st_mode & 0o777, 0o600)

    def test_trip_cooldown_refuses_symlink(self):
        cache = os.path.join(self.tmp.name, "omarchy-coros")
        os.makedirs(cache, mode=0o700, exist_ok=True)
        target = os.path.join(cache, "victim")
        with open(target, "w") as handle:
            handle.write("sentinel")
        os.symlink(target, coros.cooldown_file())
        coros.trip_cooldown()
        self.assertFalse(coros.cooldown_active())
        with open(target) as handle:
            self.assertEqual(handle.read(), "sentinel")

    def test_login_oversized_stdin_is_auth_error(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            class HugeStdin:
                def readline(self, size=-1):
                    return "x" * (coros.LOGIN_BODY_MAX + 1)  # ignores the size hint

                def read(self, *args):
                    return ""

            out = io.StringIO()
            err = io.StringIO()
            with (
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
                unittest.mock.patch.object(sys, "stdin", HugeStdin()),
            ):
                code = coros.main(["login"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["error"], "auth")
        self.assertFalse(os.path.exists(self.creds_path()))

    def test_login_blank_line_huge_fallback_is_auth_error(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            class HugeFallback:
                def readline(self, size=-1):
                    return ""

                def read(self, size=-1):
                    return "y" * (size + 1)  # returns more than asked

            out = io.StringIO()
            err = io.StringIO()
            with (
                contextlib.redirect_stdout(out),
                contextlib.redirect_stderr(err),
                unittest.mock.patch.object(sys, "stdin", HugeFallback()),
            ):
                code = coros.main(["login"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["error"], "auth")


    def test_login_same_host_redirect_followed(self):
        handler = coros.NoRedirectHandler()
        req = urllib.request.Request("https://teameuapi.coros.com/analyse/dayDetail/query", method="GET")
        redirected = handler.redirect_request(req, None, 302, "Found", None, req.full_url)
        self.assertIsInstance(redirected, urllib.request.Request)
        self.assertEqual(redirected.full_url, req.full_url)

    def test_credential_ok_rejects_non_string(self):
        self.assertFalse(coros.credential_ok(None))
        self.assertFalse(coros.credential_ok(5))

    def test_write_credentials_rejects_injection_and_bad_region(self):
        with self.assertRaises(ValueError):
            coros.write_credentials("a\nb@c", "pw", "eu")
        with self.assertRaises(ValueError):
            coros.write_credentials("a@b", "pw\rx", "eu")
        with self.assertRaises(ValueError):
            coros.write_credentials("a@b", "pw", "cn")

    def test_write_credentials_oserror_cleanup(self):
        with (
            unittest.mock.patch.object(coros.os, "fchmod", side_effect=OSError("chmod")),
            unittest.mock.patch.object(coros.os, "close", side_effect=OSError("close")),
            unittest.mock.patch.object(coros.os, "unlink", side_effect=OSError("unlink")),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(OSError):
                coros.write_credentials("a@b.c", "pw", "eu")

    def test_no_no_follow_fallback(self):
        saved = getattr(coros.os, "O_NOFOLLOW", None)
        has = hasattr(coros.os, "O_NOFOLLOW")
        if has:
            del coros.os.O_NOFOLLOW
        try:
            coros.write_credentials("a@b.c", "pw", "eu")
            coros.save_token("tok", 7, "eu")
            coros.trip_cooldown()
        finally:
            if has:
                coros.os.O_NOFOLLOW = saved
        self.assertTrue(os.path.exists(coros.cooldown_file()))
        self.assertTrue(os.path.exists(coros.cache_file()))

    def test_load_token_refuses_bool_token(self):
        self.write_cache(
            {"access_token": True, "user_id": 7, "region": "eu", "timestamp_ms": int(time.time() * 1000)}
        )
        self.fake(full_routes())
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)

    def test_load_token_refuses_unknown_region(self):
        self.write_cache(
            {"access_token": "tok", "user_id": 7, "region": "cn", "timestamp_ms": int(time.time() * 1000)}
        )
        self.fake(full_routes())
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)

    def test_load_token_refuses_stale_cache(self):
        self.write_cache({"access_token": "tok", "user_id": 7, "region": "eu", "timestamp_ms": 1})
        self.fake(full_routes())
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)

    def test_coerce_token_rejects_unsafe_types(self):
        for value in (True, False, {}, [], None):
            self.assertIsNone(coros.coerce_token(value))
        self.assertEqual(coros.coerce_token("  tok  "), "tok")

    def test_coerce_user_id_edges(self):
        self.assertIsNone(coros.coerce_user_id(True))
        self.assertIsNone(coros.coerce_user_id(None))
        self.assertIsNone(coros.coerce_user_id("not-an-int"))
        self.assertIsNone(coros.coerce_user_id({}))
        self.assertEqual(coros.coerce_user_id("7"), 7)

    def test_save_token_noop_on_bad_input(self):
        cache = os.path.join(os.path.dirname(coros.cache_file()), "token.json")
        self.assertFalse(os.path.exists(cache))
        coros.save_token(False, 7, "eu")
        coros.save_token("tok", None, "eu")
        coros.save_token("tok", 7, "cn")
        self.assertFalse(os.path.exists(cache))

    def test_save_token_failure_prints_and_cleans(self):
        with (
            unittest.mock.patch.object(coros.os, "open", side_effect=OSError("no space")),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            coros.save_token("tok", 7, "eu")

    def test_save_token_cleanup_closes_on_partial_write(self):
        with (
            unittest.mock.patch.object(coros.os, "fchmod", side_effect=OSError("chmod")),
            unittest.mock.patch.object(coros.os, "close", side_effect=OSError("close")),
            unittest.mock.patch.object(coros.os, "unlink", side_effect=OSError("unlink")),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            coros.save_token("tok", 7, "eu")

    def test_http_open_forwards_to_opener(self):
        sentinel = object()
        with unittest.mock.patch.object(coros, "http_open", self.real_http_open):
            with unittest.mock.patch.object(coros._OPENER, "open", return_value=sentinel) as opener:
                self.assertIs(coros.http_open("url", timeout=3), sentinel)
                opener.assert_called_once_with("url", timeout=3)

    def test_oversized_response_is_network_error(self):
        self.fake(
            [
                ("account/login", [login_payload()]),
                ("dayDetail", ["x" * (coros.MAX_BODY_BYTES + 1)]),
            ]
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "network")

    def test_result_code_bad_responses(self):
        self.assertIsNone(coros.result_code(["not", "a", "dict"]))
        self.assertIsNone(coros.result_code({"result": "NaN"}))
        self.assertIsNone(coros.result_code({"result": {"nested": 1}}))

    def test_login_failure_without_message(self):
        fail = {"result": 1001}
        self.fake([("account/login", [fail, fail])])
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")

    def test_login_response_without_token_falls_back(self):
        self.fake(
            [
                ("account/login", [{"result": 0, "data": {}}, login_payload()]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
            ] + extras_routes()
        )
        code, out, _ = self.run_cli(["snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)

    def test_day_timestamp_fallbacks(self):
        self.assertEqual(coros.day_timestamp({"happenDay": 20260910}), 20260910)
        self.assertEqual(coros.day_timestamp({"timestamp": 5}), 5)
        self.assertEqual(coros.day_timestamp({"happenDay": "2026-09-10"}), 0)

    def test_day_entry_variants(self):
        self.assertEqual(coros.day_entry({"dayList": []}), {})
        self.assertEqual(coros.day_entry({"data": {"dayList": "x"}}), {})
        no_recovery = [{"happenDay": 20260910, "trainingLoad": 1}, {"happenDay": 20260909}]
        self.assertEqual(coros.day_entry({"data": {"dayList": no_recovery}}), no_recovery[0])

    def test_iso_day_variants(self):
        self.assertEqual(coros.iso_day(20260907.0), "2026-09-07")
        self.assertIsNone(coros.iso_day(20260907.5))
        self.assertEqual(coros.iso_day("2026-09-10"), "2026-09-10")
        self.assertIsNone(coros.iso_day("nope"))
        self.assertIsNone(coros.iso_day("2026091"))

    def test_activity_sort_key_default_zero(self):
        self.assertEqual(coros.activity_sort_key({"name": "x"}), 0)

    def test_last_activity_no_named_key(self):
        name, day = coros.last_activity({"data": {"dataList": [{"date": 20260907}]}})
        self.assertIsNone(name)
        self.assertEqual(day, "2026-09-07")

    def test_last_activity_second_name_key_wins(self):
        name, _ = coros.last_activity({"data": {"dataList": [{"name": "", "workoutName": "W"}]}})
        self.assertEqual(name, "W")

    def test_last_activity_missing_first_list_key(self):
        name, day = coros.last_activity({"data": {"dataList": None, "list": [{"name": "R", "date": 20260907}]}})
        self.assertEqual(name, "R")
        self.assertEqual(day, "2026-09-07")

    def test_last_activity_no_list_keys(self):
        name, day = coros.last_activity({"data": {"workoutList": [{"name": "R"}]}})
        self.assertIsNone(name)
        self.assertIsNone(day)
        name, day = coros.last_activity({"data": None})
        self.assertIsNone(name)
        self.assertIsNone(day)

    def test_last_activity_data_list_direct(self):
        name, day = coros.last_activity({"data": [{"name": "R", "date": 20260907}]})
        self.assertEqual(name, "R")
        self.assertEqual(day, "2026-09-07")

    def test_num_rejects_bool(self):
        self.assertIsNone(coros.num(True))
        self.assertEqual(coros.num(3.0), 3)

    def test_parse_snapshot_stringifies_non_str_activity(self):
        snap = coros.parse_snapshot({}, 123)
        self.assertEqual(snap["activity"], "123")

    def test_resolve_region_from_env(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_REGION": "us"}):
            self.assertEqual(coros.resolve_region(None), "us")
        with unittest.mock.patch.dict(os.environ, {"COROS_REGION": ""}):
            self.assertEqual(coros.resolve_region("us"), "us")
            self.assertEqual(coros.resolve_region("cn"), "eu")

    def test_read_bounded_stops_on_eof(self):
        class EmptyReader:
            def read(self, size=-1):
                return ""

        with unittest.mock.patch.object(sys, "stdin", EmptyReader()):
            self.assertEqual(coros._read_bounded(10), "")

    def test_login_bad_json_body_is_auth_error(self):
        code, out, _ = self.run_cli(["login"], stdin_text="{not json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")

    def test_login_unknown_region_defaults_to_eu(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            self.fake(
                [
                    ("teameuapi.coros.com/account/login", [login_payload()]),
                    ("dayDetail", [day_payload()]),
                    ("activity/query", [activity_payload()]),
                ] + extras_routes()
            )
            payload = json.dumps({"email": "u@e.c", "password": "pw", "region": "cn"})
            code, out, _ = self.run_cli(["login"], stdin_text=payload)
        self.assertEqual(code, 0)
        self.assertIsNone(json.loads(out)["error"])

    def test_login_network_failure_is_network_error(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            self.fake(
                [
                    ("account/login", [urllib.error.URLError("down"), urllib.error.URLError("down")]),
                ]
            )
            payload = json.dumps({"email": "u@e.c", "password": "pw", "region": "eu"})
            code, out, _ = self.run_cli(["login"], stdin_text=payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "network")

    def test_login_write_credentials_failure_is_auth_error(self):
        with unittest.mock.patch.dict(os.environ, {"COROS_EMAIL": "", "COROS_PASSWORD": ""}):
            with (
                unittest.mock.patch.object(coros, "login", return_value=("tok", 7, "zz")),
                unittest.mock.patch.object(coros.os, "makedirs", side_effect=OSError("read-only")),
            ):
                payload = json.dumps({"email": "u@e.c", "password": "pw", "region": "eu"})
                code, out, _ = self.run_cli(["login"], stdin_text=payload)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["error"], "auth")

    def test_parse_interval_bad_value(self):
        self.assertIsNone(coros.parse_interval("abc"))
        self.assertIsNone(coros.parse_interval("0"))

    def test_usage_string(self):
        self.assertIn("usage:", coros.usage())

    def test_main_no_args_returns_usage(self):
        code, _, err = self.run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("usage:", err)
        code, _, err = self.run_cli(["bogus"])
        self.assertEqual(code, 2)
        self.assertIn("usage:", err)
        code, _, err = self.run_cli(["snapshot", "--bogus"])
        self.assertEqual(code, 2)
        self.assertIn("usage:", err)

    def test_region_equals_flag_form(self):
        http = self.fake(
            [
                ("teamapi.coros.com/account/login", [login_payload()]),
                ("dayDetail", [day_payload()]),
                ("activity/query", [activity_payload()]),
            ] + extras_routes()
        )
        code, out, _ = self.run_cli(["snapshot", "--region=us"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hrv"], 42)
        self.assertIn("teamapi.coros.com", [url for url in http.calls if "dayDetail" in url][0])

    def test_watch_invalid_interval_pair_form(self):
        line = default_snapshot(activity="Run")
        with (
            unittest.mock.patch.object(coros, "get_snapshot", return_value=dict(line)),
            unittest.mock.patch("time.sleep", side_effect=[None, KeyboardInterrupt]),
        ):
            code, out, err = self.run_cli(["watch", "--interval", "abc"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 2)
        self.assertIn("invalid --interval", err)

    def test_watch_interval_equals_forms(self):
        line = default_snapshot(activity="Run")
        with (
            unittest.mock.patch.object(coros, "get_snapshot", return_value=dict(line)),
            unittest.mock.patch("time.sleep", side_effect=[None, KeyboardInterrupt]),
        ):
            code, _, err = self.run_cli(["watch", "--interval=5"])
        self.assertEqual(code, 0)
        self.assertNotIn("invalid", err)
        with (
            unittest.mock.patch.object(coros, "get_snapshot", return_value=dict(line)),
            unittest.mock.patch("time.sleep", side_effect=[None, KeyboardInterrupt]),
        ):
            code, out, err = self.run_cli(["watch", "--interval=abc"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 2)
        self.assertIn("invalid --interval", err)

    def test_running_as_main_exits_with_main_return(self):
        out = io.StringIO()
        err = io.StringIO()
        with (
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
            unittest.mock.patch.object(sys, "argv", ["coros.py", "logout"]),
        ):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(_COROS_PATH, run_name="__main__")
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(json.loads(out.getvalue())["error"], "auth")


if __name__ == "__main__":
    unittest.main()
