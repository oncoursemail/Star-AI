# `star.agent`

Source: `star/agent.py`

A working local vision + tool-calling agent loop with bounded autonomy.

## Constants

`UNTRUSTED_SOURCE_TOOLS`, `LUAU_AFTER_UNTRUSTED`, `RULES`, `FAST_RULES`

## Classes

### `HistoryWindowPressure`(RuntimeError)

Complete replay turns need retention before they can leave the request.

#### `__init__`

```python
def __init__(self, dropped: list[dict], *, dispatched: bool, tool_actions_started: bool)
```

## Functions

### `tool_payload`

```python
def tool_payload(result)
```

Tool results returned to model are capped to prevent runaway context.

### `system_prefix`

```python
def system_prefix(project_memory: str='', *, tools_attached: bool=True, guidance: str='') -> str
```

The byte-stable start of every request of one conversation.

Rules first, then standing guidance, then stable project memory (the
compacted checkpoint, which only changes when a checkpoint is written).
Nothing that differs between two turns belongs here: the selected Studio,
retrieved notes, the mode and the date go through `volatile_context`.

### `make_system_message`

```python
def make_system_message(project_memory: str='', *, tools_attached: bool=True, guidance: str='') -> dict
```

Strict Qwen3.5/llama.cpp templates permit one system message at index 0.

Project notes may be incomplete or untrusted. Append them inside that one
first message rather than introducing another system role mid-conversation.

### `volatile_context`

```python
def volatile_context(sections=(), *, tools_attached: bool=False, studio_id: str='', may_edit: bool=False, mode: str='', today: str='', limit: int=10000, now: str='') -> str
```

Everything that may differ from one turn to the next, as one text block.

This is the ONLY place per-turn context enters a model request. The block
is appended to the final user turn, after the user's own words; it is never
put in the system message or in an earlier turn, so the start of the
request stays identical from turn to turn and the server can reuse what it
already read.

`sections` is a list of (heading, text) pairs: reviewed notes, web sources,
documentation passages. To add a new retrieval source, append one pair to
the caller's `turn_sections`; nothing else needs to change.

`now` (star.clock.now_line) is the last line of the block: the current date,
time and zone change every turn, so they belong at the very end.

Plain chat with no sections and no `now` returns "": the turn is sent as typed.

### `validate_model_roles`

```python
def validate_model_roles(messages: list[dict]) -> None
```

Reject malformed chat templates locally, before they become HTTP 500s.

### `text_size`

```python
def text_size(messages: list[dict]) -> int
```

Approximate text budget, excluding encoded image bytes. Not a token counter.

### `read_stream`

```python
async def read_stream(stream, event, *, lead: str='', call_prefix: str='call_', seen: dict | None=None)
```

Collect one streamed model turn.

Visible text is forwarded as `assistant_delta` events while it arrives
(reasoning is never forwarded). Tool calls arrive in fragments keyed by
`index`; they are joined into complete calls with the same shape as a
non-streamed reply. Returns (text, tool_calls, whether any text was shown).
`lead` is put before the first visible text, to separate it from text an
earlier model turn of the same task already showed.

Two early signals keep a slow server from looking idle: `model_responding`
when the first chunk arrives (the prompt has been read, writing has begun)
and `tool_requested` when the model starts to write a tool call. Neither
carries a name or arguments: nothing has been authorized or run yet.

`seen`, when given, receives `seen['model']`: the model name the server put
on its chunks, which is the model that really answered.

### `execute`

```python
async def execute(*, client, model: str, prompt: str, image_paths: list[Path], studio=None, discovered=None, studio_id='', may_edit=False, project_memory='', max_calls=12, context_chars=25000, checkpoint=None, on_event=None, allow_luau=False, workspace=None, workspace_edit=False, stream_tokens=False, response_tokens=1600, web_search_enabled=False, subagents_enabled=False, subagent_parallelism=1, github_enabled=False, intelligence=None, mcp_gateway=None, mcp_registry=None, blender=None, subagent_model=None, tool_workshop=None, specialists=None, history=None, turn_sections=None, mode='', guidance='', turn_context_chars=10000, request_extras=None, today=None, tool_memory=None, helper_client=None, document_tools=None, image_max_side=None, preserve_history=False, complete_code_answers=None, tool_discovery_enabled=False, candidate_code_team_enabled=False, now=None, web_settings=None)
```

Run one user turn.

Request layout (see star/context_layout.py): one system message holding the
rules and `project_memory` (stable), then `history` (earlier user/assistant
turns, oldest first), then this turn's user message with `turn_sections`
and the other per-turn facts appended by `volatile_context`.
`now` is the current-time line appended last to this turn's context (default
star.clock.now_line(); "" leaves it out). `web_settings` are the Settings the
web search/fetch tools read (search gateway address); None loads the saved ones.
`request_extras` are provider-specific body fields from
`providers.llama_request_fields`; they are empty for cloud providers.
`tool_memory` (star/turn_memory.py) keeps the prompt-selected tools of a
conversation attached, in a fixed order, so the tool list at the start of
the prompt stays byte-identical from turn to turn. `helper_client` is the
client for calls that are not this conversation (summaries, sub-agents);
on a llama.cpp server its requests carry no `id_slot` and the server places them.
