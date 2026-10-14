Two problems, both GLSL ES rules that desktop GLSL does not have:

1. In GLSL ES the fragment stage has **no default float precision**, so every float declaration in it is an error until you set one. Add `precision highp float;` (or `precision mediump float;` if you want speed on mobile) right after the `#version 300 es` line. The vertex stage already defaults to highp, which is why only the fragment shader fails.
2. `float boost = 2;` is also an error in GLSL ES: there is no implicit int-to-float conversion. Write the float literal `2.0`.

```glsl
#version 300 es
precision highp float;
uniform sampler2D uTex;
in vec2 vUv;
out vec4 fragColor;
void main() { float boost = 2.0; fragColor = texture(uTex, vUv) * boost; }
```

Keep `#version 300 es` as the very first line: WebGL 2 only accepts GLSL ES 3.00.
