"""Local, explicitly requested deliverable packaging for creator commerce.

The resulting ZIP is always a DRAFT. Hashes prove which bytes were packed,
not whether the art is original, beautiful, licensed, or client-approved.

No seller integration, network access, model calls, order processing, or billing.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any, Mapping
import zipfile

MAX_FILES = 24
MAX_EACH_BYTES = 35 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
ALLOWED_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf", ".psd",
    ".blend", ".fbx", ".obj", ".glb", ".gltf",
    ".lua", ".luau", ".ts", ".tsx", ".js", ".json", ".md",
    ".txt", ".csv", ".zip",
})
FORBIDDEN_PARTS = frozenset({
    "__pycache__", "node_modules", "secrets", "private",
    "credentials", "tokens", ".git", ".env",
})
REVIEW_NOTICE = (
    "STAR DELIVERY PACKET — DRAFT, NOT APPROVED\n\n"
    "This local ZIP has not been checked for design quality, text accuracy, "
    "licensing, client requirements or marketplace policy. Hashes only verify "
    "the packaged bytes. Independently inspect every deliverable, its source "
    "rights and customer-specific requirements before sharing.\n"
    "No Etsy listing, Fiverr delivery, order, message or purchase was made.\n"
)


def _relative(name: object) -> PurePosixPath:
    """Keep archive names portable and reject traversal, hidden and private files."""
    if not isinstance(name, str) or not 1 <= len(name) <= 240:
        raise ValueError("Each selected file needs a relative path of 1–240 characters")
    if "\\" in name or ":" in name or "\x00" in name or name.startswith("/"):
        raise ValueError(f"Unsafe or non-portable file path: {name!r}")
    parts = name.split("/")
    if any(
        not part or part in (".", "..") or part.startswith(".")
        or part.casefold() in FORBIDDEN_PARTS
        for part in parts
    ):
        raise ValueError(f"Unsafe, hidden or private file path: {name!r}")
    path = PurePosixPath(name)
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported deliverable file extension: {path.suffix!r}")
    return path


def _selected_file(root: Path, relative: PurePosixPath) -> bytes:
    """Reject symbolic links, workspace escapes, directories and oversized files."""
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError(f"Cannot include symlink: {relative}")
    try:
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"File outside the authorized workspace: {relative}")
        if resolved.stat().st_size > MAX_EACH_BYTES:
            raise ValueError(f"Selected file exceeds the 35 MiB limit: {relative}")
        with resolved.open("rb") as stream:
            content = stream.read(MAX_EACH_BYTES + 1)
        if len(content) > MAX_EACH_BYTES:
            raise ValueError(f"Selected file exceeds the 35 MiB limit: {relative}")
        return content
    except OSError as exc:
        raise ValueError(f"Cannot safely read selected file: {relative}") from exc


def build_delivery_packet(
    workspace: str | Path,
    spec: Mapping[str, Any],
    output: str | Path,
) -> dict[str, Any]:
    """Assemble a reproducible local ZIP from an explicit list of owner-chosen files.

    The local spec requires channel, brief and files. No claim of approval,
    authentication, income, market demand or delivery is returned.
    """
    if not isinstance(spec, Mapping):
        raise ValueError("Delivery specification must be a JSON object")
    channel = spec.get("channel")
    if channel not in ("etsy", "fiverr"):
        raise ValueError("channel must be 'etsy' or 'fiverr'")
    brief = spec.get("brief")
    if not isinstance(brief, str) or not 5 <= len(brief.strip()) <= 2000:
        raise ValueError("brief must describe the original work in 5–2000 characters")
    names = spec.get("files")
    if not isinstance(names, list) or not 1 <= len(names) <= MAX_FILES:
        raise ValueError("Select between 1 and 24 specific deliverable files")
    paths = [_relative(name) for name in names]
    if len({str(path).casefold() for path in paths}) != len(paths):
        raise ValueError("Duplicate or case-colliding file paths are not allowed")

    try:
        root = Path(workspace).resolve(strict=True)
    except OSError as exc:
        raise ValueError("Authorized workspace does not exist") from exc
    if not root.is_dir():
        raise ValueError("Authorized workspace must be a directory")
    destination = Path(output)
    if destination.suffix.lower() != ".zip":
        raise ValueError("Output must have a .zip extension")
    try:
        parent = destination.parent.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Output parent directory does not exist") from exc
    if not parent.is_dir():
        raise ValueError("Output parent must be a directory")
    target = parent / destination.name
    if target.is_relative_to(root):
        raise ValueError("Save the draft ZIP outside the authorized source workspace")
    if target.exists():
        raise ValueError("Output already exists; existing packages are never overwritten")

    total = 0
    materials: list[tuple[PurePosixPath, bytes]] = []
    records: list[dict[str, object]] = []
    for path in paths:
        raw = _selected_file(root, path)
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Selected files exceed the combined 100 MiB limit")
        materials.append((path, raw))
        records.append({
            "path": str(path),
            "bytes": len(raw),
            "sha256": sha256(raw).hexdigest(),
        })

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "channel": channel,
        "brief": brief.strip(),
        "status": "draft_pending_independent_owner_review",
        "marketplace_actions_executed": False,
        "rights_and_design_verified": False,
        "files": records,
        "review_required": [
            "Originality, licensing and commercial rights",
            "Spelling, visual geometry and output dimensions",
            "AI disclosures and channel-specific listing/service rules",
            "Client requirements, meaningful customization and actual preview",
            "Explicit owner approval before publishing or delivering",
        ],
    }
    meta = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    # Build the archive in the target directory, then create the requested
    # filename exclusively. Never overwrite source data or an existing ZIP.
    with tempfile.TemporaryDirectory(prefix=".star-draft-", dir=parent) as staging:
        archive = Path(staging) / "packet.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
            for name, data in [
                ("MANIFEST.json", meta),
                ("REVIEW_BEFORE_SENDING.txt", REVIEW_NOTICE.encode("utf-8")),
                *((f"deliverables/{path}", raw) for path, raw in materials),
            ]:
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o600 << 16
                zipped.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        created = False
        try:
            with target.open("xb") as written, archive.open("rb") as source:
                created = True
                shutil.copyfileobj(source, written, length=1024 * 1024)
        except OSError as exc:
            if created:
                target.unlink(missing_ok=True)
            raise ValueError("Could not create the local draft package") from exc
    return {
        "classification": "local_draft_packet_not_a_customer_delivery",
        "output": str(target),
        "output_sha256": sha256(target.read_bytes()).hexdigest(),
        "files": records,
        "manifest": manifest,
        "seller_action_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a local, unapproved Etsy/Fiverr asset package")
    parser.add_argument("--workspace", required=True, help="Directory holding chosen original assets")
    parser.add_argument("--spec", required=True, help="JSON file containing channel, brief and file paths")
    parser.add_argument("--out", required=True, help="New ZIP filename outside source workspace")
    args = parser.parse_args(argv)
    try:
        source = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        result = build_delivery_packet(args.workspace, source, args.out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
