import {useEffect,useState} from 'react'
import {AnimatePresence,motion} from 'motion/react'
import {
 Activity,ArrowRight,ArrowUpRight,BookOpen,Box,BrainCircuit,Check,CheckCircle2,
 ChevronRight,Clock3,Code2,Cpu,ExternalLink,GitBranch,GitCommitHorizontal,
 GitPullRequest,Globe2,Image,Layers3,Link2,LockKeyhole,RefreshCw,
 Search,ShieldCheck,Sparkles,Workflow,Wrench
} from 'lucide-react'
import {WEBSITE_REPO,WEBSITE_RELEASES} from './constants'
import {capabilities,filterCapabilities,milestones} from './starCatalog'
import type {CapabilityArea,CapabilityStage} from './starCatalog'
import {fetchPublicStatus,milestoneState} from './githubPublic'
import type {PublicStatus} from './githubPublic'
import './status-hub.css'

const areas={
 Intelligence:BrainCircuit,
 Creation:Wrench,
 Integrations:Link2,
 Reliability:ShieldCheck
} satisfies Record<CapabilityArea,typeof BrainCircuit>

const stageOptions=[
 {value:'all',label:'All tools'},
 {value:'main',label:'On main'},
 {value:'review',label:'In development'},
 {value:'planned',label:'Planned'}
] as const

const mainCount=capabilities.filter(item=>item.stage==='main').length
const reviewCount=capabilities.filter(item=>item.stage==='review').length
const futureCount=capabilities.filter(item=>item.stage==='planned').length

function readableDate(value:string|null|undefined){
 if(!value)return 'Date unavailable'
 const date=new Date(value)
 if(Number.isNaN(date.getTime()))return 'Date unavailable'
 return date.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})
}
function formatCount(value:number|null|undefined, capped=false){
 return value==null?'—':new Intl.NumberFormat().format(value)+(capped?'+':'')
}
function developmentStatus(number:number,snapshot:PublicStatus|null){
 const state=milestoneState(number,snapshot)
 if(state==='merged')return 'Merged to source'
 if(state==='review')return 'Open for review'
 if(state==='closed')return 'Closed, not merged'
 return 'Check pull request'
}

function MetricCard({value,label,detail,icon:Icon}:{
 value:string;label:string;detail:string;icon:typeof Activity
}){
 return <article className="sh-metric">
  <div className="sh-metric-label"><span>{label}</span><Icon size={17} strokeWidth={1.7}/></div>
  <div className="sh-metric-value">{value}</div>
  <p>{detail}</p>
 </article>
}

