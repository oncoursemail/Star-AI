"""Offline reference diagnostics and opt-in Roblox environment authoring recipes.

This module never contacts a service, starts Studio, reads its DataModel, or applies
an edit. Image comparisons measure rendered color/layout, not semantic fidelity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

MAX_INPUT_BYTES = 20_000_000
MAX_INPUT_PIXELS = 32_000_000
SAMPLE_SIZE = (160, 90)
QUALITIES = {"low": (10, 100, 128), "medium": (15, 160, 256), "high": (20, 220, 512)}

# Authored starting points, not measured settings extracted from an artist's image.
# clock, brightness, exposure, ambient, outdoor, density, haze, glare,
# atmosphere color, atmosphere decay, CC contrast/saturation/tint, bloom strength.
PRESETS = {
    "winter-shrine": (11.5, 2.0, 0.00, "#717F98", "#B9CBE0", .46, 1.8, .05,
                      "#D7E2F1", "#99A9BD", .05, -.22, "#D5E5FF", .08),
    "volcanic-crypt": (20.0, 1.1, -.25, "#29202C", "#393040", .27, 1.6, 0.0,
                       "#504251", "#31283C", .17, -.22, "#FFC4A3", .16),
    "sandstone-temple": (15.0, 2.4, -.10, "#756255", "#D4B89B", .34, 1.3, .20,
                         "#E6BFA2", "#A58776", .09, -.18, "#FFDCC2", .07),
    "gothic-library": (9.0, 1.35, -.10, "#313A54", "#737C9C", .21, .8, .05,
                       "#8EA3C8", "#485875", .18, -.10, "#C9DDFF", .12),
    "moonlit-forest": (0.8, .9, -.28, "#1E3559", "#345477", .28, 1.5, 0.0,
                       "#44699A", "#24385C", .13, -.16, "#A7D3FF", .10),
    "crimson-snow": (3.0, 1.15, -.30, "#243D65", "#6784A5", .35, 2.0, 0.0,
                     "#7296C3", "#384B75", .15, -.28, "#B9D9FF", .07),
    "misty-farm": (1.2, 1.0, -.25, "#242C2F", "#506A67", .42, 1.6, 0.0,
                   "#9AADB3", "#4B646A", .13, -.23, "#C3D3CB", .10),
    "crystal-wastes": (13.0, 2.1, -.16, "#59679B", "#ACBCF4", .30, 1.3, .05,
                       "#B1C8FF", "#7382C5", .12, .08, "#C2EFFF", .18),
    "sunset-city": (17.1, 2.2, -.05, "#715C64", "#E8AD88", .24, .8, .22,
                    "#F0C3A6", "#AB8193", .09, -.09, "#FFDFBC", .10),
    "ashfall-city": (21.3, 1.1, -.30, "#31332F", "#585A4C", .32, 2.0, 0.0,
                     "#797B6E", "#4B4A46", .21, -.35, "#D6C7AA", .06),
}


def _rgb(hex_color: str) -> str:
    return ", ".join(str(int(hex_color[i:i + 2], 16)) for i in (1, 3, 5))


def _image(path: Path) -> Image.Image:
    """Load only bounded local still images; honor EXIF and flatten alpha."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Reference must be a regular file no larger than 20 MB")
    try:
        with Image.open(path) as opened:
            if opened.width * opened.height > MAX_INPUT_PIXELS:
                raise ValueError("Reference exceeds 32 million pixels")
            if opened.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Only PNG, JPEG and WEBP still images are supported")
            oriented = ImageOps.exif_transpose(opened)
            canvas = Image.new("RGBA", oriented.size, (127, 127, 127, 255))
            canvas.alpha_composite(oriented.convert("RGBA"))
            return canvas.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Unable to decode reference image") from exc


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{v:02X}" for v in rgb)


