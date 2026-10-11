"""Offline regressions: the stand-in models guards/history, never executes real Luau."""
import asyncio
import json
from copy import deepcopy

import anyio
import pytest

from star import studio_loop as sl
from star.roblox_cloud import DENIED_PLACE_IDS
from star.studio_uncertainty import StudioUncertaintyStore
from tests.studio_fake import FakeStudio, text
from tests.test_studio_loop import opened, run


PATH = "ServerScriptService.Main"


def edit(fake, source="print('STAR')", before=""):
    return {"studio_id": fake.studio_id, "datamodel_type": "Edit", "file_path": PATH,
            "className": "Script", "edits": [{"old_string": before, "new_string": source}]}


def operation(fake, kind):
    if kind == "script":
        return "multi_edit", edit(fake)
    if kind == "luau":
        return "execute_luau", {"studio_id": fake.studio_id, "datamodel_type": "Edit", "code": "print('STAR')"}
    return "start_stop_play", {"studio_id": fake.studio_id, "is_start": True}


def raw_starts(fake):
    return [args for name, args in fake.calls if name == "start_stop_play" and args["is_start"]]


def stops(fake):
    return [args for name, args in fake.calls if name == "execute_luau" and args["code"].startswith("-- STAR:play-stop-bound ")]


@pytest.mark.parametrize("kind", ["script", "luau", "play"])
@pytest.mark.parametrize("switch", ["another_blank", "denied", "another_owned_place"])
def test_engine_guard_catches_target_switch_after_host_confirmation(kind, switch):
    fake = FakeStudio()
    studio = run(opened(fake, own_places=True, own_account_id=4242))

    def drift(current, _code):
        if switch == "another_blank":
            current.identity["session"] = "different-native-game:workspace"  # still 0/0, same window
        elif switch == "denied":
            current.identity["placeId"] = next(iter(DENIED_PLACE_IDS))
        else:
            current.identity.update(placeId=9001, gameId=7001, creatorId=4242)
    fake.before_native = drift
    name, args = operation(fake, kind)
    result = run(studio.call_tool(name, args))
    assert sl.result_failed(result) and fake.scripts == {} and not fake.playing
    assert fake.marker is False and not fake.history and not raw_starts(fake)
    assert studio.journal.entries  # uncertain dispatch remains visible
    fake.before_native = lambda *_: None
    again = run(studio.call_tool(*operation(fake, "luau")))
    assert sl.result_failed(again)


@pytest.mark.parametrize("kind", ["script", "luau", "play"])
def test_host_confirmation_distinguishes_two_unsaved_sessions_with_same_place_ids(kind):
    fake = FakeStudio()
    studio = run(opened(fake))
    fake.identity["session"] = "second-0-0-native-session:workspace"
    result = run(studio.call_tool(*operation(fake, kind)))
    assert sl.result_failed(result) and studio.verdict.kind == "changed"
    assert not studio.journal.entries and not fake.history and not raw_starts(fake)


@pytest.mark.parametrize("conflict", ["owner_source", "replaced_object", "changed_session"])
def test_editor_callback_rechecks_preimage_object_and_session(conflict):
    fake = FakeStudio()
    fake.marker = True
    fake.scripts[PATH] = {"class": "Script", "source": "print('before')"}
    studio = run(opened(fake))

    def intervene(current, path):
        if conflict == "owner_source":
            current.scripts[path]["source"] = "print('owner')"
        elif conflict == "replaced_object":
            current.scripts[path] = {"class": "Script", "source": "print('replacement')", "_id": "owner-script"}
        else:
            current.identity["session"] = "new-native-session:workspace"
    fake.on_script_callback = intervene
    result = run(studio.call_tool("multi_edit", edit(fake, "print('STAR')", "print('before')")))
    assert sl.result_failed(result)
    assert fake.scripts[PATH]["source"] != "print('STAR')"
    assert not studio.journal.entries[-1]["restorable"]
    assert sl.result_failed(run(studio.call_tool(*operation(fake, "luau"))))


@pytest.mark.parametrize("created", [False, True])
@pytest.mark.parametrize("conflict", ["source", "object", "newer_owner_history"])
def test_native_undo_preserves_owner_edits_and_distinct_history(created, conflict):
    fake = FakeStudio()
    if not created:
        fake.marker = True
        fake.scripts[PATH] = {"class": "Script", "source": "print('before')"}
    studio = run(opened(fake))
    result = run(studio.call_tool("multi_edit", edit(fake, "print('STAR')", "" if created else "print('before')")))
    assert not sl.result_failed(result)
    if conflict == "source":
        fake.scripts[PATH]["source"] = "print('owner')"
    elif conflict == "object":
        fake.scripts[PATH] = {"class": "Script", "source": "print('STAR')", "_id": "different-owner-object"}
    else:
        fake.owner_edit(lambda current: current.instances.update({"Workspace.Owner": {"class": "Part", "tags": set()}}))
    before = fake._snapshot()
    history = deepcopy(fake.history)
    undone = run(studio.undo())
    assert undone["undone"] == [] and undone["left"]
    assert fake._snapshot() == before and fake.history == history
    assert len(studio.journal.entries) == 1 and not studio.journal.entries[0]["known"]


