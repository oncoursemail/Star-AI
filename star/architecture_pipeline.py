"""Deterministic exterior building kit for a reviewed Blender -> Roblox workflow.

This module only accepts a bounded JSON design brief; it never runs model-provided Python.
A Blender build is an explicit CLI operation using STAR's fixed, shipped generator.
"""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess

from .architecture_quality import audit_plan, inspect_glb


PALETTES = {
    "storybook": {"wall": "#ead9b5", "trim": "#644936", "roof": "#445465", "glass": "#8eafb4", "door": "#775239"},
    "industrial": {"wall": "#a36e59", "trim": "#514740", "roof": "#535357", "glass": "#83a3b1", "door": "#595d60"},
    "modern": {"wall": "#c8c9c4", "trim": "#373f43", "roof": "#6a7073", "glass": "#87b2c0", "door": "#50575c"},
    "spaceport": {"wall": "#aebbc2", "trim": "#384957", "roof": "#394652", "glass": "#82c5c4", "door": "#476574"},
}
_ROOF = {"storybook": "gable", "industrial": "flat", "modern": "flat", "spaceport": "flat"}
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,47}\Z")
_REQUIRED = {"name", "style", "width_studs", "depth_studs", "floors", "bays"}
_OPTIONAL = {"story_height_studs"}


@dataclass(frozen=True)
class BuildingBrief:
    name: str
    style: str
    width_studs: int
    depth_studs: int
    floors: int
    bays: int
    story_height_studs: int = 13


def validate_brief(raw: object) -> BuildingBrief:
    """Reject unbounded geometry, unknown requests and non-finite/non-integral sizes."""
    if not isinstance(raw, dict) or set(raw) - (_REQUIRED | _OPTIONAL) or not _REQUIRED <= set(raw):
        raise ValueError("Brief must contain only the documented fields")
    if not isinstance(raw["name"], str) or not _NAME.fullmatch(raw["name"]):
        raise ValueError("name must be 1..48 safe ASCII characters")
    if not isinstance(raw["style"], str) or raw["style"] not in PALETTES:
        raise ValueError("Unsupported style")
    limits = {"width_studs": (24, 96), "depth_studs": (16, 80), "floors": (1, 4),
              "bays": (2, 8), "story_height_studs": (12, 18)}
    values = {}
    for field, (low, high) in limits.items():
        value = raw.get(field, 13 if field == "story_height_studs" else None)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{field} must be an integer in {low}..{high}")
        values[field] = value
    if values["width_studs"] / values["bays"] < 8:
        raise ValueError("Each facade bay must be at least 8 studs wide")
    return BuildingBrief(name=raw["name"], style=raw["style"], **values)


