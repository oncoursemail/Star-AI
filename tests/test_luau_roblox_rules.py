"""Opt-in Roblox Luau rules: each rule's bug cases, its false-positive guards and the lint() switch."""
import pytest

from star import luau_roblox_rules as rules
from star.luau_lint import lint
from star.luau_roblox_rules import lint_roblox_rules


def ids(code, **kwargs):
    return [f.rule_id for f in lint_roblox_rules(code, **kwargs)]


def only(code, rule, **kwargs):
    return [f for f in lint_roblox_rules(code, **kwargs) if f.rule_id == rule]


# ---------------------------------------------------------------- deprecated-api

@pytest.mark.parametrize(("code", "needle"), [
    ('local hit = workspace:FindPartOnRay(ray, character)', "Raycast"),
    ('local hit = game.Workspace:FindPartOnRayWithIgnoreList(ray, {character})', "Exclude"),
    ('local parts = workspace:FindPartsInRegion3(region, nil, 20)', "GetPartBoundsInBox"),
    ('local MarketplaceService = game:GetService("MarketplaceService")\n'
     'local info = MarketplaceService:GetProductInfo(id)', "GetProductInfoAsync"),
    ('local info = game:GetService("MarketplaceService"):GetProductInfo(id)', "GetProductInfoAsync"),
    ('local TeleportService = game:GetService("TeleportService")\n'
     'local code = TeleportService:ReserveServer(placeId)', "ReserveServerAsync"),
    ('local BadgeService = game:GetService("BadgeService")\nBadgeService:AwardBadge(player.UserId, id)', "AwardBadgeAsync"),
    ('local PhysicsService = game:GetService("PhysicsService")\nPhysicsService:CreateCollisionGroup("Ghosts")',
     "RegisterCollisionGroup"),
    ('local PhysicsService = game:GetService("PhysicsService")\nPhysicsService:SetPartCollisionGroup(part, "Ghosts")',
     "CollisionGroup property"),
    ('local Players = game:GetService("Players")\nlocal d = Players:GetHumanoidDescriptionFromUserId(1)',
     "GetHumanoidDescriptionFromUserIdAsync"),
    ('local cas = game:GetService("ContextActionService")\ncas:BindActionToInputTypes("Run", f, false, Enum.KeyCode.R)',
     "BindAction"),
    ('local ContentProvider = game:GetService("ContentProvider")\nContentProvider:Preload(id)', "PreloadAsync"),
    ('local pf = game:GetService("PathfindingService")\nlocal p = pf:ComputeRawPathAsync(a, b, 100)', "CreatePath"),
    ('local v = Instance.new("BodyVelocity")', "LinearVelocity"),
    ('local g = Instance.new("BodyGyro")', "AlignOrientation"),
    ('local w = Instance.new("ManualWeld")', "WeldConstraint"),
    ('local m = Instance.new("Message")', "TextLabel"),
    ('local child = model:findFirstChild("Handle")', "FindFirstChild"),
    ('part:Remove()', "Destroy"),
    ('local ok = ypcall(f)', "pcall"),
    ('print(elapsedTime())', "os.clock"),
    ('local n = table.getn(list)', "#t"),
    ('table.foreach(list, print)', "for loop"),
    ('workspace.FilteringEnabled = true', "always on"),
])
def test_deprecated_api_is_reported_with_its_replacement(code, needle):
    found = only(code, "deprecated-api")
    assert len(found) == 1, found
    assert needle in found[0].suggested_fix and found[0].severity == "warning"


@pytest.mark.parametrize("code", [
    'local result = workspace:Raycast(origin, direction, params)',
    'local parts = workspace:GetPartBoundsInBox(cframe, size, params)',
    'local info = game:GetService("MarketplaceService"):GetProductInfoAsync(id)',
    'local TeleportService = game:GetService("TeleportService")\nTeleportService:TeleportAsync(id, {player})',
    'local v = Instance.new("LinearVelocity")',
    'local child = model:FindFirstChild("Handle")',
    'part:Destroy()',
    'queue:Remove(item)',                                   # a user queue method with an argument
    'local Store = {}\nfunction Store:GetProductInfo(id) return id end\nStore:GetProductInfo(1)',
    'local self = {}\nself:ReserveServer()',                # unknown receiver: not a service
    'local function version() return "1" end\nprint(version())',
    'local stats = player:FindFirstChild("leaderstats")\nprint(stats)',
    'local t = { getn = 1 }\nprint(t.getn)',
    '-- workspace:FindPartOnRay(ray)\nlocal s = "Instance.new(\'BodyVelocity\')"',
    'local ok = pcall(f)',
])
def test_deprecated_api_leaves_modern_and_unrelated_code_alone(code):
    assert only(code, "deprecated-api") == []


