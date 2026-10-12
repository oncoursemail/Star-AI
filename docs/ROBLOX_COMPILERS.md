# Roblox compilers

## Player-data compiler

The pure-Python \`star.roblox_data_compiler\` module turns a JSON schema into a strict server Luau module and a Luau specification. It does not integrate with the desktop UI or contact Roblox when compiling.

Example schema:

\`\`\`json
{
  "version": 2,
  "store_name": "MyGameData",
  "autosave_seconds": 60,
  "lock_timeout_seconds": 120,
  "fields": {
    "Coins": {"type": "number", "default": 0, "min": 0, "max": 1000000, "leaderstats": true},
    "Nickname": {"type": "string", "default": "Player", "max": 32},
    "HasPass": {"type": "boolean", "default": false}
  },
  "migrations": [
    {"from": 1, "to": 2, "operations": [{"op": "rename", "field": "Money", "to": "Coins"}]}
  ]
}
\`\`\`

Use \`compile_file("schema.json", "generated")\` to write \`generated/PlayerData.luau\` and \`generated/PlayerData.spec.luau\`. Place the generated module under ServerScriptService and the spec next to it for a Luau test runner; the spec tests the exported pure \`migrate\` and \`validate\` functions. Alternatively call \`compile_schema(schema)\` for the two source strings.

Migrations must provide each sequential transition from version 1 through the declared version. The supported declarative operations are \`rename\`, \`set\`, and \`delete\`. Fields support numeric, string, and boolean defaults. Numeric bounds constrain values; string bounds constrain lengths. Invalid values are replaced with defaults and reported with \`warn\`.

The generated module acquires a DataStore session lock via \`UpdateAsync\`, refuses a live foreign lock, and releases its own lock on exit. Reads and writes retry under \`pcall\` with exponential backoff; saves use conditional \`UpdateAsync\`, never \`SetAsync\`. It mirrors fields explicitly marked \`leaderstats\`, autosaves, saves on player departure, and attempts to save within a 25-second shutdown window. Use \`Data.set(player, field, value)\` for writes so validation and leaderstats remain in sync. Roblox's shutdown time is finite; no DataStore-based implementation can guarantee a successful save when Roblox or DataStore service is unavailable. Test session-lock contention, load failures, migration failures, and shutdown using Roblox Studio before shipping.
