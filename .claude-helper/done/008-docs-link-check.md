# Repo-wide docs link check
Add a test (tests/test_docs_links.py) that checks every relative link and anchor in docs/**/*.md, README.md and root *.md files resolves (skip external URLs; allowlist known generated paths). Fix the broken links it finds. If a guide-specific link test already exists, extend rather than duplicate.
claimed by lane B at 2026-10-14T06:41:06Z
PR: https://github.com/oncoursemail/Star-AI/pull/364
Added tests/test_docs_links.py (links + anchors across root and docs markdown); fixed one broken link in docs/ROBLOX_API_CONFUSIONS.md.
Full pytest: 6830 passed, 85 skipped.
