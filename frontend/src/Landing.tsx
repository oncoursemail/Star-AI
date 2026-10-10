import {useEffect,useState} from 'react'
import type {KeyboardEvent as ReactKeyboardEvent} from 'react'
import {AnimatePresence,motion} from 'motion/react'
import {
 ArrowDownToLine,ArrowRight,ArrowUpRight,BookOpen,BrainCircuit,Check,
 ChevronRight,Code2,Download,ExternalLink,FolderOpen,Github,Layers3,
 LockKeyhole,Menu,MessageSquareText,Monitor,ShieldCheck,Sparkles,
 Workflow,X,Zap
} from 'lucide-react'
import {Brand} from './components'
import {StatusHub} from './StatusHub'
import {WEBSITE_RELEASES,WEBSITE_REPO} from './constants'
import './site-v2.css'
import './site-v3.css'

const tourViews = [
 {id:'chat',label:'Conversation',eyebrow:'01 / THINK',title:'A conversation that stays out of your way.',
  description:'Clear reading, attached references, code you can copy, and project context that stays on your computer.',icon:MessageSquareText},
 {id:'brain',label:'STAR Brain',eyebrow:'02 / RUN',title:'Your own AI, running locally.',
  description:'Install a checksum-verified model, test a real response, and see the actual engine state instead of imagined activity.',icon:BrainCircuit},
 {id:'tools',label:'Developer tools',eyebrow:'03 / BUILD',title:'Connected tools. Defined boundaries.',
  description:'Work with a selected Roblox Studio test place and local workspace. Writes require explicit scope.',icon:Workflow},
 {id:'analytics',label:'Real analytics',eyebrow:'04 / REVIEW',title:'Progress backed by evidence.',
  description:'Local task outcomes and response timings, with honest empty states until work actually happens.',icon:Layers3}
] as const
type TourId = typeof tourViews[number]['id']

const creativeTracks = [
 {id:'design',label:'Design',verb:'Shape the experience',
  request:'Design a clean, responsive inventory interface.',
  steps:['Analyze the reference','Plan editable components','Review spacing & states']},
 {id:'build',label:'Build',verb:'Build with context',
  request:'Inspect my Roblox project before changing code.',
  steps:['Discover the sandbox','Read authorized scripts','Verify each change']},
 {id:'explore',label:'Explore',verb:'Find the right direction',
  request:'Help me turn a rough idea into a build plan.',
  steps:['Understand the goal','Compare approaches','Create a clear plan']}
] as const
type TrackId=typeof creativeTracks[number]['id']

const features = [
 {number:'01',icon:MessageSquareText,title:'Chat that feels considered',
  description:'A spacious conversation view, copyable code, reference attachments and honest status while the local model works.'},
 {number:'02',icon:BrainCircuit,title:'A real local model',
  description:'STAR Brain runs on your device. Test actual inference—not just whether a server port responds.'},
 {number:'03',icon:Workflow,title:'Roblox creation tools',
  description:'Inspect a chosen Studio sandbox and coordinate scoped editing tools with explicit safety boundaries.'},
 {number:'04',icon:FolderOpen,title:'Project continuity',
  description:'Saved conversations, project notes and checkpoint history without erasing your data when STAR updates.'},
 {number:'05',icon:ShieldCheck,title:'Control without complexity',
  description:'Read-only by default, with separately enabled workspace and Studio editing scopes.'},
 {number:'06',icon:Layers3,title:'Measured improvements',
  description:'Real local analytics, quality checks and a development path that distinguishes shipped features from plans.'}
] as const

const fadeUp = {initial:{opacity:0,y:18},whileInView:{opacity:1,y:0},viewport:{once:true,amount:.12},transition:{duration:.42,ease:'easeOut' as const}}

