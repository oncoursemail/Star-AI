"""Stamp an honest local package SHA; never invent a GitHub Actions run.

Run from a clean checkout. Ignored build output does not change Git cleanliness.
The optional expected SHA prevents a checkout switch between build stages.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class BuildStampError(RuntimeError):
    """A bounded, nonsecret build precondition failed."""


def _git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments], capture_output=True,
            text=True, encoding="utf-8", errors="strict", timeout=15,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as error:
        raise BuildStampError("Git source verification failed.") from error
    if result.returncode != 0 or len(result.stdout) > 100_000:
        raise BuildStampError("Git source verification failed.")
    return result.stdout.strip()


def verified_commit(root: Path, expected_commit: str | None = None) -> str:
    root = Path(root).resolve(strict=True)
    if expected_commit is not None and not _COMMIT.fullmatch(expected_commit):
        raise BuildStampError("Expected source SHA must be a full lowercase Git SHA.")
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise BuildStampError("Build source must be the exact Git checkout root.")
    commit = _git(root, "rev-parse", "HEAD")
    if not _COMMIT.fullmatch(commit):
        raise BuildStampError("Git did not return a full source SHA.")
    if expected_commit is not None and commit != expected_commit:
        raise BuildStampError("Build source changed between stages.")
    if _git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise BuildStampError("Build source is dirty; review and commit changes first.")
    return commit


def stamp(root: Path, expected_commit: str | None = None) -> str:
    root = Path(root).resolve(strict=True)
    commit = verified_commit(root, expected_commit)
    directory = root / "star"
    if not directory.is_dir() or directory.resolve() != directory:
        raise BuildStampError("Build metadata directory must be inside this checkout.")
    payload = {
        "schema": 1, "source_commit": commit, "head_commit": commit,
        "build_event": "local_build", "run_id": "",
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=directory,
            prefix=".build-info-", suffix=".part", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, directory / "build-info.json")
        temporary = None
    except OSError as error:
        raise BuildStampError("Build metadata could not be written.") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return commit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expected-commit")
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        commit = (verified_commit(arguments.root, arguments.expected_commit)
                  if arguments.check_only else stamp(arguments.root, arguments.expected_commit))
    except (BuildStampError, OSError) as error:
        parser.exit(1, f"{error}\n" if isinstance(error, BuildStampError)
                    else "Build source could not be verified.\n")
    print(commit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
