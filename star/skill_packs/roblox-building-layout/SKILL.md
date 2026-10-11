---
name: roblox-building-layout
description: Building and level layout in Roblox: grid and scale conventions, modular kits, placing models with PivotTo, lighting and atmosphere set from scripts.
---
# Building and level layout (Roblox)
- Work on a grid: Studio snaps to 1 stud by default; build modular kits in multiples (4, 8, 16 studs) so pieces tile without gaps, and snap with math.floor(v / grid + 0.5) * grid. Keep every piece's pivot at the same place (corner or centre).
- Scale by the character: a default R15 character is about 5 studs tall, so doorways are at least 7 studs high and 4 wide, ceilings 12 or more, corridors 8 wide. Test with a character, not by eye.
- Build with Anchored parts grouped in Models; move a whole model with Model:PivotTo(CFrame) (Model:SetPrimaryPartCFrame is deprecated). Set a part's properties first and its Parent last; do not pass the parent to Instance.new.
- Lighting from scripts: Lighting.ClockTime, Brightness, Ambient, OutdoorAmbient, ExposureCompensation, and child effects Atmosphere (Density, Offset, Color, Decay, Glare, Haze), BloomEffect, ColorCorrectionEffect, SunRaysEffect. Lighting.Technology cannot be set from a script (Studio only). Reuse effects with FindFirstChildOfClass.