def test_wait_spawn_delay_stay_with_the_older_rule():
    code = "wait(1)\nspawn(f)\ndelay(1, f)"
    assert only(code, "deprecated-api") == []
    assert {"deprecated-task-global"} <= {f.rule_id for f in lint(code, roblox_rules=True)}


def test_deprecation_tables_are_consistent():
    assert all(service and method and replacement for (service, method), replacement
               in rules.DEPRECATED_SERVICE_METHODS.items())
    assert not set(rules.DEPRECATED_CLASSES) & {"LinearVelocity", "AlignPosition", "WeldConstraint", "Part"}
    assert "wait" not in rules.DEPRECATED_GLOBALS and "spawn" not in rules.DEPRECATED_GLOBALS


# ---------------------------------------------------------------- pcall-called-result

@pytest.mark.parametrize("code", [
    'local ok, value = pcall(store:GetAsync(key))',
    'local ok = pcall(require(module))',
    'local ok = xpcall(remote:InvokeServer(), warn)',
    'local ok, data = pcall(HttpService:JSONDecode(body))',
])
def test_pcall_of_an_already_made_call_is_an_error(code):
    found = only(code, "pcall-called-result")
    assert len(found) == 1 and found[0].severity == "error"


@pytest.mark.parametrize("code", [
    'local ok, value = pcall(store.GetAsync, store, key)',
    'local ok, value = pcall(function() return store:GetAsync(key) end)',
    'local ok = pcall(callbacks[name], player)',
    'local ok = pcall(fn, compute(1))',                    # only the first argument matters
    'local ok = pcall((handler))',
    'local ok = xpcall(work, debug.traceback)',
    'local Lib = {}\nfunction Lib.pcall(x) return x end\nLib.pcall(f())',
])
def test_pcall_used_correctly_is_not_reported(code):
    assert only(code, "pcall-called-result") == []


# ---------------------------------------------------------------- server-invoke-client

def test_invoke_client_is_reported_and_other_remote_calls_are_not():
    assert ids('local answer = remote:InvokeClient(player, "ready?")') == ["server-invoke-client"]
    for code in ('remote:FireClient(player, "ready")', 'local a = remote:InvokeServer("x")',
                 'remote.OnClientInvoke = function() return true end', '-- remote:InvokeClient(player)'):
        assert only(code, "server-invoke-client") == []


# ---------------------------------------------------------------- fireserver-player-argument

@pytest.mark.parametrize("code", [
    'local Players = game:GetService("Players")\nlocal player = Players.LocalPlayer\nremote:FireServer(player, 10)',
    'local me = game:GetService("Players").LocalPlayer\nremote:InvokeServer(me)',
    'remote:FireServer(game:GetService("Players").LocalPlayer, "sword")',
    'local Players = game:GetService("Players")\nremote:FireServer(Players.LocalPlayer)',
])
def test_sending_the_local_player_to_the_server_is_reported(code):
    assert len(only(code, "fireserver-player-argument")) == 1


@pytest.mark.parametrize("code", [
    'local Players = game:GetService("Players")\nlocal player = Players.LocalPlayer\nremote:FireServer("sword", 10)',
    'local player = Players.LocalPlayer\nremote:FireServer(player.Character)',   # a different value
    'local character = Players.LocalPlayer.Character\nremote:FireServer(character)',
    'remote:FireAllClients(player)',                                           # server to clients
    'remote:FireClient(player, data)',
    'local target = Players:GetPlayerByUserId(id)\nremote:FireServer(target)',  # another player, by choice
])
def test_other_first_arguments_are_not_reported(code):
    assert only(code, "fireserver-player-argument") == []


# ---------------------------------------------------------------- client-leaderstats-write

@pytest.mark.parametrize("code", [
    'local player = game:GetService("Players").LocalPlayer\nplayer.leaderstats.Coins.Value += 10',
    'local player = game:GetService("Players").LocalPlayer\n'
    'local coins = player:WaitForChild("leaderstats"):WaitForChild("Coins")\ncoins.Value = 999',
    'local player = game:GetService("Players").LocalPlayer\nlocal stats = player.leaderstats\nstats.Coins.Value -= 5',
])
def test_client_writes_to_leaderstats_are_reported(code):
    found = only(code, "client-leaderstats-write")
    assert len(found) == 1 and "server" in found[0].suggested_fix


