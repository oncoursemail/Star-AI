"""What time it is: one short per-turn line for the model, and the read-only `star_clock` tool.

Every chat turn (desktop, CLI, Discord) gets `now_line()` appended at the END of the final user
message (agent.volatile_context / live_context.discord_live), never in the system prefix: the
prefix stays byte-identical turn after turn so the model server can reuse its prompt cache.

The line carries the owner's PC local date, time and zone, the same instant in UTC, and the STAR
Server's clock when it is known to differ (read from the HTTP `Date` header of a reply from that
server; see `observe_server_date`). Nothing here touches the network.

`star_clock` answers what a model cannot do reliably in its head: the time in another zone,
converting a time between zones, adding or subtracting days/hours, and the span between dates.
IANA zone names (America/Chicago) need the `tzdata` package on Windows; fixed offsets (UTC+05:30)
and the PC's own zone always work.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from email.utils import parsedate_to_datetime
import json
import re
import threading
import time

# How far the server clock may drift before the line mentions it, and how long an observation counts.
SERVER_SKEW_SECONDS = 90
SERVER_OBSERVATION_TTL = 3600.0

_OFFSET = re.compile(r"^(?:UTC|GMT)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE)
_ALIASES = {"utc": "UTC", "gmt": "UTC", "z": "UTC", "zulu": "UTC"}
_LOCAL_WORDS = {"", "local", "here", "owner", "pc", "my time", "mine"}

_lock = threading.Lock()
_server: dict = {}   # {"offset": seconds server-minus-PC, "seen": monotonic time}


def _abbreviation(name: str) -> str:
    """'Central Daylight Time' (Windows' long names) -> 'CDT'; short names are kept."""
    name = (name or "").strip()
    if " " in name:
        letters = "".join(word[0] for word in name.split() if word[:1].isalpha())
        return letters.upper() or name
    return name


def _offset_text(moment: datetime) -> str:
    offset = moment.utcoffset() or timedelta(0)
    total = int(offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"UTC{sign}{total // 3600:02d}:{total % 3600 // 60:02d}"


def local_now(now: datetime | None = None) -> datetime:
    """The PC's local time, zone-aware."""
    if now is None:
        return datetime.now().astimezone()
    return now if now.tzinfo is not None else now.astimezone()


def observe_server_date(header_value: str, *, now: float | None = None, monotonic=time.monotonic) -> None:
    """Remember the STAR Server's clock from one HTTP `Date` header (RFC 7231). Never raises."""
    try:
        server_time = parsedate_to_datetime(str(header_value))
    except (TypeError, ValueError, IndexError):
        return
    if server_time is None or server_time.tzinfo is None:
        return
    local = time.time() if now is None else now
    with _lock:
        _server["offset"] = server_time.timestamp() - local
        _server["seen"] = monotonic()


def server_offset(*, monotonic=time.monotonic) -> float | None:
    """Seconds the server clock is ahead of the PC, if observed within the last hour."""
    with _lock:
        if "offset" not in _server or monotonic() - _server["seen"] > SERVER_OBSERVATION_TTL:
            return None
        return float(_server["offset"])


def forget_server_clock() -> None:
    with _lock:
        _server.clear()


def now_line(now: datetime | None = None, *, offset: float | None = None) -> str:
    """'Now: Tuesday 2026-10-13 13:05 CDT, the owner's local time (UTC-05:00; 18:05 UTC).'

    `offset` is the server-minus-PC clock difference in seconds (default: the last observed one);
    the server time is added only when it differs by more than SERVER_SKEW_SECONDS.
    """
    local = local_now(now)
    zone = _abbreviation(local.tzname() or "")
    utc = local.astimezone(timezone.utc)
    # Local time first and named as the owner's: a small model otherwise tends to answer in UTC.
    line = (f"Now: {local:%A %Y-%m-%d %H:%M} {zone}, the owner's local time ({_offset_text(local)}; "
            f"{utc:%H:%M} UTC).")
    skew = server_offset() if offset is None else offset
    if skew is not None and abs(skew) > SERVER_SKEW_SECONDS:
        server = utc + timedelta(seconds=skew)
        line += f" STAR Server clock reads {server:%Y-%m-%d %H:%M} UTC ({skew / 60:+.0f} min)."
    return line


def sent_line(created: str, *, offset: float | None = 0.0) -> str:
    """`now_line` for the moment a stored message was written (ISO 8601, as the chat store saves it).

    A replayed earlier turn carries the same line it was first sent with, so the request starts with
    the bytes the server already read. offset=0 leaves the server-clock note out (it was not stored);
    offset=None adds it when the clocks differ now. '' for an unreadable stamp.
    """
    try:
        moment = datetime.fromisoformat(str(created))
    except (TypeError, ValueError):
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return now_line(moment.astimezone(), offset=offset)


# -- star_clock tool ------------------------------------------------------------------------------

# A prompt that needs zone conversion or date arithmetic. "What time is it?" alone does not: the
# per-turn line already answers it. Kept narrow so unrelated prompts keep their exact tool list.
_CLOCK_PROMPT = re.compile(
    r"\btime\s+(?:is\s+it\s+)?in\s+\w|\btime\s*zones?\b|\btimezones?\b|\b(?:utc|gmt)\s*[+-]\s*\d|"
    r"\b(?:convert|what\s+is)\s+\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?\s+(?:\w+\s+)?(?:to|in)\b|"
    r"\bhow\s+(?:many|long)\s+(?:days?|weeks?|hours?|minutes?|months?|years?)\s+(?:until|till|since|from|between|ago|left|before)\b|"
    r"\b(?:days?|weeks?|hours?)\s+(?:until|till|since|from\s+now|ago)\b|"
    r"\bwhat\s+(?:day|date)\s+(?:is|was|will)\b|\b(?:days?|weeks?|months?)\s+from\s+(?:now|today)\b|"
    r"\bcountdown\b|\bday\s+of\s+the\s+week\b",
    re.IGNORECASE)


def wants_clock(prompt: str) -> bool:
    return bool(_CLOCK_PROMPT.search(prompt or ""))


TOOL = {
    "name": "star_clock",
    "description": ("Current date/time in any time zone, convert a time between zones, add or subtract "
                    "days/hours from a date, or count the time between two dates. Read-only. Zones: IANA "
                    "names (Europe/London), city names (Tokyo), UTC, or offsets like UTC+05:30; omit for "
                    "the owner's local zone."),
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["now", "convert", "add", "diff"],
                       "description": "now: time in zones; convert: a time from one zone to others; "
                                      "add: start + amount; diff: span from start to end"},
            "zones": {"type": "array", "items": {"type": "string"}, "maxItems": 8,
                      "description": "Target zones for now/convert (default: local)"},
            "time": {"type": "string", "description": "For convert/add/diff: ISO date or datetime "
                                                      "(2026-10-13, 2026-10-13T15:30) or HH:MM today"},
            "from_zone": {"type": "string", "description": "Zone that `time`/`end` are written in (default local)"},
            "end": {"type": "string", "description": "For diff: the end date/datetime (default now)"},
            "days": {"type": "number"}, "weeks": {"type": "number"},
            "hours": {"type": "number"}, "minutes": {"type": "number"},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
}


class ClockError(ValueError):
    pass


def _city_zone(name: str) -> str | None:
    try:
        from zoneinfo import available_timezones
        zones = available_timezones()
    except Exception:
        return None
    wanted = name.strip().replace(" ", "_").lower()
    for zone in sorted(zones):
        if zone.lower() == wanted or zone.rsplit("/", 1)[-1].lower() == wanted:
            return zone
    return None


def resolve_zone(name: str | None) -> tuple[tzinfo, str]:
    """(tzinfo, label) for a zone name; '' / 'local' is the PC's zone."""
    text = str(name or "").strip()
    if text.lower() in _LOCAL_WORDS:
        local = local_now()
        return local.tzinfo, f"{_abbreviation(local.tzname() or '')} (owner's PC)"
    if len(text) > 64:
        raise ClockError("Zone name too long")
    text = _ALIASES.get(text.lower(), text)
    if text == "UTC":
        return timezone.utc, "UTC"
    match = _OFFSET.match(text)
    if match and (text[:1] in "+-" or text[:3].upper() in ("UTC", "GMT")):
        sign, hours, minutes = match.group(1), int(match.group(2)), int(match.group(3) or 0)
        if hours > 14 or minutes >= 60:
            raise ClockError(f"Offset out of range: {text}")
        delta = timedelta(hours=hours, minutes=minutes) * (1 if sign == "+" else -1)
        return timezone(delta), _offset_text(datetime.now(timezone(delta)))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(text), text
    except Exception:
        pass
    city = _city_zone(text)
    if city:
        from zoneinfo import ZoneInfo
        return ZoneInfo(city), city
    raise ClockError(f"Unknown time zone '{text}'. Use an IANA name like Europe/London or an offset like "
                     "UTC+05:30 (IANA names need the tzdata package on Windows).")


def _parse_time(text: str, zone: tzinfo, now: datetime) -> datetime:
    value = str(text or "").strip()
    if not value:
        return now.astimezone(zone)
    clock = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([ap]\.?m\.?)?", value, re.IGNORECASE)
    if clock:
        hour, minute, second = int(clock.group(1)), int(clock.group(2)), int(clock.group(3) or 0)
        meridiem = (clock.group(4) or "").lower().replace(".", "")
        if meridiem:
            if not 1 <= hour <= 12:
                raise ClockError(f"Bad 12-hour time: {value}")
            hour = hour % 12 + (12 if meridiem == "pm" else 0)
        if hour > 23 or minute > 59 or second > 59:
            raise ClockError(f"Bad time: {value}")
        today = now.astimezone(zone)
        return today.replace(hour=hour, minute=minute, second=second, microsecond=0)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(value), datetime.min.time())
        except ValueError as exc:
            raise ClockError(f"Could not read the date/time '{value}'; use ISO like 2026-10-13T15:30") from exc
    return parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed


