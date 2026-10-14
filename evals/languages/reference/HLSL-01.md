HLSL packs `float4x4` members of a constant buffer **column-major** by default. Your CPU library writes the 16 floats row by row, so when the shader reads them as columns it sees the transpose of the matrix you built. `mul(ViewProj, v)` then applies that transposed matrix, which skews the mesh.

Pick one convention and use it end to end. Any one of these fixes it:

- Declare the member `row_major float4x4 ViewProj;` (or compile with `-Zpr`) so the shader reads the rows you wrote, and keep `mul(ViewProj, v)` only if your CPU matrix is built for column vectors; with a row-vector library use `mul(v, ViewProj)`.
- Or transpose the matrix on the CPU before the upload (DirectXMath's `XMMatrixTranspose`) and keep the default column-major packing.
- Or keep the upload as is and swap the arguments of `mul`, because `mul(v, M)` treats `v` as a row vector, which is the same as multiplying by the transpose.

```hlsl
cbuffer Frame : register(b0) { row_major float4x4 ViewProj; };
output.pos = mul(float4(input.pos, 1), ViewProj);   // row-vector convention, matches a row-major library
```

Do not mix fixes: transposing on upload *and* adding `row_major` cancels out.