def _regions(image: Image.Image) -> list[float]:
    w, h = image.size
    return [round(ImageStat.Stat(image.crop((x * w // 3, y * h // 3,
                                            (x + 1) * w // 3, (y + 1) * h // 3))
                                 .convert("L")).mean[0] / 255, 4)
            for y in range(3) for x in range(3)]


def _palette(image: Image.Image) -> list[dict]:
    small = image.resize((100, 60), Image.Resampling.BOX)
    quantized = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    colors = quantized.getcolors(maxcolors=256) or []
    raw = quantized.getpalette()
    seen = []
    for count, index in sorted(colors, key=lambda item: (-item[0], item[1])):
        color = tuple(raw[index * 3:index * 3 + 3])
        seen.append({"color": _hex(color), "share": round(count / 6000, 4)})
    return seen


def _features(image: Image.Image) -> dict:
    small = image.resize(SAMPLE_SIZE, Image.Resampling.BOX)
    stats = ImageStat.Stat(small)
    gray = small.convert("L")
    edge = gray.filter(ImageFilter.FIND_EDGES)
    # A coarse edge-density proxy: not a claim to infer meshes or depth.
    edge_density = sum(edge.histogram()[53:]) / (SAMPLE_SIZE[0] * SAMPLE_SIZE[1])
    return {
        "palette": _palette(small),
        "mean_rgb": [round(v / 255, 4) for v in stats.mean],
        "mean_luminance": round(ImageStat.Stat(gray).mean[0] / 255, 4),
        "luminance_grid_3x3": _regions(small),
        "edge_density_proxy": round(edge_density, 4),
    }


def inspect_reference(path: Path) -> dict:
    path = Path(path)
    image = _image(path)
    return {
        "reference": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size": list(image.size),
        "measures": _features(image),
        "limitations": "Only image color, luminance layout and edge proxies; no scene geometry or asset licensing inferred.",
    }


def compare_render(reference: Path, render: Path) -> dict:
    """Compare matched camera views; discrepancies inform an artist, not a pass/fail certification."""
    original, candidate = _image(Path(reference)), _image(Path(render))
    ra = original.width / original.height
    rb = candidate.width / candidate.height
    if abs(ra / rb - 1) > .03:
        raise ValueError("Screenshots need matching camera aspect ratios (within 3%)")
    first, second = _features(original), _features(candidate)
    from PIL import ImageChops
    a = original.resize(SAMPLE_SIZE, Image.Resampling.BOX)
    b = candidate.resize(SAMPLE_SIZE, Image.Resampling.BOX)
    pixel = round(sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / (3 * 255), 4)
    luminance = round(abs(first["mean_luminance"] - second["mean_luminance"]), 4)
    layout = round(sum(abs(x - y) for x, y in zip(first["luminance_grid_3x3"],
                                                    second["luminance_grid_3x3"])) / 9, 4)
    rgb = round(sum(abs(x - y) for x, y in zip(first["mean_rgb"], second["mean_rgb"])) / 3, 4)
    detail = round(abs(first["edge_density_proxy"] - second["edge_density_proxy"]), 4)
    fixes = []
    if layout > .1:
        fixes.append("Recheck camera framing, focal object placement, and foreground/background value grouping.")
    if luminance > .1:
        fixes.append("Review exposure, light direction, local light energy, and atmosphere density.")
    if rgb > .12:
        fixes.append("Retune environment color script, sky palette, material colors, and color correction.")
    if detail > .08:
        fixes.append("Inspect silhouette density, foliage frequency, and repeated architectural detail.")
    if pixel > .18 and not fixes:
        fixes.append("Per-pixel disagreement remains; compare the same camera, resolution and render quality.")
    return {
        "reference_sha256": hashlib.sha256(Path(reference).read_bytes()).hexdigest(),
        "render_sha256": hashlib.sha256(Path(render).read_bytes()).hexdigest(),
        "metrics": {"pixel_rgb_mae": pixel, "mean_luminance_delta": luminance,
                    "layout_luminance_mae": layout, "mean_rgb_delta": rgb,
                    "edge_density_delta": detail},
        "proposed_review": fixes,
        "limitations": ("Lower values mean closer screenshot measurements, not a verified 1:1 reconstruction. "
                        "Use the same camera, aspect, graphics quality and UI visibility. No structural or motion verification."),
    }


def lighting_recipe(name: str) -> str:
    """Create a reviewable Luau suggestion; intentionally never apply it to Studio."""
    if name not in PRESETS:
        raise ValueError(f"Unknown art-direction preset: {name}")
    (clock, brightness, exposure, ambient, outdoor, density, haze, glare,
     atm, decay, contrast, saturation, tint, bloom) = PRESETS[name]
    return f'''-- STAR environment craft preview: {name}
-- Owner-reviewed lighting starting point; paste into an authorized Studio edit context.
-- Does not replace geometry, sky textures, materials, or local authored lights.
local Lighting = game:GetService("Lighting")
Lighting.ClockTime = {clock}
Lighting.Brightness = {brightness}
Lighting.ExposureCompensation = {exposure}
Lighting.Ambient = Color3.fromRGB({_rgb(ambient)})
Lighting.OutdoorAmbient = Color3.fromRGB({_rgb(outdoor)})
local atmosphere = Lighting:FindFirstChildOfClass("Atmosphere")
if not atmosphere then
    atmosphere = Instance.new("Atmosphere")
    atmosphere.Name = "STAR_CraftAtmosphere"
    atmosphere.Parent = Lighting
end
atmosphere.Density = {density}
atmosphere.Haze = {haze}
atmosphere.Glare = {glare}
atmosphere.Color = Color3.fromRGB({_rgb(atm)})
atmosphere.Decay = Color3.fromRGB({_rgb(decay)})
local grade = Lighting:FindFirstChild("STAR_CraftColor")
if not grade then
    grade = Instance.new("ColorCorrectionEffect")
    grade.Name = "STAR_CraftColor"
    grade.Parent = Lighting
end
grade.Contrast = {contrast}
grade.Saturation = {saturation}
grade.TintColor = Color3.fromRGB({_rgb(tint)})
local glow = Lighting:FindFirstChild("STAR_CraftBloom")
if not glow then
    glow = Instance.new("BloomEffect")
    glow.Name = "STAR_CraftBloom"
    glow.Parent = Lighting
end
glow.Intensity = {bloom}
glow.Size = 24
glow.Threshold = 1.8
-- Lighting.Technology is not scriptable. Tune local lights and sky in Studio.
'''


_FOLIAGE = '''-- STAR opt-in, client-only skinned-mesh foliage sway template.
-- Place this LocalScript in StarterPlayerScripts after human review.
-- Tag static tree Models STAR_WindTree; their skinned mesh bones need
-- a numeric WindWeight attribute (0..1). No weighted bones = no sway.
-- Keep these bones free from concurrently played Animator tracks.
-- Set this LocalScript's ReduceMotion attribute to true for a still-foliage mode.
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")
local TAG = "STAR_WindTree"
local MAX_DISTANCE = __DISTANCE__
local MAX_BONES = __BONES__
local INTERVAL = 1 / __RATE__
local trees = {}
local boneCount = 0
local elapsed = 0
local accumulated = 0

local function reset(state)
    if state.active then
        for _, data in ipairs(state.bones) do
            if data.bone.Parent then data.bone.Transform = CFrame.identity end
        end
        state.active = false
    end
end

local function remove(tree)
    local state = trees[tree]
    if state then
        reset(state)
        boneCount -= #state.bones
        trees[tree] = nil
    end
end

local function register(tree)
    if trees[tree] or not tree:IsA("Model") then return end
    local bones = {}
    for _, descendant in ipairs(tree:GetDescendants()) do
        if descendant:IsA("Bone") then
            local weight = descendant:GetAttribute("WindWeight")
            if type(weight) == "number" and weight > 0 and weight <= 1 then
                table.insert(bones, {bone = descendant, weight = weight})
            end
        end
    end
    if #bones == 0 or #bones + boneCount > MAX_BONES then return end
    local position = tree:GetPivot().Position
    trees[tree] = {bones = bones, position = position,
                   phase = (position.X * .137 + position.Z * .093), active = false}
    boneCount += #bones
end

for _, tree in ipairs(CollectionService:GetTagged(TAG)) do register(tree) end
CollectionService:GetInstanceAddedSignal(TAG):Connect(register)
CollectionService:GetInstanceRemovedSignal(TAG):Connect(remove)

RunService.Heartbeat:Connect(function(dt)
    accumulated += math.min(dt, .2)
    if accumulated < INTERVAL then return end
    elapsed += accumulated
    accumulated = 0
    local camera = workspace.CurrentCamera
    if not camera then return end
    local cameraPosition = camera.CFrame.Position
    local wind = workspace.GlobalWind
    local strength = math.min(wind.Magnitude / 25, 1) * .075
    local direction = if wind.Magnitude > .001 then wind.Unit else Vector3.zero
    for tree, state in pairs(trees) do
        if not tree.Parent then
            remove(tree)
        elseif script:GetAttribute("ReduceMotion") == true or strength < .001
            or (state.position - cameraPosition).Magnitude > MAX_DISTANCE then
            reset(state)
        else
            local phase = elapsed * 1.4 + state.phase
            local gust = math.sin(phase) + .35 * math.sin(phase * 2.23)
            for _, data in ipairs(state.bones) do
                local angle = gust * strength * data.weight
                if data.bone.Parent then
                    data.bone.Transform = CFrame.Angles(direction.Z * angle, 0, -direction.X * angle)
                end
            end
            state.active = true
        end
    end
end)
'''


def foliage_script(quality: str = "medium") -> str:
    if quality not in QUALITIES:
        raise ValueError(f"Unknown foliage quality: {quality}")
    rate, distance, max_bones = QUALITIES[quality]
    return (_FOLIAGE.replace("__RATE__", str(rate))
            .replace("__DISTANCE__", str(distance)).replace("__BONES__", str(max_bones)))


# Ambient effects remain bounded and review-only; the anchor and particle textures
# must be created/approved in Studio by the owner.
VFX_PRESETS = {
    # rate, life_min, life_max, speed_min, speed_max, drag, gravity_y, color, size, glow, direction
    "falling-snow": (14, 3, 6, 1, 3, 1.2, -4, "#EDF5FF", .22, 0, "Bottom"),
    "floating-embers": (8, 1, 3, 1, 2, 2.0, 3, "#FF873C", .15, .7, "Top"),
    "dust-motes": (5, 3, 7, .1, .5, 1.5, .5, "#E2D1B0", .10, 0, "Top"),
}


def vfx_recipe(name: str) -> str:
    """Reviewable Attachment/ParticleEmitter Luau; never executed by this module."""
    if name not in VFX_PRESETS:
        raise ValueError(f"Unknown ambient VFX preset: {name}")
    rate, life_min, life_max, speed_min, speed_max, drag, gravity_y, color, size, glow, direction = VFX_PRESETS[name]
    return f'''-- STAR ambient effect preview: {name}
-- Owner must add an Anchored BasePart named STAR_FX_Anchor in the correct scene position.
-- Set an approved licensed Texture before production and profile overlapping transparent particles.
local anchor = workspace:FindFirstChild("STAR_FX_Anchor")
assert(anchor and anchor:IsA("BasePart"), "Create an anchored STAR_FX_Anchor part first")
local attachment = anchor:FindFirstChild("STAR_FX_Attachment")
if not attachment then
    attachment = Instance.new("Attachment")
    attachment.Name = "STAR_FX_Attachment"
    attachment.Parent = anchor
end
local particles = attachment:FindFirstChild("STAR_Craft_{name}")
if not particles then
    particles = Instance.new("ParticleEmitter")
    particles.Name = "STAR_Craft_{name}"
    particles.Parent = attachment
end
particles.Enabled = true
particles.Rate = {rate}
particles.Lifetime = NumberRange.new({life_min}, {life_max})
particles.Speed = NumberRange.new({speed_min}, {speed_max})
particles.Drag = {drag}
particles.WindAffectsDrag = true
particles.Acceleration = Vector3.new(0, {gravity_y}, 0)
particles.EmissionDirection = Enum.NormalId.{direction}
particles.SpreadAngle = Vector2.new(65, 65)
particles.Color = ColorSequence.new(Color3.fromRGB({_rgb(color)}))
particles.Size = NumberSequence.new({size})
particles.Transparency = NumberSequence.new({{
    NumberSequenceKeypoint.new(0, 1),
    NumberSequenceKeypoint.new(.2, .12),
    NumberSequenceKeypoint.new(.8, .25),
    NumberSequenceKeypoint.new(1, 1),
}})
particles.LightEmission = {glow}
-- Avoid stacking multiple full-screen transparent emitters.
'''


def _write(path: Path | None, contents: str) -> None:
    if path is None:
        print(contents)
        return
    target = Path(path)
    # No clobbering, including via a symlink. Preview-only by default.
    with target.open("x", encoding="utf-8") as stream:
        stream.write(contents)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Roblox art-direction diagnostics and code previews")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "compare", "lighting", "foliage", "vfx"):
        sub = commands.add_parser(name)
        if name in {"inspect", "compare"}:
            sub.add_argument("reference", type=Path)
        if name == "compare":
            sub.add_argument("render", type=Path)
        if name == "lighting":
            sub.add_argument("preset", choices=sorted(PRESETS))
        if name == "vfx":
            sub.add_argument("preset", choices=sorted(VFX_PRESETS))
        if name == "foliage":
            sub.add_argument("--quality", choices=sorted(QUALITIES), default="medium")
        sub.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = json.dumps(inspect_reference(args.reference), indent=2)
        elif args.command == "compare":
            result = json.dumps(compare_render(args.reference, args.render), indent=2)
        elif args.command == "lighting":
            result = lighting_recipe(args.preset)
        elif args.command == "foliage":
            result = foliage_script(args.quality)
        else:
            result = vfx_recipe(args.preset)
        _write(args.out, result)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