def _describe(moment: datetime, label: str) -> dict:
    return {"zone": label, "time": moment.strftime("%A %Y-%m-%d %H:%M"), "utc_offset": _offset_text(moment)}


def run_clock(args: dict, *, now: datetime | None = None) -> dict:
    """Execute one star_clock call; returns a JSON-able dict. Raises ClockError on bad input."""
    if not isinstance(args, dict):
        raise ClockError("Arguments must be an object")
    action = args.get("action")
    current = local_now(now)
    if action not in ("now", "convert", "add", "diff"):
        raise ClockError("action must be one of now, convert, add, diff")
    zones = args.get("zones") or [""]
    if not isinstance(zones, list) or len(zones) > 8:
        raise ClockError("zones must be a list of at most 8 names")
    source_zone, source_label = resolve_zone(args.get("from_zone"))
    if action == "now":
        out = []
        for name in zones:
            zone, label = resolve_zone(name)
            out.append(_describe(current.astimezone(zone), label))
        return {"action": "now", "results": out}
    if action == "convert":
        start = _parse_time(args.get("time", ""), source_zone, current)
        out = []
        for name in zones:
            zone, label = resolve_zone(name)
            out.append(_describe(start.astimezone(zone), label))
        return {"action": "convert", "from": _describe(start, source_label), "results": out}
    if action == "add":
        start = _parse_time(args.get("time", ""), source_zone, current)
        amounts = {}
        for key in ("weeks", "days", "hours", "minutes"):
            value = args.get(key, 0) or 0
            if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value) > 1_000_000:
                raise ClockError(f"{key} must be a number")
            amounts[key] = value
        try:
            result = start + timedelta(**amounts)
        except OverflowError as exc:
            raise ClockError("Result is out of range") from exc
        return {"action": "add", "from": _describe(start, source_label), "added": amounts,
                "result": _describe(result, source_label)}
    start = _parse_time(args.get("time", ""), source_zone, current)
    end = _parse_time(args.get("end", ""), source_zone, current)
    span = end - start
    seconds = int(span.total_seconds())
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    return {"action": "diff", "from": _describe(start, source_label), "to": _describe(end, source_label),
            "span": f"{sign}{seconds // 86400} days {seconds % 86400 // 3600} h {seconds % 3600 // 60} min",
            "total_days": round(span.total_seconds() / 86400, 4),
            "total_hours": round(span.total_seconds() / 3600, 2)}


def tool_result(args: dict, *, now: datetime | None = None) -> dict:
    """MCP-shaped result for agent.execute: never raises."""
    try:
        return {"isError": False, "content": [{"type": "text", "text": json.dumps(
            run_clock(args, now=now), ensure_ascii=False)}]}
    except ClockError as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
