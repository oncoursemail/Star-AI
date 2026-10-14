# STAR and Roblox: API key, headless build-and-test, Studio build loop

STAR reaches Roblox by two official routes only: **Open Cloud** with an API key the owner creates, and the
**Studio MCP connector** that ships with Roblox Studio. STAR never signs in, never uses a cookie and never drives
the website or the game client.

Code: `star/roblox_cloud.py` (key, endpoints, approvals), `star/roblox_place.py` (place builder),
`star/roblox_pipeline.py` (headless pipeline), `star/studio_loop.py` and `star/policy.py` (Studio).
Facts in this file were read from the official documentation on 2026-10-11; the pages are linked per endpoint.

## 1. Connect the key

Settings > Roblox. Paste the Open Cloud API key and press **Save key**: it goes to the operating system's
credential store, never into `settings.json`, the chat or a log. Two other sources are accepted, for servers and
for keys longer than the credential store holds:

- a key file `.star/star.env` in the user's home folder, containing either `ROBLOX_OPEN_CLOUD_API_KEY=<key>` or
  just the key on one line (a line is split on its first `=` only when a known name stands before it, because
  keys end in `=` padding);
- the environment variable `ROBLOX_OPEN_CLOUD_API_KEY`.

Order: environment, then the credential store, then the file. The key is sent only to `https://apis.roblox.com`.

**Test** makes harmless calls only (the key describes itself; the key's own account and the chosen test experience
are read) and shows one of these states:

| State | Meaning |
|---|---|
| No key | Nothing is stored. |
| Valid | Roblox accepts the key and it has what the test pipeline needs. |
| Missing permission | Roblox accepts the key; the listed permissions must be added to it in the Creator Dashboard. |
| Revoked | Roblox no longer accepts it: revoked, regenerated or deleted; switched off; or expired (a key that is not used for 60 days expires). |
| Not a key | Roblox says the text is not an API key. |
| Unreachable | Roblox could not be reached; nothing is known yet. |

Each capability is listed with the permission it needs and how it was established: the HTTP status of a read call
where a harmless one exists, otherwise the key's own permission list. Publishing and running Luau have no
harmless call, so they are never tried by the Test button.

### Which permissions the key needs

Create the key on **STAR's own Roblox account**, restricted to the test experience, with only:

- `universe-places` : Write (publish a place file)
- `universe.place.luau-execution-session` : Read and Write (run a test, read its result and logs)
- optional: `universe-datastores.control` : List (list data store names)

A key with more than this works, and the Test button points out permission groups STAR never uses (for example
ones that can spend Robux). STAR has no code that calls them.

## 2. The test experience

Open Cloud can update an existing place; it cannot create an experience. The owner creates one:

1. Open Roblox Studio signed in as STAR's own Roblox account.
2. New > Baseplate, then File > Publish to Roblox, create a new experience and leave it **Private**.
3. On create.roblox.com > Creations, open the experience's `...` menu: Copy Universe ID and Copy Start Place ID.
4. Settings > Roblox > Test experience: enter both numbers and press **Use this experience**.

STAR accepts it only when Roblox confirms, at that moment and again before every write, that the experience is
owned by the account the key belongs to (not a group, not another user), is private, and is not on the
deny-list. The deny-list is in code (`DENIED_PLACE_IDS`, and `DENIED_UNIVERSE_IDS` for the experience that
place belongs to, so no other place of it can be chosen either) and wins over every setting.

## 3. What the model can do

Read tools, available as soon as a key is present: connection status, experience information, place information,
data store names of the test experience, and the status and result of an action.

Write tools do not write. `star_roblox_cloud_request_publish` (build a place from a folder of the workspace) and
`star_roblox_cloud_request_test` (run a Luau test) record a **pending action** with exactly what would be sent:
the built file's size, hash and file list, or the script (a waiting action shows the whole script, however
long). The owner approves or rejects each action under
Settings > Roblox > Actions waiting for you. An approved action is carried out once; an action expires after 15
minutes; at most five can wait. The model cannot approve: approval is an interface action, not a tool.
An approval is for the place the action named: if another test experience is chosen before the owner decides,
the action fails without sending anything.
An action ends as **done**, **failed** or **unknown**. "Unknown" means the request was sent and no answer came
back (a time-out, a dropped connection): Roblox may or may not have carried it out, and STAR says so instead of
calling it failed. A read that fails while a test is running is tried again until the deadline, and a finished
test keeps its result even when its log lines could not be fetched.
Publishing always creates a **saved** version (`versionType=Saved`), never a live one.

