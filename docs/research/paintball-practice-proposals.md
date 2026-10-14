# Practice-task proposals from the Paintball port lessons

Status: **proposals only**. Nothing here is written into `evals/` or into `star/practice_gen.py`, and nothing has run
in the Luau VM yet. Each proposal is shaped like a `practice_gen.Spec`:

- a key and one of the five failure-ledger causes (WL wrong logic, RF required feature missing, SC self-check error,
  CO answer cut off, IA invented API name);
- a goal and ten contexts;
- a prompt that runs as plain Luau without Roblox services;
- the unit-test `check(...)` lines;
- what the reference answer does;
- the bad answer, which must fail for its named cause.

Variant knobs say which numbers or names change across the ten variants. The task IDs would follow
`LG-<cause>-<KEY>-NN`.

Every task comes from a real problem the Paintball port project hit (see `docs/research/roblox-lessons-from-paintball.md`
in the Star workspace). None of them uses that project's game data or code.

## Summary

| # | Key | Cause | Goal | Real problem behind it |
|---|---|---|---|---|
| 1 | RESTSKIP | WL | Pose writer that skips unchanged poses at an exact tolerance | PivotTo nested-pivot flood (about 32k items/s) |
| 2 | GUARDSET | WL | Attribute cache that counts only changed writes | 8,700 setter attempts/s with zero changes |
| 3 | SEQFILTER | WL | Newest-packet filter per sender for unreliable messages | Out-of-order unreliable remote updates |
| 4 | TOKENBUCKET | WL | Command rate limiter with a burst and an exact refill boundary | Client commands at 50 Hz, burst 100 |
| 5 | REQCOVER | WL | Require-coverage checker over an install list | A module missing from the installer broke startup |
| 6 | DEPCLOSURE | RF | Dependency-first install closure with cycle and unknown errors | Installing only selected modules safely |
| 7 | HASHGATE | WL | Upload gate verdict where BLOCKED overrides APPROVED | Exact-hash upload review |
| 8 | BATCHSTOP | WL | Upload batch that stops at the first moderation error | Tool success flag hiding per-item errors |
| 9 | VERDICT | WL | Combine QA step verdicts; empty or timeout is never PASS | Honest PASS/FAIL/INCOMPLETE reporting |
| 10 | WATCHDOG | WL | Loading watchdog: cancel after N s without progress, retry once | Join stuck at "Preloaded Assets" |
| 11 | CLAIMS | RF | Claim registry with a 6-hour window, release and stale report | Claude and Codex file claims |
| 12 | STUDIOLOCK | WL | Session lock: hold limit, stale age, release only by holder | The shared Studio lock |
| 13 | CHUNKS | CO | Long module: split and reassemble data chunks, finished | Large generated data split into chunk modules |
| 14 | PARTSPAN | WL | Number of mesh chunks along an axis with a 2048-stud cap | Part size cap read back as 2048 |
| 15 | BYTEMODEL | WL | Tagged-value byte estimate for a remote payload | Offline network budget fixture |
| 16 | BOUNDEDCACHE | RF | Bounded LRU cache with every listed method | Unbounded caches flagged by the perf lint |
| 17 | HANDOFF | IA | Pick the newest ACTIVE block from handoff text with real string functions | Newest-block-wins handoff file |
| 18 | SAVEGUARD | SC | Strict-typed path check before a save | Saving a place whose map was missing |

---

## 1. RESTSKIP (WL): pose writer that skips unchanged poses
- **Contexts (10):** a flag carrier, a pickup weapon, a door, a moving platform, a vehicle, a scoreboard projector, a
  turret, a held shield, an elevator, a drawbridge.
- **Variant knobs:** tolerance (0.001 to 0.05), number of objects.
- **Prompt:** Write `PoseWriter.new(tolerance)`. Its method `:shouldWrite(id, x, y, z): boolean` returns true the first
  time an id is seen. After that it returns true only when the distance from the LAST WRITTEN position is strictly
  greater than `tolerance`, and then records the new position. A refused call changes nothing. A distance exactly
  equal to the tolerance is refused. Each id is tracked separately.
- **Checks:**
  - `check("first sight writes", ...)`
  - `check("tiny move refused", ...)`
  - `check("exactly tolerance is refused", ...)`
  - `check("just over tolerance writes", ...)`
  - `check("refused moves do not drift the anchor", ...)` (many small moves add up past the tolerance and then write)
  - `check("ids are independent", ...)`
- **Reference:** a table of last positions; compares `math.sqrt(dx*dx+dy*dy+dz*dz) > tolerance`.
- **Bad (WL):** updates the stored position on refused calls too (anchor drift), so the accumulated-drift check fails.
- **Require:** defines `shouldWrite`.