export function StatusHub(){
 const [snapshot,setSnapshot]=useState<PublicStatus|null>(null)
 const [state,setState]=useState<'loading'|'ready'|'error'>('loading')
 const [refreshKey,setRefreshKey]=useState(0)
 const [stage,setStage]=useState<CapabilityStage|'all'>('all')
 const [query,setQuery]=useState('')
 useEffect(()=>{
  const controller=new AbortController()
  setState('loading')
  fetchPublicStatus(controller.signal).then(data=>{
   if(!controller.signal.aborted){setSnapshot(data);setState('ready')}
  }).catch(()=>{
   if(!controller.signal.aborted){setSnapshot(null);setState('error')}
  })
  return ()=>controller.abort()
 },[refreshKey])
 const filtered=filterCapabilities(stage,query)
 const loaded=state==='ready'
 return <>
  <section className="sh-dashboard" id="status" aria-labelledby="sh-status-title">
   <div className="sh-heading sh-heading-row">
    <div><span className="sh-eyebrow"><Activity size={14}/> 01 / DEVELOPMENT PULSE</span>
     <h2 id="sh-status-title">Built in the open.<br/><span>Progress you can verify.</span></h2>
     <p>Release activity and project statistics pulled from the public GitHub repository—not invented usage numbers or AI benchmark scores.</p>
    </div>
    <div className="sh-source-actions">
     <span className={'sh-data-pill '+(loaded?'is-current':state==='error'?'is-error':'')}>
      <span className="sh-data-dot"/>{state==='loading'?'Fetching GitHub…':state==='error'?'GitHub unavailable':snapshot?.partial?'Partial GitHub data':'Public GitHub data'}
     </span>
     <button className="sh-refresh" type="button" onClick={()=>setRefreshKey(key=>key+1)}
      disabled={state==='loading'} aria-label="Refresh public GitHub statistics">
      <RefreshCw size={15} className={state==='loading'?'sh-refreshing':''}/> Refresh
     </button>
    </div>
   </div>
   <div className="sh-pulse-grid">
    <div className="sh-metrics-grid">
     <MetricCard icon={Layers3} label="Latest release"
      value={loaded?(snapshot?.latestRelease?.tag||'—'):'—'}
      detail={loaded&&snapshot?.latestRelease?'Published '+readableDate(snapshot.latestRelease.date):'From GitHub Releases'}/>
     <MetricCard icon={GitPullRequest} label="Open pull requests"
      value={loaded?formatCount(snapshot?.openPRs,snapshot?.prsCapped):'—'} detail="Source changes under review"/>
     <MetricCard icon={Code2} label="Open issues"
      value={loaded?formatCount(snapshot?.openIssues,snapshot?.issuesCapped):'—'} detail="Excludes pull requests"/>
     <MetricCard icon={Sparkles} label="Repository stars"
      value={loaded?formatCount(snapshot?.stars):'—'} detail="Public GitHub stars, not active users"/>
    </div>
    <div className="sh-activity">
     <div className="sh-panel-top"><div><span>REPOSITORY ACTIVITY</span><h3>Latest updates</h3></div>
      <a href={WEBSITE_REPO+'/commits/main'} target="_blank" rel="noopener noreferrer" aria-label="See all GitHub commits"><ArrowUpRight size={18}/></a>
     </div>
     <div className="sh-activity-list" aria-live="polite">
      {loaded&&snapshot?.commits.length? snapshot.commits.slice(0,4).map(item=>
       <a className="sh-commit" key={item.sha} href={item.url} target="_blank" rel="noopener noreferrer">
        <span className="sh-commit-icon"><GitCommitHorizontal size={16}/></span>
        <span className="sh-commit-copy"><strong>{item.title}</strong><small>{item.sha} · {readableDate(item.date)}</small></span>
        <ChevronRight size={15}/>
       </a>):
       <p className="sh-activity-empty">{state==='loading'?'Checking the public repository…':'Recent changes could not be loaded. Open GitHub for the current commit history.'}</p>}
     </div>
     <div className="sh-activity-footer">
      <span>{loaded?'Checked '+new Date(snapshot!.fetchedAt).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}):'No locally generated statistics'}</span>
      <a href={WEBSITE_REPO} target="_blank" rel="noopener noreferrer">View source <ArrowUpRight size={12}/></a>
     </div>
    </div>
   </div>
  </section>

  <section className="sh-intelligence" id="intelligence" aria-labelledby="sh-intel-title">
   <div className="sh-intel-top">
    <div className="sh-heading"><span className="sh-eyebrow"><BrainCircuit size={14}/> 02 / STAR INTELLIGENCE</span>
     <h2 id="sh-intel-title">An AI that's more<br/><span>than a chat window.</span></h2>
     <p>STAR combines a model, the right context, scoped tools and verification. Each layer is a system you can inspect—not a claim that STAR trained itself into a frontier model.</p>
    </div>
    <div className="sh-intel-fact"><span>INTELLIGENCE STACK</span>
     <strong>ONE STAR<span>.</span></strong>
     <p>Local-first by default. Optional integrations are independently permissioned and measurable.</p>
     <div><span><Check size={14}/> Defined scope</span><span><Check size={14}/> Traceable outputs</span></div>
    </div>
   </div>
   <div className="sh-pipeline" role="list" aria-label="How STAR processes tasks">
    {[
     {number:'01',icon:BookOpen,title:'Understand',tag:'INPUT + CONTEXT',copy:'Read the request and approved project references.'},
     {number:'02',icon:BrainCircuit,title:'Reason',tag:'LOCAL AI ENGINE',copy:'Use a model and bounded plans, not fabricated certainty.'},
     {number:'03',icon:Workflow,title:'Act',tag:'SCOPED TOOL CALLS',copy:'Select authorized Studio, file or knowledge tools.'},
     {number:'04',icon:ShieldCheck,title:'Verify',tag:'TEST + REVIEW',copy:'Check evidence before calling a task complete.'}
    ].map((layer,index)=><div className="sh-pipeline-step" role="listitem" key={layer.number}>
      <div className="sh-pipeline-top"><span>{layer.number}</span><layer.icon size={23} strokeWidth={1.5}/></div>
      <span className="sh-pipeline-tag">{layer.tag}</span><h3>{layer.title}</h3><p>{layer.copy}</p>
      {index<3&&<ArrowRight className="sh-pipeline-arrow" size={18} aria-hidden="true"/>}
     </div>)}
   </div>
   <div className="sh-intel-bottom">
    <div><Cpu size={18}/><strong>Local foundation</strong><span>Model setup, conversations, project memory</span></div>
    <div><Globe2 size={18}/><strong>Expanding reach</strong><span>Providers and web research in an open PR</span></div>
    <div><Layers3 size={18}/><strong>Smarter coordination</strong><span>Agent teams and evidence-ranked memory in review</span></div>
   </div>
  </section>

  <section className="sh-tools" id="tools" aria-labelledby="sh-tools-title">
   <div className="sh-heading sh-tools-heading">
    <span className="sh-eyebrow"><Wrench size={14}/> 03 / THE TOOL LIBRARY</span>
    <h2 id="sh-tools-title">A growing toolkit.<br/><span>A clear picture of what's ready.</span></h2>
    <p>Explore STAR's implemented source integrations, active development branches and longer-term plans. Status labels refer to repository code—not guaranteed runtime success on every PC.</p>
   </div>
   <div className="sh-tool-totals" aria-label="Curated capability inventory">
    <div><strong>{mainCount.toString().padStart(2,'0')}</strong><span>On main branch</span></div>
    <div><strong>{reviewCount.toString().padStart(2,'0')}</strong><span>Under development</span></div>
    <div><strong>{futureCount.toString().padStart(2,'0')}</strong><span>Future / research</span></div>
    <p>Tracked source features and proposals, not an intelligence score. <a href={WEBSITE_REPO+'/issues'} target="_blank" rel="noopener noreferrer">Suggest a tool <ArrowUpRight size={12}/></a></p>
   </div>
   <div className="sh-library-toolbar">
    <div className="sh-stage-tabs" aria-label="Filter capabilities by delivery status">
     {stageOptions.map(item=><button key={item.value} type="button"
      className={stage===item.value?'is-selected':''} aria-pressed={stage===item.value}
      onClick={()=>setStage(item.value)}>{item.label}</button>)}
    </div>
    <label className="sh-tool-search">
     <Search size={17} aria-hidden="true"/><span className="sh-sr-only">Search capabilities</span>
     <input type="search" value={query} onChange={event=>setQuery(event.target.value)}
      placeholder="Search tools and skills…"/>
    </label>
   </div>
   <div className="sh-results-label"><span>SHOWING {filtered.length} OF {capabilities.length} TRACKED CAPABILITIES</span><span>STATUS / SOURCE-BASED</span></div>
   <div className="sh-tool-grid" aria-live="polite">
    <AnimatePresence mode="popLayout" initial={false}>
     {filtered.map(item=>{
      const Icon=areas[item.area]
      const label=item.stage==='main'?'On main':item.stage==='planned'?'Research / planned':
       item.pr&&milestoneState(item.pr,snapshot)==='merged'?'Merged source':
       item.pr&&milestoneState(item.pr,snapshot)==='closed'?'PR closed':'In PR'
      const url=item.pr?WEBSITE_REPO+'/pull/'+item.pr:WEBSITE_REPO+(item.stage==='planned'?'/issues':'/tree/main/star')
      return <motion.article layout initial={{opacity:0,y:9}} animate={{opacity:1,y:0}}
       exit={{opacity:0,scale:.98}} transition={{duration:.17}} className="sh-tool" key={item.id}>
        <div className="sh-tool-top"><span className="sh-tool-icon"><Icon size={20} strokeWidth={1.65}/></span>
         <span className={'sh-tag sh-tag-'+item.stage}>{label}</span></div>
        <span className="sh-tool-area">{item.area.toUpperCase()}</span>
        <h3>{item.name}</h3><p>{item.description}</p>
        <div className="sh-tool-details">{item.detail}</div>
        <a href={url} target="_blank" rel="noopener noreferrer" aria-label={'View source for '+item.name}>
         {item.pr?'Pull request #'+item.pr:item.stage==='planned'?'Explore issues':'Explore code'} <ArrowUpRight size={14}/>
        </a>
       </motion.article>
     })}
    </AnimatePresence>
    {filtered.length===0&&<div className="sh-empty"><Search size={26}/><h3>No matching capabilities</h3>
     <p>Try another search or show all tools.</p><button type="button" onClick={()=>{setStage('all');setQuery('')}}>Clear filters</button>
     </div>}
   </div>
  </section>

  <section className="sh-roadmap" id="roadmap" aria-labelledby="sh-roadmap-title">
   <div className="sh-heading sh-roadmap-heading">
    <span className="sh-eyebrow"><GitBranch size={14}/> 04 / WHAT COMES NEXT</span>
    <h2 id="sh-roadmap-title">The roadmap.<br/><span>Not the hype.</span></h2>
    <p>Follow the actual work as STAR grows. An open pull request means code is being reviewed, not that a feature is available in a public Windows release.</p>
   </div>
   <div className="sh-roadmap-list">
    {milestones.map((item,index)=>{
     const prState=item.pr?milestoneState(item.pr,snapshot):null
     const label=item.id==='foundation'?'Foundation in source':item.id==='future'?'Exploration':
      prState==='merged'?'Merged to source':prState==='review'?'Open pull request':
      prState==='closed'?'PR closed':'Check GitHub status'
     const href=item.pr?WEBSITE_REPO+'/pull/'+item.pr:item.id==='foundation'?WEBSITE_RELEASES:WEBSITE_REPO+'/issues'
     return <motion.a {...{initial:{opacity:0,y:12},whileInView:{opacity:1,y:0},viewport:{once:true,amount:.1},transition:{duration:.3,delay:index*.035}}}
      className={'sh-milestone '+(item.id==='foundation'?'sh-milestone-first':'')}
      href={href} target="_blank" rel="noopener noreferrer" key={item.id}>
      <span className="sh-milestone-number">{item.number}</span>
      <div className="sh-milestone-main"><span className="sh-milestone-state">{label}</span>
       <h3>{item.title}</h3><strong>{item.subtitle}</strong><p>{item.body}</p></div>
      <span className="sh-milestone-link">{item.pr?'PR #'+item.pr:item.id==='foundation'?'Releases':'Issues'} <ArrowUpRight size={15}/></span>
     </motion.a>
    })}
   </div>
   <div className="sh-roadmap-note"><div className="sh-note-icon"><LockKeyhole size={21}/></div>
    <div><strong>Shipping requires verification.</strong><p>Windows 11, real local-model inference, GPU behavior, installer upgrades and Studio integration still need native acceptance testing. Code merged into main isn't automatically a released, validated feature.</p></div>
    <a href={WEBSITE_REPO+'/issues/15'} target="_blank" rel="noopener noreferrer">Acceptance issue <ExternalLink size={15}/></a>
   </div>
  </section>
 </>
}
