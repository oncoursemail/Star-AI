"""Conservative, bounded ModuleScript dependency evidence for explicit preflight.

Only already-loaded roblox_place.Node trees and admitted UTF-8 Luau source are
consulted. No Roblox execution, local file re-read, asset lookup or write.
Unrecognized require forms are *unresolved*, never presumed absent or safe.
"""
from __future__ import annotations

from collections import defaultdict

from .roblox_api_checker import _tokens
from .roblox_place import Node, SERVICES, _script

MAX_CALLS = 256
MAX_CYCLES = 32
LIMITATIONS = (
    "Only direct require(script[.Parent...][.Child...]) and "
    "require(game:GetService('SupportedService')[.Child...]) paths are resolved.",
    "Dynamic requires, alias calls, shadowed identifiers, brackets and paths "
    "outside the admitted source tree require manual review.",
    "Missing targets mean absent from this bounded source tree, not proven "
    "absent at Roblox runtime; no ModuleScript was executed.",
)


def _runtime_source_path(relative: str) -> tuple[str, ...]:
    parts = relative.split("/")
    parsed = _script(parts[-1])
    if parsed is None:
        raise ValueError("Admitted file must be a Luau script")
    name, _ = parsed
    return tuple(parts[:-1] if name == "init" else [*parts[:-1], name])


def _node_index(services: list[Node]) -> dict[tuple[str, ...], Node]:
    nodes: dict[tuple[str, ...], Node] = {}
    def visit(node: Node, path: tuple[str, ...]) -> None:
        nodes[path] = node
        for child in node.children:
            visit(child, (*path, child.name))
    for service in services:
        visit(service, (service.name,))
    return nodes


