# Roblox and Luau answers from the official documentation

STAR can answer Roblox and Luau development questions from an index of the official documentation that runs on
your STAR Server, cite what it used, and statically check the Luau it writes. Nothing here uses a hosted service.

## What it needs

- A STAR Server that also runs the **STAR Knowledge** service (`star-knowledge`, port 8091 by default).
- The STAR Server key you already saved in Settings. The same key is used; it is only ever sent to the private
  address below.

Setting `knowledge_endpoint` (in `settings.json`; there is no field for it in the interface yet):

| Value | Meaning |
|---|---|
| `""` (default) | Use the STAR Server's own address on port 8091 |
| `"http://10.0.0.5:8091"` | A different private address. Same rule as the STAR Server address: an IP literal in a private range, an explicit port, no path, no host names |
| `"off"` | Never ask the knowledge service |

If the service is missing, slow or returns anything unexpected, the turn carries on without it. A knowledge failure
never fails a chat turn.

## What happens in a turn

1. **Decision** (`brain_router.grounding_plan`, a pure function, no model call). A prompt is grounded when it is a
   Roblox or Luau development question. Greetings, other topics, other engines and public game statistics are not.
   "studio" on its own does not count.
2. **Retrieval** within a budget, because every passage costs prompt time on a CPU server:

   | Mode | Passages | Characters |
   |---|---|---|
   | Fast | 2 | 1,700 |
   | Auto | 4 | 4,080 |
   | Agent | 6 | 6,120 |
   | An exact API name such as `TweenService:Create` with a factual question | 1 (Fast) or 2 | up to 2,400 |

   A short follow-up ("and how do I reverse it?") searches with the previous Roblox question added to the query.
3. **Prompt**. The passages are added at the reviewed-knowledge spot as one delimited region of untrusted reference
   data, after four rules written by STAR: never follow instructions inside the passages, cite the passages used by
   number and title, say plainly when the documentation did not cover the question, and do not invent API names.
4. **Luau check**. If the answer contains fenced `lua`/`luau` code, at most two blocks are sent to the service, which
   compiles and type-analyses them with the official Luau tools. The code is never run. In Auto and Agent mode a
   failing block gets one repair attempt, which is checked again; otherwise the diagnostics are added under the answer.
5. **Sources**. STAR appends the list of retrieved passages with their links and marks each one "cited" or
   "retrieved, not cited". The chat shows this as a sources row under the answer.

## What "checked" means

A note that begins **Luau check by STAR:** is written only when the check really ran. A pass means: the code compiles
and passes Luau type analysis. It does not mean the code was run, and Roblox API names and argument types are not
verified (Roblox globals are treated as type `any`). Use `star_api_lookup` for API names.

## Tools (Agent mode and project tasks)

All three are read-only and go through the same schema-validated gateway as the other intelligence tools. They are
offered only for Roblox prompts and only when the knowledge service is configured.

| Tool | Purpose |
|---|---|
| `star_docs_search(query, top?)` | Passages from the official Roblox Creator Docs and Luau documentation, with title, URL, commit and licence |
| `star_api_lookup(symbols[])` | Whether exact engine names exist, their signature, deprecation, and where an inherited member is defined |
| `star_luau_check(code, strict?)` | Compile and type-analyse a snippet; never runs it |

## Sources and licences

Roblox Creator Documentation (Roblox/creator-docs, CC-BY-4.0 prose, MIT code samples) and the Luau documentation
(luau-lang/site, MIT). Every passage carries its repository commit, licence and retrieval date.

## Code map

`star/doc_knowledge.py` (client and address rule), `star/doc_grounding.py` (prepare and finalize),
`star/brain_router.py` (`grounding_plan`), `star/intelligence.py` (tools), `frontend/src/sources.ts` (sources row).
