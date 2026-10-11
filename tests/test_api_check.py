"""Engine API names in generated Luau, checked against the official reference (star/api_check.py).

No network: `lookup` is a small table standing in for KnowledgeClient.api_lookup.
"""
import pytest

from star import api_check
from star.api_check import (DEPRECATED, REQUESTED, UNKNOWN, blank, diagnose, missing_requested, prose_of_request,
                            receivers, references, requested_names)

CLASS = "{name}   [class]\n\nInherits: Instance > Object\n\nMembers of {name}:\nproperties: {props}\nmethods: {methods}\nevents: {events}"
REFERENCE = {
    # classes (overview entries)
    "GuiService": CLASS.format(name="GuiService", props="TopbarInset, SelectedObject", methods="GetGuiInset", events="MenuOpened")
                  + "\nTags: NotCreatable, Service",
    "TweenService": CLASS.format(name="TweenService", props="", methods="Create", events="") + "\nTags: Service",
    "Players": CLASS.format(name="Players", props="LocalPlayer", methods="GetPlayers", events="PlayerAdded, PlayerRemoving")
               + "\nTags: Service",
    "DataModel": CLASS.format(name="DataModel", props="", methods="BindToClose, GetService", events=""),
    "Workspace": CLASS.format(name="Workspace", props="CurrentCamera, Gravity", methods="Raycast", events=""),
    "Camera": CLASS.format(name="Camera", props="ViewportSize, CFrame", methods="", events=""),
    "UIScale": CLASS.format(name="UIScale", props="Scale", methods="", events=""),
    "IKControl": CLASS.format(name="IKControl", props="SmoothTime, Weight, Target", methods="", events=""),
    "TextLabel": CLASS.format(name="TextLabel", props="Text, TextScaled", methods="", events=""),
    "Humanoid": CLASS.format(name="Humanoid", props="WalkSpeed, Health", methods="LoadAnimation, TakeDamage", events="Died"),
    "Player": CLASS.format(name="Player", props="UserId, Character", methods="Kick", events="CharacterAdded"),
    "RemoteEvent": CLASS.format(name="RemoteEvent", props="", methods="FireServer", events="OnServerEvent"),
    "Part": CLASS.format(name="Part", props="Anchored", methods="Destroy", events="Touched"),
    # members
    "GuiService:GetGuiInset": "GuiService:GetGuiInset(): Vector2",
    "GuiService.TopbarInset": "GuiService.TopbarInset: Rect",
    "GuiService:GetPropertyChangedSignal": "Instance:GetPropertyChangedSignal(property)",   # inherited
    "TweenService:Create": "TweenService:Create(...)",
    "Players.PlayerAdded": "Players.PlayerAdded(player)", "Players.PlayerRemoving": "Players.PlayerRemoving(player)",
    "Players:GetPlayers": "Players:GetPlayers()", "Players.LocalPlayer": "Players.LocalPlayer: Player",
    "DataModel:BindToClose": "DataModel:BindToClose(fn)", "DataModel:GetService": "DataModel:GetService(name)",
    "Workspace.Gravity": "Workspace.Gravity: number", "Workspace:Raycast": "Workspace:Raycast(...)",
    "Camera.ViewportSize": "Camera.ViewportSize: Vector2",
    "UIScale.Scale": "UIScale.Scale: float", "IKControl.SmoothTime": "IKControl.SmoothTime: float",
    "IKControl.Weight": "IKControl.Weight: float",
    "TextLabel.Text": "TextLabel.Text: string", "TextLabel.TextScaled": "TextLabel.TextScaled: boolean",
    "Humanoid.WalkSpeed": "Humanoid.WalkSpeed: float", "Humanoid:TakeDamage": "Humanoid:TakeDamage(n)",
    "Humanoid.Died": "Humanoid.Died()", "Player:Kick": "Player:Kick(message)", "Player.UserId": "Player.UserId: int64",
    "Part.Anchored": "Part.Anchored: boolean", "Part.Touched": "Part.Touched(hit)", "Part:Destroy": "Part:Destroy()",
    "Enum.EasingStyle": "Enum.EasingStyle", "Enum.EasingStyle.Quad": "Enum.EasingStyle",
    "math.floor": "math.floor(x)", "math.isfinite": "math.isfinite(x)", "task.wait": "task.wait(n)",
    "Vector3.new": "Vector3.new(x, y, z)", "Instance.new": "Instance.new(className)",
}
DEPRECATED_TEXT = {"Humanoid:LoadAnimation": "Humanoid:LoadAnimation(animation)\n\nTags: Deprecated. DEPRECATED: This "
                                             "function is deprecated in favor of using\n`Animator:LoadAnimation()` "
                                             "directly (the Animator may be created at runtime)."}


class Reference:
    """A stand-in for KnowledgeClient.api_lookup that records what it was asked."""

    def __init__(self):
        self.asked = []

    def __call__(self, symbols):
        assert 1 <= len(symbols) <= 8, "the service takes at most 8 names per request"
        self.asked.extend(symbols)
        out = []
        for symbol in symbols:
            if symbol in DEPRECATED_TEXT:
                out.append({"symbol": symbol, "found": True, "deprecated": True, "text": DEPRECATED_TEXT[symbol]})
            elif symbol in REFERENCE:
                out.append({"symbol": symbol, "found": True, "deprecated": False, "text": REFERENCE[symbol]})
            else:
                out.append({"symbol": symbol, "found": False})
        return out


