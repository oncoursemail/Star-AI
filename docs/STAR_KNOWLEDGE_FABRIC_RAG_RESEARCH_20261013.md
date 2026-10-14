# STAR Knowledge Fabric — Deep RAG, Private Memory, Agent Workflows and Verified Self-Learning

Research checkpoint: October 13, 2026. Branch: star/chatgpt-rag-quality-gate-20261013. Status: engineering research + independently testable offline evaluation tool. This document does NOT claim AnythingLLM, Khoj, Chroma, Postgres, n8n, Langflow, Docling, Letta, Mem0 or any other third-party software has been installed or connected to the live STAR application.

## Decision

**Do not replace STAR's working brain with six independent assistants.** STAR already has several valuable subsystems: verified-project SQLite memory, digest-bound conversation history, STAR Knowledge BM25+embeddings+RRF+optional reranking, source-hash-indexed embeddings, read-only external MCP and approved Tool Workshop recipes, and a tested Night School lesson loop. Treat third-party systems as optional import and inference *backends*, not parallel sources of truth.

The measurable goal: **more independently verified, useful Roblox/game-development work per interactive hour**, with correct long-distance recall, source citations, explicit user correction, exact project separation, low first-token latency, and zero surprise paid-model calls. RAG improves retrieval/context; it is NOT continuous weight training.

## Audit of current STAR (star/next as of this research)

| Component | Evidence in the existing code | Do not duplicate |
| --- | --- | --- |
| Project memory | star/knowledge.py, notes SQLite, optional FTS5/BM25, reviewer flag and evidence-bearing source/revision | Keep owner-reviewed notes as source of truth; do not silently write a new Chroma-derived fact over them |
| Conversation history | star/conversation_memory.py, docs/CONVERSATION_MEMORY.md: full source messages with digest-scoped, lossy, atomic checkpoints | Never mutate chat originals or claim a summary is verified |
| Technical docs RAG | server/knowledge/starkb/search.py: BM25, vector, hybrid/RRF, optional rerank and query facet experiments | Adding a new vector DB is NOT automatically better retrieval |
| Content cache | server/knowledge/starkb/store.py: text-hash indexed embeddings, transactional index rebuild | Preserve content-hash invalidation; do not rescan all Roblox docs after every chat |
| Evaluation | server/knowledge/starkb/evaluate.py: Recall@k, MRR@10 and latency on known official-source files | Add privacy/freshness/abstention/answer grounding; do not train on heldouts |
| Generated questions | server/knowledge/starkb/study.py: doc2query trial **hurt** one held-out set, currently off | More synthetic questions are not proof of learning |
| Skills and tools | star/tool_workshop.py and server/night_school; docs/SELF_LEARNING_LOOP.md | Candidate lessons need tests, approval/rollback; no auto-granted shell/API permissions |
| GPU/CPU load | Draft PR #266 resource admission, #274 experimental KV banks; local first-class provider routing | Benchmark rather than claiming all cores/RAM should be filled by more software |
| User image and Studio QA | Drafts #268/#277 (native Studio Lab), #287 (Discord image reference/feedback), #297 (Blender animation draft) | Keep binary/visual evidence and owner consent separate from generic PDF RAG |

## The user's six proposed products: deep comparison and decisions

