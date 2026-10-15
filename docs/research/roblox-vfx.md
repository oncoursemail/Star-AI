# Roblox ability VFX: research, techniques and how STAR builds them (2026-10-14)

Scope: what top-tier Roblox "anime ability" VFX are made of, which engine features and artist techniques produce each
layer, and how STAR now designs, builds, plays and visually checks such effects in any art style. The owner's reference
clip (a green energy ability by the creator credited on screen as VysVEX / vysdev) is used as a style reference only:
no asset, texture, mesh or frame of it is copied; STAR's effects are original.

## 1. Observation sheet of the reference clip

Frames inspected: two contact sheets of the clip (sheetA: 16 frames, sheetB: 5 effect frames plus the end card).
Timestamps were not available in the sheets; order is reading order. What is seen, not how it was made:

| Beat | Seen on screen | Likely layer (hypothesis) |
|---|---|---|
| Charge | Character darkened, green rim/aura, small sparks, dark environment | Highlight or character tint, glow particles, a dark ColorCorrection/Lighting change |
| Flash | Whole frame inverted to grey (white sky, dark figure and shapes) | One ColorCorrection frame with negative contrast and no saturation |
| Impact | Bright green burst, jagged black crack lines across the ground, chunks lifted, sharp spiky shards | Neon/decal crack lines, raycast-placed debris parts, mesh spikes with tweens |
| Shockwave | Curved green arcs sweeping around the caster, streaks across the screen | Mesh rings/crescents with transparency tweens, beams/trails |
| Green-out | Several frames almost fully green with dark silhouettes and black polygon shards | Full-screen flash or tint plus close debris in front of the camera |
| Vortex | A swirling sphere of light arcs, sparks orbiting | Spinning attachments with trails, swirl flipbooks, ForceField or neon sphere |
| Pillar | A huge vertical beam of bright layered green light, sparks and slashes at its base | Several stacked beams/cylinders with scrolling textures, slash meshes |
| Camera | Strong shake, FOV changes, close and low angles, cuts | Scripted camera (BindToRenderStep), several camera positions |

Quality lessons drawn from it (match the common VFX-artist rules in section 3): one dominant hue with white-hot cores
and near-black contrast shapes; a quiet anticipation followed by a very loud, very short impact; many layers at once
but each with its own scale (giant pillar, mid rings, tiny sparks); hard dark shapes (cracks, shards) make the glow
read; screen-level effects (inversion, green-out, shake) are reserved for the hit.

## 2. Engine building blocks (official documentation)

