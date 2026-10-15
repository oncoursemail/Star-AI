"""STAR VFX Studio: style profiles, ability cue lists, Luau generation and lint, the Studio lab against a stand-in,
the measured critique, procedural textures and their review, the Open Cloud texture upload, the opt-in tool."""
import asyncio
import base64
import io
import json
import re
from pathlib import Path

import httpx
import pytest
from PIL import Image, ImageDraw

from star import luau_lint, skill_packs
from star import roblox_vfx_studio as vfx
from star import roblox_vfx_textures as tex
from star.intelligence import LocalIntelligence

LUAU = vfx.LUAU_DIR


def luau(name: str) -> str:
    return (LUAU / f"{name}.luau").read_text(encoding="utf-8")


# ------------------------------------------------------------------ the Luau modules

def test_every_module_is_strict_and_passes_stars_luau_checks():
    sources = vfx.pack_sources()
    assert set(sources) == {"VfxStyles", "VfxPrimitives", "VfxComposer", "VfxClient", "VfxService"}
    for name, code in sources.items():
        assert code.startswith("--!strict"), name
    findings = vfx.lint_sources(sources)
    assert all(not items for items in findings.values()), findings


def test_python_style_mirror_matches_the_luau_profiles():
    code = luau("VfxStyles")
    for name, profile in vfx.STYLES.items():
        start = code.index(f"Styles.{name} = {{")
        block = code[start:code.index(":: Style", start)]
        for key, rgb in profile["palette"].items():
            assert re.search(rf"\b{key} = rgb\({rgb[0]}, {rgb[1]}, {rgb[2]}\)", block), (name, key)
        for key, value in profile["timing"].items():
            assert re.search(rf"\b{key} = {value}\b", block), (name, key)
        for key, value in profile["screen"].items():
            text = str(value).lower() if isinstance(value, bool) else (str(int(value)) if value == int(value) else str(value))
            assert re.search(rf"\b{key} = {re.escape(text)}\b", block), (name, key, text)
        assert f'shape = "{profile["shape"]}"' in block
    assert re.findall(r'"(\w+)"', code[code.index("Styles.ORDER"):].split("\n")[0]) == list(vfx.STYLES)


def test_python_effect_names_match_the_composer_and_primitives():
    composer, prims = luau("VfxComposer"), luau("VfxPrimitives")
    table = composer[composer.index("local FX:"):composer.index("Composer.FX = FX")]
    names = re.findall(r"^\t(\w+) = Prim\.(\w+),$", table, re.M)
    assert [a for a, _ in names] == list(vfx.FX) and all(a == b for a, b in names)
    for name in vfx.FX:
        assert f"function Prim.{name}(ctx: Ctx" in prims, name
    assert vfx.STAGES == tuple(re.search(r"Composer.STAGES = \{ (.*) \}", composer).group(1).replace('"', "").split(", "))
    for fx in re.findall(r'cue\("\w+", [\d.]+, "(\w+)"', composer):
        assert fx in vfx.FX


def test_stage_times_match_the_luau_formula():
    for name in vfx.STYLES:
        times = vfx.stage_times(name)
        assert times["finish"] == pytest.approx(vfx.style_length(name))
        assert times["charge"] < times["impact"] < times["shockwave"] < times["linger"] < times["dissipate"]


def test_server_module_never_trusts_the_client():
    code = luau("VfxService")
    assert "function(player: Player, ability: unknown, style: unknown, target: unknown)" in code.replace(
        "local function onRequest", "function")
    assert "#ability > 40" in code and "table.find(VfxService.config.styles, style)" in code
    assert "takeToken(player)" in code and "cooldown" in code and "Health <= 0" in code
    assert "VfxService.config.range" in code                    # a requested point is clamped to range
    assert "PlayerRemoving" in code                             # per-player tables are cleared
    client = luau("VfxClient")
    assert 'typeof(origin) ~= "CFrame"' in client and "math.clamp(speed, 0.05, 1)" in client


def test_primitives_clean_up_and_scale_with_speed():
    prims = luau("VfxPrimitives")
    assert prims.count("Prim.cleanup(ctx") >= 15
    assert "e.TimeScale = math.clamp(ctx.speed, 0, 1)" in prims
    assert "Enum.RenderPriority.Camera.Value + 2" in prims and "UnbindFromRenderStep" in prims
    assert "BulkMoveTo" in prims and "workspace:Raycast" in prims
    composer = luau("VfxComposer")
    assert "folder:Destroy()" in composer and "connection:Disconnect()" in composer
    assert "MAX_ACTIVE = 4" in composer and "PARTICLE_BUDGET = 700" in composer