def make_plan(brief: BuildingBrief) -> dict:
    """Generate an exterior shell with actual openings and a stable material kit."""
    w, d, floors, bays = brief.width_studs, brief.depth_studs, brief.floors, brief.bays
    h = brief.story_height_studs
    bw, wall = w / bays, 0.7
    opening = min(bw * 0.56, bw - 3.0)
    parts: list[dict] = []

    def box(name, material, center, size, angle=0.0):
        if min(size) <= 0:
            raise ValueError("Invalid part dimension")
        parts.append({"name": name, "kind": "box", "material": material,
                      "center": [round(float(v), 4) for v in center],
                      "size": [round(float(v), 4) for v in size], "angle_y": round(float(angle), 6)})

    # Ground floor remains navigable once the decorative doors/glazing receive appropriate collision settings.
    box("foundation", "trim", (0, 0, -0.35), (w + 1, d + 1, 0.7))
    for floor in range(floors):
        z0 = floor * h
        if floor:
            box(f"slab_{floor}", "trim", (0, 0, z0), (w, d, 0.45))
        for side in ("front", "back"):
            y = -d / 2 if side == "front" else d / 2
            for bay in range(bays):
                x = -w / 2 + (bay + 0.5) * bw
                door = side == "front" and floor == 0 and bay == (bays - 1) // 2
                sill = 0.0 if door else 3.0
                aperture_h = 8.0 if door else min(6.0, h - 5.0)
                flank = (bw - opening) / 2
                for sign, label in ((-1, "left"), (1, "right")):
                    box(f"{side}_f{floor}_b{bay}_{label}", "wall",
                        (x + sign * (opening / 2 + flank / 2), y, z0 + h / 2),
                        (flank, wall, h))
                if sill:
                    box(f"{side}_f{floor}_b{bay}_below", "wall",
                        (x, y, z0 + sill / 2), (opening, wall, sill))
                head = h - sill - aperture_h
                box(f"{side}_f{floor}_b{bay}_above", "wall",
                    (x, y, z0 + sill + aperture_h + head / 2), (opening, wall, head))
                face = y + (-0.4 if side == "front" else 0.4)
                if door:
                    box("entry_door", "door", (x, face, z0 + aperture_h / 2),
                        (opening - 0.3, 0.08, aperture_h - 0.2))
                else:
                    box(f"{side}_f{floor}_b{bay}_glazing", "glass",
                        (x, face, z0 + sill + aperture_h / 2), (opening - 0.2, 0.05, aperture_h - 0.2))
                    box(f"{side}_f{floor}_b{bay}_sill", "trim",
                        (x, y + (-0.45 if side == "front" else 0.45), z0 + sill),
                        (opening + 0.8, 0.9, 0.3))
                # Every opening has structural-looking jambs and a lintel; not floating decoration.
                for sign, label in ((-1, "a"), (1, "b")):
                    box(f"{side}_f{floor}_b{bay}_jamb_{label}", "trim",
                        (x + sign * opening / 2, face, z0 + sill + aperture_h / 2),
                        (0.3, 0.22, aperture_h + 0.3))
                box(f"{side}_f{floor}_b{bay}_lintel", "trim",
                    (x, face, z0 + sill + aperture_h), (opening + 0.5, 0.22, 0.4))
        for x, name in ((-w / 2, "left"), (w / 2, "right")):
            box(f"side_{name}_f{floor}", "wall", (x, 0, z0 + h / 2), (wall, d, h))
        # Continuous horizontal band anchors the windows to a coherent elevation rhythm.
        for side, y in (("front", -d / 2 - 0.25), ("back", d / 2 + 0.25)):
            box(f"belt_{side}_{floor}", "trim", (0, y, z0 + h - 0.35), (w + 0.2, 0.45, 0.35))

    top = floors * h
    if _ROOF[brief.style] == "flat":
        box("flat_roof", "roof", (0, 0, top + 0.35), (w + 1.4, d + 1.4, 0.7))
        for side, y in (("front", -d / 2), ("back", d / 2)):
            box(f"parapet_{side}", "trim", (0, y, top + 1.05), (w + 1.5, 0.5, 1.4))
    else:
        from math import atan2, degrees, hypot
        half = w / 2 + 0.8
        rise = min(w * 0.20, 12)
        span = hypot(half, rise)
        slope = degrees(atan2(rise, half))
        for sign, label in ((-1, "left"), (1, "right")):
            box(f"roof_{label}", "roof", (sign * half / 2, 0, top + rise / 2),
                (span + 0.35, d + 1.6, 0.38), sign * slope)
        # Gable infill closes the structural wall below the two sloping roof panels.
        for side, y in (("front", -d / 2), ("back", d / 2)):
            a, b = -w / 2, w / 2
            parts.append({"name": f"gable_{side}", "kind": "triangle_prism", "material": "wall",
                          "vertices": [[a, y - wall / 2, top], [b, y - wall / 2, top], [0, y - wall / 2, top + rise],
                                       [a, y + wall / 2, top], [b, y + wall / 2, top], [0, y + wall / 2, top + rise]]})

    estimate = 12 * sum(p["kind"] == "box" for p in parts) + 8 * sum(p["kind"] == "triangle_prism" for p in parts)
    return {"schema_version": 1, "brief": asdict(brief), "unit": "studs (verify orientation and scale in Studio)",
            "palette": PALETTES[brief.style], "parts": parts,
            "metrics": {"parts_before_material_batch": len(parts), "estimated_triangles": estimate,
                        "material_groups": len(PALETTES[brief.style])},
            "review_required": ["reference fidelity and architectural plausibility", "door gameplay and collision",
                                "Studio import scale/orientation", "mobile profiling and texturing"]}


