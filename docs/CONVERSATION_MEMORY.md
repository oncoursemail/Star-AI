# Conversation memory

STAR keeps the complete original dialogue in `conversations.sqlite3` and replays a bounded, stable segment of complete exchanges. When earlier exchanges leave that segment, an actual answer turn summarizes the newly omitted records using the layered compactor. A separate conversation checkpoint retains their constraints and context as **lossy, untrusted reference data**. Model summaries never become accepted lessons, settings or permissions.

## Scope and source coverage

Reads use the exact project and chat together. A missing chat ID means that project's `legacy` conversation, matching legacy message writes; it never reads all chats of a project. Every source record retains its ID, complete body, role, timestamp, status and reply association. Failed or cancelled turns keep the owner's question and the terminal outcome in the stored dialogue, but they are not replayed to the model and do not enter a recap: only a question that has a stored answer is model history (a question whose Retry succeeded counts, because its answer is stored after the failure record), and no placeholder answer is invented for the others. Event rows (terminal outcomes and other notes) are never model text, whatever they say. The active unanswered question stays in the active request and does not enter its own recap. A merely similar new question does not suppress an older completed exchange. A saved cursor may end after such a dropped turn; it may not end inside one.

Replay boundaries move across whole exchanges, using stable half-budget segments. An oversized prior exchange moves into the summarized prefix as a whole rather than losing its suffix. Summarization includes every newly omitted record, in chronological fragments, plus the previous lossy checkpoint. Explicit raw record IDs travel through those fragments. Cursor and source digest establish which original records were supplied; they do not establish semantic accuracy of the model's recap. Exact facts and later corrections should be checked against original chat records.

The scoped `conversation_checkpoints` table stores the last covered record ID, a SHA-256 digest of the complete canonical source prefix, checkpoint version, summary, summary digest and update time. Tool-work checkpoints remain separate. Existing messages are never rewritten or deleted by retention.

## Preparation and atomic writes

Short conversations and unchanged omission boundaries make no recap or model preflight requests. They reuse the checkpoint and preserve the stable system prefix. Warm-up reads and validates the same scoped checkpoint and composes the same reference text as an answer; it never creates, summarizes or advances conversation checkpoint state.

The agent loop checks the actual message and serialized tool-schema character budget. If whole replay exchanges must leave before the first answer dispatch, a typed preparation exception returns the exact dropped messages and dispatch/action flags. Desktop preparation can move those sources into the prefix and retry up to four times. Each retry carries the uncommitted candidate forward, so it summarizes only additional omitted records. The active request, images and schemas remain intact. If required context alone cannot fit, STAR refuses visibly.

Once model dispatch or a tool action has occurred, additional history pressure stops the task instead of restarting and repeating work. Actions already completed are not rolled back. A failed or cancelled turn, a refused request, or a failed summary leaves the previous conversation checkpoint and cursor intact.

A candidate checkpoint is written only after the answer and required transcript, answer-file and run-log persistence succeed. Inside one SQLite transaction, STAR compares the previous checkpoint, rereads and hashes the covered original prefix, checks cancellation, then writes summary and cursor together. Changed or missing originals, an incompatible version, a corrupt summary, or a concurrent checkpoint update causes visible refusal. STAR does not silently substitute an incomplete source. A saved cursor also prevents a later raw replay window from moving backward into already summarized exchanges.

## Bounds and limits

Raw history is limited to 10,000 records and 1,000,000 UTF-8 bytes across stored message bodies in one scoped conversation. SQLite checks count and byte size before transferring bodies to Python; bounded iteration repeats the checks in the same read snapshot. NUL characters and multibyte text count toward the byte limit. Over-limit history is refused without clipping, changing a checkpoint or sending a provider request. This limit includes retained originals, not only the currently replayed segment.

The layered compactor separately caps the serialized, redacted source at one million characters, 96 calls and eight layers. Summary requests contain at most 18,000 text characters and request at most 1,300 output tokens. The conversation checkpoint's final character budget is one quarter of the answer context, bounded between 700 and 6,000 characters. Empty, truncated, expansive, non-reducing or over-budget outputs fail without replacing state. Source serialization and metadata can exceed the compactor limit even when raw bodies fit their byte limit.

Character budgets approximate token capacity. A bounded lossy summary can omit meaning despite complete input coverage. This feature preserves a recoverable source and scoped reference; it does not train model weights, guarantee unlimited memory or demonstrate live-model comprehension.

## Offline validation

`tests/test_conversation_memory.py` covers full long-message tails, record provenance, restart reuse, newly omitted prefixes, legacy/project/chat isolation, historic failures, integrity checks, cancellation, bounded source work and atomic cursor writes. `tests/test_conversation_retention_chat.py` runs the actual desktop and agent paths with offline clients, checks warm-up prefix consistency and no checkpoint writes, forces huge-schema preparation, verifies unique source coverage across retries, and checks that pressure after one tool action cannot repeat it. No live provider, server or owner profile is needed.
