/**
 * Public repository data for the website's release facts and progress board.
 *
 * Only unauthenticated, public GitHub REST data for oncoursemail/Star-AI is read. There are no tokens,
 * credentials, local models or user analytics here. Nothing is invented: a part that cannot be loaded is
 * `null`, and callers show the last known snapshot with its date instead of a made-up value.
 *
 * Three layers, newest wins:
 *   1. `progress.json`, written by `scripts/build-progress.mjs` when the site is built (bundled fallback).
 *   2. A copy of the last live answer in this browser's localStorage.
 *   3. A live request at view time, at most once per `FRESH_MS`, with GitHub's rate limit respected.
 */
export const REPO_SLUG='oncoursemail/Star-AI'
export const REPO_URL='https://github.com/'+REPO_SLUG
const API_ROOT='https://api.github.com/repos/'+REPO_SLUG

/** How long a live answer is reused before asking GitHub again. Anonymous clients get 60 requests an hour. */
export const FRESH_MS=10*60*1000
export const CACHE_KEY='star.site.progress.v1'
export const RETRY_KEY='star.site.progress.retryAt'

export type ReleaseAsset={name:string;size:number;url:string;sha256:string|null}
export type ReleaseInfo={tag:string;name:string;publishedAt:string|null;url:string;prerelease:boolean;assets:ReleaseAsset[]}
export type PullInfo={
 number:number;title:string;url:string;state:'open'|'closed';draft:boolean
 mergedAt:string|null;createdAt:string|null;updatedAt:string|null;bot:boolean;labels:string[]
}
export type IssueInfo={number:number;title:string;url:string;createdAt:string|null;updatedAt:string|null;comments:number;labels:string[]}
export type CommitInfo={sha:string;title:string;date:string|null;url:string}
export type MilestoneInfo={number:number;title:string;url:string;dueOn:string|null;open:number;closed:number}

/** Field-for-field subset of GitHub's REST answers. `progress.json` stores exactly this shape. */
export type RawProgress={
 releases:unknown;pulls:unknown;issues:unknown;commits:unknown;milestones:unknown
}
export type ProgressSnapshot={
 /** When the data was read from GitHub (ISO 8601). */
 generatedAt:string
 /** `build`: written when the site was built. `live`: read by this browser. */
 origin:'build'|'live'
 releases:ReleaseInfo[]|null
 pulls:PullInfo[]|null
 issues:IssueInfo[]|null
 commits:CommitInfo[]|null
 milestones:MilestoneInfo[]|null
 /** True when a list hit the page size, so counts are a lower bound. */
 pullsCapped:boolean
 issuesCapped:boolean
}

export const PAGE_SIZE=100
/** GitHub resolves this endpoint to the newest published stable release. */
export const LATEST_RELEASE_ENDPOINT='/releases/latest'
export const ENDPOINTS={
 releases:'/releases?per_page=10',
 pulls:'/pulls?state=all&sort=updated&direction=desc&per_page='+PAGE_SIZE,
 issues:'/issues?state=open&per_page='+PAGE_SIZE,
 commits:'/commits?per_page=8',
 milestones:'/milestones?state=open&per_page=20'
} as const
type Part=keyof typeof ENDPOINTS

/* ---------- normalising untrusted JSON ---------- */

type Dict=Record<string,unknown>
const isDict=(value:unknown):value is Dict=>typeof value==='object'&&value!==null&&!Array.isArray(value)
const text=(value:unknown,limit=300):string=>typeof value==='string'?value.slice(0,limit):''
const isoOrNull=(value:unknown):string|null=>{
 if(typeof value!=='string')return null
 const time=Date.parse(value)
 return Number.isNaN(time)?null:new Date(time).toISOString()
}
const count=(value:unknown):number=>typeof value==='number'&&Number.isFinite(value)&&value>=0?Math.floor(value):0
const labelNames=(value:unknown):string[]=>Array.isArray(value)
 ?value.map(item=>isDict(item)?text(item.name,60):'').filter(Boolean).slice(0,12):[]

