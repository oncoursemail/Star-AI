# STAR Intelligence — Quiet Chat redesign

**Status:** React + Python source implementation candidate. This is **not** a new installer, not a published binary, and not a claim of GPU/ComfyUI Windows end-to-end verification.

## Product requirement

STAR should feel closer to the calm everyday chat experience of ChatGPT and Claude, *not* like an analytics dashboard that happens to contain a conversation. The owner explicitly rejects extra panels, giant gold bars, decorative rings, navigation clutter, AI-generated-looking gradients, and the independent Image Lab page.

Primary surface: **one STAR window; conversation first; images in chat; advanced developer tools available but not permanently occupying the main navigation.**

### Source review (October 2026)

- [Claude official upload guide](https://support.claude.com/en/articles/8241126-upload-files-to-claude) uses a small **+** action in the lower-left corner of the composer. STAR maps that to a keyboard-friendly menu for attachments, image creation, and audio transcription. No separate media tab.
- [ChatGPT Images help](https://help.openai.com/en/articles/11084440-im) documents creating images by asking in the conversation and viewing them in the same thread. STAR maps the explicit Create image composer choice to a local, core-node-only ComfyUI workflow; the full original stays in the user's STAR data folder. STAR does *not* claim ChatGPT's hosted image model or editing capabilities.
- [shadcn/ui chat primitives](https://ui.shadcn.com/docs/changelog/2026-06-chat-components) explain message-scroller anchoring, right-aligned user bubbles, inline attachments, stream visibility and jump-to-bottom controls. STAR implements those behaviors in its existing React view without a second styling framework.
- [Motion for React accessibility](https://motion.dev/docs/react-accessibility) recommends disabling transform animations in reduced-motion mode and keeping orientation cues. STAR retains subtle 140–190ms opacity, menu, hover and sidebar transitions and honors the OS/UI reduced motion controls.
- [Claude appearance options](https://support.claude.com/en/articles/8887527-customizing-your-appearance-settings) emphasize typographic readability and color consistency; STAR uses OS-provided fonts and one neutral dark theme, not mixed neon/color kits.
- [HeroUI](https://heroui.com/), [Chakra](https://chakra-ui.com/), [Aceternity](https://ui.aceternity.com/components) remain useful reference libraries for accessibility, spacing and interaction feedback. **Do not install all libraries at once:** it would increase offline bundle size and create inconsistent component systems.

### Exact desktop hierarchy

1. Left: STAR wordmark, lightweight New chat and Search, current project name, recent chat list. A collapsed **Workspace tools** menu contains Projects, STAR Brain, Analytics, Developer tools, Library and Settings. No duplicate navigation sections.
2. Top: single 61px header with a sidebar toggle, current context and small conversation actions. No repeated breadcrumb/status badges or second chat header.
3. Center: one maximally legible reading column (approx. 800px); assistant messages have **no colored bubble or horizontal dividers**. User prompts appear as right-aligned graphite bubbles. Copy controls are quiet; code blocks remain accessible.
4. Empty chat: one small STAR mark, one heading and three compact horizontal suggested prompts; **no hero cards**.
5. Bottom: a single anchored, growing multiline composer. The **+** menu contains Attach files, Create image, Transcribe audio. Selecting image creation places a removable in-composer mode chip and changes the placeholder.
6. Generated image: a real preview appears within the originating conversation with an accessible Radix dialog for enlarged viewing. The original image persists under local STAR data and the chat record stores only a bounded filename marker. Revisiting the thread reloads its preview.
7. AI setup and technical settings are secondary screens with progressive disclosure. STAR Brain no longer uses decorative orbit/ring imagery or repetitive health-status cards.
8. Optional desktop sidebar collapse allows distraction-free reading. Mobile sidebar uses a slide-in drawer.

### Animation policy

- Menu entry/exit ~150ms opacity + 4px movement. Message entry ~170ms and 5px. Header/page fade ~140ms. Sidebar width ~190ms.
- All animation helps describe cause and effect. No continuously moving background, glowing gradients, animated geometric decoration, heavy shadows or neon lighting.
- Streamed answers must not yank the reader down when they scroll up. Show a Jump to latest control until the user returns to the bottom.
- Respect the existing reduced-motion preference using MotionConfig and CSS.

### Local architecture and security

- Retain the Qt WebEngine React shell and restricted Python QWebChannel. Do not spawn a second desktop application.
- The default chat transport uses the existing local model; image creation is an explicit, separately authorized **generateImage** bridge action. It does not silently route the model's normal text queries.
- ComfyUI works only on 127.0.0.1 at a validated port with an approved API-format JSON workflow and reviewed core nodes. No arbitrary workflow scripts, internet downloads or surprise paid provider calls.
- A native file picker chooses the workflow; the path, node ID and port are saved in local settings. Image output filenames are validated, previews are downsampled and returned as bounded image data URLs, and original files never travel to an external host.
- Image marker messages are saved under the active `chat_id`; existing conversations remain project-scoped with older rows migrated to a legacy thread. Project-level reviewed memory remains shared by design.
- The repository stays public; source changes do not change installer secrets, release jobs, Roblox policies, model weights or user profiles. Other proposed STAR features in draft PRs require separate integration review.

### QA / Release gates

**Automated**: offline pytest, image traversal and persistence tests, conversation migration tests, frontend TypeScript/Vitest/Vite production build, and Chrome browser screenshot capture.

**Manual Windows required**: actual Qt WebEngine image menu, model streaming/cancellation behavior, ComfyUI installed and working on the configured localhost port, first-time setup, invalid workflow rejections, image saving and reloading after restart, attachment/audio selection, fully preserved pre-upgrade SQLite chats, 850px/390px displays, correct focus and ESC behavior, keyboard and screen-reader labeling, update/install/restart and no extra standalone window.

**Do not mark real ComfyUI image generation, cloud provider features or the Windows installer as verified based solely on a Linux CI run.** Release only after owner visual approval and native acceptance.
