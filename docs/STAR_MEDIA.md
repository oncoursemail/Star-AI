# STAR media: images, picture and video understanding, visual references

Status (11 Oct 2026): working on the owner's PC, branch `star/media-20261011`. Everything in "What was run" below
was run for real; the rest of this page says where something is only written.

## 1. What STAR can do now

| Capability | Where it runs | How to use it |
|---|---|---|
| Create an image from text | This PC's graphics card (ComfyUI + FLUX.2 klein 4B) | Chat `+` menu, **Create image**, choose a size, describe it |
| Change a picture by instruction | This PC | **Create image**, attach the picture, describe the change |
| Change only part of a picture (inpaint) | This PC | As above, plus a second attached picture as the mask: white (or erased to transparent) = the part to change |
| Understand an attached picture | The selected brain (STAR Server: `star-vision`) | Attach it to a normal message |
| Answer a question about a local video file | Frames and transcript made on this PC, read by the place chosen for video understanding | Attach the video to a normal message |
| Keep approved reference images per project | This PC (STAR data folder) | Projects page, **Visual references**, **Pin an image** |
| Compare STAR's output with a reference | Measured on this PC, differences listed by the vision model | Projects page, **Compare latest image** or **Compare a file** |

What it deliberately does not do: it never claims to have watched a video it only has a link or title for; it never
replaces an unavailable place with the other one; it never installs ComfyUI custom nodes; it never sends frames of a
local video to a hosted provider.

## 2. Setting it up on a PC

Needs `git`, `curl` and `uv` on PATH, an NVIDIA card with 8 GB, and about 12 GB of disk.

```bash
export MEDIA_HOME=/path/to/media                 # any folder outside the repository
bash scripts/media/setup_comfyui.sh all           # clone, Python environment, PyTorch, three model files
bash scripts/media/start_comfyui.sh 8188          # listens on 127.0.0.1 only
```

- ComfyUI comes from the official repository (`github.com/Comfy-Org/ComfyUI`), tag `v0.39.0`, with its own Python 3.13
  environment (`uv`) and PyTorch from the CUDA 13.0 index. The script refuses to continue if the checkout is not the
  pinned commit.
- Model: **FLUX.2 klein 4B (distilled, fp8)**, Apache-2.0. Files (8.26 GB), each fetched from a fixed revision and
  checked against its SHA-256:
  `black-forest-labs/FLUX.2-klein-4b-fp8/flux-2-klein-4b-fp8.safetensors` (4.07 GB),
  `Comfy-Org/vae-text-encorder-for-flux-klein-4b/.../qwen_3_4b_fp4_flux2.safetensors` (3.85 GB) and
  `.../flux2-vae.safetensors` (0.34 GB). Both repositories are marked `apache-2.0` and are not gated; the model card
  states "Open weights available for commercial use under the Apache 2.0 license". The VAE is taken from the
  Apache-2.0 repository, not from the FLUX.2 dev repository (non-commercial licence).
- In STAR: Settings, **Where STAR generates**, **ComfyUI folder** = the `ComfyUI` folder. Then **Start ComfyUI**
  starts it for this PC only and STAR stops it again when it closes. ComfyUI has no sign-in of its own, so STAR only
  ever talks to, and starts it on, `127.0.0.1`.
- Video files need FFmpeg (`ffmpeg` and `ffprobe`): on PATH, or its folder in the same Settings section. The sound of
  a video is transcribed by the voice pipeline's recogniser (faster-whisper), so it needs the voice extras
  (`requirements-voice.txt`); without them the frames are still used and the answer says there is no transcript.

## 3. The switch: "Where STAR generates"

One choice per capability, saved in settings (`media_images`, `media_voice`, `media_video`: `pc` or `servers`), asked
by one function (`star.media_places.require`). The notes next to each option are built from
`star/media_measurements.py`.

| Capability | STAR Brains (servers) | This PC (your GPU) |
|---|---|---|
| Images | **Unavailable**: no image model is installed there and the servers have no graphics card. Estimate from published processor timings: 8 to 25 minutes per 1024 image (not measured on the servers) | Available. Measured: 6.8 s per 1024 x 1024 image |
| Voice | **Unavailable**: no speech recogniser or voice is installed there; the servers only write the reply text. Not measured on the servers | Available. Measured: recognise a sentence 0.17 s, speak one 0.33 s on the graphics card |
| Video understanding | Available when a STAR Server is connected. Measured: a 16 s clip (4 frames + transcript) answered in 93 s | Available when the on-device brain is installed. Not measured |

