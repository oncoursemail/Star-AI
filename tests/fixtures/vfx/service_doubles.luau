-- Deterministic Lua 5.4/Roblox API compatibility doubles; NOT an engine simulator.
local now, serial = 0, 0
local jobs, objects, links, allTweens, warnings = {}, {}, {}, {}, {}
local services = 0
local failNewAt, failProperty, failDebris, failTweenCreate, failTweenPlay, failDelay, failConnect
local function enqueue(seconds, callback, kind)
    serial = serial + 1
    local job = {at = now + seconds, callback = callback, kind = kind, serial = serial}
    jobs[#jobs + 1] = job
    return job
end
task = {}
function task.delay(seconds, callback)
    if failDelay then failDelay = false; error("delay fault") end
    return enqueue(seconds, callback, "task")
end
function task.cancel(job)
    assert(not job.done, "cannot cancel an already completed thread")
    job.cancelled = true
end
local function advance(target)
    local count = 0
    while true do
        local nextJob
        for _, job in ipairs(jobs) do
            if not job.done and not job.cancelled and job.at <= target then
                if not nextJob or job.at < nextJob.at or (job.at == nextJob.at and job.serial < nextJob.serial) then nextJob = job end
            end
        end
        if not nextJob then break end
        now = nextJob.at
        nextJob.done = true
        nextJob.callback()
        count = count + 1
        assert(count < 10000, "unbounded scheduling")
    end
    now = target
end
function warn(message) warnings[#warnings + 1] = message end
local function signal()
    local signalLinks = {}
    return {
        Connect = function(self, callback)
            if failConnect then failConnect = false; error("connect fault") end
            local connection = {Connected = true, callback = callback}
            function connection:Disconnect() self.Connected = false end
            links[#links + 1] = connection
            signalLinks[#signalLinks + 1] = connection
            return connection
        end,
        Fire = function(self)
            for _, connection in ipairs(signalLinks) do
                if connection.Connected then connection.callback() end
            end
        end,
    }
end
local allowed = {
    ParticleEmitter = "Rate Lifetime Speed Rotation RotSpeed Size Color Transparency Acceleration SpreadAngle Drag VelocityInheritance LockedToPart EmissionDirection Orientation Brightness LightEmission LightInfluence Texture",
    Beam = "Attachment0 Attachment1 Width0 Width1 CurveSize0 CurveSize1 Segments FaceCamera TextureLength TextureSpeed TextureMode Color Transparency Brightness LightEmission LightInfluence Texture",
    Trail = "Attachment0 Attachment1 Lifetime MinLength MaxLength WidthScale FaceCamera TextureLength TextureMode Color Transparency LightEmission LightInfluence Texture",
    PointLight = "Brightness Range Color Shadows", Highlight = "FillColor OutlineColor FillTransparency OutlineTransparency DepthMode Adornee",
    Attachment = "Position", Part = "", Model = "", Folder = "",
}
local properties = {}
for cls, names in pairs(allowed) do
    properties[cls] = {Name = true, Parent = true, Enabled = cls ~= "Attachment" and cls ~= "Part" and cls ~= "Model" and cls ~= "Folder"}
    for key in string.gmatch(names, "%S+") do properties[cls][key] = true end
end
local methods = {}
function methods:IsA(cls) return self._class == cls or (cls == "BasePart" and self._class == "Part") end
function methods:Destroy()
    if self._destroyed then return end
    self._destroyed = true
    self.Destroying:Fire()
    for _, child in ipairs(self._children) do
        if child.Parent == self then child:Destroy() end
    end
    self.Parent = nil
end
function methods:Emit(count)
    assert(self._class == "ParticleEmitter" and self.Parent ~= nil, "Emit before parenting")
    assert(not self._destroyed and count >= 0 and count % 1 == 0)
    self._emitted = (self._emitted or 0) + count
end
local objectMT = {
    __index = function(self, key) return methods[key] or self._props[key] end,
    __newindex = function(self, key, value)
        if string.sub(key, 1, 1) == "_" then rawset(self, key, value); return end
        assert(properties[self._class][key], "invalid property " .. self._class .. "." .. key)
        assert(not self._destroyed or key == "Parent", "writing destroyed object")
        if failProperty == key then failProperty = nil; error("property fault") end
        if key == "Parent" and value then
            if self._class ~= "Attachment" and self._class ~= "Part" and self._class ~= "Model" then
                assert(self.Enabled == false, "visual must be configured disabled before parenting")
            end
            if self._class == "Attachment" then assert(value:IsA("BasePart")) end
            if self._class == "ParticleEmitter" or self._class == "PointLight" then
                assert(value:IsA("Attachment") and value.Parent:IsA("BasePart"))
            end
            if self._class == "Beam" or self._class == "Trail" then
                assert(self.Attachment0:IsA("Attachment") and self.Attachment1:IsA("Attachment"))
                assert(self.Attachment0.Parent:IsA("BasePart") and self.Attachment1.Parent:IsA("BasePart"))
            end
            value._children[#value._children + 1] = self
        end
        self._props[key] = value
    end,
}
Instance = {}
function Instance.new(cls)
    assert(allowed[cls], "unexpected class " .. tostring(cls))
    if failNewAt == #objects + 1 then failNewAt = nil; error("allocation fault") end
    local object = setmetatable({_class = cls, _props = {Enabled = true, Destroying = signal()}, _children = {}}, objectMT)
    objects[#objects + 1] = object
    return object
end
function typeof(value)
    if type(value) == "table" and value._class then return "Instance" end
    return type(value)
end
local function tuple(kind, ...)
    local value = {...}
    value.kind = kind
    return value
end
Color3 = {new = function(...) return tuple("Color3", ...) end}
Vector2 = {new = function(...) return tuple("Vector2", ...) end}
Vector3 = {new = function(...) return tuple("Vector3", ...) end}
NumberRange = {new = function(a, b) assert(a <= b); return tuple("NumberRange", a, b) end}
NumberSequenceKeypoint = {new = function(t, v, e) return tuple("NumberKeypoint", t, v, e) end}
ColorSequenceKeypoint = {new = function(t, c) assert(c.kind == "Color3"); return tuple("ColorKeypoint", t, c) end}
local function sequence(kind, points)
    assert(#points >= 2 and #points <= 20 and points[1][1] == 0 and points[#points][1] == 1)
    for i = 2, #points do assert(points[i][1] > points[i-1][1], "bad keypoint ordering") end
    return tuple(kind, points)
end
NumberSequence = {new = function(p) return sequence("NumberSequence", p) end}
ColorSequence = {new = function(p) return sequence("ColorSequence", p) end}
Enum = {}
for kind, names in pairs({NormalId="Top Bottom Front Back Left Right", ParticleOrientation="FacingCamera FacingCameraWorldUp VelocityParallel VelocityPerpendicular", TextureMode="Wrap Static Stretch", HighlightDepthMode="Occluded AlwaysOnTop", EasingStyle="Linear Sine Quad Cubic", EasingDirection="In Out InOut"}) do
    Enum[kind] = {}
    for name in string.gmatch(names, "%S+") do Enum[kind][name] = kind .. "." .. name end
end
TweenInfo = {new = function(duration, easing, direction, repeats, reverses, delay)
    assert(duration > 0 and repeats >= 0 and repeats % 1 == 0 and type(reverses) == "boolean" and delay == 0)
    return {duration = duration, easing = easing, direction = direction, repeats = repeats, reverses = reverses}
end}
local tweenService = {}
function tweenService:Create(object, info, goals)
    if failTweenCreate then failTweenCreate = false; error("tween creation fault") end
    local tween = {object = object, info = info, goals = goals}
    allTweens[#allTweens + 1] = tween
    function tween:Play()
        if failTweenPlay then failTweenPlay = false; error("tween play fault") end
        self.playing = true
        self.job = task.delay(info.duration * (info.reverses and 2 or 1) * (info.repeats + 1), function()
            self.playing = false
            if not info.reverses then
                for key, value in pairs(goals) do object[key] = value end
            end
        end)
    end
    function tween:Cancel()
        self.playing = false
        self.cancelled = true
        if self.job and not self.job.done then task.cancel(self.job) end
    end
    function tween:Destroy() self:Cancel(); self.destroyed = true end
    return tween
end
local debris = {}
function debris:AddItem(object, lifetime)
    if failDebris then failDebris = false; error("Debris fault") end
    assert(lifetime > 0 and lifetime <= 51)
    enqueue(lifetime, function() object:Destroy() end, "debris")
end
game = {GetService = function(self, name)
    services = services + 1
    assert(name == "Debris" or name == "TweenService", "unexpected service")
    return name == "Debris" and debris or tweenService
end}
local frameMT = {__mul = function(a, b)
    -- Enough for translation * rotation, the only composition generated here.
    return {a[1]+b[1], a[2]+b[2], a[3]+b[3], a[4]+b[4], a[5]+b[5], a[6]+b[6]}
end}
CFrame = {new = function(x, y, z) return setmetatable({x or 0, y or 0, z or 0, 0, 0, 0}, frameMT) end,
    Angles = function(x, y, z) return setmetatable({0, 0, 0, x, y, z}, frameMT) end}
local world = Instance.new("Folder")
local part = Instance.new("Part")
part.Parent = world
local baseline = #objects
local function find(cls)
    for i = baseline + 1, #objects do if objects[i]._class == cls then return objects[i] end end
end
local function clean()
    for i = baseline + 1, #objects do assert(objects[i]._destroyed, "leaked " .. objects[i]._class) end
    for _, c in ipairs(links) do assert(not c.Connected, "leaked connection") end
    for _, t in ipairs(allTweens) do assert(t.destroyed and not t.playing, "leaked tween") end
    for _, job in ipairs(jobs) do
        if job.kind == "task" then assert(job.done or job.cancelled, "leaked task") end
    end
end
