# Sources for fund-rendering-physics

Distilled from the long-form research note `docs/research/fundamentals/rendering-physics-animation.md` (researched 2026-10-13; a copy ships as `references/notes.md` so Agent mode can read it with star_skill_reference). Primary sources (papers, official documentation, talks by the engineers who shipped the technique, standards bodies) come first; secondary write-ups are marked as such. This pack is engine- and language-independent: it names no engine API, so there is nothing to verify with the knowledge service /api-lookup.

- Akenine-Moeller, Haines, Hoffman et al., *Real-Time Rendering*, 4th ed. (resources): https://www.realtimerendering.com/
- Olsson, Billeter, Assarsson, "Clustered Deferred and Forward Shading" (HPG 2012), preprint: https://www.cse.chalmers.se/~uffe/clustered_shading_preprint.pdf
- Olsson et al., "Tiled and clustered forward shading: supporting transparency and MSAA": https://research.chalmers.se/en/publication/161726
- Brian Karis, "Real Shading in Unreal Engine 4" (SIGGRAPH 2013 course notes): https://cdn2.unrealengine.com/Resources/files/2013SiggraphPresentationsNotes-26915738.pdf
- LearnOpenGL, PBR theory: https://learnopengl.com/PBR/Theory
- Physically Based Rendering: From Theory to Implementation, 4th ed. (free online): https://pbr-book.org/
- Microsoft, "Common Techniques to Improve Shadow Depth Maps": https://learn.microsoft.com/en-us/windows/win32/dxtecharts/common-techniques-to-improve-shadow-depth-maps
- Microsoft, "Cascaded Shadow Maps": https://learn.microsoft.com/en-us/windows/win32/dxtecharts/cascaded-shadow-maps
- Epic Games, "Unreal Engine 5 goes all-in on dynamic global illumination with Lumen": https://www.unrealengine.com/en-US/tech-blog/unreal-engine-5-goes-all-in-on-dynamic-global-illumination-with-lumen
- Epic Games, MegaLights documentation: https://dev.epicgames.com/documentation/unreal-engine/megalights-in-unreal-engine
- Guru3D (secondary), "Unreal Engine 5.8 Debuts Lumen Lite and Production-Ready MegaLights": https://www.guru3d.com/story/unreal-engine-58-debuts-lumen-lite-and-productionready-megalights/
- Bitterli et al., ReSTIR (SIGGRAPH 2020): https://benedikt-bitterli.me/restir/
- Majercik et al., DDGI (JCGT 2019): https://jcgt.org/published/0008/02/01/
- Erin Catto, Box2D publications and GDC talks: https://box2d.org/publications/
- Erin Catto, "Solver2D" (2024): https://box2d.org/posts/2024/02/solver2d/
- Erin Catto, "Soft Constraints" (GDC 2011): https://box2d.org/files/ErinCatto_SoftConstraints_GDC2011.pdf
- Jolt Physics documentation (architecture, deterministic simulation): https://jrouwe.github.io/JoltPhysics/
- Christer Ericson, *Real-Time Collision Detection*: https://realtimecollisiondetection.net/
- Glenn Fiedler, "Integration Basics": https://gafferongames.com/post/integration_basics/
- Mueller et al., XPBD: https://matthias-research.github.io/pages/publications/XPBD.pdf
- Aristidou and Lasenby, FABRIK: https://www.andreasaristidou.com/FABRIK
- Simon Clavet, "Motion Matching and The Road to Next-Gen Animation" (GDC 2016): https://gdcvault.com/play/1023280/Motion-Matching-and-The-Road
- Holden, Kanoun, Perepichka, Popa, "Learned Motion Matching" (SIGGRAPH 2020): https://theorangeduck.com/page/learned-motion-matching
- Daniel Holden, "Code vs Data Driven Displacement" and other animation articles: https://theorangeduck.com/page/code-vs-data-driven-displacement
- Animation Compression Library (ACL): https://github.com/nfrechette/acl
- Kavan et al., dual quaternion skinning: https://users.cs.utah.edu/~ladislav/kavan07skinning/kavan07skinning.html
