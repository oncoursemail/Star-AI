"""Optional, bounded Luau CLI second opinion for STAR's existing static checks.

Runs only an explicitly opted-in local binary, not generated Luau source.
Offline, no automatic installation and no model or Roblox server connection.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import warnings

from .luau_lint import Finding

ENV_VAR = "STAR_LUAU_ANALYZE"
TOOLS_DIR_VAR = "STAR_LUAU_TOOLS_DIR"
PINNED_VERSION = "0.691"
MAX_SOURCE_BYTES = 20_000
MAX_OUTPUT_BYTES = 48_000
MAX_FINDINGS = 20
TIMEOUT_SECONDS = 6
_STAGED_NAME = "star-check.luau"
_DIAGNOSTIC = re.compile(
    r"^(?P<file>.*?)\((?P<line>[0-9]{1,6}),(?P<column>[0-9]{1,6})\): "
    r"(?P<kind>[A-Za-z][A-Za-z0-9]*): (?P<message>[^\r\n]*)$"
)
_UNKNOWN_SYMBOL = re.compile(
    r"""^Unknown (?:global|type) ['"](?P<name>[A-Za-z_][A-Za-z_0-9]*)['"]""",
    re.IGNORECASE,
)
# The standalone CLI has no Roblox-specific engine type definitions.
_ROBLOX_SYMBOLS = frozenset({
    "game", "script", "workspace", "plugin", "shared", "task", "Enum",
    "Instance", "Vector3", "CFrame", "Color3", "UDim", "UDim2", "RaycastParams",
    "OverlapParams", "BasePart", "Player", "Players", "Model", "Humanoid",
    "Animation", "RBXScriptSignal", "RBXScriptConnection", "TweenInfo",
    "NumberSequence", "ColorSequence", "BrickColor", "Region3",
})
_notified: set[str] = set()
_notice_lock = threading.Lock()


def enabled(environ=None) -> bool:
    source = os.environ if environ is None else environ
    return source.get(ENV_VAR, "").strip().lower() == "on"


def locate_analyzer(*, tools_root: Path | None = None) -> str | None:
    """Prefer an existing pinned user-tools binary, then PATH; never download."""
    root = tools_root
    if root is None:
        value = os.environ.get(TOOLS_DIR_VAR, "").strip()
        root = Path(value) if value else None
    if root is not None:
        name = "luau-analyze.exe" if os.name == "nt" else "luau-analyze"
        candidate = Path(root) / ("luau-" + PINNED_VERSION) / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("luau-analyze")


def _notice_once(key: str, message: str) -> None:
    with _notice_lock:
        if key in _notified:
            return
        _notified.add(key)
    warnings.warn(message, RuntimeWarning, stacklevel=3)


def parse_diagnostics(output: str) -> list[Finding]:
    """Parse only diagnostics for STAR's staged Luau script."""
    findings: list[Finding] = []
    for raw in output.splitlines():
        match = _DIAGNOSTIC.fullmatch(raw)
        if match is None or Path(match["file"]).name != _STAGED_NAME:
            continue
        kind = match["kind"]
        message = match["message"]
        symbol = _UNKNOWN_SYMBOL.match(message)
        if kind == "TypeError" and symbol and symbol["name"] in _ROBLOX_SYMBOLS:
            continue
        if kind == "SyntaxError":
            fix, severity = "Repair Luau syntax before running the script.", "error"
        elif kind == "TypeError":
            fix, severity = "Review the type mismatch in Studio's Luau checker.", "warning"
        else:
            fix, severity = "Review this Luau lint diagnostic and confirm in Studio.", "review"
        clean = "".join(c if c.isprintable() else " " for c in message)[:220]
        findings.append(Finding(
            "luau-analyze-" + kind.lower(), int(match["line"]),
            kind + ": " + clean, fix, severity))
        if len(findings) >= MAX_FINDINGS:
            break
    return sorted(set(findings), key=lambda f: (f.line, f.rule_id, f.message))


@dataclass(frozen=True)
class AnalyzerEvidence:
    """One native source-analysis outcome; never a Roblox Studio verdict."""

    status: str
    findings: tuple[Finding, ...] = ()
    engine_symbols_ignored: int = 0


