# Luau checker false-positive corpus

This report is limited to known-good repository source snippets. It does not
prove Roblox Studio behavior. Sources are read directly from their original
files by `tests/test_luau_checker_false_positives.py` at test time, never copied
into golden fixtures.

## Corpus and method

- 37 authored game-source files from `examples/roblox/` and
  `examples/roblox-templates/` (exclude executable specs and test driver).
- 9 independent, reviewed code fences from the three existing maintained
  service skill packs, selected because `tests/test_core_service_skill_packs.py`
  already checks them with the default linter.
- **46 snippets total** on the indexed `star/next` snapshot.
- Each snippet passes four entrypoints: `lint(external=False,
  safety_checks=True, server_security=True)`, `inspect_safety`,
  `lint_server_trust`, and `check_luau_api` with the repository's
  `roblox_api_small.json` fixture.
- The lint-all-modes result incorporates safety/security findings already
  recorded separately. Counts include those deliberate duplicates; never
  treat the sum of all columns as a number of distinct bugs.

## CI evidence and classification

Findings must have an explicit (checker, path, rule) allowlist entry giving a
verdict and rationale, or the test fails. A new rule on an existing file,
or an existing rule on a new file, fails. Unlike Studio, the small API dump
omits some real classes and members; fixture-coverage advisories are
**not** proven Roblox API errors.

Initial findings per checker, classified true/false positives, and counts
after narrowly justified fixes are recorded from GitHub CI, not guessed.
The false-positive rate is the number of reviewed false-positive findings
divided by 46 snippets; this is findings per snippet, not a percentage
probability that any arbitrary code is safe.

Outstanding review: run the new CI regression, classify each finding,
fix small genuine false positives, explicitly allowlist justified true
positives/accepted-noise records, then state measured before/after totals.
