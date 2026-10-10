# STAR Roblox Intelligence — Research and Engineering Notes
**Research date: 2026-10-09 | Status: review-branch implementation candidate; not a Windows release.**

## Objective and shipped code

STAR now has a read-only, task-scoped Roblox research module in star/roblox_research.py, routed through its existing Python intelligence and agent tools. The user still interacts through the same STAR chat. The module does not issue writes or introduce a new frontend product. It respects existing Roblox Studio MCP editing permissions, Obsidian, Graphify, skills, chat storage and updater.

| Tool | Capability | Evidence / limits |
|---|---|---|
| star_roblox_search_games | Public keyword discovery and grounded universe IDs | Experimental endpoint; limited search, not full catalog |
| star_roblox_game_report | Officially hosted public game data: creator, description, creation/update, playing snapshot, cumulative visits, favorites, votes, image URLs, genre hypothesis | Auxiliary errors are surfaced; genre is not proven gameplay |
| star_roblox_compare_games | Same public metrics for 2–4 universes | Snapshot data, not DAU, revenue or retention |
| star_roblox_docs | Search a curated official Creator Hub/Luau link index | Not a complete documentation crawler |
| star_roblox_forum_search / star_roblox_forum_latest | Source-linked community discussions and topics | Anti-bot/rate limits possible; not every topic is official |
| star_roblox_youtube_search | Video search metadata and source links with optional API key | Without API key, returns a search link and no fabricated results |
| star_roblox_youtube_video | YouTube oEmbed or Data API metadata, thumbnail and available stats | Does not watch footage or obtain arbitrary transcripts |
| star_roblox_cloud_universe | Owner-authorized read of universe metadata | Requires locally configured least-privilege key; no writes |

A local SQLite file under STAR application data stores public aggregate game observations with timestamps. Historical delta is calculated ONLY from previous actual local observations. Data expires after 90 days. No chats, user files, identities, private player data or model weights are copied into this table.

## 1. Roblox Open Cloud: officially supported APIs

Roblox Open Cloud supports API-key/OAuth authorization, stable REST operations, scoped authorization and OpenAPI descriptions. Compared with older cookie-based interfaces, prefer Open Cloud for supported creator operations.

- API reference: https://create.roblox.com/docs/cloud
- API endpoints: https://create.roblox.com/docs/cloud/reference
- OpenAPI document: https://create.roblox.com/docs/cloud/reference/openapi
- Scopes: https://create.roblox.com/docs/cloud/reference/scopes
- API key guidance: https://create.roblox.com/docs/cloud/auth/api-keys
- Creator docs Markdown: https://github.com/Roblox/creator-docs

Current STAR integration uses only GET /cloud/v2/universes/{universe_id} with the local STAR_ROBLOX_READ_API_KEY environment credential if supplied. It does not grant a model a user's Roblox session cookie, write scopes, experiences outside token scope, publishing, server restarts or economy operations.

**Important analytics distinction:** owner-authorized Analytics Query APIs under universe.analytics:read may expose aggregated DAU, retention and revenue. These values are not accessible for arbitrary competing experiences. The analytics query API can involve asynchronous operation polling and should be added only after reviewed key scopes. Source: https://create.roblox.com/docs/cloud/guides/analytics

## 2. Public games, statistics and genre identification

Roblox Creator Hub documents public game details under games.roblox.com/v1/games and votes. The public API can include Universe ID, root Place ID, title, creator, description, playing-now count, lifetime visits, favorites, max server player capacity and dates. Some metadata and thumbnail API endpoints are experimental/legacy and can change without notice.

Sources:
- https://create.roblox.com/docs/cloud/reference/features/universes
- https://create.roblox.com/docs/cloud/reference/features/thumbnails
- https://games.roblox.com/v1/games?universeIds=920587237

**Never conflate Universe IDs and Place IDs.** A Roblox experience page URL commonly takes the root Place ID; public data endpoints take the Universe ID. A game title is not a unique identity. STAR's search hydrates explicit Universe IDs from results rather than guessing a number. Place-ID-only resolution is still a later implementation task.

**Metric semantics:** playing means a point-in-time concurrently playing snapshot, visits is cumulative sessions/visits rather than unique users, favorites and votes are platform counters. None of these proves revenue, DAU, retention, engagement time, originality or game quality. STAR should not invent any of these.

