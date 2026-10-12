/**
 * Editorial content for the public website.
 *
 * Nothing here states a version as "available". Each capability names the first release that contains it
 * (`since`), and the page compares that with the latest published GitHub release at view time. A feature that
 * exists only in source or in a draft pull request therefore reads "In development" until a release catches up.
 */
import pkg from '../package.json'
import {REPO_URL,availability} from './githubPublic'
import type {ReleaseInfo} from './githubPublic'

/** Version of the source this site was built from. It can be ahead of the latest published release. */
export const SOURCE_VERSION:string=pkg.version
export const LINKS={
 repo:REPO_URL,
 releases:REPO_URL+'/releases',
 latest:REPO_URL+'/releases/latest',
 issues:REPO_URL+'/issues',
 newIssue:REPO_URL+'/issues/new',
 pulls:REPO_URL+'/pulls',
 commits:REPO_URL+'/commits/main',
 docs:REPO_URL+'/tree/main/docs',
 start:REPO_URL+'/blob/main/START_HERE_WINDOWS11.md',
 security:REPO_URL+'/blob/main/docs/SECURITY_AND_AUTONOMY.md',
 server:REPO_URL+'/blob/main/docs/STAR_MODEL_ROUTER_WINDOWS.md',
 robloxAccess:REPO_URL+'/blob/main/docs/ROBLOX_ACCESS.md',
 knowledge:REPO_URL+'/blob/main/docs/ROBLOX_KNOWLEDGE.md',
 evals:REPO_URL+'/blob/main/docs/evals.md',
 learning:REPO_URL+'/blob/main/docs/STAR_LEARNING.md',
 voice:REPO_URL+'/blob/main/docs/STAR_VOICE_CALLS.md',
 media:REPO_URL+'/blob/main/docs/STAR_MEDIA.md',
 documents:REPO_URL+'/blob/main/star/documents.py',
 acceptance:REPO_URL+'/issues/15',
 robloxMcp:'https://create.roblox.com/docs/studio/mcp',
 // When live release data is unavailable, use the official release page rather than guessing an asset URL.
} as const

export type TourId='chat'|'brain'|'tools'|'projects'|'analytics'
export type TourView={id:TourId;tab:string;title:string;body:string;points:string[]}
/** Each view is a capture of the real interface (see scripts/capture-site-media.mjs), not a drawing. */
export const tour:TourView[]=[
 {id:'chat',tab:'Chat',title:'Ask, attach, build.',
  body:'A quiet conversation view. Replies stream in from your model, code blocks copy in one click, and screenshots or files ride along with the message.',
  points:['Streaming replies','Image and file references','Copyable code blocks']},
 {id:'brain',tab:'Brain',title:'Your model, installed in one step.',
  body:'STAR Brain downloads a verified engine and model, then asks it for a real reply, so you know it works before you rely on it.',
  points:['About 3.5 GB download','Every file checked by SHA-256','Runs on loopback, on your PC']},
 {id:'tools',tab:'Tools',title:'Exactly the access a task needs.',
  body:'Connect Roblox Studio and a project folder. Studio inspection starts read-only; editing a disposable test place requires a separate permission.',
  points:['Official Studio MCP','Read-only Studio inspection','Scoped edits are opt-in']},
 {id:'projects',tab:'Projects',title:'Every project keeps its own context.',
  body:'Conversations and references stay with the workspace they belong to, so a Roblox obby and a research notebook do not bleed into each other.',
  points:['Separate workspaces','Saved conversations','Stored on your disk']},
 {id:'analytics',tab:'Analytics',title:'Numbers from your own runs.',
  body:'Task runs, outcomes and response times, recorded locally. A fresh install shows zeros, because nothing here is invented.',
  points:['Local SQLite, no cloud tracking','Honest empty states','Median response time']}
]

export type BrainRoute={id:string;icon:'pc'|'server'|'cloud';title:string;body:string;since:string;note?:string}
export const brainRoutes:BrainRoute[]=[
 {id:'pc',icon:'pc',title:'This PC',since:'0.8.0',note:'Default',
  body:'A managed llama.cpp engine with Qwen 3.5 4B, sized for a graphics card with about 8 GB of memory.'},
 {id:'lan',icon:'server',title:'STAR Server, on your network',since:'0.9.0',
  body:'A model server you run on another machine at home. STAR reaches it at a private network address, keeps its key in Windows Credential Manager, and needs no model download on this PC.'},
 {id:'hosted',icon:'cloud',title:'A hosted provider, with your key',since:'0.9.0',note:'Optional',
  body:'Groq, OpenRouter, Gemini or Cerebras. Off until you add a key, and local chat never falls back to it silently.'}
]

/** Only label capabilities as shipped when a stable published release confirms them. */
export function modelLabelForRelease(latest:ReleaseInfo|null):string{
 const state=availability('0.9.0',latest)
 if(state==='released')return 'Local, LAN or opt-in hosted'
 if(state==='upcoming')return 'On-device model option'
 return 'Check GitHub'
}