def kinds(findings):
    return [(f["kind"], f["line"]) for f in findings]


# --- reading the code ---------------------------------------------------------------------------

def test_comments_and_strings_are_blanked_without_moving_anything():
    code = 'local a = "x:Kick()" -- p:Kick()\n--[[ q:Kick()\n more ]] local b = [[r:Kick()]]\nlocal c = `{a}:Kick()`\n'
    bare = blank(code)
    assert len(bare) == len(code) and bare.count("\n") == code.count("\n")
    assert "Kick" not in bare and "local a =" in bare and "local b =" in bare and "local c =" in bare
    kept = blank(code, strings=False)
    assert '"x:Kick()"' in kept and "p:Kick" not in kept and "q:Kick" not in kept and "[[r:Kick()]]" in kept


def test_a_receiver_has_a_class_only_when_the_code_says_so():
    code = '''
local Players = game:GetService("Players")
local remote = game:GetService("ReplicatedStorage"):WaitForChild("Buy")
local label = Instance.new("TextLabel")
local part = Instance.new("Part", workspace)
local humanoid = character:FindFirstChildOfClass("Humanoid")
local thing = character:FindFirstChild("Humanoid")
local cam: Camera = workspace.CurrentCamera
type Config = { speed: number }
local function hit(player: Player, cfg: Config, amount: number) end
'''
    found = receivers(code)
    assert found["Players"] == {"Players"} and found["label"] == {"TextLabel"} and found["part"] == {"Part"}
    assert found["humanoid"] == {"Humanoid"} and found["cam"] == {"Camera"} and found["player"] == {"Player"}
    assert found["game"] == {"DataModel"} and found["workspace"] == {"Workspace"}
    # the remote is whatever WaitForChild returns, a name alone proves nothing, and Config is the script's own type
    assert "remote" not in found and "thing" not in found and "cfg" not in found and "amount" not in found


def test_only_uses_with_solid_evidence_become_references():
    code = '''
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local label = Instance.new("TextLabel")
label.Text = "hi"                       -- assignment: a property
label.Fancy = true                      -- assignment: a property that does not exist
print(label.Whatever)                   -- a read could be a child instance: not checked
local remote = ReplicatedStorage.Remotes.Buy   -- children: not checked
Players.PlayerAdded:Connect(function() end)
Players:GetPlayers()
local style = Enum.EasingStyle.Quad
local n = math.floor(1.5)
-- label:Nope() in a comment, and "label:Nope()" in a string, are not code
local s = "label:Nope()"
'''
    shown = {r["shown"] for r in references(code)}
    assert {"label.Text", "label.Fancy", "Players.PlayerAdded", "Players:GetPlayers", "Enum.EasingStyle.Quad",
            "math.floor", "TextLabel", "Players", "ReplicatedStorage"} <= shown
    assert not {"label.Whatever", "ReplicatedStorage.Remotes", "label:Nope"} & shown


# --- asking the reference -------------------------------------------------------------------------

def test_an_invented_member_is_reported_with_the_real_members_as_a_hint():
    code = ('local GuiService = game:GetService("GuiService")\n'
            'local inset = GuiService:GetGuiInset()\n'
            'GuiService:GetPropertyChangedSignal("ViewportSize"):Connect(print)\n'
            'local size = GuiService:GetScreenResolution()\n')
    lookup = Reference()
    findings, checked = diagnose(code, lookup)
    assert kinds(findings) == [(UNKNOWN, 3), (UNKNOWN, 4)]
    assert "`GuiService.ViewportSize` is not in the official Roblox API reference" in findings[0]["message"]
    assert "class GuiService has no member `ViewportSize`" in findings[0]["message"]
    # the name exists, on another class: the hint says where and offers no list to pick a near spelling from
    assert findings[0]["hint"].startswith("`ViewportSize` is a member of Camera, not of GuiService")
    assert "TopbarInset" not in findings[0]["hint"]
    # a name that exists nowhere: the class's real members are the hint
    assert "is a member of" not in findings[1]["hint"]
    assert "GetGuiInset" in findings[1]["hint"] and "TopbarInset" in findings[1]["hint"]
    assert checked == 6, "GetService, the class, two real methods and the two invented members"


def test_invented_enum_items_classes_and_library_functions_are_reported():
    code = ('local t = Instance.new("TextLabell")\n'
            'local e = Enum.EasingStyle.Wobble\n'
            'local ok = math.isFinite(1)\n'
            'local fine = math.isfinite(1) and Enum.EasingStyle.Quad\n')
    findings, _ = diagnose(code, Reference())
    assert kinds(findings) == [(UNKNOWN, 1), (UNKNOWN, 2), (UNKNOWN, 3)]
    assert "not a class" in findings[0]["message"] and "no such enum" in findings[1]["message"]
    assert "`math.isFinite`" in findings[2]["message"]