@pytest.mark.parametrize("fault", ["engine_refusal", "no_effect", "error_reply", "lost_reply"])
def test_failed_or_uncertain_undo_retains_entry_and_does_not_replay(fault):
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool("multi_edit", edit(fake)))
    original = fake.call_tool
    dispatched = []

    async def broken(name, arguments=None):
        if name == "execute_luau" and "-- STAR:script-undo-cas" in arguments["code"]:
            dispatched.append(name)
            if fault == "error_reply":
                return text("undo failed", True)
            answer = await original(name, arguments)
            if fault == "lost_reply":
                raise RuntimeError("simulated transport loss after undo")
            return answer
        return await original(name, arguments)
    fake.undo_fail = fault == "engine_refusal"
    fake.undo_no_effect = fault == "no_effect"
    fake.call_tool = broken
    undone = run(studio.undo())
    assert undone["undone"] == [] and undone["left"]
    assert len(studio.journal.entries) == 1 and not studio.journal.entries[0]["known"]
    assert len(dispatched) == 1
    if fault != "lost_reply":
        assert fake.scripts[PATH]["source"] == "print('STAR')"
    else:
        assert PATH not in fake.scripts  # actual Undo happened; the missing reply is still unknown
    assert run(studio.undo())["undone"] == [] and len(dispatched) == 1
    assert sl.result_failed(run(studio.call_tool(*operation(fake, "luau"))))


def test_three_unique_history_entries_undo_newest_first_and_preserve_unrelated_objects():
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool("multi_edit", edit(fake)))
    fake.luau_effects = lambda _: [("Part", "Workspace.STAR")]
    run(studio.call_tool(*operation(fake, "luau")))
    run(studio.call_tool("multi_edit", edit(fake, "print('fixed')", "print('STAR')")))
    tags = [record["tag"] for record in fake.history]
    assert len(set(tags)) == 2  # existing Source-only update is in the Script Editor stack
    fake.instances["Workspace.Owner"] = {"class": "Part", "tags": set()}
    undone = run(studio.undo())
    assert len(undone["undone"]) == 3 and undone["left"] == []
    assert fake.history == [] and [record["tag"] for record in fake.redo] == tags[::-1]
    assert fake.scripts == {} and "Workspace.Owner" in fake.instances and "Workspace.STAR" not in fake.instances


@pytest.mark.parametrize("kind", ["script", "luau"])
def test_native_undo_postcondition_rejects_a_successful_no_effect_history_call(kind):
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool(*operation(fake, kind)))
    before = fake._snapshot()
    fake._undo = lambda _tag: True  # service says it returned normally, but did not undo anything
    outcome = run(studio.undo())
    assert outcome["undone"] == [] and outcome["left"]
    assert fake._snapshot() == before and len(studio.journal.entries) == 1


def test_cancelled_undo_is_unknown_before_dispatch_and_cannot_replay():
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool("multi_edit", edit(fake)))
    original = fake.call_tool

    async def cancelled(name, arguments=None):
        if name == "execute_luau" and "-- STAR:script-undo-cas" in arguments["code"]:
            assert not studio.journal.entries[0]["known"]
            await original(name, arguments)
            raise asyncio.CancelledError
        return await original(name, arguments)
    fake.call_tool = cancelled
    with pytest.raises(asyncio.CancelledError):
        run(studio.undo())
    assert PATH not in fake.scripts and len(studio.journal.entries) == 1
    assert not studio.journal.entries[0]["known"]
    assert studio.journal.report()["changes"][0]["undo"] == "Inspect the unconfirmed edit in Studio"
    assert run(studio.undo())["undone"] == []


def test_existing_source_undo_is_reverse_cas_and_data_model_history_does_not_restore_source():
    fake = FakeStudio()
    fake.marker = True
    fake.scripts[PATH] = {"class": "Script", "source": "print('before')", "_id": "original-script"}
    studio = run(opened(fake))
    run(studio.call_tool("multi_edit", edit(fake, "print('STAR')", "print('before')")))
    assert not fake.history
    assert studio.journal.report()["changes"][0]["undo"] == "Guarded reverse source edit"
    undone = run(studio.undo())
    assert undone["left"] == [] and undone["undone"] == ["restored script " + PATH]
    assert fake.scripts[PATH]["source"] == "print('before')" and fake.scripts[PATH]["_id"] == "original-script"
    assert fake.history == [] and fake.redo == []


@pytest.mark.parametrize("conflict", ["source", "object", "session"])
def test_reverse_source_cas_rechecks_owner_changes_during_callback(conflict):
    fake = FakeStudio()
    fake.marker = True
    fake.scripts[PATH] = {"class": "Script", "source": "print('before')"}
    studio = run(opened(fake))
    run(studio.call_tool("multi_edit", edit(fake, "print('STAR')", "print('before')")))

    def owner(current, path):
        if conflict == "source":
            current.scripts[path]["source"] = "print('owner')"
        elif conflict == "object":
            current.scripts[path] = {"class": "Script", "source": "print('replacement')", "_id": "replacement"}
        else:
            current.identity["session"] = "different-native-session:workspace"
    fake.on_script_callback = owner
    undone = run(studio.undo())
    assert undone["undone"] == [] and undone["left"]
    assert fake.scripts[PATH]["source"] != "print('before')"
    assert len(studio.journal.entries) == 1 and not studio.journal.entries[0]["known"]


