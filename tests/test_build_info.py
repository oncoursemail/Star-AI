"""Build provenance is bounded, nonsecret, and not a claimed signature."""
import json
from star.build_info import read_build_info


def test_unknown_source_build_is_honest(tmp_path):
    assert not read_build_info(tmp_path)["stamped"]


def test_stamped_release_points_to_exact_run(tmp_path):
    folder=tmp_path/"star"
    folder.mkdir()
    (folder/"build-info.json").write_text(json.dumps({
        "schema":1,"source_commit":"a"*40,"head_commit":"b"*40,
        "build_event":"pull_request","run_id":"38025009718"
    }),encoding="utf-8")
    result=read_build_info(tmp_path)
    assert result["stamped"]
    assert result["source_commit"]=="a"*40
    assert result["head_commit"]=="b"*40
    assert result["run_url"].endswith("/38025009718")
    assert "not a cryptographic signature" in result["note"]


def test_tampered_or_oversized_build_metadata_is_not_trusted(tmp_path):
    directory=tmp_path/"star"
    directory.mkdir()
    file=directory/"build-info.json"
    for raw in [
        "{}",
        '{"schema":1,"source_commit":"notasha"}',
        json.dumps({"schema":1,"source_commit":"a"*40,"head_commit":"b"*40,
                    "build_event":"arbitrary","run_id":"3"}),
        json.dumps({"schema":1,"source_commit":"a"*40,"head_commit":"b"*40,
                    "build_event":"push","run_id":"nan"}),
        "A"*2500,
    ]:
        file.write_text(raw,encoding="utf-8")
        assert not read_build_info(tmp_path)["stamped"]
