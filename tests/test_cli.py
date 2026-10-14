"""The `star` command line (main.py): its safety guards, stores and exit behaviour, all offline.

ROOT is pointed at a temporary folder so no command touches the checkout's .local, runs or
.env; the model, Studio and GitHub are replaced by fakes, so nothing leaves the machine.
"""
import argparse
import asyncio
import json
import sys

import pytest
from PIL import Image

from star import cli


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    for name in ("STAR_MODEL", "STAR_BASE_URL", "STAR_SANDBOX_STUDIO_ID", "STAR_MAX_MODEL_CALLS",
                 "STAR_CONTEXT_CHARS", "STAR_GITHUB_PRIVATE_KEY_FILE"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def run(**fields):
    return asyncio.run(cli.main(argparse.Namespace(**fields)))


def ask_args(prompt="Build a lobby", **overrides):
    fields = dict(command="ask", prompt=prompt, image=[], project="STAR", studio_id="", no_studio=True,
                  edit=False, unsafe_luau=False)
    fields.update(overrides)
    return fields


def picture(path, image_format="PNG", size=(8, 8)):
    Image.new("RGB", size, (200, 30, 30)).save(path, image_format)
    return path


# ---------- the loopback rule for the local model endpoint ----------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:1234/v1", "http://localhost:1234/v1", "http://localhost:8080",
])
def test_loopback_endpoints_with_a_port_are_accepted(url):
    assert cli.loopback_endpoint(url)


@pytest.mark.parametrize("url", [
    "http://localhost:1234@example.com/v1",      # user name "localhost", host example.com
    "http://127.0.0.1:1234@203.0.113.5:8080/v1",
    "http://user:pw@localhost:1234/v1",
    "https://localhost:1234/v1",
    "http://localhost/v1",                        # no explicit port, as before
    "http://localhost.example.com:1234/v1",
    "http://127.0.0.1.nip.io:1234/v1",
    "http://198.51.100.20:1234/v1",
    "http://localhost:99999/v1",                  # invalid port
    "localhost:1234",
    "",
])
def test_anything_that_could_leave_the_machine_is_refused(url):
    assert not cli.loopback_endpoint(url)


# ---------- knowledge commands ----------

def test_a_note_stays_a_candidate_until_it_is_reviewed(root, capsys):
    run(command="knowledge-add", project="Obby", kind="decision", text="Checkpoints every 20 studs",
        source="design-doc", revision="r1")
    note_id = int(capsys.readouterr().out.rsplit(":", 1)[1])
    run(command="knowledge-find", project="Obby", query="Checkpoints", include_candidates=False)
    assert json.loads(capsys.readouterr().out) == []
    run(command="knowledge-find", project="Obby", query="Checkpoints", include_candidates=True)
    assert [note["text"] for note in json.loads(capsys.readouterr().out)] == ["Checkpoints every 20 studs"]
    run(command="knowledge-review", project="Obby", note_id=note_id, evidence="Playtest 3 passed")
    assert "marked reviewed" in capsys.readouterr().out
    run(command="knowledge-find", project="Obby", query="Checkpoints", include_candidates=False)
    found = json.loads(capsys.readouterr().out)
    assert [note["id"] for note in found] == [note_id]
    run(command="knowledge-find", project="Other", query="Checkpoints", include_candidates=True)
    assert json.loads(capsys.readouterr().out) == []             # notes never cross projects
    assert (root / ".local" / "star-knowledge").is_dir()


def test_reference_images_are_typed_by_their_bytes_not_their_name(root, tmp_path, capsys, monkeypatch):
    recorded = []
    from star.knowledge import KnowledgeStore
    original = KnowledgeStore.ingest_artifact

    def spy(self, **kwargs):
        recorded.append(kwargs["media_type"])
        return original(self, **kwargs)

    monkeypatch.setattr(KnowledgeStore, "ingest_artifact", spy)
    disguised = picture(tmp_path / "shot.jpg", "PNG")
    run(command="reference-add", project="STAR", file=str(disguised))
    assert "Locally stored image:" in capsys.readouterr().out
    webp = picture(tmp_path / "concept.png", "WEBP")
    run(command="reference-add", project="STAR", file=str(webp))
    assert recorded == ["image/png", "image/webp"]


@pytest.mark.parametrize("make", [
    lambda folder: picture(folder / "anim.gif", "GIF"),
    lambda folder: (folder / "notes.png").write_bytes(b"not an image") and folder / "notes.png",
    lambda folder: folder / "missing.png",
])
def test_reference_add_refuses_anything_but_a_real_png_jpeg_or_webp(root, tmp_path, make):
    with pytest.raises((ValueError, OSError)):
        run(command="reference-add", project="STAR", file=str(make(tmp_path)))


def test_memory_without_a_checkpoint_says_so(root, capsys):
    run(command="memory", project="Nothing yet")
    assert capsys.readouterr().out.strip() == "No checkpoint for this project"