| Tool | 2026 verified value | STAR decision | Cost/license/operating caveats |
| --- | --- | --- | --- |
| AnythingLLM | MIT-licensed self-hosted document/agent app; private workspaces, ingestion, REST developer API at /api/docs | **Optional benchmark and document-workspace pilot**; test actual cited retrieval against STAR's current corpus and role/project scoping | Its workspaces are a SECOND conversational store; don't reauthor authoritative STAR messages or pass projects/cloud keys automatically. Its official sample Docker run includes a SYS_ADMIN capability; do not copy that into production without reviewing isolation |
| Khoj | AGPL-3.0 second brain; searches local PDFs, Markdown, org-mode, Word and Notion; agents, web/knowledge search, cross-encoder reranking and scheduled workflows | **Compare second-brain retrieval and personal multi-session recall** using rights-cleared fixture notes. Imported facts remain source-linked candidates | AGPL redistribution/network service considerations; its indexing/config can introduce another private-data surface. Respect non-hosted self-service setup and key handling |
| n8n Community Edition | Visual scheduling, webhooks, HTTP and AI nodes, workflow editor, queue mode and owner-run automations | **Optional external owner-operated automation** for verified Night School DM, research digest, backup and GitHub notifications; do not embed it as STAR's permission root | n8n's Sustainable Use License is **fair-code, not OSI open source**; user-facing/customer workflow authoring may require a commercial license. Public webhooks, Execute Command and community nodes expand code/secret execution risk |
| Langflow | MIT-licensed, visual AI/agent/RAG flows; external flow REST API and MCP tool exposure | **Preferred optional visual prototyping lab** for retrieval flows. Export only reviewed, read-only, schema-scoped tool definitions | Custom code/flows can execute Python; self-host auth, tokens, network bind, revisions and dependencies need pinning. MCP flows must not become arbitrary privileged tool calls |
| Chroma | Apache-2.0 vector DB with PersistentClient, dense/sparse/hybrid and metadata filters | **Optional local comparison backend** for private project notes; use separate project collections and host-side scope verification | DB stores vector + raw text/metadata: private data persists; project filters are not an authorization substitute; cloud costs apply if hosted |
| PostgreSQL + pgvector | SQL ACID, row-level security, source provenance joins, exact vector queries, optional HNSW/IVFFlat approximate indexing, partitions | **Long-term Brain 1 service option** after measured scale/concurrency demands it | Postgres server/migrations/maintenance, index RAM, backup+deletion behavior. HNSW requires extra memory and filtered ANN recall can fall; iterative scans help but need evaluation. Latest pgvector fixes matter; pin patched versions |

Official source links:
- https://github.com/Mintplex-Labs/anything-llm
- https://docs.useanything.com/features/api
- https://github.com/Mintplex-Labs/anything-llm/blob/master/TERMS_SELF_HOSTED.md
- https://github.com/khoj-ai/khoj
- https://docs.khoj.dev/features/search/
- https://support.n8n.io/article/can-i-use-your-license-for-my-use-case
- https://docs.n8n.io/deploy/host-n8n/community-edition-features/
- https://docs.langflow.org/mcp-server
- https://docs.langflow.org/concepts-api/
- https://docs.trychroma.com/
- https://github.com/pgvector/pgvector
- https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md

## Further research: tools STAR could benefit from even more

### Document understanding and ingestion

**Docling (strong priority)** — MIT-licensed structured PDF/document conversion, layout and table recognition, local execution; hybrid and hierarchical chunking. Useful for Roblox API references, large UI design specs, setup tutorials, schematics and multi-page bug reports. Preserve page/section/table boundary and document SHA. A naive PDF chunker often loses crucial headings, signatures and table context.

**LlamaIndex ingestion** — hash-based transformations, docstore upsert/delete strategies, cache and pluggable readers. Study incremental invalidation instead of moving STAR onto a new framework. Without a trusted delete path, stale documents can survive forever in a vector index.

**Haystack** — retrieval pipelines with dedicated BM25+embedding hybrid retrievers, reranking and testable modules. Caution: its retriever dynamic filter mode can REPLACE configured filters: STAR should always supply project/consent filters from the trusted host **after** or alongside query construction, never let a model remove them.

**OpenRAG (Langflow + Docling + OpenSearch)** — new package including document parsing, agentic search and visual workflows. A useful full-system *benchmark competitor*, but operationally heavier than STAR's existing SQLite knowledge engine. Do not install OpenSearch, Langflow and its ingestion servers on the 15 GiB Studio machine without real memory measurements.

