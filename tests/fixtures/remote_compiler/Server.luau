-- Generated server ModuleScript; require one copy in server code.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Validators = require(script.Parent.Validators)
local RateLimiter = require(script.Parent.RateLimiter)
local limiter = RateLimiter.new()
local folder = ReplicatedStorage:FindFirstChild("StarRemotes")
if folder then
    assert(folder.ClassName == "Folder", "StarRemotes must be a Folder")
else
    folder = Instance.new("Folder")
    folder.Name = "StarRemotes"
    folder.Parent = ReplicatedStorage
end
local definitions = {
    { name = "Buy", class = "RemoteFunction" },
    { name = "Look", class = "UnreliableRemoteEvent" },
    { name = "Updated", class = "RemoteEvent" },
    { name = "Pulse", class = "UnreliableRemoteEvent" },
    { name = "Ping", class = "RemoteEvent" },
}
local remotes, handlers, incoming = {}, {}, {}
-- No yields in remote creation/binding: each instance is created or reused once.
for _, definition in ipairs(definitions) do
    local remote = folder:FindFirstChild(definition.name)
    if remote then
        assert(remote.ClassName == definition.class, "Remote class mismatch: " .. definition.name)
    else
        remote = Instance.new(definition.class)
        remote.Name = definition.name
        remote.Parent = folder
    end
    remotes[definition.name] = remote
end
-- Only dispatch functions below can enter this private handler runner.
-- The timer is armed before the worker starts. Cooperative scheduling cannot
-- preempt a CPU-bound handler; handlers must not block the scheduler.
local pending = {}
local function invokeBounded(handler, player, ...)
    local arguments = table.pack(...)
    local finished = Instance.new("BindableEvent")
    local request = { done = false }
    local requests = pending[player]
    if not requests then
        requests = {}
        pending[player] = requests
    end
    requests[request] = true
    local worker, timer
    local function settle(result)
        if request.done then return end
        request.done = true
        request.result = result
        finished:Fire()
    end
    request.abort = function(reason)
        if request.done then return end
        -- Cancel the suspended worker before waking the caller.
        if worker and coroutine.status(worker) == "suspended" then
            pcall(task.cancel, worker)
        end
        settle(table.pack(nil, reason))
    end
    timer = task.delay(5, function()
        timer = nil
        request.abort("timeout")
    end)
    worker = task.defer(function()
        local result = table.pack(pcall(handler, player, table.unpack(arguments, 1, arguments.n)))
        if result[1] then
            settle(table.pack(table.unpack(result, 2, result.n)))
        else
            settle(table.pack(nil, "handler_error"))
        end
    end)
    if not request.done then finished.Event:Wait() end
    if timer then pcall(task.cancel, timer) end
    requests[request] = nil
    if next(requests) == nil and pending[player] == requests then
        pending[player] = nil
    end
    finished:Destroy()
    return table.unpack(request.result, 1, request.result.n)
end
local departing = setmetatable({}, { __mode = "k" })
Players.PlayerRemoving:Connect(function(player)
    departing[player] = true
    limiter:remove(player)
    local requests = pending[player]
    pending[player] = nil
    if requests then
        for request in pairs(requests) do
            request.abort("player_left")
        end
    end
end)
incoming.Buy = true
local function dispatch_Buy(player, ...)
    if not Validators.Buy(...) then return nil, "invalid_arguments" end
    if departing[player] or player.Parent ~= Players then return nil, "player_left" end
    if not limiter:allow(player, "Buy", 2, os.clock()) then return nil, "rate_limited" end
    local handler = handlers.Buy
    if not handler then return nil, "no_handler" end
    return invokeBounded(handler, player, ...)
end
remotes.Buy.OnServerInvoke = dispatch_Buy
incoming.Look = true
local function dispatch_Look(player, ...)
    if not Validators.Look(...) then return nil, "invalid_arguments" end
    if departing[player] or player.Parent ~= Players then return nil, "player_left" end
    if not limiter:allow(player, "Look", 1, os.clock()) then return nil, "rate_limited" end
    local handler = handlers.Look
    if not handler then return nil, "no_handler" end
    return invokeBounded(handler, player, ...)
end
remotes.Look.OnServerEvent:Connect(dispatch_Look)
incoming.Ping = true
local function dispatch_Ping(player, ...)
    if not Validators.Ping(...) then return nil, "invalid_arguments" end
    if departing[player] or player.Parent ~= Players then return nil, "player_left" end
    if not limiter:allow(player, "Ping", 1, os.clock()) then return nil, "rate_limited" end
    local handler = handlers.Ping
    if not handler then return nil, "no_handler" end
    return invokeBounded(handler, player, ...)
end
remotes.Ping.OnServerEvent:Connect(dispatch_Ping)
local API = {}
function API.on(name, callback)
    assert(incoming[name] == true, "unknown incoming message")
    assert(typeof(callback) == "function", "callback must be a function")
    assert(handlers[name] == nil, "handler already registered")
    handlers[name] = callback
end
function API.Updated(player, ...)
    if not Validators.Updated(...) then return nil, "invalid_arguments" end
    if departing[player] or player.Parent ~= Players then return nil, "player_left" end
    if not limiter:allow(player, "Updated", 2, os.clock()) then return nil, "rate_limited" end
    remotes.Updated:FireClient(player, ...)
    return true
end
function API.Pulse(player, ...)
    if not Validators.Pulse(...) then return nil, "invalid_arguments" end
    if departing[player] or player.Parent ~= Players then return nil, "player_left" end
    if not limiter:allow(player, "Pulse", 1, os.clock()) then return nil, "rate_limited" end
    remotes.Pulse:FireClient(player, ...)
    return true
end
return API