def test_evals_lists_cases_and_says_not_run_is_not_a_pass(capsys):
    run(command="evals")                         # read-only: uses the checkout's evals catalog
    output = capsys.readouterr().out
    assert "Not-run cases are NOT test passes" in output
    summary = json.loads(output[:output.rindex("}") + 1])
    assert isinstance(summary, dict) and summary


# ---------- self-build ----------

def test_self_build_needs_a_configured_model(root):
    with pytest.raises(RuntimeError, match="STAR_MODEL"):
        run(command="self-build", task="Add a skill", publish_draft=False)


@pytest.mark.parametrize("url", ["http://localhost:1234@example.com/v1", "https://api.example.com/v1"])
def test_self_build_refuses_a_model_endpoint_off_this_machine(root, monkeypatch, url):
    import star.selfbuild as selfbuild
    monkeypatch.setenv("STAR_MODEL", "local-model")
    monkeypatch.setenv("STAR_BASE_URL", url)
    monkeypatch.setattr(selfbuild, "develop", lambda **kwargs: pytest.fail("must not start"))
    with pytest.raises(RuntimeError, match="loopback"):
        run(command="self-build", task="Add a skill", publish_draft=False)


def test_self_build_runs_against_the_local_model_without_publishing(root, monkeypatch, capsys):
    import star.selfbuild as selfbuild
    calls = []

    async def develop(**kwargs):
        calls.append(kwargs)
        return {"status": "proposed", "files": ["star/skills/example.py"]}

    monkeypatch.setenv("STAR_MODEL", "local-model")
    monkeypatch.setattr(selfbuild, "develop", develop)
    run(command="self-build", task="Add a skill", publish_draft=False)
    assert json.loads(capsys.readouterr().out)["status"] == "proposed"
    assert calls[0]["model"] == "local-model" and calls[0]["github"] is None
    assert calls[0]["repository"] == root and calls[0]["task"] == "Add a skill"


# ---------- ask: refusals come first and store nothing ----------

@pytest.mark.parametrize("env,overrides,message", [
    ({}, {}, "STAR_MODEL"),
    ({"STAR_MODEL": "your-loaded-lm-studio-model-id"}, {}, "STAR_MODEL"),
    ({"STAR_MODEL": "m", "STAR_BASE_URL": "http://localhost:1234@example.com/v1"}, {}, "loopback"),
    ({"STAR_MODEL": "m"}, {"unsafe_luau": True}, "--unsafe-luau requires --edit"),
    ({"STAR_MODEL": "m"}, {"edit": True}, "selected disposable Studio"),
    ({"STAR_MODEL": "m"}, {"edit": True, "no_studio": False, "studio_id": "abc"}, "STAR_SANDBOX_STUDIO_ID"),
    ({"STAR_MODEL": "m", "STAR_SANDBOX_STUDIO_ID": "other"},
     {"edit": True, "no_studio": False, "studio_id": "abc"}, "STAR_SANDBOX_STUDIO_ID"),
    ({"STAR_MODEL": "m"}, {"no_studio": False}, "--studio-id"),
])
def test_ask_refuses_unsafe_or_incomplete_runs_before_storing_anything(root, tmp_path, monkeypatch,
                                                                       env, overrides, message):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    reference = picture(tmp_path / "ref.png")
    with pytest.raises(RuntimeError, match=message):
        run(**ask_args(image=[str(reference)], **overrides))
    # Regression: the reference image used to be copied into the knowledge store first.
    assert not (root / ".local").exists() and not (root / "runs").exists()


def test_ask_validates_every_reference_before_storing_any(root, tmp_path, monkeypatch):
    monkeypatch.setenv("STAR_MODEL", "m")
    good = picture(tmp_path / "good.png")
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not an image")
    with pytest.raises((ValueError, OSError)):
        run(**ask_args(image=[str(good), str(bad)]))
    assert not (root / ".local" / "star-knowledge").exists()


