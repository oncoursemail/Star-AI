# STAR Fast Brain — reviewable Windows preview

**Status:** Development candidate from PR #31. This is **not** the public v0.8.1 release, even though the code retains the v0.8.1 version baseline for strict existing updater regression compatibility. The PR has newer functionality; version promotion belongs to a separately reviewed release change.

## Download the actual Windows installer

1. Open [STAR Fast Brain PR #31](https://github.com/oncoursemail/Star-AI/pull/31) and select **Checks**.
2. Open the passing **STAR Desktop — Build, Test & Release** workflow for its newest commit. Or navigate to [STAR Actions](https://github.com/oncoursemail/Star-AI/actions/workflows/windows-desktop.yml) and select the run for branch \`star/fast-brain-integrated\`.
3. Scroll to **Artifacts**, choose **STAR-Fast-Brain-Preview**, and download the artifact ZIP. GitHub may require account sign-in to retrieve Actions artifacts. They expire after 30 days.
4. Extract the artifact ZIP. It contains:
   - \`dist/STAR-Setup-v0.8.1.exe\` — install/upgrade the actual test app.
   - \`STAR-Genesis-Windows-x64.zip\` — portable alternative, extract and run \`STAR.exe\`.
   - \`STAR-PREVIEW-SHA256SUMS.txt\` — checksum file produced from the built artifacts.
5. Confirm the installer digest on Windows PowerShell, substituting your extraction folder:
   \`(Get-FileHash .\dist\STAR-Setup-v0.8.1.exe -Algorithm SHA256).Hash\`
   Match the resulting 64 hex characters with the installer row in the manifest.
6. Test on a non-critical Windows 11 profile first. Before upgrading, copy \`%APPDATA%\STAR\` somewhere safe, then install the preview. The installer replaces application files, not the STAR profile. Do not confuse this with the public GitHub Releases v0.8.1 installer: **the artifact is linked to the preview commit, not the public release.**

## Live acceptance checklist

* Model: open **STAR Brain**, start the local engine, and run **Test actual AI response**. Check a normal answer, a long answer, and a Stop cancellation. Local speed depends on actual GPU/RAM.
* Providers: optionally configure the Groq/OpenRouter/Gemini/Cerebras key in **Settings → AI providers**. Test one response and deliberately switch provider. Cloud inference sends prompts/context to that service and uses the provider's quotas.
* Web: enable **Web** in Chat only after setting a Brave or Tavily API key. Check source URLs and that rate-limit/offline conditions appear as recoverable errors.
* Agent: select **Agent** only for complex work. Test the existing Studio tool protections, Obsidian/Graphify/Agent Skills and explicit GitHub source **read-only** inspection. Never run the agent on a live published Roblox game for these tests.
* Images: launch local ComfyUI, configure an API workflow and prompt node, then select **Image** in Chat. Confirm the image appears in the conversation and that an original remains in STAR's data folder.
* Persistence: close and restart STAR. Verify saved conversations, model downloads, project memory and references remain in the same \`%APPDATA%\STAR\` profile.
* Responsiveness: test several Fast/Auto/Agent requests and check how often STAR times out. This preview does not claim frontier-level intelligence or latency without actual measurements.

## Share a diagnosis for review

Inside the candidate app open **Settings → Diagnostics & Review → Export review ZIP**.

By default, this creates a small local archive containing exact STAR version, CPU/OS class, configured provider/tool flags, aggregated task success/error counts, duration p50/p95 and first-visible-token times as available. **It excludes conversation text, private source files, local paths, raw logs, API keys and model weights.**

An optional checkbox can include a screenshot of the currently visible STAR window. It is **off by default** because chats or credentials might be displayed. Read the files and screenshot before sharing. STAR never uploads the ZIP automatically.

Attach the ZIP to your ChatGPT conversation along with a description of the problem and the message you expected. It makes a structured code/performance review possible but does **not** grant remote access to your PC or independent verification of hardware performance.

## What is *not* verified by CI

GitHub's Python/React tests and Windows \`--doctor\` packaging prove source/bundle viability, **not** actual model quality, live GPU speed, true in-chat ComfyUI output, cloud provider rate limits, native update preservation or runtime memory behavior. These remain Windows owner acceptance gates. Do not automatically merge or publish candidate packages before approval.