## 2. GUARDSET (WL): attribute cache that counts only real changes
- **Contexts:** a sprint flag, a team colour, a health value, an ammo count, a round state, a carry state, a crouch
  flag, a score, a stamina bar, a spectate flag.
- **Variant knobs:** key names, value types (number, string, boolean).
- **Prompt:** `Cache.new()` with `:set(key, value): boolean` (true only when the value differs from the last stored
  value, or the key is new), `:attempts(): number` and `:writes(): number`. Setting nil removes the key and counts as
  a write only when the key existed.
- **Checks:**
  - new key writes
  - same value does not write but counts an attempt
  - false versus nil handled
  - removing a missing key is not a write
  - the counts are exact after a scripted sequence
- **Bad (WL):** treats `false` like nil (`if not old then`), so setting false after true is miscounted.

## 3. SEQFILTER (WL): newest-packet filter per sender
- **Contexts:** player poses, projectile updates, vehicle states, camera targets, voice levels, flag positions, NPC
  paths, ping samples, wind states, crowd animation.
- **Variant knobs:** sender IDs, sequence start values.
- **Prompt:** `Filter.new()` with `:accept(sender, sequence): boolean`. It accepts the first packet from a sender, then
  only strictly higher sequence numbers for that sender. Duplicates and older packets are refused. Senders are
  independent. `:reset(sender)` forgets one sender.
- **Checks:**
  - first accepted
  - duplicate refused
  - older refused
  - newer accepted
  - senders independent
  - reset lets a low sequence in again
- **Bad (WL):** uses `>=` (accepts duplicates).

## 4. TOKENBUCKET (WL): command rate limiter
- **Contexts:** fire commands, chat sends, emote requests, trade offers, build actions, vote clicks, ping markers,
  interact presses, reload requests, jump requests.
- **Variant knobs:** rate (10 to 60 per second), burst (rate to 2x rate).
- **Prompt:** `Bucket.new(rate, burst)` starts full. `:take(now): boolean` refills `rate * elapsed` tokens, capped at
  `burst`, then spends 1 if at least 1 token is available. A refused take spends nothing.
- **Checks:**
  - burst allowed back to back
  - burst + 1 refused
  - exactly 1/rate seconds later one more is allowed
  - the cap is never exceeded after a long idle
  - a refused take leaves the tokens unchanged
- **Bad (WL):** refills without the burst cap, so a long idle allows more than `burst`.

## 5. REQCOVER (WL): require-coverage checker
- **Contexts:** a round system, a shop, a weapon kit, a HUD, a settings menu, an audio system, a map loader, a quest
  log, an inventory, a lobby.
- **Variant knobs:** module names and graph shape.
- **Prompt:** `missingRequires(installed: {string}, requires: {[string]: {string}}): {string}`. It returns the sorted,
  de-duplicated names that some INSTALLED module requires but that are not installed. Modules that are not installed
  do not count, even when they require missing names.
- **Checks:**
  - an empty result when covered
  - one missing name found
  - duplicates reported once
  - output sorted
  - requires of uninstalled modules ignored
- **Bad (WL):** also scans uninstalled modules, so extra names are reported.

## 6. DEPCLOSURE (RF): dependency-first install closure
- **Contexts:** the same as REQCOVER.
- **Prompt:** `Closure.new(requires)` with these methods:
  - `:closure(names): {string}`: dependencies first, ties sorted alphabetically.
  - `:hasCycle(): boolean`
  - `:unknown(names): {string}`: names that are not in the graph.
  - `:isInstalledOrder(list): boolean`: every module appears after all of its dependencies.

  An unknown name makes `closure` return nil.
- **Checks:** one assertion per method ("required feature: closure", and so on), plus behaviour.
- **Bad (RF):** leaves out `isInstalledOrder`.

## 7. HASHGATE (WL): upload gate verdict
- **Contexts:** a skybox, a sign texture, a UI icon sheet, a terrain map, a decal pack, a loading image, a face sheet,
  a jersey texture, a particle sheet, a thumbnail.
- **Variant knobs:** hash strings.
- **Prompt:** `verdict(hash, approved: {[string]: boolean}, blocked: {[string]: boolean}): string` returns `"BLOCKED"`
  if the hash is blocked (even when approved), `"APPROVED"` if approved, else `"PENDING"`. Hash comparison ignores
  case. An empty or nil hash is `"PENDING"`.
- **Checks:**
  - blocked overrides approved
  - case-insensitive match
  - an unknown hash is pending
  - nil and empty are pending
- **Bad (WL):** checks approval before the blocked list.

