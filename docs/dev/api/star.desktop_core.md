# `star.desktop_core`

Source: `star/desktop_core.py`

STAR Desktop's local-only backend. The Qt GUI calls this from worker threads.

## Constants

`TERMINAL_STATUSES`, `SERVER_HISTORY_CHARS`

## Classes

### `Settings`

#### `load`

```python
def load(cls, file: Path)
```

#### `validate`

```python
def validate(self)
```

#### `save`

```python
def save(self, file: Path)
```

### `Conversations`

Persistent, project-scoped chat threads.

Existing messages are migrated in-place into a legacy thread without deleting
or rewriting their content. Callers that omit chat_id retain the historical
project-wide recent() behavior; React explicitly selects a thread.

#### `__init__`

```python
def __init__(self, db: Path)
```

#### `new_chat`

```python
def new_chat(self, project: str) -> str
```

#### `active_chat`

```python
def active_chat(self, project: str) -> str
```

#### `switch_chat`

```python
def switch_chat(self, project: str, chat_id: str) -> None
```

#### `list_chats`

```python
def list_chats(self, project: str, limit: int=60) -> list[dict]
```

#### `add`

```python
def add(self, project: str, role: str, body: str, chat_id: str | None=None, *, status: str='complete', reply_to: int | None=None) -> int
```

Store one message and return its row id.

#### `add_terminal`

```python
def add_terminal(self, project: str, chat_id: str, user_id: int, status: str, detail: str) -> int | None
```

Record that the turn started by user message ``user_id`` ended without an answer.

Idempotent: a turn gets at most one terminal record. Returns the new row id,
or None when the turn was already closed.

#### `recent`

```python
def recent(self, project: str, limit: int=70, chat_id: str | None=None, include_events: bool=True)
```

Newest ``limit`` messages, oldest first. Model context passes include_events=False.

#### `history_rows`

```python
def history_rows(self, project: str, chat_id: str | None=None, clip: int=4000)
```

Every user/assistant row of the chat as (role, text), oldest first, without events.

All rows, not the newest few: the model's history window is measured from the
first message of the chat so that it stays put from turn to turn (see
context_layout.conversation_window). Each text is cut to ``clip`` characters.

#### `raw_history_records`

```python
def raw_history_records(self, project: str, chat_id: str | None=None) -> list[dict]
```

Full ID-bearing records of exactly one chat, including terminal outcomes.

#### `recent_records`

```python
def recent_records(self, project: str, limit: int=70, chat_id: str | None=None) -> list[dict]
```

Like recent(), with row ids and turn outcome, for the UI state payload.

#### `set_feedback`

```python
def set_feedback(self, project: str, message_id: int, value: str) -> dict
```

Store, change or clear ('') the owner's thumb on one answer of this project.

Returns the chat, the answer and the question it answered, for the lesson record.

#### `turn_context`

```python
def turn_context(self, project: str, chat_id: str | None, prompt: str='') -> dict
```

The message being answered now and what happened to the turn before it.

For after-turn learning (star/lessons.py): a correction is linked to the answer it
follows, and a repeat of a failed message is a retry. Read-only. `message_id` is None
when the newest stored user message is not the one in `prompt` (a direct call that
saved nothing).

#### `retry_state`

```python
def retry_state(self, project: str, chat_id: str, busy: bool=False) -> dict | None
```

What happened to the newest user message in a chat, if it got no answer.

Returns None when the newest turn was answered (or there is no turn, or a
task is still running). Otherwise: status failed/cancelled from the stored
terminal record, or 'interrupted' when nothing at all was recorded after the
message (for example STAR was closed mid-reply). Derived on read, never written.

#### `recover_turn`

```python
def recover_turn(self, project: str, chat_id: str, message_id: int, prompt: str) -> int
```

Reuse an unanswered question after restart without inserting another user row.

#### `rename_chat`

```python
def rename_chat(self, project: str, chat_id: str, title: str) -> str
```

Give one conversation of this project a title the owner chose. Returns the stored title.

#### `delete_chat`

```python
def delete_chat(self, project: str, chat_id: str) -> str
```

Remove one conversation of this project: its messages, thumbs and context checkpoint.

Generated image files are not touched (they stay in the STAR data folder). When the
deleted chat was the open one, the newest remaining chat opens (or a new blank one).
Returns the chat that is open afterwards.

#### `projects`

```python
def projects(self)
```

#### `close`

```python
def close(self)
```

## Functions

### `app_data`

```python
def app_data() -> Path
```

### `recent_context`

```python
def recent_context(recent: list[tuple[str, str, str]], current_prompt: str) -> str
```

Exclude the current turn if the UI already saved it to the conversation DB.