Rules the code follows:

- Choosing a place that is unavailable stops the action with the reason. It is never swapped for the other place.
- A voice call or voice preview is refused while voice is set to the servers.
- A video's frames go only to the chosen place: the chat's provider must be the STAR Server (for `servers`) or
  On-device (for `pc`). With any other provider the message stops and says which setting to change.

## 4. Speeds measured on the owner's hardware (11 Oct 2026)

Images, RTX 3060 Ti 8 GB, through `star.image_gen.generate` (3 runs each, median):

| Job | Time |
|---|---|
| 1024 x 1024 | 6.8 s |
| 1280 x 720 | 6.2 s |
| 720 x 1280 | 5.8 s |
| 512 x 512 (Draft) | 2.6 s |
| Change an attached picture (1024) | 13.5 s |
| Inpaint with a mask (1024) | 13.3 s |
| 1024 x 1024 following one pinned reference | 10.2 s |
| First image after ComfyUI starts (model files already in the disk cache) | 11 to 13 s |
| Starting ComfyUI until it answers (four starts) | 25 to 33 s |

Graphics memory: whole-card peak 7730 MB of 8192 MB while the desktop itself used 1997 MB. ComfyUI moves weights in
and out on demand. A voice call (Kokoro, about 1 GB) shares the card; the two were **not** measured together. If the
card runs out, STAR asks ComfyUI to unload its models and says to close other programs or use the Draft size.

Understanding on the STAR Server (processors only, `star-vision` = `star-fast`), under the measuring lock, with the
server still shared (load average 19 to 30):

| Input | First word | Whole answer |
|---|---|---|
| Screenshot 1280 x 800 | 61.9 s | 69.1 s |
| Photo-like picture 1024 x 1024 (made by the image model) | 31.2 s | 34.0 s |
| Screenshot 2560 x 1600, sent as it is | no answer within 170 s | |
| The same screenshot scaled to 1280 on the longer side (now the default) | 41.1 s | 57.5 s |
| Compare two pictures | | 51.9 s |
| 15.9 s video: 4 frames (768 x 432) + transcript; preparing them took 3.9 s | 57.5 s | 93.4 s |

Rule of thumb from these runs: one token per 32 x 32 pixels, read at about 38 tokens a second, so a megapixel costs
roughly 1,000 tokens and half a minute before the first word. That is why a picture read by the STAR Server or the
on-device brain is scaled so its longer side is at most 1280 pixels (Settings, **Picture size the brain reads**; 0 =
full size). The attached file is never changed, and hosted providers still get the full picture.

## 5. Visual references

- Per project, up to 12. Pinning copies the picture into `<STAR data>/references/<project>/` as a PNG without
  metadata; the owner's file is not touched. Removing deletes only STAR's copy.
- Image generation gets up to two pinned references as reference images for the model (measured: 10.2 s instead of
  6.8 s with one). The answer names the references it followed.