@pytest.mark.parametrize("kind", ["script", "luau"])
@pytest.mark.parametrize("fault", ["cancelled", "lost_reply"])
def test_pending_journal_precedes_dispatch_and_survives_cancelled_or_lost_reply(kind, fault):
    fake = FakeStudio()
    studio = run(opened(fake))
    fake.luau_effects = lambda _: [("Part", "Workspace.STAR")]
    original = fake.call_tool
    dispatched = []

    async def interrupted(name, arguments=None):
        code = arguments.get("code", "")
        if name == "execute_luau" and code.startswith("-- STAR:bound "):
            assert studio.journal.entries and studio.journal.entries[-1]["known"] is False
            dispatched.append(name)
            await original(name, arguments)
            if fault == "cancelled":
                raise asyncio.CancelledError
            raise RuntimeError("response lost after applied write")
        return await original(name, arguments)
    fake.call_tool = interrupted
    if fault == "cancelled":
        with pytest.raises(asyncio.CancelledError):
            run(studio.call_tool(*operation(fake, kind)))
    else:
        assert sl.result_failed(run(studio.call_tool(*operation(fake, kind))))
    assert len(dispatched) == 1 and len(studio.journal.entries) == 1
    assert not studio.journal.entries[0]["known"]
    assert PATH in fake.scripts if kind == "script" else "Workspace.STAR" in fake.instances
    assert run(studio.undo())["undone"] == []
    assert sl.result_failed(run(studio.call_tool(*operation(fake, kind))))
    assert len(dispatched) == 1


@pytest.mark.parametrize("mode, expected", [("Edit", "Edit"), ("Play", "Playing"), ("Playing", "Playing")])
def test_anchored_real_state_field_is_supported(mode, expected):
    output = f"- Current Studio Mode: {mode}\n- Available DataModels: Edit\n- Focused DataModel in the viewport: Edit"
    assert sl._play_state(text(output)) == expected
    assert sl._play_state(text(output.replace("\n", "\r\n"))) == expected


@pytest.mark.parametrize("output", ["Playing", "- Available DataModels: Playing", "prefix - Current Studio Mode: Play",
                                    "- Current Studio Mode: Play blah", "- Current Studio Mode: Edit\n- Current Studio Mode: Playing",
                                    '{"other":"Playing"}', '{"playState":"Paused"}'])
def test_unknown_or_ambiguous_state_never_confirms_play(output):
    assert sl._play_state(text(output)) is None
    assert sl._play_state(text("- Current Studio Mode: Edit", True)) is None


def test_native_play_and_stop_work_with_captured_text_state_contract():
    fake = FakeStudio()
    fake._get_studio_state = lambda _: text("- Current Studio Mode: " + ("Play" if fake.playing else "Edit")
                                               + "\n- Available DataModels: Edit\n- Focused DataModel in the viewport: Edit")
    studio = run(opened(fake))
    report = run(sl.run_build_loop(studio, scripts=[{"path": PATH, "source": "print('STAR')"}]))
    assert report["ok"] and not fake.playing and len(stops(fake)) == 1 and not raw_starts(fake)
    sent = next(args["code"] for name, args in fake.calls if name == "execute_luau" and "-- STAR:play-bound" in args["code"])
    assert "ExecutePlayModeAsync" in sent and "starRequest" in sent and "tests.EditModeActive" in sent
    assert "timeout" not in sent


@pytest.mark.parametrize("fault", ["error_reply", "exception", "malformed_state", "image_missing"])
def test_required_initial_reads_fail_visibly_without_mutations(fault):
    fake = FakeStudio()
    studio = run(opened(fake))
    original = fake.call_tool

    async def broken(name, arguments=None):
        if fault == "exception" and name == "script_grep":
            raise RuntimeError("unreadable")
        if fault == "error_reply" and name == "search_game_tree":
            return text("unreadable", True)
        if fault == "malformed_state" and name == "get_studio_state":
            return text("unknown mode")
        if fault == "image_missing" and name == "screen_capture":
            return text("no image")
        return await original(name, arguments)
    fake.call_tool = broken
    report = run(sl.run_build_loop(studio, scripts=[{"path": PATH, "source": "print('STAR')"}]))
    assert not report["ok"] and report["stopped"]
    assert not fake.scripts and not fake.history and not raw_starts(fake)


@pytest.mark.parametrize("fault", ["error_reply", "exception"])
def test_unread_console_is_not_reported_as_clean_and_always_stops(fault):
    fake = FakeStudio()
    studio = run(opened(fake))
    original = fake.call_tool

    async def broken(name, arguments=None):
        if name == "get_console_output":
            if fault == "exception":
                raise RuntimeError("console transport failed")
            return text("console unavailable", True)
        return await original(name, arguments)
    fake.call_tool = broken
    report = run(sl.run_build_loop(studio, scripts=[{"path": PATH, "source": "print('STAR')"}]))
    step = next(step for step in report["steps"] if step["step"] == "playtest first")
    assert not report["ok"] and not step["ok"] and step["errors"] is None and not step["console_ok"]
    assert not fake.playing and len(stops(fake)) == 1


