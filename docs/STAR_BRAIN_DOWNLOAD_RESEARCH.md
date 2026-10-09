# STAR Brain: verified Windows download fix (Genesis v0.5.1)

## Root cause from actual user report

The user saw `ValueError: Cannot locate the official Windows Vulkan llama.cpp binary` at 0%. The v0.5.0 installer asked `https://api.github.com/repos/ggml-org/llama.cpp/releases/latest` for a stable release and assumed it would include the `llama-bNNNN-bin-win-vulkan-x64.zip` file. GitHub's `v0.6.0` stable pointer release **has only `nightly-tag.txt`**. The Vulkan Windows binaries exist instead on upstream numbered build releases such as `b11429` and `b11538`, tagged as prereleases. The v0.5.0 filter deliberately rejected those releases and could not proceed.

Sources checked October 9, 2026:
- Official stable [llama.cpp releases/latest API](https://api.github.com/repos/ggml-org/llama.cpp/releases/latest), tag `v0.6.0`, asset `nightly-tag.txt`, no binary.
- Official [release collection](https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15), tags of form `bNNNNN`, with SHA-256 digest per asset, including `llama-b11538-bin-win-vulkan-x64.zip` (about 33.5 MB). This tag was current when inspected; the newest numbered build changes regularly.
- Pinned fallback: [b11429 Vulkan Windows asset](https://github.com/ggml-org/llama.cpp/releases/download/b11429/llama-b11429-bin-win-vulkan-x64.zip), publisher SHA-256 `1bfe78ad9168b79fa02bf67f6af9f5e17a966d824d77238517f7bef12ac73b36`.

## v0.5.1 implementation

1. Inspect the newest stable release. Only accept a single, official Windows x64 Vulkan archive with a trustworthy SHA-256 digest and matching release tag.
2. If no Windows binary is present, query the release collection. Select the first official numbered `bNNNN` release containing a matching x64 Vulkan archive and a publisher digest. `bNNNN` builds are prereleases, so accepting them is **intentional and limited** to this publisher and validated file name.
3. If the release index cannot be used, select a previously inspected specific official build (`b11429`) and its pinned SHA-256; downloaded bytes must still match before extraction. Do not accept an arbitrary third-party binary.
4. Verify the compressed ZIP SHA-256 **before executing or extracting**; reject path traversal and symbolic links.
5. Download both model and vision projector from **one fixed revision**, not `main`, and verify against file SHA-256 values independently observed on Hugging Face:
   - `Qwen3.5-4B-Q4_K_M.gguf` (2,707,513,696 bytes): `25082a7dd3776cc3c741c6347d3bd04523f05796607b3fbc32fa3a25dfa1418c`
   - `mmproj-Qwen3.5-4B-BF16.gguf` (~676 MB): `ae08d9d7eceb8f2d0672d61b5e6aa78b611f2942b55ed71d21414980cc454b91`
   - Revision: `f9f88ac3e234be915e23811a6d28ea287bdb927e`
   - [Q4 publisher page](https://huggingface.co/lmstudio-community/Qwen3.5-4B-GGUF/blob/main/Qwen3.5-4B-Q4_K_M.gguf) and [vision projector](https://huggingface.co/lmstudio-community/Qwen3.5-4B-GGUF/blob/main/mmproj-Qwen3.5-4B-BF16.gguf). License: Apache-2.0. Attribution remains with Qwen and the quantization publisher. STAR does **not** run LM Studio.
6. Keep verified download `.part` files on network interruptions. Resume with `Range` only when HTTP 206 and the `Content-Range` start matches the existing bytes. Otherwise restart from zero. Always SHA-256 verify the entire result before promoting to installed files.
7. Display cumulative download progress across engine, model, projector and a user-friendly retry message instead of resetting the bar for every file.
8. Save the installed-engine/projector/model state only **after all downloads and verification** finish.

## UX and model limitations

The design now uses a dark-charcoal foundation, warm star-yellow and amber highlights, a high-contrast primary button, a yellow icon, readable errors and consistent setup text. Prefer deliberate spacing, font contrast, and functional controls over gratuitous neon, floating circles or irrelevant decoration.

On an RTX 3060 Ti with 8 GB GPU memory and 32 GB system RAM, a Q4 4B model plus the vision projector is a realistic *starting point*, but memory for KV cache and image tokens can still exceed model file size. The GPU must have Vulkan-compatible drivers. If the engine cannot launch, check `%APPDATA%\STAR\logs\star-brain.log`. The local model is **not guaranteed** to equal Claude or GPT-6 for coding and design.

## Evidence and next engineering tests

- Added tests for pointer-only stable release, fallback to build-prerelease with valid checksum, origin validation, hash pins, resume (`206`), range ignored (`200`), full fake install and saved state.
- Offline tests don't prove that the ~3.5 GB transfer or real Vulkan inference succeeded on Windows; those require the user's machine with actual NVIDIA drivers, storage, and network.
- Next: real Windows screenshot/animation QA; test long-run networking and resume under dropped Wi-Fi; load actual model/projector, attach a known visual reference, and run a Roblox Studio sandbox task. Measure VRAM/time/success. Track errors in GitHub Issues and only promote verified fixes.

No paid model API key or LM Studio application is required to run this verified local inference path.
