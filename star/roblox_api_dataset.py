"""Bundled Roblox engine API names and signatures.

``data/roblox_api/roblox_api.json`` is a compact copy of Roblox's official Studio Full API dump, regenerated with
``scripts/refresh_roblox_api.py`` (its ``StarSource`` block records the Studio version, download URL and the
SHA-256 of the original dump). It keeps the Full API dump schema, so ``star.roblox_api_checker.load_api_dump``
reads it directly; this module adds lookups the checker does not need: inherited members, signatures,
deprecation with the preferred replacement, services and enum items.

Offline and read-only: no network, no Studio, no code execution. The data describes one Studio build; members
added later are unknown to it, so "not found" means "not in that build", not "does not exist".

    python -m star.roblox_api_dataset WorldRoot.Raycast BodyVelocity Enum.PathStatus
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import sys

DATA = Path(__file__).resolve().parents[1] / "data" / "roblox_api" / "roblox_api.json"
_ROOTS = ("<<<ROOT>>>", "")


@dataclass(frozen=True)
class Member:
    class_name: str
    name: str
    kind: str  # Property, Function, Event or Callback
    tags: frozenset[str]
    value_type: str | None
    parameters: tuple[tuple[str, str, object], ...]  # (name, type, default or None)
    returns: tuple[str, ...]
    preferred: str | None
    security: object

    @property
    def deprecated(self) -> bool:
        return "Deprecated" in self.tags

    def signature(self) -> str:
        if self.kind in ("Function", "Callback"):
            params = ", ".join(f"{n}: {t}" + (f" = {d}" if d not in (None, "") else "") for n, t, d in self.parameters)
            result = ", ".join(self.returns) or "()"
            separator = ":" if self.kind == "Function" else "."
            return f"{self.class_name}{separator}{self.name}({params}) -> {result}"
        if self.kind == "Event":
            params = ", ".join(f"{n}: {t}" for n, t, _ in self.parameters)
            return f"{self.class_name}.{self.name}: RBXScriptSignal({params})"
        return f"{self.class_name}.{self.name}: {self.value_type}"


@dataclass(frozen=True)
class ApiClass:
    name: str
    superclass: str
    tags: frozenset[str]
    members: dict[str, Member]
    preferred: str | None

    @property
    def deprecated(self) -> bool:
        return "Deprecated" in self.tags

    @property
    def service(self) -> bool:
        return "Service" in self.tags

    @property
    def creatable(self) -> bool:
        return "NotCreatable" not in self.tags


@dataclass(frozen=True)
class Dataset:
    classes: dict[str, ApiClass]
    enums: dict[str, frozenset[str]]
    source: dict

    def ancestry(self, class_name: str) -> list[str]:
        """The class and its superclasses, nearest first; empty for an unknown class."""
        chain: list[str] = []
        current = class_name
        while current in self.classes and current not in chain:
            chain.append(current)
            current = self.classes[current].superclass
        return chain

    def member(self, class_name: str, name: str) -> Member | None:
        """A member of the class, including inherited ones (the nearest definition wins)."""
        for current in self.ancestry(class_name):
            found = self.classes[current].members.get(name)
            if found is not None:
                return found
        return None

    def members(self, class_name: str) -> dict[str, Member]:
        result: dict[str, Member] = {}
        for current in reversed(self.ancestry(class_name)):
            result.update(self.classes[current].members)
        return result

    def find_member(self, name: str) -> list[Member]:
        """Every class that defines a member with this name (not inherited copies)."""
        return [cls.members[name] for cls in self.classes.values() if name in cls.members]

    @property
    def services(self) -> frozenset[str]:
        return frozenset(name for name, cls in self.classes.items() if cls.service)

    def deprecation(self, class_name: str, member: str | None = None) -> str | None:
        """None when not deprecated; otherwise the preferred replacement, or "" when the dump names none."""
        target = self.classes.get(class_name) if member is None else self.member(class_name, member)
        if target is None or not target.deprecated:
            return None
        return target.preferred or ""

    def describe(self, query: str) -> str:
        """Human-readable answer for ``Class``, ``Class.Member`` or ``Enum.Name``; raises KeyError if unknown."""
        if query.startswith("Enum."):
            name = query[5:]
            if name not in self.enums:
                raise KeyError(query)
            return f"Enum.{name}: " + ", ".join(sorted(self.enums[name]))
        if "." in query or ":" in query:
            class_name, _, name = query.replace(":", ".").partition(".")
            found = self.member(class_name, name)
            if found is None:
                raise KeyError(query)
            note = ""
            if found.deprecated:
                note = f"  [Deprecated; use {found.preferred}]" if found.preferred else "  [Deprecated]"
            return found.signature() + note
        cls = self.classes.get(query)
        if cls is None:
            raise KeyError(query)
        flags = [flag for flag, on in (("service", cls.service), ("not creatable", not cls.creatable),
                                         ("deprecated", cls.deprecated)) if on]
        replacement = f"; use {cls.preferred}" if cls.deprecated and cls.preferred else ""
        return (f"{cls.name} < {' < '.join(self.ancestry(cls.name)[1:]) or '(root)'}"
                f" ({', '.join(flags) or 'creatable'}{replacement}); {len(self.members(cls.name))} members")


def _type_name(value: object) -> str:
    return value.get("Name", "?") if isinstance(value, dict) else str(value)


def _parse(data: dict) -> Dataset:
    if not isinstance(data, dict) or data.get("Version") != 1 or not isinstance(data.get("Classes"), list) \
            or not isinstance(data.get("Enums"), list):
        raise ValueError("not a Roblox API dataset")
    classes: dict[str, ApiClass] = {}
    for entry in data["Classes"]:
        name = entry["Name"]
        members: dict[str, Member] = {}
        for raw in entry["Members"]:
            returns = raw.get("ReturnType")
            members[raw["Name"]] = Member(
                class_name=name,
                name=raw["Name"],
                kind=raw["MemberType"],
                tags=frozenset(raw.get("Tags", ())),
                value_type=_type_name(raw["ValueType"]) if "ValueType" in raw else None,
                parameters=tuple((p["Name"], _type_name(p.get("Type")), p.get("Default"))
                                 for p in raw.get("Parameters", ())),
                returns=tuple(_type_name(r) for r in returns) if isinstance(returns, list) else (
                    (_type_name(returns),) if returns is not None and _type_name(returns) != "null" else ()),
                preferred=raw.get("PreferredDescriptorName"),
                security=raw.get("Security"),
            )
        classes[name] = ApiClass(name, entry["Superclass"], frozenset(entry.get("Tags", ())), members,
                                 entry.get("PreferredDescriptorName"))
    for cls in classes.values():
        if cls.superclass not in classes and cls.superclass not in _ROOTS:
            raise ValueError(f"unknown superclass {cls.superclass} of {cls.name}")
    enums = {e["Name"]: frozenset(item["Name"] for item in e["Items"]) for e in data["Enums"]}
    return Dataset(classes, enums, dict(data.get("StarSource") or {}))


def load(path: str | Path | None = None) -> Dataset:
    """Load the bundled dataset (cached) or another file in the same schema."""
    if path is None:
        return _bundled()
    return _parse(json.loads(Path(path).read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _bundled() -> Dataset:
    return _parse(json.loads(DATA.read_text(encoding="utf-8")))


def api_dump():
    """The bundled data as the ``ApiDump`` that ``star.roblox_api_checker.check_luau_api`` expects."""
    from .roblox_api_checker import load_api_dump
    return load_api_dump(DATA)


def main(argv: list[str] | None = None) -> int:
    queries = sys.argv[1:] if argv is None else argv
    if not queries:
        print("usage: python -m star.roblox_api_dataset Class | Class.Member | Enum.Name ...", file=sys.stderr)
        return 2
    dataset = load()
    status = 0
    for query in queries:
        try:
            print(dataset.describe(query))
        except KeyError:
            print(f"{query}: not in the bundled API data (Studio {dataset.source.get('studioVersion', '?')})")
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
