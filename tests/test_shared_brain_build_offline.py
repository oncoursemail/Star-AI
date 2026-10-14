"""shared_brain.build without Graphify installed: a small fake Graphify stands in for it.

The real-Graphify tests in test_shared_brain_build.py are skipped on CI (Graphify is an
optional tool), which left the build's publication, reuse and rollback paths untested there.
The fake records what it is given and produces a graph whose size the test controls.
"""
import json
import os
import subprocess
import sys
import types

import pytest

from star.shared_brain import build as build_module
from star.shared_brain.build import build, digest, project_id


class FakeGraph:
    def __init__(self, nodes, edges=0):
        self.nodes, self.edges = nodes, edges

    def number_of_nodes(self):
        return self.nodes

    def number_of_edges(self):
        return self.edges


class FakeGraphify:
    def __init__(self):
        self.extracted = []
        self.nodes = None            # None: one node per source
        self.commits = []
        self.during_extract = None

    def install(self, monkeypatch):
        package = types.ModuleType("graphify")
        extract = types.ModuleType("graphify.extract")
        builder = types.ModuleType("graphify.build")
        export = types.ModuleType("graphify.export")
        extract.extract = self.extract
        builder.build_from_json = self.build_from_json
        export.to_json = self.to_json
        for name, module in (("graphify", package), ("graphify.extract", extract),
                             ("graphify.build", builder), ("graphify.export", export)):
            monkeypatch.setitem(sys.modules, name, module)

    def extract(self, files, *, cache_root, root, parallel, max_workers):
        assert parallel is False and max_workers == 1 and cache_root == root
        self.extracted.append(sorted(path.relative_to(root).as_posix() for path in files))
        if self.during_extract:
            self.during_extract()
        return {"files": [path.read_text(encoding="utf-8") for path in files]}

    def build_from_json(self, extraction, *, root, directed):
        count = len(extraction["files"]) if self.nodes is None else self.nodes
        return FakeGraph(count, max(0, count - 1))

    def to_json(self, graph, communities, path, *, built_at_commit):
        self.commits.append(built_at_commit)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"nodes": [{"id": i} for i in range(graph.number_of_nodes())]}, handle)


@pytest.fixture
def graphify(monkeypatch):
    fake = FakeGraphify()
    fake.install(monkeypatch)
    # Not a git checkout: the build records no commit (and never shells out elsewhere).
    monkeypatch.setattr(build_module.subprocess, "run",
                        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 128, "", "not a repo"))
    return fake


@pytest.fixture
def project(tmp_path):
    (tmp_path / "star").mkdir()
    for name, body in (("first.py", "def retrieve():\n    return 1\n"),
                       ("other.py", "def context():\n    return 2\n")):
        (tmp_path / "star" / name).write_text(body, encoding="utf-8")
    return tmp_path


def out(project):
    return project / "graphify-out"


def test_a_build_publishes_a_graph_and_a_manifest_bound_to_it(project, graphify):
    result = build(project, ["star/other.py", "star/first.py"])
    assert graphify.extracted == [["star/first.py", "star/other.py"]]   # exactly the selected list
    graph_bytes = (out(project) / "graph.json").read_bytes()
    manifest = json.loads((out(project) / "shared-brain-manifest.json").read_text(encoding="utf-8"))
    assert manifest["graph_sha256"] == digest(graph_bytes) == result["graph_sha256"]
    assert manifest["project_id"] == project_id(project) and manifest["semantic_extraction"] is False
    assert manifest["sources"]["star/first.py"]["sha256"] == digest((project / "star/first.py").read_bytes())
    assert result["sources"] == 2 and result["changed_sources"] == 2 and result["nodes"] == 2
    assert result["input_tokens"] == result["output_tokens"] == 0
    leftovers = {p.name for p in out(project).iterdir()} - {"graph.json", "shared-brain-manifest.json",
                                                            "shared-brain-build"}
    assert leftovers == set()                                      # no lock, temp file or backup left
    assert graphify.commits == [None]


def test_rebuilds_reuse_unchanged_sources_and_count_changes_and_deletions(project, graphify):
    build(project, ["star/first.py", "star/other.py"])
    same = build(project, ["star/first.py", "star/other.py"])
    assert same["changed_sources"] == 0 and same["reused_sources"] == 2 and same["deleted_sources"] == 0
    (project / "star/first.py").write_text("def source_search():\n    return 3\n", encoding="utf-8")
    changed = build(project, ["star/first.py"])
    assert changed["changed_sources"] == 1 and changed["deleted_sources"] == 1
    staged = out(project) / "shared-brain-build" / "star" / "first.py"
    assert "source_search" in staged.read_text(encoding="utf-8")


