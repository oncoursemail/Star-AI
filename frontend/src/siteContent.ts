/**
 * Editorial content for the public website.
 *
 * Nothing here states a version as "available". Each capability names the first release that contains it
 * (`since`), and the page compares that with the latest published GitHub release at view time. A feature that
 * exists only in source or in a draft pull request therefore reads "In development" until a release catches up.
 */
import pkg from '../package.json'
import {REPO_URL} from './githubPublic'
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
 acceptance:REPO_URL+'/issues/15',
 robloxMcp:'https://create.roblox.com/docs/studio/mcp',
 // Stable file names on every release, so these always follow the newest published one.
 latestZip:REPO_URL+'/releases/latest/download/STAR-Genesis-Windows-x64.zip',
 latestSums:REPO_URL+'/releases/latest/download/SHA256SUMS.txt'
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
  body:'Connect Roblox Studio and a project folder. Everything starts read-only, and editing is a separate switch you turn on yourself.',
  points:['Official Roblox Studio MCP','Read-only by default','Write access is opt-in']},
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

export const studioScopes=[
 {level:'Inspect',state:'On by default',body:'STAR reads the test place you point it at: instances, scripts and structure.'},
 {level:'Edit',state:'Off until you enable it',body:'Scoped changes inside that test place. You review what changed.'},
 {level:'Publish',state:'Never',body:'STAR does not publish experiences or touch live player data.'}
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
 {name:'Roblox Studio',what:'Inspect and edit a test place through the official MCP server',since:'0.8.0'},
 {name:'Project folder',what:'Read a folder you choose; write only when you allow it',since:'0.8.0'},
 {name:'Images, video and audio',what:'Attach references to a message',since:'0.8.0'},
 {name:'Obsidian vault',what:'Read-only search across your Markdown notes',since:'0.9.0'},
 {name:'Graphify graph',what:'Explore an exported knowledge graph',since:'0.9.0'},
 {name:'Agent Skills',what:'Load reviewed, task-specific instructions',since:'0.9.0'},
 {name:'Web research',what:'Search with sources, using your Brave or Tavily key',since:'0.9.0'},
 {name:'ComfyUI',what:'Generate images in chat with your local ComfyUI',since:'0.9.0'},
 {name:'STAR Teams',what:'Bounded specialist agents on one task',since:'0.9.0'}
]

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
  a:'No. STAR runs an open model on your PC. You need the hardware for it and one model download.'},
 {q:'Will updating remove my chats or models?',
  a:'No. The installer replaces the app folder. Your chats, models and settings live separately in %APPDATA%\\STAR. Keep backups of work you care about anyway.'},
 {q:'Where do the numbers on this page come from?',
  a:'From the public GitHub repository: releases, pull requests, issues and commits. There are no usage figures or benchmark scores, because none have been collected.'},
 {q:'Does this website track me?',
  a:'It sets no cookies and runs no analytics. For the progress section your browser asks GitHub\'s public API directly, and the answer is kept in this browser\'s local storage for a few minutes.'}
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
