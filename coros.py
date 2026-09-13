#!/usr/bin/env python3
"""COROS Training Hub CLI for the omarchy-coros Omarchy plugin.

Logs into the unofficial COROS Training Hub REST API and prints recovery
metrics as JSON for the bar widget to poll:

    coros.py snapshot [--region eu|us]
    coros.py watch [--region eu|us] [--interval N]
    coros.py login    # JSON {email,password,region} on stdin
    coros.py logout   # delete credentials, token cache, cooldown

Credentials come from COROS_EMAIL / COROS_PASSWORD, or from the credentials
file (~/.config/omarchy-coros/credentials, mode 0600) written by the panel
login. The password is stored in that file so 24h token refresh can log in
again; the access token is cached separately in
~/.cache/omarchy-coros/token.json (mode 0600, 24h TTL). After logins fail
on both regions, further polls back off for an hour so a widget polling on
a timer cannot lock the account. One-shot commands print exactly one JSON
object on stdout; watch streams NDJSON.
"""

import hashlib
import json
import os
import stat
import sys
import time
import urllib.parse
import urllib.request

BASES = {
    "eu": "https://teameuapi.coros.com",
    "us": "https://teamapi.coros.com",
}
# Login responses include regionId; 1 is America (teamapi), 3 is Europe.
REGION_IDS = {1: "us", 3: "eu"}
TOKEN_TTL_MS = 24 * 3600 * 1000
REQUEST_TIMEOUT_S = 15
DEFAULT_INTERVAL_S = 30
MAX_BODY_BYTES = 2 * 1024 * 1024
LOGIN_BODY_MAX = 64 * 1024  # {email,password,region} from the panel is tiny
ACTIVITY_NAME_MAX = 120
ALLOWED_HOSTS = frozenset(urllib.parse.urlparse(url).hostname for url in BASES.values())

NULL_SNAPSHOT = {
    "hrv": None,
    "hrvBaseline": None,
    "hrvBandLow": None,
    "hrvBandHigh": None,
    "rhr": None,
    "testRhr": None,
    "load": None,
    "load7d": None,
    "load28d": None,
    "loadRatio": None,
    "loadState": None,
    "loadWeek": None,
    "loadWeekMin": None,
    "loadWeekMax": None,
    "ati": None,
    "cti": None,
    "balance": None,
    "fatigue": None,
    "fatigueState": None,
    "activity": None,
    "activityDay": None,
    "day": None,
    "error": None,  # null | "auth" | "network"
}

# After logins fail on both regions, stop hitting the API for a while so a
# widget polling every 30s cannot lock the account with wrong credentials.
COOLDOWN_S = 3600


class NetworkError(Exception):
    """Transport, timeout, redirect, or unparseable HTTP body — not a login reject."""


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        orig = urllib.parse.urlparse(req.full_url)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme == "https"
            and host in ALLOWED_HOSTS
            and host == (orig.hostname or "").lower()
        ):
            return super().redirect_request(req, fp, code, msg, headers, newurl)
        raise NetworkError("HTTP redirect refused")


_OPENER = urllib.request.build_opener(NoRedirectHandler())


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


def credential_ok(value):
    """Reject values that would break or inject KEY=value lines."""
    if not value or not isinstance(value, str):
        return False
    return not any(ch in value for ch in "\n\r=")