# ------------------------------------------------------------------ choosing a style and an ability

@pytest.mark.parametrize(("words", "base"), [
    ("green anime energy blast", "anime_energy"), ("soft cute pastel cartoon", "cartoon_soft"),
    ("realistic fire and smoke explosion", "realistic_fire"), ("neon cyber hologram laser", "scifi_neon"),
    ("8-bit pixel retro arcade", "pixel_retro"), ("", "anime_energy"),
])
def test_style_words_pick_a_profile(words, base):
    assert vfx.choose_style(words)["base"] == base


def test_colour_words_recolour_the_profile_but_keep_its_shape():
    choice = vfx.choose_style("purple anime aura")
    assert choice["base"] == "anime_energy" and choice["palette"]["glow"] == vfx.COLOUR_WORDS["purple"]
    assert choice["name"] == "purple_anime_energy"
    assert vfx.choose_style("anime aura")["palette"] is None


def _png(draw) -> bytes:
    image = Image.new("RGB", (120, 80), (20, 20, 24))
    draw(ImageDraw.Draw(image), image)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _glow(background, colour, *, blur=8) -> bytes:
    from PIL import ImageFilter
    image = Image.new("RGB", (120, 80), background)
    layer = Image.new("RGB", (120, 80), background)
    ImageDraw.Draw(layer).ellipse((30, 10, 90, 70), fill=colour)
    image = Image.blend(image, layer.filter(ImageFilter.GaussianBlur(blur)), 1.0)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def test_reference_image_palette_picks_and_recolours_a_profile():
    green_on_dark = _glow((10, 14, 12), (40, 255, 90))
    choice = vfx.choose_style("", green_on_dark)
    assert choice["base"] == "anime_energy" and choice["image"]["main_hue_deg"] in range(110, 150)
    assert choice["palette"]["glow"] == choice["image"]["main_rgb"]
    assert vfx.choose_style("", _glow((250, 215, 235), (200, 230, 255)))["base"] == "cartoon_soft"
    assert vfx.choose_style("", _glow((90, 70, 60), (255, 120, 30)))["base"] == "realistic_fire"
    pixel = Image.new("RGB", (32, 32), (60, 30, 90))
    draw = ImageDraw.Draw(pixel)
    draw.rectangle((4, 4, 14, 14), fill=(255, 204, 0))
    draw.rectangle((16, 16, 28, 28), fill=(255, 80, 80))
    draw.rectangle((4, 18, 12, 28), fill=(255, 255, 255))
    buffer = io.BytesIO()
    pixel.save(buffer, "PNG")
    assert vfx.choose_style("", buffer.getvalue())["base"] == "pixel_retro"


def test_ability_choice_and_generated_cue_lists():
    assert vfx.choose_ability("sword hit impact")["name"] == "impact_hit"
    assert vfx.choose_ability("ultimate ground slam")["name"] == "energy_burst"
    heal = vfx.choose_ability("a healing aura for my medic")
    assert heal["name"] == "heal_aura" and not heal["builtin"] and heal["cues"]
    assert vfx.choose_ability("grenade explosion")["name"] == "explosion"
    for spec in vfx.GENERATED_ABILITIES.values():
        assert vfx.validate_ability({"name": "x", "cues": spec["cues"]}) == []
    assert vfx.validate_ability({"name": "Bad Name", "cues": [{"stage": "nope", "at": 3, "fx": "boom"}]}) == [
        "name must be lower_snake_case, 1..40 characters", "cue 0: unknown stage"]


# ------------------------------------------------------------------ generated Luau

def test_generated_module_is_strict_lint_clean_and_safe():
    spec = vfx.make_spec("purple heal aura", style_description="soft cartoon")
    code = vfx.generated_module(spec["style"], spec["ability"])
    assert code.startswith("--!strict") and 'Styles.custom("cartoon_soft"' in code and "heal_aura" in code
    assert not [f for f in luau_lint.lint(code) if f.severity == "error"]
    with pytest.raises(ValueError):
        vfx.generated_module(spec["style"], {"name": "x", "builtin": False,
                                             "cues": [{"stage": "impact", "at": 0, "fx": "flash",
                                                       "params": {"texture": 'a"]] os.exit()'}}]})


