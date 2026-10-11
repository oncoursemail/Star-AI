```luau
--!strict
local Easing = {}
function Easing.linear(t: number): number return t end
function Easing.inQuad(t: number): number return t * t end
function Easing.outQuad(t: number): number return 1 - (1 - t) * (1 - t) end
function Easing.inOutQuad(t: number): number return t < 0.5 and 2 * t * t or 1 - (-2 * t + 2) ^ 2 / 2 end
function Easing.outCubic(t: number): number return 1 - (1 - t) ^ 3 end
function Easing.outBack(t: number): number return t end
function Easing.outElastic(t: number): number return t end
function Easing.lerp(a: number, b: number, t: number, name: string?): number return a + (b - a) * t end
return Easing
```
