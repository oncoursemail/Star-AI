# Sources for roblox-datastore-service-patterns

Reviewed against official Roblox Creator Documentation on 2026-10-12. These examples are original guidance; no Roblox Studio run or knowledge-service /api-lookup was performed.

| ID | Supported claim and API | Official Roblox documentation |
|---|---|---|
| S1 | DataStoreService server-only access; GetDataStore | https://create.roblox.com/docs/reference/engine/classes/DataStoreService |
| S2 | GlobalDataStore:UpdateAsync semantics, cancellation, metadata and user IDs | https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore |
| S3 | pcall, retries, in-memory buffering, serializing writes and uncertain outcomes | https://create.roblox.com/docs/cloud-services/data-stores/best-practices |
| S4 | Modern DataStoreRequestType.StandardRead and StandardWrite values | https://create.roblox.com/docs/reference/engine/enums/DataStoreRequestType |
| S4 | Server request budgets and throttling limits | https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits |
| S5 | Atomic session-lock metadata claim, lease refresh and recovery | https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing |
| S6 | DataModel:BindToClose server shutdown | https://create.roblox.com/docs/reference/engine/classes/DataModel |
| S1 | HttpService:GenerateGUID for a unique lock identifier | https://create.roblox.com/docs/reference/engine/classes/HttpService |

No complete production profile system is supplied. STAR's offline Luau linter is a heuristic diagnostic, not a Luau compiler or Roblox Studio.
