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

## Updating privately hosted STAR

GitHub Release assets in a private repository require authorization. The `star/updates.py` checker tries the GitHub Release API and falls back to an authenticated **GitHub CLI** installation (it never copies its token into the model's context). If authorized, in-app updates can download a versioned portable archive and validate its GitHub-provided SHA-256 before staging. A helper process waits for STAR to stop, switches the folders, invokes the packaged doctor and rolls back if it fails. Otherwise users simply download the latest `STAR-Setup-v...exe` while signed into GitHub and run it to upgrade in place.

These updater flows require real Windows acceptance testing, particularly locked files, antivirus interference and failure recovery; they should not replace code signing or an externally signed update manifest for wide distribution. Never delete the old installation before verifying the replacement or store app data next to the executable.

## GitHub Pages limitations

The website is purely static (`site/`), doesn't upload chat data, and publishes only its own vetted files. `website-pages.yml` produces a GitHub artifact for preview on every change. Automatic Pages deployment is disabled until a repository variable `STAR_DEPLOY_PAGES=true` is set and **Settings → Pages** uses `GitHub Actions`.

GitHub Free supports Pages from public repositories, but not from private repos. Private repo support requires a GitHub plan that includes it. If unavailable, use a **separate public website-only repository**. Do not expose STAR's full private source code or credentials to publish a marketing website.

Sources: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site , https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages , https://huggingface.co/lmstudio-community/Qwen3.5-4B-GGUF/tree/main , https://github.com/ggml-org/llama.cpp/releases .

## Continued learning and GitHub commits

A longer-lived autonomous development worker can prepare isolated candidate branches, run regression suites, and propose changes through a GitHub App. It should **not** grant itself permissions, publish credentials, rewrite its verification rules, or automatically merge untested modifications to `main`. The current experimental `star/selfbuild.py` feature is much earlier than autonomous, trusted long-term training. A model's weights are not automatically improved by versioning source code or compacting conversations.