def test_ask_without_studio_saves_the_run_and_a_factual_checkpoint(root, tmp_path, monkeypatch, capsys):
    import star.agent as agent
    from star.knowledge import KnowledgeStore
    from star.memory import Memory
    seen = {}

    async def execute(**kwargs):
        seen.update(kwargs)
        kwargs["on_event"]({"event": "model_call", "n": 1})
        return "Here is the lobby.", [{"role": "user", "content": "Build a lobby"}], [{"call": 1}]

    monkeypatch.setattr(agent, "execute", execute)
    monkeypatch.setenv("STAR_MODEL", "local-model")
    monkeypatch.setenv("STAR_MAX_MODEL_CALLS", "3")
    store = KnowledgeStore(root / ".local" / "star-knowledge")
    note = store.add_note(project="STAR", kind="decision", text="Lobby is 64 studs wide", source="doc")
    store.review_note(project="STAR", note_id=note, evidence="checked")
    store.add_note(project="STAR", kind="decision", text="Unreviewed lobby rumour", source="chat")
    store.close()

    run(**ask_args(image=[str(picture(tmp_path / "ref.png", "JPEG"))]))

    assert seen["model"] == "local-model" and seen["max_calls"] == 3 and "studio" not in seen
    assert "Lobby is 64 studs wide" in seen["project_memory"]
    assert "Unreviewed lobby rumour" not in seen["project_memory"]   # only reviewed notes are trusted
    [run_dir] = list((root / "runs").iterdir())
    assert (run_dir / "answer.md").read_text(encoding="utf-8") == "Here is the lobby."
    saved = json.loads((run_dir / "conversation.json").read_text(encoding="utf-8"))
    assert saved["archive"] == [{"call": 1}]
    assert json.loads((run_dir / "events.jsonl").read_text(encoding="utf-8").strip()) == {"event": "model_call", "n": 1}
    memory = Memory(root / ".local" / "star-memory.sqlite3")
    try:
        assert "Verify the final answer" in memory.get("STAR")      # never claims the run succeeded
    finally:
        memory.close()
    assert "Saved:" in capsys.readouterr().out


# ---------- GitHub commands ----------

class FakeBot:
    def __init__(self):
        self.written = []

    async def check(self):
        return {"repositories": [{"full_name": "owner/repo"}, {}]}

    async def create_branch(self, branch):
        self.branch = branch
        return "main"

    async def write_branch_file(self, branch, path, data, message):
        self.written.append(path)

    async def open_pr(self, base, branch, title, body):
        return {"html_url": "https://github.com/owner/repo/pull/1"}


def test_github_check_lists_accessible_repositories(root, monkeypatch, capsys):
    import star.github_app as github_app
    monkeypatch.setattr(github_app, "from_env", FakeBot)
    run(command="github-check")
    assert capsys.readouterr().out.splitlines()[1:] == ["owner/repo", "unknown"]


def test_github_sync_publishes_only_skill_files(root, monkeypatch, capsys):
    import star.github_app as github_app
    bot = FakeBot()
    monkeypatch.setattr(github_app, "from_env", lambda: bot)
    for relative in ("star/skills/lobby.py", "star/skills/__init__.py", "docs/skills/lobby.md",
                     "star/cli.py", "tests/test_x.py", ".env", "docs/other.md"):
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text("x", encoding="utf-8")
    run(command="github-sync", branch="star/skills-update")
    assert bot.written == ["docs/skills/lobby.md", "star/skills/lobby.py"]
    assert "pull/1" in capsys.readouterr().out


def test_github_sync_with_nothing_allowlisted_stops(root, monkeypatch):
    import star.github_app as github_app
    monkeypatch.setattr(github_app, "from_env", FakeBot)
    (root / "README.md").write_text("x", encoding="utf-8")
    with pytest.raises(RuntimeError, match="No allowlisted"):
        run(command="github-sync", branch="star/skills-update")


def test_github_commands_need_the_app_key_configured(root):
    with pytest.raises(ValueError, match="STAR_GITHUB_PRIVATE_KEY_FILE"):
        run(command="github-check")


# ---------- the entry point ----------

def test_cli_turns_a_refusal_into_exit_code_1_with_a_message(root, monkeypatch, capsys):
    monkeypatch.setattr(cli, "setup", lambda: None)
    monkeypatch.setattr(sys, "argv", ["star", "ask", "hello", "--no-studio"])
    with pytest.raises(SystemExit) as stopped:
        cli.cli()
    assert stopped.value.code == 1
    assert capsys.readouterr().err.startswith("STAR stopped: Set STAR_MODEL")


def test_cli_rejects_unknown_choices_with_usage_exit_code(root, monkeypatch, capsys):
    monkeypatch.setattr(cli, "setup", lambda: None)
    monkeypatch.setattr(sys, "argv", ["star", "knowledge-add", "--project", "P", "--kind", "gossip",
                                      "--text", "t", "--source", "s"])
    with pytest.raises(SystemExit) as stopped:
        cli.cli()
    assert stopped.value.code == 2 and "invalid choice" in capsys.readouterr().err


def test_doctor_reports_packages_and_says_it_is_not_a_live_test(root, monkeypatch, capsys):
    import star.studio as studio
    monkeypatch.setattr(studio, "launcher", lambda: (_ for _ in ()).throw(FileNotFoundError("no studio")))
    monkeypatch.setenv("STAR_MODEL", "local-model")
    monkeypatch.setattr(cli, "setup", lambda: None)
    monkeypatch.setattr(sys, "argv", ["star", "doctor"])
    cli.cli()
    output = capsys.readouterr().out
    assert "Model identifier: local-model" in output and "httpx" in output
    assert "Roblox MCP: FileNotFoundError" in output
    assert output.rstrip().endswith("This is not a live model or Roblox tool smoke test.")


def test_unknown_command_is_an_error():
    with pytest.raises(ValueError, match="Unknown command"):
        run(command="dance")
