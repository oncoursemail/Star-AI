errdefer |err| still works in 0.17; the error is that std.log.err needs `{any}` instead of `{s}`.
