# Make roblox_docs_live_enabled a real setting
star/roblox_docs_live.py checks a setting 'roblox_docs_live_enabled' that does not exist in Settings (star/desktop_core.py), so only the env var STAR_ROBLOX_DOCS_LIVE=1 works. Add the setting (default False) to the Settings dataclass with validation and persistence; keep the env var as an override. Backend only (no frontend). Tests: default off, setting on enables, env var overrides. Acceptance: full pytest green.
claimed by lane B at 2026-10-14T04:41:10Z
