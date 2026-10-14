# Roblox security practice (20 tasks)

This is **development practice material**, not a baseline, holdout, or evidence of improved model performance. It lives in `evals/roblox/practice-tasks-security-v1.json` and is **not** added to STAR's default evaluation suite or learning loop. Each prompt is a beginner-facing server-security request.

## What the checks show

The existing `star.eval_runner.load_suite` checks IDs, modes, shape and regex validity; `star.eval_checks.score_answer` requires a fenced Luau block, asks the knowledge service to check Luau, and scans comment-stripped code for `auto.require` and `auto.forbid` patterns. Every row below has both kinds. The checks confirm identifiable code idioms are present or absent; they **cannot** prove data flow, atomicity, permissions, a real Studio execution or resistance to all attacks. A deceptive or accidentally incorrect implementation can pass static patterns. The offline Python test verifies that each pattern accepts a positive syntax probe and rejects an unsafe counterexample through the real scorer with compilation stubbed; it does not compile or run the probe fragments.

| Task | Distinct failure mode | What its expected checks teach |
|---|---|---|
| `SEC-01` | fixed reward | A client can request a payout, but only a verified server completion and fixed server-owned amount authorize it. |
| `SEC-02` | teleport destinations | Server-chosen destinations and entry proximity prevent arbitrary position injection. |
| `SEC-03` | shop coupons | Client-reported prices and discounts cannot replace the authoritative catalog and server-earned coupon. |
| `SEC-04` | projectile raycast | The server must resolve who was hit from its own world query, never from the client target claim. |
| `SEC-05` | fixed window throttle | Per-user quotas based on server time prevent burst abuse without yielding or stale player entries. |
| `SEC-06` | account store key | The engine-authenticated Player is the identity authority for persistent record keys. |
| `SEC-07` | receipt decisions | Roblox retries unacknowledged receipts; correct enum responses prevent silent lost grants. |
| `SEC-08` | profile subject | A target identity supplied by the client must not authorize cross-account writes. |
| `SEC-09` | inventory equip | Client-controlled Instances cannot stand in for verified ownership and server templates. |
| `SEC-10` | team capacity | Team assignments depend on server-approved teams and authoritative live capacity. |
| `SEC-11` | world pickup | A visible pickup is not proof that the requester actually reached a real available world item. |
| `SEC-12` | server loot roll | Client-supplied luck and rarity cannot replace server-owned inventory consumption and randomness. |
| `SEC-13` | quest claim | Quest completion and one-time claim status must be recorded by the server. |
| `SEC-14` | admin allowlist | Privilege is established by the server's allowlist, not the caller's claimed role. |
| `SEC-15` | unique vote | Vote totals must come from unique authenticated players rather than packet-provided counts. |
| `SEC-16` | gamepass entitlement | Purchase entitlements must be verified by an authoritative service, with errors denying access. |
| `SEC-17` | door key and range | World-state changes require server-owned inventory authorization and proximity proof. |
| `SEC-18` | finite impulse | Numeric payloads need finite bounds and the server must control which character is affected. |
| `SEC-19` | settings write allowlist | Whitelisting patch fields and preserving server-held records prevents mass-assignment writes. |
| `SEC-20` | user text filter | Untrusted user-generated text must be filtered for its audience before public replication. |

## Choice of checking method

| Option | License / upkeep / cost | Decision |
|---|---|---|
| Existing Python `re` with `auto.require` / `auto.forbid` | Python standard library (PSF license); no added dependency or model/runtime cost, but patterns need upkeep when valid Luau style varies | **Used**: this task expressly requires positive/negative machine-checkable patterns |
| Existing standalone Luau VM fixture harness | Already present in STAR; no new dependency, but a fake Roblox service contract and test fixture must be maintained per behavior, and a server sandbox is needed to execute it | Stronger for follow-up behavioral validation; not used in this pattern-only practice suite |
| Roblox Studio playtests | Roblox platform terms; runtime/place maintenance and interactive test orchestration required, with more manual and infrastructure cost | Valuable for final security proof, but outside these standalone practice tasks |

The new suite intentionally does not reference or modify the frozen holdout or either golden suite. Running `pytest -q tests/test_security_practice.py` locally is optional for maintainers; GitHub CI status should be read independently, and no live model evaluation is claimed.
