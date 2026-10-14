# `star.providers`

Source: `star/providers.py`

Strict provider routing and OS-backed credentials for STAR Intelligence.

Never accept a model-supplied base URL or store API tokens in settings/SQLite.
The desktop may use a named hosted model only after the owner configures a key.

Every provider has a typed kind, and callers branch on the kind, never on the id:

  local  the managed llama.cpp brain on this PC's loopback interface (no key)
  lan    STAR Server: an owner-entered private address on the local network,
         OpenAI-compatible, always with an API key
  cloud  a fixed HTTPS vendor with the owner's own key

The LAN address is typed by the owner in Settings. It is validated here, at the
one place every model call passes through, so the server key can only ever be
sent only to a validated private address with no DNS lookup.

## Constants

`SERVICE`, `LOCAL`, `STAR_SERVER`, `SEARCH_KEYS`, `KEY_ENV`, `SLOT_PROBE_TIMEOUT_S`

## Classes

### `Provider`

### `CallLimits`

## Functions

### `validate_lan_endpoint`

```python
def validate_lan_endpoint(value, *, path: str='/v1', label: str='STAR Server', allow_cgnat: bool=False) -> str
```

Return a canonical local-network URL or raise ValueError.

Allow only explicitly listed private IP ranges; hostnames are refused until
connection-level DNS pinning prevents credential exfiltration via rebinding.

### `provider_spec`

```python
def provider_spec(name) -> Provider
```

Typed metadata for a provider id. Unknown ids fail closed.

### `provider_kind`

```python
def provider_kind(settings) -> ProviderKind
```

`local`, `lan` or `cloud` for the selected provider. Compare this, not the id.

### `uses_star_server`

```python
def uses_star_server(settings) -> bool
```

True when STAR Server (LAN) is the selected provider. Never raises, even
for a hand-edited settings file with an unknown provider id.

### `call_limits`

```python
def call_limits(settings) -> CallLimits
```

Per-provider HTTP budget. The LAN server is a slow CPU box: be generous.

### `get_api_key`

```python
def get_api_key(name: str) -> str | None
```

Environment variables take precedence; keyring is optional for CLI tests.

### `save_api_key`

```python
def save_api_key(name: str, token: str) -> None
```

### `clear_api_key`

```python
def clear_api_key(name: str) -> None
```

### `credential_status`

```python
def credential_status() -> dict[str, bool]
```

Never return key bytes to the browser or model.

### `connection_for`

```python
def connection_for(settings) -> tuple[str, str]
```

The single place that decides which address and bearer a model call uses.

### `open_client`

```python
def open_client(settings, *, request_timeout: float | None=None)
```

Build the AsyncOpenAI client for the selected provider with its own limits.

A private LAN server gets an explicit httpx client with `trust_env=False`,
so a Windows system proxy can never see the prompt or the server key.

### `remember_model_names`

```python
def remember_model_names(endpoint: str, model: str, aliases=()) -> None
```

`aliases` are further names of `model` on this server (from its /v1/models list).

### `remember_server_limits`

```python
def remember_server_limits(endpoint: str, model: str, context_tokens: int, slots: int) -> None
```

### `server_context_tokens`

```python
def server_context_tokens(settings, model: str | None=None) -> int
```

Per-request context of a LAN model: the owner's value, else what /props last said, else 0.

`model` is the model a request is routed to; the primary model when omitted.

### `server_slots`

```python
def server_slots(settings, model: str | None=None) -> int
```

Parallel slots a LAN model last reported through /props; 0 while unknown.

### `look_for_busy_slots`

```python
async def look_for_busy_slots(settings, model: str='', *, conversation: str='') -> frozenset
```

Before a chat turn on STAR Server, ask the server which slots of `model` are generating.

Issue 118: two STAR clients share nothing but the server, so their chats can hash to the same
slot, and a turn that names a busy slot waits although another slot is free. The answer is kept
for a few seconds and read once by this turn's `llama_request_fields`, which then moves the chat
to an idle slot (and keeps it there). Only when the request would be pinned at all (STAR Server,
two or more slots, a conversation, pinning not switched off).

Never raises and never delays a turn by more than `SLOT_PROBE_TIMEOUT_S`: any failure (no
answer, an error status, an unreadable page) leaves the slot choice exactly as it was. Sends the
server key only to the validated server address (`connection_for`), without any system proxy.
Two turns sent at the very same moment can both see the slot idle; this narrows the collision to
the few milliseconds between the look and the request, it does not lock anything on the server.
`GET /slots?model=X` on a llama.cpp router asks the instance of X, the model this turn is about to use.

### `model_slots_full`

