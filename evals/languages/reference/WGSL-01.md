Two WGSL layout rules are involved:

- In the `uniform` address space every array element must sit on a 16-byte stride, so `array<f32, 4>` (stride 4) is rejected. Each `f32` would need its own 16-byte slot.
- `vec3f` has size 12 but alignment 16. Your `intensity : f32` happens to fit into the 4 bytes after `color` (offset 12), so that part is fine, but you must not assume vec3 values are packed back to back elsewhere.

Fix the shader by packing the four weights into one `vec4f` (or use `array<vec4f, 1>`, or move the data to a `var<storage, read>` buffer, which allows a 4-byte stride):

```wgsl
struct Params {
    color     : vec3f,   // offset 0
    intensity : f32,     // offset 12
    weights   : vec4f,   // offset 16
};
@group(0) @binding(0) var<uniform> params : Params;
```

On the JavaScript side the struct is now 32 bytes: write color at float offset 0..2, intensity at offset 3, weights at offsets 4..7 of a Float32Array(8). If you had kept `array<f32, 4>` with `@align(16)` per element instead, the JS buffer would need padding after every weight. Compute offsets from the WGSL layout (webgpu-utils can do it) rather than by hand.
