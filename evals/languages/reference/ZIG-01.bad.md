Nothing changed for ArrayList; the managed ArrayList is still the default. You probably forgot `try`:
`var list = try std.ArrayList(u8).init(allocator);`.
