/* STAR's public, anonymous release feed. Never expose a private repository or token. */
(() => {
  "use strict";
  const REPO = "oncoursemail/Star-AI";
  const ROOT = "https://github.com/" + REPO + "/releases/download/";
  const API = "https://api.github.com/repos/" + REPO + "/releases/latest";
  const $ = (id) => document.getElementById(id);
  const state = $("release-state");
  const detail = $("release-detail");
  const version = $("release-version");
  const checksumState = $("hash-state");

  function displayWaiting(message) {
    state.textContent = "No public installer available";
    detail.textContent = message;
    version.textContent = "No release";
    checksumState.textContent = "Check back after a signed-off stable release is published.";
  }

  function findAsset(assets, tag, filename, maxSize) {
    if (!Array.isArray(assets)) return null;
    const matches = assets.filter((asset) =>
      asset && asset.name === filename &&
      Number.isInteger(asset.size) && asset.size > 0 && asset.size <= maxSize &&
      typeof asset.browser_download_url === "string" &&
      asset.browser_download_url === ROOT + tag + "/" + filename &&
      typeof asset.digest === "string" &&
      /^sha256:[0-9a-f]{64}$/.test(asset.digest)
    );
    return matches.length === 1 ? matches[0] : null;
  }

  function enableLink(id, asset, caption) {
    if (!asset) return;
    const link = $(id);
    link.href = asset.browser_download_url;
    link.textContent = caption + " ↗";
    link.classList.remove("disabled");
    link.removeAttribute("aria-disabled");
    link.removeAttribute("tabindex");
  }

  async function refresh() {
    try {
      const response = await fetch(API, {
        headers: { Accept: "application/vnd.github+json" },
        cache: "no-store",
        credentials: "omit",
        mode: "cors"
      });
      if (!response.ok) {
        displayWaiting("The new public release channel is being prepared. No verified public installer has been published here yet.");
        return;
      }
      const data = await response.json();
      if (!data || data.draft || data.prerelease || typeof data.tag_name !== "string" ||
          !/^v[0-9]+\.[0-9]+\.[0-9]+$/.test(data.tag_name)) {
        displayWaiting("No compatible stable release metadata was found. Use the official GitHub Releases page to check again later.");
        return;
      }
      const tag = data.tag_name;
      const setup = findAsset(data.assets, tag, "STAR-Setup-" + tag + ".exe", 750000000);
      const zip = findAsset(data.assets, tag, "STAR-Genesis-Windows-x64.zip", 1500000000);
      const sums = findAsset(data.assets, tag, "SHA256SUMS.txt", 128000);
      if (!setup || !zip || !sums) {
        displayWaiting("The latest release does not contain the required official installers and checksums. Downloads stay disabled.");
        return;
      }
      state.textContent = "Public release available";
      version.textContent = tag;
      detail.textContent = "Published through the official public STAR AI release channel. Compare the downloaded file's SHA-256 with SHA256SUMS.txt before running it.";
      checksumState.textContent = "Official release checksums are available for both Windows packages.";
      enableLink("setup-link", setup, "Download Windows Setup");
      enableLink("zip-link", zip, "Download portable ZIP");
      enableLink("checksums-link", sums, "SHA256SUMS.txt");
    } catch {
      displayWaiting("Unable to check GitHub Releases right now. You can visit the official repository's Releases page to try again.");
    }
  }

  refresh();
})();
