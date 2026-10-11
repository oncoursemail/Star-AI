"""Symbol-table check: is every class, data type, library, enum, member and enum item of the
engine API reference found by the exact lookup the service offers (`/api-lookup`)?

The list of symbols is read from the reference YAML files in the checkout, not from the index, so
a symbol the chunker dropped or renamed shows up as a miss. Invented names are looked up too: they
must NOT be found.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .quiet import wait_while_locked
from .serve import MAX_SYMBOLS, _SYMBOL, api_lookup
from .store import REFERENCE_GROUPS, connect_readonly

MEMBER_GROUPS = ("constructors", "constants", "properties", "methods", "functions", "events", "callbacks")


def symbols_from_sources(sources_dir: Path, manifest: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """([(group, symbol)], [files that could not be read])."""
    import yaml
    out: list[tuple[str, str]] = []
    unreadable: list[str] = []
    for source in json.loads(manifest.read_text(encoding="utf-8"))["sources"]:
        wait_while_locked(log=lambda message: print(message, file=sys.stderr))
        ref = sources_dir / source["name"] / source["content_root"] / "reference" / "engine"
        if not ref.is_dir():
            continue
        for group in REFERENCE_GROUPS:
            for file in sorted((ref / group).glob("*.yaml")):
                wait_while_locked(log=lambda message: print(message, file=sys.stderr))
                try:
                    data = yaml.safe_load(file.read_text(encoding="utf-8"))
                    name = str(data["name"])
                except Exception:
                    unreadable.append(file.name)
                    continue
                if group == "enums":
                    out.append(("enum", "Enum." + name))
                    for item in data.get("items") or []:
                        if isinstance(item, dict) and item.get("name") is not None:
                            out.append(("enum item", f"Enum.{name}.{item['name']}"))
                    continue
                if group != "globals":   # "Luau globals" is a page title, not a name in code
                    out.append((group[:-1] if group != "classes" else "class", name))
                for member_group in MEMBER_GROUPS:
                    for item in data.get(member_group) or []:
                        full = str(item.get("name") or "") if isinstance(item, dict) else ""
                        if not full:
                            continue
                        full = full.strip()
                        symbol = full if ("." in full or ":" in full or group == "globals") else f"{name}.{full}"
                        out.append((f"{group[:-1] if group != 'classes' else 'class'} {member_group[:-1]}", symbol))
    return out, unreadable


def run(db_path: Path, sources_dir: Path, manifest: Path) -> dict:
    symbols, unreadable = symbols_from_sources(sources_dir, manifest)
    db = connect_readonly(db_path)
    found: dict[str, int] = {}
    total: dict[str, int] = {}
    missing: list[dict] = []
    for start in range(0, len(symbols), MAX_SYMBOLS):
        wait_while_locked(log=lambda message: print(message, file=sys.stderr))
        part = symbols[start:start + MAX_SYMBOLS]
        for (group, symbol), result in zip(part, api_lookup(db, [s for _, s in part])):
            total[group] = total.get(group, 0) + 1
            if result.get("found"):
                found[group] = found.get(group, 0) + 1
            else:
                missing.append({"group": group, "symbol": symbol, "reason": result.get("reason", "")})
    # names that do not exist must not be found
    owners = [s for g, s in symbols if g == "class"][::5]
    enums = [s for g, s in symbols if g == "enum"][::5]
    invented = [f"{o}.Zq{o}Xx" for o in owners] + [f"{o}:Zq{o}Xx" for o in owners] + [f"{e}.ZqNoSuchItemXx" for e in enums] \
        + [f"Zq{o}Xx" for o in owners[:50]]
    wrongly_found = []
    for start in range(0, len(invented), MAX_SYMBOLS):
        wait_while_locked(log=lambda message: print(message, file=sys.stderr))
        part = invented[start:start + MAX_SYMBOLS]
        wrongly_found += [s for s, r in zip(part, api_lookup(db, part)) if r.get("found")]
    db.close()
    n_total, n_found = sum(total.values()), sum(found.values())
    unaddressable = [m for m in missing if not _SYMBOL.match(m["symbol"])]
    return {
        "symbols": n_total, "found": n_found, "coverage": round(n_found / n_total, 5) if n_total else None,
        "by_group": {g: f"{found.get(g, 0)}/{n}" for g, n in sorted(total.items())},
        "unreadable_files": unreadable,
        "invented_names_checked": len(invented), "invented_names_wrongly_found": len(wrongly_found),
        "wrongly_found_examples": wrongly_found[:10],
        "missing_count": len(missing),
        "missing_not_a_code_name": len(unaddressable),    # e.g. the Studio settings labels with spaces
        "missing_real": [m["symbol"] for m in missing if m not in unaddressable][:200],
        "missing": missing,
    }
