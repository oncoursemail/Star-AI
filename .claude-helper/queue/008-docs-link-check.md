# Repo-wide docs link check
Add a test (tests/test_docs_links.py) that checks every relative link and anchor in docs/**/*.md, README.md and root *.md files resolves (skip external URLs; allowlist known generated paths). Fix the broken links it finds. If a guide-specific link test already exists, extend rather than duplicate.
