--!strict
-- Generated typed client wrapper; Validators must be a sibling ModuleScript.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Validators = require(script.Parent.Validators)
local candidate = ReplicatedStorage:WaitForChild("StarRemotes", 10)
assert(candidate and candidate.ClassName == "Folder", "StarRemotes missing or wrong class")
local folder = candidate :: Folder
local function getRemote(name: string, className: string): Instance
    local remote = folder:WaitForChild(name, 10)
    assert(remote and remote.ClassName == className, "Remote missing or wrong class: " .. name)
    return remote
end
export type Client = {
    Buy: (quantity: number, item: "A" | "B") -> ...any,
    Look: (yaw: number) -> (),
    on_Updated: (callback: (ready: boolean) -> ()) -> RBXScriptConnection,
    on_Pulse: (callback: (strength: number) -> ()) -> RBXScriptConnection,
    Ping: () -> (),
}
local API = {}
local remote_Buy = getRemote("Buy", "RemoteFunction") :: RemoteFunction
function API.Buy(arg1: number, arg2: "A" | "B", ...: any): ...any
    assert(Validators.Buy(arg1, arg2, ...), "invalid outgoing arguments")
    return remote_Buy:InvokeServer(arg1, arg2, ...)
end
local remote_Look = getRemote("Look", "UnreliableRemoteEvent") :: UnreliableRemoteEvent
function API.Look(arg1: number, ...: any): ()
    assert(Validators.Look(arg1, ...), "invalid outgoing arguments")
    remote_Look:FireServer(arg1, ...)
end
local remote_Updated = getRemote("Updated", "RemoteEvent") :: RemoteEvent
function API.on_Updated(callback: (boolean) -> ()): RBXScriptConnection
    assert(typeof(callback) == "function", "callback must be a function")
    return remote_Updated.OnClientEvent:Connect(function(...: any)
        if not Validators.Updated(...) then return end
        callback(...)
    end)
end
local remote_Pulse = getRemote("Pulse", "UnreliableRemoteEvent") :: UnreliableRemoteEvent
function API.on_Pulse(callback: (number) -> ()): RBXScriptConnection
    assert(typeof(callback) == "function", "callback must be a function")
    return remote_Pulse.OnClientEvent:Connect(function(...: any)
        if not Validators.Pulse(...) then return end
        callback(...)
    end)
end
local remote_Ping = getRemote("Ping", "RemoteEvent") :: RemoteEvent
function API.Ping(...: any): ()
    assert(Validators.Ping(...), "invalid outgoing arguments")
    remote_Ping:FireServer(...)
end
return API :: Client
