"""Original, procedurally generated particle textures for the STAR VFX composer (Pillow only, deterministic).

Every texture is drawn by code from a fixed seed: no source image, no font, no text. Textures are white/grey on a
transparent background so ParticleEmitter.Color / Beam.Color tint them for any style. The set:
  soft_glow, spark, smoke_wisp, ring, crack, streak, swirl, square (pixel styles), puff_flipbook (Grid4x4).

`review(image)` applies STAR's asset review rules before anything may be uploaded: PNG RGBA, power-of-two size
<= 1024, colour-neutral (no hue: tinted at run time), transparent border, and no text, URL or barcode-like pattern
(checked by a run-length heuristic; the generator itself never renders glyphs).

Upload (optional, `--upload`): through star/roblox_cloud.py's Open Cloud key handling (the key is read from STAR's
key file by the code and never printed) to STAR's own account as private Decal assets. Without an upload the
composer keeps Roblox's built-in rbxasset:// textures.
CLI: python -m star.roblox_vfx_textures OUT_DIR [--upload --home H]
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

SIZE = 256
NAMES = ("soft_glow", "spark", "smoke_wisp", "ring", "crack", "streak", "swirl", "square", "puff_flipbook")


def _image(size: int = SIZE):
    from PIL import Image
    return Image.new("RGBA", (size, size), (255, 255, 255, 0))


def _alpha_from(values, size: int):
    """RGBA image, white, with alpha from a list of floats 0..1 (row-major)."""
    from PIL import Image
    alpha = Image.new("L", (size, size))
    alpha.putdata([max(0, min(255, int(v * 255))) for v in values])
    image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    image.putalpha(alpha)
    return image


def _value_noise(size: int, cells: int, rng: random.Random) -> list[float]:
    grid = [[rng.random() for _ in range(cells + 1)] for _ in range(cells + 1)]
    out = []
    for y in range(size):
        gy = y / size * cells
        y0, fy = int(gy), gy - int(gy)
        fy = fy * fy * (3 - 2 * fy)
        for x in range(size):
            gx = x / size * cells
            x0, fx = int(gx), gx - int(gx)
            fx = fx * fx * (3 - 2 * fx)
            a = grid[y0][x0] + (grid[y0][x0 + 1] - grid[y0][x0]) * fx
            b = grid[y0 + 1][x0] + (grid[y0 + 1][x0 + 1] - grid[y0 + 1][x0]) * fx
            out.append(a + (b - a) * fy)
    return out


def _fbm(size: int, rng: random.Random, octaves: int = 4) -> list[float]:
    total = [0.0] * (size * size)
    amp, norm = 1.0, 0.0
    for octave in range(octaves):
        layer = _value_noise(size, 4 * 2 ** octave, rng)
        total = [t + v * amp for t, v in zip(total, layer)]
        norm += amp
        amp *= 0.5
    return [t / norm for t in total]


def soft_glow(size: int = SIZE):
    c = (size - 1) / 2
    return _alpha_from([math.exp(-((((x - c) ** 2 + (y - c) ** 2) ** 0.5) / (size * 0.18)) ** 2)
                        * max(0.0, 1 - (((x - c) ** 2 + (y - c) ** 2) ** 0.5) / (size * 0.5))
                        for y in range(size) for x in range(size)], size)


def spark(size: int = SIZE):
    """Four-point star: a hot core with two thin crossing flares."""
    c = (size - 1) / 2
    values = []
    for y in range(size):
        for x in range(size):
            dx, dy = abs(x - c) / c, abs(y - c) / c
            r = (dx * dx + dy * dy) ** 0.5
            core = math.exp(-(r / 0.08) ** 2)
            flare = math.exp(-(dy / 0.025) ** 2) * max(0, 1 - dx) ** 2 + math.exp(-(dx / 0.025) ** 2) * max(0, 1 - dy) ** 2
            diag = 0.35 * (math.exp(-(abs(dx - dy) / 0.03) ** 2) * max(0, 1 - r * 1.6) ** 2)
            values.append(min(1.0, core + flare * 0.9 + diag) * max(0.0, 1 - r) ** 0.5)
    return _alpha_from(values, size)


def smoke_wisp(size: int = SIZE, seed: int = 7):
    rng = random.Random(seed)
    noise = _fbm(size, rng)
    c = (size - 1) / 2
    values = []
    for i, n in enumerate(noise):
        x, y = i % size, i // size
        r = (((x - c) ** 2 + (y - c) ** 2) ** 0.5) / (size * 0.5)
        falloff = max(0.0, 1 - r) ** 1.4
        values.append(max(0.0, (n - 0.35) * 1.8) * falloff)
    return _alpha_from(values, size)


def ring(size: int = SIZE, seed: int = 3):
    rng = random.Random(seed)
    noise = _value_noise(size, 12, rng)
    c = (size - 1) / 2
    values = []
    for i, n in enumerate(noise):
        x, y = i % size, i // size
        r = (((x - c) ** 2 + (y - c) ** 2) ** 0.5) / (size * 0.5)
        band = math.exp(-((r - 0.82) / 0.07) ** 2) + 0.35 * math.exp(-((r - 0.7) / 0.12) ** 2)
        values.append(min(1.0, band) * (0.75 + 0.25 * n) * (1.0 if r < 0.98 else 0.0))
    return _alpha_from(values, size)


def crack(size: int = SIZE, seed: int = 11):
    """Radial, branching crack lines (a ground decal), drawn as jagged polylines."""
    from PIL import ImageDraw, ImageFilter
    rng = random.Random(seed)
    image = _image(size)
    draw = ImageDraw.Draw(image)
    c = size / 2
    for i in range(11):
        angle = i / 11 * math.tau + rng.uniform(-0.2, 0.2)
        x, y, width = c, c, 7
        for _step in range(7):
            angle += rng.uniform(-0.45, 0.45)
            length = size * rng.uniform(0.045, 0.08)
            nx, ny = x + math.cos(angle) * length, y + math.sin(angle) * length
            draw.line((x, y, nx, ny), fill=(255, 255, 255, 255), width=max(1, int(width)))
            if rng.random() < 0.3:
                ba = angle + rng.choice((-1, 1)) * rng.uniform(0.5, 1.0)
                draw.line((nx, ny, nx + math.cos(ba) * length * 0.7, ny + math.sin(ba) * length * 0.7),
                          fill=(255, 255, 255, 200), width=max(1, int(width * 0.5)))
            x, y, width = nx, ny, width * 0.78
    draw.ellipse((c - 16, c - 16, c + 16, c + 16), fill=(255, 255, 255, 255))
    return image.filter(ImageFilter.GaussianBlur(0.8))


def streak(size: int = SIZE):
    """A horizontal tapered streak for VelocityParallel sparks, slashes and beam layers."""
    c = (size - 1) / 2
    values = []
    for y in range(size):
        for x in range(size):
            u = x / (size - 1)
            taper = math.sin(math.pi * u) ** 0.6 * (0.4 + 0.6 * u)
            values.append(math.exp(-(abs(y - c) / (size * 0.09 * taper + 0.5)) ** 2) * taper)
    return _alpha_from(values, size)


def swirl(size: int = SIZE):
    """Three spiral arms for vortex particles."""
    c = (size - 1) / 2
    values = []
    for y in range(size):
        for x in range(size):
            dx, dy = x - c, y - c
            r = (dx * dx + dy * dy) ** 0.5 / c
            a = math.atan2(dy, dx)
            arm = 0.5 + 0.5 * math.cos(3 * (a + r * 4.2))
            values.append((arm ** 6) * max(0.0, 1 - r) * min(1.0, r * 5))
    return _alpha_from(values, size)


def square(size: int = 64):
    """A crisp square with a one-pixel soft rim, for pixel/retro styles."""
    image = _image(size)
    from PIL import ImageDraw
    ImageDraw.Draw(image).rectangle((6, 6, size - 7, size - 7), fill=(255, 255, 255, 255))
    return image


def puff_flipbook(size: int = 512, seed: int = 5):
    """A 4x4 flipbook (FlipbookLayout Grid4x4): a smoke puff that expands, breaks up and fades over 16 frames."""
    from PIL import Image
    cell = size // 4
    rng = random.Random(seed)
    noise = _fbm(cell, rng)
    sheet = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    c = (cell - 1) / 2
    for frame in range(16):
        k = frame / 15
        radius = 0.55 + 0.45 * k
        threshold = 0.05 + 0.4 * k
        values = []
        for i, n in enumerate(noise):
            x, y = i % cell, i // cell
            r = (((x - c) ** 2 + (y - c) ** 2) ** 0.5) / (cell * 0.5)
            fall = max(0.0, 1 - r / radius)
            values.append(min(1.0, max(0.0, (n - threshold + 0.45 * fall) * 2.6) * fall ** 0.6 * (1 - k * 0.7)))
        sheet.paste(_alpha_from(values, cell), ((frame % 4) * cell, (frame // 4) * cell))
    return sheet


BUILDERS = {"soft_glow": soft_glow, "spark": spark, "smoke_wisp": smoke_wisp, "ring": ring, "crack": crack,
            "streak": streak, "swirl": swirl, "square": square, "puff_flipbook": puff_flipbook}
# Which composer texture slot each image fills (VfxStyles.Textures keys).
SLOTS = {"soft_glow": "glow", "spark": "spark", "smoke_wisp": "smoke", "ring": "ring", "crack": "crack",
         "streak": "streak", "swirl": "swirl"}


def review(image) -> list[str]:
    """STAR asset review rules for a particle texture. [] means it may be uploaded."""
    problems = []
    w, h = image.size
    if image.mode != "RGBA":
        problems.append("not RGBA")
    if w != h or w & (w - 1) or w > 1024 or w < 16:
        problems.append("size must be a power of two, square, 16..1024")
    rgba = image.convert("RGBA")
    getter = getattr(rgba, "get_flattened_data", None)
    pixels = list(getter() if getter else rgba.getdata())
    visible = [p for p in pixels if p[3] > 8]
    if not visible:
        problems.append("fully transparent")
        return problems
    if any(max(p[:3]) - min(p[:3]) > 6 for p in visible):
        problems.append("not colour-neutral (tint at run time instead)")
    border = [rgba.getpixel((x, y)) for x in range(w) for y in (0, h - 1)] + \
             [rgba.getpixel((x, y)) for y in range(h) for x in (0, w - 1)]
    if image.size[0] <= 256 and max(p[3] for p in border) > 40:
        problems.append("visible border: particle would show a hard square edge")
    # Barcode / text heuristic: many short, high-contrast alternating runs along rows or columns.
    alpha = [p[3] for p in pixels]
    suspicious_rows = 0
    for y in range(0, h, max(1, h // 64)):
        row = alpha[y * w:(y + 1) * w]
        runs, last, length, short = 0, row[0] > 127, 0, 0
        for value in row:
            state = value > 127
            if state != last:
                runs += 1
                if length <= max(2, w // 64):
                    short += 1
                length = 0
                last = state
            length += 1
        if runs >= 24 and short >= 16:
            suspicious_rows += 1
    if suspicious_rows >= 6:
        problems.append("barcode- or text-like pattern")
    return problems


def generate(out: Path) -> list[dict]:
    """Draw every texture into `out` (PNG) and review it. Returns one record per file."""
    import hashlib
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for name in NAMES:
        image = BUILDERS[name]()
        path = out / f"star_vfx_{name}.png"
        image.save(path, optimize=True)
        data = path.read_bytes()
        records.append({"name": name, "file": path.name, "size": list(image.size), "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "review": review(image),
                        "slot": SLOTS.get(name), "flipbook": "Grid4x4" if name == "puff_flipbook" else None})
    return records


def contact_sheet(out: Path, records: list[dict]) -> Path:
    """Preview of the set on dark and light backgrounds (for the evidence folder)."""
    from PIL import Image
    tile = 160
    sheet = Image.new("RGB", (tile * len(records), tile * 2), (20, 20, 24))
    for i, record in enumerate(records):
        image = Image.open(out / record["file"]).convert("RGBA").resize((tile, tile))
        dark = Image.new("RGBA", (tile, tile), (20, 20, 24, 255))
        light = Image.new("RGBA", (tile, tile), (70, 140, 90, 255))
        sheet.paste(Image.alpha_composite(dark, image).convert("RGB"), (i * tile, 0))
        sheet.paste(Image.alpha_composite(light, image).convert("RGB"), (i * tile, tile))
    path = out / "textures-sheet.png"
    sheet.save(path)
    return path


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.roblox_vfx_textures")
    parser.add_argument("out")
    parser.add_argument("--upload", action="store_true", help="upload reviewed textures to STAR's own account")
    parser.add_argument("--home", help="STAR home with the Open Cloud key settings (required with --upload)")
    args = parser.parse_args(arguments)
    out = Path(args.out)
    records = generate(out)
    contact_sheet(out, records)
    if args.upload:
        from .roblox_cloud import RobloxCloud
        cloud = RobloxCloud(home=Path(args.home))
        try:
            for record in records:
                if record["review"]:
                    record["upload"] = {"ok": False, "detail": "review failed: " + "; ".join(record["review"])}
                    continue
                record["upload"] = cloud.upload_image_asset((out / record["file"]).read_bytes(),
                                                            display_name=f"STAR VFX {record['name']}",
                                                            description="Procedural particle texture made by STAR")
        finally:
            cloud.close()
    (out / "textures.json").write_text(json.dumps(records, indent=1), encoding="utf-8")
    print(json.dumps([{k: r.get(k) for k in ("name", "file", "review", "upload")} for r in records], indent=1))
    return 0 if all(not r["review"] for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
