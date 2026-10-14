# STAR's self-learning loop: what reaches the app, and how the owner stays in charge

W7 and W8 of `docs/research/self-improving-star-claude-v2.md`, built on the paired gate (`star/eval_stats.py`, W1) and
the protected-path guard (`star/protected_paths.py`, W2). The owner's rules (see
`docs/agents/context/CHATGPT_PLANS_20261013.md`):

- lessons carry evidence; nothing is learned from a model's say-so alone;
- a change is kept only when it beats a protected baseline on held-out tests;
- STAR never edits its own safety checks, evaluations or gate;
- owner corrections (in the app or on Discord) become candidates the owner reviews.

STAR's model weights never change in this loop. What it learns is text (lessons) and checked practice answers (worked
examples).

## W7: "What STAR learned this week"

```
night school (server 1)         reviewed bundle (draft PR)              STAR Desktop
practice -> lesson candidate -> star-learning-bundle-v1      ->   import once per app version
paired gate on the held-out     lessons + their gate evidence,      PROMOTE text lesson: live 14 days
validation slice (W1)           checked worked examples              anything else: waits for review
```

1. **Build the bundle** from night school's outbox (`/opt/star/learning/outbox` on server 1; copy it read-only):

       python -m star.learned_week bundle --outbox <outbox copy> --out star/skill_packs/learning_bundle.json \
           [--scoreboard <night school report>]

   Every row is validated with the app's own importers. A worked example the importer refuses (for example an answer
   longer than 4,000 characters) is skipped and counted, not silently dropped. The bundle records each lesson's
   paired-gate verdict exactly as night school wrote it in the evidence; a bundle whose verdict field disagrees with
   its evidence is refused.

2. **Review it in a draft pull request** on a generator branch (`star/outbox-learning-<date>`). The protected-path
   guard (W2) refuses any such PR that touches `evals/`, the graders, the gate or night school's promotion code.
   Nothing is pushed to `main`; the bundle ships with the next release only after review.

3. **The app applies it once per version** (`star/learned_week.import_bundled`, called when the desktop loads), into
   the current project:
   - a text lesson whose evidence says **paired gate PROMOTE** goes live at once, for **14 days**, and is listed under
     *What STAR learned this week* (Projects page, Learning panel) with its evidence;
   - every other lesson (the old single-run rule, INCONCLUSIVE, no evidence) is a candidate that waits for review;
   - worked examples are stored with the same 14-day expiry; using them in answers stays behind the owner's
     "worked examples" setting.

   The owner's switch *Use what night school learns, on a 14-day trial* (`learning_auto_live`, on by default per the
   owner) turns automatic use off: then every bundle lesson waits for review.

4. **Owner controls, one click each** (the host refuses them without the click's `approved` flag):
   - **Undo**: STAR stops using it at once;
   - **Restore**: brings back the byte-identical lesson row (allowed until its 14 days end);
   - **Keep for good**: the lesson becomes an owner-approved lesson; an example loses its expiry.

   An expired provisional lesson is not recalled even before the next sweep marks it expired (its expiry is part of
   the row's `revision`, which recall checks).

Local import for testing, without a release: `python -m star.learned_week import <bundle> --home <data folder>
[--project P] [--candidates-only]`.

## W8: owner corrections become regression-test candidates

- **In the app:** mark an answer *Not helpful* and say what was wrong in the box that appears under it.
- **On Discord:** DM the bot `wrong: <what was wrong>` right after its answer (needs the DM lesson-candidates switch,
  `STAR_DISCORD_DM_LEARNING_CANDIDATES=1`). The bot uses its own one-hour DM memory for the question and answer.

Either way STAR keeps, in `<data>/corrections.sqlite3` on this PC:

- a **correction candidate**: the original prompt, an excerpt of the failing answer, the owner's words, the
  failure-ledger cause they point at, and a check stub (patterns only when the correction names them, such as "use
  `task.wait` instead of `wait`");
- a **lesson candidate** in the owner's words (it is not used until approved, like every inferred lesson).

Under *Your corrections* the owner chooses **Make it a test** or **Dismiss**. Only *Make it a test* writes the task to
the **corrections suite**, `<data>/corrections/corrections-<project>.json`, in the evaluation-suite format (loaded by
the same loader). It is a development-tier suite: never the blind holdout, never inside the repository's `evals/`
folder (the writer refuses both), never sent anywhere. Text that looks like a key or password is refused; private
addresses are replaced. Corrections also feed the failure ledger (`CorrectionStore.as_failures`), so practice can
target their cause.

## What this does not do

- It does not retrain a model, change a setting or a permission, or touch an evaluation file.
- It does not prove STAR got smarter. That claim needs the paired gate on held-out tasks (night school's validation
  slice, then the sealed holdout), reported with its interval.
- The corrections suite's check stubs are weak until someone writes a real check; `check_status` says so.
