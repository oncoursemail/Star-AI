-- Deterministic cooperative scheduler and Roblox service doubles for generated
-- server execution. This is a test harness, not an engine implementation.
local typeof = type
local now, sequence = 0, 0
local ready, timers, live = {}, {}, {}
local immediateSignals = false
local task = {}
local function enqueue(thread, arguments)
    ready[#ready + 1] = { thread = thread, arguments = arguments or table.pack() }
end
local function resumeThread(thread, arguments)
    if coroutine.status(thread) == "dead" then return end
    local ok, failure = coroutine.resume(thread, table.unpack(arguments, 1, arguments.n))
    assert(ok, failure)
    if coroutine.status(thread) == "dead" then live[thread] = nil end
end
function task.defer(callback)
    local thread = coroutine.create(callback)
    live[thread] = true
    enqueue(thread)
    return thread
end
function task.delay(seconds, callback)
    local thread = coroutine.create(callback)
    live[thread] = true
    sequence = sequence + 1
    timers[thread] = { at = now + seconds, order = sequence }
    return thread
end
function task.cancel(thread)
    assert(thread ~= coroutine.running(), "cannot cancel the running thread")
    timers[thread] = nil
    live[thread] = nil
    coroutine.close(thread)
end
function task.wait(seconds)
    local thread = coroutine.running()
    sequence = sequence + 1
    timers[thread] = { at = now + (seconds or 0), order = sequence }
    coroutine.yield()
end
local function tick(at)
    if at ~= nil then now = at end
    local iterations = 0
    while true do
        local earliest, chosen
        for thread, timer in pairs(timers) do
            if timer.at <= now and (not earliest or timer.at < earliest.at or
                (timer.at == earliest.at and timer.order < earliest.order)) then
                earliest, chosen = timer, thread
            end
        end
        if chosen then
            timers[chosen] = nil
            enqueue(chosen)
        end
        local entry = table.remove(ready, 1)
        if not entry then break end
        resumeThread(entry.thread, entry.arguments)
        iterations = iterations + 1
        assert(iterations < 10000, "scheduler did not settle")
    end
end
local function alive()
    local count = 0
    for _ in pairs(live) do count = count + 1 end
    return count
end
local function signal()
    local result = { listeners = {}, waiters = {} }
    function result:Connect(callback)
        local connection = { Connected = true }
        function connection:Disconnect() self.Connected = false end
        self.listeners[#self.listeners + 1] = { callback = callback, connection = connection }
        return connection
    end
    function result:Wait()
        self.waiters[#self.waiters + 1] = coroutine.running()
        return coroutine.yield()
    end
    function result:Fire(...)
        local arguments = table.pack(...)
        for _, listener in ipairs(self.listeners) do
            if listener.connection.Connected then
                local callback = listener.callback
                task.defer(function() callback(table.unpack(arguments, 1, arguments.n)) end)
            end
        end
        local waiters = self.waiters
        self.waiters = {}
        for _, thread in ipairs(waiters) do
            if immediateSignals then resumeThread(thread, arguments) else enqueue(thread, arguments) end
        end
    end
    return result
end
local created, bindableAlive = {}, 0
local Instance = {}
function Instance.new(className)
    created[className] = (created[className] or 0) + 1
    local properties = { ClassName = className, Name = className, children = {}, sent = {} }
    local object = setmetatable({}, {
        __index = properties,
        __newindex = function(_, key, value)
            if key == "Parent" then
                if properties.Parent then
                    for index, child in ipairs(properties.Parent.children) do
                        if child == properties.self then table.remove(properties.Parent.children, index); break end
                    end
                end
                if value then value.children[#value.children + 1] = properties.self end
            end
            properties[key] = value
        end,
    })
    properties.self = object
    function object:FindFirstChild(name)
        for _, child in ipairs(self.children) do if child.Name == name then return child end end
        return nil
    end
    function object:WaitForChild(name, timeout)
        assert(timeout == 10, "unbounded client lookup")
        return self:FindFirstChild(name)
    end
    function object:IsA(name) return self.ClassName == name end
    function object:Destroy()
        assert(not self.destroyed, "double destroy")
        self.destroyed = true
        if self.ClassName == "BindableEvent" then bindableAlive = bindableAlive - 1 end
        self.Parent = nil
    end
    if className == "BindableEvent" then
        bindableAlive = bindableAlive + 1
        object.Event = signal()
        function object:Fire(...)
            assert(not self.destroyed, "firing destroyed event")
            self.Event:Fire(...)
        end
    elseif className == "RemoteEvent" or className == "UnreliableRemoteEvent" then
        object.OnServerEvent, object.OnClientEvent = signal(), signal()
        function object:FireClient(player, ...)
            self.sent[#self.sent + 1] = table.pack(player, ...)
            self.OnClientEvent:Fire(...)
        end
        function object:FireServer(...)
            self.sent[#self.sent + 1] = table.pack(...)
        end
    elseif className == "RemoteFunction" then
        function object:InvokeServer(...) return self.OnServerInvoke(...) end
    end
    return object
end
local Players = Instance.new("Players")
Players.PlayerRemoving = signal()
local ReplicatedStorage = Instance.new("ReplicatedStorage")
local services = { Players = Players, ReplicatedStorage = ReplicatedStorage }
local game = {}
function game:GetService(name) return assert(services[name]) end
local os = { clock = function() return now end }
local function player()
    local value = Instance.new("Player")
    value.Parent = Players
    return value
end
local function invoke(remote, who, ...)
    local arguments = table.pack(...)
    local result = {}
    task.defer(function()
        result.values = table.pack(remote.OnServerInvoke(who, table.unpack(arguments, 1, arguments.n)))
    end)
    tick()
    return result
end