```python
async def model_slots_full(settings, model: str, *, probe=None) -> bool
```

True when every slot of `model` on STAR Server is generating right now (so a new request would queue).

One `look_for_busy_slots` question (<= `SLOT_PROBE_TIMEOUT_S`). False whenever it cannot tell: not STAR
Server, slot count unknown, probe switched off or failed. Used to keep interactive chat off a main model
whose slots are all held by background answers (docs/agents/chat-speed-20261013.md).

### `llama_request_fields`

```python
def llama_request_fields(settings, *, conversation: str='', tools: bool=False, model: str='', background: bool=False, prime: bool=False) -> dict
```

Extra request-body fields that make a llama.cpp server reuse its prompt cache.

Only for the kinds `local` and `lan`, which are llama.cpp servers the owner
runs. Cloud providers get {}: these are not OpenAI fields and are never
sent to a vendor.

  cache_prompt        keep the tokens of this prompt in the slot and reuse the
                      common start on the next request
  chat_template_kwargs.preserve_thinking
                      render earlier answers exactly as they were generated
                      (Qwen templates otherwise re-render them differently, which
                      makes the server read every previous answer again)
  id_slot             one conversation stays on one slot of each model. Sent only
                      for the conversation's own requests (a turn and its
                      warm-up), and only when that model has reported two or
                      more slots.

Slot rules:

  * `model` is the model this request goes to; slots belong to a model, so
    the same chat has one slot on the quick model and one on the main model.
  * A chat keeps its slot. A chat that is opened while another one is in use
    takes a different slot, so switching back finds the first one cached.
  * `prime=True` is the cache warm-up: it takes the chat's slot (the turn it
    prepares is sent there) without declaring that chat the one in use.
  * `background=True` (summaries, sub-agents, code repairs, the lesson digest,
    a voice call: prompts of their own) carries no `id_slot`. A request with
    `id_slot` waits for that one slot even while another is free, so helpers
    pinned to one slot queued behind each other and behind another client
    (issue 118). The server now places them itself. The price: nothing keeps
    the server from putting such a request into the slot that holds the
    chat's prompt, and the chat's next turn then reads its prompt again or
    gets it back from the server's RAM prompt cache.
  * A request without a conversation name is not pinned either.
  * `tools` does not move a request to another slot. The tool prompt and the
    plain prompt of one chat share its slot; the server's RAM prompt cache
    brings back whichever was replaced (1.3-1.6 s, measured).

Two STAR clients share nothing but the server, so the chats of two clients
can have the same slot number (a hash, with two slots: one pair in two).
Before a chat turn the app asks the server which slots are generating
(`look_for_busy_slots`, issue 118); when the chat's slot is busy and another
is idle, the turn goes to the idle one and the chat stays there. Two turns
sent at the very same moment can still both see the slot idle, and then the
second waits for the first one's request. Setting the
environment variable `STAR_SERVER_SLOT_PINNING=off` (read for every request,
off unless set) removes `id_slot` from every request: the server then places
the chat's turns too, and no client waits while a slot is free. The price:
a conversation finds its cached prompt only through the server's own choice,
and two chats with the same system prompt take turns in one slot.

Pinned requests were verified against llama.cpp build 11541 (router mode) on
the owner's server. Where the server puts a request without `id_slot` was
measured there once with a probe script (research notes, server inference
2.4): the idle slot whose cached prompt shares the longest start with the
request (above 10 %), otherwise the least recently used one; the next turn
of a conversation reused its cached prompt that way. It has not been
measured with STAR's own helpers running or with two clients. That a
request with `id_slot` waits while its slot is busy is how the llama.cpp
server queues work (it defers the task); the tests reproduce it with a fake
server, and it was not timed on the owner's server for this change.

### `model_unavailable`

```python
def model_unavailable(exc: BaseException) -> bool
```

Did a request fail because the server could not serve that model at all?

True for "model not found" (llama.cpp router: HTTP 400), 404, and the 5xx a
router returns when a model fails to load. Nothing was generated in any of
these cases, so the same message can be sent to another model.

### `background_client`

```python
def background_client(client, settings, *, conversation: str='')
```

The client for model calls that are not the conversation itself.

On STAR Server every such call carries `llama_request_fields(...,
background=True)`: the prompt-cache fields without `id_slot`, so the server
chooses the slot and two helpers never wait for the same one. That also
means a helper is no longer kept out of the chat's slot (see
`llama_request_fields`). `conversation` is accepted for the callers and
does not select anything. For a cloud provider and the on-PC brain this is
the plain client.

### `provider_catalog`

```python
def provider_catalog() -> list[dict]
```
