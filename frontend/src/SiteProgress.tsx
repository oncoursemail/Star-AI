/**
 * The progress board. Every row comes from the public GitHub repository: releases, pull requests, issues,
 * milestones and commits. Nothing is curated by hand, so the board cannot drift from the repository.
 *
 * Vocabulary is deliberate. An open draft pull request is "in progress". A merged one is "in the source".
 * Only a published release is "shipped".
 */
import {useMemo,useState} from 'react'
import type {ReactNode} from 'react'
import {ArrowUpRight,RefreshCw} from 'lucide-react'
import {buildBoard,pullStage} from './githubPublic'
import type {Board,IssueInfo,PullInfo} from './githubPublic'
import {LINKS,formatAgo,formatDate,formatDateTime} from './siteContent'
import type {ProgressState} from './siteHooks'
import {delay,useHydrated} from './siteHooks'

const VISIBLE_ROWS=5
const plural=(count:number,one:string,many:string)=>count+' '+(count===1?one:many)

function syncMessage(progress:ProgressState,localTime:boolean):{tone:'live'|'wait'|'stale';line:string;detail:string|null}{
 const {snapshot,status}=progress
 // Prerendered markup carries a plain UTC date; the visitor's own clock takes over once the page is interactive.
 const asOf=snapshot?(localTime?formatDateTime(snapshot.generatedAt):formatDate(snapshot.generatedAt)):null
 if(!snapshot){
  return status.kind==='loading'
   ?{tone:'wait',line:'Checking GitHub…',detail:null}
   :{tone:'stale',line:'Progress could not be loaded',detail:'Open the repository on GitHub for the current state.'}
 }
 const origin=snapshot.origin==='build'?'saved when this site was built':'last read by this browser'
 switch(status.kind){
  case 'live':return {tone:'live',line:'Live from GitHub · checked '+asOf,
   detail:status.partial?'GitHub answered only in part. Missing sections are marked.':null}
  case 'loading':return {tone:'wait',line:'Checking GitHub…',detail:'Showing the state as of '+asOf+'.'}
  case 'limited':return {tone:'stale',line:'Last known state · '+asOf,
   detail:'GitHub limits anonymous requests per network, and that limit is used up for now. Live data returns after '+
    new Date(status.retryAt).toLocaleTimeString('en',{hour:'numeric',minute:'2-digit'})+'.'}
  case 'failed':return {tone:'stale',line:'Last known state · '+asOf,
   detail:'Could not load the current state from GitHub. This copy was '+origin+'.'}
  default:return {tone:'stale',line:'Snapshot · '+asOf,detail:'This copy was '+origin+'.'}
 }
}

function PullRow({pull,merged,relative}:{pull:PullInfo;merged?:boolean;relative:boolean}){
 const stage=pullStage(pull)
 return <li>
  <a className="sw-row" href={pull.url} target="_blank" rel="noopener noreferrer">
   <span className="sw-row-id">#{pull.number}</span>
   <span className="sw-row-title">{pull.title}</span>
   <span className="sw-row-meta">
    {!merged&&<span className={'sw-chip sw-chip-'+stage}>{stage==='draft'?'Draft':'In review'}</span>}
    {merged?'Merged '+formatDate(pull.mergedAt):'Updated '+(relative?formatAgo(pull.updatedAt):formatDate(pull.updatedAt))}
   </span>
  </a>
 </li>
}
function IssueRow({issue,idea}:{issue:IssueInfo;idea:boolean}){
 return <li>
  <a className="sw-row" href={issue.url} target="_blank" rel="noopener noreferrer">
   <span className="sw-row-id">#{issue.number}</span>
   <span className="sw-row-title">{issue.title}</span>
   <span className="sw-row-meta">
    <span className={'sw-chip '+(idea?'sw-chip-idea':'sw-chip-task')}>{idea?'Idea':'Task'}</span>
    Opened {formatDate(issue.createdAt)}{issue.comments?' · '+plural(issue.comments,'comment','comments'):''}
   </span>
  </a>
 </li>
}

