Since Zig **0.15**, `std.ArrayList` is the **unmanaged** list: it no longer stores the allocator, so there is no
`init(allocator)`. You initialize it with the `.empty` decl literal and pass the allocator to every method that may
allocate or free, for example `append(gpa, x)` and `deinit(gpa)`. (The old managed type survives as
`std.array_list.Managed`, but new code should not use it.) In 0.16+ the usual allocator comes from `init.gpa` in
`main`.

```zig
const std = @import("std");

pub fn main(init: std.process.Init) !void {
    const gpa = init.gpa;
    var list: std.ArrayList(u8) = .empty;
    defer list.deinit(gpa);
    try list.append(gpa, 'a');
}
```
