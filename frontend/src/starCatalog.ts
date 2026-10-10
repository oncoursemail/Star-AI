/** Curated and inspectable source inventory; not a runtime health or benchmark claim. */
export type CapabilityStage='main'|'review'|'planned'
export type CapabilityArea='Intelligence'|'Creation'|'Integrations'|'Reliability'
export type Capability={
 id:string
 name:string
 area:CapabilityArea
 stage:CapabilityStage
 description:string
 detail:string
 pr?:number
}
export const capabilities:Capability[]=[
 {id:'local',name:'STAR Brain · Local AI',area:'Intelligence',stage:'main',
  description:'Local model download, inference checks and conversations.',
  detail:'Runs on-device with a supported model and sufficient hardware; Windows GPU acceptance is still required.'},
 {id:'memory',name:'Project memory',area:'Intelligence',stage:'main',
  description:'Chats, project references and saved knowledge.',
  detail:'Persistent data stays outside the replaceable installer directory.'},
 {id:'studio',name:'Roblox Studio MCP',area:'Creation',stage:'main',
  description:'Inspect and edit an authorized Studio test project.',
  detail:'Scoped permissions and human verification apply; not a promise of unattended full-game creation.'},
 {id:'vision',name:'Vision & references',area:'Creation',stage:'main',
  description:'Attach visual references and preserve project context.',
  detail:'Model-dependent understanding; reference interpretation still needs review.'},
 {id:'analytics',name:'Local task analytics',area:'Reliability',stage:'main',
  description:'Real project and task observations in the desktop app.',
  detail:'Uses local stored activity, not fabricated user traffic or invented benchmark scores.'},
 {id:'obsidian',name:'Obsidian vault reader',area:'Integrations',stage:'main',
  description:'Permissioned, read-only search and note inspection.',
  detail:'Merged source integration, opt-in, requires a selected vault; not necessarily in the latest installer.'},
 {id:'graphify',name:'Graphify knowledge graph',area:'Integrations',stage:'main',
  description:'Explore a local exported graph and its relationships.',
  detail:'Read-only, dependent on graph.json in the allowed project; not an active background crawler.'},
 {id:'skills',name:'Agent Skills',area:'Integrations',stage:'main',
  description:'Discover and load validated task-specific skills.',
  detail:'Skills provide instructions and references, not extra model weights or unrestricted permissions.'},
 {id:'github',name:'GitHub App workflow',area:'Integrations',stage:'main',
  description:'Scoped development integration and draft pull requests.',
  detail:'Present in source; depends on separately configured repository permissions.'},
 {id:'providers',name:'Open / free provider routing',area:'Intelligence',stage:'review',pr:28,
  description:'Optional hosted model routes with local-first fallback.',
  detail:'Proposed in the fast-brain PR; availability depends on provider policies and API access.'},
 {id:'search',name:'Web search & research',area:'Intelligence',stage:'review',pr:28,
  description:'Grounded external research with sources and bounds.',
  detail:'Under review for safer search results, citations and scoped network access.'},
 {id:'image',name:'In-chat image generation',area:'Creation',stage:'review',pr:28,
  description:'Create images from the conversation workspace.',
  detail:'Backend image adapters exist; integrated chat delivery is being reviewed.'},
 {id:'teams',name:'Parallel subagents',area:'Intelligence',stage:'review',pr:29,
  description:'Coordinate bounded specialist tasks and shared results.',
  detail:'In-development team runtime, not unlimited autonomous workers.'},
 {id:'evidence',name:'Source-ranked memory',area:'Intelligence',stage:'review',pr:29,
  description:'Promote traceable, verified context over unverified claims.',
  detail:'Proposed ranking and provenance work, with human oversight and test gates.'},
 {id:'learning',name:'Verified learning loop',area:'Reliability',stage:'review',pr:29,
  description:'Use measured task outcomes to improve later runs.',
  detail:'Not self-training model weights or silently rewriting core permissions.'},
 {id:'3d',name:'Blender + 3D pipeline',area:'Creation',stage:'planned',
  description:'Editable assets, mesh checks and generation workflows.',
  detail:'Research / planned integration; no shipped unattended 3D pipeline claim.'},
 {id:'animation',name:'Animation & video tools',area:'Creation',stage:'planned',
  description:'Specialized motion and media generation workflows.',
  detail:'Planned end-to-end UI, rig validation and production render checks.'},
 {id:'qa',name:'Roblox visual QA',area:'Reliability',stage:'planned',
  description:'Automated scene screenshots and gameplay acceptance checks.',
  detail:'Planned real Studio/device test harness; not currently validated on live games.'},
 {id:'extensions',name:'Expanded MCP connections',area:'Integrations',stage:'planned',
  description:'Discover and approve more tool servers from one place.',
  detail:'Future connector registry with explicit scopes, limits and revocation.'},
]
export const milestones=[
 {id:'foundation',number:'01',title:'Local-first foundation',subtitle:'Desktop, model setup, project data and Roblox tooling',
  body:'The working source foundation. Installer and GPU testing remain separate acceptance tasks.',pr:null},
 {id:'design',number:'02',title:'A more unified STAR',subtitle:'Conversation-first desktop workspace',
  body:'Refining the React experience so intelligence and tools feel like one product.',pr:27},
 {id:'fast',number:'03',title:'Faster, wider intelligence',subtitle:'Open model routes, web research and chat images',
  body:'More useful answers and creation paths, subject to provider and performance tests.',pr:28},
 {id:'teams',number:'04',title:'Agent teams that remember',subtitle:'Concurrent specialists and source-ranked context',
  body:'Bounded parallel execution and memory backed by observable evidence.',pr:29},
 {id:'future',number:'05',title:'Deep creation workflows',subtitle:'3D, animation, MCP expansion and automated Roblox QA',
  body:'Longer-term research priorities. No speculative completion dates.',pr:null}
] as const
export function filterCapabilities(stage:CapabilityStage|'all',term:string):Capability[]{
 const query=term.trim().toLowerCase()
 return capabilities.filter(item=>
  (stage==='all'||stage===item.stage) &&
  (!query||[item.name,item.area,item.description,item.detail].join(' ').toLowerCase().includes(query))
 )
}
