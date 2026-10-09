import {useCallback,useEffect,useRef,useState} from 'react'
import {AnimatePresence,motion} from 'motion/react'
import {Activity,ArrowRight,ArrowUp,BookOpen,Boxes,BrainCircuit,Check,ChevronDown,ChevronRight,Command,Download,ExternalLink,File,Folder,FolderOpen,Globe,HardDrive,ImagePlus,Info,LayoutDashboard,LoaderCircle,MessageCircleMore,Mic,Monitor,MoreHorizontal,Plus,RefreshCcw,Send,Settings2,Shield,ShieldCheck,SlidersHorizontal,Sparkles,SquarePen,Star,Terminal,Trash2,Upload,Workflow,X, Zap} from 'lucide-react'
import {AnalyticsView} from './Charts'
import {Brand,EmptyState,Message,Panel,PrivacyNote,Starlight,Tag} from './components'
import {examples,WEBSITE_RELEASES,WEBSITE_REPO} from './constants'
import {onBackendEvent,request} from './bridge'
import type {Analytics,AppSettings,BackendEvent,BootData,ChatMessage} from './types'

type Tab='chat'|'projects'|'brain'|'analytics'|'tools'|'library'|'settings'
const sections:[Tab,string,typeof MessageCircleMore][]=[['chat','Chat',MessageCircleMore],['projects','Projects',Boxes],['brain','STAR Brain',BrainCircuit],['analytics','Analytics',Activity],['tools','Developer tools',Workflow],['library','Library',BookOpen],['settings','Settings',Settings2]]
const truncate=(s:string,n=90)=>s.length>n?s.slice(0,n-1)+'…':s
const friendly=(v:unknown)=>typeof v==='string'?v:JSON.stringify(v,null,2)
const defaultSettings:AppSettings={endpoint:'http://127.0.0.1:8080/v1',model:'',project:'STAR',workspace:'',studio_id:'',studio_edit:false,workspace_edit:false,max_calls:12,context_chars:26000,reduced_motion:false}
const makeMsg=(role:ChatMessage['role'],text:string,attachments?:string[]):ChatMessage=>({id:crypto.randomUUID(),role,text,created:new Date().toISOString(),attachments})
const emptyAnalytics:Analytics={started:0,succeeded:0,failed:0,tools:0,rejected:0,median_ms:null,messages:0,project:'STAR',period_days:14,trend:[],recent:[]}

