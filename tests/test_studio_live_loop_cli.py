"""The acceptance CLI uses isolated settings and STAR MCP; no live connections."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from scripts import studio_live_loop as cli
from star import studio_loop
from star.studio import StudioTransportError
from tests.studio_fake import FakeStudio, text


def edit_args(tmp_path, *extra):
    return cli.parse_arguments(["--edit", "--studio", "exact-studio", "--state-dir", str(tmp_path / "state"), *extra])


@pytest.mark.parametrize("argv", [
    ["--edit"], ["--edit", "--studio", "exact-studio"],
    ["--edit", "--studio", "exact-studio", "--state-dir", "relative"],
    ["--studio", "exact-studio"], ["--undo"], ["--keep"],
    ["--target", "auto"], ["--wait", "nan"], ["--wait", "inf"],
    ["--wait", "-inf"], ["--wait", "-0.1"], ["--wait", "30.1"], ["--wait", "bad"],
])
def test_invalid_cli_grants_and_waits_are_rejected_before_connection(argv):
    with pytest.raises(SystemExit) as error:
        cli.parse_arguments(argv)
    assert error.value.code == 2


@pytest.mark.parametrize("wait", ["0", "30"])
def test_boundary_waits_are_valid_and_recovery_requires_opt_in(tmp_path, wait):
    arguments = edit_args(tmp_path, "--wait", wait)
    assert arguments.wait == float(wait) and arguments.undo is False
    assert arguments.state_dir.is_absolute()
    assert edit_args(tmp_path, "--undo").undo is True


@pytest.mark.parametrize("route", ["local_pc", "host_launcher"])
@pytest.mark.parametrize("studios", [[], [{"id": "first"}, {"id": "second"}]])
def test_discovery_crosses_own_mcp_without_selecting_or_loading_profile(monkeypatch, capsys, route, studios):
    calls = []
    async def discover(**kwargs):
        calls.append(kwargs)
        return {"status": "tools_and_instances_discovered" if studios else "tools_discovered_no_instances",
                "studios": studios, "selected": None, "local_mcp": "memory", "target": route}
    def forbidden(*args, **kwargs):
        pytest.fail("discovery selected/edited an instance or loaded an app profile")
    monkeypatch.setattr(cli.local_mcp, "discover", discover)
    monkeypatch.setattr(cli.local_mcp, "connect_studio", forbidden)
    monkeypatch.setattr(cli.Settings, "load", forbidden)
    code = asyncio.run(cli.main(cli.parse_arguments(["--target", route])))
    assert code == (0 if studios else 2) and calls == [{"target": route}]
    output = capsys.readouterr().out
    assert '"selected": null' in output and "no instance selected or edited" in output


@pytest.mark.parametrize("route", ["local_pc", "host_launcher"])
@pytest.mark.parametrize("undo", [False, True])
def test_edit_uses_fresh_host_settings_explicit_persistent_state_and_truthful_loop_result(monkeypatch, tmp_path, route, undo):
    captured = {}
    identity = studio_loop.PlaceIdentity(0, 0, 0, "User", "Blank", 0, False, "native:workspace")
    connection = SimpleNamespace(verdict=studio_loop.Verdict(True, "blank", "approved", identity))
    @asynccontextmanager
    async def connect(settings, home):
        captured.update(settings=settings, home=home)
        yield connection
    async def loop(guarded, **kwargs):
        assert guarded is connection
        captured["loop"] = kwargs
        assert kwargs["scripts"][0]["source"] == cli.BROKEN and kwargs["luau_edits"] == [cli.BUILD]
        assert kwargs["fix"](["observed error"])[0]["source"] == cli.FIXED
        await kwargs["settle"]()
        return {"ok": not undo, "undo": {"left": ["manual connector history"]} if undo else None}
    monkeypatch.setattr(cli.local_mcp, "connect_studio", connect)
    monkeypatch.setattr(cli.studio_loop, "run_build_loop", loop)
    monkeypatch.setattr(cli.Settings, "load", lambda *args: pytest.fail("CLI loaded app settings"))
    args = edit_args(tmp_path, "--target", route, "--wait", "0", *( ["--undo"] if undo else [] ))
    code = asyncio.run(cli.main(args))
    settings = captured["settings"]
    assert settings.studio_target == route and settings.studio_id == "exact-studio"
    assert settings.studio_edit is True and settings.studio_luau is True and settings.studio_own_places is False
    assert captured["home"] == tmp_path / "state" and captured["loop"]["undo_at_end"] is undo
    assert code == (1 if undo else 0)


@pytest.mark.parametrize("editable, kind, place, universe", [
    (False, "blank", 0, 0), (True, "own", 12, 13),
    (True, "blank", 12, 0), (True, "blank", 0, 13),
])
def test_cli_never_builds_in_published_or_unapproved_targets(monkeypatch, tmp_path, editable, kind, place, universe):
    identity = studio_loop.PlaceIdentity(place, universe, 0, "User", "Target", 0, True, "native:workspace")
    @asynccontextmanager
    async def connect(*args):
        yield SimpleNamespace(verdict=studio_loop.Verdict(editable, kind, "reason", identity))
    monkeypatch.setattr(cli.local_mcp, "connect_studio", connect)
    monkeypatch.setattr(cli.studio_loop, "run_build_loop", lambda *args, **kwargs: pytest.fail("CLI built in forbidden target"))
    assert asyncio.run(cli.main(edit_args(tmp_path))) == 3


def test_cli_actual_own_mcp_keeps_required_screenshot_failure_before_any_edit(monkeypatch, tmp_path, capsys):
    fake = FakeStudio(studio_id="exact-studio")
    fake._screen_capture = lambda _: text("native viewport capture unavailable", True)
    routes = []
    @asynccontextmanager
    async def remote(*, target):
        routes.append(target)
        yield fake
    monkeypatch.setattr(cli.local_mcp.studio, "connect", remote)
    monkeypatch.setattr(cli.studio_loop, "own_account_id", lambda *args: pytest.fail("blank-only CLI looked up a credential/account"))
    monkeypatch.setattr(cli.Settings, "load", lambda *args: pytest.fail("CLI loaded actual app profile"))
    assert asyncio.run(cli.main(edit_args(tmp_path, "--wait", "0"))) == 1
    assert routes == ["local_pc"] and not fake.scripts and not fake.history and not fake.playing
    assert not [args for name, args in fake.calls if name == "execute_luau" and args["code"].startswith("-- STAR:bound ")]
    assert not [name for name, _ in fake.calls if name == "start_stop_play"]
    assert '"ok": false' in capsys.readouterr().out


def test_transport_failure_reports_failure_without_route_fallback(monkeypatch, capsys):
    calls = []
    async def discover(*, target):
        calls.append(target)
        raise StudioTransportError("configured Studio route unavailable")
    monkeypatch.setattr(cli.local_mcp, "discover", discover)
    assert asyncio.run(cli.main(cli.parse_arguments(["--target", "host_launcher"]))) == 2
    assert calls == ["host_launcher"] and "unavailable" in capsys.readouterr().out