def test_a_deprecated_member_is_an_advisory_that_names_the_replacement():
    code = ('local function play(humanoid: Humanoid, animation)\n'
            '\treturn humanoid:LoadAnimation(animation)\n'
            'end\n')
    findings, checked = diagnose(code, Reference())
    assert kinds(findings) == [(DEPRECATED, 2)] and checked == 1
    assert "deprecated" in findings[0]["message"] and "Animator:LoadAnimation()" in findings[0]["message"]
    assert DEPRECATED in api_check.ADVISORY_KINDS and UNKNOWN not in api_check.ADVISORY_KINDS


def test_correct_code_and_code_with_nothing_to_check_produce_no_findings():
    good = ('local Players = game:GetService("Players")\n'
            'Players.PlayerRemoving:Connect(function(player: Player) player:Kick("bye") end)\n'
            'game:BindToClose(function() task.wait(1) end)\n'
            'workspace.Gravity = 50\n')
    findings, checked = diagnose(good, Reference())
    assert findings == [] and checked >= 5
    assert diagnose("local function add(a: number, b: number): number\n\treturn a + b\nend\n", Reference()) == ([], 0)


def test_the_scripts_own_types_and_unknown_owners_are_never_judged():
    code = ('type Signal = { Fire: (self: Signal) -> () }\n'
            'local function go(signal: Signal, pool: BulletPool)\n'
            '\tsignal:Fire()\n\tpool:get()\nend\n')
    assert diagnose(code, Reference()) == ([], 0)


def test_a_name_bound_to_two_classes_is_fine_when_either_has_the_member():
    code = ('local a = Instance.new("TextLabel")\na.Text = "x"\n'
            'local function f()\n\tlocal a = Instance.new("Part")\n\ta.Anchored = true\nend\n')
    assert diagnose(code, Reference())[0] == []


def test_a_lookup_failure_is_the_callers_to_handle():
    def down(symbols):
        raise OSError("knowledge is down")

    with pytest.raises(OSError):
        diagnose('local p = Instance.new("Part")\np.Anchored = true\n', down)


# --- names the request asks for -----------------------------------------------------------------

def test_pasted_code_is_not_part_of_what_the_request_says():
    prompt = ("Rewrite this so it uses a UIScale.\n\n"
              'local gui = Instance.new("ScreenGui")\n'
              "gui.Parent = Players.LocalPlayer:WaitForChild(\"PlayerGui\")\n"
              "panel.Size = UDim2.fromOffset(500, 300)\n")
    prose = prose_of_request(prompt)
    assert "UIScale" in prose and "ScreenGui" not in prose and "fromOffset" not in prose


@pytest.mark.parametrize("prompt, expected", [
    ("Rewrite it so the panel scales: use a UIScale driven by the camera's ViewportSize.", ["UIScale"]),
    ("Reach the door using the official IKControl instance and give it a SmoothTime so the arm does not snap.",
     ["IKControl", "SmoothTime"]),
    ("Fade the weight with TweenService and flush every player in game:BindToClose.",
     ["TweenService", "BindToClose"]),
    ("Write a module whose forget() is connected to Players.PlayerRemoving.", ["PlayerRemoving"]),
    # background, containers, negations and names the reference does not know are not requests
    ("StreamingEnabled is on in our place. Make this LocalScript safe.", []),
    ("Write a LocalScript (for StarterPlayerScripts) that builds a ScreenGui in the player's PlayerGui.", []),
    ("Save with UpdateAsync, do not use a RemoteEvent and never call Humanoid:LoadAnimation.", []),
    ("Players fire the RemoteEvent UseAbility. Write a server ModuleScript AbilityGate.", []),
    ("Use my InventoryHud helper with the CoolWidget module.", []),
])
def test_requested_names_need_a_directive_and_a_reference_entry(prompt, expected):
    assert [item["name"] for item in requested_names(prompt, Reference())] == expected


def test_a_class_that_usually_already_exists_counts_only_when_one_is_to_be_made():
    # "with a RemoteEvent" may be an existing object reached by its path; "create a RemoteEvent" is not.
    assert requested_names("Send the result back with a RemoteEvent.", Reference()) == []
    assert [i["name"] for i in requested_names("Create a RemoteEvent for the result.", Reference())] == ["RemoteEvent"]


def test_a_requested_name_is_missing_only_when_no_block_uses_it():
    requested = requested_names("Use a UIScale and give the IKControl a SmoothTime.", Reference())
    uses = 'local scale = Instance.new("UIScale")\nik.SmoothTime = 0.2 -- IKControl\n'
    assert missing_requested(requested, ["local x = 1\n", uses]) == [
        f for f in missing_requested(requested, [uses]) if "IKControl`" in f["message"]]
    comment_only = "-- a UIScale would go here, with SmoothTime\nlocal x = 1\n"
    missing = missing_requested(requested, [comment_only])
    assert [f["kind"] for f in missing] == [REQUESTED] * len(missing) and len(missing) >= 2
    assert "the code never uses `UIScale`" in missing[0]["message"] and "only background" in missing[0]["hint"]
