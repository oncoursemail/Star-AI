"""Validate prospective documentation corpora without fetching or indexing them.

The live Roblox index still uses corpora.json. This catalogue is intentionally
separate: future importers must request ingestion rights explicitly.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SOURCES_DIR = Path(__file__).resolve().parent.parent / "sources"
SCHEMA_VERSION = 1
_MODES = {"ingest-allowed", "link-only"}
_KINDS = {"git", "website", "zip"}
# This is an explicit policy gate, not a conclusion that every page in a repo is licensed alike.
_PERMITTED_TEXT_LICENCES = frozenset({"CC-BY-4.0", "CC-BY-SA-2.5-or-later", "PSF-2.0", "MIT", "CC-BY-3.0"})
_CADENCES = {"weekly", "monthly", "quarterly", "per-release", "as-published"}
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class ManifestError(ValueError):
    """A corpus manifest is invalid or cannot be used for indexing."""


class IngestionNotAllowed(ManifestError):
    """The corpus has not granted the rights needed for this ingestion."""


def _fields(value: object, keys: set[str], where: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ManifestError(f"{where}: expected fields {', '.join(sorted(keys))}")
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ManifestError(f"{where}: expected non-empty text")
    return value


def _url(value: object, where: str) -> str:
    text = _text(value, where)
    try:
        parsed = urlsplit(text)
        host = parsed.hostname
    except ValueError as exc:
        raise ManifestError(f"{where}: invalid URL") from exc
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or any(ord(char) < 32 or ord(char) == 127 for char in text)):
        raise ManifestError(f"{where}: expected a public HTTPS URL without credentials")
    return text


def _sections(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ManifestError(f"{where}: expected at least one section")
    for item in value:
        _text(item, where)
        if ".." in item or "\\" in item:
            raise ManifestError(f"{where}: invalid section selector")
    if len(value) != len(set(value)):
        raise ManifestError(f"{where}: duplicate section")
    return value


def _rights(value: object, where: str) -> dict:
    fields = {"id", "url", "redistribution_allowed", "attribution", "conditions", "evidence_url", "evidence_quote"}
    rights = _fields(value, fields, where)
    for key in ("id", "attribution", "conditions", "evidence_quote"):
        _text(rights[key], f"{where}.{key}")
    _url(rights["url"], f"{where}.url")
    _url(rights["evidence_url"], f"{where}.evidence_url")
    if type(rights["redistribution_allowed"]) is not bool:
        raise ManifestError(f"{where}.redistribution_allowed: expected boolean")
    return rights


def validate_manifest(value: object) -> dict:
    """Reject incomplete, ambiguous or self-contradictory manifests, offline."""
    fields = {"schema_version", "name", "title", "mode", "source", "licence",
              "include", "exclude", "expected_size", "update_cadence", "citation"}
    doc = _fields(value, fields, "manifest")
    if type(doc["schema_version"]) is not int or doc["schema_version"] != SCHEMA_VERSION:
        raise ManifestError("manifest.schema_version: unsupported version")
    if not _NAME.fullmatch(_text(doc["name"], "manifest.name")):
        raise ManifestError("manifest.name: expected a lowercase slug")
    _text(doc["title"], "manifest.title")
    if not isinstance(doc["mode"], str) or doc["mode"] not in _MODES:
        raise ManifestError("manifest.mode: expected ingest-allowed or link-only")

    source = _fields(doc["source"], {"kind", "url", "revision", "content_root", "public_base"}, "source")
    if not isinstance(source["kind"], str) or source["kind"] not in _KINDS:
        raise ManifestError("source.kind: expected git, zip or website")
    _url(source["url"], "source.url")
    _text(source["revision"], "source.revision")
    _text(source["content_root"], "source.content_root")
    _url(source["public_base"], "source.public_base")

    licence = _fields(doc["licence"], {"text", "code_samples"}, "licence")
    _rights(licence["text"], "licence.text")
    _rights(licence["code_samples"], "licence.code_samples")
    if doc["mode"] == "ingest-allowed" and (
            not licence["text"]["redistribution_allowed"]
            or licence["text"]["id"] not in _PERMITTED_TEXT_LICENCES):
        raise ManifestError("manifest.mode: text rights do not permit ingestion")

    _sections(doc["include"], "include")
    _sections(doc["exclude"], "exclude")
    if set(doc["include"]) & set(doc["exclude"]):
        raise ManifestError("manifest: sections cannot be both included and excluded")

    size = _fields(doc["expected_size"], {"unit", "min", "max", "note"}, "expected_size")
    if size["unit"] != "documents" or type(size["min"]) is not int or type(size["max"]) is not int:
        raise ManifestError("expected_size: expected document count range")
    if size["min"] < 1 or size["max"] < size["min"]:
        raise ManifestError("expected_size: invalid range")
    _text(size["note"], "expected_size.note")

    cadence = _fields(doc["update_cadence"], {"frequency", "note"}, "update_cadence")
    if not isinstance(cadence["frequency"], str) or cadence["frequency"] not in _CADENCES:
        raise ManifestError("update_cadence.frequency: invalid cadence")
    _text(cadence["note"], "update_cadence.note")

    citation = _fields(doc["citation"], {"format", "example"}, "citation")
    fmt = _text(citation["format"], "citation.format")
    if "{title}" not in fmt or "{url}" not in fmt:
        raise ManifestError("citation.format: must include title and URL placeholders")
    _text(citation["example"], "citation.example")
    return doc


def require_ingestion_rights(manifest: dict, *, include_code_samples: bool = False) -> None:
    """Gate future text/code importers before they read or store source content."""
    validate_manifest(manifest)
    if manifest["mode"] != "ingest-allowed" or not manifest["licence"]["text"]["redistribution_allowed"]:
        raise IngestionNotAllowed(f"{manifest['name']}: link-only; document text must not be ingested")
    if include_code_samples and not manifest["licence"]["code_samples"]["redistribution_allowed"]:
        raise IngestionNotAllowed(f"{manifest['name']}: code sample redistribution is not permitted")


def load_manifest(path: Path, *, for_ingestion: bool = False, include_code_samples: bool = False) -> dict:
    """Parse metadata only; ingest mode rejects link-only and disallowed samples."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot load manifest {Path(path).name}: {type(exc).__name__}") from exc
    validate_manifest(doc)
    if for_ingestion:
        require_ingestion_rights(doc, include_code_samples=include_code_samples)
    return doc


def load_manifests(directory: Path = SOURCES_DIR, *, for_ingestion: bool = False,
                   include_code_samples: bool = False) -> list[dict]:
    """Return a deterministic catalogue; never silently skip invalid or restricted sources."""
    found: list[dict] = []
    names: set[str] = set()
    directory = Path(directory)
    if not directory.is_dir():
        raise ManifestError(f"{directory.name}: no manifest directory")
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ManifestError(f"{directory.name}: no corpus manifests")
    for path in paths:
        doc = load_manifest(path, for_ingestion=for_ingestion, include_code_samples=include_code_samples)
        if doc["name"] != path.stem or doc["name"] in names:
            raise ManifestError(f"{path.name}: duplicate or mismatched corpus name")
        found.append(doc)
        names.add(doc["name"])
    return found
