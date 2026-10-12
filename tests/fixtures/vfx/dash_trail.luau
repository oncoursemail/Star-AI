return build({
    name = "Dash",
    cleanup_after = 0.6,
    effects = {
        {
            id = "ribbon",
            class = "Trail",
            at = 0,
            duration = 0.3,
            tail = 0.25,
            attachments = {Vector3.new(-0.5, 0, 0), Vector3.new(0.5, 0, 0)},
            properties = {
                {"Color", ColorSequence.new({ColorSequenceKeypoint.new(0, Color3.new(1, 1, 1)), ColorSequenceKeypoint.new(1, Color3.new(0.2, 0.5, 1))})},
                {"FaceCamera", true},
                {"Lifetime", 0.25},
                {"LightEmission", 0.7},
                {"LightInfluence", 0},
                {"MaxLength", 10},
                {"MinLength", 0.1},
                {"Texture", "rbxasset://textures/particles/sparkles_main.dds"},
                {"TextureLength", 1},
                {"TextureMode", Enum.TextureMode.Stretch},
                {"Transparency", NumberSequence.new({NumberSequenceKeypoint.new(0, 0.1, 0), NumberSequenceKeypoint.new(1, 1, 0)})},
                {"WidthScale", NumberSequence.new({NumberSequenceKeypoint.new(0, 1, 0), NumberSequenceKeypoint.new(1, 0, 0)})},
            },
            tweens = {
            },
        },
    },
})
