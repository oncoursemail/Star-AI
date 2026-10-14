# `star.intelligence`

Source: `star/intelligence.py`

STAR's optional local intelligence adapters.

Models see concise, task-relevant function schemas; source content is fetched
only after a validated tool call. No arbitrary subprocess, shell, vault writes,
or user-supplied MCP server is exposed here.

## Constants

`SKILL_TOOLS`, `ASSET_TOOLS`, `OBSIDIAN_TOOLS`, `GRAPHIFY_TOOLS`, `ROBLOX_GAME_TOOLS`, `ROBLOX_KNOWLEDGE_TOOLS`, `DOC_KNOWLEDGE_TOOLS`, `CRAFT_TOOLS`, `ROBLOX_VIDEO_TOOLS`, `ROBLOX_CLOUD_TOOLS`, `DESIGN_TOOLS`, `MAP_PLAN_TOOLS`, `ROBLOX_DOCS_LIVE_TOOLS`, `MAX_TOOL_TEXT`, `ALL_TOOLS`

## Classes

### `LocalIntelligence`

Read-only adapters are initialized from validated desktop settings.

#### `__init__`

```python
def __init__(self, *, home: Path, workspace: Path | None=None, obsidian_vault: Path | None=None, skills_enabled: bool=True, graphify_enabled: bool=True, roblox_research_enabled: bool=True, asset_forge_enabled: bool=False, docs=None, cloud=None, design_enabled: bool=True, map_plans_enabled: bool=True, docs_live: RobloxDocsLive | None=None, registered_workspaces: Iterable[Path | str]=(), graph_boundary_check: Callable[[], bool] | None=None)
```

#### `close`

```python
def close(self) -> None
```

Revoke this hub. Dispatch holds no SQLite handle between calls.

#### `status`

```python
def status(self) -> dict
```

#### `definitions`

```python
def definitions(self, prompt: str) -> list[dict]
```

Conserve small-model context and plain-chat streaming where possible.

#### `owns`

```python
def owns(name: str) -> bool
```

#### `call`

```python
def call(self, name: str, args: dict, *, enabled: set[str]) -> dict
```

## Functions

### `for_settings`

```python
def for_settings(settings, home: Path) -> LocalIntelligence
```

Register the owner-selected workspace, not any path supplied by the model.

A new hub belongs to each turn. A changed in-memory settings snapshot
revokes its graph boundary; independently saved settings are not watched
while a turn is already running.
