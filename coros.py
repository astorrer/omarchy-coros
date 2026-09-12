#!/usr/bin/env python3
"""COROS Training Hub CLI for the omarchy-coros Omarchy plugin.

Logs into the unofficial COROS Training Hub REST API and prints recovery
metrics as JSON for the bar widget to poll:

    coros.py snapshot [--region eu|us]
    coros.py watch [--region eu|us] [--interval N]

Credentials come from COROS_EMAIL / COROS_PASSWORD and are never stored;
the access token is cached in ~/.cache/omarchy-coros/token.json. One-shot
commands print exactly one JSON object on stdout; watch streams NDJSON.
"""

import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASES = {
    "eu": "https://teameuapi.coros.com",
    "us": "https://teamapi.coros.com",
}
TOKEN_TTL_MS = 24 * 3600 * 1000
REQUEST_TIMEOUT_S = 15
DEFAULT_INTERVAL_S = 30

NULL_SNAPSHOT = {
    "hrv": None,
    "hrvBaseline": None,
    "rhr": None,
    "load": None,
    "sleepH": None,
    "activity": None,
}


def eprint(msg):
    sys.stderr.write(str(msg) + "\n")
    sys.stderr.flush()


def cache_file():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "omarchy-coros", "token.json")


def load_token():
    try:
        with open(cache_file(), "rb") as handle:
            if os.fstat(handle.fileno()).st_mode & 0o077:
                return None  # refuse group/other-readable cache
            entry = json.load(handle)
        if not entry.get("access_token") or entry.get("user_id") is None:
            return None
        if entry.get("region") not in BASES:
            return None
        age_ms = time.time() * 1000 - float(entry.get("timestamp_ms") or 0)
        if age_ms < 0 or age_ms > TOKEN_TTL_MS:
            return None
        return entry
    except (OSError, ValueError):
        return None


def save_token(access_token, user_id, region):
    path = cache_file()
    try:
        parent = os.path.dirname(path)
        os.makedirs(parent, mode=0o700, exist_ok=True)
        os.chmod(parent, 0o700)
        payload = json.dumps(
            {
                "access_token": access_token,
                "user_id": user_id,
                "region": region,
                "timestamp_ms": int(time.time() * 1000),
            }
        ).encode("utf-8")
        # 0o600 at creation: a new file is never world-readable, not even
        # briefly. umask can only narrow these bits, so creation is safe; the
        # fchmod covers a pre-existing file with looser mode (O_TRUNC keeps
        # its mode). Truncation happens before the chmod, but an empty file
        # leaks nothing and the token is only written after.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    except OSError as exc:
        eprint("coros.py: could not cache token: " + str(exc))


def http_json(method, url, headers, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=dict(headers or {}), method=method)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def result_code(resp):
    if not isinstance(resp, dict):
        return None
    try:
        return int(resp.get("result"))
    except (TypeError, ValueError):
        return None


def other_region(region):
    return "us" if region == "eu" else "eu"


def do_login(email, password, region):
    resp = http_json(
        "POST",
        BASES[region] + "/account/login",
        {"Content-Type": "application/json"},
        {"account": email, "accountType": 2, "pwd": hashlib.md5(password.encode("utf-8"), usedforsecurity=False).hexdigest()},
    )
    code = result_code(resp)
    if code is not None and code != 0:
        raise ValueError("login returned result " + str(code))
    data = resp.get("data") if isinstance(resp, dict) else None
    data = data if isinstance(data, dict) else {}
    token = data.get("accessToken")
    user_id = data.get("userId", data.get("userID", data.get("id")))
    if not token or user_id is None:
        raise ValueError("login response has no access token")
    save_token(token, user_id, region)
    return token, user_id, region


def login(email, password, region):
    try:
        return do_login(email, password, region)
    except Exception as exc:  # noqa: BLE001 - any login failure falls back to the other region
        fallback = other_region(region)
        eprint("coros.py: login on " + region + " failed (" + str(exc) + "), trying " + fallback)
        return do_login(email, password, fallback)


def ensure_auth(email, password, region):
    cached = load_token()
    if cached is not None:
        return cached["access_token"], cached["user_id"], cached["region"]
    return login(email, password, region)


def api_get(base, path, token, user_id):
    return http_json(
        "GET",
        base + path,
        {"accessToken": str(token), "yfheader": json.dumps({"userId": user_id})},
    )


def day_entry(resp):
    data = resp.get("data") if isinstance(resp, dict) else None
    days = data.get("dayList") if isinstance(data, dict) else data
    if days is None and isinstance(resp, dict):
        days = resp.get("dayList")
    if isinstance(days, list) and days and isinstance(days[0], dict):
        return days[0]
    return {}