- **ParticleEmitter**: Rate 0 plus `Emit(n)` for one-shot bursts. `TimeScale` (0..1) slows the emitter;
  `Squash` stretches particles over life; `Orientation` FacingCamera, FacingCameraWorldUp, VelocityParallel (streaks),
  VelocityPerpendicular (flat to the velocity: ground rings and decals); `Shape` / `ShapeStyle` / `ShapeInOut`
  (Inward = motes that gather); `LightEmission` 0 normal / 1 additive blending; `LightInfluence` 0 = full brightness;
  `ZOffset`; flipbooks: `FlipbookLayout` (Grid2x2, Grid4x4, Grid8x8, Custom), `FlipbookMode` (Loop, OneShot, PingPong,
  Random). Sources: [ParticleEmitter reference](https://create.roblox.com/docs/reference/engine/classes/ParticleEmitter),
  [particle emitters guide](https://create.roblox.com/docs/effects/particle-emitters); descriptions read from the
  creator-docs YAML source.
- **Beam**: a textured strip between Attachment0 and Attachment1; widths, curve sizes, Segments, FaceCamera,
  TextureMode, TextureLength, TextureSpeed (scrolling energy). [Beams](https://create.roblox.com/docs/effects/beams).
- **Trail**: a ribbon left by two moving attachments; Lifetime, WidthScale.
  [Trails](https://create.roblox.com/docs/effects/trails).
- **Attachments** host emitters, beams and trails; moving or rotating their parent animates all of them.
- **Highlight**: fill + outline around an adornee; DepthMode AlwaysOnTop or Occluded; the client shows at most 255
  highlights at once (extras silently ignored).
  [Highlight](https://create.roblox.com/docs/reference/engine/classes/Highlight).
- **Post-processing**: ColorCorrectionEffect (Brightness -1..1, Contrast below 0 reduces contrast, Saturation -1 full
  desaturation, TintColor multiplies channels; only works under Lighting or the current camera), BloomEffect, Blur,
  DepthOfField. [ColorCorrectionEffect](https://create.roblox.com/docs/reference/engine/classes/ColorCorrectionEffect),
  [post-processing](https://create.roblox.com/docs/environment/post-processing-effects).
- **TweenService**: property tweens with EasingStyle/Direction for sizes, transparency, CFrame, beam widths, light
  brightness, FOV. [TweenService](https://create.roblox.com/docs/reference/engine/classes/TweenService).
- **Camera shake**: `RunService:BindToRenderStep` with a priority relative to `Enum.RenderPriority.Camera` (the default
  camera scripts run at 200; lower numbers run first). `RenderStepped` is superseded by `PreRender`.
  [RunService](https://create.roblox.com/docs/reference/engine/classes/RunService).
- **Cleanup**: `Debris:AddItem(instance, seconds)`.
  [Debris](https://create.roblox.com/docs/reference/engine/classes/Debris). Moving many parts:
  `WorldRoot:BulkMoveTo`. [WorldRoot](https://create.roblox.com/docs/reference/engine/classes/WorldRoot).
- **Remotes**: client requests, server validates, server tells clients.
  [Remote events](https://create.roblox.com/docs/scripting/events/remote).
- **Textures via Open Cloud**: the Assets API uploads Decal/Image files (png/jpeg/bmp/tga under 8000x8000) as a
  multipart form (`request` JSON + `fileContent`); the answer is an operation whose result carries the asset id and a
  moderation result. [Assets usage guide](https://create.roblox.com/docs/cloud/guides/usage-assets).

All 24 API names STAR's modules rely on were checked with STAR's knowledge service `/api-lookup` on 2026-10-14: all
found, none deprecated (list in star/skill_packs/roblox-vfx-composer/references/sources.md).

## 3. VFX-artist techniques (community practice)

- **Mesh shockwaves with transparency tweens**: a ring/cylinder/crescent mesh scaled up while its transparency goes to
  1 is the standard Roblox shockwave; DevForum answers on spells describe "meshes and a lot of tweening"
  ([How to make spells](https://devforum.roblox.com/t/how-to-make-spells/411488)); a DevForum VFX tutorial builds the
  cylinder mesh in Blender ([VFX Tutorial](https://devforum.roblox.com/t/vfx-tutorial-roblox/872437)); particles cannot
  be touched, so gameplay hit areas stay separate parts
  ([How can I do a shockwave?](https://devforum.roblox.com/t/how-can-i-do-a-shockwave/1827644)).
- **Scrolling textures**: Beam TextureSpeed (and offset animation on textures) makes static geometry feel like flowing
  energy; two layers scrolling in opposite directions read as turbulence.
- **Debris via raycast + physics**: raycast the floor at the impact, copy its colour and material into chunks, throw
  them out and up; many artists let physics run, which can push players and costs network ownership; a client-side
  ballistic step with short raycasts for bounces avoids both.
- **Flash frames**: one or two frames of white/colour flash or inversion on the hit, never longer; the eye reads the
  hit from the contrast jump.
- **Timing (anticipation, impact, follow-through, dissipation)**: classic animation principles applied to VFX: a
  readable wind-up, a very short extreme, a longer settle; stagger layers instead of firing everything on frame 0;
  every layer fades rather than popping off.
- **Camera shake**: decaying noise offsets after the camera update, plus a short FOV punch; community modules (e.g.
  the widely used EZ Camera Shake module mentioned on the DevForum) follow the same pattern.
- **Silhouette and value**: dark shapes (cracks, shards, smoke cores) against glow make an effect readable; check the
  impact frame in greyscale.
- **Overdraw budget**: big transparent particles stacked on screen are the expensive part, more than instance counts
  ([performance design](https://create.roblox.com/docs/performance-optimization/design)).

## 4. What STAR built (PR to star/next, branch star/roblox-vfx-20261013)

Style-agnostic by design (owner clarification): the clip is one art direction, not the target.

- **Skill pack `roblox-vfx-composer`** (star/skill_packs/roblox-vfx-composer/; opt-in, not on by default): SKILL.md
  (timeline, shape languages, techniques, budgets, security, review), references/recipes.md (code recipes),
  references/sources.md (citations + API check), and typed Luau modules in luau/:
  - `VfxStyles` - five built-in profiles: anime_energy (jagged, inverted flash, hard shake), cartoon_soft (round,
    pastel, Back easing, ball debris, no spikes), realistic_fire (wispy lit smoke, long dissipate), scifi_neon (crisp,
    ForceField shells, two-tone), pixel_retro (square particles, stepped motion, cube debris, no bloom);
    `Styles.custom` (recolour/adapt), `Styles.withTextures` (project's own textures), `Styles.stageTimes`.
  - `VfxPrimitives` - burst, sparks, smoke (flipbook when the style has one), ring (flat particle), ringSegments
    (mesh-like shockwave), dome, pillar (two scrolling beams + core + sleeve), slashes, vortex (shell + spinning trail
    arms), crack (decal + glowing polylines), debris (raycast + own ballistic physics + BulkMoveTo), spikes, aura
    (Highlight + rising + inward motes), light, flash (inverted frame then colour flash, bloom kick), tint, shake
    (Camera + 2, decaying noise, FOV punch). Every primitive reads the style, scales with quality and budget, follows
    a playback speed, and cleans up with Debris.
  - `VfxComposer` - plays an ability (cues on charge, impact, shockwave, linger, dissipate) in a style; max 4 active,
    700-particle budget at quality 1, device quality (touch-only 0.5, graphics level), cull 350 studs, screen
    effects within 120 studs, one Folder per effect destroyed at the end. Built-in abilities: energy_burst, impact_hit.
  - `VfxClient` / `VfxService` - client render + request; server validation (string allow lists, per-ability
    cooldown, token bucket, origin from the server's own character, range clamp, relevance radius).
- **`star/roblox_vfx_studio.py`** - picks/adapts a style from words and/or a reference image (Pillow palette analysis),
  picks an ability or generates a cue list (heal_aura, explosion), generates the Luau, lints with STAR's Luau checks,
  installs it in STAR Test Place through the guarded Studio path (PinnedSession -> GuardedStudio, one undo step),
  runs a slow-motion playtest (the lab Script plays the effect through the real RemoteEvent path), captures frames
  with the connector's screen_capture, stops, writes frames + contact sheet + measured critique.
- **`star/roblox_vfx_textures.py`** - nine original procedural textures (soft glow, spark, smoke wisp, ring, crack,
  streak, swirl, square, 4x4 puff flipbook), white on transparent so styles tint them; review rules (PNG RGBA,
  power-of-two, colour-neutral, transparent border, no text/URL/barcode pattern; the generator never draws glyphs).
  Uploaded to STAR's own account as private Decals through `RobloxCloud.upload_image_asset` (new, key read
  in code, never printed); all 9 were approved by moderation; image ids resolved in Studio with
  InsertService:LoadAsset.
- **STAR tool `star_roblox_vfx_make`** (off by default: setting `vfx_studio_enabled` or `STAR_VFX_STUDIO=1`): "plan"
  returns style/ability/Luau/lint offline; "build" runs the Studio lab and returns frame evidence.

## 5. Results in Studio (real runs on brain 2, STAR Test Place, nothing saved or published)

Evidence: docs/agents/roblox-vfx-20261013/ (each run: frames, sheet.jpg, report.json, playtest-output.txt,
VfxGenerated.luau). Playback speed 0.25 (4x slow motion), frames every ~0.13 s of effect time.

| Run | Style | What changed | Critique (measured) |
|---|---|---|---|
| iter1b/anime-green | anime | first working run | camera far, opaque dome hides layers, weak charge |
| iter2/anime-green | anime | close camera, dusk, ForceField dome, wider pillar, charge ring + streaks | impact/charge 16x, no findings |
| iter2/pixel-retro | pixel | first run | big dark smoke squares dominate the tail |
| iter2/cartoon-soft | cartoon | first run | dark crack pool, rock debris and spikes are off-style |
| iter3/* | all three | flash after inversion, thicker slashes, wider vortex arms; soft splat, ball debris, no spikes for round; small fast pixels for blocky smoke | anime: no findings; pixel and cartoon: only "main colour barely visible" (metric limitation, see below) |
| iter4/anime-green-startex | anime | STAR's own uploaded textures | renders with own textures |
| iter4/fire-startex, iter5/fire-startex | realistic fire | explosion cue list; iter5 adds a fireball core and lit grey-brown smoke | iter4 had no fireball; iter5 reads as an explosion |

Honest gaps against the reference: STAR's effects are procedural primitives (parts, particles, beams, trails) with
built-in or simple procedural textures; the reference uses hand-made meshes (crescents, shards), richer flipbooks,
cinematic camera cuts and colour grading. The automatic critique measures contrast, motion, duration, palette and
tail; it cannot judge taste, and its palette metric under-counts low-saturation pastel and small yellow pixels. The
inverted frame is ~0.07 s of effect time and is captured only when a frame lands on it (seen in iter1b).

## 6. Next steps

1. Mesh assets for crescents/shards made in Blender on brain 2 (star_blender, PR #289) and uploaded as private meshes.
2. A capture mode that freezes the effect at given times (TimeScale 0 + paused tweens) for exact frames.
3. A vision critique by brain 1 once the release eval is done (advisory, like the Studio Lab's).
4. Run the evaluation gate on the skill pack before enabling it by default.

## Images in this repository

- [roblox-vfx/styles-compare.jpg](roblox-vfx/styles-compare.jpg): the same ability (and the explosion cue list) in
  four style profiles, five stages each, captured in a real Studio playtest.
- [roblox-vfx/anime-energy-sheet.jpg](roblox-vfx/anime-energy-sheet.jpg): the anime energy burst, 16 labelled frames.
- [roblox-vfx/textures-sheet.png](roblox-vfx/textures-sheet.png): STAR's nine procedural textures on dark and green.
