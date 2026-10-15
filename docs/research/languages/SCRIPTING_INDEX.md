# Scripting, web, shader and data languages: research index (checked 2026-10-13)

STAR is strongest at Roblox Luau. These notes give it accurate, sourced knowledge of the languages owners most often
meet next. Systems languages and game engines are covered by separate notes in this folder written by other agents.

Every note has the same twelve sections (mental model, type system, runtime/async, tooling, testing, idioms,
pitfalls with exact error messages, performance, security, game-dev usage, cheat sheet against Luau, recent changes)
and ends with numbered official sources. Facts that could not be confirmed on 2026-10-13 are marked as unverified.

| Area | Note | Skill pack (catalog only) |
|---|---|---|
| Python 3.13 / 3.14 | [python.md](python.md) | `lang-python` |
| JavaScript / TypeScript, Node, Deno, Bun | [javascript-typescript.md](javascript-typescript.md) | `lang-javascript-typescript` |
| Lua 5.4 and LuaJIT (differences from Luau) | [lua-luajit.md](lua-luajit.md) | `lang-lua-luajit` |
| GDScript (Godot 4) | [gdscript.md](gdscript.md) | `lang-gdscript-verse` |
| Verse (UEFN) | [verse.md](verse.md) | `lang-gdscript-verse` |
| Ruby | [ruby.md](ruby.md) | `lang-ruby-php` |
| PHP 8.4 | [php.md](php.md) | `lang-ruby-php` |
| Dart | [dart.md](dart.md) | `lang-dart-elixir-functional` |
| Elixir | [elixir.md](elixir.md) | `lang-dart-elixir-functional` |
| Haskell and OCaml (brief) | [haskell-ocaml.md](haskell-ocaml.md) | `lang-dart-elixir-functional` |
| Bash | [bash.md](bash.md) | `lang-shell` |
| PowerShell 7 | [powershell.md](powershell.md) | `lang-shell` |
| SQL (PostgreSQL, SQLite) | [sql.md](sql.md) | `lang-sql` |
| HTML and CSS | [html-css.md](html-css.md) | `lang-web-html-css-wasm` |
| WebAssembly | [webassembly.md](webassembly.md) | `lang-web-html-css-wasm` |
| HLSL | [hlsl.md](hlsl.md) | `lang-shaders` |
| GLSL | [glsl.md](glsl.md) | `lang-shaders` |
| WGSL | [wgsl.md](wgsl.md) | `lang-shaders` |
| Slang | [slang.md](slang.md) | `lang-shaders` |

## How STAR uses this

- **Skill packs** (`star/skill_packs/lang-*`): ordinary Agent Skills (`SKILL.md` + `references/sources.md` +
  `references/pitfalls.md`). They are listed by the skill catalog, so the model can load one with `star_skill_catalog`
  when a question is about that language. They are **not** in `star.skill_packs.TRIGGERS`, so no prompt is changed
  automatically; automatic routing for non-Roblox prompts is a follow-up that must pass the evaluation gate first.
- **Golden tasks** (`evals/languages/golden-tasks-scripting-v1.json`): development-split, prose-graded tasks (the
  current grader only extracts Luau code, so these tasks check explanations and forbid the classic wrong claim).
  Each task has a reference answer that must pass and a `.bad.md` answer that must fail;
  `tests/test_language_research_scripting.py` checks both offline. No model run has been measured yet.
- **These notes** are for maintainers and for future knowledge-service indexing; the STAR knowledge service indexes
  only Roblox and Luau documentation today.