@pytest.mark.parametrize("fault", ["stop_refused", "stop_no_effect", "unknown_play_state", "never_started"])
def test_requested_play_is_not_success_and_stop_failure_is_visible(fault, monkeypatch):
    monkeypatch.setattr(sl, "PLAY_START_SECONDS", .015)
    monkeypatch.setattr(sl, "PLAY_STOP_SECONDS", .015)
    monkeypatch.setattr(sl, "PLAY_POLL_SECONDS", .001)
    fake = FakeStudio()
    studio = run(opened(fake))
    original = fake.call_tool

    async def broken(name, arguments=None):
        if name == "execute_luau" and arguments["code"].startswith("-- STAR:play-stop-bound "):
            if fault == "stop_refused":
                return text("stop refused", True)
            if fault == "stop_no_effect":
                pin = json.loads(arguments["code"].split("\n", 1)[0].split(" ", 2)[2])
                return text(sl.PLAY_STOP_MARK + json.dumps({"request": pin["request"], "session": pin["session"], "requested": True}))
        answer = await original(name, arguments)
        if name == "execute_luau" and "-- STAR:play-bound" in arguments["code"]:
            if fault == "never_started":
                fake.playing = False
            if fault == "unknown_play_state":
                fake._get_studio_state = lambda _: text("Playing somewhere, state unknown")
        return answer
    fake.call_tool = broken
    report = run(sl.run_build_loop(studio, scripts=[{"path": PATH, "source": "print('STAR')"}]))
    assert not report["ok"] and not raw_starts(fake)
    assert any(entry["kind"] == "playtest" and not entry["confirmed"] for entry in studio.journal.entries)
    assert sl.result_failed(run(studio.call_tool(*operation(fake, "luau"))))


@pytest.mark.parametrize("during", ["settle", "native_request"])
def test_asyncio_cancel_stops_once_and_preserves_unknown_launch(during):
    async def exercise():
        fake = FakeStudio()
        studio = await opened(fake)
        entered = asyncio.Event()
        original = fake.call_tool

        async def blocked(name, arguments=None):
            answer = await original(name, arguments)
            if during == "native_request" and name == "execute_luau" and "-- STAR:play-bound" in arguments["code"]:
                entered.set()
                await asyncio.Event().wait()
            return answer
        fake.call_tool = blocked

        async def settle():
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(sl.run_build_loop(studio, scripts=[], settle=settle))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not fake.playing and len(stops(fake)) == 1 and not raw_starts(fake)
        starts = [entry for entry in studio.journal.entries if entry["kind"] == "playtest" and entry["start"]]
        assert starts[0]["confirmed"] is (during == "settle")
        if during == "native_request":
            assert sl.result_failed(await studio.call_tool(*operation(fake, "luau")))
    run(exercise())


@pytest.mark.parametrize("during", ["settle", "native_request"])
def test_anyio_level_triggered_cancel_scope_cannot_interrupt_stop_cleanup(during):
    async def exercise():
        fake = FakeStudio()
        studio = await opened(fake)
        entered = anyio.Event()
        original = fake.call_tool
        cleanup_checkpoints = []

        async def checkpoints(name, arguments=None):
            if name == "execute_luau" and arguments["code"].startswith("-- STAR:play-stop-bound "):
                await anyio.sleep(0)
                cleanup_checkpoints.append("stop-dispatched")
            if name == "get_studio_state":
                await anyio.sleep(0)
            answer = await original(name, arguments)
            if during == "native_request" and name == "execute_luau" and "-- STAR:play-bound" in arguments["code"]:
                entered.set()
                await anyio.sleep_forever()
            return answer
        fake.call_tool = checkpoints

        async def settle():
            entered.set()
            await anyio.sleep_forever()
        async with anyio.create_task_group() as group:
            group.start_soon(lambda: sl.run_build_loop(studio, scripts=[], settle=settle))
            await entered.wait()
            group.cancel_scope.cancel()
        assert not fake.playing and len(stops(fake)) == 1
        assert cleanup_checkpoints == ["stop-dispatched"] and not studio._play_pending
    anyio.run(exercise, backend="asyncio")


def test_missing_native_identity_never_authorizes_zero_id_mutation():
    fake = FakeStudio()
    fake.identity["session"] = ""
    studio = run(opened(fake))
    result = run(studio.call_tool("multi_edit", edit(fake)))
    assert sl.result_failed(result) and not fake.scripts and not studio.journal.entries


def test_native_error_diagnostic_is_preserved_bounded_and_redacted_without_replay():
    fake = FakeStudio()
    studio = run(opened(fake))
    original = fake.call_tool
    calls = []

    async def failure(name, arguments=None):
        if name == "execute_luau" and "-- STAR:script-cas" in arguments["code"]:
            calls.append(name)
            return text("Assistant.ExecuteLuauTool:42: STAR could not begin an undo recording "
                        "password=private-example-token C:\\private\\folder https://private.example:1234/secret 203.0.113.9:99 "
                        + "x" * 1000, True)
        return await original(name, arguments)
    fake.call_tool = failure
    result = run(studio.call_tool("multi_edit", edit(fake)))
    diagnostic = studio.journal.entries[0]["diagnostic"]
    assert "could not begin an undo recording" in diagnostic and len(diagnostic) <= 500
    assert all(secret not in diagnostic for secret in ("private-example-token", "private.example", "203.0.113.9", "C:\\private"))
    assert diagnostic in sl.result_text(result)
    assert studio.journal.report()["changes"][0]["diagnostic"] == diagnostic
    assert sl.result_failed(run(studio.call_tool("multi_edit", edit(fake)))) and len(calls) == 1


