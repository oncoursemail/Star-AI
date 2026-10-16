# Night-school importer size limit

Task #164; branch `star/chatgpt-night-school-import-limit-20261016`.
Base: `origin/star/next` at `9e8c80e3`.

The worked-example importer (not the short-lesson importer) limited responses to
4,000 characters and serialized JSONL rows to 15,000 characters. The night-school
outbox calls the same row validator and excludes answers above that response cap.

Raised responses to 64,000 characters and JSONL rows to 1 MiB of characters,
enough for worst-case escaped Unicode plus metadata. The existing 5 MiB file cap,
500-row corpus limit, provenance checks, atomic validation, and 2,400-character
retrieval budget remain unchanged. Large stored answers still do not enter a
turn if they cannot fit intact. This does not verify the reported game answer;
tests use synthetic offline data and preserve its declared check evidence.

Validation so far: 301 targeted tests passed, including importer, night-school,
weekly bundle, and every failure/error from the initial full run. That first full
run had 9,323 passed, 34 failed, 15 errors, and 304 skipped: one obsolete weekly
bundle cap expectation was corrected; the others passed after moving pytest's
temp directory outside the repository to a shorter, isolated OS-temp path.
Fresh full suite: **9,372 passed, 304 skipped, 4 warnings, zero failures/errors**
in 400.19 seconds. Command: the shared audit Python with `-m pytest -q -p
no:cacheprovider --basetemp=<new isolated OS-temp root>/pt`; APPDATA, TEMP and TMP
pointed into that new temp root, and PYTHONDONTWRITEBYTECODE was set to 1.
Local output: `.test-full2.log`; targeted output: `.test-targeted-final.log`
(not committed). Ruff on all four changed Python files and `git diff --check`
pass. Frontend checks have not run: this new worktree has no node_modules, no
dependencies were installed, and no frontend files changed.

GitHub PR lookup failed with HTTP 401; commit locally and hand off to Claude for
review, required frontend checks, push and draft PR to `star/next`.
No graph exists in this worktree; traced the importer and exporter with targeted
source reads. No server, game project, or owner application data accessed.
