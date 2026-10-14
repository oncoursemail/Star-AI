---
name: roblox-open-cloud
description: Opt-in Roblox Open Cloud integration recipes - secrets and scoped keys, live-ops messages into running servers, ConfigService values, and data store entries that external tools can safely read and edit, in typed Luau.
---
# roblox-open-cloud
## When to use
Use when tools outside the game (a support portal, live-ops dashboard, CI job or bot) must reach a Roblox game through Open Cloud: sending messages to live servers, editing data store entries, changing configs, or when game servers call Open Cloud through HttpService.

## Ten concrete rules
1. Open Cloud is the HTTP side of the same data stores, memory stores, messaging, configs and assets that game servers use; external tools always pass the universe ID. [S1][S2]
2. Never put an Open Cloud key in Luau source or anything a client can read. Game servers read it from the secrets store with HttpService:GetSecret; a Secret prints only its name. [S3]
3. Give each key the minimum scopes, restrict accepted IP addresses where possible and set an expiration date. [S4]
4. HttpService can call a subset of Open Cloud endpoints: only the x-api-key and content-type headers are allowed, the key must be a Secret, and each server gets 2,500 Open Cloud requests per minute. [S5]
5. External tools reach live servers through Open Cloud messaging; servers listen with MessagingService:SubscribeAsync. Messages are at most 1 KiB and topics 80 characters, with limits shared by both APIs. [S6][S7]
6. Treat every message and every externally edited entry as hostile: decode JSON in pcall, allow-list actions and check types, sizes and NaN. [S6][S8]
7. Open Cloud serializes entries as JSON and returns non-finite numbers as tagged objects, so store finite numbers in plain tables. [S2]
8. Return user IDs from UpdateAsync (keep info:GetUserIds and GetMetadata unless you change them) and put the user ID in key names, so right-to-be-forgotten requests find the data. [S9][S10]
9. ConfigService runs on the server only; snapshots do not update by themselves: Refresh on UpdateAvailable, and keep defaults for when GetConfigAsync errors. [S11]
10. External callers must handle HTTP 429: wait for retry-after, otherwise back off exponentially. [S12]

## Three correct Luau examples
All three are server Scripts.

### Example 1: live-ops messages from an external dashboard
~~~luau
--!strict
local HttpService = game:GetService("HttpService")
local MessagingService = game:GetService("MessagingService")
local Players = game:GetService("Players")

local actions: { [string]: (payload: { [string]: any }) -> () } = {
	announce = function(payload)
		if typeof(payload.text) == "string" and #payload.text <= 200 then
			workspace:SetAttribute("Announcement", payload.text)
		end
	end,
	kick = function(payload)
		local id = payload.userId
		local player = if typeof(id) == "number" then Players:GetPlayerByUserId(id) else nil
		if player then
			player:Kick("Removed by a moderator")
		end
	end,
}

local function onMessage(message: { Data: any, Sent: number })
	local data = message.Data
	if typeof(data) ~= "string" or #data > 1024 then
		return
	end
	local ok, payload = pcall(HttpService.JSONDecode, HttpService, data)
	if ok and typeof(payload) == "table" and typeof(payload.action) == "string" then
		local action = actions[payload.action]
		if action then
			action(payload)
		end
	end
end

local ok, err = pcall(MessagingService.SubscribeAsync, MessagingService, "LiveOps", onMessage)
if not ok then
	warn("LiveOps subscription failed", err)
end
~~~
Unknown actions are ignored, so a leaked dashboard cannot run arbitrary commands. [S6][S7][S8]

### Example 2: live configs with safe defaults
~~~luau
--!strict
local ConfigService = game:GetService("ConfigService")
local live = { bossHealth = 500, eventEnabled = false }

local function apply(snapshot: ConfigSnapshot)
	local health = snapshot:GetValue("bossHealth")
	live.bossHealth = if typeof(health) == "number" and health > 0 and health < 1e6 then health else 500
	local enabled = snapshot:GetValue("eventEnabled")
	live.eventEnabled = enabled == true
	workspace:SetAttribute("EventEnabled", live.eventEnabled)
end

local ok, snapshot = pcall(ConfigService.GetConfigAsync, ConfigService)
if ok then
	apply(snapshot)
	snapshot.UpdateAvailable:Connect(function()
		snapshot:Refresh()
	end)
	snapshot:GetValueChangedSignal("bossHealth"):Connect(function()
		apply(snapshot)
	end)
	snapshot:GetValueChangedSignal("eventEnabled"):Connect(function()
		apply(snapshot)
	end)
else
	warn("Configs unavailable, using defaults", snapshot)
end

return live
~~~
Values changed through Creator Hub or the Open Cloud configs API arrive without a restart. [S11]

### Example 3: entries that support tools can edit safely
~~~luau
--!strict
local DataStoreService = game:GetService("DataStoreService")
local store = DataStoreService:GetDataStore("Inventory")
type Inventory = { schema: number, coins: number, items: { string } }

local function clean(value: unknown): Inventory
	local raw = (if typeof(value) == "table" then value else {}) :: { [string]: any }
	local coins = raw.coins
	local safeCoins = if typeof(coins) == "number" and coins == coins then math.clamp(math.floor(coins), 0, 1e9) else 0
	local items: { string } = {}
	if typeof(raw.items) == "table" then
		for _, item in raw.items do
			if typeof(item) == "string" and #item <= 50 then
				table.insert(items, item)
			end
		end
	end
	return { schema = 2, coins = safeCoins, items = items }
end

local function save(userId: number, inventory: Inventory): boolean
	local ok = pcall(store.UpdateAsync, store, "user_" .. userId, function(_: any, info: DataStoreKeyInfo?)
		local metadata = if info then info:GetMetadata() else {}
		return clean(inventory), { userId }, metadata
	end)
	return ok
end

return { clean = clean, save = save }
~~~
Load with clean(value) after GetAsync in pcall, because a portal may have written the entry. [S2][S9][S10]

## Three common mistakes
1. Pasting an Open Cloud key into a script, a client or a repository. [S3][S4]
2. Running whatever a message says without decoding in pcall and allow-listing. [S6][S8]
3. Trusting data store entries edited outside the game, or saving NaN or infinity. [S2]

## Checklist
- [ ] Keys live in the secrets store with minimum scopes.
- [ ] Message handlers decode in pcall and allow-list actions.
- [ ] Entries are plain JSON-safe tables with finite numbers.
- [ ] Keys carry user IDs for right-to-be-forgotten.
- [ ] Config reads have defaults; external callers back off on 429.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S12]. Names and limits are illustrative.