def test_texture_overrides_are_validated_and_pixel_styles_keep_squares():
    own = {"glow": "rbxassetid://123", "ring": "rbxassetid://456", "spark": "http://evil", "bogus": "rbxassetid://1"}
    assert vfx.textures_for("anime_energy", own) == {"glow": "rbxassetid://123", "ring": "rbxassetid://456"}
    assert vfx.textures_for("pixel_retro", own) == {"ring": "rbxassetid://456"}
    code = vfx.generated_module({"base": "anime_energy", "name": "anime_energy"}, {"name": "energy_burst", "builtin": True},
                                textures=own)
    assert 'Styles.withTextures(style, { glow = "rbxassetid://123", ring = "rbxassetid://456" })' in code


def test_apply_installs_only_the_lab_and_survives_brackets_in_sources():
    spec = vfx.make_spec("energy burst")
    code = vfx.apply_luau(spec, "abcd1234")
    for name in (*vfx.SHARED_MODULES, "VfxGenerated", "VfxLabConfig", "VfxService"):
        assert f'"{name}"' in code
    header = code[:code.index("local folder")]
    assert header.count("Destroy()") == 1 and '"StarVfxLab", "StarVfxLabClient"' in header
    assert "STARVFX_APPLY abcd1234" in code and "speed = 0.25" in code
    assert vfx._long_string("a]]b]=]c") == "[==[a]]b]=]c]==]"
    assert "StarVfxLab" in vfx.remove_luau() and "Destroy()" in vfx.remove_luau()
    assert "speed = 1.0" in vfx.lab_config({**spec, "speed": 9}, "r")      # clamped


def test_plan_reports_style_ability_luau_and_lint():
    result = vfx.plan("make a green anime energy burst")
    assert result["spec"]["style"]["base"] == "anime_energy" and result["lint_errors"] == 0
    assert "VfxGenerated" in result["modules"] and result["length_seconds"] > 2


# ------------------------------------------------------------------ frames, critique, sheet

def _frame(index, t, *, colour=(30, 30, 40), blob=None, size=(160, 90)):
    image = Image.new("RGB", size, colour)
    if blob:
        ImageDraw.Draw(image).ellipse(blob[0], fill=blob[1])
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return {"index": index, "effect_t": t, "data": buffer.getvalue()}