**Gameplay taxonomy:** a name and description may suggest an obby, shooter, survival, simulator, tycoon, social RP, battleground, puzzle, tower defense or racing game, including overlapping types. STAR returns matching phrase clues and low/medium/insufficient-confidence labels. A description is not observation of UI, combat, animations, economy or game loop. For verified mechanics, inspect Studio state, screenshots or permitted gameplay footage.

## 3. Discovery and game search

Roblox deprecated older games/list and games/sorts interfaces and recommended its search-api/omni-search and explore-api systems in a May 2024 announcement:
https://devforum.roblox.com/t/official-list-of-deprecated-web-endpoints/62889/59

The current public search can change structure, localization and availability. STAR's integration pins the host to apis.roblox.com, requests only a small page, walks nested data with a depth bound, deduplicates explicit Universe IDs and verifies matches against official game details. It does not assume that results are exhaustive. It refuses to fake results if the endpoint is unavailable or changes schema. No unreviewed third-party proxy or CAPTCHA bypass is used.

Later improvements: optional search pagination, named-game ambiguity resolution, Explore sorts, source freshness timestamps, and cache invalidation. Competitor monitoring must be opt-in and rate-budgeted.

## 4. Image retrieval and UI reasoning

The thumbnails.roblox.com endpoints can return game icon/thumbnail asset URLs:
https://create.roblox.com/docs/cloud/reference/features/thumbnails

Current patch retrieves fixed-host JSON and returns only validated Roblox-CDN image URLs with source attribution. **Returning an image URL is not the same as displaying or visually analyzing pixels.** Actual image understanding requires a guarded media-fetch and decode path (known Roblox CDN origins, MIME/byte bounds, encoded image decode, resizing, cached preview, local vision support) wired into STAR's existing chat. This should not become a separate Image Lab screen.

STAR already has a Studio MCP screenshot path that can send genuine Studio image pixels to a vision-capable model. Roblox Studio MCP official information: https://create.roblox.com/docs/studio/mcp

## 5. Luau engineering and code research

Relevant official resources:
- Language: https://create.roblox.com/docs/luau
- Engine APIs: https://create.roblox.com/docs/reference/engine
- General scripting: https://create.roblox.com/docs/scripting
- Remote communication: https://create.roblox.com/docs/scripting/events/remote
- Type checking: https://create.roblox.com/docs/luau/type-checking
- Script profiler: https://create.roblox.com/docs/studio/optimization/scriptprofiler
- Improve performance: https://create.roblox.com/docs/performance-optimization/improve
- Parallel Luau: https://create.roblox.com/docs/scripting/multithreading

Reviewable external developer tools:
- Roblox Studio MCP: https://create.roblox.com/docs/studio/mcp
- Luau compiler/type checker (luau-analyze): https://github.com/luau-lang/luau
- Studio Script Sync: https://create.roblox.com/docs/scripting/sync
- Rojo filesystem project sync: https://github.com/rojo-rbx/rojo
- StyLua formatter: https://github.com/JohnnyMorganz/StyLua

These are **candidate future integrations**, not installed executables in this patch. Proper Luau development must consider server/client authority, RemoteEvent payload validation, replication cost, DataStore limits, clean event connection teardown, StreamingEnabled, mobile layout and performance. Review Luau scripts before executing them; prohibit model-generated unrestricted code execution, publication, purchases, private data access, and unauthorized third-party assets. STAR's existing selected Studio and disposable-edit gates remain in place.

## 6. Roblox DevForum and news

Forum search uses the public Discourse search interface and latest topics when accessible, with fixed origin, bounded JSON and source links. A topic can be wrong or outdated: distinguish community advice, announcement posts and official current documentation. Some DevForum endpoints can return challenge pages; STOP and report that rather than bypassing anti-bot protections.

- Updates: https://devforum.roblox.com/c/updates/45/l/latest
- Newsroom: https://about.roblox.com/newsroom
- Service status: https://status.roblox.com/
- Creator Hub: https://create.roblox.com/docs

Future update pipeline: separately approved polling of official announcements, ETags, cache, categorization by affected Roblox API/component, duplicate handling, timestamp provenance and regression notices when Luau API behavior changes.

## 7. YouTube: metadata versus actual watching

