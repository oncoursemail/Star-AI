"""The self-builder's refusals, tool replies, clean-up and publishing (star/selfbuild.py), offline.

A throwaway Git repository and a scripted model stand in for the real ones; GitHub is a fake.
test_star.py covers the happy path; these cover what must not happen.
"""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from star.selfbuild import develop, read_source, run_git, write_source


def call(name, arguments, ident="c1"):
    return SimpleNamespace(id=ident, function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))


def reply(text="", calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=calls))])


class ScriptedModel:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []

    async def create(self, **request):
        self.requests.append(json.loads(json.dumps(request["messages"])))
        return self.replies.pop(0)


def client(*replies):
    model = ScriptedModel(replies)
    return SimpleNamespace(chat=SimpleNamespace(completions=model)), model


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "star" / "skills").mkdir(parents=True)
    (root / "docs" / "skills").mkdir(parents=True)
    (root / "star" / "skills" / "__init__.py").write_text("", encoding="utf-8")
    (root / "star" / "skills" / "existing.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    (root / "docs" / "skills" / "existing.md").write_text("# Existing\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    run_git("init", cwd=root)
    run_git("add", ".", cwd=root)
    run_git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "base", cwd=root)
    return root


def worktrees(root):
    return [line for line in run_git("worktree", "list", "--porcelain", cwd=root).splitlines() if line.startswith("worktree ")]


def test_a_folder_that_is_not_a_repository_is_refused(tmp_path):
    fake, model = client()
    with pytest.raises(RuntimeError, match="Initialize and commit"):
        asyncio.run(develop(client=fake, model="m", repository=tmp_path, task="x"))
    assert model.requests == []


def test_uncommitted_changes_are_never_built_on(repo):
    (repo / "star" / "skills" / "existing.py").write_text("def hello():\n    return 2\n", encoding="utf-8")
    fake, model = client()
    with pytest.raises(RuntimeError, match="Commit your pending changes"):
        asyncio.run(develop(client=fake, model="m", repository=repo, task="x"))
    assert model.requests == []


def test_tool_replies_list_read_and_refuse_out_of_scope_writes(repo):
    fake, model = client(
        reply(calls=[call("list_skill_files", {}, "a"), call("read_skill_file", {"path": "star/skills/existing.py"}, "b"),
                     call("read_skill_file", {"path": "star/skills/missing.py"}, "c"),
                     call("write_skill_file", {"path": "tests/test_x.py", "content": "# gone"}, "d"),
                     call("write_skill_file", {"path": "star/skills/broken.py", "content": "def ("}, "e"),
                     call("run_shell", {"command": "dir"}, "f"),
                     call("list_skill_files", {"extra": 1}, "g")]),
        reply("Nothing to change"))
    with pytest.raises(RuntimeError, match="no accepted patch"):
        asyncio.run(develop(client=fake, model="m", repository=repo, task="Look around"))
    tool_replies = {m["tool_call_id"]: json.loads(m["content"]) for m in model.requests[1] if m["role"] == "tool"}
    assert tool_replies["a"]["message"].splitlines() == ["docs/skills/existing.md", "star/skills/existing.py"]
    assert tool_replies["b"]["message"] == "def hello():\n    return 1\n"
    assert tool_replies["c"]["message"] == "File does not exist."
    assert tool_replies["d"] == {"ok": False, "error": "ValueError",
                                 "detail": "Self-build path restricted to star/skills/*.py and docs/skills/*.md"}
    assert tool_replies["e"]["error"] == "SyntaxError"
    assert tool_replies["f"]["error"] == tool_replies["g"]["error"] == "ValueError"
    # The isolated worktree is removed even though the build failed, and the checkout is untouched.
    assert len(worktrees(repo)) == 1
    assert (repo / "tests" / "test_x.py").read_text(encoding="utf-8") == "def test_x():\n    pass\n"
    assert run_git("status", "--porcelain", cwd=repo) == ""


def test_the_build_stops_after_its_turn_budget(repo):
    loop = [reply(calls=[call("list_skill_files", {}, f"t{i}")]) for i in range(3)]
    fake, model = client(*loop)
    with pytest.raises(RuntimeError, match="no accepted patch"):
        asyncio.run(develop(client=fake, model="m", repository=repo, task="x", max_turns=3))
    assert len(model.requests) == 3


class FakeGitHub:
    def __init__(self):
        self.calls = []

    async def work_base(self, branch):
        self.calls.append(("work_base", branch))

    async def create_branch(self, branch):
        self.calls.append(("create_branch", branch))
        return "star/next"

    async def write_branch_file(self, branch, path, data, message):
        self.calls.append(("write", path, data))

    async def open_pr(self, base, branch, title, body):
        self.calls.append(("open_pr", base, branch))
        return {"html_url": "https://github.com/owner/repo/pull/7"}


def test_a_publishing_build_checks_the_base_first_and_opens_a_pull_request_against_it(repo):
    github = FakeGitHub()
    fake, _ = client(
        reply(calls=[call("write_skill_file", {"path": "docs/skills/tween.md", "content": "# Tweens\n"})]),
        reply("Documented tweens"))
    result = asyncio.run(develop(client=fake, model="m", repository=repo, task="Document tweens", github=github))
    assert github.calls[0] == ("work_base", result["branch"])           # before any model call
    assert ("write", "docs/skills/tween.md", b"# Tweens\n") in github.calls
    assert github.calls[-1] == ("open_pr", "star/next", result["branch"])
    assert result["github_pr"] == "https://github.com/owner/repo/pull/7" and result["model_notes"] == ["Documented tweens"]
    assert len(worktrees(repo)) == 1


def test_a_refused_base_stops_the_build_before_the_model_is_asked(repo):
    class Refusing(FakeGitHub):
        async def work_base(self, branch):
            raise RuntimeError("Pull requests may not target main")
    fake, model = client()
    with pytest.raises(RuntimeError, match="may not target main"):
        asyncio.run(develop(client=fake, model="m", repository=repo, task="x", github=Refusing()))
    assert model.requests == [] and len(worktrees(repo)) == 1


def test_reads_and_writes_are_bounded(tmp_path):
    (tmp_path / "star" / "skills").mkdir(parents=True)
    (tmp_path / "star" / "skills" / "big.py").write_text("#" * 80_001, encoding="utf-8")
    with pytest.raises(ValueError, match="oversized"):
        read_source(tmp_path, "star/skills/big.py")
    with pytest.raises(ValueError, match="too long"):
        write_source(tmp_path, "star/skills/new.py", "#" * 40_001)
    assert write_source(tmp_path, "docs/skills/notes.md", "def (") .startswith("Wrote docs/skills/notes.md")


def test_git_failures_are_reported_with_their_message(tmp_path):
    with pytest.raises(RuntimeError, match="Git operation failed"):
        run_git("rev-parse", "HEAD", cwd=tmp_path)
