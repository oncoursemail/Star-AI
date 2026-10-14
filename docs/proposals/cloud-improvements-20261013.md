# Cloud improvement proposals (2026-10-13)

Source review of `star/next` at `64c1982` by a Claude Code session. Three read-only review passes
(reliability and data writes, security of fetchers and paths, chat streaming / performance / Luau
tooling) were followed by reading every cited line before it was listed here. Items marked
**PR** are implemented with tests; the rest are proposals with the file and line to start from.

Open PRs checked for overlap first: #249 (first-token audit), #273 (worked examples), #280/#279
(project preflight), #286/#288 (test determinism), #291/#300/#302 (Luau checker work), #294 (voice),
#299 (validation messages), #301/#303 (accessibility). Parallel cloud branches in progress at the
time: `star/cloud-security-web-fetch-*`, `star/cloud-security-workspace-paths-*`,
`star/cloud-perf-python-*`, `star/cloud-tests-base-*`; items they cover are marked as such.

Value: H = a user hits it in normal use or loses data; M = visible but needs a specific situation;
L = hygiene. Effort: S = under a day with tests, M = a few days, L = a week or more.

## Ranked list

| # | Area | Improvement | Value | Effort | Status |
|---|------|-------------|-------|--------|--------|
| 1 | Reliability | Crash-safe `settings.json`: atomic save, recover from a damaged file | H | S | **PR #308** |
| 2 | Chat UX | Composer shows the prompt limit and blocks prompts the host refuses | H | S | **PR #320** |
| 3 | Reliability | Stopping STAR Brain froze the window (lock held while waiting) | H | S | **PR #312** |
| 4 | Reliability | Corrections store: WAL + busy timeout (desktop and Discord bot) | M | S | **PR #309** |
| 5 | Roblox tooling | API checker: no "did you mean" for unrelated names | M | S | **PR #311** |
| 6 | Reliability / speed | A "prompt too large" 400 was sent three times | M | S | **PR #324** |
| 7 | Performance | Streaming answer re-renders and re-parses all Markdown per delta | H | M | proposal |
| 8 | Performance | Chat switch / new chat / delete return the whole app state | H | M | proposal |
| 9 | Security | `star_web_fetch`: hostile charset, malformed redirect, gateway exemption on redirects | M | S | in `star/cloud-security-web-fetch-*` (see notes) |
| 10 | Reliability | Move the remaining hand-written writers onto `star/atomic_io.py` | M | S | proposal (after #308) |
| 11 | Reliability | Lesson capture failures are swallowed with no trace | M | S | proposal |
| 12 | Roblox tooling | `luau_lint` lexer: backtick strings, unterminated strings, quadratic slicing | M | M | proposal (coordinate #291/#300) |
| 13 | Roblox tooling | `luau_lint` rule precision (touched debounce, loop connection, DataStore race) | M | M | proposal (coordinate #291) |
| 14 | Roblox tooling | `luau_analyze` ignore list misses common globals and class types | M | S | proposal (coordinate #280) |
| 15 | Accessibility | Live region says "STAR replied" when an old chat is opened | M | S | proposal |
| 16 | Chat UX | In-session Retry after a failure adds a second user row | M | S | proposal (confirm intent) |
| 17 | Security | Voice `STAR_SERVER_URL` accepts link-local / metadata addresses | M | S | proposal (coordinate #294) |
| 18 | Security | Search replies and voice model downloads are not size-capped while streaming | L | S | proposal |
| 19 | Security | `github_app` HTTP clients honour system proxies (`trust_env`) | L | S | proposal |
| 20 | Security / CI | `protected_paths` git diff has no timeout and accepts refs starting with `-` | L | S | proposal |
| 21 | Performance | PIL imported at module top on text-only launches | L | S | proposal (may be in `cloud-perf`) |
| 22 | Performance | `roblox_errors.explain_output` matches every record twice | L | S | proposal |
| 23 | Chat UX | `active_task` is cleared after the result event is emitted | L | S | proposal |
| 24 | Code health | Duplicate helpers: UTC timestamps, private-IP regexes, three secret redactors | L | M | proposal |
| 25 | Code health | `with sqlite3.connect()` never closes; two more stores without WAL | L | S | proposal (after #273) |

## Implemented (details in each PR)

1. **Crash-safe settings (#308).** `Settings.save` wrote straight onto `settings.json`. A crash, or a
   read from another STAR process, could see a truncated file, and then every `Settings.load`
   raised. New `star/atomic_io.py` (`atomic_write_text`, `move_aside`). A damaged file is renamed
   `settings.json.corrupt-<UTC>` and the safe defaults are used.
2. **Composer limits (#320).** `react_shell.py` refuses chat over 30,000 characters, team over 12,000
   and image over 1,500. The composer let them through: a failed turn followed, the composer was
   cleared, and Retry failed again. It now shows a counter from 80%, disables Send over the limit
   and shows `aria-invalid` plus an alert. A parity test keeps the TypeScript limits equal to Python.
3. **Runtime stop (#312).** `Runtime.stop()` waited up to 15 s while holding the lock that
   `status()` needs. `status()` runs on the Qt UI thread for every state refresh. Stop now waits
   outside the lock. A crashed run's log handle is closed before the next start.
4. **Corrections WAL (#309).** A commit no longer fails with `database is locked` while the other
   process is reading. Checkpoints only get the longer busy timeout: the warm-up reads that file
   read-only, and WAL would leave `-wal`/`-shm` files behind.
5. **API suggestions (#311).** `get_close_matches(cutoff=0)` always suggested something. For
   example, `Instance.new("MyCustomHitboxThing")` produced "Review MeshPart." Suggestions now come
   from a case-only match or a difflib ratio of at least 0.6.
6. **Context refusals (#324).**
   `agent.execute` retried any 400 without the cache fields and then again without streaming. A
   prompt larger than the server context was refused three times before the error showed. That
   refusal is now recognised (llama.cpp, OpenAI-compatible, vLLM wording) and raised after one
   request. Other 400s keep both fallbacks.

## Proposals

7. **Streaming render cost.** `frontend/src/Desktop.tsx:237-239` calls `setStreamingText` for every
   delta, about every 75 ms. That re-renders the desktop. `Prose` (`components.tsx:102-128`) then
   re-parses the whole growing answer with remark-gfm, so total work grows with the square of the
   answer length. Fix: batch to one update per animation frame. Render finished blocks as memoized
   `Prose` and re-parse only the live tail. Wrap `Message` in `memo`.
8. **Slim state on chat switching.** `react_shell.py:1050-1077` (`newChat`, `openChat`,
   `deleteChat`) returns `_get_state()`. That re-imports bundles, rebuilds the analytics dashboard,
   learning status, MCP/Roblox/Blender/Studio status, and runs one keyring lookup per provider
   (`providers.py:193`), all on the UI thread. Fix: return
   `{messages, active_chat, chats, retry}`, and cache `credential_status()` until a key changes.
9. **Web fetch hardening.** Covered by the parallel `cloud-security-web-fetch` branch. Two points to
   carry over:
   - `codecs.lookup()` accepts non-text codecs (`rot13`, `base64`, `zlib`), and `bytes.decode`
     then still raises `LookupError`. Check `CodecInfo._is_text_encoding`.
   - `tool_result` claims it "never raises", but only catches four exception types, and
     `agent.py:726` has no `try` around it. Add a final `except Exception` that returns an
     `isError` result.
   A redirect issued by the gateway itself (`/search` → `/search/`) should keep the exemption.
10. **Atomic writers.** These use a fixed temporary name (it collides when two writers run at once
    and is left behind on error): `corrections.py:238`, `lessons.py:949`, `references.py:61`,
    `eval_runner.py:154` (harness-owned, do not change without review), `studio_remote.py:91`,
    `roblox_cloud.py:403`, `brain_setup.py:304`. `voice/bridge.py:143,232` writes `voice.json`
    in place. Move them all to `atomic_io.atomic_write_text` once #308 is merged. Leave voice until
    #294 is merged.
11. **Lesson capture errors.** At `desktop_core.py:975` the whole `learn_from_turn` body sits under
    `except Exception: pass`. If the lesson database breaks, lessons silently stop. Log a redacted
    one-liner and emit a `lessons_capture_failed` event.
12. **Luau lexer.**
    - `luau_lint.py:54` has no branch for backtick (interpolated) strings, so `` `wait(1)` `` is
      linted as code. `luau_safety.py` reuses the same lexer.
    - An unterminated quote swallows the rest of the file. Luau strings end at an unescaped newline.
    - `re.match(..., code[i:])` at lines 45 and 65 copies the rest of the source at every `--`
      and `[`.
    `roblox_api_checker.py:46,107,141-151` already does all three correctly; port it.
13. **Luau rule precision.**
    - `luau_lint.py:209` (touched debounce) inspects the first `function` anywhere after
      `Touched`, even with `Touched:Connect(onTouch)`.
    - At line 187, `"=" not in v[a:i]` suppresses loop-connection in every numeric `for` loop.
    - At lines 202-206, the GetAsync-then-SetAsync race is not checked in top-level code once any
      function exists.
14. **Analyzer ignore list.** `luau_analyze.py:36-42` lacks `Vector2`, `NumberRange`, `Random`,
    `Ray`, `DateTime`, `Rect`, `PhysicalProperties`, and class types used in `--!strict`
    annotations. These show up as "Unknown global/type". When an API dump is loaded, ignore
    `Unknown type` for class names in it.
15. **Live region.** `Desktop.tsx:665` derives `announce` from the last row. Opening an old chat
    therefore announces "STAR replied." Set the announcement only from the result and error
    handlers.
16. **Retry duplicates.** After a same-session failure, Retry (`Desktop.tsx:389,658`) sends no
    `retryMessageId`. That adds a second user bubble and a second database row
    (`react_shell.py:831`). Keep the failed turn's user row id and pass it, as the restart path
    (`recover_turn`) already does.
17. **Voice server URL.** `star/voice/brain.py:42-47`:
    - accepts `is_link_local` addresses (169.254.169.254, fe80::/10), `localhost` and any port;
    - the Bearer key is then sent there (lines 202, 239).
    Use `providers.validate_lan_endpoint` instead.
18. **Streaming size caps.** `web_search.py:106-111` downloads the whole body before checking its
    size, and the Brave and Tavily paths (133, 147) have no cap at all. `voice/setup_models.py:75-80`
    writes the whole file before comparing size, and does not check that the final URL is `https`.
    Count bytes while streaming, as `tool_discovery.py` does.
19. **Proxy for GitHub tokens.** `github_app.py:68,86` creates `httpx.AsyncClient` with the default
    `trust_env=True`. Every other client in the package sets it to `False`.
20. **protected_paths.** `protected_paths.py:123` runs `git diff base...head` with no timeout and no
    check for a leading `-` (CI-only input). Add `timeout=60` and refuse refs that start with `-`.
21. **Lazy PIL.** `media.py:5`, `chat_images.py:8`, `image_gen.py:23` and `diagnostics.py:22`
    import PIL at module level. `react_shell.py` pulls them in at startup. Import PIL inside the
    functions that use it.
22. **Double matching.** `roblox_errors.py:538,558`: `explain_output` runs `match_error` (about 60
    regexes) again for each record that `parse_output` already matched. Keep the matched rule on
    the record.
23. **Busy flag order.** `react_shell.py:513` emits `result` before `task()`'s `finally` clears
    `active_task`. A send in that window gets "already handling a task". The window is narrow in
    practice. Clear the flag before emitting.
24. **Duplicate helpers.**
    - UTC "now": `corrections._now`, `tool_workshop._now`, `memory.utc_now`, `learned_week._iso`,
      plus 14 inline copies.
    - Private-address regexes that disagree: `corrections.py:35` matches 127.x;
      `eval_runner.py:56` does not.
    - Secret patterns: `redact.redact_text`, `lessons._SECRET` and `roblox_training._SECRET`.
    Merge into `redact.py` and one clock helper. `eval_runner` is harness-owned and needs review.
25. **SQLite hygiene.** `with sqlite3.connect(...)` commits but does not close
    (`worked_examples.py:121,186`, `analytics.py:92`, `roblox_research.py:236`). Use
    `contextlib.closing`. `learned_week.py:198` and `worked_examples.py` have no WAL and no busy
    timeout. Do this after #273.

## Checked and fine (no change proposed)

- **`web_fetch.check_url`:**
  - checks every DNS answer, not just the host name;
  - connects to the checked IP, with SNI and Host carrying the name;
  - checks each redirect hop by hand;
  - refuses IPv4-mapped IPv6 spellings;
  - streams with a 2 MB limit.
- **Fixed-host fetchers** (`roblox_docs_live`, `roblox_research`, `evolution_research`,
  `asset_forge`, `tool_discovery`, `mcp_connections`) do not follow redirects, cap bytes while
  streaming, and set timeouts.
- **Archives:** `brain_setup._safe_extract` and `updates._extract_update` reject `..`, absolute
  paths, drive letters, symlinks and oversize archives. `documents._safe_zip` validates without
  extracting. No `tarfile` or `extractall` anywhere.
- **Path containment** is checked in `workspace.resolve`, `selfbuild._target`,
  `project_builder._file_under`, `agent_skills.read_reference`, `obsidian_bridge`,
  `blender_bridge.inspect`, `references`, `chat_images`, `comfy.upload`, `knowledge.artifact` and
  `react_shell.file_allowed`.
- **Subprocess timeouts:** every `subprocess.run` has one, except item 20.
