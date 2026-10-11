from copy import deepcopy
from pathlib import Path
import socket
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from starkb.corpus_cli import main
from starkb.corpus_manifest import CorpusError, contained_file
from starkb.corpus_plan import plan
from corpus_fixture import save, snapshot, tree_bytes


def test_dry_run_changes_no_files_git_metadata_or_indexes(tmp_path, monkeypatch):
    repo, manifest, _ = snapshot(tmp_path)
    before = tree_bytes(tmp_path)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network forbidden"))
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: pytest.fail("write forbidden"))
    monkeypatch.setattr(Path, "write_bytes", lambda *a, **k: pytest.fail("write forbidden"))
    result = plan(manifest, repo.parent)
    assert result["sources"][0]["status"] == "verified-local"
    assert result["network"] is False and result["model_calls"] is False
    assert tree_bytes(tmp_path) == before
    assert result == plan(manifest, repo.parent)


def test_unresolved_catalogue_is_honest_and_writes_nothing(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    before = tree_bytes(tmp_path)
    result = plan(root / "corpus-candidates.json", tmp_path / "missing-sources")
    assert len(result["sources"]) == 9
    assert all(s["status"] == "unavailable" for s in result["sources"])
    assert tree_bytes(tmp_path) == before
    assert main(["plan", "--sources-dir", str(tmp_path / "missing-sources")]) == 0
    assert '"status": "unavailable"' in capsys.readouterr().out


@pytest.mark.parametrize("key,value", [("file_bytes", 10), ("total_bytes", 10), ("chunks", 1)])
def test_meaningful_content_bounds_are_visible(tmp_path, key, value):
    text = "# A\n" + "Body line\n" * 300
    repo, manifest, source = snapshot(tmp_path, files={"src/content/docs/a.md": text})
    source["limits"][key] = value
    save(manifest, [source])
    result = plan(manifest, repo.parent)
    assert result["sources"][0]["status"] == "unavailable"
    assert "bound" in result["sources"][0]["error"]


def test_file_count_bound_is_selection_validation(tmp_path):
    _, manifest, source = snapshot(tmp_path)
    source["paths"].append("src/content/docs/other.md")
    source["limits"]["files"] = 1
    save(manifest, [source])
    with pytest.raises(CorpusError, match="file count"):
        plan(manifest, tmp_path / "sources")


def test_symlink_cannot_be_used_as_selected_material(tmp_path):
    target = tmp_path / "outside.md"
    target.write_text("outside")
    repo = tmp_path / "repo"
    repo.mkdir()
    try:
        (repo / "link.md").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable on this host")
    with pytest.raises(CorpusError, match="symlink"):
        contained_file(repo, "link.md", 1000)


def test_unknown_selection_and_missing_sources_fail_visibly(tmp_path):
    repo, manifest, source = snapshot(tmp_path)
    with pytest.raises(CorpusError, match="unknown"):
        plan(manifest, repo.parent, selected=["invented"])
    source["paths"] = ["src/content/docs/missing.md"]
    save(manifest, [source])
    assert "missing" in plan(manifest, repo.parent)["sources"][0]["error"]