Sources:
- https://github.com/docling-project/docling
- https://github.com/docling-project/docling/blob/main/docs/reference/cli.md
- https://arxiv.org/abs/2408.09869
- https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/ingestion/pipeline.py
- https://docs.haystack.deepset.ai/docs/opensearchhybridretriever
- https://docs.haystack.deepset.ai/docs/retriever
- https://github.com/langflow-ai/openrag

2026 small-domain PDF-to-RAG research (https://arxiv.org/abs/2604.04948) reports that hierarchy and metadata quality often mattered more than parser choice: its best automatic configuration used Docling+hierarchical splitting+image descriptions on 36 Portuguese administrative documents. Results were based on a limited domain and an LLM judge; do not extrapolate the percentages to STAR's Roblox corpus without testing. It also reports an exploratory GraphRAG pipeline underperformed basic RAG in that study.

### Memory agents, temporal graphs and embeddings

**Letta (MemGPT lineage)** — memory-aware agent harness and state, now active in letta-code, helpful as a *design reference* for continuity and long-running tasks. A Letta process is not a safe replacement for STAR's official private project memory or permissions.

**Mem0** — memory extraction and retrieval, source-time aware entity linking and multiple retrieval signals. Its April 2026 published large benchmark numbers describe a managed stack with proprietary components, NOT guaranteed results from the OSS SDK. Compare recall, abstention, and token budgets on STAR tasks.

**Graphiti** — Apache-2.0 temporal knowledge graphs with episode/source provenance and time-validity windows. Use selectively when a task asks relationships across changing versions (which Roblox project the user approved, what superseded a rig type, which lesson is current). Graph edges inferred by an LLM are not automatically source truth. An external graph DB adds operational cost.

**Cognee** — document/conversation-to-graph memory, MCP tools for remember/recall/forget, self-hosted experimentation. Some workflows involve embedding and LLM provider credentials, so "free local" depends on the models configured. Treat tool writes as reviewable, not automatic memory promotion.

**LightRAG** — graph+vector approach with local/global/hybrid retrieval modes and incremental updates. Its published benchmark results should be independently reproduced on a source-scoped STAR benchmark. Generic graph expansion can contaminate project scope.

**Embedding/reranker candidates:** BGE-M3 dense+sparse multilingual retrieval; BGE reranker v2 M3 cross encoder (Apache 2.0) for *top few* candidates. Test model VRAM/RAM footprint against the existing STAR Knowledge embedder instead of downloading and running all at once.

Sources:
- https://github.com/letta-ai/letta
- https://github.com/mem0ai/mem0
- https://github.com/getzep/graphiti
- https://github.com/topoteretes/cognee
- https://github.com/HKUDS/LightRAG
- https://huggingface.co/BAAI/bge-m3
- https://huggingface.co/BAAI/bge-reranker-v2-m3

### Minimal local vector search

**SQLite FTS5** — already built into STAR. Keyword/BM25 is very efficient on Luau symbols, API names, GUIDs and explicit user correction quotes; retain it as a first-class query route. It needs no additional service or AI model.

**sqlite-vec** — Apache/MIT-licensed SQLite vector extension, lightweight for desktop and embedded deployment, but upstream is pre-v1 and warns of breaking changes. If selected, pin and verify the native binary in the Windows packaging pipeline and never load arbitrary SQLite extensions from user-provided paths.

**Chroma** — quick local experimentation, no Postgres provisioning; baseline should still be FTS5 for exact tokens and core STAR Knowledge for official docs.

**Qdrant** — good future dense+sparse hybrid query and payload/tenant filters for high-volume indexing; introduces one more server and remote API to secure.

**Postgres/pgvector** — use only once multiple independent projects/users and sustained corpus growth clearly justify migration; prefer exact search for tiny corpora and test ANN recall under project filters. pgvector 0.8.7 (2026-10-01) includes important safety fixes; pin a currently patched version after advisory review.

Sources:
- https://www.sqlite.org/fts5.html
- https://github.com/asg017/sqlite-vec
- https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md
- https://docs.haystack.deepset.ai/docs/3.2/qdranthybridretriever

## STAR Knowledge Fabric: proposed architecture

~~~text
User request (text / screenshot / project question)
  -> permission + project + chat + privacy intent gate
  -> query classification (exact Luau symbol, docs, code, visual, personal memory)
  -> retrieve in parallel ONLY from already authorized sources
       exact symbol & SQLite FTS5        (fast, strong for API identifiers)
       local semantic retrieval          (when paraphrases require meaning)
       optional graph/version retrieval  (time-sensitive multi-hop cases)
       official source watcher          (fresh Roblox/Blender/Unity/Godot docs)
  -> reciprocal-rank fusion / bounded reranker, if its measured benefit justifies latency
  -> SOURCE VALIDATION BEFORE MODEL:
       exact authorized project, reviewed/accepted memory state,
       active source hash, permissions, timestamps, revoked/deleted sources,
       source license, source URL/path/line
  -> compose small evidence snippets with citations + unknown/contradiction flags
  -> model answer: never invent a retrieved source; refuse unsupported factual claims
  -> optional code/test/Studio verifier
  -> owner feedback + verified test receipt
  -> isolated lesson / retrieval-index change CANDIDATE
  -> protected independent evaluations, canary, owner approval and rollback
~~~

### Data contract: SourceVault

Every indexed source must carry: (project_id, source_id, kind, source URI/path, rights/consent, SHA-256, revision, timestamp, extraction method/version, table/page/line/span, active/deleted status, reviewed status and user correction links). Raw author data stays local, and secrets must not enter a model provider or unencrypted connector without owner authorization.

An indexed image is not equivalent to a model's scene understanding; store image origin+hash, permitted structured observations, camera/time where known and owner corrections. Native Studio/Blender evidence stays bound to actual run IDs; an AI-written summary is not a game test.

Deletion and revocation must propagate to FTS, embeddings, graph projections, answer/KV caches and optional external workflow state; test deletion under crash/restart and stale-index races. Caches keyed only by question text are dangerously stale. Versioned content fingerprint, tool revision, model/template and permission state must be part of a cache key.

### Smart retrieval routing

- **Exact symbol questions**: static API dump/verified source line + FTS5; vector-only paraphrase models sometimes hallucinate or omit exact symbols such as TweenService:Create or Enum names.
- **Design/aesthetics**: approved owner preference + specific reference hashes + earlier rejected render and actual native metadata, not random internet image suggestions.
- **General knowledge / paper research**: official source watcher, metadata, DOI, citations with retrieval date; do not assume every public article licenses weights training.
- **Multiple docs**: multi-query decomposition only after cheap exact/BM25 route; rerank at most the most relevant ~10-20, not full archive every turn.
- **Memory and corrections**: source-digest checked original history and reviewed supersession; episodic failed attempts do not become success facts. A private chat turn cannot promote memory solely by saying "I learned."
- **Abstention**: when independently expected evidence is absent, answer "not enough verified information" rather than hallucinating a doc; negative questions are explicit benchmark cases.

## Actual improvement added in this PR: RAG Quality Gate

New file star/rag_quality.py is a **small, stdlib-only, read-only evaluation** for source-scoped backend outputs. It measures two retrievers against the SAME frozen source catalog and independent per-task expected source IDs.

Inputs: v1 JSON with sources (id, project, SHA-256, reviewed, active) and cases (id, project, gold expected IDs or an empty no-answer set, baseline hits+latency, candidate hits+latency). It accepts no document text, URLs, model code, secrets or custom endpoint and does no actual retrieval. Counts candidate citations to unauthorized projects, unknown IDs, stale revisions, unreviewed content and deleted/inactive sources; ANY such candidate citation causes rejection even if Recall@5 is perfect.

Metrics: Recall@1/@5/@10, MRR@10, no-answer (abstention) accuracy, mean/p95 latency and violation counts. Review gate rejects scope/trust leaks or lower quality/major p95 regression, remains inconclusive on small sample (<20 paired cases, <10 answerable or <3 negative cases), and can only mark an improvement a **candidate_for_owner_review**. There is NO automatic backend switch, skill promotion, learning, model training or index migration. An operator independently supplies trusted freeze/test artifacts; an AI-generated manifest with fabricated gold labels has no authority.

Run on the explicit, operator-reviewed fixture manifest when one is available:

~~~text
python -m star.rag_quality --manifest /absolute/operator-reviewed/retrieval-fixtures.json
~~~

The CLI reads only that file (1 MiB bound), outputs aggregate numbers without document bodies/source IDs, and never connects to the internet. Synthetic offline tests cover policy, privacy, missing/stale sources, negative questions, exact review flags, duplicates, latency, and manipulated manifests. Passing synthetic tests verifies the GATE, **not a real Chroma/Khoj/pgvector search**. Existing server/knowledge/starkb/evaluate.py continues to handle true retrieval tests on the actual indexed Roblox corpus. Connect the two in a separate reviewed PR after pinning actual source revision IDs and test split.

## Self-improvement that learns faster without hallucinating

### Tier 1: instant safe progress

- Prioritize exact/FTS5 and cached results; don't run a vector embedding if identifier lookup already answers the question.
- Incremental source hash and page/heading aware chunks; process changed documents only; avoid repeating model embeddings on identical text.
- Cached authorized prefixes and small evidence summaries; do not fill the long context with irrelevant docs.
- Parallelize cheap *independent* BM25+vector work only when background resource planning says it won't delay chat; keep one quick-model lane open.

### Tier 2: reviewed knowledge and skill evolution

- Record every outcome as a typed event with project, actual source/run hash, checker identity, owner correction and evidence class (static, simulated, native Studio, visual approval).
- Extract only **candidate** lessons from corrected Roblox scripts/animation import failures. Never train from arbitrary internet text, Discord public conversation, unlicensed PDFs or model-said successes.
- Use actual holdout coding/gameplay cases: no-training contamination, grouped by project/bug family. A failure classification yields a new practice task with an external, frozen evaluator.
- Require correct/verified tasks per hour to improve; stop if p95 chat latency or source-leak count rises. Use Night School when spare resources exist and defer to user's interactive chat.

### Tier 3: experiments beyond current RAG

**Hypothesis: STAR Evidence Ecology**, an original integration idea, *not* a proven scientific discovery. For every source of knowledge STAR records both its **evidence dependencies** and the verified tasks it influenced. It can ask which previously accepted solution is now at risk when a Roblox API doc changes, a user reverses a style preference, an animation rig changes or a deleted PDF citation disappears.

Instead of simply repeating a vector search, run a controlled **counterfactual retrieval replay**: same task and frozen outcome, compare (A) direct lexical result, (B) current hybrid result, (C) source-timestamp-aware and correction-aware result under equal CPU/token budgets; measure whether each avoids wrong, stale or unauthorized claims. Invalidated facts become review candidates, never silent new truths.

An independent test suite then investigates whether a changed retrieval policy would have prevented the actual failure. This could yield a self-improving *retrieval strategy* without changing the underlying LLM weights, and can be tested in a few synthetic examples before spending GPU time. Controlling for source licensing, sealed questions, project boundaries and reviewer bias is essential.

Related memory and 2026 research:
- Mem0 April 2026 retrieval paper/benchmark: https://github.com/mem0ai/mem0 (managed platform scores not directly comparable to OSS STAR)
- LongMemEval includes multi-session reasoning, updates, temporal recall and abstention; May 2026 added V2 agentic memory: https://github.com/xiaowu0162/LongMemEval
- FinCacheServe (July 2026 preprint): dependency-consistent answer reuse after document changes; promising concept requiring independent validation on STAR: https://arxiv.org/abs/2607.26076
- GePA reflective prompt evolution and strong heldout evaluation: https://arxiv.org/abs/2507.19457
- LlamaIndex hash-and-transformation cache: https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/ingestion/pipeline.py

## Hardware deployment guidance (only after measurement)

- **Brain 1 ~125 GiB RAM, CPU models**: owner-authorized document/source index, SQLite FTS5 and hybrid retrieval, optional small embedding/rerank resident service; larger full-text/pgvector only if measured worth the complexity. Tune CPU memory bandwidth and NUMA; cache useful embeddings but don't blindly allocate 80 GiB.
- **Brain 2 ~15 GiB RAM**: prioritize real Studio test jobs, viewport/screenshots and CPU memory headroom; don't run n8n+Langflow+OpenSearch+Khoj+multiple model servers on top of Studio.
- **Windows PC ~8 GiB VRAM**: user interactive visual and Blender tasks first. Avoid concurrent massive Docling OCR/VLM, text generation, ComfyUI and QLoRA. Offer a local-only scheduled ingestion queue with queue caps.
- User-selected Chroma PersistentClient or PostgreSQL memory sources remain OFF unless explicit source and privacy review; never auto-download Docker images or host arbitrary API listeners just because a model asked.

## Workflow pilot suggestions

- **AnythingLLM / Khoj**: ingest SAME rights-cleared 20–100 documents as STAR Knowledge. Test exact Roblox API questions, long user preference corrections, inaccessible-source trials, document deletions, and source citation quality. Do not copy real private chat transcripts into hosted services.
- **Langflow**: one private, read-only flow that receives an approved query and returns bounded document IDs and citations, no custom Python or shell; compare latency/recall using STAR's quality gate.
- **n8n**: owner-run opt-in automation that consumes a signed/verified Night School event, sends one owner-only Discord digest, and stores a dedupe receipt. Never give n8n the ability to approve STAR tool permissions, edit CI/tests or send private files to arbitrary URLs.
- **Chroma**: compare local embedded collection vs SQLite FTS5/STAR KB under identical source revisions. Check source deletion propagation, metadata filters and CPU/RAM latency.
- **Postgres+pgvector**: provision on isolated Brain 1 only after Chroma vs STAR baseline evidence justifies it, with per-project RLS or partitioning, backup/restore, migration, EXPLAIN profiling and exact-vs-HNSW recall tests.

## Go/no-go requirements

1. No unauthorized source or wrong-project hit in top 20 of any candidate backend, including during stale, deleted, nonreviewed or concurrent ingestion.
2. Held-out improvement measured on at least 20 paired examples (recommended far more); correctness and abstention never regress. Faster retrieval alone does NOT excuse wrong factual evidence.
3. Lower p95 time to first *correct* response and no regression in interactive chat p95 and Studio FPS at same hardware budget.
4. No unreviewed model-created memory/tool or weight update becomes active. A candidate needs independent evidence, protected evaluator and owner review; rollback on source/quality regression.
5. Source version, format conversion loss, citations and query-to-source dependency are visible; negatives and missing data are handled with an honest abstention.
6. No API keys/private project data in logs or GitHub fixtures. n8n/community node, Langflow custom Python, external MCP and AnythingLLM developer keys always require secure operator configuration. Comply with Khoj AGPL and n8n SUL before shipping a distributable app with either component.
7. Test deployment and data deletion end-to-end with native Windows installer, private Brain 1 index, Brain 2 Studio availability, and Discord owner-only reports. Nothing in this research branch claims those integration tests have run.

**Success is not the number of AI tools installed. It is how reliably STAR can recall, research, act, test, explain and improve a real owner's project under explicit resource, privacy and quality constraints.**