- A chat turn about how something looks (UI, screen, menu, icon, style, "match the reference") gets up to two of them
  attached, with a line that names them and asks for a one-to-one match. This happens only when the model that will
  receive them reads pictures (the STAR Server's vision model, or a vision model set in Settings), and counts toward
  the four-picture limit of a message. Each attached picture costs the reading time in the table above.
- **Compare**: a side-by-side picture (saved under `<STAR data>/comparisons/`), facts measured locally (shape,
  brightness and average colour, the three regions that differ most), and up to eight concrete differences from the
  vision model. If the model cannot be reached the measured facts are still shown and the panel says the model was
  not asked. STAR does not decide whether the result is good enough.
- Switch: Settings, **Use this project's visual references** (`media_use_references`).

## 6. Video understanding (first slice)

For one attached local video (MP4, MOV, MKV, WebM, AVI; up to 700 MB and 90 minutes):

1. `ffprobe` reads length, size and whether there is sound.
2. `ffmpeg` samples evenly spaced frames, at most four per message (fewer if pictures are attached too), scaled to
   768 pixels on the longer side.
3. The first ten minutes of sound are transcribed in 30-second pieces by the voice pipeline's recogniser. Silent
   pieces are skipped, because the recogniser writes stray words when given silence.
4. The model gets the frames, their times, the transcript with its times, and the rule to answer only from them.
5. STAR itself adds a line to the answer: which frames and how much transcript it was based on, and that the rest of
   the video was not seen.

A message that only contains a video link gets the opposite rule: STAR has no frames and no sound, has not watched
it, and says so. Nothing in STAR fetches the link.

Limits of this slice: at most four frames per message, so fast action between frames is missed; no scene detection;
only the first ten minutes of sound; one video per message; the recogniser is English-first (the voice pipeline's
default models).

## 7. Errors the owner sees

| Situation | Message (start) |
|---|---|
| ComfyUI not running | "ComfyUI is not running on this PC (127.0.0.1:8188). Start it in Settings ..." |
| A model file is missing | "ComfyUI does not have the model file ... Run scripts/media/setup_comfyui.sh models ..." |
| Graphics card out of memory | "The graphics card ran out of memory ... STAR asked ComfyUI to unload its models ... close other programs ... or choose the Draft size" |
| Images set to the servers | "Images is set to STAR Brains (servers) ... Not available: ..." |
| FFmpeg missing | "FFmpeg was not found, so STAR cannot open video files ..." |
| Video with a hosted provider selected | "Video understanding is set to ..., but the chat is using a hosted provider ..." |

## 8. Code map

| File | What it does |
|---|---|
| `star/comfy.py` | ComfyUI client (127.0.0.1), STAR's own klein workflows from core nodes, error wording; the older custom-workflow runner is kept |
| `star/image_gen.py` | Text to image, edit, inpaint; saves the original and a JSON note; pinned references |
| `star/media_places.py`, `star/media_measurements.py` | The switch and its measured notes |
| `star/references.py` | Pin, list, remove, side by side, measured differences, compare |
| `star/vision.py` | One bounded question to the vision model (compare, tests) |
| `star/video_understanding.py`, `star/chat_media.py` | Frames + transcript, the not-watched rule, what a turn's attachments become |
| `star/media_actions.py` | Bridge actions and the ComfyUI launcher |
| `frontend/src/MediaPanel.tsx`, `media.css` | Settings section and the references panel |
| `scripts/media/` | `setup_comfyui.sh`, `start_comfyui.sh`, `measure_images.py`, `measure_vision.py` |

Bridge actions: `generateImage {prompt, files?: [picture, mask?], size?}`, `mediaStatus`, `mediaStartComfy`,
`mediaFreeMemory`, `listReferences`, `pinReference {file, label?, note?}`, `unpinReference {id}`,
`compareReference {id, file?}`.

## 9. Tests

- `tests/test_media_pipeline.py`: 35 tests with fakes (a fake ComfyUI server over an httpx transport, fake ffmpeg and
  recogniser, a fake model client) and 4 live tests that are skipped unless the service is there:
  `STAR_LIVE_COMFY=1` (image generation and edit on this PC), `STAR_LIVE_SERVER_URL` + `STAR_SERVER_API_KEY` (picture
  understanding; with `ffmpeg` on PATH also video understanding), `STAR_LIVE_VOICE=1` (the recogniser loads).
- `frontend/src/media.test.tsx`: 14 tests (the switch, references, the composer's image mode).
- `scripts/shell_acceptance.py --phases media`: the real desktop window with a throwaway profile.

## 10. What was run, and what was not

Run on 11 Oct 2026: the install; all image jobs in section 4 on the real card; text to image from the chat in the
real desktop window (throwaway profile); picture understanding, video understanding and compare against the real
STAR Server through the chat's own code path; the four live tests; the full test suites.

Not run: a video attached through the real window's file picker (the acceptance tool never opens file dialogs; the
same functions were run from `scripts/media/measure_vision.py`); pinning and comparing through the real window (same
reason; covered by fakes in both test suites, and compare was run for real from the script); the **Start ComfyUI**
button in the real window (the launcher behind it was run for real from Python: ComfyUI answered after 33 s on
127.0.0.1 only, made a picture, freed its memory and was stopped again; the button itself was not clicked);
the on-device brain as the place for video; image generation while a voice call is active; any server-side image or
speech engine (none exists).

Seen once: a ComfyUI started two seconds after another one had been killed by force never opened its port. Three
later starts worked (25 to 33 s). A start that does not answer within two minutes is now stopped again by STAR, with
a message to try once more.
