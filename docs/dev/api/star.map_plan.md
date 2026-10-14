# `star.map_plan`

Source: `star/map_plan.py`

Map plans: a declarative JSON description of a Roblox blockout and an offline dry run.

The shape is inspired by the SceneSpec format of ShiroKSH/skills
(https://github.com/ShiroKSH/skills, MIT, commit b1251cc): a named map under a managed root
(``Workspace/MapDrafts``), tagged Roblox values, an explicit asset allowlist, and a dry run that
reports what an apply would do before anything touches Studio. This module is an independent,
much smaller Python implementation; no ShiroKSH code is copied.

What the dry run checks (all offline, deterministic, no Studio needed):
- schema (jsonschema), unique names, managed root, object limit;
- bounds: every object's axis-aligned box (rotation included) inside the declared bounds;
- overlaps between solid objects (with a z-fighting hint when two faces share a plane);
- spawns: at least one, inside the bounds, with head room above the pad;
- route: each leg between waypoints is jumpable for a default character (gap and rise);
- assets: only ids on the plan's allowlist; unanchored and floating parts are reported.

``dry_run(plan)`` returns the report; when there are no blockers it also returns the ordered
operations (create folder / part / spawn, insert allowlisted asset, set lighting) that STAR's
Studio tools can apply later, and ``to_luau(plan)`` renders the same operations as one Luau
script that records a single undo step. Nothing here applies anything.

## Constants

`MANAGED_ROOT`, `DEFAULT_MAX_JUMP_GAP`, `DEFAULT_MAX_JUMP_RISE`, `CHARACTER_HEADROOM`, `SPAWN_SIZE`, `BATCH_SIZE`, `OVERLAP_TOLERANCE`, `SUPPORT_TOLERANCE`, `MAX_REPORTED`, `CREDIT`, `PART_CLASSES`, `MATERIALS`, `STYLES`, `ROLES`, `SCHEMA`

## Functions

### `dry_run`

```python
def dry_run(plan, *, include_operations: bool=True) -> dict
```

Validate a plan and report what applying it would do. Never raises on bad input.

### `operations`

```python
def operations(plan: dict) -> list[dict]
```

Ordered, Studio-neutral operations with tagged values (Vector3, Color3, Enum).

### `to_luau`

```python
def to_luau(plan: dict) -> str
```

One Luau script (for a throwaway place) that builds the plan under the managed root as a
single undo step. Refuses plans with blockers. Assets are left to the Studio insert tool.
