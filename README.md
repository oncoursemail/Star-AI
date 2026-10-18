# STAR AI — Official Downloads

**This is the public distribution repository for [STAR Intelligence](https://github.com/oncoursemail/Star-AI).** The application's development source, automated research, tests, and internal build workflows live in a separately maintained private repository.

> **Migration in progress:** The new public release channel has no published installer yet. **Do not download executables from issues, discussions, unofficial mirrors, or third-party links.** Once a verified release is published, it will appear on the [Releases page](https://github.com/oncoursemail/Star-AI/releases).

## Download

Visit **[Official GitHub Releases](https://github.com/oncoursemail/Star-AI/releases)**. A stable release should contain:

| File | Purpose |
| --- | --- |
| `STAR-Setup-vX.Y.Z.exe` | Windows desktop installer |
| `STAR-Genesis-Windows-x64.zip` | Windows portable app |
| `SHA256SUMS.txt` | Hashes to verify the two files |

No release is currently published in this repository. Do not claim a completed migration until a Windows installer has passed the private CI checks, has been published here, and has been independently downloaded and tested.

## Verify your download on Windows

Download `SHA256SUMS.txt` from the **same release** as your installer and check its listed SHA-256 against:

```powershell
Get-FileHash .\STAR-Setup-vX.Y.Z.exe -Algorithm SHA256
```

The digest must match the exact installer filename. A checksum detects accidental changes; it is **not** a substitute for publisher authentication or genuine code signing.

## Updating STAR

STAR uses the **public, unauthenticated** [GitHub Releases API](https://api.github.com/repos/oncoursemail/Star-AI/releases/latest) to check for updates. Automatic staging requires a newer stable release, the precise trusted release-asset URL, the advertised size and a matching SHA-256 digest. Installations do not need permission to access the private development repository.

The Windows installer is designed to preserve application settings, conversations, models and user files under the user's local STAR profile. Back up important data before major upgrades.

## Privacy and support

This repository contains only public distribution materials. It should never contain the private application source tree, private keys, personal chats, user databases, training datasets or model weights.

For troubleshooting, use [Issues](https://github.com/oncoursemail/Star-AI/issues) without sharing credentials, private logs or personal data. **Official installers will only be linked from this repository's GitHub Releases.**
