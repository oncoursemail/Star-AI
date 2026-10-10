"""Review bundles must be explicit, useful and secret-free."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import json
import sqlite3
import zipfile

from PIL import Image
import pytest

from star.desktop_core import Settings
from star.diagnostics import export_review_bundle, review_snapshot


def test_diagnostics_excludes_user_content_and_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "super-private-api-key-ABCDE")
    home = tmp_path / "profile"
    home.mkdir()
    private = "VERY_PRIVATE_PROJECT_OR_PASSWORD"
    chats = sqlite3.connect(home / "conversations.sqlite3")
    chats.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, project TEXT, body TEXT)")
    chats.execute("INSERT INTO messages (project,body) VALUES (?,?)", (private,private))
    chats.commit()
    chats.close()
    metrics = sqlite3.connect(home / "analytics.sqlite3")
    metrics.execute("CREATE TABLE events (kind TEXT, elapsed_ms INTEGER, detail TEXT, recorded_at TEXT)")
    metrics.execute(
        "INSERT INTO events VALUES ('run_failed',7,?,datetime('now'))",
        ("Authorization error contains "+private,)
    )
    metrics.commit()
    metrics.close()
    settings = Settings(project=private,workspace=str(tmp_path),model="openai/gpt-oss-20b",
                        provider="groq")
    out = export_review_bundle(home,settings,tmp_path/"bundle.zip")
    with zipfile.ZipFile(out) as archive:
        names=set(archive.namelist())
        assert names == {"README.txt", "manifest.json", "environment.json",
                         "configuration.json", "activity-summary.json"}
        combined=b"".join(archive.read(item) for item in names)
        assert private.encode() not in combined
        assert str(tmp_path).encode() not in combined
        assert b"super-private-api-key-ABCDE" not in combined
        conf=json.loads(archive.read("configuration.json"))
        assert conf["provider_credentials_configured"]["groq"] is True
        assert conf["workspace_configured"] is True
        assert "workspace" not in str(conf.values())
        activity=json.loads(archive.read("activity-summary.json"))
        assert activity["conversation_message_count"] == 1
        assert activity["failures_by_exception_type"] == {"Other": 1}


def test_screenshot_only_with_explicit_bytes(tmp_path):
    buf=BytesIO()
    Image.new("RGB",(80,60),(25,40,60)).save(buf,format="PNG")
    settings=Settings()
    out=export_review_bundle(tmp_path,settings,tmp_path/"with-screen.zip",
                             screenshot_png=buf.getvalue())
    with zipfile.ZipFile(out) as archive:
        assert "current-screen.png" in archive.namelist()
        assert json.loads(archive.read("manifest.json"))["screenshot_included"]
    with pytest.raises(ValueError):
        export_review_bundle(tmp_path,settings,tmp_path/"bad.zip",screenshot_png=b"not PNG")


def test_reject_bad_output_target(tmp_path):
    for filename in ("review.txt", "review"):
        with pytest.raises(ValueError):
            export_review_bundle(tmp_path,Settings(),tmp_path/filename)
    other=tmp_path/"out.zip"
    other.symlink_to(tmp_path/"target.zip")
    with pytest.raises(PermissionError):
        export_review_bundle(tmp_path,Settings(),other)


def test_snapshot_never_publishes_keys_or_local_paths(tmp_path):
    config=review_snapshot(tmp_path,Settings(project="secret",model="testing",workspace="private/path"),"running")
    assert config["configuration.json"]["workspace_configured"] is True
    assert "private/path" not in json.dumps(config)
    assert "secret" not in json.dumps(config)