@pytest.mark.parametrize("previous", [
    "{not json",
    json.dumps({"project_id": "another-project", "sources": {"star/first.py": {"sha256": "x"}}}),
])
def test_an_unreadable_or_foreign_manifest_is_ignored_not_trusted(project, graphify, previous):
    out(project).mkdir()
    (out(project) / "shared-brain-manifest.json").write_text(previous, encoding="utf-8")
    result = build(project, ["star/first.py"])
    assert result["changed_sources"] == 1 and result["deleted_sources"] == 0


def test_without_a_list_the_default_sources_that_exist_are_built(project, graphify):
    (project / "star" / "memory.py").write_text("def remember():\n    return 1\n", encoding="utf-8")
    (project / "star" / "agent.py").write_text("def act():\n    return 1\n", encoding="utf-8")
    result = build(project)
    assert graphify.extracted == [["star/agent.py", "star/memory.py"]] and result["sources"] == 2


def test_an_empty_extraction_keeps_the_previous_graph(project, graphify):
    build(project, ["star/first.py"])
    before = (out(project) / "graph.json").read_bytes()
    graphify.nodes = 0
    with pytest.raises(ValueError, match="Extraction is empty"):
        build(project, ["star/first.py", "star/other.py"])
    assert (out(project) / "graph.json").read_bytes() == before
    assert not (out(project) / ".shared-brain-build.lock").exists()


def test_a_source_edited_during_extraction_is_not_published(project, graphify):
    build(project, ["star/first.py"])
    before = (out(project) / "graph.json").read_bytes()
    graphify.during_extract = lambda: (project / "star/first.py").write_text("def edited():\n    pass\n",
                                                                            encoding="utf-8")
    with pytest.raises(ValueError, match="Sources changed during extraction"):
        build(project, ["star/first.py"])
    assert (out(project) / "graph.json").read_bytes() == before


def test_a_build_in_progress_is_never_interrupted_or_unlocked_by_a_second(project, graphify):
    out(project).mkdir()
    lock = out(project) / ".shared-brain-build.lock"
    lock.write_text("", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build(project, ["star/first.py"])
    assert lock.exists()                         # the other build's lock is left alone
    assert graphify.extracted == [] and not (out(project) / "graph.json").exists()


def test_a_failed_manifest_publish_restores_the_previous_graph(project, graphify, monkeypatch):
    build(project, ["star/first.py"])
    before_graph = (out(project) / "graph.json").read_bytes()
    before_manifest = (out(project) / "shared-brain-manifest.json").read_bytes()
    real_replace = os.replace

    def failing_replace(source, target):
        if str(target).endswith("shared-brain-manifest.json"):
            raise OSError("disk full")
        return real_replace(source, target)

    monkeypatch.setattr(build_module.os, "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        build(project, ["star/first.py", "star/other.py"])
    assert (out(project) / "graph.json").read_bytes() == before_graph
    assert (out(project) / "shared-brain-manifest.json").read_bytes() == before_manifest
    assert not (out(project) / ".shared-brain-build.lock").exists()


def test_a_failed_first_publish_leaves_no_half_published_graph(project, graphify, monkeypatch):
    real_replace = os.replace

    def failing_replace(source, target):
        if str(target).endswith("shared-brain-manifest.json"):
            raise OSError("disk full")
        return real_replace(source, target)

    monkeypatch.setattr(build_module.os, "replace", failing_replace)
    with pytest.raises(OSError):
        build(project, ["star/first.py"])
    assert not (out(project) / "graph.json").exists()


def test_the_git_commit_is_recorded_when_the_project_is_a_checkout(project, graphify, monkeypatch):
    monkeypatch.setattr(build_module.subprocess, "run",
                        lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, "abc123\n", ""))
    build(project, ["star/first.py"])
    assert graphify.commits == ["abc123"]


@pytest.mark.parametrize("sources", [[], ["star/first.py", "star/first.py"],
                                     [f"star/m{i}.py" for i in range(257)]])
def test_source_lists_must_be_1_to_256_distinct_names(project, graphify, sources):
    with pytest.raises(ValueError, match="1–256 distinct"):
        build(project, sources)
    assert not out(project).exists()


def test_the_whole_corpus_is_bounded(project, graphify, monkeypatch):
    monkeypatch.setattr(build_module, "MAX_CORPUS_BYTES", 40)
    with pytest.raises(ValueError, match="corpus exceeds"):
        build(project, ["star/first.py", "star/other.py"])
    assert graphify.extracted == []


def test_a_project_must_be_a_directory(tmp_path, graphify):
    file = tmp_path / "file.py"
    file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="project directory"):
        build(file, ["star/first.py"])
