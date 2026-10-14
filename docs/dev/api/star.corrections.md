# `star.corrections`

Source: `star/corrections.py`

Owner corrections become regression-test candidates (W8 of docs/research/self-improving-star-claude-v2.md).

When the owner marks an answer as wrong and says what was wrong (thumbs-down plus a correction in the app, or a
`wrong: ...` / `correction: ...` DM to the Discord bot right after STAR's answer), STAR keeps a CANDIDATE: the original
prompt, an excerpt of the failing answer, the owner's correction and a check stub. Nothing more happens by itself:

* a candidate is added to the separate CORRECTIONS SUITE only when the owner approves it (an explicit click);
* the corrections suite is a development-tier task file in STAR's own data folder
  (`<data>/corrections/corrections-<project>.json`, same JSON shape as the evaluation suites). It is never the blind
  holdout and never written into the repository's `evals/` folder: the writer refuses such paths;
* everything stays on this PC. Text that looks like a key or password is refused and private addresses are replaced
  before anything is stored;
* each candidate is also a failure-ledger record (`as_failures`), so practice can target the cause.

The check stub is honest about what it is: `forbid`/`require` patterns only when the correction names them plainly
("use X instead of Y", "don't use Y"), otherwise the task is a `human` task that the owner (or a later session) gives a
real check. `check_status` says "stub" until then.

## Constants

`STATUSES`, `SOURCES`, `MAX_PROMPT`, `MAX_ANSWER`, `MAX_CORRECTION`, `CORRECTION_ACTIONS`

## Classes

### `CorrectionStore`

#### `__init__`

```python
def __init__(self, home: Path)
```

#### `close`

```python
def close(self) -> None
```

#### `record`

```python
def record(self, *, project: str, source: str, ref: str, prompt: str, answer: str, correction: str) -> dict
```

Keep one candidate per corrected answer (a second correction of the same answer updates the text).

#### `withdraw`

```python
def withdraw(self, *, project: str, source: str, ref: str) -> int
```

The owner took the thumbs-down back: an unreviewed candidate goes too.

#### `get`

```python
def get(self, project: str, item_id: int) -> dict
```

#### `list`

```python
def list(self, project: str, status: str | None=None) -> list[dict]
```

#### `counts`

```python
def counts(self, project: str) -> dict
```

#### `suite_path`

```python
def suite_path(self, project: str) -> Path
```

#### `approve`

```python
def approve(self, project: str, item_id: int, *, human_approved: bool=False) -> dict
```

The owner promotes a candidate into the corrections suite (never the holdout).

#### `dismiss`

```python
def dismiss(self, project: str, item_id: int, *, human_approved: bool=False) -> dict
```

#### `as_failures`

```python
def as_failures(self, project: str)
```

Every non-dismissed correction as a failure-ledger record, for targeted practice.

## Functions

### `scrub`

```python
def scrub(text: str, limit: int, *, one_line: bool=False) -> str
```

### `cause_for`

```python
def cause_for(correction: str) -> str
```

The failure-ledger cause a correction most plainly describes; "wrong logic" otherwise.

### `check_stub`

```python
def check_stub(correction: str, answer: str) -> dict
```

Patterns the correction itself names. Empty when it names none (the task then needs a human-written check).

### `task_for`

```python
def task_for(item: dict, task_id: str) -> dict
```

A corrections-suite task in the evaluation-suite shape. Patterns only when the owner named them.

### `write_suite`

```python
def write_suite(path: Path, tasks: list[dict]) -> None
```

Write the corrections suite. Never inside an `evals` folder, never a golden or holdout file.

### `handle_action`

```python
def handle_action(home: Path, project: str, action: str, body: dict) -> dict
```