function Lane({id,title,count,capped,hint,rows,unavailable,empty}:{
 id:string;title:string;count:number;capped?:boolean;hint:string;rows:ReactNode[];unavailable:boolean;empty:string
}){
 const [open,setOpen]=useState(false)
 const shown=open?rows:rows.slice(0,VISIBLE_ROWS)
 return <section className="sw-lane" aria-labelledby={id}>
  <h3 id={id}>{title}{!unavailable&&<span className="sw-count" aria-label={count+(capped?' or more':'')+(count===1?' item':' items')}>{count}{capped?'+':''}</span>}</h3>
  <p className="sw-lane-hint">{hint}</p>
  {unavailable?<p className="sw-lane-empty">This part could not be loaded from GitHub.</p>
   :rows.length?<ul className="sw-rows" id={id+'-rows'}>{shown}</ul>
   :<p className="sw-lane-empty">{empty}</p>}
  {!unavailable&&rows.length>VISIBLE_ROWS&&<button type="button" className="sw-more" aria-expanded={open} aria-controls={id+'-rows'}
   onClick={()=>setOpen(value=>!value)}>{open?'Show fewer':'Show all '+rows.length}</button>}
 </section>
}

function ReleaseRail({board}:{board:Board}){
 const shown=[...board.releases].slice(0,4).reverse()
 const sinceCount=board.unreleased.length+board.unreleasedMaintenance
 if(!shown.length)return null
 return <ol className="sw-rail" aria-label="Published releases, oldest first, then unreleased work on main">
  {shown.map((release,index)=>{
   const isLatest=release.tag===board.latest?.tag
   return <li key={release.tag} data-latest={isLatest} style={delay(index*80)}>
    <a href={release.url} target="_blank" rel="noopener noreferrer">
     <span className="sw-rail-node" aria-hidden="true"/>
     <span className="sw-rail-tag">{release.tag}</span>
     <span className="sw-rail-date">{formatDate(release.publishedAt)}</span>
     {isLatest&&<span className="sw-rail-flag">Latest release</span>}
    </a>
   </li>
  })}
  <li data-main="true" style={delay(shown.length*80)}>
   <a href={LINKS.commits} target="_blank" rel="noopener noreferrer">
    <span className="sw-rail-node" aria-hidden="true"/>
    <span className="sw-rail-tag">main</span>
    <span className="sw-rail-date">{sinceCount?plural(sinceCount,'change','changes')+' merged since':'No merges since'}</span>
    <span className="sw-rail-flag">Not released yet</span>
   </a>
  </li>
 </ol>
}

