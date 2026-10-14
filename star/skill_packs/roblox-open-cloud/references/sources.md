# Sources for roblox-open-cloud

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live game, and no Open Cloud request was sent while writing this pack.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | Open Cloud overview | https://create.roblox.com/docs/cloud |
| S2 | Open Cloud data stores: universe ID, separate create/update permissions, serialization, tagged non-finite numbers | https://create.roblox.com/docs/cloud/guides/data-stores |
| S3 | Secrets stores: GetSecret on servers, a Secret prints only its name, local secrets for Studio | https://create.roblox.com/docs/cloud-services/secrets |
| S4 | Managing keys: minimum scopes, accepted IP addresses, expiration | https://create.roblox.com/docs/cloud/auth/api-keys |
| S5 | HttpService with Open Cloud: supported endpoints, allowed headers, Secret key, 2,500 requests per minute, validate received data | https://create.roblox.com/docs/cloud-services/http-service |
| S6 | Open Cloud messaging usage: topics, live servers, shared limits, 1 KiB messages, 80-character topics | https://create.roblox.com/docs/cloud/guides/usage-messaging |
| S7 | MessagingService SubscribeAsync and message Data | https://create.roblox.com/docs/reference/engine/classes/MessagingService |
| S8 | HttpService JSONDecode and GetSecret | https://create.roblox.com/docs/reference/engine/classes/HttpService |
| S9 | GlobalDataStore UpdateAsync callback may return value, user IDs and metadata | https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore |
| S10 | Data store right to be forgotten: user ID in the name or key | https://create.roblox.com/docs/cloud-services/data-stores/right-to-be-forgotten |
| S11 | Experience configs: ConfigService on the server, snapshots, Refresh, UpdateAvailable, value change signals, errors | https://create.roblox.com/docs/production/configs |
| S11 | ConfigService GetConfigAsync | https://create.roblox.com/docs/reference/engine/classes/ConfigService |
| S12 | Open Cloud rate limits: HTTP 429, retry-after, exponential backoff | https://create.roblox.com/docs/cloud/reference/rate-limits |
| S13 | DataStoreService GetDataStore | https://create.roblox.com/docs/reference/engine/classes/DataStoreService |
| S14 | Players GetPlayerByUserId and Player Kick | https://create.roblox.com/docs/reference/engine/classes/Players |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
