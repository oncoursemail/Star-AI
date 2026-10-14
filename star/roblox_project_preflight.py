"""Explicit read-only Roblox source-tree preflight, never Studio verification.

Only scripts accepted by roblox_place.read_tree() are inspected. Static checks
are bounded, advisory, and never execute Luau or alter project files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .luau_lint import lint
from .roblox_api_confusion_preflight import confusion_advisories
from .roblox_api_checker import ApiDump, check_luau_api, load_api_dump
from .roblox_place import BuildError, MAX_FILES, Node, _script, read_tree

MAX_CHECK_SOURCE_BYTES = 20_000
MAX_API_DUMP_BYTES = 20_000_000
MAX_PROJECT_ENTRIES = MAX_FILES * 3
MAX_FILE_FINDINGS = 50
MAX_UNSUPPORTED = 32
LIMITATIONS = (
    "Static source checks only: Luau is not executed or typechecked.",
    "No Roblox Studio, game simulation, asset validation or gameplay verification.",
    "API coverage is limited to types inferred by STAR and entries in the supplied API dump.",
    "Remote trust checks inspect inline handlers in known Script sources; "
    "ModuleScripts and indirect handlers need manual review.",
)


def _invalid(reason: str) -> dict:
    return {
        "schema_version": 1, "status": "invalid", "coverage": "none",
        "files": [], "unsupported_files": [], "findings": 0,
        "error": reason[:240], "limitations": list(LIMITATIONS),
    }


def _source_node(services: list[Node], relative: str) -> tuple[str, str]:
    """Get the *already loaded* source and trusted script class from read_tree."""
    pieces = relative.split("/")
    script = _script(pieces[-1])
    if script is None:
        raise BuildError("Place tree returned a non-Luau path")
    name, script_class = script
    node = next((item for item in services if item.name == pieces[0]), None)
    if node is None:
        raise BuildError("Missing service node in place tree")
    for part in pieces[1:-1]:
        node = next((child for child in node.children if child.name == part), None)
        if node is None:
            raise BuildError("Missing folder node in place tree")
    if name != "init":
        node = next((child for child in node.children if child.name == name), None)
    if node is None or node.source is None or node.class_name != script_class:
        raise BuildError("Source node/class mismatch in place tree")
    return node.source, node.class_name


def _unsupported_paths(source: Path, supported: set[str]) -> tuple[list[str], bool]:
    """Bound enumeration of files read_tree intentionally does not include.

    Does not read file bytes or follow directory links.
    """
    ignored: list[str] = []
    entries = 0
    truncated = False
    for item in source.rglob("*"):
        entries += 1
        if entries > MAX_PROJECT_ENTRIES:
            return ignored, True
        if item.is_symlink() or item.is_file():
            relative = item.relative_to(source).as_posix()
            if relative not in supported:
                if len(ignored) < MAX_UNSUPPORTED:
                    ignored.append(relative)
                else:
                    truncated = True
    return sorted(ignored), truncated


def _api_report(source: str, dump: ApiDump) -> list[dict]:
    results: list[dict] = []
    for found in check_luau_api(source, dump):
        label = found.name if found.class_name is None else f"{found.class_name}.{found.name}"
        suggestion = f" Review {found.suggestion}." if found.suggestion else ""
        results.append({
            "line": found.line, "rule": "api:" + found.rule_id,
            "severity": "warning", "checker": "roblox-api-dump",
            "message": (f"Unknown API name {label}." + suggestion)[:240],
        })
    return results


def _lint_report(source: str, script_class: str) -> list[dict]:
    results: list[dict] = []
    for found in lint(source, safety_checks=True, script_class=script_class,
                      server_security=(script_class == "Script"), roblox_rules=True):
        results.append({
            "line": found.line, "rule": found.rule_id,
            "severity": found.severity, "checker": "luau-static",
            "message": found.message[:240], "suggested_fix": found.suggested_fix[:240],
        })
    return results


def preflight(source: str | Path, *, api_dump: str | Path | None = None,
              api_confusions: bool = False) -> dict:
    """Inspect a bounded script-only Roblox place tree with explicit evidence.

    Return invalid for malformed structures or API dumps; never conflate missing
    API coverage, ignored files, or oversized source with a fully checked tree.
    """
    root = Path(source)
    if api_dump is not None:
        path = Path(api_dump)
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_API_DUMP_BYTES:
                return _invalid("API dump missing, linked or exceeds the size limit")
            dump = load_api_dump(path)
        except (OSError, ValueError, UnicodeError):
            return _invalid("Supplied Roblox API dump is missing or malformed")
    else:
        dump = None
    try:
        services, paths = read_tree(root)
        ignored, truncated_tree = _unsupported_paths(root, set(paths))
        if truncated_tree:
            return _invalid("Project file enumeration exceeds the preflight limit")
        files: list[dict] = []
        total_findings = 0
        confusion_candidates = 0
        confusion_reported = 0
        limited = False
        for relative in paths:
            code, script_class = _source_node(services, relative)
            scopes: list[str] = []
            warnings: list[str] = []
            findings: list[dict] = []
            if len(code.encode("utf-8")) > MAX_CHECK_SOURCE_BYTES:
                warnings.append("Source exceeds 20 KB per-file static-check budget")
            else:
                scopes.extend(("luau-patterns", "lifetime-safety", "roblox-api-rules"))
                if script_class == "Script":
                    scopes.append("inline-server-remote-trust")
                findings.extend(_lint_report(code, script_class))
                if dump is not None:
                    scopes.append("api-names-where-type-is-inferred")
                    findings.extend(_api_report(code, dump))
                else:
                    warnings.append("API names unchecked: no validated dump supplied")
                if api_confusions:
                    scopes.append("api-confusion-spellings-advisory")
                    try:
                        advisories, candidate_count = confusion_advisories(
                            code, dump, limit=max(0, MAX_FILE_FINDINGS - len(findings)))
                    except (OSError, UnicodeError, ValueError):
                        return _invalid("API confusion corpus missing or invalid")
                    confusion_candidates += candidate_count
                    confusion_reported += len(advisories)
                    findings.extend(advisories)
                    if candidate_count:
                        warnings.append(
                            "Possible API-confusion spellings are not confirmed errors; "
                            "custom methods and receiver types need manual review")
                    if candidate_count > len(advisories):
                        warnings.append(
                            "API-confusion advisories truncated by per-file finding limit")
            if script_class == "ModuleScript":
                warnings.append("ModuleScript execution side is unknown; server trust is not verified")
            findings = sorted(findings, key=lambda f: (
                f["line"], f["rule"], f["checker"], f["message"]))
            if len(findings) > MAX_FILE_FINDINGS:
                findings = findings[:MAX_FILE_FINDINGS]
                warnings.append("Findings truncated at 50 entries")
            limited = limited or bool(warnings)
            total_findings += len(findings)
            files.append({
                "file": relative, "script_class": script_class,
                "status": "partial" if warnings else "checked",
                "checked_scope": scopes, "findings": findings,
                "unverified": warnings,
            })
    except BuildError as exc:
        return _invalid(str(exc))
    except (OSError, UnicodeError):
        return _invalid("Cannot read the supplied project source tree")

    if total_findings:
        state = "findings"
    elif ignored:
        state = "unsupported"
    elif limited:
        state = "partial"
    else:
        state = "checked"
    report = {
        "schema_version": 1, "status": state,
        "coverage": "partial" if limited or ignored else "static-only",
        "files": files, "unsupported_files": ignored,
        "findings": total_findings, "error": None, "limitations": list(LIMITATIONS),
        "summary": {
            "checked_files": sum(f["status"] == "checked" for f in files),
            "partial_files": sum(f["status"] == "partial" for f in files),
            "unsupported_files": len(ignored), "findings": total_findings,
        },
    }
    if api_confusions:
        report["summary"].update({
            "api_confusion_candidates": confusion_candidates,
            "api_confusion_advisories": confusion_reported,
            "api_confusion_confirmed_engine_errors": 0,
        })
        report["limitations"].append(
            "API-confusion matches are lexical suggestions, not Roblox errors; "
            "even API-dump-inferred receiver types need human or Studio verification.")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Roblox place source preflight")
    parser.add_argument("source", type=Path, help="place source folder (not an .rbxlx file)")
    parser.add_argument("--api-dump", type=Path, help="local Studio --fullApi JSON dump")
    parser.add_argument(
        "--api-confusions", action="store_true",
        help="opt in to source-linked possible Roblox method spelling advisories")
    args = parser.parse_args(argv)
    report = preflight(args.source, api_dump=args.api_dump,
                       api_confusions=args.api_confusions)
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    if report["status"] == "invalid":
        return 2
    return 0 if report["status"] == "checked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
