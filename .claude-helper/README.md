# STAR Claude helper queue

Cloud routines ("STAR Claude helper" lanes) work through this queue, one task per run.

- `queue/NNN-slug.md`: pending tasks (lowest number first).
- `claimed/NNN-slug.md`: a run moved it here when it started (with lane + UTC time). A claim older than 3 hours is stale and may be re-taken.
- `done/NNN-slug.md`: finished, with the PR link and a short result.

To add work: put a new numbered file in `queue/` on the `claude-helper/queue` branch. Each task must be self-contained:
goal, where in the code, acceptance checks, and anything to avoid.

Global rules for every task: branch from `star/next` as `star/helper-NNN-<slug>`; open a PR against `star/next`;
never push to `main` or `star/next`; no force-push; never commit secrets, private IPs, host names or user names;
commit messages start with `[claude]` and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
PR bodies end with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`; never edit `evals/`, graders,
`star/eval_*.py` or the blind holdout; never touch PRs #152, #217, #270, #271, #274, #275, #278.