## 8. BATCHSTOP (WL): upload batch that stops at the first moderation error
- **Contexts:** a texture batch, an audio batch, a decal batch, an icon batch, a mesh batch, a face batch, a jersey
  batch, a sign batch, a sky batch, a UI batch.
- **Prompt:** `processBatch(results)`. Each result is `{ name, ok, assetId?, error? }`, and the reply as a whole may
  also carry `overallSuccess = true`. Return `{ uploaded = {names}, stoppedAt = name|nil, reason = string|nil }`.
  - Count a result as uploaded only when `ok` is true AND `assetId` is a positive integer.
  - Stop at the first result whose error contains "moderated", "Blocked" or "403", case-insensitive.
  - Keep earlier successes.
  - Results after the stop are not processed.
- **Checks:**
  - an `overallSuccess` flag does not hide per-item errors
  - a missing or zero assetId is not uploaded
  - stops at the first moderation error
  - later items untouched
  - the reason is recorded
- **Bad (WL):** trusts `overallSuccess`, or continues after the moderation error.

## 9. VERDICT (WL): combine QA verdicts
- **Contexts:** a CTF capture run, a team battle, a late join, a grenade test, a shield test, name tags, loading, VO
  playback, a settings menu, a spawn check.
- **Prompt:** `combine(steps: {string}): string`.
  - Any `"FAIL"` gives `"FAIL"`.
  - Otherwise any `"INCOMPLETE"`, `"PENDING"` or unknown string gives `"INCOMPLETE"`.
  - Only a non-empty list of all `"PASS"` gives `"PASS"`.
  - An empty list is `"INCOMPLETE"`.
- **Checks:**
  - all pass
  - one fail wins over incomplete
  - pending counts as incomplete
  - an unknown label is incomplete
  - an empty list is INCOMPLETE
- **Bad (WL):** an empty list returns PASS.

## 10. WATCHDOG (WL): loading watchdog with one bounded retry
- **Contexts:** mesh loading, image loading, audio preload, avatar build, map streaming, data fetch, font load,
  animation bank, UI atlas, music preload.
- **Variant knobs:** timeout (10 to 45 s).
- **Prompt:** `Watchdog.new(timeout)` with these methods:
  - `:progress(now)`: records progress.
  - `:tick(now)`: returns `"ok"`, `"retry"` or `"fail"`.
  - `:failService()`: marks a service failure, which is never retried.

  `"retry"` comes once, when `now - lastProgress >= timeout` and no retry has happened. After a retry the timer
  restarts. A second timeout gives `"fail"`. A service failure gives `"fail"` immediately, without a retry.
- **Checks:**
  - exactly the timeout triggers a retry
  - progress resets the timer
  - the second timeout fails
  - a service failure never retries
- **Bad (WL):** retries forever (returns "retry" on every timeout).

## 11. CLAIMS (RF): claim registry
- **Contexts:** a code folder, a map file, a UI folder, a data builder, a test file, an installer list, a handoff file,
  a baseline file, a ledger, a sound folder.
- **Prompt:** `Claims.new(windowSeconds)` with these methods:
  - `:add(owner, path, now)` returns false if another owner claimed the path within the window;
  - `:release(owner, path)`, which only the owner can do;
  - `:owner(path, now)`;
  - `:stale(now): {string}`, the sorted paths whose claim is older than the window. It reports them and never releases
    them.
- **Checks:** "required feature: add/release/owner/stale", plus:
  - another owner refused inside the window
  - allowed after it
  - a non-owner cannot release
  - stale does not release
- **Bad (RF):** leaves out `stale`.

## 12. STUDIOLOCK (WL): session lock with hold and stale limits
- **Contexts:** a Studio session, a timing run, a playtest, a cloud save, an install, an asset import, a perf capture,
  a QA scenario, a screenshot pass, a server benchmark.
- **Variant knobs:** maxHold (300 to 900 s), staleAfter (maxHold + 300).
- **Prompt:** `Lock.new(maxHold, staleAfter)` with these methods:
  - `:take(holder, now)`: true if the lock is free, already held by the same holder (this refreshes it), or stale
    (`now - takenAt >= staleAfter`);
  - `:release(holder)`: true only for the current holder;
  - `:overdue(now)`: true when `now - takenAt > maxHold`.
- **Checks:**
  - a second holder is refused before stale
  - exactly staleAfter can be taken over
  - a non-holder cannot release
  - overdue is strict
- **Bad (WL):** lets any caller release the lock.

## 13. CHUNKS (CO): long chunking module, finished
- **Contexts:** avatar geometry, animation data, a map manifest, a dialogue table, a jersey table, a gun colour table,
  a sound index, a collision table, a UI atlas index, a localisation table.