@pytest.mark.parametrize("kind", ["script", "luau"])
def test_active_connector_recording_allows_confirmed_edit_but_never_automatic_history_undo(kind):
    fake = FakeStudio()
    fake.connector_recording = True
    fake.luau_effects = lambda _: [("Part", "Workspace.STAR")]
    studio = run(opened(fake))
    result = run(studio.call_tool(*operation(fake, kind)))
    assert not sl.result_failed(result)
    entry = studio.journal.entries[-1]
    assert entry["known"] and entry["ok"] and not entry["recorded"] and entry["connector_recorded"]
    assert fake.history[-1]["tag"].startswith("Assistant ")
    assert studio.journal.report()["changes"][-1]["undo"] == "Manual Studio history (connector recording)"
    history = deepcopy(fake.history)
    snapshot = fake._snapshot()
    undone = run(studio.undo())
    assert undone["undone"] == [] and undone["left"]
    assert fake._snapshot() == snapshot and fake.history == history
    assert not any("-- STAR:script-undo-cas" in args.get("code", "")
                   or "-- STAR:recording-undo" in args.get("code", "") for _, args in fake.calls)


def test_connector_owned_script_creation_followed_by_source_edit_and_reverse_cas():
    fake = FakeStudio()
    fake.connector_recording = True
    studio = run(opened(fake))
    assert not sl.result_failed(run(studio.call_tool("multi_edit", edit(fake))))
    assert not sl.result_failed(run(studio.call_tool("multi_edit", edit(fake, "print('new')", "print('STAR')"))))
    assert studio.journal.entries[-1]["restorable"]
    # This unrelated owner history is deliberately preserved. Source restoration
    # has its own exact CAS and makes no claim to undo the connector's history.
    fake.owner_edit(lambda current: current.instances.update({"Workspace.Owner": {"class": "Part", "tags": set()}}))
    undone = run(studio.undo())
    assert undone["undone"] == ["restored script " + PATH] and undone["left"]
    assert fake.scripts[PATH]["source"] == "print('STAR')" and "Workspace.Owner" in fake.instances
    assert len(studio.journal.entries) == 1 and studio.journal.entries[0]["created"]


@pytest.mark.parametrize("kind", ["script", "luau"])
def test_no_owned_or_active_connector_recording_refuses_before_any_mutation(kind):
    fake = FakeStudio()
    fake.recording_available = False
    fake.luau_effects = lambda _: [("Part", "Workspace.STAR")]
    studio = run(opened(fake))
    result = run(studio.call_tool(*operation(fake, kind)))
    assert sl.result_failed(result) and not fake.marker and not fake.history and not fake.scripts
    assert "Workspace.STAR" not in fake.instances and studio.journal.entries[-1]["known"] is False


def test_connector_owned_loop_builds_and_stops_with_truthful_manual_history():
    fake = FakeStudio()
    fake.connector_recording = True
    studio = run(opened(fake))
    report = run(sl.run_build_loop(studio, scripts=[{"path": PATH, "source": "print('STAR')"}]))
    assert report["ok"] and not fake.playing
    assert report["changes"]["changes"][0]["undo"] == "Manual Studio history (connector recording)"


@pytest.mark.parametrize("kind", ["script", "luau", "play"])
def test_durable_pending_exists_before_native_dispatch_and_exact_success_clears_it(tmp_path, kind):
    fake = FakeStudio()
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    original = fake.call_tool
    dispatched = []

    async def witness(name, arguments=None):
        if name == "execute_luau" and arguments["code"].startswith("-- STAR:bound "):
            pending = store.pending(studio._uncertainty_scope)
            assert len(pending) == 1 and pending[0]["kind"] == {"script": "script", "luau": "luau", "play": "play_start"}[kind]
            dispatched.append(name)
        return await original(name, arguments)
    fake.call_tool = witness
    assert not sl.result_failed(run(studio.call_tool(*operation(fake, kind))))
    assert len(dispatched) == 1 and store.pending(studio._uncertainty_scope) == []
    if kind == "play":
        assert not sl.result_failed(run(studio.call_tool("start_stop_play", {"studio_id": fake.studio_id, "is_start": False})))