def create_package(raw: object, output_dir: Path, *, blender: Path | None = None,
                   run=subprocess.run) -> Path:
    """Write plan; optionally run *bundled* Blender script after explicit invocation.

    Never overwrites existing output. Blender is never called for a plan-only request.
    """
    brief = validate_brief(raw)
    output_dir = Path(output_dir).expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(f"Output path already exists: {output_dir}")
    if blender is not None:
        blender = Path(blender).expanduser().resolve()
        if not blender.is_file() or blender.name.lower() not in {"blender", "blender.exe"}:
            raise ValueError("Explicit path to the installed Blender executable required")
    # Static validation is required even though STAR itself generated the geometry.
    plan_data = make_plan(brief)
    review = audit_plan(plan_data)
    if not review["valid"]:
        raise RuntimeError("Building plan failed its geometry audit: " + "; ".join(review["errors"]))
    output_dir.mkdir(parents=True, exist_ok=False)
    plan = output_dir / "building-plan.json"
    text = json.dumps(plan_data, indent=2) + "\n"
    plan.write_text(text, encoding="utf-8")
    (output_dir / "architecture-audit.json").write_text(
        json.dumps(review, indent=2) + "\n", encoding="utf-8")
    export = None
    if blender is not None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "blender_building.py"
        glb = output_dir / "building.glb"
        cmd = [str(blender), "--background", "--factory-startup", "--disable-autoexec", "--threads", "2",
               "--python", str(script), "--", str(plan), str(glb)]
        try:
            result = run(cmd, capture_output=True, text=True, timeout=180, check=True)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Blender build exceeded 180 seconds; see the retained plan") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"Blender export failed: {str(exc.stderr or '')[-1500:]}") from exc
        if not glb.is_file() or not (output_dir / "building.blend").is_file():
            raise RuntimeError("Blender did not write the expected .glb and .blend files")
        try:
            export = inspect_glb(glb, expected_material_roles=tuple(plan_data["palette"]))
        except ValueError as exc:
            raise RuntimeError(f"Blender GLB export was not validated: {exc}") from exc

    manifest = {
        "schema_version": 1,
        "status": "exported_needs_studio_review" if export else "plan_only",
        "name": brief.name, "style": brief.style,
        "brief_sha256": hashlib.sha256(json.dumps(asdict(brief), sort_keys=True).encode("utf-8")).hexdigest(),
        "plan_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "files": ["building-plan.json", "architecture-audit.json", "studio-import-guide.md",
                  "asset-manifest.json"] + (["building.blend", "building.glb"] if export else []),
        "blender_export": export,
        "studio_imported": False, "visual_quality_verified": False,
        "review_required": plan_data["review_required"],
    }
    (output_dir / "asset-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output_dir / "studio-import-guide.md").write_text(
        "# STAR building import review\n\n"
        "This is a procedural **prototype**, NOT an approved, playable building.\n\n"
        "1. Open a private test place in Roblox Studio and use File > Import on building.glb.\n"
        "2. Preview the mesh. Set World Forward to Front, World Up to Top and Scale Unit to Stud.\n"
        "3. Verify proportions with real R6/R15 avatars, lighting, face normals and imported materials.\n"
        "4. Doors and glass are static visual placeholders. Configure collisions and working doors in Studio.\n"
        "5. For upper floors, implement and test stairs/landings before claiming accessibility.\n"
        "6. Inspect memory, rendering, streaming and draw calls on target devices.\n"
        "7. Preserve the STAR_<role> mesh names for reimport; obtain owner approval before uploads.\n\n"
        "Reference: https://create.roblox.com/docs/art/blender\n",
        encoding="utf-8")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a bounded Roblox architecture kit using Blender")
    parser.add_argument("brief", type=Path, help="A JSON brief with documented fields")
    parser.add_argument("--out", required=True, type=Path, help="New, empty output path (never overwritten)")
    parser.add_argument("--blender", type=Path, help="Explicit Blender executable; omit for plan-only")
    args = parser.parse_args(argv)
    if args.brief.stat().st_size > 16_384:
        parser.error("Brief exceeds 16 KB")
    try:
        plan = create_package(json.loads(args.brief.read_text(encoding="utf-8")),
                              args.out, blender=args.blender)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    print(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
