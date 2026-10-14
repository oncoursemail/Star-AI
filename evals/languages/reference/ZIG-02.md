Zig **0.17 removed the `errdefer |err|` capture**: an `errdefer` can still run cleanup on the error path, but it can no
longer bind the error value. The upgrade guide says to split the function: keep the work in an inner function and let a
small wrapper handle the error with `catch |err|`.

```zig
fn load(gpa: std.mem.Allocator, path: []const u8) !Level {
    return loadInner(gpa, path) catch |err| {
        std.log.err("load failed: {s}", .{@errorName(err)});
        return err;
    };
}

fn loadInner(gpa: std.mem.Allocator, path: []const u8) !Level {
    const buf = try gpa.alloc(u8, 4096);
    errdefer gpa.free(buf); // plain errdefer without a capture is still fine
    // ...
}
```
