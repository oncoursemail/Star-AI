# Validate the learning bundle format
star/learned_week.py imports star/skill_packs/learning_bundle.json when present. Add a JSON-schema-style validator plus a test that (a) a well-formed sample bundle passes, (b) malformed ones (missing evidence, bad expiry, unknown kinds, oversized text) are refused with clear errors, and (c) the import path rejects invalid bundles without partial writes. Don't change night-school or eval code. Tests only plus the small validator.
claimed by lane A at 2026-10-14T07:17:04Z
PR: https://github.com/oncoursemail/Star-AI/pull/365
Result: added bundle_error() + tests/test_learning_bundle_validation.py (33 tests); full suite 6720 passed. No shipped learning_bundle.json exists in repo.