def activity_name(resp):
    data = resp.get("data") if isinstance(resp, dict) else None
    items = []
    if isinstance(data, dict):
        for key in ("dataList", "list", "activities", "records"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    elif isinstance(data, list):
        items = data
    if items and isinstance(items[0], dict):
        for key in ("name", "workoutName", "title", "label"):
            if items[0].get(key):
                return str(items[0][key])
    return None


def num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def parse_snapshot(day, activity):
    day = day if isinstance(day, dict) else {}
    tib = num(day.get("tib"))
    rhr = num(day.get("rhr"))
    if rhr is None:
        rhr = num(day.get("testRhr"))
    return {
        "hrv": num(day.get("avgSleepHrv")),
        "hrvBaseline": num(day.get("sleepHrvBase")),
        "rhr": rhr,
        "load": num(day.get("trainingLoad")),
        "sleepH": round(tib / 60, 1) if tib is not None else None,
        "activity": activity,
    }


def ymd(ts):
    return time.strftime("%Y%m%d", time.localtime(ts))


def get_snapshot(region):
    email = os.environ.get("COROS_EMAIL")
    password = os.environ.get("COROS_PASSWORD")
    if not email or not password:
        eprint("coros.py: set COROS_EMAIL and COROS_PASSWORD")
        return dict(NULL_SNAPSHOT)
    try:
        token, user_id, used = ensure_auth(email, password, region)
        auth = {"token": token, "user_id": user_id, "region": used}

        def get(path):
            resp = api_get(BASES[auth["region"]], path, auth["token"], auth["user_id"])
            if result_code(resp) == 1019:
                auth["token"], auth["user_id"], auth["region"] = login(email, password, auth["region"])
                resp = api_get(BASES[auth["region"]], path, auth["token"], auth["user_id"])
            return resp

        today = ymd(time.time())
        week_ago = ymd(time.time() - 6 * 86400)
        day = day_entry(
            get("/analyse/dayDetail/query?" + urllib.parse.urlencode({"startDay": today, "endDay": today}))
        )
        activity = activity_name(
            get(
                "/activity/query?"
                + urllib.parse.urlencode({"size": 1, "pageNumber": 1, "startDay": week_ago, "endDay": today})
            )
        )
        return parse_snapshot(day, activity)
    except Exception as exc:  # noqa: BLE001 - display path always prints valid JSON, never fails
        eprint("coros.py: snapshot failed: " + str(exc))
        return dict(NULL_SNAPSHOT)


def resolve_region(flag):
    region = str(flag if flag else os.environ.get("COROS_REGION") or "eu").strip().lower()
    return region if region in BASES else None


def cmd_snapshot(region_flag):
    region = resolve_region(region_flag)
    if region is None:
        eprint("coros.py: region must be eu or us")
        print(json.dumps(dict(NULL_SNAPSHOT)))
        return 0
    print(json.dumps(get_snapshot(region)))
    return 0


def cmd_watch(region_flag, interval):
    region = resolve_region(region_flag)
    if region is None:
        eprint("coros.py: region must be eu or us")
    try:
        while True:
            print(json.dumps(dict(NULL_SNAPSHOT) if region is None else get_snapshot(region)))
            sys.stdout.flush()
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    return 0


def parse_interval(raw):
    try:
        value = int(raw)
        if value > 0:
            return value
    except (TypeError, ValueError):
        pass
    return None


def usage():
    return "usage: coros.py snapshot [--region eu|us]\n       coros.py watch [--region eu|us] [--interval N]"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("snapshot", "watch"):
        eprint(usage())
        return 2
    command = argv[0]
    region_flag = None
    interval = DEFAULT_INTERVAL_S
    rest = argv[1:]
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--region" and i + 1 < len(rest):
            region_flag = rest[i + 1]
            i += 2
        elif arg.startswith("--region="):
            region_flag = arg.split("=", 1)[1]
            i += 1
        elif arg == "--interval" and i + 1 < len(rest):
            parsed = parse_interval(rest[i + 1])
            if parsed is None:
                eprint("coros.py: invalid --interval, using default 30")
            else:
                interval = parsed
            i += 2
        elif arg.startswith("--interval="):
            parsed = parse_interval(arg.split("=", 1)[1])
            if parsed is None:
                eprint("coros.py: invalid --interval, using default 30")
            else:
                interval = parsed
            i += 1
        else:
            eprint(usage())
            return 2
    if command == "snapshot":
        return cmd_snapshot(region_flag)
    return cmd_watch(region_flag, interval)


if __name__ == "__main__":
    sys.exit(main())