@pytest.mark.parametrize("kind", ["script", "luau", "play"])
@pytest.mark.parametrize("fault", ["lost_reply", "cancelled"])
def test_uncertainty_survives_new_guard_and_connector_id_then_blocks_replay(tmp_path, kind, fault):
    fake = FakeStudio()
    path = tmp_path / "uncertainty.sqlite3"
    store = StudioUncertaintyStore(path)
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    original = fake.call_tool
    count = []

    async def interrupted(name, arguments=None):
        answer = await original(name, arguments)
        if name == "execute_luau" and arguments["code"].startswith("-- STAR:bound "):
            count.append(name)
            if fault == "cancelled":
                raise asyncio.CancelledError
            raise RuntimeError("lost reply after native action")
        return answer
    fake.call_tool = interrupted
    if fault == "cancelled":
        with pytest.raises(asyncio.CancelledError):
            run(studio.call_tool(*operation(fake, kind)))
    else:
        assert sl.result_failed(run(studio.call_tool(*operation(fake, kind))))
    assert len(store.pending(studio._uncertainty_scope)) == 1 and len(count) == 1
    fake.call_tool = original
    fake.studio_id = "new-transient-connector-id"
    replacement = run(opened(fake, uncertainty_store=StudioUncertaintyStore(path), route="local_pc"))
    assert replacement.journal.entries == [] and replacement._uncertainty_scope == studio._uncertainty_scope
    before = fake._snapshot()
    denied = run(replacement.call_tool(*operation(fake, "script")))
    assert sl.result_failed(denied) and "acknowledgement" in sl.result_text(denied)
    assert fake._snapshot() == before
    assert not sl.result_failed(run(replacement.call_tool("get_studio_state", {"studio_id": fake.studio_id})))
    if kind == "play":
        assert not fake.playing  # original cancellation/lost request cleanup ran
    assert len(store.pending(studio._uncertainty_scope)) == 1  # confirmed stop does not erase uncertain launch


def test_durable_undo_pending_survives_lost_reply_and_reconnection(tmp_path):
    fake = FakeStudio()
    path = tmp_path / "uncertainty.sqlite3"
    store = StudioUncertaintyStore(path)
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    run(studio.call_tool("multi_edit", edit(fake)))
    original = fake.call_tool

    async def lost(name, arguments=None):
        if name == "execute_luau" and "-- STAR:script-undo-cas" in arguments["code"]:
            assert store.pending(studio._uncertainty_scope)[0]["kind"] == "undo"
            await original(name, arguments)
            raise RuntimeError("undo applied but response lost")
        return await original(name, arguments)
    fake.call_tool = lost
    assert run(studio.undo())["left"] and PATH not in fake.scripts
    fake.call_tool = original
    replacement = run(opened(fake, uncertainty_store=StudioUncertaintyStore(path), route="local_pc"))
    assert sl.result_failed(run(replacement.call_tool("multi_edit", edit(fake))))
    assert store.pending(studio._uncertainty_scope)[0]["kind"] == "undo"


@pytest.mark.parametrize("kind", ["script", "luau", "play"])
def test_durable_confirmation_failure_is_visible_and_keeps_pending(tmp_path, kind):
    class FailingConfirmation(StudioUncertaintyStore):
        def confirm(self, *args, **kwargs):
            raise OSError("private host/path must not reach model")
    fake = FakeStudio()
    store = FailingConfirmation(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    result = run(studio.call_tool(*operation(fake, kind)))
    assert sl.result_failed(result) and "durable confirmation" in sl.result_text(result)
    assert "private host/path" not in sl.result_text(result)
    assert len(store.pending(studio._uncertainty_scope)) == 1
    assert sl.result_failed(run(studio.call_tool(*operation(fake, "script"))))
    if kind == "play":
        assert not fake.playing and len(stops(fake)) == 1


@pytest.mark.parametrize("binding", ["route_missing", "route_invalid", "session_missing"])
def test_invalid_durable_binding_refuses_writes_but_allows_reads(tmp_path, binding):
    fake = FakeStudio()
    if binding == "session_missing":
        fake.identity["session"] = ""
    route = None if binding == "route_missing" else "unconfigured-route" if binding == "route_invalid" else "local_pc"
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route=route))
    result = run(studio.call_tool("multi_edit", edit(fake)))
    assert sl.result_failed(result) and "binding" in sl.result_text(result) and not fake.scripts
    assert not sl.result_failed(run(studio.call_tool("get_studio_state", {"studio_id": fake.studio_id})))


def test_corrupt_durable_store_refuses_writes_without_preventing_stop_or_reads(tmp_path):
    path = tmp_path / "uncertainty.sqlite3"
    fake = FakeStudio()
    studio = run(opened(fake, uncertainty_store=StudioUncertaintyStore(path), route="local_pc"))
    assert not sl.result_failed(run(studio.call_tool(*operation(fake, "play"))))
    path.write_bytes(b"not a sqlite ledger")
    assert sl.result_failed(run(studio.call_tool("multi_edit", edit(fake)))) and not fake.scripts
    assert not sl.result_failed(run(studio.call_tool("get_studio_state", {"studio_id": fake.studio_id})))
    assert not sl.result_failed(run(studio.call_tool("start_stop_play", {"studio_id": fake.studio_id, "is_start": False})))
    assert not fake.playing and path.read_bytes() == b"not a sqlite ledger"


def test_successful_guarded_source_undo_confirms_its_own_durable_token(tmp_path):
    fake = FakeStudio()
    fake.connector_recording = True
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    run(studio.call_tool("multi_edit", edit(fake)))
    run(studio.call_tool("multi_edit", edit(fake, "print('new')", "print('STAR')")))
    original = fake.call_tool
    witnessed = []

    async def witness(name, arguments=None):
        if name == "execute_luau" and "-- STAR:script-undo-cas" in arguments["code"]:
            witnessed.append(store.pending(studio._uncertainty_scope)[0]["kind"])
        return await original(name, arguments)
    fake.call_tool = witness
    outcome = run(studio.undo())
    assert outcome["undone"] == ["restored script " + PATH] and witnessed == ["undo"]
    assert store.pending(studio._uncertainty_scope) == []