export function SiteProgress({progress}:{progress:ProgressState}){
 const board=useMemo(()=>buildBoard(progress.snapshot),[progress.snapshot])
 const hydrated=useHydrated()
 const sync=syncMessage(progress,hydrated)
 const snapshot=progress.snapshot
 const loading=progress.status.kind==='loading'
 const openCount=board.tasks.length+board.ideas.length
 return <section className="sw-progress" id="progress" aria-labelledby="sw-progress-title">
  <div className="sw-wrap">
   <div className="sw-progress-head" data-reveal>
    <div className="sw-chapter-head">
     <p className="sw-kicker">Progress</p>
     <h2 id="sw-progress-title">Shipped, in flight, and next.</h2>
     <p>This board uses public GitHub data. It may show a dated build-time or browser-cached snapshot while
      it checks for updates, or when GitHub is unavailable; the status above says which.</p>
    </div>
    <div className="sw-sync">
     <p className="sw-sync-line" data-tone={sync.tone} role="status" aria-live="polite">
      <span className="sw-sync-dot" aria-hidden="true"/>{sync.line}
     </p>
     {sync.detail&&<p className="sw-sync-detail">{sync.detail}</p>}
     <button type="button" className="sw-btn sw-btn-quiet sw-btn-compact" onClick={progress.refresh} disabled={loading||progress.status.kind==='limited'}>
      <RefreshCw size={15} aria-hidden="true" className={loading?'sw-spin':undefined}/> Refresh
     </button>
    </div>
   </div>

   {snapshot&&<>
    <div data-reveal><ReleaseRail board={board}/></div>

    {/* The full board is for people following development; visitors get the release line first. */}
    <details className="sw-progress-more" data-reveal style={delay(60)}>
     <summary><span>Open work on GitHub</span><span className="sw-progress-counts">{board.active.length+board.activeMaintenance} in progress · {board.unreleased.length+board.unreleasedMaintenance} merged, not released · {openCount} open {openCount===1?'issue':'issues'}</span></summary>
    <div className="sw-lanes">
     <Lane id="sw-lane-active" title="In progress" count={board.active.length+board.activeMaintenance} capped={snapshot.pullsCapped}
      unavailable={!snapshot.pulls} empty="No open pull requests right now."
      hint="Open pull requests. A draft is unfinished work, not a feature you can download."
      rows={[...board.active.map(pull=><PullRow key={pull.number} pull={pull} relative={hydrated}/>),
       ...(board.activeMaintenance?[<li key="bots" className="sw-row-plain">+ {plural(board.activeMaintenance,'dependency update','dependency updates')} open</li>]:[])]}/>

     <Lane id="sw-lane-merged" title="Merged, not released" count={board.unreleased.length+board.unreleasedMaintenance}
      unavailable={!snapshot.pulls||!snapshot.releases}
      empty={'Everything merged so far is in '+(board.latest?.tag||'a release')+'.'}
      hint={board.latest?'In the source on main since '+board.latest.tag+'. It reaches you with the next release.':'Merged work that no release contains yet.'}
      rows={[...board.unreleased.map(pull=><PullRow key={pull.number} pull={pull} merged relative={hydrated}/>),
       ...(board.unreleasedMaintenance?[<li key="bots" className="sw-row-plain">+ {plural(board.unreleasedMaintenance,'dependency update','dependency updates')}</li>]:[])]}/>

     <Lane id="sw-lane-next" title="Tasks and ideas" count={openCount} capped={snapshot.issuesCapped}
      unavailable={!snapshot.issues} empty=""
      hint="Open issues. Anything labelled idea, enhancement or proposal is listed as an idea."
      rows={[...board.tasks.map(issue=><IssueRow key={issue.number} issue={issue} idea={false}/>),
       ...board.ideas.map(issue=><IssueRow key={issue.number} issue={issue} idea/>),
       <li key="suggest" className="sw-row-plain">
        {openCount?'':'No open issues right now. '}
        <a href={LINKS.newIssue} target="_blank" rel="noopener noreferrer">Suggest an idea or report a problem<ArrowUpRight size={13} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span></a>
       </li>]}/>
    </div>

    {board.milestones.length>0&&<div className="sw-milestones" data-reveal>
     <h3>Milestones</h3>
     <ul>
      {board.milestones.map(item=>{
       const total=item.open+item.closed
       const done=total?item.closed/total:0
       return <li key={item.number}>
        <a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a>
        <span className="sw-meter" role="img" aria-label={item.closed+' of '+total+' issues closed'}><i style={{transform:'scaleX('+done+')'}}/></span>
        <span className="sw-row-meta">{item.closed} of {total} closed{item.dueOn?' · due '+formatDate(item.dueOn):''}</span>
       </li>
      })}
     </ul>
    </div>}

    <div className="sw-activity" data-reveal>
     <h3>Latest commits on main</h3>
     {board.commits.length?<ul>
      {board.commits.slice(0,5).map(commit=><li key={commit.sha}>
       <a className="sw-commit" href={commit.url} target="_blank" rel="noopener noreferrer">
        <code>{commit.sha}</code><span>{commit.title}</span><time dateTime={commit.date||undefined}>{formatDate(commit.date)}</time>
       </a>
      </li>)}
     </ul>:<p className="sw-lane-empty">Commits could not be loaded. <a href={LINKS.commits} target="_blank" rel="noopener noreferrer">See them on GitHub</a>.</p>}
    </div>
    </details>
   </>}
  </div>
 </section>
}
