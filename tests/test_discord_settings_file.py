from star.discord_bot import __main__ as entry
from star.discord_bot.local_config import (
    SETTINGS_FILE, SETTINGS_TEMPLATE, ensure_settings_file, load_merged_env, parse_env_text)


def test_template_is_created_once_and_parses(tmp_path):
    env = {"STAR_DISCORD_CONFIG_DIR": str(tmp_path / ".star")}
    assert ensure_settings_file(env) is True
    path = tmp_path / ".star" / SETTINGS_FILE
    assert path.read_text(encoding="utf-8") == SETTINGS_TEMPLATE
    assert "TOKEN" not in SETTINGS_TEMPLATE.replace("the bot token goes in discord.env", "")
    parse_env_text(SETTINGS_TEMPLATE, origin=SETTINGS_FILE)
    load_merged_env(env)


def test_existing_file_is_never_overwritten(tmp_path):
    (tmp_path / SETTINGS_FILE).write_text("DISCORD_OWNER_ID=5\n", encoding="utf-8")
    assert ensure_settings_file({"STAR_DISCORD_CONFIG_DIR": str(tmp_path)}) is False
    assert (tmp_path / SETTINGS_FILE).read_text(encoding="utf-8") == "DISCORD_OWNER_ID=5\n"


def test_doctor_writes_template_under_temp_home(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("STAR_DISCORD_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["star.discord_bot", "doctor"])
    entry.main()
    assert (tmp_path / ".star" / SETTINGS_FILE).is_file()
    assert not (tmp_path / ".star" / "discord.env").exists()
