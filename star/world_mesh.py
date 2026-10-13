"""Small deterministic terrain OBJ exporter; no Blender, Studio, or network I/O.

An OBJ is a real geometric artifact but not a verified Roblox terrain/world.
Only an explicit CLI invocation writes a file. Model tools remain read-only.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from .asset_forge import preview_terrain


def terrain_obj(preview: dict) -> str:
    """Convert a bounded, world-space heightfield to upward-facing OBJ triangles.

    Adjacent chunks use the same world coordinates for boundary vertices.
    OBJ dimensions are Roblox studs; a later import must review scaling.
    """
    if not isinstance(preview, dict):
        raise ValueError("expected terrain preview")
    heights = preview.get("heights_studs")
    size = len(heights) if isinstance(heights, list) else 0
    if not 2 <= size <= 64 or any(not isinstance(r, list) or len(r) != size for r in heights):
        raise ValueError("expected bounded square heightfield")
    origin = preview.get("origin_studs")
    if not isinstance(origin, list) or len(origin) != 2 or any(type(v) is not int for v in origin):
        raise ValueError("invalid world origin")
    step = preview.get("step_studs")
    if type(step) is not int or not 1 <= step <= 256:
        raise ValueError("invalid terrain step")
    for row in heights:
        for h in row:
            if type(h) not in (float, int) or not math.isfinite(h) or h < 0 or h > 100000:
                raise ValueError("invalid terrain elevation")
    if not isinstance(preview.get("biome"), str) or preview["biome"] not in {"temperate", "desert", "alpine", "alien"}:
        raise ValueError("invalid terrain biome")
    lines = ["# STAR Asset Forge: deterministic heightfield preview mesh", "# Geometry only; import not yet validated in Roblox Studio", "o STAR_terrain", "s 1"]
    x0, z0 = origin
    for z, row in enumerate(heights):
        for x, height in enumerate(row):
            lines.append(f"v {x0 + step * x} {height:.3f} {z0 + step * z}")
    for z in range(size):
        for x in range(size):
            lines.append(f"vt {x / (size-1):.6f} {1 - z / (size-1):.6f}")
    for z in range(size - 1):
        for x in range(size - 1):
            a = z * size + x + 1
            b = a + 1
            c = a + size
            d = c + 1
            # Positive Y normals for Blender's x-right/z-depth coordinate system.
            lines.append(f"f {a}/{a} {c}/{c} {b}/{b}")
            lines.append(f"f {b}/{b} {c}/{c} {d}/{d}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a deterministic STAR preview heightfield to OBJ.")
    parser.add_argument("--output", type=Path, required=True, help="OBJ file path explicitly selected by the operator")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--biome", choices=["temperate", "desert", "alpine", "alien"], default="temperate")
    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--origin-x", type=int, default=0)
    parser.add_argument("--origin-z", type=int, default=0)
    parser.add_argument("--step", type=int, default=16)
    parser.add_argument("--force", action="store_true", help="Explicitly replace an existing OBJ file")
    args = parser.parse_args(argv)
    if args.output.suffix.lower() != ".obj":
        parser.error("output path must end in .obj")
    if args.output.exists() and not args.force:
        parser.error("output exists; pass --force to overwrite")
    try:
        sample = preview_terrain(seed=args.seed, biome=args.biome, size=args.size,
                                 origin_x=args.origin_x, origin_z=args.origin_z, step=args.step)
        mesh = terrain_obj(sample)
    except ValueError as exc:
        parser.error(str(exc))
    # The only I/O path is the manually invoked CLI; tool responses are read-only.
    args.output.write_text(mesh, encoding="utf-8", newline="\n")
    print(f"Wrote {args.output} ({args.size * args.size} vertices, {2 * (args.size - 1)**2} triangles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
