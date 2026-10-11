# Document attachments and data calculations

STAR can retain document evidence for a conversation, retrieve relevant passages on later turns, and calculate aggregates from attached tables. Use **Attach files** to select a source, then ask a question about it. Fast mode keeps its selected model and can use the attached-document tools; this does not enable other tools.

## Supported sources

| Format | Extracted evidence | Limits to interpretation |
| --- | --- | --- |
| TXT and Markdown | Text with line locations | UTF-8 or Unicode with a byte-order mark; binary text is rejected. |
| PDF | Text with page locations | No OCR; scanned pages and complex layout may need another source. Encrypted PDFs are rejected. |
| DOCX | Body paragraphs, tables, headers and footers | Embedded media, comments, revisions and unsupported nested content are not fully represented. |
| PPTX | Slide text, tables and speaker notes | Pictures are not OCR; animations, transitions and presentation layout are not interpreted. |
| CSV and TSV | Tables with physical line locations | A header row and consistent column counts are required. Leading-zero identifiers remain text. |
| XLSX | Sheets and cached cell values with row locations | Formulas are never executed. Missing cached values remain missing and are reported. Macros and external links do not run. |
| JSON | Text and scalar tabular arrays with JSON locations | Duplicate keys and non-finite numeric values are rejected. Nested cells become text with a warning. |

Install the repository requirements for all readers. PDF decoding requires `pypdf>=6.20` for its parsing limits. The local Windows build script explicitly collects parser resources. The packaged `--doctor` also exercises synthetic PDF/Office/text/table evidence and exact calculation in a disposable directory; missing parser resources fail the existing CI smoke check. `--document-doctor` runs that check alone. It uses no application profile, model, engine or network.

## Sources and follow-up questions

Originals are copied into the existing immutable artifact store and checked against their content digest whenever saved evidence is loaded. The extracted evidence and references live in `documents.sqlite3` under STAR's application-data folder, separate from trusted lessons. References are scoped to the selected project and conversation. Attaching an updated file replaces that conversation's reference while preserving its older original.

Retrieval ranks passages across the complete bounded extraction. A question about a term near the end of a document can retrieve that passage, rather than receiving only the beginning. A general overview samples the beginning, middle and end of each source. Every result identifies its source and location, reports omitted chunks, and keeps the full extracted evidence available for another query. Lexical retrieval can miss paraphrases; a displayed excerpt is not proof of complete comprehension.

The model receives two read-only tools when applicable:

- `star_document_search` searches the already attached sources and returns source locations plus a bounded table inventory.
- `star_data_analyze` calculates `count`, `sum`, `mean`, `min` or `max`, optionally with up to four filters and one grouping column. It accepts only a scoped dataset ID and exact column names; it cannot open a path or run code.

Results include the dataset, filters, row counts, missing values, exact or rounded status, parser warnings and up to eight selected-row locations. Additional locations are counted explicitly. Counts are integers; other aggregate values are decimal strings, or null when no numeric evidence exists. CSV and JSON decimal lexemes retain their original precision. Spreadsheet values reflect the workbook's stored values; this is not a recalculation of Excel formulas.

## Tool compaction and request budgets

The original active question, its image parts and the system message remain intact. STAR bounds app-added reference sections and archives omitted evidence or earlier complete turns before model dispatch. The request budget includes both message text and serialized tool schemas. If required content alone cannot fit, STAR stops visibly and suggests attaching long source text as a file or using a larger context window. Character budgets approximate capacity; model tokenizers and image token costs differ.

When tool work needs compaction, STAR summarizes all bounded prior evidence in chronological fragments, then reduces the summaries in layers. It carries explicit metadata identifiers separately and labels the checkpoint as lossy, untrusted reference data. Facts, constraints and identifiers embedded in prose remain dependent on the model's summary. Exact facts should be retrieved again from original sources. Failed, empty, truncated, expansive or non-reducing summaries do not replace the checkpoint.

Compaction is bounded to one million source characters, 96 model calls, eight layers and a 6,000-character final checkpoint. Each summary request is capped at 18,000 text characters and 1,300 output tokens. These are work limits, not unlimited memory or proof of semantic fidelity. Large inputs can require several sequential calls.

Ordinary conversation replay uses bounded segments of complete exchanges. When a segment moves, STAR summarizes the newly omitted original records into a separate, scoped conversation checkpoint. Short chats and unchanged boundaries add no summary calls. The checkpoint carries a deterministic source cursor and digest; it advances only after a successful answer and atomic source validation. Tool-schema pressure can trigger up to four preparation retries before the first answer dispatch. Pressure after model or tool work stops visibly without replaying actions. History over 10,000 records or one million stored-body UTF-8 bytes is refused before loading bodies or contacting a provider. Original dialogue remains intact; the lossy recap does not establish unlimited recall or verified facts. See [Conversation memory](CONVERSATION_MEMORY.md) for scope, failure behavior and validation.

## Resource limits

One source is limited to 32 MiB, one million extracted characters and 100,000 table cells. A conversation can reference at most 32 documents. Office archives are checked before parsing for bounded expansion and member counts; PDFs apply decoding, page-tree and recursion limits. Each calculator operation validates only its selected table, with at most 50,000 rows, 256 columns and 100 groups. A larger extracted table can still be read but requires a smaller source for calculation.

Cancellation is checked between parsing units. A library call already decoding a page or package is not preempted immediately. Attachments and transcripts remain local unless the user selects a provider or tool that sends their contents elsewhere, as in ordinary STAR chat. Document evidence never becomes an automatically accepted lesson merely because a source contains instructions.

## Offline validation

Synthetic fixtures cover each reader, late-document retrieval, restart and scope isolation, original and extraction integrity, exact decimal calculations, invalid inputs, grouped and filtered aggregates, context bounds, preserved questions/images, complete tool exchanges and compaction failures. These checks establish application behavior; they do not establish live-model comprehension or general game-building quality.