def _close_call(values: list[str], opening: int) -> int | None:
    depth = 0
    for j in range(opening, len(values)):
        if values[j] == "(":
            depth += 1
        elif values[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return None


def _target(expr: list, current: tuple[str, ...]) -> tuple[tuple[str, ...] | None, str]:
    values = [token.value for token in expr]
    if not expr:
        return None, "empty-require-expression"
    if expr[0].kind == "word" and values[0] == "script":
        path = current
        index = 1
    elif (len(expr) >= 6 and values[:4] == ["game", ":", "GetService", "("]
          and expr[4].kind == "string" and values[5] == ")"):
        service = expr[4].value
        if service not in SERVICES:
            return None, "service-outside-admitted-tree"
        path = (service,)
        index = 6
    else:
        return None, "dynamic-or-unsupported-require"
    while index < len(expr):
        if (index + 1 >= len(expr) or values[index] != "."
                or expr[index + 1].kind != "word"):
            return None, "dynamic-or-unsupported-require"
        name = values[index + 1]
        if name == "Parent":
            if len(path) <= 1:
                return None, "parent-outside-admitted-tree"
            path = path[:-1]
        else:
            path = (*path, name)
        index += 2
    return path, ""


def _calls(source: str):
    """Yield lexical require() candidates with source lines and alias uncertainty."""
    tokens = _tokens(source)
    values = [token.value for token in tokens]
    shadowed = any(
        values[i:i + 2] == ["local", "require"]
        or values[i:i + 3] == ["local", "function", "require"]
        or values[i:i + 2] == ["function", "require"]
        or (values[i] == "require" and values[i + 1:i + 2] == ["="])
        for i in range(len(values))
    )
    aliases = {
        values[i + 1] for i in range(len(values) - 3)
        if values[i] == "local" and tokens[i + 1].kind == "word"
        and values[i + 2:i + 4] == ["=", "require"]
    }
    for i, token in enumerate(tokens):
        if (token.kind != "word" or token.value not in aliases | {"require"}
                or values[i + 1:i + 2] != ["("]
                or (i and values[i - 1] in (".", ":", "function"))):
            continue
        end = _close_call(values, i + 1)
        if end is None:
            yield token.line, None, "unclosed-require-call"
        elif token.value in aliases or shadowed:
            yield token.line, None, "require-alias-or-shadowed"
        else:
            yield token.line, tokens[i + 2:end], ""


def _cycles(module_files: dict[tuple[str, ...], str],
            edges: list[dict]) -> tuple[list[dict], bool]:
    """Report deterministic strongly connected ModuleScript components."""
    adjacency: dict[str, set[str]] = {file: set() for file in module_files.values()}
    for edge in edges:
        if edge["from"] in adjacency and edge["to"] in adjacency:
            adjacency[edge["from"]].add(edge["to"])
    order: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    present: set[str] = set()
    groups: list[tuple[str, ...]] = []

    def visit(name: str) -> None:
        order[name] = low[name] = len(order)
        stack.append(name)
        present.add(name)
        for other in sorted(adjacency[name]):
            if other not in order:
                visit(other)
                low[name] = min(low[name], low[other])
            elif other in present:
                low[name] = min(low[name], order[other])
        if low[name] == order[name]:
            group: list[str] = []
            while True:
                other = stack.pop()
                present.remove(other)
                group.append(other)
                if other == name:
                    break
            if len(group) > 1 or name in adjacency[name]:
                groups.append(tuple(sorted(group)))

    for module in sorted(adjacency):
        if module not in order:
            visit(module)
    groups.sort()
    return [{"modules": list(group)} for group in groups[:MAX_CYCLES]], len(groups) > MAX_CYCLES


def inspect_require_graph(services: list[Node], admitted: dict[str, str],
                          skipped: list[str]) -> dict:
    """Classify up to MAX_CALLS requires in already admitted source.

    A static edge is definite *only within this validated source-tree snapshot*.
    Runtime-created modules and dynamically routed require calls are not ruled out.
    """
    nodes = _node_index(services)
    module_files = {
        _runtime_source_path(path): path for path in admitted
        if _script(path.split("/")[-1])[1] == "ModuleScript"
    }
    # Keep module identity for oversized sources even when their content was
    # excluded from the per-file static check budget.
    for path in skipped:
        if _script(path.split("/")[-1])[1] == "ModuleScript":
            module_files[_runtime_source_path(path)] = path
    edges: list[dict] = []
    missing: list[dict] = []
    unresolved: list[dict] = []
    count = 0
    truncated = False
    for relative, code in sorted(admitted.items()):
        current = _runtime_source_path(relative)
        for line, expression, reason in _calls(code):
            if count >= MAX_CALLS:
                truncated = True
                break
            count += 1
            target, invalid = ((None, reason) if expression is None
                               else _target(expression, current))
            if invalid:
                unresolved.append({"file": relative, "line": line, "reason": invalid})
                continue
            node = nodes.get(target)
            if node is None:
                missing.append({"file": relative, "line": line,
                                "target": "/".join(target), "reason": "missing-from-source-tree"})
            elif node.class_name != "ModuleScript" or target not in module_files:
                missing.append({"file": relative, "line": line,
                                "target": "/".join(target), "reason": "not-an-admitted-ModuleScript"})
            else:
                edges.append({"from": relative, "to": module_files[target], "line": line})
        if truncated:
            break

    cycles, cycles_truncated = _cycles(module_files, edges)
    incomplete = bool(unresolved or skipped or truncated or cycles_truncated)
    status = ("findings" if missing or cycles else
              "partial" if incomplete else "checked-static")
    return {
        "status": status,
        "module_scripts": len(module_files),
        "scanned_sources": len(admitted),
        "scanned_calls": count,
        "edges": edges,
        "cycles": cycles,
        "missing": missing,
        "unresolved": unresolved,
        "skipped_sources": sorted(skipped),
        "truncated": truncated or cycles_truncated,
        "coverage": "partial" if incomplete else "static-only",
        "limitations": list(LIMITATIONS),
    }