This prevents the local model receiving the exact same new user request
as both system-context history and the actual user message.

### `query_models`

```python
def query_models(settings: Settings) -> list[str]
```

### `check_studio`

```python
def check_studio(settings: Settings | None=None, home: Path | None=None)
```

### `redact_for_logs`

```python
def redact_for_logs(value)
```

Image bytes are retained in the artifact store, not duplicated in transcripts.

### `needs_project_tools`

```python
def needs_project_tools(prompt: str, prior_user_turns: list[str] | None=None, *, blender: bool=False) -> bool
```

Load task tools on explicit request or scoped short edit follow-up.

User context hints are not permissions; executable scopes remain enforced.

### `needs_studio_connection`

```python
def needs_studio_connection(prompt: str, prior_user_turns: list[str] | None=None, *, blender: bool=False) -> bool
```

Only connect to Roblox Studio for an actual selected-place operation.

A configured studio_id is NOT a request to connect for every agent call.
Public Roblox game stats, forum research, generic coding discussions,
image generation and tool catalogues must remain independent of Studio.

### `model_context_char_budget`

```python
def model_context_char_budget(settings: Settings, model: str | None=None) -> int
```

Conservative CHAR proxy, not an exact tokenizer, for managed local router.

The router's ctx-size is in tokens; complex Luau/MCP schemas can have many
tokens per character. Keep a reserve for the active user prompt, tools and
response. Other inference endpoints retain their existing settings.

### `history_char_budget`

```python
def history_char_budget(settings: Settings) -> int
```

Characters of earlier turns to replay.

Cached history costs nothing per turn; what costs is the first message
after a start and each time the window moves, when the server reads what is
in the window again (see conversation_memory.select_window: the window
moves by half of this budget at a time, and one replayed message is at most
a quarter of it).

  cloud        12000: a hosted provider reads fast.
  STAR Server  12000: measured on the owner's server (docs/agents/model-routing.md).
               The old 6000 cut every replayed message at 1500 characters, less than
               one Fast-mode answer, and kept one to three exchanges. 12000 keeps a
               whole Fast-mode answer (3000 characters) and three to seven exchanges.
               A window move re-reads about 6000 characters; the post-answer warm-up
               does that while the owner reads the answer.
  on this PC   6000: small GPU models with small contexts; unchanged.

One budget for every model of a server: the window is then the same request
start whichever model answers.

### `stable_memory`

```python
def stable_memory(settings: Settings, checkpoint: str) -> str
```

The part of the compacted checkpoint that goes into the system message.

### `memory_scope_for`

```python
def memory_scope_for(settings: Settings, chat_id: str | None) -> str
```

### `chat_history`

```python
def chat_history(settings: Settings, home: Path, chat_id: str | None)
```

Earlier turns of a chat exactly as the next request will replay them.

Returns (history messages, newest stored rows). The same function feeds a
real turn and the cache warm-up, so both start with identical bytes. A
trailing user row is the message being answered now (already saved by the
UI) and is not history; an earlier message that never got a reply (failed,
stopped or interrupted) is left out, with no placeholder answer (see
conversation_memory.select_window).

### `chat_history_snapshot`

```python
def chat_history_snapshot(settings: Settings, home: Path, chat_id: str | None, *, current_text=None)
```

Full scoped originals and a pure bounded window, shared with warm-up.

### `with_sent_times`

```python
def with_sent_times(window)
```

Each replayed user turn ends with the time line it was first sent with.

A plain chat turn is sent as the owner's words plus a context block holding only the
current time (star.agent.volatile_context). Replaying the earlier turns with the same
block, rebuilt from each message's stored timestamp, keeps the request starting with the
bytes the model server already read. Same number and order of messages as the window.

### `current_turn_line`

```python
def current_turn_line(records) -> str
```

The time line for the message being answered: from its stored timestamp (so the next turn
replays the same bytes), with a live server-clock note if the clocks differ; else the time now.

### `picture_limit`

```python
def picture_limit(settings) -> int | None
```

Longest side of a picture as the model reads it: capped on our own hardware, untouched for hosted models.

### `run_task`

```python
def run_task(settings: Settings, prompt: str, images: list[Path] | None=None, on_event: Callable[[dict], None] | None=None, stream_tokens: bool=False, mode: str='auto', research: bool=False, cancel_event=None, github_enabled: bool=False, chat_id: str | None=None, owner_text: str | None=None, documents: list[Path] | None=None, studio_configuration_home: Path | None=None, attachment_count: int=0) -> str
```

User-controlled fast/automatic/agent routing; all hosted calls are opt-in.

`owner_text` is what the owner typed, when `prompt` also carries text STAR added (an
audio transcript, a note about video frames). Only the owner's own words can become an
automatically accepted lesson.
