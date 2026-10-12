"""Opt-in smoke runs of final answer snippets, on STAR Knowledge only.

Runs happen after any static repair, before the answer is saved/displayed. No
source is rewritten, no local process is started, and sandbox output is never
sent to the model. Only bounded verdicts, line locations and usage are recorded.
A successful smoke run does not establish functional or Roblox correctness.
"""
from __future__ import annotations

import asyncio
import math
import re
from time import monotonic

MAX_BLOCKS = 2
MAX_SOURCE_BYTES = 65_536
RUN_SECONDS = 3.0
MEMORY_MB = 256
# Leave room for the authenticated client's transport and for saving the answer.
REQUEST_SECONDS = 17.0
REVIEW_SECONDS = 40.0
SAVE_RESERVE_SECONDS = 10.0
MARKER = "**Sandbox execution report (STAR):**"
_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)\r?\n?$")
_UNSET = object()


def snippets(answer: str) -> list[str]:
    """Closed, explicitly labelled Lua/Luau fences, not fences inside other fences.

    Unlike the static check's historical extractor, this accepts only the exact
    language label. Source bytes (including whitespace) are preserved.
    """
    result = []
    fence, language, body = "", "", []
    for line in answer.splitlines(keepends=True):
        if not fence:
            match = _OPEN.fullmatch(line)
            if match:
                fence, language = match[1], match[2].strip().lower()
                body = []
        elif re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*\r?\n?", line):
            code = "".join(body)
            if language in ("lua", "luau") and code.strip():
                result.append(code)
            fence, language, body = "", "", []
        else:
            body.append(line)
    return result


def _emit(on_event, event: dict) -> None:
    if on_event is not None:
        try:
            on_event(event)
        except Exception:
            pass


def _record(report: dict) -> dict:
    """Reduce the client's validated protocol to nonsecret, non-instruction data."""
    if (not isinstance(report, dict) or report.get("ran") is not True
            or report.get("executed") is not True or type(report.get("ok")) is not bool
            or report.get("status") != ("pass" if report["ok"] else "fail")
            or type(report.get("exit_code")) is not int
            or type(report.get("timed_out")) is not bool
            or type(report.get("output_limited")) is not bool):
        raise ValueError("Unverified sandbox reply")
    if report["ok"] and (report["exit_code"] != 0 or report["timed_out"]
                         or report["output_limited"] or report.get("error") or report.get("errors")):
        raise ValueError("Inconsistent sandbox verdict")
    usage = report.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Missing sandbox usage")
    for key in ("wall_seconds", "cpu_seconds"):
        value = usage.get(key)
        if type(value) not in (int, float) or not 0 <= value < 3600 or not math.isfinite(value):
            raise ValueError("Invalid sandbox usage")
    for key, maximum in (("max_rss_bytes", 2**50), ("output_bytes", MAX_SOURCE_BYTES)):
        value = usage.get(key)
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError("Invalid sandbox usage")
    locations = []
    errors = report.get("errors")
    if not isinstance(errors, list):
        raise ValueError("Invalid sandbox diagnostics")
    for error in errors[:4]:
        if (not isinstance(error, dict) or error.get("source") not in ("code", "tests")
                or type(error.get("line")) is not int or not 1 <= error["line"] < 1_000_000):
            raise ValueError("Invalid sandbox location")
        locations.append({"source": error["source"], "line": error["line"]})
    category = report.get("error")
    if category not in ("timeout", "output_limit", "resource_limit", "runtime_error"):
        category = "runtime_error"
    return {"ran": True, "ok": report["ok"], "state": "passed" if report["ok"] else "failed",
            "error": "" if report["ok"] else category, "locations": locations,
            "usage": {k: usage[k] for k in ("wall_seconds", "cpu_seconds", "max_rss_bytes", "output_bytes")}}


