# Lessons: wrong logic and missing required features

**Status:** standalone review material, not loaded into STAR by default. These 12 examples are *illustrative* minimal patterns reconstructed from failed checks; they are **not verbatim model answers**. Stored-result lines support the observed failures; linked official Creator Hub/Luau documentation supports the API contract, while task-specific invariants are verified by the recorded evaluation assertions. Neither a static regex hit nor an example proves live Studio behavior.

The baseline failure ledger ([report](../FAILURE_LEDGER.md)) records 15 wrong-logic and 25 required-feature-missing failed attempts across repeated evaluation runs; it does not establish 40 independent root causes. Each entry below is grounded in an explicit stored failed check and a relevant official API/scripting reference. No unproven claims about the model's intent were included.

## 1. Player removal leaves a stale count (NET-03; wrong logic)

**Mistake:** PlayerRemoving disconnects the player but does not decrement trackedCount.

**Bad (illustrative):**

~~~luau
tracking[player] = nil -- trackedCount stays too high
~~~

**Corrected pattern:**

~~~luau
if tracking[player] then
    tracking[player] = nil
    trackedCount -= 1
end
~~~

**Rule:** Whenever one tracked player leaves, update membership and count together.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L417) (task NET-03, failed check at line 417); [official API/scripting reference](https://create.roblox.com/docs/reference/engine/classes/Players).

## 2. A rate limit rejects an allowed transition incorrectly (NET-10; wrong logic)

**Mistake:** The sixth request in a one-second window modifies WalkSpeed anyway, or sprint has no stamina guard.

**Bad (illustrative):**

~~~luau
humanoid.WalkSpeed = requestedSpeed -- trusts client
~~~

**Corrected pattern:**

~~~luau
if #recentRequests >= 5 then return end
if mode == "sprint" and stamina > 0 then
    humanoid.WalkSpeed = 24
end
~~~

**Rule:** Enforce server-owned rate limits before state mutation and test each boundary.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L1645) (task NET-10, failed check at line 1645); [official API/scripting reference](https://create.roblox.com/docs/scripting/security/client-server-boundary).

## 3. Released pooled objects are not reused (PERF-03; wrong logic)

**Mistake:** Every shot creates a new instance after a part has been returned to the pool.

**Bad (illustrative):**

~~~luau
function Pool.get()
    return Instance.new("Part")
end
~~~

**Corrected pattern:**

~~~luau
function Pool.get()
    return table.remove(free) or Instance.new("Part")
end
~~~

**Rule:** Test pool reuse across acquire/release/acquire, not only initial allocation.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L2338) (task PERF-03, failed check at line 2338); [official API/scripting reference](https://create.roblox.com/docs/performance-optimization/improve).

## 4. Double releases corrupt an effect pool (VFX-03; wrong logic)

**Mistake:** Calling release twice subtracts twice and admits an unowned emitter.

**Bad (illustrative):**

~~~luau
function release(item)
    activeCount -= 1
    table.insert(free, item)
end
~~~

**Corrected pattern:**

~~~luau
function release(item)
    if not active[item] then return end
    active[item] = nil
    activeCount -= 1
    table.insert(free, item)
end
~~~

**Rule:** Make release idempotent and ignore effects the pool does not own.

**Evidence:** [Recorded failure](../../evals/results/baseline-creation-v1.json#L667) (task VFX-03, failed check at line 667); [official API/scripting reference](https://create.roblox.com/docs/effects/particle-emitters).

## 5. Combo buffer advances before recovery ends (ANI-08; wrong logic)

**Mistake:** A buffered attack skips remaining recovery frames and starts the next sword move early.

**Bad (illustrative):**

~~~luau
if buffered then startNextMove() end -- inside recovery step
~~~

**Corrected pattern:**

~~~luau
if recoveryFrame > recoveryLength then
    if buffered then startNextMove() else resetCombo() end
end
~~~

**Rule:** Assert exact phase boundaries before accepting a buffered transition.

**Evidence:** [Recorded failure](../../evals/results/baseline-creation-v1.json#L96) (task ANI-08, failed check at line 96); [official API/scripting reference](https://create.roblox.com/docs/animation/events).

## 6. Malformed key/value segments leak into results (LUA-05; wrong logic)

**Mistake:** Segments with no equals sign or an empty key are stored rather than discarded.

**Bad (illustrative):**

~~~luau
local key, value = segment:match("(.-)=(.*)")
result[key] = value
~~~

**Corrected pattern:**

~~~luau
local key, value = segment:match("^%s*([^=]+)%s*=(.*)$")
if key and key:match("%S") then
    result[key:match("^%s*(.-)%s*$")] = value
end
~~~

**Rule:** Test empty keys, malformed segments and whitespace, not only the happy path.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L352) (task LUA-05, failed check at line 352); [official API/scripting reference](https://create.roblox.com/docs/luau/strings).

## 7. Continuous aim traffic uses the wrong remote type (NET-04; missing feature)

**Mistake:** The requested 20 Hz lossy aim stream is sent on a reliable RemoteEvent.

**Bad (illustrative):**

~~~luau
local aimRemote = Instance.new("RemoteEvent")
~~~

**Corrected pattern:**

~~~luau
local aimRemote = Instance.new("UnreliableRemoteEvent")
aimRemote.Name = "AimUpdates"
~~~

**Rule:** Use UnreliableRemoteEvent for disposable frequent updates; keep critical messages reliable.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L542) (task NET-04, failed check at line 542); [official API/scripting reference](https://create.roblox.com/docs/reference/engine/classes/UnreliableRemoteEvent).

## 8. Inventory slots lack an aspect constraint (UI-09; missing feature)

**Mistake:** A grid can squeeze slots into rectangles on a narrow phone viewport.

**Bad (illustrative):**

~~~luau
local slot = Instance.new("Frame")
slot.Size = UDim2.fromScale(0.2, 0.2)
~~~

**Corrected pattern:**

~~~luau
local slot = Instance.new("Frame")
local ratio = Instance.new("UIAspectRatioConstraint")
ratio.AspectRatio = 1
ratio.Parent = slot
~~~

**Rule:** Require an explicit 1:1 aspect constraint when square inventory slots are specified.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L987) (task UI-09, failed check at line 987); [official API/scripting reference](https://create.roblox.com/docs/reference/engine/classes/UIAspectRatioConstraint).

## 9. Viewport scaling omits UIScale (UI-12; missing feature)

**Mistake:** A pixel-sized settings panel stays the same physical dimensions on phones and 4K.

**Bad (illustrative):**

~~~luau
panel.Size = UDim2.fromOffset(500, 300)
~~~

**Corrected pattern:**

~~~luau
local scale = Instance.new("UIScale")
scale.Scale = math.clamp(viewport.X / 1280, 0.6, 1.6)
scale.Parent = panel
~~~

**Rule:** Implement the named UI scaling mechanism, not just a fixed offset.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L1110) (task UI-12, failed check at line 1110); [official API/scripting reference](https://create.roblox.com/docs/reference/engine/classes/UIScale).

## 10. Mouse-only feedback ignores gamepad selection (UI-13; missing feature)

**Mistake:** Animations only respond to MouseEnter and MouseLeave.

**Bad (illustrative):**

~~~luau
button.MouseEnter:Connect(onHover)
~~~

**Corrected pattern:**

~~~luau
button.MouseEnter:Connect(onHover)
button.SelectionGained:Connect(onHover)
button.SelectionLost:Connect(onLeave)
~~~

**Rule:** Include gamepad selection paths when mouse, touch and controller input are required.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L1201) (task UI-13, failed check at line 1201); [official API/scripting reference](https://create.roblox.com/docs/ui/gamepad).

## 11. Nameplate text has no bounded font size (UI-14; missing feature)

**Mistake:** TextScaled is enabled without a minimum or maximum font size.

**Bad (illustrative):**

~~~luau
nameplate.TextScaled = true
~~~

**Corrected pattern:**

~~~luau
nameplate.TextScaled = true
local bounds = Instance.new("UITextSizeConstraint")
bounds.MinTextSize = 10
bounds.MaxTextSize = 24
bounds.Parent = nameplate
~~~

**Rule:** Long names need a testable text size bound rather than unbounded scaling.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L1268) (task UI-14, failed check at line 1268); [official API/scripting reference](https://create.roblox.com/docs/reference/engine/classes/UITextSizeConstraint).

## 12. Streaming-aware code assumes objects stay present (PERF-02; missing feature)

**Mistake:** Code waits once for a child but never responds to parts streaming out.

**Bad (illustrative):**

~~~luau
local target = workspace:WaitForChild("Target")
use(target) -- persists a stale assumption
~~~

**Corrected pattern:**

~~~luau
workspace.DescendantAdded:Connect(function(item)
    if item.Name == "Target" then use(item) end
end)
workspace.DescendantRemoving:Connect(function(item)
    if item.Name == "Target" then clearTarget(item) end
end)
~~~

**Rule:** For StreamingEnabled, handle both arrival and removal instead of assuming permanent presence.

**Evidence:** [Recorded failure](../../evals/results/baseline-v2.json#L2274) (task PERF-02, failed check at line 2274); [official API/scripting reference](https://create.roblox.com/docs/workspace/streaming).

## Limits and adoption

- New checks in `star/lesson_checklists.py` are advisory and only recognize a small fixed feature vocabulary. They are **not wired into generation**, do not run Roblox code, and cannot confirm behavioral correctness.
- The example snippets show one distinguishing decision, not complete deployable scripts. No lessons from the blind holdout were opened or used.
- Before adding any lesson to a recalled or trusted skill pack, run the evaluation gate and the existing human review process. 12 evidenced entries included; **0 additional speculative entries promoted**.
