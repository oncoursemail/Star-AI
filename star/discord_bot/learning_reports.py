"""Evidence-labeled Night School digests for STAR's optional Discord companion.

This deliberately parses ONLY fixed counters from STAR's local report. Model-
authored lesson text, explanations, paths and other report prose are never
included in a Discord DM. Static/VM checks are not Studio playtests and do not
change model weights. The outbound notifier is opt-in and a separate process.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat

MAX_REPORT_BYTES = 64 * 1024
MAX_IMAGE_BYTES = 6 * 1024 * 1024
MAX_IMAGE_PIXELS = 4096 * 4096
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}\.(?:png|jpg|jpeg)$")


@dataclass(frozen=True)
class LearningSnapshot:
    written: datetime
    attempts: int
    tasks: int
    passed_first: int
    fixed_by_lesson: int
    failed_latest: int
    examples: int
    candidates: int
    promoted_total: int
    retired_total: int
    held_total: int
    baseline_passed: int
    validation_passed: int
    validation_total: int

    def __post_init__(self) -> None:
        if self.written.tzinfo is None or self.written.utcoffset() is None:
            raise ValueError("Report timestamp must have a timezone")
        numbers = (self.attempts, self.tasks, self.passed_first, self.fixed_by_lesson,
                   self.failed_latest, self.examples, self.candidates, self.promoted_total,
                   self.retired_total, self.held_total, self.baseline_passed,
                   self.validation_passed, self.validation_total)
        if any(type(n) is not int or not 0 <= n <= 10_000_000 for n in numbers):
            raise ValueError("Invalid Night School counter")
        if not 1 <= self.validation_total <= 10000:
            raise ValueError("Missing validation task count")
        if self.baseline_passed > self.validation_total or self.validation_passed > self.validation_total:
            raise ValueError("Impossible validation result")
        if self.tasks > self.attempts or self.examples > self.attempts:
            raise ValueError("Impossible practice result")

    @property
    def stamp(self) -> str:
        return self.written.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _count(report: str, expression: str) -> int:
    matches = re.findall(expression, report, flags=re.M)
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous Night School counter")
    return int(matches[0])


def parse_night_school_report(text: str) -> LearningSnapshot:
    """Read the *format*, not untrusted model narrative or suggested lessons."""
    if not isinstance(text, str) or not 1 <= len(text.encode("utf-8")) <= MAX_REPORT_BYTES:
        raise ValueError("Night School report is empty or too large")
    if not text.startswith("# STAR night school: latest numbers\n"):
        raise ValueError("Not a STAR Night School report")
    timestamp = re.findall(r"^written (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) \|", text, re.M)
    if len(timestamp) != 1:
        raise ValueError("Missing or ambiguous Night School timestamp")
    stamp = datetime.fromisoformat(timestamp[0].replace("Z", "+00:00"))
    validation_lines = re.findall(
        r"^- (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ): (\d+)/(\d+) with \d+ lesson\(s\).*$",
        text, flags=re.M)
    if not validation_lines:
        raise ValueError("Night School has no independently checked validation slice")
    if len({int(row[2]) for row in validation_lines}) != 1:
        raise ValueError("Validation task count changed inside report")
    first = validation_lines[0]
    last = validation_lines[-1]
    if datetime.fromisoformat(last[0].replace("Z", "+00:00")) > stamp:
        raise ValueError("Validation timestamp is later than report")
    return LearningSnapshot(
        written=stamp,
        attempts=_count(text, r"^task attempts: (\d+) on \d+ different tasks$"),
        tasks=_count(text, r"^task attempts: \d+ on (\d+) different tasks$"),
        passed_first=_count(text, r"^passed first time: (\d+)$"),
        fixed_by_lesson=_count(text, r"^fixed by a lesson: (\d+)$"),
        failed_latest=_count(text, r"^tasks by their latest attempt: failed (\d+), fixed \d+, passed first \d+$"),
        examples=_count(text, r"^verified worked examples stored: (\d+)$"),
        candidates=_count(text, r"^proposed by the model: \d+ \| kept as candidate \(fixed its task\): (\d+) \| discarded"),
        promoted_total=_count(text, r"^promoted to active: (\d+) \| held back by validation: \d+ \| retired later: \d+$"),
        held_total=_count(text, r"^promoted to active: \d+ \| held back by validation: (\d+) \| retired later: \d+$"),
        retired_total=_count(text, r"^promoted to active: \d+ \| held back by validation: \d+ \| retired later: (\d+)$"),
        baseline_passed=int(first[1]),
        validation_passed=int(last[1]),
        validation_total=int(last[2]),
    )


def read_night_school_report(path: Path) -> LearningSnapshot:
    """A trusted host selects this single path, never a Discord/model message."""
    location = Path(path)
    if not location.is_absolute() or location.is_symlink():
        raise ValueError("Report must be a direct absolute regular file")
    info = location.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT_BYTES:
        raise ValueError("Report must be a small regular file")
    data = location.read_bytes()
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError("Report became too large during read")
    return parse_night_school_report(data.decode("utf-8"))


def _fresh(s: LearningSnapshot, now: datetime) -> bool:
    return (now.tzinfo is not None and now.utcoffset() is not None
            and 0 <= (now - s.written).total_seconds() <= 7 * 86400)


def significant_change(old: LearningSnapshot | None, new: LearningSnapshot) -> bool:
    """No repeated 'I learned' DM merely because a paused report was rewritten."""
    if old is None:
        return True
    if new.written <= old.written:
        return False
    if new.examples > old.examples or new.fixed_by_lesson > old.fixed_by_lesson:
        return True
    return new.validation_total == old.validation_total and new.validation_passed > old.validation_passed


def format_learning_digest(
    current: LearningSnapshot, *,
    previous: LearningSnapshot | None = None,
    now: datetime | None = None,
) -> str:
    """Bounded truthful Discord text; never pass arbitrary report prose to a DM."""
    now = now or datetime.now(timezone.utc)
    if not _fresh(current, now):
        raise ValueError("Night School report is stale or from the future")
    if previous is not None and not significant_change(previous, current):
        raise ValueError("No new evidence since previous digest")
    lines = ["**STAR · Verified practice update**",
             "Scope: Luau static checks and simulated VM tests; **not Roblox Studio**.",
             f"Report: {current.stamp}"]
    if previous is None:
        lines.extend((
            f"Checked worked examples (cumulative): **{current.examples}**",
            f"Tasks passed on first attempt: **{current.passed_first}**",
            f"Lesson-assisted repairs (cumulative): **{current.fixed_by_lesson}**",
        ))
    else:
        lines.extend((
            f"New checked examples: **+{max(0, current.examples - previous.examples)}**",
            f"New lesson-assisted repairs: **+{max(0, current.fixed_by_lesson - previous.fixed_by_lesson)}**",
        ))
    lines.extend((
        f"Latest practice failures: **{current.failed_latest}**",
        f"Unseen validation: **{current.validation_passed}/{current.validation_total}** "
        f"(original baseline {current.baseline_passed}/{current.validation_total})",
        f"Candidate lessons awaiting promotion: **{current.candidates}**",
        "The model's weights have **not** changed. No claim of improved general intelligence "
        "is made without an independently repeated validation gain.",
    ))
    return "\n".join(lines)[:1900]


@dataclass(frozen=True)
class ApprovedVisual:
    """Explicit operator-owned artifact approval, never generated by a model."""
    report_stamp: str
    filename: str
    digest: str
    approval: bool

    @classmethod
    def load(cls, path: Path) -> "ApprovedVisual":
        location = Path(path)
        if not location.is_absolute() or location.is_symlink():
            raise ValueError("Visual manifest must be an absolute regular file")
        info = location.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise ValueError("Invalid visual manifest")
        manifest = json.loads(location.read_text(encoding="utf-8"))
        if type(manifest) is not dict or set(manifest) != {
            "format", "report_stamp", "filename", "sha256", "approved_for_owner_dm"
        } or manifest["format"] != "star-owner-approved-visual-v1":
            raise ValueError("Unrecognized visual approval manifest")
        return cls(manifest["report_stamp"], manifest["filename"],
                   manifest["sha256"], manifest["approved_for_owner_dm"])

    def verified_bytes(self, *, report: LearningSnapshot, directory: Path) -> bytes:
        if self.approval is not True or self.report_stamp != report.stamp:
            raise PermissionError("Screenshot not explicitly approved for this report")
        if not isinstance(self.filename, str) or not _SAFE_NAME.fullmatch(self.filename):
            raise ValueError("Unsafe screenshot filename")
        if not isinstance(self.digest, str) or not _SHA.fullmatch(self.digest):
            raise ValueError("Invalid screenshot SHA256")
        base = Path(directory)
        if not base.is_absolute() or not base.is_dir() or base.is_symlink():
            raise ValueError("Artifact directory must be an approved absolute directory")
        location = base / self.filename
        if location.is_symlink():
            raise ValueError("Linked screenshot is forbidden")
        info = location.stat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_IMAGE_BYTES:
            raise ValueError("Screenshot must be a bounded regular file")
        data = location.read_bytes()
        if (len(data) > MAX_IMAGE_BYTES or
                hashlib.sha256(data).hexdigest() != self.digest):
            raise ValueError("Screenshot changed after approval")
        # Image validation is defensive; no arbitrary path or render from a bot command.
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in {"PNG", "JPEG"} or img.width * img.height > MAX_IMAGE_PIXELS:
                raise ValueError("Screenshot must be PNG/JPEG with safe dimensions")
            img.verify()
        return data
