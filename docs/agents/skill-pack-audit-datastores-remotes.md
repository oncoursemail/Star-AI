# DataStore and remotes skill-pack factual audit

Status: review material, not a model-quality evaluation. Examined 53 checkable claims on 2026-10-13 against the linked *official Roblox Creator Hub* pages. Each line number refers to the **pre-audit** `SKILL.md` on `star/next` at commit `64c1982c37521ca78d3c893a483a6d833b9a81f1`. A verdict of **partly** means qualified or context-dependent; **unverifiable** means the cited page does not establish the stronger original wording. Such numbers and categorical requirements were removed or marked as nonengine policy, not endorsed.

| Verdict | Count |
|---|---:|
| true | 35 |
| partly | 11 |
| false | 3 |
| unverifiable | 4 |
| **Total** | **53** |

## Audited claims

| Pack / original line | Checkable claim from pack (paraphrased) | Verdict | Official source | Treatment |
|---|---|---|---|---|
| `star/skill_packs/roblox-datastore-safety/SKILL.md:6` | pcall for yielding data-store calls | **true** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/best-practices) | Clarified transient retries |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:6` | Three attempts is the prescribed retry count | **unverifiable** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/best-practices) | Labelled optional policy, not engine default |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:7` | UpdateAsync reads current value and conditionally commits | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore) | Clarified concurrency and retries |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:7` | SetAsync must never replace an existing key | **false** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/best-practices) | Allow independent replacement/new-key writes |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:7` | UpdateAsync callback cannot yield and can be retried | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore) | Retained |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:8` | Player_ prefix is required by the engine | **unverifiable** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/DataStoreService) | Explained as key convention |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:8` | A key value can contain serializable data | **true** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits) | Clarified encoding |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:8` | Maximum key-value size is simply 4 MB | **partly** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits) | Replaced with 4,194,304 serialized characters |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:9` | Players.PlayerRemoving is a departure event | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/Players) | Retained |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:9` | BindToClose callbacks run in parallel during shutdown | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/DataModel) | Clarified shutdown success is not guaranteed |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:10` | Throttled requests queue; full queues drop 301-306 | **true** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits) | Added 30-per-queue bound |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:10` | Autosave interval 60 seconds is an engine limit | **unverifiable** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/best-practices) | Explicitly labelled design choice |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:11` | ProcessReceipt success requires confirmed grant and PurchaseId | **partly** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing) | Specified atomic persistence and replay |
| `star/skill_packs/roblox-datastore-safety/SKILL.md:12` | A session lock is required for all keys | **partly** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing) | Conditional lock with owner/lease checks |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:8` | DataStoreService belongs in server scripts | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/DataStoreService) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:9` | UpdateAsync reads and writes budget types | **true** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:10` | UpdateAsync nil transform cancels write | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:10` | UpdateAsync transform must not yield | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:11` | pcall and ordered bounded retries are recommended | **true** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/best-practices) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:12` | StandardRead and StandardWrite are current enum names | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/enums/DataStoreRequestType) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:12` | The older UpdateAsync budget enum is called legacy | **partly** | [Creator Hub](https://create.roblox.com/docs/reference/engine/enums/DataStoreRequestType) | Rephrased: still exists but newer budget docs use Standard types |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:13` | Preflight budget snapshot does not reserve capacity | **partly** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/error-codes-and-limits) | Kept as caveat, not hard guarantee |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:14` | Atomic session-lock claim can use UpdateAsync metadata | **true** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:15` | Lease needs refresh, release and crash recovery | **true** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/player-data-purchasing) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:16` | Metadata and user IDs should be preserved | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/GlobalDataStore) | Retained |
| `star/skill_packs/roblox-datastore-service-patterns/SKILL.md:17` | Serialized writes protect cross-server progress | **partly** | [Creator Hub](https://create.roblox.com/docs/cloud-services/data-stores/best-practices) | Keep ordered retries; no universal serialization guarantee |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:8` | Server must validate untrusted client messages | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:9` | OnServerEvent first arg is sender Player | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteEvent) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:9` | OnServerInvoke first arg is sender Player | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteFunction) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:9` | A client-supplied identity must not replace the sender Player | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Already correctly rejects client-supplied identity |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:10` | Reject every client-supplied Instance regardless of validation | **partly** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Explicitly allow independent server authorization |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:11` | Measure distance against server state | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:12` | Apply server-owned per-player rate limiting | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:13` | Clean up PlayerRemoving keyed state | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/Players) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:14` | FireServer is client-to-server RemoteEvent API | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteEvent) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:14` | FireClient provides server-to-client async notification | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteEvent) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:15` | InvokeServer invokes server callback and yields | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteFunction) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:16` | InvokeClient can hang and must not authorize rewards | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteFunction) | Retained |
| `star/skill_packs/roblox-remote-event-function-patterns/SKILL.md:17` | Any approved message key is automatically secure | **partly** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Advice only; server must still sanitize exposed information |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:6` | Client arguments are untrusted | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:7` | Handlers may take only player plus one request argument | **false** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteEvent) | Removed absolute argument count |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:8` | typeof alone is insufficient for range validation | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:8` | NaN and infinity pass basic number type tests | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:8` | math.isfinite rejects NaN and infinity | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:8` | String allowlists and length caps are always mandatory | **partly** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained as safe recommendation, not API requirement |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:8` | Instance class and ancestry can be checked | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:9` | Server verifies distance, ownership, cooldowns | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:10` | Per-player server throttles and departure cleanup | **true** | [Creator Hub](https://create.roblox.com/docs/scripting/security/client-server-boundary) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:11` | InvokeClient must never be called under any circumstances | **false** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/RemoteFunction) | Clarified authority/deadlock warning |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:12` | UnreliableRemoteEvent supports lossy transient updates | **true** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/UnreliableRemoteEvent) | Retained |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:12` | Class reference documents a universal 1000-byte limit | **unverifiable** | [Creator Hub](https://create.roblox.com/docs/reference/engine/classes/UnreliableRemoteEvent) | Removed hard-coded payload number |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:12` | RemoteEvent should carry messages needing reliable ordered delivery | **partly** | [Creator Hub](https://create.roblox.com/docs/scripting/events/remote) | Qualified connected transport and reconnection recovery |
| `star/skill_packs/roblox-secure-remotes/SKILL.md:13` | Receipt acknowledgment after persisted grant and ID | **partly** | [Creator Hub](https://create.roblox.com/docs/production/monetization/developer-products) | Specified atomic award/ID history |

## Scope, confidence and retesting

- This is a claim-by-claim audit, not a sample of model replies and not a claim of measurable STAR generation improvement. Only references on Creator Hub are used as factual authorities; recommendations (cooldowns, key prefix, cap/backoff policy) are distinguished from required engine behavior.
- The two packs with Luau code use three `~~~luau` examples each; the other two are prose-only. The regression test runs all six blocks through STAR's offline linter, confirms the original four pack files and source links exist, asserts audited corrections and bounded loader behavior, and checks `DEFAULT_ENABLED` remains unchanged.
- `roblox-secure-remotes` is **default-on**. Its corrections change injected prompt text, so the lead should decide whether to re-run the *independent evaluation gate* before merging. This audit itself does **not** run that gate.
- UnreliableRemoteEvent's current class API reference documents methods and events, but not a general 1000-byte payload ceiling; no numeric assertion is retained. Consider testing engine behavior and updated docs at release time.
- No Roblox Studio session, real DataStore request, server connection or held-out model-quality benchmark was performed.
