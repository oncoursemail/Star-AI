"""Regression checks for the Inno Setup post-install app launches."""
from pathlib import Path


def test_all_postinstall_star_launches_use_original_user():
    script = (Path(__file__).resolve().parents[1] / "installer" / "STAR.iss").read_text(encoding="utf-8")
    section = script.split("[Run]", 1)[1].split("\n[", 1)[0]
    launches = [line for line in section.splitlines() if line.strip() and not line.lstrip().startswith(";") and "Filename:" in line and "{#STARExe}" in line]
    assert launches, "No STAR post-install launch entries found"
    assert any("postinstall" in line.lower() and "skipifsilent" in line.lower() for line in launches)
    assert any("skipifnotsilent" in line.lower() for line in launches)
    for line in launches:
        flags = line.split("Flags:", 1)[1].strip().lower().split() if "Flags:" in line else []
        assert "runasoriginaluser" in flags, f"Launch would inherit installer elevation: {line}"
