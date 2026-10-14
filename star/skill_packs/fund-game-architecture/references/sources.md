# Sources for fund-game-architecture

Distilled from the long-form research note `docs/research/fundamentals/game-architecture-and-ai.md` (researched 2026-10-13; a copy ships as `references/notes.md` so Agent mode can read it with star_skill_reference). Primary sources (papers, official documentation, talks by the engineers who shipped the technique, standards bodies) come first; secondary write-ups are marked as such. This pack is engine- and language-independent: it names no engine API, so there is nothing to verify with the knowledge service /api-lookup.

- Glenn Fiedler, "Fix Your Timestep!": https://gafferongames.com/post/fix_your_timestep/
- Robert Nystrom, *Game Programming Patterns*: Game Loop https://gameprogrammingpatterns.com/game-loop.html ; Update Method https://gameprogrammingpatterns.com/update-method.html ; Component https://gameprogrammingpatterns.com/component.html ; Observer https://gameprogrammingpatterns.com/observer.html ; Event Queue https://gameprogrammingpatterns.com/event-queue.html ; State https://gameprogrammingpatterns.com/state.html ; Command https://gameprogrammingpatterns.com/command.html ; Data Locality https://gameprogrammingpatterns.com/data-locality.html
- Jason Gregory, *Game Engine Architecture*, 3rd ed. (book site): https://www.gameenginebook.com/
- Timothy Ford, "Overwatch Gameplay Architecture and Netcode" (GDC 2017): https://gdcvault.com/play/1024001/-Overwatch-Gameplay-Architecture-and
- Sander Mertens, Flecs documentation and ECS FAQ: https://www.flecs.dev/flecs/md_docs_2FAQ.html
- Unity Entities (DOTS) manual: https://docs.unity3d.com/Packages/com.unity.entities@1.3/manual/index.html
- Bevy ECS (component storage): https://docs.rs/bevy_ecs/latest/bevy_ecs/
- EnTT wiki (sparse sets): https://github.com/skypjack/entt/wiki
- "Archetypal ECS Considered Harmful?" (secondary, trade-offs): https://moonside.games/posts/archetypal-ecs-considered-harmful/
- Damian Isla, "Handling Complexity in the Halo 2 AI" (GDC 2005, Game Developer article): https://www.gamedeveloper.com/programming/gdc-2005-proceeding-handling-complexity-in-the-i-halo-2-i-ai
- Colledanchise and Oegren, *Behavior Trees in Robotics and AI* (arXiv): https://arxiv.org/abs/1709.00084
- Unreal Engine Behavior Tree overview: https://dev.epicgames.com/documentation/en-us/unreal-engine/behavior-tree-in-unreal-engine---overview
- Jeff Orkin, "Three States and a Plan: The A.I. of F.E.A.R." (GDC 2006): https://gdcvault.com/play/1013282/Three-States-and-a-Plan
- Jeff Orkin, "Three States and a Plan" paper (PDF mirror): https://www.gamedevs.org/uploads/three-states-plan-ai-of-fear.pdf
- Dave Mark and Mike Lewis, "Building a Better Centaur: AI at Massive Scale" (GDC 2015, IAUS): https://gdcvault.com/play/1021848/Building-a-Better-Centaur-AI
- Kevin Dill, Dave Mark, "Improving AI Decision Modeling Through Utility Theory" (GDC 2010): https://gdcvault.com/play/1012410/Improving-AI-Decision-Modeling-Through
- Game AI Pro (free online chapters): https://www.gameaipro.com/
- Amit Patel, Red Blob Games, Introduction to A*: https://www.redblobgames.com/pathfinding/a-star/introduction.html ; Amit's A* pages (heuristics): https://theory.stanford.edu/~amitp/GameProgramming/Heuristics.html
- Red Blob Games, flow field pathfinding for tower defense: https://www.redblobgames.com/pathfinding/tower-defense/
- Elijah Emerson, "Crowd Pathfinding and Steering Using Flow Field Tiles" (Game AI Pro, ch. 23): https://www.gameaipro.com/GameAIPro/GameAIPro_Chapter23_Crowd_Pathfinding_and_Steering_Using_Flow_Field_Tiles.pdf
- Harabor and Grastien, Jump Point Search: https://users.cecs.anu.edu.au/~dharabor/data/papers/harabor-grastien-aaai11.pdf
- Recast & Detour navigation mesh toolset: https://recastnav.com/ and https://github.com/recastnavigation/recastnavigation
- Craig Reynolds, steering behaviors: https://www.red3d.com/cwr/steer/
- van den Berg et al., RVO2 / ORCA: https://gamma.cs.unc.edu/RVO2/
- Maxim Gumin, WaveFunctionCollapse: https://github.com/mxgmn/WaveFunctionCollapse
- Red Blob Games, noise-based terrain: https://www.redblobgames.com/maps/terrain-from-noise/
- PCG book, Shaker, Togelius, Nelson, *Procedural Content Generation in Games* (free): https://www.pcgbook.com/
