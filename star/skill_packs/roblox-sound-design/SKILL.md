---
name: roblox-sound-design
description: Opt-in Roblox audio recipes with the Audio API (AudioPlayer, Wire, AudioFader, AudioEmitter, AudioDeviceOutput), positional rolloff, volume buses and legacy Sound in typed Luau.
---
# roblox-sound-design
## When to use
Use for Roblox music, sound effects, positional audio, volume settings, UI clicks and choosing between the Audio API and legacy Sound objects. Not for voice chat moderation or for licensing questions about audio you upload.

## Ten concrete rules
1. The Audio API is the newer system: an AudioPlayer loads Asset, Wires carry its stream, and an AudioDeviceOutput is what people hear. Sound and SoundGroup are legacy. [S1][S2][S11]
2. A Wire needs SourceInstance and TargetInstance; nothing is heard until a chain reaches an AudioDeviceOutput. [S2][S3]
3. AudioDeviceOutput.Player limits who hears it; left empty, everyone wired to it hears it. Instances made by a LocalScript stay on that client. [S4]
4. For 3D audio wire an AudioPlayer to an AudioEmitter inside a part or attachment; with SoundService.DefaultListenerLocation set to Character or Camera, the listener and output are created for you. [S2][S5]
5. Shape rolloff with AudioEmitter.DistanceAttenuationMode and DistanceAttenuationBounds (full volume inside the minimum, silent past the maximum). [S6]
6. Route groups through an AudioFader (Volume 0 to 3) to build Music and Effects buses for a settings menu. [S7]
7. Set Looping for music and ambience; AutoLoad loads the asset on assignment, and IsReady tells you it is buffered. [S8]
8. A legacy Sound in a part is positional; in SoundService or Workspace it plays everywhere. RollOffMinDistance and RollOffMaxDistance bound its range. [S9][S10]
9. SoundService:PlayLocalSound plays a copy only the calling client hears, ideal for UI clicks. [S5]
10. ContentProvider:PreloadAsync waits for listed instances' assets, so the first play is not late; preload only what is needed soon. [S12]

## Three correct Luau examples
Example 2 is a server Script; examples 1 and 3 are LocalScripts. Replace the asset IDs with audio you are allowed to use.

### Example 1: music and effects buses for a settings menu
~~~luau
--!strict
local SoundService = game:GetService("SoundService")
local MUSIC_ID = "rbxassetid://0" -- your music asset

local function connect(source: Instance, target: Instance)
	local wire = Instance.new("Wire")
	wire.SourceInstance = source
	wire.TargetInstance = target
	wire.Parent = target
end

local output = Instance.new("AudioDeviceOutput")
output.Parent = SoundService

local buses: { [string]: AudioFader } = {}
for _, name in { "Music", "Effects" } do
	local fader = Instance.new("AudioFader")
	fader.Name = name
	fader.Parent = SoundService
	connect(fader, output)
	buses[name] = fader
end

local music = Instance.new("AudioPlayer")
music.Asset = MUSIC_ID
music.Looping = true
music.Parent = SoundService
connect(music, buses.Music)
music:Play()

local function setVolume(bus: string, volume: number)
	local fader = buses[bus]
	if fader then
		fader.Volume = math.clamp(volume, 0, 1)
	end
end

setVolume("Music", 0.6) -- call from the settings slider
~~~
Created by a LocalScript, this mix is private to the player who changes it. [S2][S4][S7]

### Example 2: looping 3D alarm at a speaker part
~~~luau
--!strict
local speaker = workspace:WaitForChild("AlarmSpeaker") :: BasePart
local ALARM_ID = "rbxassetid://0" -- your alarm asset

local player = Instance.new("AudioPlayer")
player.Asset = ALARM_ID
player.Looping = true
player.Parent = speaker

local emitter = Instance.new("AudioEmitter")
emitter.DistanceAttenuationMode = Enum.DistanceAttenuationMode.InverseTapered
emitter.DistanceAttenuationBounds = NumberRange.new(8, 120)
emitter.Parent = speaker

local wire = Instance.new("Wire")
wire.SourceInstance = player
wire.TargetInstance = emitter
wire.Parent = emitter

local function setAlarm(on: boolean)
	if on then
		player:Play()
	else
		player:Stop()
	end
end

setAlarm(true)
~~~
Set DefaultListenerLocation to Character in SoundService so each client hears it from the speaker. [S5][S6][S8]

### Example 3: preloaded UI click with legacy Sound
~~~luau
--!strict
local ContentProvider = game:GetService("ContentProvider")
local SoundService = game:GetService("SoundService")
local click = SoundService:WaitForChild("Click") :: Sound
local button = script.Parent :: GuiButton

task.spawn(function()
	ContentProvider:PreloadAsync({ click })
end)

button.Activated:Connect(function()
	SoundService:PlayLocalSound(click)
end)
~~~
The preload runs in its own thread so the button works at once. [S5][S12]

## Three common mistakes
1. Creating an AudioPlayer with no Wire to an emitter or output, then wondering why it is silent. [S2][S3]
2. Playing personal sounds (UI clicks, a player's own settings) from the server, so everyone hears them. [S4][S5]
3. One flat volume for everything instead of buses players can adjust. [S7]

## Checklist
- [ ] Every AudioPlayer reaches an output or emitter through Wires.
- [ ] 3D sounds use an emitter with deliberate rolloff bounds.
- [ ] Music and effects go through separate faders.
- [ ] Personal sounds play on the client only.
- [ ] Assets are ones you may use and are preloaded when needed.

## Sources
See [references/sources.md](references/sources.md) for [S1]-[S12]. Distances and volumes are illustrative.