YouTube Data API v3 provides:
- Video search: https://developers.google.com/youtube/v3/docs/search/list
- Metadata/statistics: https://developers.google.com/youtube/v3/docs/videos/list
- Quotas: https://developers.google.com/youtube/v3/getting-started
- Caption listing: https://developers.google.com/youtube/v3/docs/captions/list
- Caption downloads: https://developers.google.com/youtube/v3/docs/captions/download

The search API may be enabled with STAR_YOUTUBE_API_KEY in the local process environment. STAR can report titles, creator, thumbnail, descriptions, publish time and public statistics. Public oEmbed can supply metadata for exact IDs when the API key is missing.

**Important:** YouTube metadata is not video comprehension. YouTube caption download requires authorization to edit the video; a public API key does not authorize arbitrary transcript downloads. STAR's video tools explicitly return video_watched=false and do not claim frames, audio, motion or transcript interpretation.

Compliant future video understanding:
1. User supplies a lawful local clip, authorized recording, or permitted captions.
2. Decode sampled video frames offline with a pinned, security-reviewed FFmpeg/PyAV pipeline, cap media duration, image dimensions and total bytes, preserve frame timestamps.
3. Process frames with local vision and optional authorized local speech transcription.
4. Derive time-coded scene, gameplay, UI, VFX, camera and animation evidence; retain observation versus inference.
5. Generate a game-mechanics outline with citations and human verification; no unauthorized copyrighted game cloning.

## 8. Engineering architecture, budgets and threats

The adapter performs GET calls only against fixed Roblox, forum, Google and YouTube hosts. Hosts and endpoint paths are developer-selected, never model-supplied. Numeric IDs, video IDs and search terms have validation. HTTP redirects, proxy environment inheritance, oversized JSON, HTML/CAPTCHA responses and malformed output are rejected. Per-task TTL caching avoids needless duplicate calls; extra thumbnails and vote failures are downgraded to warnings, not fabricated values. Google/Roblox keys never appear in returned data, application settings, or code repository.

A persistent SQLite snapshot contains only public game universe ID, time, CCU, visits and favorite counts, and prunes observations older than 90 days. STAR keeps its existing private user-chat, memories and models untouched.

Performance strategy: only advertise relevant tool schemas in the model request. Cache frequent game lookups, limit comparisons to four games, return compact metadata and cap API timeout; add batching/circuit breakers only when measured. Do not claim a benchmark improvement without p50/p95 local tests and real network timings.

## 9. Path to a world-class Roblox development agent

**R1 — Current review candidate.** Grounded public search/report/compare; genre uncertainty; original image URLs; curated docs; DevForum; YouTube metadata; read-only scoped Open Cloud; task-scoped STAR chat tools; regression tests.

**R2 — Images and identity.** Reliable Place ID → Universe ID resolution; image display directly in chat and actual vision image analysis; source provenance; official-announcement filter; Explore categories; measured parallel/batched requests.

**R3 — Knowledge and analytics.** Incrementally index official Creator Docs and APIs with citations, retrieve relevant current API descriptions and examples, ingest Roblox engine change notices, add owner-only analytics query with careful permission scopes and asynchronous polls.

**R4 — Toolchain and Studio workflows.** Integrate approved luau-analyze, StyLua and Rojo/Script Sync under a bounded file workspace and independently reviewed executors; automatic disposable-place tests, Luau warnings, replication validation, server-client security review, Studio screenshot baselines, game UI responsive checks and performance profiler observations.

**R5 — Training and evaluation.** Use licensed or user-owned Luau projects and expert-reviewed synthetic examples, not scraped copyrighted game code or private player data. Train/evaluate a specialist adapter only after a held-out corpus and benchmarks for correctness, type safety, security, server-client boundaries, game loop behavior, layout screenshots, FPS, streaming and regression. Retrieval/tool integration is not the same thing as modifying model weights.

## 10. Release checklist and reality

Run: Python compileall, entire pytest suite, static checks, frontend TypeScript/Vitest/Vite, Windows packaged smoke tests, manual real Roblox Studio connection and live API key/429/timeout behavior. Never call mocked tests a real API integration test. Human review is needed before merging into main or publishing installers because other Star teams are concurrently working on chat, images and model performance.

**Security non-goals:** no cookies/scraping bypass, secrets in GitHub, player data harvesting, arbitrary URL proxies, model-run remote scripts, unsandboxed Luau execution, live game edits without permission, auto-publish or silent model training.
