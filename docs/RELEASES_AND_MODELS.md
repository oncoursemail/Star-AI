# Research and implementation: STAR model setup, updates, Releases, and Pages

## Model runtime architecture

STAR wraps the permissively licensed llama.cpp inference engine as a subprocess. Its Windows **Vulkan** release is chosen to avoid installing a full CUDA SDK just to start a 4B quantized model, but users still need modern NVIDIA Vulkan-capable drivers. Engine zip selection is narrowed to the official `ggml-org/llama.cpp` stable release with a GitHub-provided SHA-256 digest. URL validation, safe ZIP extraction, download size limits, and hash checking are performed in `star/brain_setup.py`.

The first model is `lmstudio-community/Qwen3.5-4B-GGUF`, specifically `Qwen3.5-4B-Q4_K_M.gguf` and `mmproj-Qwen3.5-4B-BF16.gguf`. The Hugging Face repository exposes both, under Apache-2.0. The code validates upstream content hashes using the Hugging Face model tree API before it installs files. This does **not** require LM Studio software; the `lmstudio-community` name refers only to the group that published the conversion.

Do not treat model download size as total inference memory consumption. Prompt context, KV cache, image projector and Vulkan allocations consume additional GPU memory. With an RTX 3060 Ti 8 GB, start with 4K tokens, one model loaded at a time, and 30 GPU layers. If OOM occurs, reduce offload layers or close other GPU-intensive software. A smaller model and fewer layers are not equivalent to frontier intelligence.

**Limitations to verify live:** the exact latest llama.cpp release asset's binary dependencies and multimodal support, the Hugging Face tree response `lfs` digests, the model's OpenAI-compatible `/v1/models` ID, and Vulkan initialization on Windows. The offline suite checks protocol and safety assumptions, not GPU execution.

## Release publishing / installer research

PyInstaller bundles a portable `STAR.exe` and dependent libraries; Inno Setup 6 wraps that directory into `STAR-Setup-vX.Y.Z.exe`. Inno uses a stable AppId and per-user install directory (`%LOCALAPPDATA%\\Programs\\STAR`). Running a newer setup version upgrades the existing installation rather than extracting another portable folder. Project memory and weights live separately in `%APPDATA%\\STAR`, and are preserved during application upgrades.

The `windows-desktop.yml` pipeline runs tests, builds both executables, executes the packaged `--doctor` smoke test and uploads them as artifact. A separate job with limited `contents: write` publishes `vX.Y.Z` only after successful Windows build. The published release contains the setup EXE, the portable ZIP, and SHA256SUMS. Existing release tags are left unchanged; bump `star/version.py` to trigger a new release.

GitHub CLI `gh release create`: https://cli.github.com/manual/gh_release_create
Inno Setup official: https://jrsoftware.org/isinfo.php
PyInstaller: https://pyinstaller.org/en/stable/

## Updating STAR from its public Releases

`oncoursemail/Star-AI` is intentionally public. `star/updates.py` checks the unauthenticated, official `/repos/oncoursemail/Star-AI/releases/latest` API endpoint; it does **not** need GitHub CLI, a login, or a separate mirror repository. It accepts only a newer release from this exact repository, validates the named Windows installer, its advertised size, HTTPS URL and SHA-256, and downloads the installer to versioned staging storage. If the API is unavailable or inaccessible, the user is directed to the official Releases page in a browser rather than silently installing something else.

A user-approved Setup run upgrades the application in place. Only a manifest-verified installer can use unattended mode. `prune_obsolete_update_packages` may remove outdated **versioned update downloads**, never chats, models, references, projects, or other user files under `%APPDATA%\\STAR`.

The Windows workflow publishes the Setup EXE, portable ZIP and `SHA256SUMS.txt` from its successful build into the same repository's GitHub Releases. It never overwrites an existing tag. Automated tests and packaged `--doctor` checks are valuable but **cannot substitute** for live Windows upgrade, antivirus, GPU inference, and Roblox Studio acceptance.

## GitHub Pages and website

The canonical public website is built from `frontend/` (React/TypeScript/Vite) by `.github/workflows/website-pages.yml` and deployed from the successful `frontend/dist` artifact when GitHub Pages is configured and not disabled by `STAR_DEPLOY_PAGES=false`. `site/` holds historical standalone static-site assets kept for compatibility tests, **not** a second downloads repository or current React deployment source.

GitHub Pages must be enabled using **Settings → Pages → Source: GitHub Actions** and verified at its actual public URL. No website or build preview may include local conversations, credentials, model weights, or other private device data.

Sources: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site , https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages , https://huggingface.co/lmstudio-community/Qwen3.5-4B-GGUF/tree/main , https://github.com/ggml-org/llama.cpp/releases .

## Continued learning and GitHub commits

A longer-lived autonomous development worker can prepare isolated candidate branches, run regression suites, and propose changes through a GitHub App. It should **not** grant itself permissions, publish credentials, rewrite its verification rules, or automatically merge untested modifications to `main`. The current experimental `star/selfbuild.py` feature is much earlier than autonomous, trusted long-term training. A model's weights are not automatically improved by versioning source code or compacting conversations.
