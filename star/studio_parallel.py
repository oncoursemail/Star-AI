"""Bounded read-only checks across explicitly selected Roblox Studio MCP instances.

Each Studio keeps its own sequential observation lane, while unrelated Studios
can be inspected concurrently. A successful observation proves only that two
read-only MCP calls returned; it is not a gameplay, visual or performance pass.
No Studio is launched, no Luau runs, and no editing/test-mode tool is called.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
from time import perf_counter

from . import studio

MAX_STUDIOS = 8
MAX_ROUNDS = 20
MAX_PARALLEL = 8
MAX_EVIDENCE_BYTES = 64_000
# Keep this allowlist strictly read-only. This CLI-only observer must never be exposed as a model tool.
READ_TOOLS = frozenset({"list_roblox_studios", "get_studio_state", "get_console_output"})
_ALERT = re.compile(r"\b(?:error|warning|warn)\b", re.IGNORECASE)


class EvidenceError(ValueError):
    """The connector response could not establish a bounded read-only observation."""


@dataclass(frozen=True)
class Observation:
    studio_id: str
    round: int
    status: str  # observed | timed_out | invalid_evidence | unavailable
    elapsed_ms: int
    play_state: str = "unknown"
    console_lines: int = 0
    console_alert_lines: int = 0
    console_sha256: str = ""
    reason: str = ""


@dataclass(frozen=True)
class Batch:
    schema: int
    source: str
    observed_at: str
    target: str
    rounds: int
    max_parallel: int
    peak_concurrency: int
    elapsed_ms: int
    results: tuple[Observation, ...]

    def public(self) -> dict:
        """No original console output, raw exception text or connection command is exported."""
        records = [asdict(item) for item in self.results]
        observed = [item for item in self.results if item.status == "observed"]
        elapsed = sorted(item.elapsed_ms for item in observed)
        p95 = elapsed[max(0, (95 * len(elapsed) + 99) // 100 - 1)] if elapsed else None
        return {"schema": self.schema, "source": self.source,
                "observed_at": self.observed_at, "target": self.target,
                "rounds": self.rounds, "max_parallel": self.max_parallel,
                "peak_concurrency": self.peak_concurrency, "elapsed_ms": self.elapsed_ms,
                "observations": len(records), "observed": len(observed),
                "incomplete": len(records) - len(observed),
                "median_observation_ms": statistics.median(elapsed) if elapsed else None,
                "p95_observation_ms": p95,
                "gameplay_verified": False, "model_trained": False,
                "results": records,
                "learning_candidates": candidate_findings(self)}


def _instance_ids(ids) -> tuple[str, ...]:
    if (not isinstance(ids, (tuple, list)) or not 1 <= len(ids) <= MAX_STUDIOS
            or any(type(item) is not str or not 1 <= len(item) <= 200
                   or item.strip() != item or any(ord(char) < 32 or ord(char) == 127 for char in item)
                   for item in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("Choose 1-8 different, valid Studio IDs explicitly")
    return tuple(ids)


def _read_text(reply, *, empty_ok: bool = False) -> str:
    try:
        value = reply.model_dump(by_alias=True, exclude_none=True) if hasattr(reply, "model_dump") else reply
        if not isinstance(value, dict) or (value.get("isError") is not None
                                            and value.get("isError") is not False):
            raise EvidenceError("connector_rejected")
        parts = value.get("content")
        if not isinstance(parts, list) or len(parts) > 16:
            raise EvidenceError("invalid_content")
        if any(not isinstance(part, dict) or part.get("type") != "text"
               or not isinstance(part.get("text"), str) for part in parts):
            raise EvidenceError("invalid_content")
        text = "\n".join(part["text"] for part in parts)
        if len(text.encode("utf-8")) > MAX_EVIDENCE_BYTES or (not empty_ok and not text.strip()):
            raise EvidenceError("invalid_content")
        return text
    except EvidenceError:
        raise
    except Exception:
        raise EvidenceError("invalid_content") from None


def _play_state(text: str) -> str:
    try:
        data = json.loads(text)
    except ValueError:
        return "unknown"
    state = data.get("playState") if isinstance(data, dict) else None
    return state if state in {"Edit", "Playing", "Run", "Running", "Stopped"} else "unknown"


def candidate_findings(batch: Batch, *, minimum_observations: int = 3) -> list[dict]:
    """Propose recurring warnings for human review; never accept them as memory."""
    if not 2 <= minimum_observations <= MAX_ROUNDS:
        raise ValueError("Invalid finding threshold")
    results = []
    for studio_id in dict.fromkeys(item.studio_id for item in batch.results):
        observations = [item for item in batch.results
                        if item.studio_id == studio_id and item.status == "observed"]
        affected = [item for item in observations if item.console_alert_lines]
        # Re-reading an unchanged console buffer is not independent evidence of a recurring issue.
        if (len(observations) < minimum_observations or len(affected) < 2
                or len({item.console_sha256 for item in affected}) < 2):
            continue
        results.append({"studio_id": studio_id, "status": "candidate",
                        "source": "studio_mcp_read_only", "requires_human_review": True,
                        "description": (f"Console warning/error patterns appeared in {len(affected)} of "
                                        f"{len(observations)} independent read-only observations "
                                        "with changing output snapshots; inspect Studio output "
                                        "before approving a lesson."),
                        "rounds": [item.round for item in affected]})
    return results


async def inspect(session, studio_ids, *, target: str = "local_pc", rounds: int = 1,
                  max_parallel: int = 2, timeout_seconds: float = 12.0) -> Batch:
    """Inspect already-open Studios; only host-supplied selected instance IDs are used.

    A fresh tool and instance discovery occurs before any observation. Each
    instance is serialized across rounds, independent instances can overlap.
    Individual connector errors are contained to that one observation.
    """
    ids = _instance_ids(studio_ids)
    if target not in {"local_pc", "host_launcher"}:
        raise ValueError("Unknown Studio target")
    if type(rounds) is not int or not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError("Rounds must be between 1 and 20")
    if type(max_parallel) is not int or not 1 <= max_parallel <= MAX_PARALLEL:
        raise ValueError("Parallelism must be between 1 and 8")
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not 0.01 <= timeout_seconds <= 120.0):
        raise ValueError("Invalid per-observation timeout")

    tools = await studio.list_tools(session)
    names = {tool["name"] for tool in tools}
    if not READ_TOOLS <= names:
        raise ValueError("Studio MCP has not provided all required read-only tools")
    available = {entry["id"] for entry in await studio.list_studios(session, tool_count=len(tools))}
    if not set(ids) <= available:
        raise ValueError("A selected Studio is unavailable; refresh discovery and choose explicit IDs")

    started = perf_counter()
    semaphore = asyncio.Semaphore(max_parallel)
    lanes = {studio_id: asyncio.Lock() for studio_id in ids}
    active = peak = 0

    async def one(studio_id: str, round_number: int) -> Observation:
        nonlocal active, peak
        # A Studio never runs two observations at once, even across rounds.
        async with lanes[studio_id]:
            async with semaphore:
                active += 1
                peak = max(peak, active)
                tick = perf_counter()
                status, reason, play_state = "observed", "", "unknown"
                console_lines = console_alert_lines = 0
                console_sha256 = ""
                try:
                    async with asyncio.timeout(timeout_seconds):
                        state = _read_text(await session.call_tool(
                            "get_studio_state", arguments={"studio_id": studio_id}))
                        play_state = _play_state(state)
                        console = _read_text(await session.call_tool(
                            "get_console_output", arguments={"studio_id": studio_id}), empty_ok=True)
                        console_sha256 = hashlib.sha256(console.encode("utf-8")).hexdigest()
                        lines = console.splitlines()
                        console_lines = len(lines)
                        console_alert_lines = sum(bool(_ALERT.search(line)) for line in lines)
                except TimeoutError:
                    status, reason = "timed_out", "deadline"
                except EvidenceError as exc:
                    status, reason = "invalid_evidence", str(exc)
                except Exception:
                    status, reason = "unavailable", "connector_error"
                finally:
                    active -= 1
                return Observation(studio_id, round_number, status,
                                   max(0, round((perf_counter() - tick) * 1000)),
                                   play_state, console_lines, console_alert_lines,
                                   console_sha256, reason)

    tasks = [one(studio_id, number) for number in range(1, rounds + 1) for studio_id in ids]
    items = await asyncio.gather(*tasks)
    return Batch(1, "official_roblox_studio_mcp_read_only",
                 datetime.now(timezone.utc).isoformat(), target, rounds, max_parallel,
                 peak, round((perf_counter() - started) * 1000), tuple(items))


def _save_report(path: Path, document: dict) -> None:
    """One explicit destination, atomically replaced; no unreviewed lessons are persisted."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".tmp")
    try:
        staging.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


async def _run_cli(args) -> dict:
    async with studio.connect(target=args.target) as session:
        return (await inspect(session, args.studio_id, target=args.target, rounds=args.rounds,
                              max_parallel=args.max_parallel, timeout_seconds=args.timeout)).public()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only concurrent Studio MCP observations")
    parser.add_argument("--studio-id", action="append", required=True,
                        help="Explicit instance ID from the Studio connector; repeat for each open Studio")
    parser.add_argument("--target", choices=("local_pc", "host_launcher"), default="local_pc")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--max-parallel", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--out", type=Path, help="Optional explicit local JSON evidence destination")
    args = parser.parse_args(argv)
    try:
        document = asyncio.run(_run_cli(args))
        if args.out:
            _save_report(args.out.expanduser(), document)
        print(json.dumps(document, indent=2))
        return 0 if not document["incomplete"] else 1
    except (ValueError, studio.StudioTransportError) as exc:
        print(f"Studio inspection unavailable: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
