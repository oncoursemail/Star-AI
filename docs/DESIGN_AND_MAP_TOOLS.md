# Design, DESIGN.md, map plan and live Roblox docs tools

Five agent tools, all in `star/intelligence.py`, each added to a turn only when the prompt asks for it.

| Tool | Module | Default | Network | Shown when the prompt mentions |
|---|---|---|---|---|
| `star_design_search` | `star/design_db.py` | on | no | palette, colour scheme, font pairing, typography, design system, DESIGN.md, contrast, WCAG, website, landing page |
| `star_design_md` | `star/design_md.py` | on | no | same as above |
| `star_roblox_map_plan` | `star/map_plan.py` | on | no | a Roblox prompt with map, blockout, greybox, level layout, scene spec |
| `star_roblox_docs_live_search` | `star/roblox_docs_live.py` | **off** | create.roblox.com only | a Roblox docs/code question, once enabled |
| `star_roblox_docs_live_page` | `star/roblox_docs_live.py` | **off** | create.roblox.com only | same |

Switches: `STAR_DESIGN_TOOLS=off`, `STAR_MAP_PLAN_TOOLS=off` turn the first three off; `STAR_ROBLOX_DOCS_LIVE=1`
(or a `roblox_docs_live_enabled = True` setting) turns live docs on. Plain prompts such as "Build a Roblox UI"
get no new tools, so their requests are unchanged.

## Design database
`star/data/design/ui-ux-pro-max/`: four unmodified CSV tables from
[UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) (MIT, commit `7246805`): 88 UI styles,
192 product palettes, 74 Google Fonts pairings, 119 UX rules. Licence, commit and SHA-256 per file are in
`LICENSE` and `PROVENANCE.json` (verified by `tests/test_design_db.py`). Search is BM25 over the descriptive
columns; deprecated styles are hidden; palettes come with measured WCAG contrast; `recommend` returns one style,
palette, font pairing and UX rules plus DESIGN.md-ready tokens. No brand-derived DESIGN.md files are bundled.

## DESIGN.md
Google's [design.md](https://github.com/google-labs-code/design.md) format (Apache-2.0, spec "alpha"): YAML
front matter with `colors`, `typography`, `rounded`, `spacing`, `components`, then Markdown sections in a fixed
order. `star/design_md.py` is an independent Python implementation: `lint` (broken/circular references,
missing primary/typography/sections, WCAG AA contrast for component and `on-*` colour pairs, invalid colours and
dimensions, duplicate or out-of-order sections, unquoted `#hex` turned into a YAML comment), `parse`, `render`,
`draft` (from the design database), and `read`/`write` of `<workspace>/DESIGN.md`. The agent tool never writes;
saving goes through the existing `workspace_write` tool, which needs the workspace edit switch. PyYAML is not
a dependency, so only the block-style YAML subset DESIGN.md files use is accepted (anything else is a lint
error, never a guess).

## Map plans
A JSON map plan (shape inspired by the SceneSpec format of [ShiroKSH/skills](https://github.com/ShiroKSH/skills),
MIT; no code copied) and an offline dry run: schema, unique names, managed root `Workspace/MapDrafts`, object
limit, bounds (rotation included), overlaps with a z-fighting hint, spawn head room, route legs a default
character can jump (8-stud gap, 6.5-stud rise; TrussParts are climbable), asset allowlist, unanchored and
floating parts. A clean plan returns ordered operations (folder / create / insert_asset / set) with tagged
values, and optionally one Luau script that builds it as a single undo step. Nothing is applied by these tools.

## Live Roblox docs
`/docs/api/search/<question>` (semantic search, JSON), `/docs/llms.txt` (page index) and `<page>.md` on
`create.roblox.com` only: fixed host and path prefixes, no redirects, no proxy from the environment, 6-second
timeouts, byte limits, memory and disk cache (`<STAR home>/cache/roblox-docs`, 1 day; index 7 days). Offline it
returns the stale cached copy, then the cached index, then STAR's curated links. Results are marked untrusted
and carry the CC BY 4.0 attribution of Roblox's Creator Docs. Tests use recorded responses in
`tests/fixtures/roblox_docs/` and never touch the network.
