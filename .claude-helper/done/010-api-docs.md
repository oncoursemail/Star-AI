# Developer API docs for star/
Generate developer reference docs for STAR's main Python modules (agent, desktop_core, providers, intelligence, skill_packs, lessons, learned_week, corrections, map_plan, design tools) into docs/dev/api/ (pdoc or a small script; commit the generator, plus the generated Markdown only if it is small, otherwise just the script and a CI-free make target). Add missing module docstrings where obviously absent. No behaviour changes.
claimed by lane B at 2026-10-14T07:41:38Z

PR: https://github.com/oncoursemail/Star-AI/pull/366 (branch star/helper-010-api-docs)
Result: added stdlib AST generator scripts/gen_api_docs.py and generated docs/dev/api/ (~62 KB, 12 modules + index). No docstrings were missing. pytest not run (not installed; docs/script only).
