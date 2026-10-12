"""Bounded protocol adapter for KnowledgeClient.luau_run; never executes locally."""
from __future__ import annotations

import math

MAX_SOURCE_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
RUN_TIMEOUT = 15.0       # server: at most 2 s queued + 10 s running, plus response margin


def run(client, code: str, *, tests: str = "", time_limit_s: float = 3.0,
        memory_limit_mb: int = 256) -> dict:
    from .doc_knowledge import KnowledgeUnavailable, clean_text

    if not isinstance(code, str) or not code.strip() or not isinstance(tests, str):
        raise ValueError("Luau code must be non-empty text and tests must be text")
    try:
        size = len(code.encode("utf-8")) + len(tests.encode("utf-8"))
    except UnicodeError:
        raise ValueError("Luau source must be valid UTF-8") from None
    if size > MAX_SOURCE_BYTES or "\x00" in code or "\x00" in tests:
        raise ValueError("Luau code and tests must total at most 65536 bytes, without NUL")
    if (type(time_limit_s) not in (int, float) or not 0 < time_limit_s <= 10
            or not math.isfinite(time_limit_s)):
        raise ValueError("Luau time limit must be greater than 0 and at most 10 seconds")
    if type(memory_limit_mb) is not int or not 32 <= memory_limit_mb <= 256:
        raise ValueError("Luau memory limit must be an integer in 32..256 MB")
    data = client._request("POST", "/luau/run", {
        "code": code, "tests": tests, "time_limit_s": time_limit_s,
        "memory_limit_mb": memory_limit_mb}, RUN_TIMEOUT)

    def malformed():
        raise KnowledgeUnavailable("STAR Knowledge sent an unexpected Luau run reply")

    if (data.get("executed") is not True or type(data.get("ok")) is not bool
            or type(data.get("exit_code")) is not int
            or type(data.get("timed_out")) is not bool
            or type(data.get("output_limited")) is not bool
            or not isinstance(data.get("output"), str)
            or not isinstance(data.get("error"), str)
            or not isinstance(data.get("errors"), list)
            or data.get("status") != ("pass" if data["ok"] else "fail")):
        malformed()
    if data["ok"] and (data["exit_code"] != 0 or data["timed_out"] or data["output_limited"]
                       or data["error"] or data["errors"]):
        malformed()
    usage = data.get("usage")
    if not isinstance(usage, dict):
        malformed()
    for field in ("wall_seconds", "cpu_seconds"):
        value = usage.get(field)
        if type(value) not in (int, float) or not 0 <= value < 3600 or not math.isfinite(value):
            malformed()
    for field in ("max_rss_bytes", "output_bytes"):
        value = usage.get(field)
        if type(value) is not int or not 0 <= value <= 2**50:
            malformed()
    if usage["output_bytes"] > MAX_OUTPUT_BYTES:
        malformed()
    errors = []
    for raw in data["errors"][:12]:
        if not isinstance(raw, dict):
            malformed()
        line = raw.get("line")
        if (raw.get("source") not in ("code", "tests") or type(line) is not int
                or not 1 <= line < 1_000_000 or not isinstance(raw.get("message"), str)):
            malformed()
        errors.append({"source": raw["source"], "line": line,
                       "message": clean_text(raw["message"], 500)})
    output = clean_text(data["output"], MAX_OUTPUT_BYTES)
    output = output.encode("utf-8", "replace")[:MAX_OUTPUT_BYTES].decode("utf-8", "ignore")
    return {"ran": True, "executed": True, "ok": data["ok"], "status": data["status"],
            "output": output, "error": clean_text(data["error"], 500), "errors": errors,
            "exit_code": data["exit_code"], "timed_out": data["timed_out"],
            "output_limited": data["output_limited"],
            "usage": {key: usage[key] for key in
                      ("wall_seconds", "cpu_seconds", "max_rss_bytes", "output_bytes")},
            "untrusted": True, "roblox_engine": False}
