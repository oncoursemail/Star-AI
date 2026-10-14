# Optional deprecated Roblox API lint rules

Enable with **lint(source, deprecated_apis=True, external=False)**. The new
switch defaults to **False**; existing lint rule IDs, calls, ordering and
findings are unchanged. This is a deterministic offline token heuristic,
not a Luau type checker or an automatic migration.

## Included rules and verified Roblox engine reference

| Rule ID | Flags | Suggested replacement | Official source |
| --- | --- | --- | --- |
| deprecated-body-velocity | Instance.new("BodyVelocity") | LinearVelocity with attachments | [BodyVelocity](https://create.roblox.com/docs/reference/engine/classes/BodyVelocity) |
| deprecated-body-gyro | Instance.new("BodyGyro") | AlignOrientation with attachments | [BodyGyro](https://create.roblox.com/docs/reference/engine/classes/BodyGyro) |
| deprecated-body-position | Instance.new("BodyPosition") | AlignPosition with attachments | [BodyPosition](https://create.roblox.com/docs/reference/engine/classes/BodyPosition) |
| deprecated-body-force | Instance.new("BodyForce") | VectorForce with attachments | [BodyForce](https://create.roblox.com/docs/reference/engine/classes/BodyForce) |
| deprecated-find-part-on-ray | workspace:FindPartOnRay(...) | workspace:Raycast(ray.Origin, ray.Direction, params), inspect RaycastResult | [WorldRoot:FindPartOnRay](https://create.roblox.com/docs/reference/engine/classes/WorldRoot/FindPartOnRay) |
| deprecated-find-part-on-ray-ignore | workspace:FindPartOnRayWithIgnoreList(...) | Raycast with RaycastParams.ExcludeInstances | [WorldRoot:FindPartOnRayWithIgnoreList](https://create.roblox.com/docs/reference/engine/classes/WorldRoot/FindPartOnRayWithIgnoreList) |
| deprecated-find-part-on-ray-whitelist | workspace:FindPartOnRayWithWhitelist(...) | Raycast with RaycastParams.IncludeInstances | [WorldRoot:FindPartOnRayWithWhitelist](https://create.roblox.com/docs/reference/engine/classes/WorldRoot/FindPartOnRayWithWhitelist) |

The official Roblox references mark all seven members/classes Deprecated.
The [RaycastParams reference](https://create.roblox.com/docs/reference/engine/datatypes/RaycastParams)
now prefers ExcludeInstances and IncludeInstances over the older
FilterDescendantsInstances/FilterType pair. Constraint replacements require
attachments and setup, so these are suggestions, not drop-in rewrites.
Raycast returns a RaycastResult rather than the legacy tuple.

## Intentionally excluded

- Lowercase aliases such as :children(), :isA(), :findFirstChild(), :connect():
  a textual match on an untyped Luau table cannot establish Roblox receiver
  identity. Their deprecation status is not asserted by these rules.
- Instance:Remove() and :remove(): the
  [Instance reference](https://create.roblox.com/docs/reference/engine/classes/Instance)
  marks them Deprecated, and Destroy() is appropriate for known Instances,
  but an arbitrary table can define its own Remove method.
- Computed class names, long-bracket class literals, aliased constructors
  and custom WorldRoot references: unresolved by design.
- Unsupported removed APIs without a proven safe replacement: unverified;
  do not flag or claim an API was removed merely because it is old.

Only an unshadowed global Instance.new with a first quoted literal and an
unshadowed global workspace ray method are diagnosed. Locals, assignments,
function parameters, unrelated receiver methods, comments and literal
strings are conservatively excluded. This intentionally causes false negatives
for aliases and complex control flow; there is no runtime type analysis.

## Three implementation options

1. **Chosen:** keyword-only deprecated_apis: bool = False on existing lint().
   Python standard library, no added licence or dependencies, $0 tool cost,
   small maintenance surface; all old callers stay unchanged.
2. Separate public deprecated-API function: same licence/dependency cost;
   additional caller wiring, duplicate lexing and finding merging to maintain.
3. Reuse safety_checks: same licence/dependency cost but tightly couples
   deprecation to lifetime safety and changes prior opt-in results. Rejected.

An independent open PR (#330) has overlapping broader deprecated API rules.
The lead should reconcile the overlap before merging both branches. The
[API confusion corpus](ROBLOX_API_CONFUSIONS.md) covers misspelling advice,
not deprecated engine APIs, and is not copied here.

## Verification

tests/test_luau_deprecated_apis.py exercises 21 positive snippets and 34
negative snippets across the seven rules, plus shadowing, inert text,
line numbers, default-off behavior, invalid input, literal inputs from the
existing lint test file, and checked-in Roblox example source. These tests
require no network, GPU, keyring or Studio and do not assert engine execution.
