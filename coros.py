#!/usr/bin/env python3
"""COROS Training Hub CLI for the omarchy-coros Omarchy plugin.

Logs into the unofficial COROS Training Hub REST API and prints recovery
metrics as JSON for the bar widget to poll:

    coros.py snapshot [--region eu|us]
    coros.py watch [--region eu|us] [--interval N]

Credentials come from COROS_EMAIL / COROS_PASSWORD, or from the setup.sh
credentials file (~/.config/omarchy-coros/credentials, mode 0600); the
password is never stored, only the access token is cached in
~/.cache/omarchy-coros/token.json. After logins fail on both regions,
further polls back off for an hour so a widget polling on a timer cannot
lock the account. One-shot commands print exactly one JSON object on
stdout; watch streams NDJSON.
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
    "error": None,  # null | "auth" | "network"
}

# After logins fail on both regions, stop hitting the API for a while so a
# widget polling every 30s cannot lock the account with wrong credentials.
COOLDOWN_S = 3600


def eprint(msg):
    sys.stderr.write(str(msg) + "\n")
    sys.stderr.flush()


def cache_file():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "omarchy-coros", "token.json")


CREDS_MARK = "# Written by omarchy-coros"


def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "omarchy-coros")


def read_config_file():
    """KEY=value pairs from the setup.sh credentials file (0600)."""
    values = {}
    try:
        with open(os.path.join(config_dir(), "credentials"), encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip("\"'")
    except OSError:
        pass
    return values


def credentials():
    """Env wins; the credentials file (written by the panel or setup.sh) is the fallback."""
    config = read_config_file()
    email = os.environ.get("COROS_EMAIL") or config.get("COROS_EMAIL")
    password = os.environ.get("COROS_PASSWORD") or config.get("COROS_PASSWORD")
    return email or None, password or None


def write_credentials(email, password, region):
    parent = config_dir()
    os.makedirs(parent, mode=0o700, exist_ok=True)
    os.chmod(parent, 0o700)
    path = os.path.join(parent, "credentials")
    body = (
        CREDS_MARK
        + "\nCOROS_EMAIL="
        + email
        + "\nCOROS_PASSWORD="
        + password
        + "\nCOROS_REGION="
        + region
        + "\n"
    ).encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)


def cooldown_file():
    return os.path.join(os.path.dirname(cache_file()), "auth_cooldown")


def cooldown_active():
    try:
        age = time.time() - os.stat(cooldown_file()).st_mtime
        return age >= 0 and age < COOLDOWN_S
    except OSError:
        return False


def trip_cooldown():
    try:
        parent = os.path.dirname(cooldown_file())
        os.makedirs(parent, mode=0o700, exist_ok=True)
        with open(cooldown_file(), "w"):
            pass
    except OSError as exc:
        eprint("coros.py: could not write cooldown marker: " + str(exc))


def clear_cooldown():
    try:
        os.unlink(cooldown_file())
    except OSError:
        pass


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
        clear_cooldown()
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
        "error": None,
    }


def ymd(ts):
    return time.strftime("%Y%m%d", time.localtime(ts))


def get_snapshot(region):
    email, password = credentials()
    if not email or not password:
        eprint("coros.py: no credentials — sign in from the widget, or set COROS_EMAIL and COROS_PASSWORD")
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        return snap
    if cooldown_active():
        eprint("coros.py: login cooling down after failures — sign in from the widget to retry now")
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        return snap
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
    except ValueError as exc:  # login rejected on both regions: back off, don't hammer
        eprint("coros.py: login failed: " + str(exc))
        trip_cooldown()
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        return snap
    except Exception as exc:  # noqa: BLE001 - display path always prints valid JSON, never fails
        eprint("coros.py: snapshot failed: " + str(exc))
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "network"
        return snap


def resolve_region(flag):
    if flag and str(flag).strip().lower() in BASES:
        return str(flag).strip().lower()
    env = (os.environ.get("COROS_REGION") or "").strip().lower()
    if env in BASES:
        return env
    conf = read_config_file().get("COROS_REGION", "").strip().lower()
    return conf if conf in BASES else "eu"


def cmd_login():
    """Read {email,password,region} JSON from stdin, store 0600 creds, print a snapshot.

    Password never appears on argv. Always one JSON object on stdout, exit 0.
    """
    try:
        body = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    email = str(body.get("email") or "").strip()
    password = str(body.get("password") or "")
    region = str(body.get("region") or "eu").strip().lower()
    if region not in BASES:
        region = "eu"
    if not email or not password:
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        print(json.dumps(snap))
        return 0
    try:
        write_credentials(email, password, region)
        clear_cooldown()
    except OSError as exc:
        eprint("coros.py: could not write credentials: " + str(exc))
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        print(json.dumps(snap))
        return 0
    print(json.dumps(get_snapshot(region)))
    return 0


def cmd_snapshot(region_flag):
    print(json.dumps(get_snapshot(resolve_region(region_flag))))
    return 0


def cmd_watch(region_flag, interval):
    try:
        while True:
            print(json.dumps(get_snapshot(resolve_region(region_flag))))
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
    return (
        "usage: coros.py snapshot [--region eu|us]\n"
        "       coros.py watch [--region eu|us] [--interval N]\n"
        "       coros.py login   # JSON {email,password,region} on stdin"
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("snapshot", "watch", "login"):
        eprint(usage())
        return 2
    command = argv[0]
    if command == "login":
        return cmd_login()
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
