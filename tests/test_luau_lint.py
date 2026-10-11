"""Offline tests for the standalone Luau linter."""
import pytest

from star.luau_lint import Finding, lint


@pytest.mark.parametrize(("rule", "bad", "good"), [["deprecated-task-global","wait(1)","task.wait(1)"],["instance-parent-argument","Instance.new(\"Part\", workspace)","local p = Instance.new(\"Part\")\np.Parent = workspace"],["service-property","game.Players","game:GetService(\"Players\")"],["loop-without-yield","while true do print(1) end","while true do task.wait(1) end"],["datastore-unprotected","store:GetAsync(\"x\")","pcall(function() return store:GetAsync(\"x\") end)"],["datastore-read-set","function save() store:GetAsync(\"x\") store:SetAsync(\"x\", 2) end","function save() store:UpdateAsync(\"x\", function(v) return v end) end"],["humanoid-load-animation","Humanoid:LoadAnimation(anim)","animator:LoadAnimation(anim)"],["touched-debounce","part.Touched:Connect(function(hit) print(hit) end)","part.Touched:Connect(function(hit) if busy then return end busy = true end)"],["remote-unvalidated","remote.OnServerEvent:Connect(function(player, amount) coins.Value += amount end)","remote.OnServerEvent:Connect(function(player, amount) if typeof(amount) ~= \"number\" then return end coins.Value += amount end)"],["loop-connection","while true do part.Touched:Connect(onTouch) task.wait() end","while true do local conn = part.Touched:Connect(onTouch) conn:Disconnect() task.wait() end"],["unchecked-find-child","workspace:FindFirstChild(\"Foo\").Name","local foo = workspace:FindFirstChild(\"Foo\")\nif foo then print(foo.Name) end"],["mixed-client-server","print(game:GetService(\"ServerStorage\"), game.Players.LocalPlayer)","print(game:GetService(\"Players\").LocalPlayer)"]])
def test_positive_and_negative(rule, bad, good):
    assert rule in {f.rule_id for f in lint(bad)}
    assert rule not in {f.rule_id for f in lint(good)}


@pytest.mark.parametrize("source", [
    "-- wait(1)\n",
    "--[[ game.Players wait(1) ]]",
    "--[==[ Instance.new('Part', workspace) ]==]",
    "local x = 'game.Players wait(1)'",
    'local x = "Humanoid:LoadAnimation(anim)"',
    "local x = [=[ workspace:FindFirstChild('x').Name ]=]",
    '--[=[ while true do print(1) end ]=]',
    'local s = "escaped \\" wait(1)"',
])
def test_comment_and_string_contents_are_ignored(source):
    assert lint(source) == []


def test_line_numbers_and_deterministic_order():
    source = "-- comment\nlocal x = [[wait(3)]]\nwait(1)\n"
    assert lint(source) == [Finding(
        "deprecated-task-global", 3, "Deprecated global wait().",
        "Use task.wait().", "warning")]
    assert lint(source) == lint(source)


def test_code_is_never_executed():
    assert lint('require(12345)\nloadstring("error()")') == []
    with pytest.raises(TypeError):
        lint(None)


CORRECT_SCRIPTS = ["local Players = game:GetService(\"Players\")\nPlayers.PlayerAdded:Connect(function(player) print(player.Name) end)","local p = Instance.new(\"Part\")\np.Name = \"Ready\"\np.Parent = workspace","task.spawn(function() while true do task.wait(1) end end)","local a = game:GetService(\"TweenService\")\nprint(a)","local result = workspace:FindFirstChild(\"Door\")\nif result then result.Transparency = 0 end","local animator = humanoid:FindFirstChildOfClass(\"Animator\")\nif animator then animator:LoadAnimation(animation) end","local ok, result = pcall(function() return store:GetAsync(\"Key\") end)\nif ok then print(result) end","pcall(function() store:UpdateAsync(\"Key\", function(old) return (old or 0) + 1 end) end)","remote.OnServerEvent:Connect(function(player, amount) if typeof(amount) ~= \"number\" then return end if amount < 0 or amount > 10 then return end print(amount) end)","part.Touched:Connect(function(hit) if debounce then return end debounce = true task.delay(1, function() debounce = false end) end)"]


@pytest.mark.parametrize("script", CORRECT_SCRIPTS)
def test_ten_idiomatic_scripts_have_no_error_or_warning(script):
    assert not [f for f in lint(script) if f.severity in ("error", "warning")]


def test_finite_repeat_does_not_need_yield():
    assert "loop-without-yield" not in {finding.rule_id for finding in lint(
        "repeat attempts += 1 until attempts >= 3")}
    assert "loop-without-yield" not in {finding.rule_id for finding in lint(
        "repeat print('once') until true")}
    assert "loop-without-yield" in {finding.rule_id for finding in lint(
        "repeat print('spin') until false")}
