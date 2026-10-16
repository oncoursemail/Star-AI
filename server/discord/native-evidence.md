# Native Studio/Blender evidence and task DMs (#290)

This wiring is **off by default** and has not been deployed by this change.
The bot already runs on the same host/container as Brain 2's native jobs. Use
an operator-provisioned local directory as the private handoff; no listener,
SSH command, model tool, desktop capture or remote-control permission is added.

## Provision and opt in after review

Choose an absolute staging directory. Give the trusted native job identity
write access and the bot read/traverse access (a dedicated read group works).
Keep the directory and all its ancestors free of symlinks/junctions. Model
tools, downloaded scripts and arbitrary Blender Python must not be able to
write there. Files are created with mode 0640, event directories with 0750.
The producer's group must be the bot's approved read group. On Windows, set
equivalent ACLs. These permissions authenticate the producer; SHA-256 is an
integrity binding, **not a signature or proof of identity**.

In the trusted native job's process environment only:

```text
STAR_DISCORD_EVIDENCE_PRODUCER=1
STAR_DISCORD_EVIDENCE_DIRECTORY=/absolute/operator-selected/evidence
```

In the bot's existing nonsecret settings (keep its existing owner allowlist):

```text
STAR_DISCORD_LAB_STATUS=1
STAR_DISCORD_LAB_REPORT=/absolute/operator-selected/evidence/latest.json
STAR_DISCORD_LEARNING_DM_OPT_IN=1
STAR_DISCORD_EVIDENCE_DIRECTORY=/absolute/operator-selected/evidence
STAR_DISCORD_LEARNING_STATE=/absolute/bot-writable/state/learning_dms.sqlite3
STAR_DISCORD_LEARNING_DM_COOLDOWN_HOURS=6
STAR_DISCORD_LEARNING_CHECK_MINUTES=30
```

If several owners are configured, select one with the existing
`STAR_DISCORD_LEARNING_DM_OWNER_ID` setting. The existing Night School file/SSH
report source can stay configured; native-only notifications do not require it.
Native events run in the existing timer, reuse its owner callback and SQLite
delivery ledger, and share its cooldown/unknown-delivery budget. No second bot
or sender process is needed. Disable the producer and learning-DM opt-in to
stop staging and notifications; disabling Lab status also removes the viewer.

## What is produced

- Studio Lab map runs: build/read-back hash, iteration, native route results,
  actual fixed-camera screenshot, capture timestamp and SHA-256. An event
  needs successful apply/read-back, started/stopped playtest, reached route,
  and no script errors or defects.
- Studio UI runs: recipe hash, iteration, measured layout/device checks and
  device screenshot. Explicitly labeled UI checks, not gameplay or animation.
- Playtest learning: full script-build hash, robot completion/check results
  and confirmed Studio start/stop. It currently has **no camera capture**; it
  never borrows an image from another task or labels a lesson's text as proof.
- First-party Blender recipe worker: exported GLB hash, fixed camera render and GLB
  header/length check, only after worker success and controller inspection.
  This is not full GLB conformance, visual approval or Studio-import evidence.
  The arbitrary-Python Brain 2 Blender bridge is intentionally not a producer.

Native report prose, model answers, lesson text, scripts, paths and raw logs
are not exported. Task names must be short identifiers. Images are size and
signature checked, decoded, normalized to JPEG and stripped of metadata.
Images and event files use content-derived immutable names; the manifest is
atomically replaced last. Concurrent producers serialize manifest replacement
and do not replace a newer timestamp with an older one. A failed publication
logs only the exception type and does not abort the underlying native task.

The viewer shows **recorded** activity. `/star labshot` and `send lab screenshot`
never trigger live remote capture. Active status expires after 15 minutes;
native images are refused after 15 minutes even for completed jobs. Events
expire after seven days. Future timestamps, missing/corrupt images, changed
hashes, traversal paths and symlinks fail closed. A dead/offline job naturally
becomes unknown when its last active report expires.

For another bot host, provision an authenticated operator-managed transfer
outside Discord. Transfer only selected content-addressed JPEGs and bounded
event JSON, then atomically publish `latest.json` last; preserve the original
timestamps and hashes. Do not copy raw native job directories, private source
files, or the producer's `.publisher.sqlite3`. Cross-host transfer tooling and
native end-to-end acceptance are not implemented/tested by this patch.

## Independent owner review and optional DM images

By default a successful native task produces a **checked task result** DM:
review pending, lesson still a candidate, weights unchanged. It does not claim
that STAR learned a general new skill. Existing aggregate digests retain their
separate Luau/static/VM labels. No event type claims actual weight training.

Optional `STAR_DISCORD_EVIDENCE_REVIEWS` selects a **separate operator-only**
directory (outside the producer tree). Neither the job producer nor Discord
model tools should have write access. For an independently reviewed event,
write `<event_id>.json` there containing:

```json
{
  "event_id": "<64-character event filename stem>",
  "event_sha256": "<SHA-256 of the exact staged event JSON bytes>",
  "approved_for_reuse": true,
  "image_sha256": "<optional exact capture_sha256 from that event>"
}
```

Omit `image_sha256` to send text only. A false approval rejects the build and
suppresses its DM. Invalid/mismatched reviews also suppress delivery. Review
does not itself promote anything in LessonStore or start training. At most one
notification is sent per owner/event, including after restart or later review;
an already sent task is not resent when its review changes. Reserve happens
transactionally **before** sending. Timeout/cancellation leaves unknown state:
the same event is never silently retried, and other sends wait 24 hours.

The reader handles at most 256 event files per tick. Operators should archive
events older than seven days and unreferenced JPEGs. Keep event history and
review files where needed for audit; keep the bot's delivery ledger when
restarting or upgrading. No automatic destructive cleanup is added.

## Reference feedback

Use `/compare` with a reference image and omit the result attachment to compare
against the current fresh native Lab capture. Both Lab status and private image
analysis must be enabled. It uses the existing local/private vision route and
always replies privately. Supplying two attachments keeps the existing behavior.

The temporary conversation receipt retains full reference/result/capture hashes,
build hash, job, iteration, camera and exact owner instructions (up to 1000
characters, including negative constraints). Follow-up corrections use the
existing pending-only correction/lesson workflow. Native counts and state are
shown separately from advisory visual opinions; a model saying a failed build
looks good cannot approve it. Current support does not semantically verify a
vision model's animation, rig or VFX claims against multi-frame/native metadata.
That broader #290 phase-4 acceptance remains follow-up, as does live validation.

## Acceptance still requiring the conductor

On the authorized throwaway Test Place, run a native failure/fix/pass sequence,
inspect the receipt and actual camera image, confirm bot-user read permissions,
opt in, and observe one owner DM. Then test a fixed Blender recipe render, an
offline producer, a stale image, and a restart without duplicate delivery.
No server, Studio, Blender or real Discord operation was performed for this patch.