def read_config_file():
    """KEY=value pairs from the credentials file (0600)."""
    values = {}
    try:
        with open(os.path.join(config_dir(), "credentials"), encoding="utf-8") as handle:
            if os.fstat(handle.fileno()).st_mode & 0o077:
                return {}  # refuse group/other-readable credentials
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
    if not credential_ok(email) or not credential_ok(password):
        raise ValueError("credentials contain a newline, CR, or '='")
    if region not in BASES:
        raise ValueError("invalid region")
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
    tmp = path + ".tmp"
    fd = -1
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(tmp, flags, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        # rename(2) replaces the directory entry atomically and never follows
        # a pre-existing symlink at `path`, so a planted link cannot redirect
        # the write and the plaintext password never lands in a foreign file.
        os.replace(tmp, path)
        tmp = None
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def cooldown_file():
    return os.path.join(os.path.dirname(cache_file()), "auth_cooldown")


def cooldown_active():
    try:
        st = os.lstat(cooldown_file())
        if not stat.S_ISREG(st.st_mode):
            return False  # planted symlink/dir is never a cooldown
        age = time.time() - st.st_mtime
        return age >= 0 and age < COOLDOWN_S
    except OSError:
        return False


def trip_cooldown():
    try:
        parent = os.path.dirname(cooldown_file())
        os.makedirs(parent, mode=0o700, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        os.close(os.open(cooldown_file(), flags, 0o600))
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
        token = coerce_token(entry.get("access_token"))
        user_id = coerce_user_id(entry.get("user_id"))
        if not token or user_id is None:
            return None
        if entry.get("region") not in BASES:
            return None
        age_ms = time.time() * 1000 - float(entry.get("timestamp_ms") or 0)
        if age_ms < 0 or age_ms > TOKEN_TTL_MS:
            return None
        entry["access_token"] = token
        entry["user_id"] = user_id
        return entry
    except (OSError, ValueError):
        return None


def coerce_token(value):
    if isinstance(value, (bool, dict, list)) or value is None:
        return None
    text = str(value).strip()
    return text if text else None


def coerce_user_id(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def save_token(access_token, user_id, region):
    access_token = coerce_token(access_token)
    user_id = coerce_user_id(user_id)
    if not access_token or user_id is None or region not in BASES:
        return
    path = cache_file()
    tmp = None
    fd = -1
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
        tmp = path + ".tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(tmp, flags, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        tmp = None
    except OSError as exc:
        eprint("coros.py: could not cache token: " + str(exc))
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def http_open(req, timeout=REQUEST_TIMEOUT_S):
    return _OPENER.open(req, timeout=timeout)


def http_json(method, url, headers, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=dict(headers or {}), method=method)
    try:
        with http_open(req, timeout=REQUEST_TIMEOUT_S) as resp:
            raw = resp.read(MAX_BODY_BYTES + 1)
            if len(raw) > MAX_BODY_BYTES:
                raise NetworkError("response too large")
            return json.loads(raw.decode("utf-8"))
    except NetworkError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, OSError, TimeoutError) as exc:
        raise NetworkError(str(exc)) from exc


def result_code(resp):
    if not isinstance(resp, dict):
        return None
    try:
        return int(resp.get("result"))
    except (TypeError, ValueError):
        return None


def other_region(region):
    return "us" if region == "eu" else "eu"


def region_from_login(data, requested):
    """Prefer the account's Training Hub region over the caller's guess."""
    try:
        mapped = REGION_IDS.get(int(data.get("regionId")))
    except (TypeError, ValueError):
        mapped = None
    return mapped if mapped in BASES else requested


def do_login(email, password, region):
    resp = http_json(
        "POST",
        BASES[region] + "/account/login",
        {"Content-Type": "application/json"},
        {"account": email, "accountType": 2, "pwd": hashlib.md5(password.encode("utf-8"), usedforsecurity=False).hexdigest()},
    )
    code = result_code(resp)
    if code is not None and code != 0:
        message = ""
        if isinstance(resp, dict) and resp.get("message"):
            message = ": " + str(resp.get("message"))
        raise ValueError("login returned result " + str(code) + message)
    data = resp.get("data") if isinstance(resp, dict) else None
    data = data if isinstance(data, dict) else {}
    token = coerce_token(data.get("accessToken"))
    user_id = coerce_user_id(data.get("userId", data.get("userID", data.get("id"))))
    if not token or user_id is None:
        raise ValueError("login response has no access token")
    used = region_from_login(data, region)
    save_token(token, user_id, used)
    return token, user_id, used


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


def day_timestamp(day):
    for key in ("happenDay", "date", "day"):
        try:
            return int(day.get(key))
        except (TypeError, ValueError):
            continue
    ts = num(day.get("timestamp"))
    return int(ts) if ts is not None else 0


def has_recovery(day):
    return (
        num(day.get("avgSleepHrv")) is not None
        or num(day.get("rhr")) is not None
        or num(day.get("testRhr")) is not None
    )


def day_entry(resp):
    data = resp.get("data") if isinstance(resp, dict) else None
    days = data.get("dayList") if isinstance(data, dict) else data
    if days is None and isinstance(resp, dict):
        days = resp.get("dayList")
    if not isinstance(days, list):
        return {}
    days = [day for day in days if isinstance(day, dict)]
    if not days:
        return {}
    days.sort(key=day_timestamp)
    for day in reversed(days):
        if has_recovery(day):
            return day
    return days[-1]


def iso_day(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    if isinstance(value, int):
        raw = str(value)
    else:
        raw = str(value).strip().replace("-", "")
    if len(raw) != 8 or not raw.isdigit():
        return None
    return raw[0:4] + "-" + raw[4:6] + "-" + raw[6:8]


def activity_sort_key(item):
    for key in ("startTime", "endTime", "date"):
        try:
            return int(item.get(key))
        except (TypeError, ValueError):
            continue
    return 0


def last_activity(resp):
    data = resp.get("data") if isinstance(resp, dict) else None
    items = []
    if isinstance(data, dict):
        for key in ("dataList", "list", "activities", "records"):
            if isinstance(data.get(key), list):
                items = [row for row in data[key] if isinstance(row, dict)]
                break
    elif isinstance(data, list):
        items = [row for row in data if isinstance(row, dict)]
    if not items:
        return None, None
    item = max(items, key=activity_sort_key)
    name = None
    for key in ("name", "workoutName", "title", "label"):
        if item.get(key):
            name = str(item[key])[:ACTIVITY_NAME_MAX]
            break
    return name, iso_day(item.get("date"))


def num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    return None


def state(value):
    n = num(value)
    if n is None:
        return None
    n = int(n)
    return n if 1 <= n <= 5 else None


def hrv_band(day):
    raw = day.get("sleepHrvIntervalList")
    if not isinstance(raw, list) or len(raw) < 4:
        return None, None
    return num(raw[2]), num(raw[3])


def week_entry(resp):
    data = resp.get("data") if isinstance(resp, dict) else None
    weeks = data.get("weekList") if isinstance(data, dict) else None
    if not isinstance(weeks, list):
        return {}
    weeks = [week for week in weeks if isinstance(week, dict)]
    return weeks[-1] if weeks else {}


def parse_snapshot(day, activity, activity_day=None, week=None):
    day = day if isinstance(day, dict) else {}
    week = week if isinstance(week, dict) else {}
    if isinstance(activity, str):
        activity = activity[:ACTIVITY_NAME_MAX]
    elif activity is not None:
        activity = str(activity)[:ACTIVITY_NAME_MAX]
    rhr = num(day.get("rhr"))
    test_rhr = num(day.get("testRhr"))
    if rhr is None:
        rhr = test_rhr
    band_low, band_high = hrv_band(day)
    ratio = num(day.get("trainingLoadRatio"))
    return {
        "hrv": num(day.get("avgSleepHrv")),
        "hrvBaseline": num(day.get("sleepHrvBase")),
        "hrvBandLow": band_low,
        "hrvBandHigh": band_high,
        "rhr": rhr,
        "testRhr": test_rhr,
        "load": num(day.get("trainingLoad")),
        "load7d": num(day.get("t7d")),
        "load28d": num(day.get("t28d")),
        "loadRatio": round(ratio, 2) if ratio is not None else None,
        "loadState": state(day.get("trainingLoadRatioState")),
        "loadWeek": num(week.get("trainingLoad")),
        "loadWeekMin": num(week.get("recomendTlMin", day.get("recomendTlMin"))),
        "loadWeekMax": num(week.get("recomendTlMax", day.get("recomendTlMax"))),
        "ati": num(day.get("ati")),
        "cti": num(day.get("cti")),
        "balance": num(day.get("tib")),
        "fatigue": num(day.get("tiredRateNew", day.get("tiredRate"))),
        "fatigueState": state(day.get("tiredRateStateNew")),
        "activity": activity,
        "activityDay": activity_day,
        "day": iso_day(day.get("happenDay") or day.get("date") or day.get("day")),
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
        # Training Hub often leaves today blank until overnight HRV lands;
        # walk the trailing week and keep the newest day that has recovery data.
        detail = get("/analyse/dayDetail/query?" + urllib.parse.urlencode({"startDay": week_ago, "endDay": today}))
        detail_code = result_code(detail)
        if detail_code is not None and detail_code != 0:
            raise NetworkError("dayDetail result " + str(detail_code))
        activity, activity_day = last_activity(
            get(
                "/activity/query?"
                + urllib.parse.urlencode({"size": 10, "pageNumber": 1, "startDay": week_ago, "endDay": today})
            )
        )
        return parse_snapshot(day_entry(detail), activity, activity_day, week_entry(detail))
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


def _read_bounded(limit):
    """Read up to `limit` bytes from stdin without buffering past the cap."""
    chunks = []
    total = 0
    while total < limit:
        chunk = sys.stdin.read(limit - total)
        if not chunk:
            break
        total += len(chunk)
        chunks.append(chunk)
    return "".join(chunks)


def read_login_body():
    """One JSON object from stdin, under a strict byte budget.

    A single line is enough; full-stdin still works. A hostile or stalled
    producer cannot push an unbounded buffer: the first line is read bounded,
    the fallback full read stops at LOGIN_BODY_MAX, and anything oversized is
    treated as an empty body (auth error) rather than buffered.
    """
    raw = sys.stdin.readline(LOGIN_BODY_MAX) if hasattr(sys.stdin, "readline") else ""
    if not str(raw).strip():
        raw = _read_bounded(LOGIN_BODY_MAX)
    if not str(raw).strip() or len(raw) > LOGIN_BODY_MAX:
        return {}
    try:
        body = json.loads(raw or "{}")
    except json.JSONDecodeError:
        body = {}
    return body if isinstance(body, dict) else {}


def cmd_login():
    """Read {email,password,region} JSON from stdin, store 0600 creds, print a snapshot.

    Password never appears on argv. Always one JSON object on stdout, exit 0.
    """
    body = read_login_body()
    email = str(body.get("email") or "").strip()
    password = str(body.get("password") or "")
    region = str(body.get("region") or "eu").strip().lower()
    if region not in BASES:
        region = "eu"
    if not email or not password or not credential_ok(email) or not credential_ok(password):
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        print(json.dumps(snap), flush=True)
        return 0
    try:
        _token, _user_id, used = login(email, password, region)
    except ValueError as exc:
        eprint("coros.py: login failed: " + str(exc))
        trip_cooldown()
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        print(json.dumps(snap), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 - display path always prints valid JSON, never fails
        eprint("coros.py: login failed: " + str(exc))
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "network"
        print(json.dumps(snap), flush=True)
        return 0
    if used not in BASES:
        used = region
    try:
        write_credentials(email, password, used)
        clear_cooldown()
    except (OSError, ValueError) as exc:
        eprint("coros.py: could not write credentials: " + str(exc))
        snap = dict(NULL_SNAPSHOT)
        snap["error"] = "auth"
        print(json.dumps(snap), flush=True)
        return 0
    snap = get_snapshot(used)
    print(json.dumps(snap), flush=True)
    return 0


def cmd_logout():
    """Delete credentials, token cache, and cooldown. Print an auth snapshot.

    Always one JSON object on stdout, exit 0. Never prints the password.
    """
    for path in (os.path.join(config_dir(), "credentials"), cache_file(), cooldown_file()):
        try:
            os.unlink(path)
        except OSError:
            pass
    snap = dict(NULL_SNAPSHOT)
    snap["error"] = "auth"
    print(json.dumps(snap), flush=True)
    return 0


def cmd_snapshot(region_flag):
    print(json.dumps(get_snapshot(resolve_region(region_flag))), flush=True)
    return 0


def cmd_watch(region_flag, interval):
    try:
        while True:
            print(json.dumps(get_snapshot(resolve_region(region_flag))), flush=True)
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
        "       coros.py login   # JSON {email,password,region} on stdin\n"
        "       coros.py logout  # delete credentials, token cache, cooldown"
    )


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("snapshot", "watch", "login", "logout"):
        eprint(usage())
        return 2
    command = argv[0]
    if command == "login":
        return cmd_login()
    if command == "logout":
        return cmd_logout()
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