async def review(answer: str, settings, route, *, started: float | None = None,
                 on_event=None, client=_UNSET) -> tuple[str, list[dict]]:
    """Run at most two independent snippets after explicit consent, never by default.

    Missing/disabled service and transport failures keep the answer and report no
    verified result. A timed-out request may have executed remotely; it is never
    described as a pass or retried. Cancellation propagates. The HTTP worker may
    finish its bounded request after cancellation; the server's deadline remains
    independent and no further snippet is submitted.
    """
    if getattr(settings, "luau_run_before_answer", False) is not True:
        return answer, []
    blocks = snippets(answer)
    if not blocks:
        return answer, []
    deadline = monotonic() + REVIEW_SECONDS
    budget = getattr(route, "task_timeout", 0) or 0
    if started is not None and budget > 0:
        deadline = min(deadline, started + budget - SAVE_RESERVE_SECONDS)
    records = []
    _emit(on_event, {"event": "luau_run_started", "blocks": min(len(blocks), MAX_BLOCKS)})
    for number, code in enumerate(blocks[:MAX_BLOCKS], 1):
        item = {"block": number, "attempted": False, "ran": False, "ok": False, "state": "unavailable"}
        records.append(item)
        if deadline - monotonic() < REQUEST_SECONDS:
            item["state"] = "skipped_budget"
            continue
        try:
            if len(code.encode("utf-8")) > MAX_SOURCE_BYTES or "\x00" in code:
                item["state"] = "skipped_source"
                continue
            if client is _UNSET:
                from .doc_knowledge import client_for
                client = client_for(settings)
            if client is None:
                item["state"] = "not_configured"
                continue
            item["attempted"] = True
            report = await asyncio.wait_for(
                asyncio.to_thread(client.luau_run, code, time_limit_s=RUN_SECONDS, memory_limit_mb=MEMORY_MB),
                timeout=min(REQUEST_SECONDS, max(0.01, deadline - monotonic())))
            item.update(_record(report))
        except asyncio.CancelledError:
            raise
        except UnicodeError:
            item["state"] = "skipped_source"
        except asyncio.TimeoutError:
            # Do not submit a second snippet while this HTTP worker may still be active.
            deadline = monotonic()
        except Exception:
            # Do not expose exception text, endpoints, keys, source, or untrusted VM output.
            pass
    notes = []
    for item in records:
        prefix = f"Code block {item['block']}"
        if item["state"] == "passed":
            notes.append(prefix + " passed a standalone Luau smoke run.")
        elif item["state"] == "failed":
            locations = ", ".join(f"{e['source']} line {e['line']}" for e in item["locations"])
            reason = item["error"].replace("_", " ") + ("; " + locations if locations else "")
            notes.append(prefix + f" failed ({reason}); the code is shown unchanged by the runtime check.")
        elif item["state"] == "skipped_budget":
            notes.append(prefix + " was not run: insufficient time left in this turn.")
        elif item["state"] == "skipped_source":
            notes.append(prefix + " was not run: source exceeds the sandbox's size or encoding limits.")
        elif item["state"] == "not_configured":
            notes.append(prefix + " was not run: STAR Knowledge is off or not configured with a key.")
        else:
            notes.append(prefix + " has no verified execution result: the sandbox request was unavailable or invalid.")
    if len(blocks) > MAX_BLOCKS:
        notes.append(f"{len(blocks) - MAX_BLOCKS} additional Lua/Luau block(s) were not run (two-block limit).")
    notes.append("Blocks run independently with no supplied test body. A pass only means normal completion; "
                 "it does not verify functionality, Roblox services, or Studio behavior.")
    state = "failed" if any(r["state"] == "failed" for r in records) else (
        "passed" if all(r["state"] == "passed" for r in records) and len(blocks) <= MAX_BLOCKS else "incomplete")
    _emit(on_event, {"event": "luau_run_finished", "state": state, "blocks": sum(r["ran"] for r in records)})
    return answer.rstrip() + "\n\n" + MARKER + " " + " ".join(notes) + "\n", records