def analyze_evidence(source: str, *, tools_root: Path | None = None) -> AnalyzerEvidence:
    """Check a source using an already installed standalone Luau analyzer.

    No code execution or network access. No source, tool path, output stderr,
    or project file path is copied into the returned evidence.
    """
    if not isinstance(source, str):
        raise TypeError("source must be str")
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        return AnalyzerEvidence("skipped")
    binary = locate_analyzer(tools_root=tools_root)
    if not binary:
        return AnalyzerEvidence("unavailable")
    try:
        with tempfile.TemporaryDirectory(prefix="star-luau-check-") as temporary:
            (Path(temporary) / _STAGED_NAME).write_text(source, encoding="utf-8")
            environment = {"PATH": os.environ.get("PATH", ""),
                           "HOME": temporary, "USERPROFILE": temporary,
                           "TEMP": temporary, "TMP": temporary}
            for name in ("SYSTEMROOT", "WINDIR"):
                if name in os.environ:
                    environment[name] = os.environ[name]
            result = subprocess.run(
                [binary, "--mode=strict", _STAGED_NAME],
                cwd=temporary, env=environment,
                capture_output=True, encoding="utf-8", errors="replace",
                text=True, check=False, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return AnalyzerEvidence("timed_out")
    except (OSError, UnicodeError):
        return AnalyzerEvidence("failed")

    if (type(result.returncode) is not int or result.returncode not in (0, 1)
            or not isinstance(result.stderr, str)
            or not isinstance(result.stdout, str)):
        return AnalyzerEvidence("malformed")
    output = result.stderr
    if (len(output.encode("utf-8")) > MAX_OUTPUT_BYTES
            or len(result.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES):
        return AnalyzerEvidence("truncated")
    if result.stdout.strip():
        return AnalyzerEvidence("malformed")
    diagnostic_rows = 0
    error_rows = 0
    suppressed = 0
    max_line = source.count("\n") + 1
    for line in output.splitlines():
        if not line.strip():
            continue
        match = _DIAGNOSTIC.fullmatch(line)
        if match is None and diagnostic_rows:
            # luau-analyze 0.691 prints multi-line TypeErrors ("caused by:",
            # tab-indented types) after a diagnostic header line.
            continue
        if (match is None or Path(match["file"]).name != _STAGED_NAME
                or not 1 <= int(match["line"]) <= max_line
                or int(match["column"]) < 1):
            return AnalyzerEvidence("malformed")
        diagnostic_rows += 1
        error_rows += match["kind"] in {"SyntaxError", "TypeError"}
        symbol = _UNKNOWN_SYMBOL.match(match["message"])
        if (match["kind"] == "TypeError" and symbol
                and symbol["name"] in _ROBLOX_SYMBOLS):
            suppressed += 1
    if diagnostic_rows > MAX_FINDINGS:
        # The existing parser caps output; never disguise incomplete results.
        return AnalyzerEvidence("truncated", tuple(parse_diagnostics(output)), suppressed)
    if result.returncode == 0:
        # luau-analyze prints lint warnings (e.g. LocalUnused) and still exits 0;
        # only syntax/type errors with a zero exit are inconsistent evidence.
        if error_rows:
            return AnalyzerEvidence("malformed")
        if not diagnostic_rows:
            return AnalyzerEvidence("checked")
        return AnalyzerEvidence("diagnostics", tuple(parse_diagnostics(output)), suppressed)
    if not diagnostic_rows:
        return AnalyzerEvidence("malformed")
    findings = tuple(parse_diagnostics(output))
    return AnalyzerEvidence("diagnostics" if findings else "engine_limited",
                            findings, suppressed)


def analyze(source: str, *, tools_root: Path | None = None) -> list[Finding]:
    """Retain legacy advisory behavior; callers needing evidence use analyze_evidence."""
    evidence = analyze_evidence(source, tools_root=tools_root)
    if evidence.status == "skipped":
        _notice_once("size", "Luau analyzer skipped oversized code; static checks remain available.")
    elif evidence.status == "unavailable":
        _notice_once("missing", "Luau analyzer is missing; using STAR's static checks only.")
    elif evidence.status in {"failed", "timed_out"}:
        _notice_once("failure", "Luau analyzer could not run; using STAR's static checks only.")
    elif evidence.status in {"truncated", "malformed"}:
        _notice_once("failure", "Luau analyzer returned an invalid result; using static checks only.")
    return list(evidence.findings)