@pytest.mark.parametrize("foreign", ["place", "universe", "creator", "creator_type", "blank_session", "nonce", "no_args"])
def test_cleanup_never_ends_a_foreign_server_test(foreign, tmp_path):
    fake = FakeStudio()
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    assert not sl.result_failed(run(studio.call_tool(*operation(fake, "play"))))
    if foreign in {"place", "universe", "creator", "creator_type"}:
        key, value = {"place": ("placeId", 91), "universe": ("gameId", 92),
                      "creator": ("creatorId", 93), "creator_type": ("creatorType", "Group")}[foreign]
        fake.identity[key] = value
    elif foreign == "blank_session":
        fake.identity["session"] = "another-blank:workspace"
        fake.test_args["starSession"] = fake.identity["session"]
    elif foreign == "nonce":
        fake.test_args["starRequest"] = "StarEdit_ffffffff"
    else:
        fake.test_args = None
    result = run(studio.call_tool("start_stop_play", {"studio_id": fake.studio_id, "is_start": False}))
    assert sl.result_failed(result) and fake.playing and studio._play_pending
    assert not stops(fake) and not raw_starts(fake)
    assert store.pending(studio._uncertainty_scope) == []  # no EndTest dispatch


def test_stop_rechecks_foreign_nonce_inside_native_call_after_readonly_probe(tmp_path):
    fake = FakeStudio()
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    run(studio.call_tool(*operation(fake, "play")))

    def switch_after_probe(studio_fake, code):
        if code.startswith("-- STAR:play-stop-bound "):
            studio_fake.test_args["starRequest"] = "foreign-test"
    fake.before_native = switch_after_probe
    result = run(studio.call_tool("start_stop_play", {"studio_id": fake.studio_id, "is_start": False}))
    assert sl.result_failed(result) and fake.playing and len(stops(fake)) == 1
    assert store.pending(studio._uncertainty_scope)[0]["kind"] == "play_stop"
    assert sl.result_failed(run(studio._stop_cleanup())) and len(stops(fake)) == 1


def test_native_stop_uses_frozen_launch_identity_when_current_verdict_changes():
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool(*operation(fake, "play")))
    original = studio._play_identity
    changed = sl.PlaceIdentity(12, 13, 14, "Group", "Different", 0, True, "other:workspace")
    studio.verdict = sl.Verdict(False, "changed", "another place", changed)
    result = run(studio.call_tool("start_stop_play", {"studio_id": fake.studio_id, "is_start": False}))
    assert not sl.result_failed(result) and not fake.playing
    payload = json.loads(stops(fake)[0]["code"].split("\n", 1)[0].split(" ", 2)[2])
    assert payload["session"] == original.session and payload["placeId"] == original.place_id
    assert "GetTestArgs()" in stops(fake)[0]["code"] and "IsServer()" in stops(fake)[0]["code"]
    assert "EndTest({ starStopped = expected.request, starSession = expected.session })" in stops(fake)[0]["code"]


@pytest.mark.parametrize("readiness_text", ["Target is not reachable", "Target is not reachable (createExecuteLuauBridge_loadCodeAsync, Server)"])
def test_server_readiness_retries_only_fixed_readonly_probe_then_one_endtest(monkeypatch, readiness_text):
    monkeypatch.setattr(sl, "PLAY_POLL_SECONDS", .001)
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool(*operation(fake, "play")))
    fake.server_unreachable_reads = 3
    fake.server_unreachable_text = readiness_text
    before = len(fake.calls)
    result = run(studio._stop_cleanup())
    probes = [args for name, args in fake.calls[before:] if name == "execute_luau" and args["code"].startswith("-- STAR:play-stop-probe ")]
    assert not sl.result_failed(result) and not fake.playing and len(probes) == 4 and len(stops(fake)) == 1
    assert not [args for name, args in fake.calls if name == "start_stop_play"]


def test_start_waits_for_captured_native_server_readiness_and_confirms_exact_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "PLAY_POLL_SECONDS", .001)
    fake = FakeStudio()
    fake.server_unreachable_text = "Target is not reachable (createExecuteLuauBridge_loadCodeAsync, Server)"
    fake.server_unreachable_reads = 3
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    assert not sl.result_failed(run(studio.call_tool(*operation(fake, "play"))))
    probes = [args for name, args in fake.calls if name == "execute_luau" and args["code"].startswith("-- STAR:play-stop-probe ")]
    assert fake.playing and studio._play_entry["confirmed"] and len(probes) == 4
    assert store.pending(studio._uncertainty_scope) == []
    assert not sl.result_failed(run(studio._stop_cleanup()))


@pytest.mark.parametrize("foreign", ["blank_session", "nonce", "target", "no_args"])
def test_foreign_playing_cannot_confirm_native_start_or_release_its_pending_token(tmp_path, foreign):
    fake = FakeStudio()
    def foreign_play(studio_fake):
        if foreign == "blank_session":
            studio_fake.identity["session"] = "other-blank:workspace"
            studio_fake.test_args["starSession"] = "other-blank:workspace"
        elif foreign == "nonce":
            studio_fake.test_args["starRequest"] = "foreign-test"
        elif foreign == "target":
            studio_fake.identity["placeId"] = 91
        else:
            studio_fake.test_args = None
    fake.on_play = foreign_play
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    result = run(studio.call_tool(*operation(fake, "play")))
    assert sl.result_failed(result) and fake.playing and not studio._play_entry["confirmed"]
    assert store.pending(studio._uncertainty_scope)[0]["kind"] == "play_start"
    assert not stops(fake) and not raw_starts(fake)


