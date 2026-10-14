# Sources for roblox-sound-design

Reviewed on 2026-10-13 against the official Roblox Creator Documentation (source: the Roblox/creator-docs repository) and the Roblox Studio Full API dump for Studio 0.742 (every class, member and enum item in the examples exists there and none is tagged Deprecated). The examples passed luau-compile and luau-analyze 0.691 in strict mode with Roblox globals stubbed as `any`, plus STAR's offline linter. They have not run in a live Roblox Studio session.

| ID | Claim | Official Roblox documentation |
|---|---|---|
| S1 | Audio overview: AudioPlayer, AudioEmitter, AudioListener, AudioDeviceOutput and Wire; Sound is legacy | https://create.roblox.com/docs/audio |
| S2 | Audio objects: 2D and 3D wiring, default listener location creates listener and output | https://create.roblox.com/docs/audio/objects |
| S3 | Wire SourceInstance and TargetInstance | https://create.roblox.com/docs/reference/engine/classes/Wire |
| S4 | AudioDeviceOutput and its optional Player | https://create.roblox.com/docs/reference/engine/classes/AudioDeviceOutput |
| S5 | SoundService DefaultListenerLocation; PlayLocalSound plays a copy only the calling client hears | https://create.roblox.com/docs/reference/engine/classes/SoundService |
| S6 | AudioEmitter DistanceAttenuationMode and DistanceAttenuationBounds | https://create.roblox.com/docs/reference/engine/classes/AudioEmitter |
| S7 | AudioFader Volume (0 to 3) | https://create.roblox.com/docs/reference/engine/classes/AudioFader |
| S8 | AudioPlayer Asset, Looping, AutoLoad, IsReady, Play, Stop; IsPlaying replicates | https://create.roblox.com/docs/reference/engine/classes/AudioPlayer |
| S8 | Add 3D audio tutorial: server and client scripts play AudioPlayers | https://create.roblox.com/docs/tutorials/use-case-tutorials/audio/add-3D-audio |
| S9 | Legacy Sound placement: positional in parts, global in SoundService or Workspace | https://create.roblox.com/docs/sound/objects |
| S10 | Sound RollOffMinDistance, RollOffMaxDistance and RollOffMode | https://create.roblox.com/docs/reference/engine/classes/Sound |
| S11 | SoundGroup is discouraged in favour of the audio objects | https://create.roblox.com/docs/sound/groups |
| S12 | ContentProvider PreloadAsync | https://create.roblox.com/docs/reference/engine/classes/ContentProvider |
| S13 | GuiButton Activated | https://create.roblox.com/docs/reference/engine/classes/GuiButton |

Code samples have not run in a live game. STAR's Luau static checker is a heuristic linter.