@pytest.mark.parametrize(("code", "script_class"), [
    ('player.leaderstats.Coins.Value += 10', "Script"),       # server script: fine
    ('player.leaderstats.Coins.Value += 10', None),           # no client evidence
    ('local player = game:GetService("Players").LocalPlayer\nlabel.Text = player.leaderstats.Coins.Value', None),
    ('local player = game:GetService("Players").LocalPlayer\nif player.leaderstats.Coins.Value == 5 then end', None),
    ('local player = game:GetService("Players").LocalPlayer\nlocal volume = settings.Volume\nvolume.Value = 0.5', None),
])
def test_reads_server_scripts_and_other_values_are_not_reported(code, script_class):
    assert only(code, "client-leaderstats-write", script_class=script_class) == []


def test_script_class_metadata_decides_the_client_side():
    code = 'local coins = player.leaderstats.Coins\ncoins.Value = 1'
    assert len(only(code, "client-leaderstats-write", script_class="LocalScript")) == 1
    assert only(code, "client-leaderstats-write", script_class="ModuleScript") == []


# ---------------------------------------------------------------- playeradded-existing-players

def test_playeradded_without_existing_players_is_a_review_note():
    code = 'local Players = game:GetService("Players")\nPlayers.PlayerAdded:Connect(onPlayerAdded)'
    found = only(code, "playeradded-existing-players")
    assert len(found) == 1 and found[0].severity == "review" and "GetPlayers" in found[0].suggested_fix
    fixed = code + '\nfor _, player in Players:GetPlayers() do task.spawn(onPlayerAdded, player) end'
    assert only(fixed, "playeradded-existing-players") == []
    assert only('Players.PlayerRemoving:Connect(f)', "playeradded-existing-players") == []


# ---------------------------------------------------------------- characteradded-existing-character

def test_characteradded_needs_the_existing_character_handled():
    code = 'local player = game:GetService("Players").LocalPlayer\nplayer.CharacterAdded:Connect(onCharacter)'
    assert len(only(code, "characteradded-existing-character")) == 1
    fixed = code + '\nif player.Character then onCharacter(player.Character) end'
    assert only(fixed, "characteradded-existing-character") == []


@pytest.mark.parametrize("code", [
    # The standard server idiom: connected inside PlayerAdded before the first spawn.
    'Players.PlayerAdded:Connect(function(player)\n\tplayer.CharacterAdded:Connect(onCharacter)\nend)\n'
    'for _, p in Players:GetPlayers() do end',
    'local function onPlayerAdded(player)\n\tplayer.CharacterAdded:Connect(onCharacter)\nend\n'
    'Players.PlayerAdded:Connect(onPlayerAdded)\nfor _, p in Players:GetPlayers() do onPlayerAdded(p) end',
    'local character = player.Character or player.CharacterAdded:Wait()',
])
def test_characteradded_idioms_are_not_reported(code):
    assert only(code, "characteradded-existing-character") == []


# ---------------------------------------------------------------- per-player-connection-leak

@pytest.mark.parametrize("code", [
    'local RunService = game:GetService("RunService")\nPlayers.PlayerAdded:Connect(function(player)\n'
    '\tRunService.Heartbeat:Connect(function() print(player.Name) end)\nend)',
    'Players.PlayerAdded:Connect(function(player)\n\tremote.OnServerEvent:Connect(function(p, x) end)\nend)',
    'local UserInputService = game:GetService("UserInputService")\nlocal function onCharacter(character)\n'
    '\tUserInputService.JumpRequest:Connect(function() end)\nend\nplayer.CharacterAdded:Connect(onCharacter)',
    'player.CharacterAdded:Connect(function(character)\n'
    '\tgame:GetService("RunService").Stepped:Connect(function() end)\nend)',
])
def test_long_lived_connections_made_per_player_are_reported(code):
    found = only(code, "per-player-connection-leak")
    assert len(found) == 1 and "Disconnect" in found[0].suggested_fix