export function Desktop({initial=null,preview=false}:{initial?:BootData|null;preview?:boolean}) {
 const [tab,setTab]=useState<Tab>('chat')
 const [data,setData]=useState<BootData>(initial??{version:'0.7.0',project:'STAR',projects:[],messages:[],settings:defaultSettings,brain_installed:false,brain_running:false,analytics:emptyAnalytics,release_url:WEBSITE_RELEASES})
 const [messages,setMessages]=useState<ChatMessage[]>(initial?.messages??[])
 const [prompt,setPrompt]=useState('')
 const [files,setFiles]=useState<string[]>([])
 const [busy,setBusy]=useState(false)
 const [notice,setNotice]=useState('')
 const [brainProgress,setBrainProgress]=useState<{phase:string;downloaded:number;total:number}|null>(null)
 const [update,setUpdate]=useState<{available:boolean;version:string;url:string;requires_browser?:boolean;explanation?:string}|null>(null)
 const [studio,setStudio]=useState('')
 const [draft,setDraft]=useState<AppSettings>(initial?.settings??defaultSettings)
 const [newProject,setNewProject]=useState('')
 const [leftOpen,setLeftOpen]=useState(false)
 const [modelList,setModelList]=useState<string[]>([])
 const [themeMotion,setThemeMotion]=useState(!initial?.settings?.reduced_motion)
 const running=useRef<Map<string,string>>(new Map())
 const scrollTo=useRef<HTMLDivElement>(null)
 const lastProject=useRef(data.project)
 const inactive=preview||!initial
 const sync=useCallback(async()=>{
   if(inactive)return
   const r=await request<BootData>('bootstrap')
   if(r.ok&&r.data){setData(r.data);setDraft(r.data.settings);setMessages(r.data.messages);setThemeMotion(!r.data.settings.reduced_motion)}
 },[inactive])
 useEffect(()=>{if(!inactive) void sync()},[sync,inactive])
 useEffect(()=>{scrollTo.current?.scrollIntoView({block:'end',behavior:themeMotion?'smooth':'auto'})},[messages.length,themeMotion,tab])
 const act=useCallback(async(action:string,params:Record<string,unknown>={})=>{
   if(inactive){setNotice('This is a preview. Install STAR Desktop to use local AI and tools.');return null}
   const requestId=crypto.randomUUID()
   running.current.set(requestId,action) // Subscribe before a very fast worker can respond.
   const result=await request<unknown>(action,params,requestId)
   if(!result.ok){running.current.delete(requestId);setNotice(result.error||'STAR could not complete this action.');return null}
   if(result.pending)return result
   running.current.delete(requestId)
   return result.data
 },[inactive])
 useEffect(()=>onBackendEvent((event:BackendEvent)=>{
   const action=running.current.get(event.requestId)
   if(!action)return
   if(event.kind==='progress'){
     if(action==='installBrain'){
       const obj=(event.data||{}) as Record<string,unknown>
       setBrainProgress({phase:String(obj.phase||'Preparing your AI'),downloaded:Number(obj.overall_downloaded??obj.downloaded??0),total:Number(obj.overall_total??obj.total??0)})
     }else if(action==='sendMessage')setNotice(truncate(typeof event.data==='string'?event.data:'STAR is working…',120))
     return
   }
   running.current.delete(event.requestId)
   if(event.kind==='error'){
     const msg=typeof event.data==='string'?event.data:String((event.data as {error?:string})?.error||'Task could not finish.')
     setNotice(msg);if(action==='sendMessage'){setBusy(false);setMessages(m=>[...m,makeMsg('event',msg)])}
     return
   }
   const result=event.data as Record<string,unknown>
   if(action==='sendMessage'){
     setBusy(false);setNotice('');setMessages(m=>[...m,makeMsg('assistant',String(result?.answer||''))]);void sync()
   }else if(action==='installBrain'||action==='startBrain'){
     setBrainProgress(null);setNotice('STAR Brain is ready to use.');void sync()
   }else if(action==='checkUpdates'){
     setUpdate(result as unknown as typeof update)
     if(result.requires_browser)setNotice(String(result.explanation||'Download this version from GitHub Releases.'))
   }else if(action==='installUpdate')setNotice('Verified update downloaded. Windows Setup will upgrade STAR and restart it.')
   else if(action==='discoverStudio')setStudio(JSON.stringify(result,null,2))
   else if(action==='listModels')setModelList(Array.isArray(result.models)?result.models as string[]:[])
   else if(action==='generateImage')setNotice('Image generation completed. Check your generated images folder.')
   else if(action==='transcribe')setPrompt(p=>p+(p?'\n':'')+String(result.text||''))
   else void sync()
 }),[sync])

 const send=useCallback(async(text=prompt)=>{
   const value=text.trim();if(busy||!value)return
   if(inactive){setNotice('This preview does not run a model. Download STAR to chat locally.');return}
   const selected=files.slice()
   setMessages(m=>[...m,makeMsg('user',value,selected.map(f=>f.split(/[\\/]/).pop()||f))]);setFiles([]);setPrompt('');setBusy(true);setNotice('STAR is thinking…');setTab('chat')
   const res=await act('sendMessage',{prompt:value,files:selected})
   if(!res){setBusy(false);setMessages(m=>[...m,makeMsg('event','Could not connect to STAR Brain. Open STAR Brain and check that it is running.')])}
 },[prompt,busy,files,inactive,act])
 const attach=async()=>{const v=await act('pickFiles');if(Array.isArray(v))setFiles(f=>[...f,...v.map(String)].slice(0,8))}
 const changeProject=async(name:string)=>{const v=await act('switchProject',{project:name});if(v){const b=v as BootData;setData(b);setDraft(b.settings);setMessages(b.messages);lastProject.current=name;setTab('chat')}setLeftOpen(false)}
 const saveSettings=async()=>{const v=await act('saveSettings',{settings:draft});if(v){setNotice('Settings saved.');void sync()}}
 const nav=(id:Tab)=>{setTab(id);setLeftOpen(false);if(id==='analytics')void sync()}
 const wrapper='shell '+(!leftOpen?'':'shell-open')
 return <div className={wrapper} data-preview={preview}>
   <aside className="sidebar" aria-label="STAR navigation">
     <div className="brand-area"><Brand/><button className="sidebar-collapse icon-button" aria-label="Close menu" onClick={()=>setLeftOpen(false)}><X size={16}/></button></div>
     <div className="workspace-selector"><button type="button" onClick={()=>nav('projects')}><span className="workspace-tile"><Folder size={17}/></span><span className="workspace-label"><strong>{data.project}</strong><small>Local workspace</small></span><ChevronDown size={15}/></button></div>
     <div className="nav-block"><span className="nav-label">WORKSPACE</span>{sections.slice(0,4).map(([id,text,Icon])=><button key={id} className={'nav-item '+(tab===id?'active':'')} onClick={()=>nav(id)} aria-current={tab===id?'page':undefined}><Icon size={18} strokeWidth={1.85}/>{text}{tab===id?<motion.span className="nav-marker" layoutId="active-nav" transition={{type:'spring',stiffness:440,damping:36}}/>:null}</button>)}</div>
     <div className="nav-block"><span className="nav-label">DEVELOPMENT</span>{sections.slice(4).map(([id,text,Icon])=><button key={id} className={'nav-item '+(tab===id?'active':'')} onClick={()=>nav(id)} aria-current={tab===id?'page':undefined}><Icon size={18} strokeWidth={1.85}/>{text}{tab===id?<motion.span className="nav-marker" layoutId="active-nav"/>:null}</button>)}</div>
     <div className="sidebar-fill"/>
     <div className="sidebar-footer"><div className="sidebar-engine"><span className={'status-dot '+(data.brain_running?'ok':'')}/><span>{data.brain_running?'STAR Brain online':'Brain not running'}</span><button className="icon-button" aria-label="Go to STAR Brain" onClick={()=>nav('brain')}><ChevronRight size={14}/></button></div><div className="sidebar-version"><span>STAR GENESIS</span><span>v{data.version}</span></div></div>
   </aside>
   <div className="shell-main">
     <header className="topbar"><div className="topbar-left"><button className="hamburger icon-button" aria-label="Open navigation" onClick={()=>setLeftOpen(true)}><MoreHorizontal size={20}/></button><span className="crumb-muted">Workspace</span><ChevronRight size={13}/><strong>{sections.find(x=>x[0]===tab)?.[1]}</strong></div><div className="topbar-right"><span className="topbar-private"><ShieldCheck size={14}/> Local-first</span><span className="topbar-pill"><span className={'status-dot '+(data.brain_running?'ok':'')}/>{data.brain_running?'Brain ready':'Engine offline'}</span><button className="avatar-button" onClick={()=>nav('settings')} title="Settings">S</button></div></header>
     {preview&&<div className="demo-ribbon"><Info size={14}/> Interactive interface preview — real AI features are available only in STAR Desktop.</div>}
     <AnimatePresence mode="wait" initial={false}>
       <motion.main key={tab} className="page-stage" initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-5}} transition={{duration:.16}}>
         {tab==='chat'&&<div className="chat-page"><div className="chat-scroll"><div className="chat-inner">
           {!messages.length?<div className="welcome"><div className="welcome-star"><Star size={24} fill="currentColor" strokeWidth={1}/></div><div className="eyebrow">YOUR PERSONAL INTELLIGENCE</div><h1>What shall we <em>create</em> today?</h1><p>Ideas, code, design, and Roblox creation. One workspace for everything you want to build.</p><div className="suggestions">{examples.map(ex=><button key={ex.title} onClick={()=>send(ex.prompt)} disabled={busy}><span><Sparkles size={15}/>{ex.title}</span><small>{ex.description}</small><ArrowRight className="suggest-arrow" size={15}/></button>)}</div></div>:
           <div className="conversation">{messages.map(m=><Message key={m.id} entry={m}/>)}{busy&&<div className="thinking"><span className="pulse-bar"><i/><i/><i/></span>STAR is working on your request…</div>}<div ref={scrollTo}/></div>}
         </div></div>
         <div className="composer-zone"><div className="composer">
           {!!files.length&&<div className="file-chips">{files.map((f,i)=><span key={f}><File size={14}/>{truncate(f.split(/[\\/]/).pop()||f,40)}<button title="Remove attachment" aria-label="Remove attachment" onClick={()=>setFiles(x=>x.filter((_,j)=>i!==j))}><X size={13}/></button></span>)}</div>}
           <label className="sr-only" htmlFor="star-prompt">Message STAR</label>
           <textarea id="star-prompt" rows={2} placeholder="Ask STAR anything. Build, design, research, create…" value={prompt} onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void send()}}}/>
           <div className="composer-tools"><div className="composer-left"><button className="attach-button" onClick={attach} title="Attach references"><Plus size={17}/> Add reference</button><span className="composer-separator"/><button className="icon-button" aria-label="Start voice transcription" onClick={async()=>{const r=await act('pickFiles',{kind:'audio'});if(Array.isArray(r)&&r[0])void act('transcribe',{file:r[0]})}}><Mic size={17}/></button><span className="composer-model"><span className="status-dot"/>{truncate(data.settings.model||'No model selected',22)}</span></div><div className="composer-right"><span>Enter to send</span><button className="send-button" aria-label="Send message" disabled={!prompt.trim()||busy} onClick={()=>send()}>{busy?<LoaderCircle className="spin" size={19}/>:<ArrowUp size={19}/>}</button></div></div>
         </div><div className="composer-hint"><PrivacyNote/><span>STAR may make mistakes. Verify consequential changes.</span></div></div></div>}
         {tab==='analytics'&&<AnalyticsView data={data.analytics}/>}
         {tab==='projects'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="PROJECT MANAGEMENT" title="Your workspaces" description="Separate contexts, conversations, and design decisions for every project."/><div className="project-create"><input aria-label="New project name" value={newProject} onChange={e=>setNewProject(e.target.value)} placeholder="New project name" maxLength={60} onKeyDown={e=>{if(e.key==='Enter'&&newProject.trim()){void changeProject(newProject.trim());setNewProject('')}}}/><button className="primary-button" onClick={()=>{if(newProject.trim()){void changeProject(newProject.trim());setNewProject('')}}}><Plus size={17}/> New workspace</button></div><div className="project-grid">{[...new Set([data.project,...data.projects])].map(name=><button className={'project-card '+(name===data.project?'project-current':'')} key={name} onClick={()=>changeProject(name)}><FolderOpen size={25}/><strong>{name}</strong><span>{name===data.project?'Current workspace':'Open workspace'}</span><ArrowRight size={18}/></button>)}</div></div></div>}
         {tab==='brain'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="YOUR AI, ON YOUR PC" title="STAR Brain" description="One click to your private local intelligence. No separate chat application. No paid model API key."/><Panel className="brain-hero"><div className="brain-art"><div className="brain-core"><Star size={38} fill="currentColor"/></div><span className="brain-orbit orbit-one"/><span className="brain-orbit orbit-two"/></div><div><Tag kind={data.brain_running?'green':'gold'}>{data.brain_running?'Ready to create':'LOCAL INTELLIGENCE'}</Tag><h2>{data.brain_installed?'Your brain is installed.':'A real AI, running on your machine.'}</h2><p>Download a small vision-capable model with a verified engine. STAR manages the model and stores it locally.</p><button className="primary-button" disabled={brainProgress!==null} onClick={()=>void act(data.brain_installed?'startBrain':'installBrain')}><Download size={17}/>{data.brain_installed?'Start STAR Brain':'Download & launch STAR Brain'}<ArrowRight size={17}/></button></div></Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">INSTALLATION STATUS</span><h2>Local engine</h2></div><Tag kind={data.brain_running?'green':'neutral'}>{data.brain_running?'Running':data.brain_installed?'Installed':'Not installed'}</Tag></div><p>{brainProgress?.phase||'Model downloads are saved on your PC and checked against published SHA-256 hashes.'}</p>{brainProgress&&<div className="progress-track"><motion.div animate={{width:brainProgress.total?`${Math.max(2,brainProgress.downloaded/brainProgress.total*100)}%`:'9%'}} transition={{duration:.25}}/></div>}<div className="brain-info"><span><HardDrive size={17}/> Several GB free space required</span><span><ShieldCheck size={17}/> Verified downloads</span><span><Monitor size={17}/> Tuned for smaller local models</span></div></Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">MODEL CONNECTION</span><h2>Installed model</h2></div><BrainCircuit size={20}/></div><p>{data.settings.model||'No model selected. Download STAR Brain to start.'}</p><small>{data.settings.endpoint}</small></Panel></div></div>}
         {tab==='tools'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="DEVELOPER WORKSPACE" title="Connect your tools" description="Give STAR only the project access it needs, then inspect and build with evidence."/><div className="two-up"><Panel className="settings-section"><div className="tool-icon"><Workflow size={22}/></div><h2>Roblox Studio</h2><p>Connect to the official Roblox Studio MCP server. Start in an unpublished test place.</p><button className="secondary-button" onClick={()=>void act('discoverStudio')}><RefreshCcw size={15}/> Discover Studio instances</button>{studio&&<pre className="tool-output">{truncate(studio,2400)}</pre>}</Panel><Panel className="settings-section"><div className="tool-icon"><Folder size={22}/></div><h2>Local workspace</h2><p>STAR can inspect a selected folder, and edit files only when you enable workspace write permissions.</p><Tag>{data.settings.workspace||'Not connected'}</Tag><button className="secondary-button" onClick={()=>nav('settings')}>Configure folder <ArrowRight size={14}/></button></Panel></div><Panel className="settings-section"><h2><Shield size={18}/> Scoped access</h2><p>GitHub updates and model downloads never require your AI to see your private credentials. Publishing and unrestricted PC control are not enabled by default.</p><div className="toggle-line"><span>Studio edits</span><Tag kind={data.settings.studio_edit?'gold':'neutral'}>{data.settings.studio_edit?'Enabled':'Read only'}</Tag></div><div className="toggle-line"><span>Workspace writes</span><Tag kind={data.settings.workspace_edit?'gold':'neutral'}>{data.settings.workspace_edit?'Enabled':'Read only'}</Tag></div></Panel></div></div>}
         {tab==='library'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="PROJECT RESOURCES" title="Your library" description="Project references, verified decisions, conversation history, and generated files."/><div className="two-up"><Panel className="settings-section"><FolderOpen size={23} className="gold"/><h2>STAR data folder</h2><p>Local storage for saved conversations, checkpoints, images, and project knowledge.</p><button className="secondary-button" onClick={()=>void act('openDataFolder')}>Open local STAR files <ArrowRight size={15}/></button></Panel><Panel className="settings-section"><BookOpen size={23} className="gold"/><h2>Verified knowledge</h2><p>STAR only promotes reviewed, source-grounded knowledge into trusted project memory.</p><button className="secondary-button" onClick={()=>nav('projects')}>View projects <ArrowRight size={15}/></button></Panel></div><Panel className="settings-section"><h2>Image and media workflows</h2><p>STAR accepts image references, sampled video frames and optional audio transcripts in chat. Image generation uses an optional locally configured ComfyUI workflow.</p><button className="secondary-button" onClick={()=>void act('openLegacy')}>Open advanced Image Lab <ArrowRight size={15}/></button><small>Uses STAR's previous native tools while the React Image Lab is being migrated.</small></Panel></div></div>}
         {tab==='settings'&&<div className="scroll-region"><div className="page-wrap settings-page"><PageTitle eyebrow="PERSONALIZE YOUR WORKSPACE" title="Settings" description="Keep daily work simple; advanced integrations stay here when you need them."/><Panel className="settings-section"><div className="section-heading"><div><h2>Local model</h2><p>STAR Brain configures these automatically after installation.</p></div><BrainCircuit size={20}/></div><div className="field-grid"><label>Model ID<input value={draft.model} onChange={e=>setDraft(d=>({...d,model:e.target.value}))} placeholder="Installed model"/></label><label>Local endpoint<input value={draft.endpoint} onChange={e=>setDraft(d=>({...d,endpoint:e.target.value}))}/></label></div><button className="secondary-button" onClick={()=>void act('listModels')}>Check model connection <RefreshCcw size={14}/></button>{modelList.length>0&&<small>Available: {modelList.join(', ')}</small>}</Panel>
           <Panel className="settings-section"><h2>Developer permissions</h2><div className="field-grid"><label>Workspace folder<input value={draft.workspace} onChange={e=>setDraft(d=>({...d,workspace:e.target.value}))} placeholder="Choose a project folder"/></label><label>Roblox Studio instance ID<input value={draft.studio_id} onChange={e=>setDraft(d=>({...d,studio_id:e.target.value}))}/></label></div><label className="setting-switch"><span><strong>Allow workspace writes</strong><small>Only inside your selected workspace</small></span><input type="checkbox" checked={draft.workspace_edit} onChange={e=>setDraft(d=>({...d,workspace_edit:e.target.checked}))}/></label><label className="setting-switch"><span><strong>Allow Studio edits</strong><small>Use an unpublished disposable test place first</small></span><input type="checkbox" checked={draft.studio_edit} onChange={e=>setDraft(d=>({...d,studio_edit:e.target.checked}))}/></label></Panel>
           <Panel className="settings-section"><h2>Interface & performance</h2><label className="setting-switch"><span><strong>Reduce interface motion</strong><small>Respect your preference for quieter transitions</small></span><input type="checkbox" checked={draft.reduced_motion} onChange={e=>{setDraft(d=>({...d,reduced_motion:e.target.checked}));setThemeMotion(!e.target.checked)}}/></label><div className="field-grid"><label>Model turns per task<input type="number" min="1" max="30" value={draft.max_calls} onChange={e=>setDraft(d=>({...d,max_calls:Number(e.target.value)}))}/></label><label>Context character budget<input type="number" min="6000" max="80000" value={draft.context_chars} onChange={e=>setDraft(d=>({...d,context_chars:Number(e.target.value)}))}/></label></div></Panel><button className="primary-button save-button" onClick={saveSettings}><Check size={17}/> Save settings</button></div></div>}
       </motion.main>
     </AnimatePresence>
     {notice&&<div role="status" className="toast"><Info size={16}/><span>{truncate(notice,240)}</span><button aria-label="Dismiss message" onClick={()=>setNotice('')}><X size={16}/></button></div>}
   </div>
   {leftOpen&&<button className="mobile-scrim" onClick={()=>setLeftOpen(false)} aria-label="Close navigation"/>}
 </div>
}
function PageTitle({eyebrow,title,description}:{eyebrow:string;title:string;description:string}) {return <div className="page-intro"><span className="eyebrow">{eyebrow}</span><h1>{title}<span className="gold-dot">.</span></h1><p>{description}</p></div>}
