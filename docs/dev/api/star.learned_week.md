# `star.learned_week`

Source: `star/learned_week.py`

What STAR learned this week: night school's reviewed bundle reaching the app, visibly, with expiry and undo.

W7 of docs/research/self-improving-star-claude-v2.md, with the owner's defaults (docs/agents/context/
CHATGPT_PLANS_20261013.md, owner decision O1):

* The nightly export is a REVIEWED BUNDLE (`star-learning-bundle-v1`), built from night school's outbox by
  `python -m star.learned_week bundle` and committed through a draft pull request. Nothing reaches the app silently and
  no weights change: a bundle is text (lessons) and checked practice answers (worked examples).
* A text-only lesson goes live automatically ("provisional") only when its evidence shows it won night school's paired
  gate (W1, decision PROMOTE) against the protected baseline on the held-out validation slice. Everything else (the
  old single-run rule, INCONCLUSIVE, no evidence) arrives as a candidate that waits for the owner, as before.
* Every item that goes live is listed in "What STAR learned this week" with its evidence, expires 14 days after it
  went live unless the owner presses Keep, and can be undone with one click. Undo, then Restore, gives back the
  byte-identical lesson row. The owner can turn automatic use off (`learning_auto_live`); then bundles only add
  candidates.
* A lesson is text only (star/lessons.py refuses keys, passwords and permission requests). Nothing here can edit an
  evaluation, a grader, the gate or a setting.

Storage: lesson rows stay in the knowledge database (`notes`), with `revision = "provisional:<expiry ISO time>"` so that
recall skips an expired lesson even before the next sweep; this module's own table `learned_items` keeps the evidence,
the dates and a snapshot of each row for undo. Worked examples go to `worked_examples.sqlite3` (star/worked_examples.py)
with their expiry in `example_expiry`; using them in answers stays behind the owner's `worked_examples_enabled`.

## Constants

`FORMAT`, `EXPIRY_DAYS`, `WEEK_DAYS`, `PROVISIONAL`, `MAX_BUNDLE_BYTES`, `MAX_LESSONS`, `GATE`, `STATES`, `LEARNED_ACTIONS`

## Classes

### `Registry`

Lessons (in the knowledge database) and worked examples that arrived from a bundle, with their dates.

#### `__init__`

```python
def __init__(self, home: Path, *, clock=now)
```

#### `close`

```python
def close(self) -> None
```

#### `apply`

```python
def apply(self, data: dict, *, auto_live: bool=True, project: str | None=None) -> dict
```

Lessons with a PROMOTE verdict go live for 14 days (when `auto_live`); other lessons become candidates;
worked examples are stored with a 14-day expiry. Idempotent: an item seen before is skipped. `project`
(the app's current project) replaces the bundle's own project name.

#### `sweep`

```python
def sweep(self, project: str) -> int
```

Retire every live item whose 14 days are over. Returns how many.

#### `week`

```python
def week(self, project: str) -> dict
```

Items that went live or expired in the last 7 days, plus every item still on its 14-day trial, newest
first.

#### `undo`

```python
def undo(self, project: str, item_id: int, *, human_approved: bool=False) -> dict
```

One click: STAR stops using this item now. The record stays so Restore can bring it back.

#### `restore`

```python
def restore(self, project: str, item_id: int, *, human_approved: bool=False) -> dict
```

Undo the undo: the lesson row comes back byte for byte (same text, status, revision and dates).

#### `keep`

```python
def keep(self, project: str, item_id: int, *, human_approved: bool=False) -> dict
```

The owner keeps an item for good: a lesson becomes an owner-approved lesson, an example loses its expiry.

## Functions

### `expired`

```python
def expired(revision: str, at: str) -> bool
```

True for a provisional lesson whose 14 days are over (the same comparison recall makes in SQL).

### `gate_of`

```python
def gate_of(evidence: str) -> dict
```

The paired-gate verdict written into a night-school lesson's evidence; {"decision": "NONE"} when absent.

### `build_bundle`

```python
def build_bundle(outbox: Path, *, project: str='STAR', created: str | None=None, scoreboard: str='', report: dict | None=None) -> dict
```

Package night school's outbox (`star-lessons-night-school.json`, `worked-examples.jsonl`) for review.
Every row is validated with the app's own importers first; the bundle is plain data for a pull request.

### `parse_bundle`

```python
def parse_bundle(data: object) -> dict
```

Validate a whole bundle before any write. Imported statuses are never trusted: only the gate verdict in the
lesson's own evidence decides whether it may go live automatically.

### `read_bundle`

```python
def read_bundle(path: Path) -> dict
```

### `handle_action`

```python
def handle_action(home: Path, project: str, action: str, body: dict) -> dict
```

`learnedThisWeek` lists; `learnedItem` {op: undo|restore|keep, id, approved: true} is an owner click.

### `import_bundled`

```python
def import_bundled(home: Path, version: str, *, auto_live: bool=True, bundle: Path | None=None, project: str | None=None) -> dict
```

Apply the bundle shipped with this app version once (star/skill_packs/learning_bundle.json, when present).

### `main`

```python
def main(argv: list[str] | None=None) -> int
```
