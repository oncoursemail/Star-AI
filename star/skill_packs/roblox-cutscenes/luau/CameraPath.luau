--!strict
-- CameraPath (shared ModuleScript): camera moves for cutscenes.
--   * curves: Catmull-Rom (passes through every point; good for flythroughs), Bezier (points are control points;
--     one smooth sweep), linear;
--   * arc-length parameterisation: a lookup table maps "fraction of the distance" to the curve parameter, so the
--     camera's SPEED comes only from the easing curve, not from how far apart the points happen to be;
--   * easing through TweenService:GetValue (the same curves as tweens: Sine, Quad, Cubic, Quint, Back, ...);
--   * the look target, FOV and roll are interpolated with the same eased alpha.
-- Nothing here touches the camera: `sample` returns (CFrame, fov) and the player applies it every frame.

local TweenService = game:GetService("TweenService")

local Types = require(script.Parent:WaitForChild("CutsceneTypes"))

export type Path = {
	shot: Types.Shot,
	sample: (self: Path, t: number, origin: CFrame, actorHead: ((name: string) -> Vector3?)?) -> (CFrame, number),
	alpha: (self: Path, t: number) -> number,
	position: (self: Path, alpha: number) -> Vector3,
	_table: { number },
	_points: { Vector3 },
	_look: { Vector3 }?,
}

local CameraPath = {}
CameraPath.__index = CameraPath
CameraPath.SAMPLES = 48

function CameraPath.ease(alpha: number, style: string?, direction: string?): number
	local a = math.clamp(alpha, 0, 1)
	local s = Enum.EasingStyle.Sine
	local d = Enum.EasingDirection.InOut
	if style then
		local ok, item = pcall(function()
			return (Enum.EasingStyle :: any)[style :: string]
		end)
		if ok and item then
			s = item
		end
	end
	if direction then
		local ok, item = pcall(function()
			return (Enum.EasingDirection :: any)[direction :: string]
		end)
		if ok and item then
			d = item
		end
	end
	return TweenService:GetValue(a, s, d)
end

-- Uniform Catmull-Rom through p1..p2 with neighbours p0 and p3.
local function catmull(p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, u: number): Vector3
	local u2 = u * u
	local u3 = u2 * u
	return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u3)
end

function CameraPath.catmullRom(points: { Vector3 }, u: number): Vector3
	local n = #points
	if n == 1 then
		return points[1]
	end
	local segments = n - 1
	local x = math.clamp(u, 0, 1) * segments
	local i = math.min(math.floor(x), segments - 1)
	local f = x - i
	local p1 = points[i + 1]
	local p2 = points[i + 2]
	local p0 = points[i] or (2 * p1 - p2) -- mirrored end tangents
	local p3 = points[i + 3] or (2 * p2 - p1)
	return catmull(p0, p1, p2, p3, f)
end

-- De Casteljau for any number of control points.
function CameraPath.bezier(points: { Vector3 }, u: number): Vector3
	local work = table.clone(points)
	local t = math.clamp(u, 0, 1)
	for level = #work - 1, 1, -1 do
		for i = 1, level do
			work[i] = work[i]:Lerp(work[i + 1], t)
		end
	end
	return work[1]
end

function CameraPath.linear(points: { Vector3 }, u: number): Vector3
	local n = #points
	if n == 1 then
		return points[1]
	end
	local x = math.clamp(u, 0, 1) * (n - 1)
	local i = math.min(math.floor(x), n - 2)
	return points[i + 1]:Lerp(points[i + 2], x - i)
end

local function curveFn(name: string?): ({ Vector3 }, number) -> Vector3
	if name == "bezier" then
		return CameraPath.bezier
	elseif name == "linear" then
		return CameraPath.linear
	end
	return CameraPath.catmullRom
end

-- Cumulative arc length at SAMPLES+1 evenly spaced parameters, normalised to 0..1.
local function arcTable(points: { Vector3 }, fn: ({ Vector3 }, number) -> Vector3): { number }
	local out = { 0 }
	local total = 0
	local previous = fn(points, 0)
	for i = 1, CameraPath.SAMPLES do
		local p = fn(points, i / CameraPath.SAMPLES)
		total += (p - previous).Magnitude
		previous = p
		out[i + 1] = total
	end
	for i = 1, #out do
		out[i] = if total > 1e-6 then out[i] / total else (i - 1) / CameraPath.SAMPLES
	end
	return out
end

-- Distance fraction (0..1) -> curve parameter (0..1), by binary search in the arc table.
local function toParameter(arc: { number }, s: number): number
	local lo, hi = 1, #arc
	while hi - lo > 1 do
		local mid = (lo + hi) // 2
		if arc[mid] < s then
			lo = mid
		else
			hi = mid
		end
	end
	local span = arc[hi] - arc[lo]
	local f = if span > 1e-9 then (s - arc[lo]) / span else 0
	return ((lo - 1) + f) / CameraPath.SAMPLES
end

function CameraPath.new(shot: Types.Shot): Path
	local fn = curveFn(shot.curve)
	local self = setmetatable({}, CameraPath) :: any
	self.shot = shot
	self._points = shot.points
	self._look = shot.look
	self._fn = fn
	self._table = arcTable(shot.points, fn)
	return self :: Path
end

-- Eased alpha (0..1) for a time t (seconds from the cutscene start) inside this shot.
function CameraPath.alpha(self: any, t: number): number
	local shot: Types.Shot = self.shot
	local raw = (t - shot.start) / shot.duration
	local ease = shot.ease
	return CameraPath.ease(raw, ease and ease.style, ease and ease.direction)
end

-- Camera position (local space) at an eased alpha: constant speed along the curve for linear alpha.
function CameraPath.position(self: any, alpha: number): Vector3
	return self._fn(self._points, toParameter(self._table, math.clamp(alpha, 0, 1)))
end

local function lerpList(values: { number }?, alpha: number, default: number): number
	if not values or #values == 0 then
		return default
	end
	if #values == 1 then
		return values[1]
	end
	local x = alpha * (#values - 1)
	local i = math.min(math.floor(x), #values - 2)
	return values[i + 1] + (values[i + 2] - values[i + 1]) * (x - i)
end

-- (camera CFrame in world space, field of view) at time t. `actorHead` resolves lookActor to a world position.
function CameraPath.sample(self: any, t: number, origin: CFrame, actorHead: ((name: string) -> Vector3?)?): (CFrame, number)
	local shot: Types.Shot = self.shot
	local alpha = CameraPath.alpha(self, t)
	local eye = origin:PointToWorldSpace(CameraPath.position(self, alpha))
	local target: Vector3? = nil
	if shot.lookActor and actorHead then
		local head = actorHead(shot.lookActor)
		if head then
			target = head + origin:VectorToWorldSpace(shot.lookOffset or Vector3.zero)
		end
	end
	if not target then
		local look = self._look
		if look then
			target = origin:PointToWorldSpace(CameraPath.linear(look, alpha))
		else
			target = eye + origin.LookVector
		end
	end
	local at = target :: Vector3
	if (at - eye).Magnitude < 1e-3 then
		at = eye + origin.LookVector
	end
	local cf = CFrame.lookAt(eye, at)
	local roll = shot.roll
	if roll and roll ~= 0 then
		cf *= CFrame.Angles(0, 0, math.rad(roll))
	end
	return cf, lerpList(shot.fov, alpha, 70)
end

return CameraPath