export function Landing(){
 const [menu,setMenu]=useState(false)
 const immediateEntrance=new URLSearchParams(window.location.search).has('visualqa') || window.matchMedia('(prefers-reduced-motion: reduce)').matches
 const [tour,setTour]=useState<TourId>('chat')
 const [track,setTrack]=useState<TrackId>('design')
 const onTourKeys=(event:ReactKeyboardEvent<HTMLDivElement>)=>{
   const keys=['ArrowDown','ArrowUp','ArrowLeft','ArrowRight','Home','End']
   if(!keys.includes(event.key))return
   event.preventDefault()
   const current=tourViews.findIndex(view=>view.id===tour)
   const index=event.key==='Home'?0:event.key==='End'?tourViews.length-1:
     (current+(event.key==='ArrowDown'||event.key==='ArrowRight'?1:-1)+tourViews.length)%tourViews.length
   const next=tourViews[index].id
   setTour(next)
   document.getElementById('sv-tab-'+next)?.focus()
 }
 const selected=tourViews.find(v=>v.id===tour)||tourViews[0]
 const chosen=creativeTracks.find(v=>v.id===track)||creativeTracks[0]
 useEffect(()=>{
   const close=(event:KeyboardEvent)=>{if(event.key==='Escape')setMenu(false)}
   window.addEventListener('keydown',close)
   return ()=>window.removeEventListener('keydown',close)
 },[])
 return <div className="landing sv-page" id="top">
  <header className="sv-header">
   <a className="sv-home" href="#top" aria-label="STAR Intelligence home"><Brand small/></a>
   <nav className={'sv-navigation'+(menu?' sv-navigation-open':'')} aria-label="Main navigation">
     <a href="#status" onClick={()=>setMenu(false)}>Live stats</a>
     <a href="#intelligence" onClick={()=>setMenu(false)}>Intelligence</a>
     <a href="#tools" onClick={()=>setMenu(false)}>Tools</a>
     <a href="#roadmap" onClick={()=>setMenu(false)}>Roadmap</a>
     <a href={WEBSITE_REPO} target="_blank" rel="noopener noreferrer" onClick={()=>setMenu(false)}>GitHub <ArrowUpRight size={14}/></a>
   </nav>
   <div className="sv-header-actions">
    <span className="sv-header-platform"><span className="sv-spark-small">✦</span> OPEN DEVELOPMENT</span>
    <a className="sv-nav-download" href={WEBSITE_RELEASES}><Download size={15}/> Get STAR</a>
    <button className="sv-menu-button" aria-label={menu?'Close menu':'Open menu'} aria-expanded={menu}
      onClick={()=>setMenu(!menu)}>{menu?<X size={20}/>:<Menu size={20}/>}</button>
   </div>
  </header>

  <main>
   <section className="sv-hero" aria-labelledby="sv-title">
    <div className="sv-hero-grid" aria-hidden="true"/>
    <motion.div className="sv-hero-copy" initial={immediateEntrance?false:{opacity:0,y:20}} animate={{opacity:1,y:0}}
      transition={{duration:.55,ease:'easeOut'}}>
     <span className="sv-overline"><span className="sv-overline-mark">✦</span> THE NEXT GENERATION OF STAR <span className="sv-overline-line"/></span>
     <h1 id="sv-title">One AI.<br/><span>Endless ways to create.</span></h1>
     <p className="sv-hero-lede">Meet STAR Intelligence—your local-first AI workspace for building, researching and bringing ambitious ideas to life. Explore the tools it has now, the intelligence coming next, and every real step forward.</p>
     <div className="sv-hero-cta">
       <a className="sv-button sv-button-primary" href={WEBSITE_RELEASES}><ArrowDownToLine size={18}/> Download for Windows <ArrowRight size={17}/></a>
       <a className="sv-button sv-button-quiet" href="#status">See development progress <ArrowUpRight size={17}/></a>
     </div>
     <div className="sv-proof-line">
       <span><Check size={14}/> Your own local brain</span>
       <span><LockKeyhole size={14}/> Permissioned tools</span>
       <span><Monitor size={14}/> Windows desktop</span>
     </div>
    </motion.div>
    <motion.div className="sv-hero-visual" initial={immediateEntrance?false:{opacity:0,x:22}} animate={{opacity:1,x:0}}
      transition={{duration:.65,delay:.12,ease:'easeOut'}}>
      <div className="sv-visual-caption"><span>FIG 01.</span> AN INTELLIGENCE WORKSPACE</div>
      <div className="sv-concept-window">
       <div className="sv-concept-titlebar">
        <span className="sv-concept-emblem" aria-hidden="true">✦</span>
        <span>STAR <span className="sv-concept-secondary">/ WORKSPACE</span></span>
        <span className="sv-concept-preview-label">CONCEPT PREVIEW</span>
       </div>
       <div className="sv-concept-main">
        <div className="sv-concept-rail" aria-hidden="true"><MessageSquareText size={18}/><BrainCircuit size={18}/><Code2 size={18}/><Layers3 size={18}/></div>
        <div className="sv-concept-content">
         <span className="sv-concept-kicker">THE CREATIVE LOOP</span>
         <AnimatePresence mode="wait" initial={false}>
          <motion.div key={chosen.id} initial={{opacity:0,y:8}} animate={{opacity:1,y:0}}
            exit={{opacity:0,y:-5}} transition={{duration:.18}} className="sv-concept-dynamic">
            <h2>{chosen.verb}<span className="sv-period">.</span></h2>
            <div className="sv-concept-message"><span>YOUR IDEA</span><p>{chosen.request}</p></div>
            <div className="sv-concept-sequence" aria-label="Illustrative workflow">
             {chosen.steps.map((step,i)=><div className="sv-concept-step" key={step}>
               <span className="sv-step-num">0{i+1}</span><span className="sv-step-connector"/><span>{step}</span>
               {i===chosen.steps.length-1?<Check size={13}/>:<ChevronRight size={13}/>}
             </div>)}
            </div>
          </motion.div>
         </AnimatePresence>
        </div>
       </div>
       <div className="sv-concept-bottom"><span>INTERFACE CONCEPT · NOT A LIVE MODEL SESSION</span><span>LOCAL / PRIVATE</span></div>
      </div>
      <div className="sv-concept-switch" role="group" aria-label="Preview different creative workflows">
       {creativeTracks.map(item=><button type="button" key={item.id} aria-pressed={track===item.id}
         className={track===item.id?'sv-concept-choice active':'sv-concept-choice'}
         onClick={()=>setTrack(item.id)}>{item.label}{track===item.id&&<motion.span layoutId="sv-track-active" className="sv-concept-choice-indicator"/>}</button>)}
      </div>
    </motion.div>
    <div className="sv-hero-bottom" aria-hidden="true"><span>STAR / INTELLIGENCE</span><span>CREATE · CONNECT · EVOLVE</span></div>
   </section>

   <div className="sv-divider-band"><span>ONE STAR INTELLIGENCE</span><span> / </span><span>VISIBLE PROGRESS</span><span> / </span><span>REAL TOOLS</span><span className="sv-band-star">✦</span></div>
   <StatusHub/>

   <section id="experience" className="sv-experience" aria-labelledby="sv-experience-title">
    <motion.div {...fadeUp} className="sv-section-heading">
     <span className="sv-section-kicker">01 / THE WORKSPACE</span>
     <h2 id="sv-experience-title">Beautiful when you open it.<br/><span>Useful when you work.</span></h2>
     <p>From the first message to the final review, STAR keeps the important tools close—and everything else out of the way.</p>
    </motion.div>
    <div className="sv-tour-layout">
      <div className="sv-tour-choices" role="tablist" aria-label="STAR interface areas" aria-orientation="vertical" onKeyDown={onTourKeys}>
       {tourViews.map(item=><button key={item.id} id={'sv-tab-'+item.id} type="button"
        role="tab" aria-controls="sv-tour-panel" aria-selected={tour===item.id} tabIndex={tour===item.id?0:-1}
        className={tour===item.id?'sv-tour-choice selected':'sv-tour-choice'}
        onClick={()=>setTour(item.id)}>
        <span className="sv-tour-item-icon"><item.icon size={18}/></span>
        <span><strong>{item.label}</strong><small>{item.eyebrow}</small></span><ArrowRight size={15}/>
       </button>)}
       <div className="sv-tour-description" role="tabpanel" aria-labelledby={'sv-tab-'+tour}>
         <AnimatePresence mode="wait" initial={false}><motion.div key={tour}
          initial={{opacity:0,y:7}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-5}}
          transition={{duration:.18}}>
           <span>{selected.eyebrow}</span><h3>{selected.title}</h3><p>{selected.description}</p>
          </motion.div></AnimatePresence>
       </div>
      </div>
      <div id="sv-tour-panel" className="sv-tour-screen">
       <div className="sv-screen-topbar">
        <span className="sv-screen-icon">✦</span>
        <span>STAR INTELLIGENCE</span><span className="sv-screen-meta">ACTUAL REACT INTERFACE · READ-ONLY PREVIEW</span>
       </div>
       <iframe title={'STAR '+selected.label+' interactive interface preview'}
         src={'./?preview=1&tab='+tour} loading="lazy"/>
       <div className="sv-screen-footer"><ShieldCheck size={14}/> This public preview cannot read your local files or run the AI.</div>
      </div>
    </div>
   </section>

   <section id="process" className="sv-process" aria-labelledby="sv-process-title">
    <motion.div {...fadeUp} className="sv-process-intro">
      <span className="sv-section-kicker">03 / SIMPLE FROM THE START</span>
      <h2 id="sv-process-title">Less setup.<br/><span>More making.</span></h2>
      <p>Install the desktop app, start your local brain, and open your first project. STAR's advanced controls are there when you need them.</p>
      <a className="sv-button sv-button-primary" href={WEBSITE_RELEASES}><Download size={17}/> Get STAR Intelligence <ArrowRight size={17}/></a>
    </motion.div>
    <div className="sv-process-list">
     {[
      {number:'01',title:'Install STAR',copy:'Download the latest verified Windows installer from GitHub Releases. STAR keeps its application files separate from your chats and models.'},
      {number:'02',title:'Start your local brain',copy:'Download the official checksum-verified model and engine from inside the application. Test an actual AI response before you rely on it.'},
      {number:'03',title:'Create in your workspace',copy:'Chat, attach references and connect an authorized Roblox Studio test project when you choose to.'}
     ].map(step=><div className="sv-process-step" key={step.number}>
       <span className="sv-process-number">{step.number}</span><div><h3>{step.title}</h3><p>{step.copy}</p></div><ArrowUpRight size={18}/>
     </div>)}
    </div>
   </section>

   <section className="sv-faq" aria-labelledby="sv-faq-title">
    <div><span className="sv-section-kicker">GOOD TO KNOW</span><h2 id="sv-faq-title">Straight answers.</h2><p>STAR is evolving. Here's what it can and cannot do today.</p></div>
    <div className="sv-faq-list">
      <details><summary>Do I need to pay for a cloud model?<ChevronRight size={17}/></summary><p>No. STAR can run an open model locally. You still need sufficient PC resources and an initial model download.</p></details>
      <details><summary>Does it build Roblox games automatically?<ChevronRight size={17}/></summary><p>STAR helps inspect, plan and edit a selected Studio sandbox with permitted tools. Results need real testing and human review; it does not guarantee a complete production game.</p></details>
      <details><summary>Will updating remove my chats and models?<ChevronRight size={17}/></summary><p>The installer replaces application files and is designed to preserve separate local STAR data. Always keep backups of important projects.</p></details>
      <details><summary>Are the public statistics actual model benchmarks?<ChevronRight size={17}/></summary><p>No. Website statistics come from GitHub releases, pull requests, issues and repository activity. Local response speed and task outcomes are only measured in the Windows application. We do not invent intelligence scores.</p></details>
      <details><summary>When will web search, more models and subagents arrive?<ChevronRight size={17}/></summary><p>They are active development priorities, not promised release dates. The roadmap links to the code changes and review status so you can check what has actually shipped.</p></details>
    </div>
   </section>
   <section className="sv-final" aria-labelledby="sv-final-title"><span className="sv-final-mark">✦</span>
    <span className="sv-section-kicker">YOUR NEXT PROJECT IS WAITING</span>
    <h2 id="sv-final-title">Make your next<br/><em>big thing.</em></h2>
    <p>Built for ambitious ideas, detailed work, and the joy of creating something real.</p>
    <a className="sv-button sv-button-primary" href={WEBSITE_RELEASES}><ArrowDownToLine size={18}/> Download STAR <ArrowRight size={17}/></a>
   </section>
  </main>
  <footer className="sv-footer"><Brand small/><p>© 2026 STAR Intelligence. Local-first, built to evolve.</p>
   <nav aria-label="Footer navigation"><a href={WEBSITE_REPO} target="_blank" rel="noopener noreferrer">Source <Github size={14}/></a>
    <a href={WEBSITE_RELEASES}>Releases <ExternalLink size={14}/></a>
    <a href={WEBSITE_REPO+'/issues'}>Feedback <BookOpen size={14}/></a></nav>
  </footer>
 </div>
}