export const studioScopes=[
 {level:'Inspect',state:'On by default',body:'STAR reads the test place you point it at: instances, scripts and structure.'},
 {level:'Edit',state:'Off until you enable it',body:'Scoped changes inside that test place. You review what changed.'},
 {level:'Open Cloud',state:'Separate approval',body:'Studio does not publish. Open Cloud may save a version in your approved private test experience, only after you approve that action.'}
] as const

/** The real layout of %APPDATA%\STAR, as written by the desktop app. */
export const dataFolder=[
 {name:'conversations.sqlite3',what:'Your chats'},
 {name:'checkpoints.sqlite3',what:'Project memory'},
 {name:'analytics.sqlite3',what:'Local run statistics'},
 {name:'settings.json',what:'Preferences'},
 {name:'models\\',what:'Downloaded model weights'},
 {name:'engines\\',what:'The llama.cpp runtime'},
 {name:'runs\\',what:'Transcripts of finished tasks'}
] as const

export type Connection={name:string;what:string;since:string}
export const connections:Connection[]=[
 {name:'Roblox Studio',what:'Inspect a disposable test place; scoped editing is opt-in',since:'0.8.0'},
 {name:'Roblox Open Cloud',what:'Owner-approved saved test-place versions and Luau test runs; no live publishing',since:'0.9.0'},
 {name:'STAR Knowledge',what:'Cited official Roblox documentation and static Luau checks on your STAR Server',since:'0.9.0'},
 {name:'Project folder',what:'Read a folder you choose; write only when you allow it',since:'0.8.0'},
 {name:'Images, video and audio',what:'Attach references to a message',since:'0.8.0'},
 {name:'Obsidian vault',what:'Read-only search across your Markdown notes',since:'0.9.0'},
 {name:'Graphify graph',what:'Explore an exported knowledge graph',since:'0.9.0'},
 {name:'Agent Skills',what:'Load reviewed, task-specific instructions',since:'0.9.0'},
 {name:'Web research',what:'Search with sources, using your Brave or Tavily key',since:'0.9.0'},
 {name:'ComfyUI',what:'Generate images in chat with your local ComfyUI',since:'0.9.0'},
 {name:'STAR Teams',what:'Bounded specialist agents on one task',since:'0.9.0'}
]

/** Code-backed v0.9.0 features; release badges are driven only by published GitHub tags. */
export const capabilities=[
 {name:'STAR Server on your network',since:'0.9.0',doc:LINKS.server,
  what:'Use a model server at a private network address. Its key stays in the OS credential store; this PC needs no local model download.'},
 {name:'Roblox answers with sources',since:'0.9.0',doc:LINKS.knowledge,
  what:'STAR Knowledge retrieves and cites official Roblox and Luau documentation. Static compile/type checks do not playtest code or fully validate Roblox APIs.'},
 {name:'Studio and Open Cloud',since:'0.9.0',doc:LINKS.robloxAccess,
  what:'Studio inspection is read-only first. Separate Open Cloud actions save versions to an owner-approved private test place or run Luau tests, each requiring approval.'},
 {name:'Skills and the evaluation gate',since:'0.9.0',doc:LINKS.evals,
  what:'Eighteen task-specific skill packs ship, five on by default; the six game-type packs stay off until the gate has measured them. The gate checks for regressions using fixed automated tasks; it does not judge visual quality in Studio.'},
 {name:'Project learning',since:'0.9.0',doc:LINKS.learning,
  what:'Source-linked local lessons are scoped to a project. Inferred lessons await review; the model is not retrained.'},
 {name:'Voice calls',since:'0.9.0',doc:LINKS.voice,
  what:'Optional on-PC speech recognition and Kokoro speech, with interruption controls. Extra voice packages and models are not bundled; real microphones remain untested.'},
 {name:'Images and video',since:'0.9.0',doc:LINKS.media,
  what:'Optional local ComfyUI creates or edits images. Video answers use up to four sampled frames and, with voice extras, a limited audio transcript; not full video playback.'},
 {name:'Documents and tables',since:'0.9.0',doc:LINKS.documents,
  what:'Bounded reading and source-linked search of attached PDF, DOCX, PPTX, XLSX, CSV and text files, with exact table calculations. Files and macros are not executed.'}
] as const

/** Baselines only: not a measure of Roblox Studio gameplay or a combined skill-pack run. */
/** Dated observed runs, not a reproducible best score or combined benchmark. */
export const evalResults=[
 {suite:'Roblox v2 scripting (October 12 and earlier runs)',passed:'13–18 / 34',rate:'varies by run'},
 {suite:'Creation v1 (earlier; not reproduced on v0.9.0)',passed:'11 / 23 (historical)',rate:'unverified on release'}
] as const

