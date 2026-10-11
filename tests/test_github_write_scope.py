"""What STAR's own GitHub App may write, and where its pull requests may point. No network."""
import asyncio

import pytest

from star.github_app import GitHubApp, valid_upload_path
from star.selfbuild import skill_path
from star.version import REPO

ALLOWED = (
    "star/skills/tween_helpers.py",
    "star/skills/ui/layout_grid.py",
    "docs/skills/tween_helpers.md",
)

# Everything STAR is judged or limited by, plus the usual escapes.
REFUSED = (
    "tests/test_star.py", "tests/conftest.py", "tests/fixtures/shared_brain_retrieval.json",
    "pyproject.toml", "requirements.txt", "README.md", "main.py",
    "star/agent.py", "star/policy.py", "star/github_app.py", "star/selfbuild.py", "star/frontier_lab.py",
    "star/evals.py", "star/eval_gate.py", "star/eval_runner.py", "star/updates.py", "star/__init__.py",
    "star/skills/__init__.py", "star/skills/notes.md", "star/skills/data.json", "star/skillsx/a.py",
    "evals/roblox_cases.json", "evals/roblox/golden-tasks-v2.json", "evals/results/baseline-v2.json",
    "docs/evals.md", "docs/SECURITY_AND_AUTONOMY.md", "docs/GITHUB_APP_SETUP.md", "docs/skills/run.py",
    "docs/skills/../evals.md", "docs/skills/.hidden.md", "docs/skillsx/a.md",
    ".github/workflows/windows-desktop.yml", ".github/workflows/tests.yml", ".env", ".gitattributes",
    "star/skills/../policy.py", "star/skills/./a.py", "star/skills//a.py", "/star/skills/a.py",
    "star\\skills\\a.py", "star/skills/.secret.py", "star/skills/" + "a" * 200 + ".py", "",
)


@pytest.mark.parametrize("path", ALLOWED)
def test_skill_modules_and_their_pages_may_be_uploaded(path):
    assert valid_upload_path(path)


@pytest.mark.parametrize("path", REFUSED)
def test_tests_gate_policy_build_files_and_workflows_may_not_be_uploaded(path):
    assert not valid_upload_path(path)


@pytest.mark.parametrize("path", ALLOWED + REFUSED)
def test_upload_rule_equals_the_self_builder_rule(path):
    assert valid_upload_path(path) == skill_path(path)


@pytest.mark.parametrize("path", [None, 7, b"star/skills/a.py", ["star/skills/a.py"]])
def test_upload_rule_refuses_values_that_are_not_text(path):
    assert not valid_upload_path(path)


class Recorder(GitHubApp):
    """A GitHubApp whose requests are recorded and answered from a table instead of being sent."""

    def __init__(self, tmp_path, repo=REPO, answers=None, **kwargs):
        key = tmp_path / "fixture.pem"
        key.write_text("not a key: test fixture", encoding="utf-8")
        super().__init__("123", "456", key, repo, **kwargs)
        self.calls = []
        self.answers = answers or {}

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs.get("json")))
        return self.answers.get((method, path), {})


@pytest.mark.parametrize("path", ["tests/test_star.py", "pyproject.toml", "star/policy.py", "docs/evals.md",
                                  ".github/workflows/tests.yml", "star/skills/__init__.py"])
def test_write_branch_file_refuses_before_any_request(tmp_path, path):
    app = Recorder(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(app.write_branch_file("star/demo", path, b"x = 1\n", "test"))
    assert app.calls == []


def test_write_branch_file_still_writes_a_skill_module(tmp_path):
    app = Recorder(tmp_path)
    asyncio.run(app.write_branch_file("star/demo", "star/skills/tween_helpers.py", b"x = 1\n", "test"))
    assert [(m, p) for m, p, _ in app.calls] == [
        ("GET", f"/repos/{REPO}/contents/star/skills/tween_helpers.py"),
        ("PUT", f"/repos/{REPO}/contents/star/skills/tween_helpers.py")]
    assert app.calls[1][2]["branch"] == "star/demo"
