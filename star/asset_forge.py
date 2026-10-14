"""Bounded asset discovery and deterministic geometry briefs for Roblox creators.

This is a planning/research layer, not a Blender renderer or Studio write tool.
Third-party text is untrusted; only a fixed, documented public API is queried.
"""
from __future__ import annotations

import json
import math
import re
import time

import httpx

_API = "https://api.polyhaven.com"
_SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\Z")
_KINDS = {"models": 2, "textures": 1, "hdris": 0}
_MAX_RESPONSE = 160_000
_BAY = 12
_FLOOR = 14
_STYLES = {
    "classic-studs": {"form": "Roblox-stud grid, crisp silhouettes, intentionally simple trim",
                      "materials": ["plastic", "brick", "painted metal"], "palette": ["#c1b6a3", "#756d65", "#b48c64", "#393939"]},
    "stylized-fantasy": {"form": "Readable stepped silhouettes, timber structure, carved trim",
                         "materials": ["timber", "stone", "plaster"], "palette": ["#c9ae7e", "#5a6750", "#704c35", "#e1d3aa"]},
    "grounded-realism": {"form": "Architectural proportions, restrained bevels, varied masonry",
                         "materials": ["stone", "concrete", "aged wood"], "palette": ["#a7a39a", "#5d615d", "#897761", "#c0b8a9"]},
    "anime-toon": {"form": "Clean planes, broad eaves, strong silhouette, controlled outlines",
                    "materials": ["painted plaster", "tile", "wood"], "palette": ["#f2d9b7", "#758a97", "#b96556", "#534c5a"]},
}
_BIOMES = frozenset({"temperate", "desert", "alpine", "alien"})


def _short(value, length=220) -> str:
    return re.sub(r"\s+", " ", value).strip()[:length] if isinstance(value, str) else ""


