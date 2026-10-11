from contextlib import closing
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from star.shared_brain.build import build, project_id, source_path
from star.shared_brain.store import SharedBrain


def test_incremental_build_and_deletion(tmp_path):
    pytest.importorskip("graphify")
    (tmp_path / "star").mkdir()
    source = tmp_path / "star" / "first.py"
    other = tmp_path / "star" / "other.py"
    source.write_text("def retrieve():\n    return 1\n", encoding="utf-8")
    other.write_text("def context():\n    return 2\n", encoding="utf-8")
    first = build(tmp_path, ["star/first.py", "star/other.py"])
    same = build(tmp_path, ["star/first.py", "star/other.py"])
    assert first["changed_sources"] == 2
    assert same["changed_sources"] == 0 and same["reused_sources"] == 2
    source.write_text("def source_search():\n    return 3\n", encoding="utf-8")
    changed = build(tmp_path, ["star/first.py"])
    assert changed["changed_sources"] == 1 and changed["deleted_sources"] == 1
    graph = json.loads((tmp_path / "graphify-out/graph.json").read_text(encoding="utf-8"))
    assert any(n.get("label") == "source_search()" for n in graph["nodes"])
    assert not any(n.get("label") == "context()" for n in graph["nodes"])
    manifest = json.loads((tmp_path / "graphify-out/shared-brain-manifest.json").read_text())
    assert manifest["project_id"] == project_id(tmp_path)
    assert manifest["input_tokens"] == manifest["output_tokens"] == 0


@pytest.mark.parametrize("name", ["../other.py", "star/../other.py", "star/.env.py", "star/secret.py", "C:/other.py"])
def test_source_scope(tmp_path, name):
    with pytest.raises(ValueError):
        source_path(tmp_path, name)


def test_bad_build_preserves_previous_graph(tmp_path):
    (tmp_path / "graphify-out").mkdir()
    graph = tmp_path / "graphify-out/graph.json"
    graph.write_text('{"nodes":[{"id":"original"}]}')
    with pytest.raises(ValueError):
        build(tmp_path, ["star/missing.py"])
    assert "original" in graph.read_text()


def test_manifest_temp_link_cannot_overwrite_outside_file(tmp_path, monkeypatch):
    pytest.importorskip("graphify")
    project = tmp_path / "project"
    (project / "star").mkdir(parents=True)
    (project / "star/source.py").write_text("def retrieve():\n    return 1\n")
    out = project / "graphify-out"
    out.mkdir()
    victim = tmp_path / "outside-manifest.json"
    victim.write_text("outside sentinel")
    temporary = out / ".shared-brain-manifest.tmp"
    try:
        temporary.symlink_to(victim)
    except OSError:
        # NTFS hard links need no symlink privilege. Simulate the link flag,
        # while keeping a real alias that would expose an unsafe write.
        os.link(victim, temporary)
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda p: p == temporary or original(p))
    with pytest.raises(ValueError, match="links"):
        build(project, ["star/source.py"])
    assert victim.read_text() == "outside sentinel"
    assert not (out / "graph.json").exists()


@pytest.mark.parametrize("kind", ["source", "stage", "output"])
def test_in_root_junctions_are_rejected(tmp_path, monkeypatch, kind):
    pytest.importorskip("graphify")
    (tmp_path / "star").mkdir()
    source_name = "star/source.py"
    if kind == "source":
        junction = tmp_path / "star/alias"
        junction.mkdir()
        source_name = "star/alias/source.py"
    else:
        junction = tmp_path / "graphify-out"
        junction.mkdir()
        if kind == "stage":
            junction = junction / "shared-brain-build"
            junction.mkdir()
    (tmp_path / source_name).write_text("def retrieve():\n    return 1\n")
    # An in-root alias passes resolved containment. Explicit junction refusal
    # must still hold on Windows and on test runtimes without is_junction().
    original = getattr(Path, "is_junction", lambda p: False)
    monkeypatch.setattr(Path, "is_junction", lambda p: p == junction or original(p), raising=False)
    with pytest.raises(ValueError, match="links"):
        build(tmp_path, [source_name])
    assert not (tmp_path / "graphify-out/graph.json").exists()


def test_reparse_source_refused_without_junction_api(tmp_path, monkeypatch):
    alias = tmp_path / "star/alias"
    alias.mkdir(parents=True)
    (alias / "source.py").write_text("def retrieve():\n    return 1\n")
    original_lstat = Path.lstat

    def flagged_lstat(path, *args, **kwargs):
        value = original_lstat(path, *args, **kwargs)
        if path != alias:
            return value
        return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=0x400)

    # Python 3.11 lacks is_junction(); the Windows reparse attribute still
    # identifies junction ancestors without following their target contents.
    monkeypatch.setattr(Path, "is_junction", lambda p: False, raising=False)
    monkeypatch.setattr(Path, "lstat", flagged_lstat)
    with pytest.raises(ValueError, match="links"):
        source_path(tmp_path, "star/alias/source.py")


def test_second_publish_failure_preserves_previous_attested_pair(tmp_path, monkeypatch):
    pytest.importorskip("graphify")
    import importlib
    module = importlib.import_module("star.shared_brain.build")
    (tmp_path / "star").mkdir()
    source = tmp_path / "star/source.py"
    source.write_text("def original():\n    return 1\n")
    build(tmp_path, ["star/source.py"])
    graph = tmp_path / "graphify-out/graph.json"
    manifest = tmp_path / "graphify-out/shared-brain-manifest.json"
    before = graph.read_bytes(), manifest.read_bytes()
    source.write_text("def changed():\n    return 2\n")
    original_replace = module.os.replace

    def fail_manifest_replace(src, dest):
        if Path(dest) == manifest:
            raise OSError("synthetic manifest publication failure")
        return original_replace(src, dest)

    monkeypatch.setattr(module.os, "replace", fail_manifest_replace)
    with pytest.raises(OSError, match="synthetic"):
        build(tmp_path, ["star/source.py"])
    assert (graph.read_bytes(), manifest.read_bytes()) == before
    assert not (tmp_path / "graphify-out/.shared-brain-build.lock").exists()


def test_sync_refuses_in_progress_graph_publication(tmp_path):
    pytest.importorskip("graphify")
    (tmp_path / "star").mkdir()
    (tmp_path / "star/source.py").write_text("def retrieve():\n    return 1\n")
    build(tmp_path, ["star/source.py"])
    with closing(SharedBrain(tmp_path)) as brain:
        brain.sync()
        before = brain.stats()
        lock = tmp_path / "graphify-out/.shared-brain-build.lock"
        lock.write_text("synthetic in-progress publication")
        with pytest.raises(RuntimeError, match="build is in progress"):
            brain.sync()
        assert brain.stats() == before


def test_source_growth_after_scope_check_cannot_exceed_read_budget(tmp_path, monkeypatch):
    pytest.importorskip("graphify")
    import importlib
    module = importlib.import_module("star.shared_brain.build")
    (tmp_path / "star").mkdir()
    source = tmp_path / "star/source.py"
    source.write_text("def retrieve():\n    return 1\n")
    original_source_path = module.source_path

    def grow_after_check(root, name):
        path = original_source_path(root, name)
        path.write_bytes(b"#" + b"x" * module.MAX_SOURCE_BYTES + b"\ndef retrieve():\n    return 1\n")
        return path

    monkeypatch.setattr(module, "source_path", grow_after_check)
    with pytest.raises(ValueError, match="size|limit"):
        build(tmp_path, ["star/source.py"])
    assert not (tmp_path / "graphify-out/graph.json").exists()
