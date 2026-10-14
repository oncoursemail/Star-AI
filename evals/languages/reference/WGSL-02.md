`textureSample` picks a mip level from **implicit derivatives**: the GPU runs fragments in 2x2 quads and compares the UVs of neighbouring fragments. If some fragments of a quad take the `if` and others do not, those derivatives are undefined. WGSL's uniformity analysis therefore requires `textureSample` (and `dpdx`, `dpdy`, `fwidth`) to be called only in uniform control flow, and `in.mask` is a per-fragment input, so the branch is non-uniform and the shader is rejected at compile time. This is the language rule working as designed, not a defect.

Fix it by sampling before the branch, so every fragment of the quad executes the sample, and branching on the result:

```wgsl
let c = textureSample(tex, smp, in.uv);
if (in.mask > 0.5) { return c; }
return vec4f(0.0);
```

If you really need the sample inside the branch, use `textureSampleLevel(tex, smp, in.uv, 0.0)` (explicit LOD) or `textureSampleGrad` with derivatives computed outside the branch; those do not need uniform control flow. Turning the check off with `diagnostic(off, derivative_uniformity)` only hides the problem.
