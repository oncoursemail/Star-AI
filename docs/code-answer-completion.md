# Opt-in recovery of truncated code answers

Status: **OFF by default**. This extends the bounded-continuation prototype in
[PR #147](https://github.com/oncoursemail/Star-AI/pull/147) on current
```star/next```, without merging its conflicting evaluation changes.
[star/agent.py](../star/agent.py) collects streaming and nonstreaming replies;
[star/code_answer_completion.py](../star/code_answer_completion.py) owns the
fence scanner, continuation splice, two-attempt bound and failure warning.

## Enable / disable

Set **```STAR_COMPLETE_CODE_ANSWERS=on```** in STAR's process environment before
launching. Any other value or an unset variable leaves behavior unchanged. Tests
may also pass ```complete_code_answers=True``` to ```star.agent.execute```.
No server change, remote connection, credentials or installation is required.

When switched on, STAR buffers streamed **final-answer text** until generation
ends; tool-requested text remains streamed. If ```finish_reason == "length"```
or a fenced code block is not closed, STAR makes up to **two** tool-free
```/v1/chat/completions``` follow-ups, each with a fresh
```max_tokens: 900``` and original conversation context. If both fail, a final
unclosed fence is closed for rendering **with an explicit warning that the
code is incomplete and must not be run**. Context exhaustion or provider
failure also retains the partial output and adds that warning. Completed replies
(including whitespace) are returned byte-for-byte unchanged in one model call.

This handles Markdown fence presentation, **not Luau syntax or semantics**.
Successful Luau compilation or gameplay behavior still requires Luau analysis
and real Studio tests.

## Options compared

| Option | llama.cpp interface and failure mode | Evidence / speed cost |
| --- | --- | --- |
| GBNF grammars | The per-request ```grammar``` string restricts tokens to a grammar, but ```max_tokens``` still ends generation mid-production. A correct Luau grammar plus mixed prose/tool calls would be costly to maintain. | Grammar-specific overhead varies greatly. [llama.cpp #4218](https://github.com/ggml-org/llama.cpp/issues/4218) documents slow sampling. [#20867](https://github.com/ggml-org/llama.cpp/issues/20867) reports **34.12 ms/token with grammar vs 34.67 ms/token without** in *one* Qwen3.5-27B tools scenario, not a general guarantee. |
| JSON-schema output | ```response_format``` on chat completions allows a constrained JSON envelope, but a long code string can still be truncated. Serializing/rendering code and text changes STAR's response protocol; llama.cpp only supports part of JSON Schema. | It uses grammar-based sampling; no STAR-specific speed measurement exists. |
| Stop sequences / larger budget | ```stop``` may end generation *early*. ```max_tokens``` and native completion ```n_predict``` raise the limit, without guaranteeing a completed program. | Extra tokens increase latency; exact inference rate depends on installed model/hardware. |
| **Bounded continuation (selected)** | Read final ```finish_reason```, including for streams; detect open fences; remove the split code line and request the missing lines only. Close and label any failed continuation. | **0 additional generated tokens and calls on complete answers**. At most **2 extra requests / 1,800 generated tokens** for a cut-off answer. No speed benchmark of the owner’s server was performed. Buffering changes visible time-to-first-text while enabled. |

Sources: official [llama.cpp GBNF guide](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md),
[server README/API](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md),
[server schema implementation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/server-schema.cpp).
The server code is MIT licensed and maintained by ggml-org. Each option uses
the existing llama.cpp server without a paid dependency. GBNF and JSON-schema
add constrained-sampling maintenance/CPU cost, while continuation pays only on
truncation with additional inference tokens.

## Exact server request fields and flags

No new ```llama-server``` flag is needed for the selected mechanism. Keep
the existing server launch flags and OpenAI-compatible
```/v1/chat/completions``` endpoint. The ordinary request already sends
```max_tokens``` and, when used, ```stream: true```; completion responses
carry ```choices[0].finish_reason```, normally ```length``` if capped.
Recovery requests send ```max_tokens: 900``` and omit ```tools```,
```tool_choice```, and ```stream```. Existing prompt-cache ```extra_body```
settings are preserved. The server does not receive a grammar or schema.

For manual, independent experiments *not enabled by this PR*:
- GBNF: ```extra_body={"grammar": "<GBNF rules>"}``` for llama-server.
- JSON schema: ```response_format={"type":"json_schema","json_schema":{"schema":{...}}}```
  on llama-server builds supporting that format.

## Proof and limits

Fake-provider tests drive the *real* ```star.agent.execute``` path for truncation
inside a function, inside a string, a byte-for-byte complete answer, two cuts
in succession, exhausted retries, a provider failure, streaming suppression
until a final repair, and omission of tools on follow-ups. A separate test
exercises the environment flag through ```desktop_core.run_task``` with its
fake provider. CI results are the actual test record; no local run or call to
the owner's brain/server was made.

This does **not** prove the model's continuation is semantically sound. It
cannot force a model to finish under the token cap, and no latency/accuracy
measurements against a real STAR server were performed. A failure is made
visibly incomplete instead of being presented as a runnable script.