## 4. Headless pipeline (no Studio, runs on the PC or a Linux server)

    python -m star.roblox_pipeline --source examples/roblox-test-place          # build, check key and experience
    python -m star.roblox_pipeline --set-test-experience <universe> <place>
    python -m star.roblox_pipeline --source examples/roblox-test-place --publish-and-test

Steps: build the place file from source, check the key, verify the test experience, publish as a saved version,
run the test harness in exactly that version through Luau execution, wait for it, collect the returned value and
the logs. The run stops at the first step that cannot be done and prints what the owner has to do. On a server,
give the key through the environment variable or a key file (`STAR_ROBLOX_KEY_FILE=<path>`).

**Builder.** `star/roblox_place.py` writes the XML place format (`.rbxlx`) itself from a folder such as
`ServerScriptService/Main.server.luau`, `ReplicatedStorage/Shared/Catalog.luau`,
`StarterPlayer/StarterPlayerScripts/Hud.client.luau`; a folder with `init.luau` becomes that script. It covers
scripts and folders, which is what a server-side test needs. For places with geometry, UI or assets, Rojo can be
used instead (`--builder rojo`): version **7.7.1** is pinned with the SHA-256 of the official release archives
(`scripts/fetch_rojo.py` downloads from github.com/rojo-rbx/rojo/releases and refuses a file that does not
match). Nothing is downloaded unless the owner runs that script with `--yes`.

**Tests.** The harness (`TEST_HARNESS`) requires every ModuleScript named `*.spec` under
`ServerScriptService.Tests`; each returns a table of named functions. It returns `{passed, failed, cases}` and
also prints it on one marked log line, so the result can be read from either place.

No screenshots exist on this path: it tests logic on Roblox's servers, not how a place looks.

## 5. Open Cloud endpoints

Base `https://apis.roblox.com`, header `x-api-key`. Limit = requests per minute per API key owner.
STAR calls only the first table; the client refuses any path that is not in it.

