from pathlib import Path

from star.brain_overview import brain_snapshot
from star.desktop_core import Settings
from star.react_shell import ALLOWED_ACTIONS


def test_brain_snapshot_reads_temporary_profile_without_network(tmp_path: Path):
    profile = tmp_path / "profile"
    profile.mkdir()
    settings_file = profile / "settings.json"
    settings = Settings()
    settings.model = "configured-model"
    settings.fast_model = "fast-model"
    settings.skills_enabled = False
    settings.save(settings_file)
    result = brain_snapshot(settings_file, profile)
    assert "brainSnapshot" in ALLOWED_ACTIONS
    assert result["models"] == ["configured-model", "fast-model"]
    assert result["skills"]["enabled"] is False
    assert result["lessons"]["candidate"] == 0
    assert result["evaluation"] is None
    assert isinstance(result["tools"], list)
    assert result["roles"]


def test_brain_snapshot_reads_stored_evaluation_summary(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    Settings().save(settings_file)
    folder = tmp_path / "evals"
    folder.mkdir()
    (folder / "latest_summary.json").write_text('{"passed": 3, "total": 4, "secret": "no"}')
    result = brain_snapshot(settings_file, tmp_path)
    assert result["evaluation"] == {"passed": 3, "total": 4}
