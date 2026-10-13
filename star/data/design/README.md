# Design data shipped with STAR

`ui-ux-pro-max/` holds four CSV tables (UI styles, colour palettes, font pairings, UX rules) copied unchanged
from the MIT-licensed [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) project at commit
`7246805992a42b7bba37d4cac83b01416f0c6c44`. The licence is in `ui-ux-pro-max/LICENSE`; source, commit and file
hashes are in `ui-ux-pro-max/PROVENANCE.json` (checked by `tests/test_design_db.py`).

`star/design_db.py` loads and searches these tables; STAR's agent reaches them through the `star_design_search`
and `star_design_md` tools (`star/intelligence.py`). To update: copy the same four files from a newer upstream
commit, update `PROVENANCE.json` (commit, date, hashes, row counts), and run the tests.
