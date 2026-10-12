# Pure numerical companions

These examples assume finite inputs of ordinary gameplay scale. Use radians,
seconds and consistent distance units. Table vectors use lowercase x/y/z;
Roblox Vector3 uses uppercase X/Y/Z and methods. Do not silently mix the two.
Functions return fresh tables and never write the input state. Each block is
independent; combine functions explicitly when building a module.

## Plain-table vectors and ordered rigid transforms

```luau
local function dot(a,b) return a.x*b.x+a.y*b.y+a.z*b.z end
local function cross(a,b)
    return {x=a.y*b.z-a.z*b.y,y=a.z*b.x-a.x*b.z,z=a.x*b.y-a.y*b.x}
end
local function unit(v)
    local n=math.sqrt(dot(v,v))
    if n <= 1e-12 then return nil end
    return {x=v.x/n,y=v.y/n,z=v.z/n}
end
local function projection(v,onto)
    local d=dot(onto,onto)
    if d <= 1e-24 then return nil end
    local s=dot(v,onto)/d
    return {x=onto.x*s,y=onto.y*s,z=onto.z*s}
end
```

For a row-major rotation r and a column vector v, multiply rows by v. A rigid
frame is {p=translation, r=nine rotation entries}. compose(a,b) means a*b:

```luau
local function compose(a,b)
    local r={}
    for i=0,2 do
        for j=1,3 do
            local s=0
            for k=1,3 do s=s+a.r[i*3+k]*b.r[(k-1)*3+j] end
            r[i*3+j]=s
        end
    end
    local q=b.p
    return {p={x=a.p.x+a.r[1]*q.x+a.r[2]*q.y+a.r[3]*q.z,
        y=a.p.y+a.r[4]*q.x+a.r[5]*q.y+a.r[6]*q.z,
        z=a.p.z+a.r[7]*q.x+a.r[8]*q.y+a.r[9]*q.z},r=r}
end
```

For a pure look-at frame use back=unit(eye-target),
right=unit(cross(up,back)), correctedUp=cross(back,right). Reject coincident
positions. Normalize supplied up first; for zero or nearly parallel up, select
world Y unless back is nearly vertical, then world X. Pack right/up/back as
rotation COLUMNS, not rows. The Roblox engine equivalent is CFrame.lookAt.

## Pure easing families

Clamp the parameter once. InOut reflects a half-sized In curve; it does not
apply In to the entire interval. Validate the selected family and direction.
Polynomial powers 2,3,4,5 correspond to quadratic,cubic,quartic,quintic.
Exponential curves need exact endpoint handling.

```luau
local function ease(t,family,direction,power)
    assert(family == "power" or family == "sine" or family == "expo")
    assert(direction == "in" or direction == "out" or direction == "inOut")
    if family == "power" then
        assert(power >= 2 and power <= 5 and power%1 == 0)
    end
    t=math.max(0,math.min(1,t))
    if t == 0 or t == 1 then return t end
    local function inward(x)
        if family == "power" then return x^power end
        if family == "sine" then return 1-math.cos(math.pi*x/2) end
        return 2^(10*(x-1))
    end
    if direction == "in" then return inward(t) end
    if direction == "out" then return 1-inward(1-t) end
    if t < 0.5 then return inward(2*t)/2 end
    return 1-inward(2*(1-t))/2
end
```

Back and Elastic intentionally overshoot; do not clamp their output. Bounce is
piecewise. When matching Roblox's exact curves, use TweenService:GetValue with
the documented enum rather than presenting a visually similar approximation
as the same easing. A spring is stateful motion, not an easing of elapsed time.

## Cubic tangents and projectile coordinates

The derivative of cubic(a,b,c,d,t) is
3*(1-t)^2*(b-a)+6*(1-t)*t*(c-b)+3*t^2*(d-c). Normalize it only when its magnitude
is nonzero. Use this tangent for an orientation, and explicitly choose a stable
up axis. To move at constant speed, accumulate sampled segment lengths, invert
the monotonic distance table, and then evaluate the curve at the resulting t.

For table vectors, apply the gravity formula independently to every component:

```luau
local function projectile(p0,v0,g,t)
    assert(t >= 0)
    local p,v={},{}
    for _,k in ipairs({"x","y","z"}) do
        p[k]=p0[k]+v0[k]*t+0.5*g[k]*t*t
        v[k]=v0[k]+g[k]*t
    end
    return p,v
end
```

Position/velocity formulas assume constant acceleration and no drag or collision.
Sweep the displacement between simulated positions to detect impacts; a point
sample can miss thin obstacles. An analytic trajectory alone does not reproduce
Roblox's complete physics simulation.

## Ray-sphere intersection with a nonunit direction

Solve a*t^2+2*b*t+c=0 with a=dot(d,d), b=dot(o-center,d),
c=dot(o-center,o-center)-radius^2. A sphere behind the ray is a miss even when the
infinite line intersects. Starting inside selects the exit root, not a negative
entry root. The compact formula is for ordinary scales; extreme coordinates
may need a cancellation-resistant quadratic solver and scaled arithmetic.

```luau
local function raySphere(o,d,center,radius)
    assert(radius >= 0)
    local function dot(a,b) return a.x*b.x+a.y*b.y+a.z*b.z end
    local a=dot(d,d)
    if a == 0 then return nil end
    local m={x=o.x-center.x,y=o.y-center.y,z=o.z-center.z}
    local b=dot(m,d)
    local disc=b*b-a*(dot(m,m)-radius*radius)
    if disc < 0 then return nil end
    local root=math.sqrt(disc)
    local first=(-b-root)/a
    if first >= 0 then return first end
    local last=(-b+root)/a
    if last >= 0 then return last end
    return nil
end
```

## Explicit portable seed state

Roblox Random objects isolate streams. To make a small, fully specified pure
numeric example independent of an engine RNG, keep this recurrence's state in
the caller. The product stays below 2^53, so the integer arithmetic is exact in
Luau's number representation. The algorithm is not cryptographically secure.

```luau
local function nextRandom(state)
    assert(state >= 1 and state <= 2147483646 and state%1 == 0)
    local nextState=(state*16807)%2147483647
    return nextState,(nextState-1)/2147483646
end
```

Use the returned u in choose(weights,u). Preserve returned nextState for the next
call; never reset it on each draw. Explicit draws make weighted-boundary tests
deterministic without relying on a statistical test or a wall-clock seed.

## Fixed-step ownership

Keep the accumulator in the simulation owner, not in a helper-local variable.
advance returns the count of steps to execute, remaining elapsed time and a
render alpha clamped to 1. It does not simulate or call RunService. With a cap,
remainder may exceed h: this is deliberate backlog. Discarding it changes the
simulation timeline. A pause/resume policy can drop backlog explicitly, but must
not be hidden in the arithmetic. Equal timesteps do not make engine physics or
network event ordering deterministic across devices.
