"""Native producers -> staged evidence -> existing digest timer, entirely offline."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import base64
import struct

from PIL import Image, PngImagePlugin
import pytest

from star.discord_bot.core import AccessPolicy
from star.discord_bot.digest_task import DigestConfig, check_and_send
from star.discord_bot.lab_status import LabSettings, read_receipt, read_capture, parse_receipt
from star.discord_bot.learning_sender import DeliveryLedger
from star.discord_bot.native_evidence import (atomic_file, emit, encoded, publish_blender,
                                              publish_studio, read_bounded, stage)
from star.discord_bot.task_events import load_event

NOW = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)
STAMP = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def png():
    out = BytesIO()
    meta = PngImagePlugin.PngInfo()
    meta.add_text("private_metadata", "must never leave the producer")
    Image.new("RGB", (32, 32), "blue").save(out, format="PNG", pnginfo=meta)
    return out.getvalue()


def receipt(**changes):
    value = dict(version=2, job_id="job-1", engine="roblox-studio", state="completed", phase="verifying",
                 task="DoorTest", next_step="Review candidate", checked=2, total=2, evidence="native-studio",
                 updated_at=STAMP, build_sha256="a" * 64, iteration=2, source="playtest-learning",
                 camera="", captured_at="")
    return value | changes


def config(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    env = {"STAR_DISCORD_LEARNING_DM_OPT_IN": "1", "STAR_DISCORD_EVIDENCE_DIRECTORY": str(shared),
           "STAR_DISCORD_EVIDENCE_REVIEWS": str(reviews), "STAR_DISCORD_LEARNING_STATE": str(tmp_path / "sent.sqlite3")}
    return DigestConfig.from_env(env, policy=AccessPolicy(frozenset({123}), frozenset()))


def send_tick(cfg, now=NOW, *, fail=False):
    sent = []
    async def send(body, image):
        if fail:
            raise TimeoutError("offline fake")
        sent.append((body, image))
    return asyncio.run(check_and_send(cfg, send, now=now)), sent


def test_opt_in_owner_and_review_boundary(tmp_path, monkeypatch):
    assert not DigestConfig.from_env({"STAR_DISCORD_EVIDENCE_DIRECTORY": str(tmp_path)}).enabled
    cfg = config(tmp_path)
    assert cfg.enabled and cfg.owner_id == 123 and not cfg.ssh_target
    env = {"STAR_DISCORD_LEARNING_DM_OPT_IN": "1", "STAR_DISCORD_EVIDENCE_DIRECTORY": str(tmp_path),
           "STAR_DISCORD_LEARNING_DM_OWNER_ID": "999"}
    with pytest.raises(PermissionError):
        DigestConfig.from_env(env, policy=AccessPolicy(frozenset({123}), frozenset()))
    env.pop("STAR_DISCORD_LEARNING_DM_OWNER_ID")
    env["STAR_DISCORD_EVIDENCE_REVIEWS"] = str(tmp_path / "nested")
    with pytest.raises(ValueError, match="separate"):
        DigestConfig.from_env(env, policy=AccessPolicy(frozenset({123}), frozenset()))
    monkeypatch.delenv("STAR_DISCORD_EVIDENCE_PRODUCER", raising=False)
    emit("playtest-learning", {}, tmp_path)  # disabled path does not inspect the malformed report
    assert not (tmp_path / "latest.json").exists()
    assert send_tick(replace(cfg, enabled=False))[0]["state"] == "disabled"


def test_atomic_capture_hash_metadata_and_stale_timestamp(tmp_path):
    cfg = config(tmp_path)
    rec = receipt(capture_kind="studio-viewport", camera="front", captured_at=STAMP)
    event = stage(cfg.evidence_directory, rec, capture=png(), event=True)
    settings = LabSettings(True, cfg.evidence_directory / "latest.json")
    native = read_receipt(settings)
    raw = (cfg.evidence_directory / native.capture_file).read_bytes()
    assert sha256(raw).hexdigest() == native.capture_sha256
    assert b"private_metadata" not in raw
    assert "front" == native.camera and native.build_sha256 == "a" * 64
    assert read_capture(settings, now=NOW)[0] == "star-lab.jpg"
    assert load_event(cfg.evidence_directory / "events" / (event + ".json"), now=NOW)[0] == event
    with pytest.raises(ValueError, match="stale"):
        read_capture(settings, now=NOW + timedelta(minutes=16))
    (cfg.evidence_directory / native.capture_file).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="matches"):
        read_capture(settings, now=NOW)


@pytest.mark.parametrize("change", [dict(build_sha256="bad"), dict(source="model"), dict(iteration=True),
                                    dict(source="blender-worker"), dict(camera="../x", captured_at=STAMP),
                                    dict(capture_file="../private.png")])
def test_native_schema_rejects_bad_metadata(change):
    with pytest.raises(ValueError):
        parse_receipt(encoded(receipt(**change)))


def test_bad_image_cannot_replace_current_manifest(tmp_path):
    stage(tmp_path, receipt())
    before = (tmp_path / "latest.json").read_bytes()
    with pytest.raises(ValueError):
        stage(tmp_path, receipt(capture_kind="studio-viewport", camera="front", captured_at=STAMP), capture=b"not an image")
    assert (tmp_path / "latest.json").read_bytes() == before
    older = receipt(job_id="older", updated_at="2026-10-16T14:00:00Z")
    stage(tmp_path, older)
    assert (tmp_path / "latest.json").read_bytes() == before
    path = tmp_path / "immutable.json"
    atomic_file(path, b"first", immutable=True)
    with pytest.raises(ValueError, match="collision"):
        atomic_file(path, b"other", immutable=True)
    assert path.read_bytes() == b"first"


def test_symlink_ancestor_and_file_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "alias"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="links"):
        stage(link, receipt())
    target = real / "file.json"
    target.write_bytes(b"{}")
    with pytest.raises(ValueError, match="links"):
        read_bounded(link / "file.json", 100)


def play_report():
    return {"run": "native-1", "game": "DoorTest", "finished": STAMP,
            "passed": True, "lesson": {"text": "model prose must not be sent", "reviewed": True},
            "iterations": [{"index": 2, "build_sha256": "a" * 64, "apply": {"ok": True},
                            "playtest": {"started": True, "stopped": True, "errors": {}},
                            "robot": {"started": True, "finished": True, "ok": True,
                                      "checks": [{"ok": True}, {"ok": True}]},
                            "report": {"passed": True, "failures": []}}]}


def test_native_checks_drive_events_not_model_lesson(tmp_path):
    cfg = config(tmp_path)
    report = play_report()
    event_id = publish_studio(cfg.evidence_directory, report, tmp_path, playtest=True)
    assert event_id
    result, sent = send_tick(cfg)
    assert result["sent"] and len(sent) == 1 and sent[0][1] is None
    body = sent[0][0]
    assert "DoorTest" in body and "robot playtest" in body and "pending" in body
    assert "model prose" not in body and "no model weights" in body
    from star.discord_bot.digest_task import ledger_state
    assert ledger_state(cfg).startswith("last native task: sent")
    assert not send_tick(cfg, NOW + timedelta(days=1))[1]  # durable across new connections
    report["run"] = "robot-broken"
    report["iterations"][0]["robot"]["finished"] = False
    assert publish_studio(cfg.evidence_directory, report, tmp_path, playtest=True) is None
    assert read_receipt(LabSettings(True, cfg.evidence_directory / "latest.json")).state == "failed"


def test_uncertain_send_and_cooldown_shared_with_existing_ledger(tmp_path):
    cfg = config(tmp_path)
    stage(cfg.evidence_directory, receipt(), event=True)
    with pytest.raises(TimeoutError):
        send_tick(cfg, fail=True)
    stage(cfg.evidence_directory, receipt(job_id="job-2"), event=True)
    assert send_tick(cfg)[0]["state"] == "awaiting_review"
    result, sent = send_tick(cfg, NOW + timedelta(hours=25))
    assert result["sent"] and len(sent) == 1  # unknown first event is never retried
    stage(cfg.evidence_directory, receipt(job_id="job-3"), event=True)
    assert send_tick(cfg, NOW + timedelta(hours=26))[0]["state"] == "cooldown"
    ledger = DeliveryLedger(cfg.state_path, cfg.owner_id)
    try:
        assert ledger.delivery_hold(now=NOW + timedelta(hours=26), cooldown_hours=6) == "cooldown"
    finally:
        ledger.close()


def test_review_binds_exact_event_image_and_rejection(tmp_path):
    cfg = config(tmp_path)
    rec = receipt(capture_kind="studio-viewport", camera="front", captured_at=STAMP)
    event = stage(cfg.evidence_directory, rec, capture=png(), event=True)
    path = cfg.evidence_directory / "events" / (event + ".json")
    _, digest, native = load_event(path, now=NOW)
    review = {"event_id": event, "event_sha256": digest, "approved_for_reuse": False}
    review_path = cfg.evidence_reviews / (event + ".json")
    review_path.write_bytes(encoded(review))
    assert not send_tick(cfg)[1]
    review.update(approved_for_reuse=True, image_sha256="0" * 64)
    review_path.write_bytes(encoded(review))
    assert not send_tick(cfg)[1]
    review["image_sha256"] = native.capture_sha256
    review_path.write_bytes(encoded(review))
    _, sent = send_tick(cfg)
    assert "approved for reuse" in sent[0][0] and sent[0][1][0] == "star-lab.jpg"


def test_invalid_and_stale_events_do_not_block_good_event(tmp_path):
    cfg = config(tmp_path)
    stage(cfg.evidence_directory, receipt(updated_at="2026-10-01T00:00:00Z"), event=True)
    (cfg.evidence_directory / "events" / "bad.json").write_text("[]")
    stage(cfg.evidence_directory, receipt(job_id="valid"), event=True)
    assert send_tick(cfg)[0]["sent"]


def test_native_blender_requires_fixed_render_and_glb_header(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    monkeypatch.setattr("star.discord_bot.native_evidence.stamp", lambda: STAMP)
    (tmp_path / "preview.png").write_bytes(png())
    (tmp_path / "scene.glb").write_bytes(struct.pack("<4sII", b"glTF", 2, 20) + b"12345678")
    event = publish_blender(cfg.evidence_directory, {"job_id": "blender-1", "preview_file": "present"},
                            tmp_path, {"name": "Arch"})
    assert event
    _, sent = send_tick(cfg)
    assert "GLB header" in sent[0][0] and "Studio import untested" in sent[0][0]
    (tmp_path / "scene.glb").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="header"):
        publish_blender(cfg.evidence_directory, {"job_id": "blender-2", "preview_file": "present"},
                        tmp_path, {"name": "Arch"})


def test_real_playtest_loop_hook_with_fake_native_tools(tmp_path, monkeypatch):
    from tests.test_playtest_learning import FakeStudio, FakeBrain, answer, opener, spec, no_sleep
    from star import playtest_learning as pl
    cfg = config(tmp_path)
    monkeypatch.setenv("STAR_DISCORD_EVIDENCE_PRODUCER", "1")
    monkeypatch.setenv("STAR_DISCORD_EVIDENCE_DIRECTORY", str(cfg.evidence_directory))
    studio = FakeStudio()
    brain = FakeBrain([answer("-- BUG\nprint(1)"), answer("print(2)", "Keep the door closed.")])
    result = asyncio.run(pl.run_suite([spec()], opener(studio), brain, tmp_path / "out", log=lambda *_: None,
                                      run_kwargs={"sleep": no_sleep, "poll": 0}))
    assert result["reports"][0]["passed"]
    events = list((cfg.evidence_directory / "events").glob("*.json"))
    assert len(events) == 1
    _, _, native = load_event(events[0], now=datetime.now(timezone.utc))
    assert native.iteration == 2 and native.source == "playtest-learning"


@pytest.mark.parametrize("ui", [False, True])
def test_native_studio_hooks_with_real_image_fakes(tmp_path, monkeypatch, ui):
    from star import studio_lab
    from tests.test_studio_lab import StandInStudio, spec
    from tests.test_studio_lab_v3 import ScriptedUiLab, spec_named
    cfg = config(tmp_path)
    monkeypatch.setenv("STAR_DISCORD_EVIDENCE_PRODUCER", "1")
    monkeypatch.setenv("STAR_DISCORD_EVIDENCE_DIRECTORY", str(cfg.evidence_directory))
    image_result = {"content": [{"type": "image", "data": base64.b64encode(png()).decode(), "mimeType": "image/png"}]}
    async def no_sleep(_):
        pass
    if ui:
        lab = ScriptedUiLab(tmp_path / "out")
        async def read(*args, **kwargs):
            return image_result
        lab._read = read
        report = asyncio.run(lab.run(spec_named("V3UiLongButton"), run="abcd1234"))
    else:
        studio = StandInStudio()
        original = studio.call_tool
        async def call(name, args):
            if name == "start_stop_play" and args["is_start"]:
                status = read_receipt(LabSettings(True, cfg.evidence_directory / "latest.json"))
                assert status.phase == "playtesting" and status.state == "running" and status.camera
            return image_result if name == "screen_capture" else await original(name, args)
        studio.call_tool = call
        lab = studio_lab.Lab(studio, tmp_path / "out", log=lambda *_: None, sleep=no_sleep, poll=0)
        report = asyncio.run(lab.run(spec(), run="feedbeef"))
    assert report["passed"]
    events = list((cfg.evidence_directory / "events").glob("*.json"))
    assert len(events) == 1
    _, _, native = load_event(events[0], now=datetime.now(timezone.utc))
    assert native.source == ("studio-ui" if ui else "studio-lab")
    assert native.camera and native.captured_at and native.iteration == 2


def test_native_reference_binding_preserves_owner_constraints_and_auth(tmp_path, monkeypatch):
    from star.discord_bot.service import DiscordService
    from star.discord_bot.dm_mode import prepare_discord_image
    cfg = config(tmp_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stage(cfg.evidence_directory, receipt(state="failed", updated_at=now, capture_kind="studio-viewport",
                                         camera="front", captured_at=now), capture=png())
    service = DiscordService(AccessPolicy(frozenset({123}), frozenset({456})))
    settings = LabSettings(True, cfg.evidence_directory / "latest.json")
    reference = prepare_discord_image("ref.png", "image/png", len(png()), png())
    class Vision:
        async def compare(self, prompt, reference, rendered):
            return "This looks successful."
    words = "Keep the original silhouette. No neon; do not change the face."
    result = asyncio.run(service.compare_lab_reference((None, 555, 123), words, reference, settings, vision=Vision()))
    assert "state: failed" in result and "cannot override rejection" in result
    context = service.memory.history((None, 555, 123))[0]["content"]
    assert words in context and "build=" + "a" * 64 in context
    assert sha256(reference).hexdigest() in context and "job=job-1" in context and "camera=front" in context
    for key in ((None, 555, 999), (789, 555, 123)):
        with pytest.raises(PermissionError):
            asyncio.run(service.compare_lab_reference(key, words, reference, settings, vision=Vision()))


def test_parallel_publishers_and_delivery_reservations(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    cfg = config(tmp_path)
    def publish(hour):
        stage(cfg.evidence_directory, receipt(job_id=f"job-{hour}", updated_at=f"2026-10-16T{hour:02}:00:00Z"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(publish, (13, 15, 14)))
    assert read_receipt(LabSettings(True, cfg.evidence_directory / "latest.json")).job_id == "job-15"
    def reserve(_):
        ledger = DeliveryLedger(cfg.state_path, cfg.owner_id)
        try:
            return ledger.reserve_task("a" * 64, now=NOW, cooldown_hours=6)
        finally:
            ledger.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, (1, 2))) == ["already_processed", "ready"]


def test_aggregate_and_task_delivery_share_cooldown_both_directions(tmp_path):
    from star.discord_bot.learning_reports import parse_night_school_report
    from star.discord_bot.learning_sender import run_delivery
    from tests.test_discord_learning_digests import example_report
    cfg = config(tmp_path)
    snapshot = parse_night_school_report(example_report(now=NOW))
    sent = []
    async def send(body, image):
        sent.append(body)
    settings = cfg.delivery_settings()
    assert asyncio.run(run_delivery(settings, dry_run=False, snapshot=snapshot, send=send, now=NOW))["sent"]
    stage(cfg.evidence_directory, receipt(), event=True)
    assert send_tick(cfg, NOW + timedelta(hours=1))[0]["state"] == "cooldown"
    assert send_tick(cfg, NOW + timedelta(hours=7))[0]["sent"]
    next_report = parse_night_school_report(example_report(now=NOW + timedelta(hours=8), examples=150))
    result = asyncio.run(run_delivery(settings, dry_run=False, snapshot=next_report, send=send,
                                     now=NOW + timedelta(hours=8)))
    assert result["state"] == "cooldown" and len(sent) == 1


def test_fixed_blender_controller_hook_with_fake_process(tmp_path, monkeypatch):
    from tests.test_blender_brain2 import FakeBlenderProcess, SCENE
    from star.blender_bridge import BlenderController
    from star.desktop_core import Settings
    from pathlib import Path
    cfg = config(tmp_path)
    monkeypatch.setenv("STAR_DISCORD_EVIDENCE_PRODUCER", "1")
    monkeypatch.setenv("STAR_DISCORD_EVIDENCE_DIRECTORY", str(cfg.evidence_directory))
    class Process(FakeBlenderProcess):
        async def communicate(self):
            result = await super().communicate()
            folder = Path(self.args[-1]).parent
            (folder / "preview.png").write_bytes(png())
            (folder / "scene.glb").write_bytes(struct.pack("<4sII", b"glTF", 2, 20) + b"12345678")
            return result
    async def spawn(*args, **kwargs):
        return Process(args)
    host = BlenderController(settings=Settings(blender_enabled=True, blender_edit=True), home=tmp_path, spawn=spawn)
    monkeypatch.setattr(host, "_executable", lambda: Path("fake-blender"))
    result = asyncio.run(host.build(SCENE | {"render_preview": True}))
    events = list((cfg.evidence_directory / "events").glob("*.json"))
    assert len(events) == 1
    _, _, native = load_event(events[0], now=datetime.now(timezone.utc))
    assert native.job_id == result["job_id"] and native.source == "blender-worker"
