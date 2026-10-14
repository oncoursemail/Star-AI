---
name: roblox-game-math
description: Roblox gameplay math: vectors, dot and cross products, CFrame composition and look-at, interpolation and easing, critical springs, Bezier paths, projectiles, angle wrapping, ray geometry, weighted seeded randomness and fixed timesteps.
---
# Game math (Roblox)
State units, coordinate space, input domain and tolerance first. Examples assume finite, moderate inputs; radians and seconds. Keep numerical logic pure and test degenerate cases. Engine APIs below require Roblox; plain-table equivalents and additional formulas are in references/math.md. This pack is opt-in pending evaluation.

## Vectors and coordinate frames
Normalize before comparing direction; raw dot products depend on length. Dot gives projection/facing; cross is ordered (a cross b = -(b cross a)). Guard zero-length directions and collinear surface edges.
```luau
local function unit(v)
    if v.Magnitude <= 1e-12 then return nil end
    return v.Unit
end
local function inCone(forward, offset, halfAngle)
    if offset.Magnitude <= 1e-12 then return true end
    local f, d = unit(forward), unit(offset)
    return f ~= nil and f:Dot(d) >= math.cos(halfAngle)
end
local function surfaceNormal(edgeA, edgeB)
    return unit(edgeA:Cross(edgeB))
end
local function compose(parent, localPose) return parent * localPose end
local function relative(parent, worldPose) return parent:ToObjectSpace(worldPose) end
local function lookAt(eye, target, up)
    local f = unit(target-eye)
    if not f then return nil end
    local u = unit(up or Vector3.yAxis) or Vector3.yAxis
    if math.abs(f:Dot(u)) >= 0.999 then
        u = math.abs(f.Y) < 0.999 and Vector3.yAxis or Vector3.xAxis
    end
    return CFrame.lookAt(eye, target, u)
end
```
CFrame multiplication is noncommutative: parent * local applies the local transform in parent space. Points include translation; directions do not (PointToWorldSpace vs VectorToWorldSpace). LookVector is local -Z, not +Z; never normalize a zero look direction.

## Lerp, easing and springs
Scalar/Vector3 lerp may extrapolate; clamp t only when the contract requires it. Use CFrame:Lerp for frames, not componentwise Euler-angle lerp. For easing, clamp the input, not an overshooting output. Linear; Quad/Cubic/Quart/Quint; Sine/Exponential/Circular; Back/Bounce/Elastic have different timing and overshoot. In, Out and InOut are directions, not separate durations.
```luau
local function lerp(a,b,t)
    if t == 0 then return a end
    if t == 1 then return b end
    return a+(b-a)*t
end
local TweenService = game:GetService("TweenService")
local function easedLerp(a,b,t,style,direction)
    local u = TweenService:GetValue(math.clamp(t,0,1),style,direction)
    return lerp(a,b,u)
end
local function spring(x,v,target,omega,dt)
    assert(omega >= 0 and dt >= 0)
    local y = x-target
    local j = v+omega*y
    local e = math.exp(-omega*dt)
    return target+(y+j*dt)*e, (v-omega*j*dt)*e
end
```
The spring is the exact critical-damping solution for a constant target over dt; retain BOTH returned position and velocity. omega is radians/second (2*pi*frequencyHz). At omega=0 it is free motion. Subdividing a constant-target interval preserves the result; arbitrary moving targets need their own sampling policy. Initial velocity can still carry it past the target.

## Paths, gravity and angles
```luau
local function quadratic(a,b,c,t)
    local s=1-t
    return s*s*a+2*s*t*b+t*t*c
end
local function cubic(a,b,c,d,t)
    local s=1-t
    return s^3*a+3*s*s*t*b+3*s*t*t*c+t^3*d
end
local function projectile(p,v,g,t)
    assert(t >= 0)
    return p+v*t+0.5*g*t*t, v+g*t
end
local function launch(p,target,g,t)
    assert(t > 0)
    return (target-p-0.5*g*t*t)/t
end
local function wrap(a) return (a+math.pi)%(2*math.pi)-math.pi end
local function angleLerp(a,b,t)
    return wrap(a+wrap(b-a)*math.clamp(t,0,1))
end
```
Bezier t is not distance: equal t increments rarely give constant speed; use an arc-length lookup for that. Gravity is acceleration, e.g. Vector3.new(0,-workspace.Gravity,0), not velocity. wrap returns [-pi,pi); an exact pi tie turns negative. Use modulo, not math.fmod, for negative angles.

## Rays, randomness and fixed steps
A ray is o+t*d. d need not be unit length; t is distance only when d is unit. Workspace:Raycast takes a displacement (direction AND length): target-origin, not just its Unit. Test parallel, behind-origin, inside-sphere and segment-end cases.
```luau
local function rayPlane(o,d,p,n,maxT)
    assert(maxT >= 0)
    local denom=d:Dot(n)
    if math.abs(denom) <= 1e-12*d.Magnitude*n.Magnitude then return nil end
    local t=(p-o):Dot(n)/denom
    if t < 0 or t > maxT then return nil end
    return t,o+t*d
end
local function choose(weights,u)
    assert(u >= 0 and u < 1)
    local total,last=0,nil
    for i,w in ipairs(weights) do
        assert(w >= 0 and w < math.huge)
        total=total+w
        if w > 0 then last=i end
    end
    assert(total > 0 and total < math.huge)
    local target,sum=u*total,0
    for i,w in ipairs(weights) do
        sum=sum+w
        if target < sum then return i end
    end
    return last
end
local function advance(acc,dt,h,cap)
    assert(acc >= 0 and dt >= 0 and h > 0 and cap >= 0 and cap%1 == 0)
    local total=acc+dt
    local count=math.min(math.floor(total/h),cap)
    local rest=total-count*h
    return count,rest,math.min(rest/h,1)
end
```
Weights must be a dense nonempty array. A strict cumulative boundary prevents zero weights winning. Pass an injected draw u in [0,1); own one Random.new(seed) per stream rather than reseeding global math.random. Clamp a potentially inclusive engine draw with math.min(rng:NextNumber(),1-2^-53). Record seed AND draw order; seeds are not cryptographic security.
Feed measured dt into advance and simulate exactly count steps of h. Preserve rest across calls, including capped backlog; alpha is a clamped render fraction. Bound work, not elapsed time silently. Pause/discard policies must be explicit. Floating-point boundaries need stated tolerances; do not add an arbitrary epsilon that advances simulation early.
