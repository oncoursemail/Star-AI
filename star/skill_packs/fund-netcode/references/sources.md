# Sources for fund-netcode

Distilled from the long-form research note `docs/research/fundamentals/multiplayer-netcode.md` (researched 2026-10-13; a copy ships as `references/notes.md` so Agent mode can read it with star_skill_reference). Primary sources (papers, official documentation, talks by the engineers who shipped the technique, standards bodies) come first; secondary write-ups are marked as such. This pack is engine- and language-independent: it names no engine API, so there is nothing to verify with the knowledge service /api-lookup.

- Gabriel Gambetta, Fast-Paced Multiplayer series: Part I https://www.gabrielgambetta.com/client-server-game-architecture.html ; Part II prediction and reconciliation https://www.gabrielgambetta.com/client-side-prediction-server-reconciliation.html ; Part III entity interpolation https://www.gabrielgambetta.com/entity-interpolation.html ; Part IV lag compensation https://www.gabrielgambetta.com/lag-compensation.html
- Valve, "Source Multiplayer Networking": https://developer.valvesoftware.com/wiki/Source_Multiplayer_Networking
- Valve, "Lag Compensation": https://developer.valvesoftware.com/wiki/Lag_Compensation
- Yahn Bernier, "Latency Compensating Methods in Client/Server In-game Protocol Design and Optimization" (2001): https://developer.valvesoftware.com/wiki/Latency_Compensating_Methods_in_Client/Server_In-game_Protocol_Design_and_Optimization
- Glenn Fiedler, Networked Physics series (deterministic lockstep, snapshot interpolation, state synchronization): https://gafferongames.com/categories/networked-physics/ ; "Snapshot Interpolation": https://gafferongames.com/post/snapshot_interpolation/
- Glenn Fiedler, Building a Game Network Protocol series: https://gafferongames.com/categories/building-a-game-network-protocol/
- Timothy Ford, "Overwatch Gameplay Architecture and Netcode" (GDC 2017): https://gdcvault.com/play/1024001/-Overwatch-Gameplay-Architecture-and
- Riot Games tech blog, "VALORANT's 128-Tick Servers": https://technology.riotgames.com/news/valorants-128-tick-servers
- Riot Games tech blog, "Peeking into VALORANT's Netcode": https://technology.riotgames.com/news/peeking-valorants-netcode
- Infil, "Netcode: explaining how fighting games use delay-based and rollback netcode": https://words.infil.net/w02-netcode.html
- GGPO (rollback networking SDK): https://github.com/pond3r/ggpo
- GGRS (Rust rollback): https://github.com/gschup/ggrs
- Mark Terrano and Paul Bettner, "1500 Archers on a 28.8: Network Programming in Age of Empires and Beyond": https://www.gamedeveloper.com/programming/1500-archers-on-a-28-8-network-programming-in-age-of-empires-and-beyond
- Unreal Engine, Networking overview and Replication Graph / Iris: https://dev.epicgames.com/documentation/en-us/unreal-engine/networking-overview-for-unreal-engine
- Unity Netcode for Entities (prediction, ghost relevancy): https://docs.unity3d.com/Packages/com.unity.netcode@1.3/manual/index.html
- Photon Fusion interest management (secondary engine example): https://doc.photonengine.com/fusion-unreal/v3/manual/replication/interest-management
- Roblox, client-server security model (example of server authority): https://create.roblox.com/docs/scripting/security/security-tactics