def _between(name: str, value: int, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")
    return value


class PolyHavenCatalog:
    """Read-only, source-attributed asset search. No arbitrary URL or download."""

    def __init__(self, *, client: httpx.Client | None = None, now=None):
        self._client = client or httpx.Client(timeout=8.0, follow_redirects=False, trust_env=False,
                                            headers={"User-Agent": "STAR-Intelligence-Assets/1.0",
                                                     "Accept": "application/json"})
        self._owned = client is None
        self._now = now or time.time

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self._owned:
            self._client.close()

    def _get(self, path: str, params=None) -> dict:
        try:
            with self._client.stream("GET", _API + path, params=params, timeout=8.0,
                                     follow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError(f"Poly Haven returned HTTP {response.status_code}; no asset was imported")
                chunks, received = [], 0
                for chunk in response.iter_bytes():
                    received += len(chunk)
                    if received > _MAX_RESPONSE:
                        raise ValueError("Poly Haven response exceeded the metadata limit")
                    chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise ValueError(f"Poly Haven metadata request failed: {type(exc).__name__}") from None
        try:
            data = json.loads(b"".join(chunks))
        except (ValueError, UnicodeDecodeError):
            raise ValueError("Poly Haven returned invalid JSON") from None
        if not isinstance(data, dict):
            raise ValueError("Poly Haven returned unexpected metadata")
        return data

    def search(self, query: str, *, kind: str = "models", limit: int = 4) -> dict:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100:
            raise ValueError("search query must have 1–100 characters")
        if kind not in _KINDS:
            raise ValueError("asset type must be models, textures, or hdris")
        _between("limit", limit, 1, 6)
        terms = query.strip().lower()
        deadline = time.monotonic() + 15.0  # soft bound; an in-flight request may take up to 8s more
        data = self._get("/search", {"q": terms, "t": kind, "limit": limit, "future": "false"})
        ranked = data.get("results")
        if not isinstance(ranked, list):
            raise ValueError("Poly Haven search response lacks ranked results")
        matches = []
        truncated = False
        for row in ranked[:limit]:
            if time.monotonic() >= deadline:
                truncated = True
                break
            if not isinstance(row, dict) or not isinstance(row.get("slug"), str):
                continue
            slug = row["slug"]
            if not _SLUG.fullmatch(slug):
                continue
            info = self._get(f"/info/{slug}")
            if info.get("type") != _KINDS[kind]:
                continue
            published = info.get("date_published")
            if type(published) in (int, float) and published > self._now():
                continue
            thumb = info.get("thumbnail_url")
            if not (isinstance(thumb, str) and thumb.startswith("https://cdn.polyhaven.com/")):
                thumb = None
            score = row.get("score")
            score = round(score, 4) if type(score) in (float, int) and math.isfinite(score) else None
            matches.append({
                "id": slug, "title": _short(info.get("name"), 120),
                "description": _short(info.get("description")),
                "type": kind, "category": _short(info.get("category"), 120),
                "source_url": f"https://polyhaven.com/a/{slug}",
                "thumbnail_url": thumb, "ranking_score": score,
                "license": "CC0", "license_url": "https://polyhaven.com/license",
            })
        return {"provider": "Poly Haven", "credit": "Powered by Poly Haven", "untrusted": True,
                "query": terms, "type": kind, "assets": matches, "truncated": truncated,
                "note": "Official public metadata only. When reporting these results, say Powered by Poly Haven "
                        "and cite each source_url. Inspect source files, geometry, terms and suitability before importing."}


def plan_building(*, width_bays: int = 4, depth_bays: int = 4, floors: int = 2,
                  style: str = "stylized-fantasy", seed: int = 1) -> dict:
    """Create a reproducible modular architectural *specification*, not a baked mesh."""
    _between("width_bays", width_bays, 3, 6)
    _between("depth_bays", depth_bays, 3, 6)
    _between("floors", floors, 1, 3)
    _between("seed", seed, 0, 2_147_483_647)
    if style not in _STYLES:
        raise ValueError("unknown style preset")
    width, depth = width_bays * _BAY, depth_bays * _BAY
    entry = width_bays // 2
    # Alternate stair flights so each slab opens above the preceding stair, not the next one.
    def stair_bay(floor: int) -> tuple[int, int]:
        return (entry - 1 if floor % 2 == 0 else entry + 1, depth_bays - 2)

    modules, zones, walls = [], [], {}
    room_count = 0
    for floor in range(floors):
        lower = floor * _FLOOR
        modules.append({"id": f"slab-{floor}", "kind": "floor-slab",
                        "center": [0, lower, 0], "size": [width, 1, depth],
                        "cutouts": ([{"bay": list(stair_bay(floor - 1)), "kind": "stairwell"}] if floor else [])})
        for side in ("front", "back", "left", "right"):
            length = width_bays if side in ("front", "back") else depth_bays
            bays = []
            for bay in range(length):
                opening = ("D" if side == "front" and floor == 0 and bay == entry
                           else "W" if (bay + floor + seed) % 3 != 0 else "S")
                bays.append(opening)
            walls[f"{side}/{floor}"] = " ".join(bays)
        for x in range(width_bays):
            for z in range(depth_bays):
                bay = (x, z)
                if floor < floors - 1 and bay == stair_bay(floor):
                    purpose = "stairs"
                elif floor and bay == stair_bay(floor - 1):
                    purpose = "landing"
                elif x == entry:
                    purpose = "corridor"
                else:
                    room_count += 1
                    continue
                zones.append({"floor": floor, "bay": [x, z], "purpose": purpose})
        if floor < floors - 1:
            modules.append({"id": f"stair-{floor}", "kind": "stairs",
                            "from_floor": floor, "to_floor": floor + 1, "bay": list(stair_bay(floor)),
                            "clearance_studs": _FLOOR})
    modules.append({"id": "roof", "kind": "roof-kit", "shape": "gable" if style != "grounded-realism" else "flat",
                    "center": [0, floors * _FLOOR + 3, 0], "size": [width + 4, 6, depth + 4]})
    return {"stage": "plan_only", "seed": seed, "style": style, "style_guide": _STYLES[style],
            "footprint_studs": [width, depth], "floor_height_studs": _FLOOR,
            "entrance": {"side": "front", "bay": entry, "floor": 0},
            "wall_bay_guide": {"width_studs": _BAY, "height_studs": _FLOOR,
                               "symbols": {"D": "door", "W": "window", "S": "solid"}},
            "walls": walls, "stairwell_bays": [list(stair_bay(f)) for f in range(floors - 1)],
            "modules": modules, "zones": zones, "room_count": room_count,
            "validation_needed": ["realize door/window openings", "cut stairwell slabs",
                                  "plan separate stair landings and turns", "generate UVs and collision",
                                  "check navigation and structure", "render and inspect in Blender and Roblox Studio"]}

def _hash(x: int, z: int, seed: int) -> float:
    n = (x * 374761393 + z * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF * 2 - 1


def _noise(x: float, z: float, seed: int, scale: float) -> float:
    xf, zf = x / scale, z / scale
    ix, iz = math.floor(xf), math.floor(zf)
    u, v = xf - ix, zf - iz
    u, v = u * u * (3 - 2 * u), v * v * (3 - 2 * v)
    a = _hash(ix, iz, seed) * (1 - u) + _hash(ix + 1, iz, seed) * u
    b = _hash(ix, iz + 1, seed) * (1 - u) + _hash(ix + 1, iz + 1, seed) * u
    return a * (1 - v) + b * v


def terrain_height(x: float, z: float, *, seed: int = 1, biome: str = "temperate") -> float:
    """Sample world-space coordinates so adjacent exported chunks share exact edges."""
    _between("seed", seed, 0, 2_147_483_647)
    if biome not in _BIOMES:
        raise ValueError("unknown biome")
    base = 16 + 30 * _noise(x, z, seed, 160) + 12 * _noise(x, z, seed + 73, 48)
    fine = 4 * _noise(x, z, seed + 137, 12)
    if biome == "alpine":
        return max(0.0, base * 1.9 + fine * 2)
    if biome == "desert":
        return max(0.0, base * .65 + fine * .4)
    if biome == "alien":
        return max(0.0, base + fine + 6 * abs(_noise(x, z, seed + 503, 30)))
    return max(0.0, base + fine)


def preview_terrain(*, seed: int = 1, biome: str = "temperate", size: int = 8,
                    origin_x: int = 0, origin_z: int = 0, step: int = 16) -> dict:
    """Bounded sampled heightfield. No Studio terrain is written."""
    _between("size", size, 4, 16)
    _between("origin_x", origin_x, -100_000, 100_000)
    _between("origin_z", origin_z, -100_000, 100_000)
    _between("step", step, 4, 64)
    points = [[round(terrain_height(origin_x + x * step, origin_z + z * step,
                                    seed=seed, biome=biome), 3) for x in range(size)] for z in range(size)]
    heights = [h for row in points for h in row]
    return {"stage": "heightmap_preview", "seed": seed, "biome": biome,
            "origin_studs": [origin_x, origin_z], "step_studs": step,
            "heights_studs": points, "min_height": min(heights), "max_height": max(heights),
            "note": "Sample identical world coordinates at chunk boundaries. Material masks, erosion, paths and Roblox voxels require a separate validation stage."}
