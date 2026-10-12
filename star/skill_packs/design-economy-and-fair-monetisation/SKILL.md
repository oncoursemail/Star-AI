---
name: design-economy-and-fair-monetisation
description: Design Roblox economy sources, sinks and fair monetisation with current official paid-random-item and purchase policies.
---
# design-economy-and-fair-monetisation
## When to use
Use for Roblox currency, upgrade pricing, inflation, shops or paid random items. Produce an economy ledger and a policy review checklist, not transaction code. Re-read current Roblox Community Standards and monetisation policies before a release or pricing change; policy review is not proof of compliance. [S1-S4]

## Ten concrete rules
1. List every currency source, sink and transfer with amount, frequency and eligible players. Player-to-player transfers do not remove currency; one-time starter gifts are not recurring income. [S1]
2. Model net creation per session and aggregate balances over time. Compare beginners, veterans and event participants; rising balances can erode progression even when fixed shop prices never rise.
3. Price useful progression in playtime, including failed attempts and compulsory costs. Simulate slow earnings and event windfalls, not just an average spender or the fastest player.
4. Use desirable optional sinks such as cosmetic collections. Keep basic tools and recovery affordable; never create a loss spiral to sell the player relief from it.
5. Reject pay-to-win traps for children: no paid combat superiority, engineered frustration, paid rescue from unavoidable failure or punishment for declining. This is this pack's stricter fairness rule, not a claim that Roblox bans every paid advantage.
6. Make prices, currency, contents, duration and renewal clear before confirmation. Use genuine offers, an obvious cancel path and no fake scarcity, restarting countdowns or high-pressure messages to minors. [S2]
7. For paid random items, disclose every possible final outcome and its actual numerical percentage before purchase, including spending currency bought with Robux. Underlying probabilities total 100%; rarity labels alone are insufficient. [S3]
8. Explain paid luck boosts numerically and update the displayed odds for the player's active modifiers or remaining obtainable items. Each possible paid outcome must benefit the player; no payment-for-nothing outcome. [S3, S4]
9. Require per-player PolicyService eligibility: respect ArePaidRandomItemsRestricted and IsPaidItemTradingAllowed independently. Do not infer eligibility from language or an age guess. If eligibility is unavailable, keep restricted offers unavailable and provide a free or guaranteed alternative. [S2-S4]
10. Review the current Community Standards, monetisation guidelines and applicable product policies together. Odds disclosure is not permission for gambling, off-platform cash-out or banned prizes. Record sources, review date, unresolved questions and observed tests; stop the affected offer until gaps are resolved. [S2-S4]

## Worked Roblox example
Hypothetical game: Harbor Helpers, a cooperative cleanup game. The following arithmetic uses proposed assumptions, not observed earnings or approved prices.

| Flow in a 10-minute session | Calculation | Shells |
|---|---|---|
| Four cleanup jobs | 4 x 30 earned shells | +120 |
| Optional chosen boat decal | One direct cosmetic purchase | -80 |
| Net for a player choosing that decal | 120 - 80 | +40 |
| Net for a player buying nothing | 120 - 0 | +120 |

Shells are earned only, not sold for Robux. At an assumed 50% decal take-up, mean net creation is 120 - (0.5 x 80) = 80 shells per session. For 100 sessions that is 8,000 new shells, not 4,000. Because a decal is bought only once, its sink weakens as players collect it; model later sessions separately. A 180-shell cosmetic takes six 30-shell jobs, or fifteen minutes at the assumed four jobs per ten minutes, with no other spending. A double-reward event increases creation; do not silently double every existing price in response.

The proposed paid shop sells a guaranteed cosmetic boat paint with no speed, cargo or reward bonus. It states the current Robux price and exactly what is received. No random purchase or trading is needed in this design.

For a review-only alternative, a cosmetic capsule could offer three distinct decals at 60%, 30% and 10%, totalling 100%. These are illustrative odds, not permission to enable a capsule. An eligible buyer must see the complete outcome list before spending, including through purchased tickets; any boost needs an updated disclosure. A restricted or unknown-eligibility player gets the guaranteed-paint shop instead. Repeated outcomes still need a stated benefit. Do not add this alternative until its separate policy and product review is complete.

## Checklist
- [ ] Source/sink ledger distinguishes transfers, one-time grants and recurring flows.
- [ ] Slow progression, non-spenders, saturated sinks and event inflation are modelled.
- [ ] Every offer is clear, cancellable and free of pay-to-win or pressure traps.
- [ ] Any paid randomness has complete, current numerical disclosures before spending.
- [ ] Restricted, unknown-eligibility and trading-disabled paths are separately reviewed.
- [ ] Current official policies and product rules are checked; unresolved offers stay unavailable.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S4], reviewed on 2026-10-11. The ledger and fairness choices are original recommendations; no gameplay, policy-service execution or legal approval is claimed.