def test_server_readiness_timeout_never_dispatches_endtest(monkeypatch):
    monkeypatch.setattr(sl, "PLAY_POLL_SECONDS", .001)
    monkeypatch.setattr(sl, "PLAY_STOP_SECONDS", .01)
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool(*operation(fake, "play")))
    fake.server_unreachable_reads = 100000
    assert sl.result_failed(run(studio._stop_cleanup())) and fake.playing and not stops(fake)


@pytest.mark.parametrize("foreign_edit", [False, True])
def test_already_edit_cleanup_verifies_original_native_session_without_stop(foreign_edit):
    fake = FakeStudio()
    studio = run(opened(fake))
    run(studio.call_tool(*operation(fake, "play")))
    fake.playing = False
    if foreign_edit:
        fake.identity["session"] = "other-blank:workspace"
    result = run(studio._stop_cleanup())
    assert sl.result_failed(result) is foreign_edit and not stops(fake)
    assert studio._play_pending is foreign_edit


def test_fresh_guard_cannot_stop_foreign_play_without_original_request():
    fake = FakeStudio()
    studio = run(opened(fake))
    fake.playing = True
    fake.test_args = {"starSession": fake.identity["session"], "starRequest": "foreign"}
    assert sl.result_failed(run(studio._stop_cleanup())) and fake.playing and not stops(fake)


@pytest.mark.parametrize("fault", ["lost_reply", "malformed_receipt", "wrong_edit_session", "cancelled"])
def test_dispatched_endtest_uncertainty_survives_reconnect_and_never_replays(tmp_path, fault):
    async def exercise():
        fake = FakeStudio()
        path = tmp_path / "uncertainty.sqlite3"
        store = StudioUncertaintyStore(path)
        studio = await opened(fake, uncertainty_store=store, route="local_pc")
        await studio.call_tool(*operation(fake, "play"))
        original = fake.call_tool

        async def broken(name, arguments=None):
            if name == "execute_luau" and arguments["code"].startswith("-- STAR:play-stop-bound "):
                assert store.pending(studio._uncertainty_scope)[0]["kind"] == "play_stop"
                answer = await original(name, arguments)
                if fault == "cancelled":
                    raise asyncio.CancelledError
                if fault == "lost_reply":
                    raise RuntimeError("native stop happened, receipt lost")
                if fault == "malformed_receipt":
                    return text("STAR_STOP {}")
                fake.identity["session"] = "different-blank:workspace"
                return answer
            return await original(name, arguments)
        fake.call_tool = broken
        args = {"studio_id": fake.studio_id, "is_start": False}
        if fault == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await studio.call_tool("start_stop_play", args)
        else:
            assert sl.result_failed(await studio.call_tool("start_stop_play", args))
        assert not fake.playing and len(stops(fake)) == 1
        assert store.pending(studio._uncertainty_scope)[0]["kind"] == "play_stop"
        assert sl.result_failed(await studio.call_tool("start_stop_play", args)) and len(stops(fake)) == 1
        fake.call_tool = original
        # Scope-preserving reconnect retains the barrier even if the connector ID changes.
        fake.identity["session"] = studio._play_identity.session
        fake.studio_id = "replacement-connector-id"
        replacement = await opened(fake, uncertainty_store=StudioUncertaintyStore(path), route="local_pc")
        assert sl.result_failed(await replacement.call_tool(*operation(fake, "script")))
        assert len(stops(fake)) == 1
    run(exercise())


@pytest.mark.parametrize("name, payload", [
    ("character_navigation", {"x": 1, "y": 2, "z": 3}),
    ("user_keyboard_input", {"actions": [{"action": "keyPress", "key_code": "W"}]}),
    ("user_mouse_input", {"actions": [{"action": "mouseButtonClick", "mouse_button": "left", "x": 1, "y": 2}]}),
])
@pytest.mark.parametrize("state", ["own_play", "foreign_play", "edit"])
def test_unbound_playtest_input_is_refused_without_any_native_dispatch(name, payload, state, tmp_path):
    fake = FakeStudio()
    store = StudioUncertaintyStore(tmp_path / "uncertainty.sqlite3")
    studio = run(opened(fake, uncertainty_store=store, route="local_pc"))
    if state != "edit":
        assert not sl.result_failed(run(studio.call_tool(*operation(fake, "play"))))
        if state == "foreign_play":
            fake.identity["session"] = "other-blank:workspace"
            fake.test_args = {"starSession": "other-blank:workspace", "starRequest": "foreign"}
    before = len(fake.calls)
    journal = deepcopy(studio.journal.entries)
    result = run(studio.call_tool(name, {"studio_id": fake.studio_id, "datamodel_type": "Client", **payload}))
    assert sl.result_failed(result) and "temporarily unavailable" in sl.result_text(result)
    assert len(fake.calls) == before and studio.journal.entries == journal
    assert store.pending(studio._uncertainty_scope) == []
