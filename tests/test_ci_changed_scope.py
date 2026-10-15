"""The docs-only CI shortcut skips tests only for documents that no code or test reads."""
from pathlib import Path

import pytest

from scripts import ci_changed_scope as scope

ROOT = Path(__file__).resolve().parents[1]


def repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_x.py").write_text("README = open('docs/WEBSITE_RELEASE_CHECKLIST.md')\n")
    (tmp_path / "docs/agents").mkdir(parents=True)
    (tmp_path / "docs/agents/free-notes.md").write_text("notes\n")
    return tmp_path


@pytest.mark.parametrize("changed", [["docs/agents/free-notes.md"], ["docs/agents/free-notes.md", "CONTRIBUTING.md"]])
def test_unread_documents_only_may_skip(tmp_path, changed):
    docs_only, _ = scope.decide(repo(tmp_path), changed)
    assert docs_only


@pytest.mark.parametrize("changed", [
    [],                                                   # unknown change: run everything
    ["docs/agents/free-notes.md", "star/app.py"],         # any code
    ["docs/WEBSITE_RELEASE_CHECKLIST.md"],                # read by a test (full path)
    ["docs/other/WEBSITE_RELEASE_CHECKLIST.md"],          # same file name as a read document
    ["docs/lessons/roblox-character-lifecycle.md"],       # the app reads lessons
    ["star/skill_packs/x/SKILL.md"],                      # packaged data
    ["frontend/README.md"], ["tests/fixtures/a.md"], ["evals/reference/HO-1.md"],
    ["docs/diagram.png"], ["../outside.md"],
])
def test_everything_else_runs_the_tests(tmp_path, changed):
    docs_only, _ = scope.decide(repo(tmp_path), changed)
    assert not docs_only


def test_real_repository_readme_is_read_by_tests():
    assert not scope.decide(ROOT, ["README.md"])[0]


def test_main_fails_towards_running_everything(tmp_path, capsys):
    assert scope.main(["--root", str(tmp_path), "--files", str(tmp_path / "missing.txt")]) == 0
    assert capsys.readouterr().out.strip() == "docs_only=false"
    listed = tmp_path / "changed.txt"
    listed.write_text("docs/agents/free-notes.md\n")
    assert scope.main(["--root", str(repo(tmp_path)), "--files", str(listed)]) == 0
    assert capsys.readouterr().out.strip() == "docs_only=true"
