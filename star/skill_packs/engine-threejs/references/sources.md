# Sources for engine-threejs

Official documentation reviewed 2026-10-13 (accessed by web, not by a live engine run):

- https://github.com/mrdoob/three.js/releases (r183-r186 release notes; PCFSoftShadowMap removal, TextureSource rename, Object3D.dispose in r186)
- https://github.com/mrdoob/three.js/wiki/Migration-Guide (Geometry removal r125, BufferGeometry aliases r144, examples/js removal r148, color management r152, legacy lights r155, Clock to Timer r183, TSL renames)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/installation.html (npm + Vite, import map, three/addons)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/webgpurenderer.html (three/webgpu, WebGL 2 fallback, init/setAnimationLoop, unsupported ShaderMaterial/onBeforeCompile/EffectComposer)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/physics.html (physics addons, Rapier, cannon-es status)
- https://raw.githubusercontent.com/mrdoob/three.js/dev/manual/pages/how-to-dispose-of-objects.html (dispose rules)
- https://raw.githubusercontent.com/mrdoob/three.js/r186/src/core/Timer.js (Timer API)
- https://registry.npmjs.org/three (0.186.x version, dates and package exports)

These are documentation references; no editor/compiler run is claimed for the skeleton.