@pytest.mark.parametrize("code", [
    # Signals on the player or character die with them.
    'Players.PlayerAdded:Connect(function(player)\n\tplayer.Chatted:Connect(function(msg) end)\n'
    '\tplayer.CharacterAdded:Connect(function(c) c.Humanoid.Died:Connect(function() end) end)\nend)',
    # Kept and disconnected.
    'local RunService = game:GetService("RunService")\nPlayers.PlayerAdded:Connect(function(player)\n'
    '\tlocal conn = RunService.Heartbeat:Connect(function() end)\n'
    '\tplayer.AncestryChanged:Connect(function() conn:Disconnect() end)\nend)',
    # Stored in a table for later cleanup.
    'local RunService = game:GetService("RunService")\nPlayers.PlayerAdded:Connect(function(player)\n'
    '\tconnections[player] = RunService.Heartbeat:Connect(function() end)\nend)',
    # Connected once, outside any handler.
    'local RunService = game:GetService("RunService")\nRunService.Heartbeat:Connect(step)',
])
def test_connections_with_owners_or_short_lives_are_not_reported(code):
    assert only(code, "per-player-connection-leak") == []


# ---------------------------------------------------------------- remote-every-frame

def test_remote_sent_from_a_frame_callback_is_reported():
    code = ('local RunService = game:GetService("RunService")\n'
            'RunService.Heartbeat:Connect(function(dt)\n\tremote:FireServer(camera.CFrame)\nend)')
    found = only(code, "remote-every-frame")
    assert len(found) == 1 and found[0].line == 3
    render = 'RunService:BindToRenderStep("Aim", 200, function()\n\tremote:FireServer(mouse.Hit)\nend)'
    assert len(only(render, "remote-every-frame")) == 1


@pytest.mark.parametrize("code", [
    'local RunService = game:GetService("RunService")\nlocal last = 0\n'
    'RunService.Heartbeat:Connect(function()\n\tif os.clock() - last < 0.1 then return end\n'
    '\tlast = os.clock()\n\tremote:FireServer(camera.CFrame)\nend)',
    'local RunService = game:GetService("RunService")\nRunService.Heartbeat:Connect(function(dt)\n'
    '\tif aim ~= previousAim then previousAim = aim remote:FireServer(aim) end\nend)',
    'local RunService = game:GetService("RunService")\nRunService.Heartbeat:Connect(function(dt) part.CFrame *= spin end)',
    'button.Activated:Connect(function() remote:FireServer("buy") end)',
])
def test_throttled_or_event_driven_sends_are_not_reported(code):
    assert only(code, "remote-every-frame") == []


# ---------------------------------------------------------------- integration

def test_rules_are_off_by_default_and_on_with_the_switch():
    code = 'local v = Instance.new("BodyVelocity")\nlocal answer = remote:InvokeClient(player)'
    assert not {"deprecated-api", "server-invoke-client"} & {f.rule_id for f in lint(code)}
    assert {"deprecated-api", "server-invoke-client"} <= {f.rule_id for f in lint(code, roblox_rules=True)}


def test_every_rule_id_is_declared_and_every_finding_has_a_fix():
    code = "\n".join([
        'local Players = game:GetService("Players")',
        'local RunService = game:GetService("RunService")',
        'local player = Players.LocalPlayer',
        'local v = Instance.new("BodyVelocity")',
        'local ok = pcall(store:GetAsync(key))',
        'remote:InvokeClient(player)',
        'remote:FireServer(player, 1)',
        'player.leaderstats.Coins.Value += 1',
        'Players.PlayerAdded:Connect(function(p) RunService.Heartbeat:Connect(function() end) end)',
        'player.CharacterAdded:Connect(onCharacter)',
        'RunService.Heartbeat:Connect(function() remote:FireServer(1) end)',
    ])
    found = lint_roblox_rules(code)
    assert {f.rule_id for f in found} == set(rules.RULE_IDS)
    for finding in found:
        assert finding.message.endswith(".") and finding.suggested_fix and finding.line >= 1
        assert finding.severity in ("error", "warning", "review")
    assert found == sorted(found, key=lambda f: (f.line, f.rule_id, f.message))
    assert lint_roblox_rules(code) == found  # deterministic


def test_bad_input_and_empty_source():
    with pytest.raises(TypeError):
        lint_roblox_rules(None)
    assert lint_roblox_rules("") == [] and lint_roblox_rules("-- only a comment") == []


def test_preflight_runs_the_roblox_rules(tmp_path):
    from star.roblox_project_preflight import preflight
    root = tmp_path / "place"
    (root / "ServerScriptService").mkdir(parents=True)
    (root / "ServerScriptService" / "Main.server.luau").write_text(
        'local v = Instance.new("BodyVelocity")\nv.Parent = workspace\n', encoding="utf-8")
    report = preflight(root)
    file = report["files"][0]
    assert "roblox-api-rules" in file["checked_scope"]
    assert any(f["rule"] == "deprecated-api" for f in file["findings"])
