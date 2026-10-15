Without a `#language` line Slang uses the `legacy` language version, where declarations are visible to importers. Since language version 2025 (and therefore in 2026) the default visibility is **internal**: a declaration is visible everywhere inside its own module but not to modules that `import` it. `lambert` has no modifier, so `main.slang` cannot see it.

Mark the function `public`:

```slang
// lighting.slang
#language slang 2026
module lighting;
public float3 lambert(float3 albedo) { return albedo / 3.14159; }
```

Keep the `module lighting;` declaration: 2025 and later require it. Also mark any struct or interface you want to share as `public`; in 2026 its unmodified members then inherit that visibility, while explicit `private` or `internal` members stay hidden.
