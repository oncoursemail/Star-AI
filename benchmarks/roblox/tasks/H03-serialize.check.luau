local M = solution()
local HttpServiceForJson = game:GetService("HttpService")
local original = {
	name = "base",
	level = 3,
	alive = true,
	spawn = Vector3.new(1.5, -2, 300),
	pose = CFrame.new(10, 20, 30) * CFrame.Angles(0.3, 1.2, -0.5),
	tint = Color3.new(0.25, 0.5, 1),
	list = { Vector3.new(1, 2, 3), "x", { deep = Color3.fromRGB(10, 20, 30) } },
}
local back
check("JSON round trip works", function()
	local json = HttpServiceForJson:JSONEncode(M.encode(original))
	back = M.decode(HttpServiceForJson:JSONDecode(json))
	expect(type(back) == "table", "decode did not return a table")
end)
check("plain values", function()
	expect(back.name == "base" and back.level == 3 and back.alive == true, "plain values")
end)
check("Vector3", function()
	expect(typeof(back.spawn) == "Vector3" and (back.spawn - original.spawn).Magnitude < 1e-4, "Vector3")
end)
check("CFrame with rotation", function()
	expect(typeof(back.pose) == "CFrame", "type " .. typeof(back.pose))
	expect((back.pose.Position - original.pose.Position).Magnitude < 1e-4, "position")
	expect(back.pose.LookVector:Dot(original.pose.LookVector) > 0.9999, "rotation (look)")
	expect(back.pose.UpVector:Dot(original.pose.UpVector) > 0.9999, "rotation (up)")
end)
check("Color3", function()
	expect(typeof(back.tint) == "Color3" and near(back.tint.G, 0.5, 1e-4), "Color3")
end)
check("nested array and table", function()
	expect(typeof(back.list[1]) == "Vector3" and back.list[2] == "x", "array items")
	expect(typeof(back.list[3].deep) == "Color3" and near(back.list[3].deep.R, 10 / 255, 1e-3), "nested Color3")
end)
