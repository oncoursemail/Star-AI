"""Every GitHub Action a workflow runs is pinned to a full commit SHA (a moved tag cannot change CI)."""
from pathlib import Path
import re

WORKFLOWS = sorted((Path(__file__).resolve().parents[1] / ".github" / "workflows").glob("*.yml"))


def test_every_action_is_pinned_to_a_commit_with_its_version_noted():
    assert WORKFLOWS
    loose = []
    for workflow in WORKFLOWS:
        for number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            found = re.match(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$", line)
            if not found or found.group(1).startswith("./"):
                continue
            if not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", found.group(1)) or not re.match(r"\s+# v\d", found.group(2)):
                loose.append(f"{workflow.name}:{number}: {line.strip()}")
    assert not loose, "pin actions as owner/repo@<40-hex sha> # vX.Y.Z:\n" + "\n".join(loose)