/** Links are only ever followed into this repository on github.com; anything else falls back to the repository page. */
export function repoUrl(value:unknown,fallback=REPO_URL):string{
 return typeof value==='string'&&value.startsWith(REPO_URL+'/')&&!/[\s"'<>\\]/.test(value)?value:fallback
}
const assetUrl=(value:unknown):string|null=>{
 const url=repoUrl(value,'')
 return url.startsWith(REPO_URL+'/releases/download/')?url:null
}
const sha256=(value:unknown):string|null=>{
 const match=/^sha256:([0-9a-f]{64})$/i.exec(typeof value==='string'?value:'')
 return match?match[1].toLowerCase():null
}

function toReleases(raw:unknown):ReleaseInfo[]|null{
 if(!Array.isArray(raw))return null
 return raw.filter(isDict).filter(item=>item.draft!==true&&/^v?\d+\.\d+\.\d+/.test(text(item.tag_name,40))).map(item=>({
  tag:text(item.tag_name,40),
  name:text(item.name,120)||text(item.tag_name,40),
  publishedAt:isoOrNull(item.published_at),
  url:repoUrl(item.html_url,REPO_URL+'/releases'),
  prerelease:item.prerelease===true,
  assets:(Array.isArray(item.assets)?item.assets:[]).filter(isDict).flatMap(asset=>{
   const url=assetUrl(asset.browser_download_url)
   const name=text(asset.name,120)
   return url&&name?[{name,size:count(asset.size),url,sha256:sha256(asset.digest)}]:[]
  })
 })).sort((a,b)=>Date.parse(b.publishedAt||'')-Date.parse(a.publishedAt||'')||0)
}
function toPulls(raw:unknown):PullInfo[]|null{
 if(!Array.isArray(raw))return null
 return raw.filter(isDict).filter(item=>count(item.number)>0).map(item=>{
  const user=isDict(item.user)?item.user:{}
  return {
   number:count(item.number),
   title:text(item.title),
   url:repoUrl(item.html_url,REPO_URL+'/pulls'),
   state:item.state==='open'?'open' as const:'closed' as const,
   draft:item.draft===true,
   mergedAt:isoOrNull(item.merged_at),
   createdAt:isoOrNull(item.created_at),
   updatedAt:isoOrNull(item.updated_at),
   bot:user.type==='Bot'||/\[bot\]$/.test(text(user.login,80)),
   labels:labelNames(item.labels)
  }
 })
}
function toIssues(raw:unknown):IssueInfo[]|null{
 if(!Array.isArray(raw))return null
 // GitHub's issues endpoint also returns pull requests; those are counted as pull requests, never as issues.
 return raw.filter(isDict).filter(item=>count(item.number)>0&&!item.pull_request&&item.state!=='closed').map(item=>({
  number:count(item.number),
  title:text(item.title),
  url:repoUrl(item.html_url,REPO_URL+'/issues'),
  createdAt:isoOrNull(item.created_at),
  updatedAt:isoOrNull(item.updated_at),
  comments:count(item.comments),
  labels:labelNames(item.labels)
 }))
}
function toCommits(raw:unknown):CommitInfo[]|null{
 if(!Array.isArray(raw))return null
 return raw.filter(isDict).flatMap(item=>{
  const commit=isDict(item.commit)?item.commit:{}
  const committer=isDict(commit.committer)?commit.committer:{}
  const sha=text(item.sha,40)
  return /^[0-9a-f]{7,40}$/i.test(sha)?[{
   sha:sha.slice(0,7),
   title:text(commit.message,400).split('\n')[0].slice(0,160),
   date:isoOrNull(committer.date),
   url:repoUrl(item.html_url,REPO_URL+'/commits')
  }]:[]
 })
}
function toMilestones(raw:unknown):MilestoneInfo[]|null{
 if(!Array.isArray(raw))return null
 return raw.filter(isDict).filter(item=>count(item.number)>0&&text(item.title)).map(item=>({
  number:count(item.number),
  title:text(item.title,120),
  url:repoUrl(item.html_url,REPO_URL+'/milestones'),
  dueOn:isoOrNull(item.due_on),
  open:count(item.open_issues),
  closed:count(item.closed_issues)
 }))
}
const rawLength=(value:unknown)=>Array.isArray(value)?value.length:0

export function normalizeProgress(raw:Partial<RawProgress>,generatedAt:string,origin:'build'|'live'):ProgressSnapshot{
 return {
  generatedAt,origin,
  releases:toReleases(raw.releases),
  pulls:toPulls(raw.pulls),
  issues:toIssues(raw.issues),
  commits:toCommits(raw.commits),
  milestones:toMilestones(raw.milestones),
  pullsCapped:rawLength(raw.pulls)>=PAGE_SIZE,
  issuesCapped:rawLength(raw.issues)>=PAGE_SIZE
 }
}

/** Reads a `progress.json` document or a cached copy. Returns null for anything malformed or undated. */
export function parseStoredProgress(value:unknown,origin:'build'|'live'):ProgressSnapshot|null{
 if(!isDict(value)||value.schema!==1||value.repo!==REPO_SLUG||!isDict(value.raw))return null
 const generatedAt=isoOrNull(value.generatedAt)
 if(!generatedAt)return null
 const snapshot=normalizeProgress(value.raw as Partial<RawProgress>,generatedAt,origin)
 return snapshot.releases||snapshot.pulls||snapshot.issues?snapshot:null
}

/* ---------- live requests ---------- */

export class RateLimitError extends Error{
 /** Epoch milliseconds after which GitHub accepts anonymous requests again. */
 readonly retryAt:number
 constructor(retryAt:number){super('GitHub rate limit reached');this.name='RateLimitError';this.retryAt=retryAt}
}
function rateLimitFrom(response:Response,now:number):RateLimitError|null{
 if(response.status!==403&&response.status!==429)return null
 const retryAfter=Number(response.headers.get('retry-after'))
 const reset=Number(response.headers.get('x-ratelimit-reset'))
 const remaining=response.headers.get('x-ratelimit-remaining')
 if(Number.isFinite(retryAfter)&&retryAfter>0)return new RateLimitError(now+retryAfter*1000)
 if(remaining==='0'&&Number.isFinite(reset)&&reset>0)return new RateLimitError(Math.max(reset*1000,now+60_000))
 // A 429, or a 403 without usable headers, is still treated as "back off for a while".
 return response.status===429?new RateLimitError(now+5*60_000):null
}
async function readPart(part:Part,signal:AbortSignal|undefined,now:number):Promise<unknown>{
 // Accept is a CORS-safelisted header, so this stays a simple request with no preflight and no credentials.
 const response=await fetch(API_ROOT+ENDPOINTS[part],{signal,credentials:'omit',headers:{Accept:'application/vnd.github+json'}})
 const limited=rateLimitFrom(response,now)
 if(limited)throw limited
 if(!response.ok)throw new Error('GitHub returned '+response.status)
 return await response.json() as unknown
}

/** Direct release lookup. The prerendered progress.json remains the static offline/rate-limit fallback. */
export async function fetchLatestStableRelease(signal?:AbortSignal,now=Date.now()):Promise<ReleaseInfo|null>{
 const response=await fetch(API_ROOT+LATEST_RELEASE_ENDPOINT,{signal,credentials:'omit',headers:{Accept:'application/vnd.github+json'}})
 const limited=rateLimitFrom(response,now)
 if(limited)throw limited
 if(!response.ok)throw new Error('Latest GitHub release is unavailable')
 const releases=toReleases([await response.json() as unknown])
 return releases?.find(release=>!release.prerelease)||null
}

export type LiveResult={snapshot:ProgressSnapshot;raw:Partial<RawProgress>;partial:boolean}

/**
 * One live read of all five public endpoints.
 * Throws RateLimitError when GitHub is throttling this network, and a plain Error when nothing could be read.
 * `partial` is true when some parts failed; those parts are `null`, never guessed.
 */
export async function fetchLiveProgress(signal?:AbortSignal,now=Date.now()):Promise<LiveResult>{
 const parts=Object.keys(ENDPOINTS) as Part[]
 const settled=await Promise.allSettled(parts.map(part=>readPart(part,signal,now)))
 const limited=settled.find(result=>result.status==='rejected'&&result.reason instanceof RateLimitError)
 if(limited&&limited.status==='rejected')throw limited.reason
 if(settled.every(result=>result.status==='rejected'))throw new Error('Public GitHub data is temporarily unavailable')
 const raw:Partial<RawProgress>={}
 settled.forEach((result,index)=>{if(result.status==='fulfilled')raw[parts[index]]=result.value})
 return {
  raw,
  snapshot:normalizeProgress(raw,new Date(now).toISOString(),'live'),
  partial:settled.some(result=>result.status==='rejected')
 }
}

/* ---------- browser cache (only public GitHub answers are stored) ---------- */

type Store=Pick<Storage,'getItem'|'setItem'|'removeItem'>
function safeStore():Store|null{
 try{return typeof window!=='undefined'&&window.localStorage?window.localStorage:null}catch{return null}
}
export function readCachedProgress(store:Store|null=safeStore()):ProgressSnapshot|null{
 try{
  const saved=store?.getItem(CACHE_KEY)
  return saved?parseStoredProgress(JSON.parse(saved),'live'):null
 }catch{return null}
}
export function writeCachedProgress(result:LiveResult,store:Store|null=safeStore()):void{
 if(result.partial)return // Only complete answers replace the last known state.
 try{store?.setItem(CACHE_KEY,JSON.stringify({schema:1,repo:REPO_SLUG,generatedAt:result.snapshot.generatedAt,raw:result.raw}))}
 catch{/* Private browsing or a full quota only costs the cache. */}
}
export function readRetryAt(now=Date.now(),store:Store|null=safeStore()):number|null{
 try{
  const value=Number(store?.getItem(RETRY_KEY))
  if(Number.isFinite(value)&&value>now)return value
  if(value)store?.removeItem(RETRY_KEY)
 }catch{/* ignore */}
 return null
}
export function writeRetryAt(retryAt:number,store:Store|null=safeStore()):void{
 try{store?.setItem(RETRY_KEY,String(Math.round(retryAt)))}catch{/* ignore */}
}
export const isFresh=(snapshot:ProgressSnapshot|null,now=Date.now()):boolean=>
 Boolean(snapshot&&snapshot.origin==='live'&&now-Date.parse(snapshot.generatedAt)<FRESH_MS)
/** Of two snapshots, the one read from GitHub most recently. */
export function newest(a:ProgressSnapshot|null,b:ProgressSnapshot|null):ProgressSnapshot|null{
 if(!a||!b)return a||b
 return Date.parse(b.generatedAt)>Date.parse(a.generatedAt)?b:a
}

/* ---------- versions ---------- */

export function parseVersion(value:string|null|undefined):[number,number,number]|null{
 const match=/^v?(\d+)\.(\d+)\.(\d+)/.exec((value||'').trim())
 return match?[Number(match[1]),Number(match[2]),Number(match[3])]:null
}
/** Negative when `a` is older than `b`. Unparseable versions compare as equal so nothing is claimed either way. */
export function compareVersions(a:string|null|undefined,b:string|null|undefined):number{
 const left=parseVersion(a),right=parseVersion(b)
 if(!left||!right)return 0
 for(let index=0;index<3;index+=1){if(left[index]!==right[index])return left[index]-right[index]}
 return 0
}
export const latestStable=(snapshot:ProgressSnapshot|null):ReleaseInfo|null=>
 snapshot?.releases?.find(release=>!release.prerelease)||null

export type Availability='released'|'upcoming'|'unknown'
/** A capability is "released" only when a published, stable release is at least the version that first contains it. */
export function availability(since:string,latest:ReleaseInfo|null):Availability{
 if(!latest||!parseVersion(latest.tag)||!parseVersion(since))return 'unknown'
 return compareVersions(latest.tag,since)>=0?'released':'upcoming'
}

/* ---------- the board ---------- */

export type PullStage='draft'|'review'|'merged'|'closed'
/** A draft is work in progress. Only a merged pull request is in the source, and only a release ships it. */
export function pullStage(pull:Pick<PullInfo,'state'|'draft'|'mergedAt'>):PullStage{
 if(pull.mergedAt)return 'merged'
 if(pull.state==='open')return pull.draft?'draft':'review'
 return 'closed'
}
const IDEA_LABEL=/^(idea|ideas|enhancement|feature|feature request|proposal|discussion|question)$/i
export type Board={
 latest:ReleaseInfo|null
 releases:ReleaseInfo[]
 /** Open pull requests written by people, newest activity first. Drafts are in progress; the rest await review. */
 active:PullInfo[]
 draftCount:number
 reviewCount:number
 /** Open pull requests from dependency bots. */
 activeMaintenance:number
 /** Merged after the latest release was published: in the source, not in a download yet. */
 unreleased:PullInfo[]
 unreleasedMaintenance:number
 tasks:IssueInfo[]
 ideas:IssueInfo[]
 milestones:MilestoneInfo[]
 commits:CommitInfo[]
}
const byRecent=(a:{updatedAt:string|null},b:{updatedAt:string|null})=>Date.parse(b.updatedAt||'')-Date.parse(a.updatedAt||'')||0
export function buildBoard(snapshot:ProgressSnapshot|null):Board{
 const latest=latestStable(snapshot)
 const pulls=snapshot?.pulls||[]
 const open=pulls.filter(pull=>pull.state==='open')
 const cut=latest?.publishedAt?Date.parse(latest.publishedAt):null
 const mergedSince=cut===null?[]:pulls.filter(pull=>pull.mergedAt&&Date.parse(pull.mergedAt)>cut)
  .sort((a,b)=>Date.parse(b.mergedAt||'')-Date.parse(a.mergedAt||''))
 const issues=[...(snapshot?.issues||[])].sort(byRecent)
 const isIdea=(issue:IssueInfo)=>issue.labels.some(label=>IDEA_LABEL.test(label))
 const active=open.filter(pull=>!pull.bot).sort(byRecent)
 return {
  latest,
  releases:snapshot?.releases||[],
  active,
  draftCount:active.filter(pull=>pull.draft).length,
  reviewCount:active.filter(pull=>!pull.draft).length,
  activeMaintenance:open.filter(pull=>pull.bot).length,
  unreleased:mergedSince.filter(pull=>!pull.bot),
  unreleasedMaintenance:mergedSince.filter(pull=>pull.bot).length,
  tasks:issues.filter(issue=>!isIdea(issue)),
  ideas:issues.filter(isIdea),
  milestones:snapshot?.milestones||[],
  commits:snapshot?.commits||[]
 }
}