- **Prompt:** 8 functions:
  - `split(text, size)`
  - `join(chunks)`
  - `count(text, size)`
  - `chunkName(i)` gives `"Chunk001"` style names
  - `manifest(text, size)`
  - `verify(chunks, manifest)`
  - `checksum(text)` (a sum of bytes mod 2^32)
  - `largest(chunks)`

  Written compact, ending with the return statement.
- **Checks:**
  - round trip at exact multiples and at multiples plus 1
  - zero-padded names
  - checksum stable
  - verify catches a missing chunk
- **Bad (CO):** stops mid-module inside an open fence.

## 14. PARTSPAN (WL): mesh chunks along an axis with a cap
- **Contexts:** a terrain strip, a river bed, a fence line, a road, a wall, a cliff face, a bridge deck, a tunnel, a
  pipe run, a runway.
- **Variant knobs:** cap (512, 1024, 2048), lengths.
- **Prompt:** `chunks(length, cap): number` returns the smallest number of equal chunks so that each one is at most
  `cap`; `chunkSize(length, cap)` returns length / chunks. A zero or negative length gives 0 chunks.
- **Checks:**
  - an exact multiple (2 x cap gives 2, not 3)
  - cap + 1 gives 2
  - a tiny length gives 1
  - zero gives 0
  - the size never exceeds the cap
- **Bad (WL):** `math.floor(length / cap) + 1`, which is wrong at exact multiples.

## 15. BYTEMODEL (WL): tagged-value byte estimate
- **Contexts:** a snapshot, a hit event, a score update, a pose packet, a chat relay, an inventory sync, a flag event,
  a round state, a kill feed entry, a settings sync.
- **Prompt:** `size(value)`. Every value costs 1 tag byte plus a payload:
  - number 8
  - boolean 1
  - string 4 + #s
  - table 4, plus the size of each key and each value (array keys count as numbers)
  - nil 0

  Nested tables are counted recursively.
- **Checks:**
  - each scalar type
  - an empty table = 5
  - array keys counted
  - nested tables include their own tag
- **Bad (WL):** forgets the tag byte on nested tables.

## 16. BOUNDEDCACHE (RF): LRU cache with eviction
- **Contexts:** a mesh cache, a pose cache, a text-width cache, a raycast cache, an icon cache, a path cache, a name-tag
  cache, a sound cache, a colour cache, a texture cache.
- **Prompt:** `LRU.new(capacity)` with `:get(k)`, `:set(k, v)`, `:size()`, `:evictions()`, `:clear()` and `:keys()`
  (most recent first). A `get` refreshes recency. Setting an existing key refreshes it without an eviction.
- **Checks:** "required feature" for each method, plus:
  - capacity respected
  - the oldest evicted
  - get refreshes
  - clear resets size but not the eviction count
- **Bad (RF):** leaves out `evictions` (and so the eviction accounting).

## 17. HANDOFF (IA): newest ACTIVE block with real string functions
- **Contexts:** a game port, a tycoon build, an obby, a shooter, a racing game, a simulator, a roleplay town, a tower
  defense, a horror map, a sports game.
- **Prompt:** `newestActive(text): string?`. Blocks start with a line `## ACTIVE <ISO-8601 UTC time>`. Return the body
  of the block with the latest time, compared as strings in the fixed `YYYY-MM-DDTHH:MM:SSZ` format. Use only
  `string.gmatch`, `string.match`, `string.find`, `string.sub` and `table` functions.
- **Checks:**
  - newest chosen even when it is not first
  - a malformed header is ignored
  - no block returns nil
  - the body excludes the next header
- **Bad (IA):** calls a nonexistent `StringUtil.split` helper.

## 18. SAVEGUARD (SC): strict-typed path check before saving
- **Contexts:** an arena map, a lobby, a race track, an obby course, a tycoon plot, a battle royale island, a dungeon,
  a city, a farm, a space station.
- **Prompt:** `--!strict` module over a plain-table tree. The type is `type Node = { name: string, children: {Node} }`,
  and `findPath(root: Node, path: {string}): Node?` returns the node or nil. `canSave(root: Node, required:
  {{string}}, running: boolean): (boolean, string?)` is false while running, or when any required path is missing,
  and gives the first missing path joined with ".".
- **Checks:**
  - a present path is found
  - a missing path gives false with its name
  - running blocks the save
  - strict type check passes
- **Bad (SC):** indexes an optional `Node?` without narrowing, which is a real strict-mode error.

## Next steps (not done here)
1. Turn the chosen proposals into `Spec` builders with ten variants each, including the reference and bad answers.
2. Run them through `practice_gen.verify` and the real Luau VM, and check that the ledger labels each bad answer with
   its cause.
3. Only then add them to the practice pool. They stay out of the holdout and the golden tasks.