export const steps=[
 {title:'Download STAR',fact:'installer',
  body:'One Setup file from GitHub Releases. It installs for your user account, so there is no administrator prompt.'},
 {title:'Start STAR Brain',fact:'3.5 GB download · keep 4.3 GB free',
  body:'Open STAR Brain and press Download and start. STAR fetches the engine and model, checks every file, then runs a test reply.'},
 {title:'Start creating',fact:'Works offline after setup',
  body:'Open Chat and ask for what you need. Attach a screenshot or a file when it helps.'},
 {title:'Connect tools, if you want',fact:'Optional · read-only first',
  body:'Roblox Studio and a project folder live under Developer tools. Begin with an unpublished test place.'}
] as const

export const requirements=[
 {term:'System',detail:'Windows 11, 64-bit. Windows 10 is untested.'},
 {term:'Graphics',detail:'The default model targets a Vulkan GPU with about 8 GB of memory.'},
 {term:'Disk',detail:'About 4.3 GB free for STAR Brain, plus the app itself.'},
 {term:'Internet',detail:'Needed to download the model and to check for updates. Local chat then works offline.'},
 {term:'Account',detail:'None. No sign-in, no API key for the local brain.'}
] as const

export const limits=[
 {title:'It is early software.',body:'Testing on real Windows 11 machines, graphics cards and the updater is still open.',link:{href:LINKS.acceptance,label:'Acceptance issue #15'}},
 {title:'The installer is not code-signed.',body:'Windows may show a publisher warning. Compare the SHA-256 below before you run it.'},
 {title:'A 4B local model is not a frontier model.',body:'It is quick and private. It also makes mistakes, so check what matters.'},
 {title:'Roblox work needs your review.',body:'STAR assists inside a Studio session. It does not ship a finished game, and what it writes needs playtesting.'},
 {title:'Windows only, no licence file yet.',body:'The source is public to read. An open-source licence has not been published.',link:{href:LINKS.security,label:'Security and autonomy notes'}}
] as const

export const faqs=[
 {q:'Do I need to pay for a cloud model?',
  a:'No. You can use an on-device model or a STAR Server on your own network. Hosted providers are optional and need their own keys.'},
 {q:'Will updating remove my chats or models?',
  a:'No. The installer replaces the app folder. Your chats, models and settings live separately in %APPDATA%\\STAR. Keep backups of work you care about anyway.'},
 {q:'Where do the numbers on this page come from?',
  a:'Release and project progress come from public GitHub data. Separately, docs/evals.md reports measured automated Roblox task pass rates; those do not measure Studio game quality.'},
 {q:'Does this website track me?',
  a:'It sets no cookies and runs no analytics. Your browser requests public release and progress data from GitHub; progress answers are cached briefly in browser storage.'}
] as const

/* ---------- formatting ---------- */

/** Sizes the way Windows Explorer shows them (1 MB = 1,048,576 bytes), so the number matches the downloaded file. */
export function formatBytes(bytes:number|null|undefined):string{
 if(!bytes||bytes<=0)return 'size unavailable'
 const mb=bytes/1_048_576
 return mb>=1024?(mb/1024).toFixed(1)+' GB':Math.round(mb)+' MB'
}
export function formatDate(value:string|null|undefined,style:'short'|'long'='short'):string{
 if(!value)return 'date unavailable'
 const date=new Date(value)
 if(Number.isNaN(date.getTime()))return 'date unavailable'
 return date.toLocaleDateString('en',{month:style==='long'?'long':'short',day:'numeric',year:'numeric',timeZone:'UTC'})
}
export function formatDateTime(value:string|null|undefined):string{
 if(!value)return 'unknown time'
 const date=new Date(value)
 if(Number.isNaN(date.getTime()))return 'unknown time'
 return date.toLocaleString('en',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'})
}
/** "3 hours ago" with a coarse, honest granularity. */
export function formatAgo(value:string|null|undefined,now=Date.now()):string{
 const time=value?Date.parse(value):NaN
 if(Number.isNaN(time))return ''
 const minutes=Math.max(0,Math.round((now-time)/60_000))
 if(minutes<1)return 'just now'
 if(minutes<60)return minutes+' min ago'
 const hours=Math.round(minutes/60)
 if(hours<24)return hours+(hours===1?' hour ago':' hours ago')
 const days=Math.round(hours/24)
 if(days<30)return days+(days===1?' day ago':' days ago')
 return formatDate(value)
}

export type ReleaseFiles={setup:ReleaseInfo['assets'][number]|null;zip:ReleaseInfo['assets'][number]|null;sums:ReleaseInfo['assets'][number]|null}
export function releaseFiles(release:ReleaseInfo|null):ReleaseFiles{
 const assets=release?.assets||[]
 return {
  setup:assets.find(asset=>/^STAR-Setup-v\d+\.\d+\.\d+\.exe$/.test(asset.name))||null,
  zip:assets.find(asset=>asset.name==='STAR-Genesis-Windows-x64.zip')||null,
  sums:assets.find(asset=>asset.name==='SHA256SUMS.txt')||null
 }
}