| Call | Permission | Limit | Kind | Documentation | Notes |
|---|---|---|---|---|---|
| `POST /api-keys/v1/introspect` | none (the key describes itself) | not stated | read | [API keys](https://create.roblox.com/docs/cloud/auth/api-keys#post-api-keysv1introspect) | Body `{apiKey}`. Returns name, authorizedUserId, scopes, enabled, expired, expirationTimeUtc. |
| `GET /cloud/v2/users/{user}` | `user.advanced:read`, `user.social:read` for optional fields | 1000 | read | [Users](https://create.roblox.com/docs/cloud/reference/features/users) | Used once, for the name of the key's own account. |
| `GET /cloud/v2/universes/{universe}` | none listed | 100 | read | [Universes](https://create.roblox.com/docs/cloud/reference/features/universes) | Answers 200 for any universe with any valid key: ownership is the `user` field, not the status. |
| `GET /cloud/v2/universes/{universe}/places/{place}` | none listed | 100 | read | [Places](https://create.roblox.com/docs/cloud/reference/features/places) | |
| `GET /cloud/v2/universes/{universe}/data-stores` | `universe-datastores.control:list` | 1000000 | read | [Data and memory stores](https://create.roblox.com/docs/cloud/reference/features/storage) | Names only. |
| `POST /universes/v1/{universe}/places/{place}/versions` | `universe-places:write` | 30 | write | [Places](https://create.roblox.com/docs/cloud/reference/features/places), [guide](https://create.roblox.com/docs/cloud/guides/usage-place-publishing) | Query `versionType=Saved` or `Published`. Body is the place file: `application/xml` (.rbxlx) or `application/octet-stream` (.rbxl). Answers `{versionNumber}`. Not updated by this call: EditableImage, EditableMesh, PartOperation, SurfaceAppearance, BaseWrap. |
| `POST /cloud/v2/universes/{universe}/places/{place}/versions/{version}/luau-execution-session-tasks` | `universe.place.luau-execution-session:write` | 5 | write | [Luau execution](https://create.roblox.com/docs/cloud/reference/features/luau-execution) | Body `{script}`. Script and returned value 4 MB each; run time up to 5 minutes; at most 10 unfinished tasks per place (then 429); task information is kept 24 hours. |
| `POST /cloud/v2/universes/{universe}/places/{place}/luau-execution-session-tasks` | `universe.place.luau-execution-session:write` | 5 | write | same page | Without a version. The page does not say which version runs, so the pipeline always names the version it just published. |
| `GET /cloud/v2/universes/{universe}/places/{place}/versions/{version}/luau-execution-sessions/{session}/tasks/{task}` | `universe.place.luau-execution-session:read` or `:write` | 200 | read | same page | `state`: QUEUED, PROCESSING, CANCELLED, COMPLETE (then `output`), FAILED (then `error`). |
| `GET /cloud/v2/universes/{universe}/places/{place}/versions/{version}/luau-execution-sessions/{session}/tasks/{task}/logs` | `universe.place.luau-execution-session:read` or `:write` | 45 | read | same page | `view=FLAT` gives `messages`; `maxPageSize` up to 10000; 450 KB of logs are kept, oldest dropped first. |

Documented and recorded, never called by STAR today:

| Call | Permission | Limit | Kind | Documentation | Notes |
|---|---|---|---|---|---|
| `GET /cloud/v2/universes/{universe}/data-stores/{data_store}/entries` | `universe-datastores.objects:list` | 1000000 | read | [Data and memory stores](https://create.roblox.com/docs/cloud/reference/features/storage) | |
| `GET /cloud/v2/universes/{universe}/data-stores/{data_store}/entries/{entry}` | `universe-datastores.objects:read` | 1000000 | read | same page | POST, PATCH and DELETE need `objects:create`, `:update`, `:delete`. Ordered data stores and memory stores are on the same page. |
| `POST /cloud/v2/universes/{universe}:publishMessage` | `universe-messaging-service:publish` | 5000 | write | [Universes](https://create.roblox.com/docs/cloud/reference/features/universes), [guide](https://create.roblox.com/docs/cloud/guides/usage-messaging) | Body `{topic, message}`: topic 80 characters, message 1,024. Reaches live servers only; Open Cloud cannot subscribe. |
| `POST /cloud/v2/universes/{universe}:restartServers` | `universe:write` | 30 | write | [Universes](https://create.roblox.com/docs/cloud/reference/features/universes) | |
| `GET /assets/v1/assets/{asset}` | `asset:read` | 120 | read | [Assets](https://create.roblox.com/docs/cloud/reference/features/assets) | |
| `POST /assets/v1/assets` | `asset:read` and `asset:write` | 120 | write | same page | Answers an operation: `GET /assets/v1/operations/{operation}` (300). |
| `GET /cloud/v2/universes/{universe}/places/{place}/instances/{instance}:listChildren` | `universe.place.instance:read` | 45 | read | [Places](https://create.roblox.com/docs/cloud/reference/features/places) | Beta. |

Not in the documentation, so not in STAR: creating an experience through Open Cloud; listing the experiences of
an account with an API key (the listing endpoints documented need a signed-in browser session).

The documentation pages do not define the fields inside a task's `output` and `error`, nor the format of the
optional `timeout`. STAR therefore sends no `timeout`, passes `output` and `error` on as they arrive, and can
take the test result from the marked log line.

### What the service answered on 2026-10-11 (read calls only)

| Request | Status |
|---|---|
| Any resource call without a key | 403 |
| A resource call with text Roblox does not accept as a key | 401 |
| `introspect` with text that is not a key | 400 |
| `introspect` with a working key | 200 |
| `GET /cloud/v2/universes/{universe}` for an experience of another account | 200 |
| `GET .../data-stores` for an experience of another account | 401 |

## 6. Studio build loop

`star/studio.py` starts Studio's own MCP launcher and reads the connector's tool list at runtime.
`star/policy.py` sorts every tool; one it does not know is reported as new and never offered to a model, and
the guard in front of the connector (`GuardedStudio`) refuses it as well.
With the connector of 2026-10-11 (30 tools):

| Group | Tools | When a model gets them |
|---|---|---|
| read | list_roblox_studios, get_studio_state, search_game_tree, inspect_instance, script_read, script_search, script_grep, get_console_output, screen_capture, search_asset, skill, http_get | always (a screenshot may not move the camera in read-only mode) |
| edit | multi_edit, start_stop_play | sandbox only |
| playtest | character_navigation, user_keyboard_input, user_mouse_input | sandbox only |
| Luau | execute_luau (Edit DataModel) | sandbox only, and only with "Let STAR run Luau in the sandbox" |
| never | insert_asset, generate_material, generate_mesh, generate_procedural_model, generate_texture, segment_mesh, store_image, upload_image, subagent, wait_job_finished, list_plugin_guis, capture_plugin_gui | never |

**The sandbox rule is code** (`studio_loop.judge`). When STAR connects it asks the open place what it is, with a
fixed read-only question (`IDENTITY_PROBE`: PlaceId, GameId, CreatorId, CreatorType, script count). STAR edits
only when **Studio edits** is on and the place is

- a blank, unsaved place (PlaceId 0; no scripts, or marked by an earlier STAR edit), or
- a place owned by STAR's own Roblox account (the account of the connected API key), with
  **Also places of STAR's own account** switched on.

The question is asked again, and the rule applied again, before every script edit, every Luau edit, every
playtest start and before an undo: a turn can last minutes, and if another place has been opened in that Studio
window meanwhile, the change is refused and the rest of the turn only reads. (Stopping a playtest is never
refused.) That costs two extra read calls per change.

Everything else is read-only whatever the settings say: any other published place, an unsaved place that already
has scripts STAR did not make, a place STAR could not identify, and always the deny-list (by place id and by
the id of its experience, `game.GameId`). A place whose Studio title carries a deny-listed id is not even asked
the question.

**Edits are recorded.** Every edit goes through `GuardedStudio`: a script edit stores the script's earlier text; a
Luau edit is wrapped so that it is one undo step in Studio (`ChangeHistoryService`), and what it added is tagged
and listed. At the end of a turn the answer gets a block written by code: what was created or edited, and how to
undo it. Within the same session STAR can itself remove what it added and restore scripts it edited
(`GuardedStudio.undo`, used by the live check). The journal is not kept after the turn, so later the way back is
Studio's own undo (Ctrl+Z): a Luau edit is one undo step; whether a script edit made through the connector is
one undo step in Studio has not been checked in a real session. STAR never saves or publishes from Studio.

### The live check

No Studio session existed while this was built, so the loop was driven against `tests/studio_fake.py`, which
carries the connector's real tool list (compared tool by tool with the connector on 2026-10-11) and rejects any
call the real schemas would reject. With Studio open on a new Baseplate:

    python scripts/studio_live_loop.py            # reads only
    python scripts/studio_live_loop.py --edit     # build, playtest, read the error, fix, playtest, report, undo

Expected with `--edit`: every step ok, the first playtest shows the planted error, the second is clean, three
edits are reported, and after the undo the script and the two parts are gone.

**A Studio on another machine.** By default STAR starts the connector of the Studio on this PC. For a Studio that
runs elsewhere (for example on a second machine reached over SSH), set the environment variable
`STAR_STUDIO_MCP_COMMAND` to a JSON list: the program, then its arguments, for a command that speaks the
connector's MCP over standard input and output, for example
`["ssh", "-o", "BatchMode=yes", "<host>", "<launcher script on that machine>"]`. The sandbox rule is the same: the
place open there is asked what it is before anything is edited. The variable is read from the process environment
only, so a model cannot set it.

### The STAR Studio server (a Studio on Linux, signed in as STAR's own account)

STAR has its own Roblox Studio on a second machine: Studio under Wine (Vinegar) in a container, started by a
service on a virtual display, opened on **STAR Test Place** (experience 10770312935, place 128074805767678,
private). STAR reaches it as an MCP stdio command over SSH with the existing key; no network service is opened.

    python -m star.studio_remote --home <STAR data folder> --set-target server --set-command '["ssh", "-o", "BatchMode=yes", "<host>", "<launcher>"]'
    python -m star.studio_remote --home <STAR data folder> --test          # reads only: tools, instance, place, rule

- **Setting.** `star/studio_remote.py` keeps the target (`pc` = "Studio: this PC", `server` = "Studio: STAR Studio
  server") and the command in `<STAR data folder>/studio/remote.json`. The process environment
  (`STAR_STUDIO_MCP_COMMAND`) wins over the file. What the interface is given (`public`) never contains the
  command, only that one is stored and the name of its program. `test()` is the backend of a Test button; a
  failure reports its kind, never the command.
- **Narrower rule on the server.** `PinnedSession` sits under `GuardedStudio` and lets STAR change exactly one
  published place there, STAR Test Place, checked by both ids and never by name, or a blank unsaved place.
  Every Luau call carries the check on its first line, inside the same engine call, so it cannot run in a place
  that was opened a moment earlier. A script edit and a playtest start ask the place first and are refused on any
  other answer, on an error and on no answer. Reads and stopping a playtest pass. The general rule still applies
  on top: the place must belong to the account of the connected key.
- **Waiting for Studio.** A connector that has just started answers its tool list at once from a cache but lists
  no Studio for about two seconds, until Studio attaches. `wait_for_studio` waits (20 s at most) instead of
  reporting "no Studio". Every tool of the real connector needs `studio_id`.
- **The loop, run for real on 2026-10-11** (`scripts/studio_remote_loop.py`, through `star/studio.py`,
  `PinnedSession` and `GuardedStudio`): read the tree (21 instances); build a lobby (16 anchored parts with a
  spawn, two lights and a sign), a shop panel made of native layout objects (UIListLayout, UIPadding, UICorner,
  UIStroke, UISizeConstraint, automatic size), two RemoteEvents, a server script that validates purchase requests
  and a local script that sends them; playtest; read the output (one purchase accepted, three refused: unknown
  item, bad quantity, not enough coins; no errors); judge true captures of the display; fix what the first capture
  showed (the panel's lower third was empty, the walls were blown out, the camera did not show the spawn); undo
  through STAR's journal (the tree was back at 21 instances); build again; publish from Studio (a key press in
  the Studio window by the operator: STAR's code has no publish step); verify from outside
  with `scripts/studio_remote_verify.py`: the place's update time moved, a server-side Luau task ran in version 3
  instead of 2 and counted the 16 anchored parts, the spawn, both RemoteEvents, the panel and both scripts. The
  experience is still private.
- **Three things the real connector taught** (the stand-in did not): a script is created by `multi_edit` with a
  `game.`-prefixed path and a class name; Studio's output can still hold an earlier playtest's lines, word for
  word the same, so each playtest gets a run mark that the server script prints and only what follows it is
  judged; the journal is per session, so a later session removes earlier work by name (`--remove`), not by undo.
- **What a Luau task answers** (not on the documentation pages): `output` is `{"results": ["<returned value>"]}`.

**Why the connector must run inside Studio's own sandbox.** Vinegar is a flatpak app. A connector started with a
second `flatpak run` has its own process-id namespace but still reaches Studio's Wine server through the `/tmp`
that instances of one app share. The Wine server uses the process ids its clients report in its own namespace,
where the connector's id belongs to Vinegar: the first launch kills Vinegar, the second one takes the Wine server
down and Studio hangs for good ("Hang In Progress ... MainThreadHangs"). The launcher therefore enters the running
Studio's sandbox (`nsenter` into its user, mount and process-id namespaces, with Studio's own environment and Wine
build). Fifty launches since, no hang. The official MCP switch is the key `"mcp-server": {"enabled": true}` in
Studio's `AssistantSettings/<user id>.json`. A display without any window manager does not work either: Wine
leaves Studio's loading box on top and ignores a resize, so the service runs one window manager and no desktop.

**Restarts.** A watchdog restarts a Studio that cannot answer any more (its Wine server is gone, or its process
vanished) and reopens the test place; the rules that rely on a connector probe never run while a client session
holds the connector lock, and a restart keeps that lock so no connector starts in between. A Studio that was
stopped by force leaves an auto-recovery file, and the next start then shows a dialog ("Auto Recovery File Found")
that nobody answers: the service moves such files aside before it starts Studio (nothing is deleted). Edits that
were not published before a forced restart are therefore not in the reopened place: a loop that must survive a
restart publishes, or rebuilds from its own record.

## 7. What is not here

- Nothing is ever made public, bought or spent; there is no code path for it.
- No write goes anywhere but the one test experience. Messaging, data store writes and asset uploads are
  documented above and not built.
- The place builder covers scripts and folders only.