def test_critique_finds_a_flat_effect_and_passes_a_readable_one():
    style = {"base": "anime_energy"}
    flat = [_frame(i, i * 0.2 - 0.4) for i in range(30)]
    report = vfx.critique(flat, style)
    assert not report["ok"] and any("weak impact" in f for f in report["findings"])
    times = vfx.stage_times("anime_energy")
    good = []
    for i in range(30):
        t = i * 0.2 - 0.4
        if t < 0 or t > times["finish"]:
            good.append(_frame(i, t))
        elif t < times["impact"]:
            good.append(_frame(i, t, blob=((70, 35, 70 + 4 * i, 35 + 4 * i), (40, 255, 90))))
        elif t < times["shockwave"] + 0.25:
            good.append(_frame(i, t, colour=(220, 255, 225)))
        else:
            r = 10 + 3 * i
            good.append(_frame(i, t, blob=((80 - r, 45 - r // 2, 80 + r, 45 + r // 2), (40, 255, 90))))
    report = vfx.critique(good, style)
    assert report["ok"], report["findings"]
    assert report["scores"]["impact_over_charge"] > 1.5 and report["scores"]["tail_change"] < 0.05


def test_contact_sheet_labels_up_to_sixteen_frames(tmp_path):
    frames = [_frame(i, i * 0.1) for i in range(30)]
    info = vfx.contact_sheet(frames, tmp_path / "sheet.jpg", title="test")
    assert len(info["frames"]) == 16 and (tmp_path / "sheet.jpg").is_file()


# ------------------------------------------------------------------ the lab against a stand-in Studio

class FakeJournal:
    def __init__(self):
        self.entries = []

    def report(self):
        return {"edits": len(self.entries)}


class FakeGuarded:
    """Speaks GuardedStudio's call_tool; plays the lab's console markers and returns images."""
    studio_id = "studio-1"

    def __init__(self):
        self.journal = FakeJournal()
        self.calls = []
        self.run = None
        self.playing = False
        self.reads = 0

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == "execute_luau":
            code = arguments["code"]
            found = re.search(r"STARVFX_(APPLY|CHECK) (\w+)", code)
            if found:
                self.run = found.group(2)
                result = (f"STARVFX_APPLY {self.run} 6" if found.group(1) == "APPLY"
                          else f"STARVFX_CHECK {self.run} VfxStyles=table; VfxComposer=table")
            else:
                result = "STARVFX_REMOVED 3"
            self.journal.entries.append({"ok": True})
            return {"content": [{"type": "text", "text": "STAR_EDIT " + json.dumps({"ok": True, "result": result})}]}
        if name == "start_stop_play":
            self.playing = arguments["is_start"]
            return {"content": [{"type": "text", "text": "ok"}]}
        if name == "get_console_output":
            self.reads += 1
            lines = [f"STARVFX client-ready {self.run}"]
            if self.reads > 3:
                lines.append(f"STARVFX client-play {self.run} length 3.38")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        if name == "screen_capture":
            shade = 40 + (self.reads * 7) % 200
            data = _frame(0, 0, colour=(shade, 255 if self.reads > 5 else shade, shade))["data"]
            return {"content": [{"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/png"}]}
        return {"isError": True, "content": [{"type": "text", "text": "unknown"}]}


def test_the_lab_applies_checks_plays_captures_and_stops(tmp_path):
    clock = {"t": 0.0}

    async def sleep(seconds):
        clock["t"] += seconds

    def now():
        clock["t"] += 0.3
        return clock["t"]

    guarded = FakeGuarded()
    lab = vfx.VfxLab(guarded, tmp_path, log=lambda *_: None, sleep=sleep, clock=now)
    spec = vfx.make_spec("energy burst", speed=0.5)
    report = asyncio.run(lab.run(spec))
    assert report["apply"]["ok"] and report["check"]["ok"]
    play = report["playtest"]
    assert play["client_ready"] and play["played"] and play["frames"] >= 5 and play["stopped"]
    assert guarded.calls.count("start_stop_play") == 2 and not guarded.playing
    assert (tmp_path / "sheet.jpg").is_file() and (tmp_path / "report.json").is_file()
    assert report["critique"]["scores"]["frames_during"] >= 1
    assert all("data" not in f for f in play["frame_files"])
    summary = vfx.public_summary({"ok": True, "results": [report]})
    assert summary["runs"][0]["sheet"] == "sheet.jpg" and "data" not in json.dumps(summary)


def test_the_lab_stops_play_even_when_the_client_never_starts(tmp_path):
    clock = {"t": 0.0}

    async def sleep(seconds):
        clock["t"] += seconds

    guarded = FakeGuarded()

    async def silent(name, arguments, original=guarded.call_tool):
        if name == "get_console_output":
            return {"content": [{"type": "text", "text": ""}]}
        return await original(name, arguments)

    guarded.call_tool = silent
    lab = vfx.VfxLab(guarded, tmp_path, log=lambda *_: None, sleep=sleep, clock=lambda: clock["t"])
    report = asyncio.run(lab.run(vfx.make_spec("energy burst")))
    assert report["playtest"]["client_ready"] is False and report["playtest"]["stopped"] and not guarded.playing


# ------------------------------------------------------------------ textures

def test_every_texture_is_procedural_neutral_and_passes_review(tmp_path):
    records = tex.generate(tmp_path)
    assert [r["name"] for r in records] == list(tex.NAMES)
    assert all(r["review"] == [] for r in records), [(r["name"], r["review"]) for r in records]
    assert Image.open(tmp_path / "star_vfx_puff_flipbook.png").size == (512, 512)
    source = Path(tex.__file__).read_text(encoding="utf-8")
    assert ".text(" not in source and "ImageFont" not in source       # no glyphs are ever drawn


def test_review_rejects_colour_borders_and_barcodes():
    coloured = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(coloured).ellipse((10, 10, 50, 50), fill=(255, 0, 0, 255))
    assert "not colour-neutral (tint at run time instead)" in tex.review(coloured)
    boxed = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    assert any("border" in p for p in tex.review(boxed))
    bars = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
    draw = ImageDraw.Draw(bars)
    for x in range(20, 236, 4):
        draw.rectangle((x, 20, x + 1, 236), fill=(255, 255, 255, 255))
    assert "barcode- or text-like pattern" in tex.review(bars)
    assert any("power of two" in p for p in tex.review(Image.new("RGBA", (100, 100))))


# ------------------------------------------------------------------ Open Cloud texture upload

def test_upload_sends_one_decal_to_the_keys_own_account_and_polls_the_operation(tmp_path, monkeypatch):
    from star import roblox_cloud as rc
    from tests.roblox_fakes import ACCOUNT, FULL_SCOPES, KEY, PLACE, UNIVERSE, FakeRoblox
    for name in rc.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    fake = FakeRoblox(scopes=FULL_SCOPES + [{"name": "asset", "operations": ["read", "write"]}])
    sent = []

    def handle(request):
        if request.url.path == "/assets/v1/assets":
            assert request.headers["x-api-key"] == KEY
            sent.append(request.content)
            return httpx.Response(200, json={"path": "operations/op-1", "operationId": "op-1", "done": False})
        if request.url.path == "/assets/v1/operations/op-1":
            return httpx.Response(200, json={"done": True, "response": {
                "assetId": "555", "moderationResult": {"moderationState": "Approved"}}})
        return fake.handle(request)

    cloud = rc.RobloxCloud(home=tmp_path, key=KEY, source="keyring",
                           client=httpx.Client(transport=httpx.MockTransport(handle)), sleep=lambda _s: None)
    cloud.set_test_experience(UNIVERSE, PLACE, human_approved=True)
    png = io.BytesIO()
    Image.new("RGBA", (16, 16)).save(png, "PNG")
    result = cloud.upload_image_asset(png.getvalue(), display_name="STAR VFX ring")
    assert result["ok"] and result["asset_id"] == "555" and result["moderation"] == "Approved"
    body = sent[0].decode("latin-1")
    assert '"assetType": "Decal"' in body and f'"userId": "{ACCOUNT}"' in body and "image/png" in body
    with pytest.raises(rc.CloudError):
        cloud.upload_image_asset(b"GIF89a", display_name="STAR VFX ring")
    with pytest.raises(rc.CloudError):
        cloud.upload_image_asset(png.getvalue(), display_name="bad/name")
    with pytest.raises(rc.CloudError):
        rc.OpenCloud(KEY, client=httpx.Client(transport=httpx.MockTransport(handle))).call(
            "universe", universe=UNIVERSE, files={"x": ("a", b"b")})


# ------------------------------------------------------------------ the opt-in tool and the skill pack

def hub(tmp_path, **kwargs):
    return LocalIntelligence(home=tmp_path / "home", workspace=kwargs.pop("workspace", None), skills_enabled=False,
                             graphify_enabled=False, **kwargs)


PROMPT = "In Roblox, make a VFX for a fire explosion ability"


def test_the_vfx_tool_is_off_by_default_and_offered_only_for_roblox_vfx_prompts(tmp_path):
    def offered(h, prompt):
        return {t["name"] for t in h.definitions(prompt)}
    assert "star_roblox_vfx_make" not in offered(hub(tmp_path), PROMPT)
    on = hub(tmp_path, vfx_studio_enabled=True)
    assert "star_roblox_vfx_make" in offered(on, PROMPT)
    assert "star_roblox_vfx_make" not in offered(on, "make a VFX for my slideshow")
    with pytest.raises(PermissionError):
        hub(tmp_path).call("star_roblox_vfx_make", {"prompt": "x"}, enabled={"star_roblox_vfx_make"})


def test_the_vfx_tool_plans_offline_and_reads_reference_images_only_inside_the_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "ref.png").write_bytes(_png(lambda d, _i: d.ellipse((30, 10, 90, 70), fill=(0, 220, 255))))
    on = hub(tmp_path, vfx_studio_enabled=True, workspace=workspace)
    result = on.call("star_roblox_vfx_make", {"prompt": "energy burst", "reference_image": "ref.png"},
                     enabled={"star_roblox_vfx_make"})
    assert result["spec"]["style"].get("image") and "Styles.custom" in result["generated_luau"]
    assert "nothing was applied" in result["note"]
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"x")
    with pytest.raises(PermissionError):
        on.call("star_roblox_vfx_make", {"prompt": "energy burst", "reference_image": "../secret.png"},
                enabled={"star_roblox_vfx_make"})


def test_the_composer_pack_is_opt_in_and_chosen_for_ability_vfx_words():
    assert "roblox-vfx-composer" not in skill_packs.DEFAULT_ENABLED
    names = [p.name for p in skill_packs.available()]
    prompt = "In my Roblox game: an anime ability VFX with a screen flash, camera shake and a ground crack."
    assert skill_packs.matching_names(prompt, enabled=names) == ["roblox-vfx-composer"]
    assert skill_packs.matching_names("In my Roblox game: spawn a ParticleEmitter burst with a Beam and a Trail on hit.",
                                      enabled=names) == ["roblox-vfx"]
