# `star.skill_packs`

Source: `star/skill_packs/__init__.py`

Roblox skill packs: short guidance distilled from the official documentation.

A pack is an ordinary Agent Skill (a folder with SKILL.md and references/, the format read by
`star.agent_skills`), shipped inside the application. Unlike a skill the model has to ask for, a pack
is chosen here, in code, from the user's words: it is added to the turn only when the prompt is a
Roblox question AND names the pack's topic, so unrelated prompts are byte-for-byte unchanged.

Where it goes: `desktop_core.run_task` appends the rendered block to `turn_sections`, which
`star.agent.volatile_context` puts after the user's own words. It never enters the system message,
which stays byte-stable for the model server's prompt cache.

Cost: the text is read by the model on every turn it is added. Only the best-matching pack is added
(MAX_PACKS_PER_TURN = 1). Bodies must fit MAX_BODY_CHARS; richer, unmeasured design packs remain opt-in.
Do not extend latency measurements from the shorter measured packs to these longer packs.

Whether a pack is on is decided by evidence, not by hope: a pack is enabled by default (DEFAULT_ENABLED)
only after the evaluation gate (docs/evals.md) showed that it does not lower the golden-task score.
`STAR_SKILL_PACKS` overrides it: `off`, `all`, or a comma list of pack names.

## Constants

`PACKS_DIR`, `ENV_VAR`, `MAX_BODY_CHARS`, `MAX_PACKS_PER_TURN`, `MAX_BLOCK_CHARS`, `BLOCK_HEADING`, `GODOT_PACKS`

## Classes

### `Pack`

## Functions

### `available`

```python
def available() -> tuple[Pack, ...]
```

Every pack shipped in this folder, in the order of TRIGGERS. A broken pack is skipped, never fatal.

### `enabled_names`

```python
def enabled_names(environ=None, *, home=None) -> frozenset[str]
```

Pack names that may be used now: STAR_SKILL_PACKS, else DEFAULT_ENABLED.

### `select`

```python
def select(prompt, *, enabled=None, limit: int=MAX_PACKS_PER_TURN, home=None) -> list[Pack]
```

The packs for this prompt, best match first. Empty for anything that is not a Roblox question.

### `render`

```python
def render(packs) -> str
```

The text added to the turn under BLOCK_HEADING, '' when no pack applies. Bounded by MAX_BLOCK_CHARS.

### `matching_names`

```python
def matching_names(prompt, *, enabled=None) -> list[str]
```
