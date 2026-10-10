import {useCallback,useEffect,useRef,useState} from 'react'
import {AnimatePresence,MotionConfig,motion} from 'motion/react'
import {Activity,ArrowRight,ArrowUp,BookOpen,Boxes,BrainCircuit,Check,ChevronDown,ChevronRight,Command,Copy,Download,ExternalLink,File,Folder,FolderOpen,Globe,HardDrive,ImagePlus,Info,LayoutDashboard,LoaderCircle,MessageCircleMore,Mic,Monitor,MoreHorizontal,Plus,RefreshCcw,Search,Send,Settings2,Shield,ShieldCheck,SlidersHorizontal,Sparkles,SquarePen,Star,Terminal,Trash2,Upload,Workflow,X, Zap} from 'lucide-react'
import {AnalyticsView} from './Charts'
import {Brand,EmptyState,Message,Panel,PrivacyNote,Starlight,Tag} from './components'
import {examples,WEBSITE_RELEASES,WEBSITE_REPO} from './constants'
import {onBackendEvent,request} from './bridge'
import type {Analytics,AppSettings,BackendEvent,BootData,ChatMessage} from './types'
import './desktop-v2.css'

type Tab='chat'|'projects'|'brain'|'analytics'|'tools'|'library'|'settings'
type UpdateInfo={available:boolean;version:string;url:string;requires_browser?:boolean;explanation?:string}
const sections:[Tab,string,typeof MessageCircleMore][]=[['chat','Chat',MessageCircleMore],['projects','Projects',Boxes],['brain','STAR Brain',BrainCircuit],['analytics','Analytics',Activity],['tools','Developer tools',Workflow],['library','Library',BookOpen],['settings','Settings',Settings2]]
const truncate=(s:string,n=90)=>s.length>n?s.slice(0,n-1)+'…':s
const friendly=(v:unknown)=>typeof v==='string'?v:JSON.stringify(v,null,2)
const defaultSettings:AppSettings={endpoint:'http://127.0.0.1:8080/v1',provider:'local',model:'',fast_model:'',reasoning_model:'',roblox_model:'',vision_model:'',router_models_dir:'',router_context:4096,gpu_layers:25,project:'STAR',workspace:'',studio_id:'',studio_edit:false,workspace_edit:false,max_calls:12,context_chars:26000,reduced_motion:false,comfy_workflow:'',comfy_prompt_node:'6',comfy_port:8188,obsidian_vault:'',obsidian_enabled:false,skills_enabled:true,graphify_enabled:true}
const makeMsg=(role:ChatMessage['role'],text:string,attachments?:string[]):ChatMessage=>({id:crypto.randomUUID(),role,text,created:new Date().toISOString(),attachments})
const emptyAnalytics:Analytics={started:0,succeeded:0,failed:0,tools:0,rejected:0,median_ms:null,messages:0,project:'STAR',period_days:14,trend:[],recent:[]}

function initialPreviewTab(preview:boolean):Tab {
 const value=new URLSearchParams(window.location.search).get('tab')
 if(preview&&value&&['chat','projects','brain','analytics','tools','library','settings'].includes(value))return value as Tab
 return 'chat'
}
export function Desktop({initial=null,preview=false}:{initial?:BootData|null;preview?:boolean}) {
 const [tab,setTab]=useState<Tab>(()=>initialPreviewTab(preview))
 const [data,setData]=useState<BootData>(initial??{version:'0.8.1',project:'STAR',projects:[],messages:[],settings:defaultSettings,brain_installed:false,brain_running:false,analytics:emptyAnalytics,release_url:WEBSITE_RELEASES,credentials:{}})
 const [messages,setMessages]=useState<ChatMessage[]>(initial?.messages??[])
 const [prompt,setPrompt]=useState('')
 const [chatMode,setChatMode]=useState<'fast'|'auto'|'agent'>('auto')
 const [research,setResearch]=useState(false)
 const [githubSource,setGithubSource]=useState(false)
 const [imageMode,setImageMode]=useState(false)
 const [keyProvider,setKeyProvider]=useState('groq')
 const [providerKey,setProviderKey]=useState('')
 const [files,setFiles]=useState<string[]>([])
 const [busy,setBusy]=useState(false)
 const [notice,setNotice]=useState('')
 const [workPhase,setWorkPhase]=useState('')
 const [streamingText,setStreamingText]=useState('')
 const [chatSearch,setChatSearch]=useState('')
 const [showChatSearch,setShowChatSearch]=useState(false)
 const [retryText,setRetryText]=useState('')
 const [modelCheck,setModelCheck]=useState<{ok:boolean;model:string;sample:string}|null>(null)
 const [modelChecking,setModelChecking]=useState(false)
 const [routerBusy,setRouterBusy]=useState(false)
 const [teamChecking,setTeamChecking]=useState(false)
 const [teamResult,setTeamResult]=useState<{all_text_ready:boolean;note:string;roles:Record<string,{model:string;ok:boolean;sample?:string;error_type?:string}>}|null>(null)
 const [brainProgress,setBrainProgress]=useState<{phase:string;downloaded:number;total:number}|null>(null)
 const [update,setUpdate]=useState<UpdateInfo|null>(null)
 const [updateBusy,setUpdateBusy]=useState(false)
 const [updateProgress,setUpdateProgress]=useState<{phase:string;downloaded:number;total:number}|null>(null)
 const [studio,setStudio]=useState('')
 const [draft,setDraft]=useState<AppSettings>(initial?.settings??defaultSettings)
 const [newProject,setNewProject]=useState('')
 const [leftOpen,setLeftOpen]=useState(false)
 const [modelList,setModelList]=useState<string[]>([])
 const [themeMotion,setThemeMotion]=useState(!initial?.settings?.reduced_motion)
 const running=useRef<Map<string,string>>(new Map())
 const scrollTo=useRef<HTMLDivElement>(null)
 const composerRef=useRef<HTMLTextAreaElement>(null)
 const lastSent=useRef('')
 const lastProject=useRef(data.project)
 const inactive=preview||!initial
 const brainReady=data.settings.provider==='local'?data.brain_running:Boolean(data.credentials?.[data.settings.provider])
 const brainLabel=data.settings.provider==='local'?'STAR Brain':'Cloud model'
 const sync=useCallback(async(refreshChat=true)=>{
   if(inactive)return
   const r=await request<BootData>('bootstrap')
   if(r.ok&&r.data){setData(r.data);setDraft(r.data.settings);if(refreshChat)setMessages(r.data.messages);setThemeMotion(!r.data.settings.reduced_motion)}
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
     }else if(action==='sendMessage'||action==='generateImage'){
       const info=(event.data||{}) as {phase?:string;delta?:string}
       if(typeof info.delta==='string'&&info.delta){
         setStreamingText(previous=>previous+info.delta)
         setWorkPhase('Writing your response…')
       }else{
         const detail=typeof event.data==='string'?event.data:String(info.phase||'STAR is working…')
         setWorkPhase(truncate(detail,120))
       }
     }else if(action==='testModelTeam'){
       const detail=(event.data||{}) as {phase?:string;model?:string}
       setNotice(String(detail.phase||'Testing models')+(detail.model?' · '+detail.model:''))
     }else if(action==='installUpdate'){
       const detail=(event.data||{}) as {phase?:string;downloaded?:number;total?:number}
       setUpdateProgress({phase:String(detail.phase||'Downloading update'),downloaded:Number(detail.downloaded||0),total:Number(detail.total||0)})
     }
     return
   }
   running.current.delete(event.requestId)
   if(event.kind==='error'){
     const msg=typeof event.data==='string'?event.data:String((event.data as {error?:string})?.error||'Task could not finish.')
     setNotice(msg);if(action==='sendMessage'||action==='generateImage'){setBusy(false);setWorkPhase('');setStreamingText('');setRetryText(lastSent.current);setMessages(m=>[...m,makeMsg('event',msg)])}
     if(action==='testModel')setModelChecking(false)
     if(action==='testModelTeam')setTeamChecking(false)
     if(action==='startModelRouter'||action==='stopBrain')setRouterBusy(false)
     if(action==='checkUpdates'||action==='installUpdate'){setUpdateBusy(false);setUpdateProgress(null)}
     if(action==='installBrain'||action==='startBrain')setBrainProgress(null)
     return
   }
   const result=event.data as Record<string,unknown>
   if(action==='sendMessage'||action==='generateImage'){
     setBusy(false);setWorkPhase('');setStreamingText('');setRetryText('');setNotice('');setMessages(m=>[...m,{...makeMsg('assistant',String(result?.answer||'')),image:typeof result?.image==='string'?result.image:undefined}]);void sync(false)
   }else if(action==='installBrain'||action==='startBrain'){
     setBrainProgress(null);setNotice('STAR Brain is ready to use.');void sync()
   }else if(action==='testModel'){
     setModelChecking(false);setModelCheck(result as {ok:boolean;model:string;sample:string});setNotice('STAR Brain responded successfully to a real prompt.')
   }else if(action==='startModelRouter'){
     setRouterBusy(false);setModelList(Array.isArray(result.models)?result.models as string[]:[])
     setNotice('Local router is reachable. Select and test your model before relying on it.');void sync()
   }else if(action==='stopBrain'){
     setRouterBusy(false);setNotice('Managed STAR model server stopped. Conversations and model files are preserved.');void sync()
   }else if(action==='testModelTeam'){
     setTeamChecking(false)
     const report=result as {all_text_ready:boolean;note:string;roles:Record<string,{model:string;ok:boolean;sample?:string;error_type?:string}>}
     setTeamResult(report)
     setNotice(report.all_text_ready?'Configured models passed text tests.':'Some configured models failed text tests. Check their availability.')
   }else if(action==='checkUpdates'){
     setUpdateBusy(false)
     setUpdate(result as unknown as UpdateInfo)
     if(result.requires_browser)setNotice(String(result.explanation||'Download this version from GitHub Releases.'))
     else setNotice(result.available?`STAR v${result.version} is ready to install.`:'STAR is up to date.')
   }else if(action==='installUpdate'){
     setUpdateBusy(false);setUpdateProgress(null)
     setNotice('Verified setup launched. STAR will restart after installation.')
   }
   else if(action==='discoverStudio')setStudio(JSON.stringify(result,null,2))
   else if(action==='listModels')setModelList(Array.isArray(result.models)?result.models as string[]:[])
   else if(action==='transcribe')setPrompt(p=>p+(p?'\n':'')+String(result.text||''))
   else void sync()
 }),[sync])

 const send=useCallback(async(text=prompt)=>{
   const value=text.trim();if(busy||!value)return
   if(inactive){setNotice('This preview does not run a model. Download STAR to chat locally.');return}
   const selected=files.slice()
   lastSent.current=value
   setRetryText('');setStreamingText('');setChatSearch('');setShowChatSearch(false)
   setMessages(m=>[...m,makeMsg('user',value,selected.map(f=>f.split(/[\\/]/).pop()||f))]);setFiles([]);setPrompt('');setBusy(true);setWorkPhase('Preparing your response…');setNotice('');setTab('chat')
   const res=await act(imageMode?'generateImage':'sendMessage',{prompt:value,...(imageMode?{}:{files:selected,mode:chatMode,research,github:chatMode==='agent'&&githubSource})})
   if(!res){setBusy(false);setWorkPhase('');setRetryText(value);setMessages(m=>[...m,makeMsg('event','STAR could not start this request. Check the model or image workflow in Settings.')])}
 },[prompt,busy,files,inactive,act,imageMode,chatMode,research])

 useEffect(()=>{
   const onShortcut=(e:KeyboardEvent)=>{
     const mod=e.ctrlKey||e.metaKey
     if(mod&&e.key.toLowerCase()==='k'){
       e.preventDefault();setTab('chat');composerRef.current?.focus()
     }else if(mod&&e.key===','){
       e.preventDefault();setTab('settings')
     }else if(e.key==='Escape'){
       setLeftOpen(false);setNotice('')
     }
   }
   window.addEventListener('keydown',onShortcut)
   return ()=>window.removeEventListener('keydown',onShortcut)
 },[])
 const attach=async()=>{const v=await act('pickFiles');if(Array.isArray(v))setFiles(f=>[...f,...v.map(String)].slice(0,8))}
 const changeProject=async(name:string)=>{const v=await act('switchProject',{project:name});if(v){const b=v as BootData;setData(b);setDraft(b.settings);setMessages(b.messages);lastProject.current=name;setTab('chat')}setLeftOpen(false)}
 const saveSettings=async()=>{const v=await act('saveSettings',{settings:draft});if(v){setNotice('Settings saved.');setModelCheck(null);void sync()}}
 const stopChat=async()=>{if(!busy)return;setWorkPhase('Stopping request…');await act('cancelMessage')}
 const saveKey=async()=>{if(!providerKey.trim())return;const result=await act('saveProviderKey',{provider:keyProvider,key:providerKey.trim()});if(result){setProviderKey('');setNotice('API key saved securely on this computer.');void sync()}}
 const removeKey=async()=>{const result=await act('clearProviderKey',{provider:keyProvider});if(result){setProviderKey('');setNotice('Saved credential cleared.');void sync()}}
 const testActualModel=async()=>{
   if(modelChecking)return
   setModelChecking(true);setModelCheck(null)
   const response=await act('testModel')
   if(!response)setModelChecking(false)
 }
 const startLocalRouter=async()=>{
   if(routerBusy||busy)return
   setRouterBusy(true);setNotice('Starting the local model router…')
   const saved=await act('saveSettings',{settings:draft})
   if(!saved){setRouterBusy(false);return}
   const launched=await act('startModelRouter')
   if(!launched)setRouterBusy(false)
 }
 const stopLocalBrain=async()=>{
   if(routerBusy||busy)return
   setRouterBusy(true)
   const stopped=await act('stopBrain')
   if(!stopped)setRouterBusy(false)
 }
 const testSpecialists=async()=>{
   if(teamChecking||busy)return
   setTeamChecking(true);setTeamResult(null);setNotice('Testing the configured model team…')
   const saved=await act('saveSettings',{settings:draft})
   if(!saved){setTeamChecking(false);return}
   const result=await act('testModelTeam')
   if(!result)setTeamChecking(false)
 }
 const copyConversation=async()=>{
   if(!messages.length){setNotice('Nothing to copy yet.');return}
   const transcript=messages.map(m=>(m.role==='assistant'?'STAR':m.role==='user'?'You':'System')+':\n'+m.text).join('\n\n---\n\n')
   try{
     if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(transcript);setNotice('Conversation copied to clipboard.');return}
   }catch{/* Local Qt WebEngine clipboard may be unavailable; use native bridge below. */}
   const response=await act('copyText',{text:transcript})
   if(response)setNotice('Conversation copied to clipboard.')
 }
 const checkForUpdates=async()=>{
   if(updateBusy)return
   setUpdateBusy(true);setUpdateProgress(null)
   const response=await act('checkUpdates')
   if(!response)setUpdateBusy(false)
 }
 const installVerifiedUpdate=async()=>{
   if(updateBusy||!update?.available||update.requires_browser)return
   setUpdateBusy(true)
   setUpdateProgress({phase:'Checking trusted release details',downloaded:0,total:0})
   const response=await act('installUpdate')
   if(!response){setUpdateBusy(false);setUpdateProgress(null)}
 }
 const nav=(id:Tab)=>{setTab(id);setLeftOpen(false);if(id==='analytics')void sync()}
 const wrapper='shell '+(!leftOpen?'':'shell-open')
 const matchingMessages=chatSearch.trim()?messages.filter(m=>m.text.toLowerCase().includes(chatSearch.trim().toLowerCase())):messages
 return <MotionConfig reducedMotion={themeMotion?'user':'always'}><div className={wrapper} data-preview={preview}>
   <aside className="sidebar" aria-label="STAR navigation">
     <div className="brand-area"><Brand/><button className="sidebar-collapse icon-button" aria-label="Close menu" onClick={()=>setLeftOpen(false)}><X size={16}/></button></div>
     <div className="workspace-selector"><button type="button" onClick={()=>nav('projects')}><span className="workspace-tile"><Folder size={17}/></span><span className="workspace-label"><strong>{data.project}</strong><small>Local workspace</small></span><ChevronDown size={15}/></button></div>
     <div className="nav-block"><span className="nav-label">WORKSPACE</span>{sections.slice(0,4).map(([id,text,Icon])=><button key={id} className={'nav-item '+(tab===id?'active':'')} onClick={()=>nav(id)} aria-current={tab===id?'page':undefined}><Icon size={18} strokeWidth={1.85}/>{text}{tab===id?<motion.span className="nav-marker" layoutId="active-nav" transition={{type:'spring',stiffness:440,damping:36}}/>:null}</button>)}</div>
     <div className="nav-block"><span className="nav-label">DEVELOPMENT</span>{sections.slice(4).map(([id,text,Icon])=><button key={id} className={'nav-item '+(tab===id?'active':'')} onClick={()=>nav(id)} aria-current={tab===id?'page':undefined}><Icon size={18} strokeWidth={1.85}/>{text}{tab===id?<motion.span className="nav-marker" layoutId="active-nav"/>:null}</button>)}</div>
     <div className="sidebar-fill"/>
     <div className="sidebar-footer"><div className="sidebar-engine"><span className={'status-dot '+(brainReady?'ok':'')}/><span>{brainReady?`${brainLabel} online`:'Model not connected'}</span><button className="icon-button" aria-label="Go to STAR Brain" onClick={()=>nav('brain')}><ChevronRight size={14}/></button></div><div className="sidebar-version"><span>STAR GENESIS</span><span>v{data.version}</span></div></div>
   </aside>
   <div className="shell-main">
     <header className="topbar"><div className="topbar-left"><button className="hamburger icon-button" aria-label="Open navigation" onClick={()=>setLeftOpen(true)}><MoreHorizontal size={20}/></button><span className="crumb-muted">Workspace</span><ChevronRight size={13}/><strong>{sections.find(x=>x[0]===tab)?.[1]}</strong></div><div className="topbar-right"><span className="topbar-private"><ShieldCheck size={14}/> Local-first</span><button className="topbar-update" type="button" onClick={()=>nav('settings')} title="Open version and update settings"><Download size={14}/> v{data.version}</button><span className="topbar-pill"><span className={'status-dot '+(data.brain_running?'ok':'')}/>{brainReady?'Model ready':'Model offline'}</span><button className="avatar-button" onClick={()=>nav('settings')} title="Settings">S</button></div></header>
     {preview&&<div className="demo-ribbon"><Info size={14}/> Interactive interface preview — real AI features are available only in STAR Desktop.</div>}
     <AnimatePresence mode="wait" initial={false}>
       <motion.main key={tab} className="page-stage" initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-5}} transition={{duration:.16}}>
         {tab==='chat'&&<div className="chat-page">
           <div className="chat-topline">
             <div className="chat-top-context"><span className="eyebrow">CURRENT WORKSPACE / {data.project.toUpperCase()}</span><strong>Conversation</strong><small>Think, create, inspect and build with STAR.</small></div>
             <div className="chat-top-actions">
               {showChatSearch&&<input type="search" aria-label="Search this conversation" className="chat-find-input" autoFocus placeholder="Find in conversation…" value={chatSearch} onChange={e=>setChatSearch(e.target.value)}/>}
               <button type="button" className={'chat-tool-button'+(showChatSearch?' is-active':'')} title="Search messages" aria-label="Search messages" onClick={()=>{setShowChatSearch(v=>!v);setChatSearch('')}}><Search size={17}/></button>
               <button type="button" className="chat-tool-button chat-copy-control" title="Copy conversation" aria-label="Copy conversation" disabled={!messages.length} onClick={()=>void copyConversation()}><Copy size={16}/></button>
               <button type="button" className="chat-brain-control" title="STAR Brain settings" onClick={()=>nav('brain')}><span className={'status-dot '+(data.brain_running?'ok':'')}/><span>{brainReady?'Model connected':'Connect a model'}</span><ChevronRight size={13}/></button>
             </div>
           </div>
           <div className="chat-scroll"><div className="chat-inner">
           {!messages.length?<div className="welcome"><div className="welcome-star"><Star size={24} fill="currentColor" strokeWidth={1}/></div><div className="eyebrow">YOUR PERSONAL INTELLIGENCE</div><h1>What shall we <em>create</em> today?</h1><p>Ideas, code, design, and Roblox creation. One workspace for everything you want to build.</p><div className="suggestions">{examples.map(ex=><button key={ex.title} onClick={()=>send(ex.prompt)} disabled={busy}><span><Sparkles size={15}/>{ex.title}</span><small>{ex.description}</small><ArrowRight className="suggest-arrow" size={15}/></button>)}</div></div>:
           <div className="conversation">{matchingMessages.map(m=><Message key={m.id} entry={m}/>)}
             {showChatSearch&&chatSearch.trim()&&!matchingMessages.length&&<div className="chat-no-results"><Search size={20}/><strong>No matching messages</strong><small>Try searching for a different phrase.</small></div>}
             {busy&&streamingText&&<Message animated={false} key="stream-live" entry={{id:'stream-live',role:'assistant',text:streamingText}} partial/>}
             {busy&&<div className="thinking" role="status" aria-live="polite"><span className="pulse-bar"><i/><i/><i/></span><div><strong>STAR is working</strong><small>{workPhase||'Thinking through your request…'}</small></div></div>}
             {!busy&&retryText&&<div className="chat-recovery"><span>The last request did not finish. Your message is still here.</span><button type="button" onClick={()=>void send(retryText)}><RefreshCcw size={14}/> Retry message</button></div>}
             <div ref={scrollTo}/></div>}
         </div></div>
         <div className="composer-zone"><div className="composer">
           {!!files.length&&<div className="file-chips">{files.map((f,i)=><span key={f}><File size={14}/>{truncate(f.split(/[\\/]/).pop()||f,40)}<button title="Remove attachment" aria-label="Remove attachment" onClick={()=>setFiles(x=>x.filter((_,j)=>i!==j))}><X size={13}/></button></span>)}</div>}
           <label className="sr-only" htmlFor="star-prompt">Message STAR</label>
           <textarea ref={composerRef} id="star-prompt" rows={2} placeholder={imageMode?'Describe an image to generate…':research?'Ask STAR to research the web and cite sources…':'Ask STAR anything. Build, design, research, create…'} value={prompt} onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void send()}}}/>
           <div className="composer-tools"><div className="composer-left"><button className="attach-button" onClick={attach} title="Attach references"><Plus size={17}/> Add reference</button><span className="composer-separator"/>
                <button type="button" className={'composer-feature '+(research?'feature-active':'')} onClick={()=>setResearch(v=>!v)} disabled={busy||imageMode} title="Search the web with Brave or Tavily and cite sources"><Globe size={15}/> Web</button>
                <button type="button" className={'composer-feature '+(imageMode?'feature-active':'')} onClick={()=>{setImageMode(v=>!v);setFiles([])}} disabled={busy} title="Generate an image in chat using local ComfyUI"><ImagePlus size={15}/> Image</button>
                {chatMode==='agent'&&<button type="button" className={'composer-feature '+(githubSource?'feature-active':'')} onClick={()=>setGithubSource(v=>!v)} disabled={busy||imageMode} title="Inspect public STAR GitHub source code (read-only)"><Terminal size={15}/> GitHub</button>}
                <label className="mode-picker"><span className="sr-only">Chat mode</span><select aria-label="Chat mode" value={chatMode} onChange={e=>setChatMode(e.target.value as 'fast'|'auto'|'agent')} disabled={busy||imageMode}><option value="fast">Fast</option><option value="auto">Auto</option><option value="agent">Agent</option></select></label>
                <span className="composer-separator"/><button className="icon-button" aria-label="Start voice transcription" onClick={async()=>{const r=await act('pickFiles',{kind:'audio'});if(Array.isArray(r)&&r[0])void act('transcribe',{file:r[0]})}}><Mic size={17}/></button><span className="composer-model"><span className={'status-dot '+(data.brain_running?'ok':'')}/>{truncate(data.settings.model||'No model selected',22)}</span></div><div className="composer-right"><span>Enter to send</span><button className={'send-button '+(busy?'send-stop':'')} aria-label={busy?'Stop response':'Send message'} title={busy?'Stop this request':'Send message'} disabled={!busy&&!prompt.trim()} onClick={()=>busy?void stopChat():void send()}>{busy?<X size={19}/>:<ArrowUp size={19}/>}</button></div></div>
         </div><div className="composer-hint"><PrivacyNote/><span>{imageMode?'Local image generation · your image appears in chat':githubSource&&chatMode==='agent'?'GitHub source inspection: public STAR files only · read-only':research?'Live web citations enabled · source snippets are untrusted':'Enter sends · Shift+Enter new line · Ctrl+K chat · Ctrl+, settings'}</span></div></div></div>}
         {tab==='analytics'&&<AnalyticsView data={data.analytics}/>}
         {tab==='projects'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="PROJECT MANAGEMENT" title="Your workspaces" description="Separate contexts, conversations, and design decisions for every project."/><div className="project-create"><input aria-label="New project name" value={newProject} onChange={e=>setNewProject(e.target.value)} placeholder="New project name" maxLength={60} onKeyDown={e=>{if(e.key==='Enter'&&newProject.trim()){void changeProject(newProject.trim());setNewProject('')}}}/><button className="primary-button" onClick={()=>{if(newProject.trim()){void changeProject(newProject.trim());setNewProject('')}}}><Plus size={17}/> New workspace</button></div><div className="project-grid">{[...new Set([data.project,...data.projects])].map(name=><button className={'project-card '+(name===data.project?'project-current':'')} key={name} onClick={()=>changeProject(name)}><FolderOpen size={25}/><strong>{name}</strong><span>{name===data.project?'Current workspace':'Open workspace'}</span><ArrowRight size={18}/></button>)}</div></div></div>}
         {tab==='brain'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="YOUR AI, ON YOUR PC" title="STAR Brain" description="One click to your private local intelligence. No separate chat application. No paid model API key."/><Panel className="brain-hero"><div className="brain-art"><div className="brain-core"><Star size={38} fill="currentColor"/></div><span className="brain-orbit orbit-one"/><span className="brain-orbit orbit-two"/></div><div><Tag kind={data.brain_running?'green':'gold'}>{data.brain_running?'Ready to create':'LOCAL INTELLIGENCE'}</Tag><h2>{data.brain_installed?'Your brain is installed.':'A real AI, running on your machine.'}</h2><p>Download a small vision-capable model with a verified engine. STAR manages the model and stores it locally.</p><button className="primary-button" disabled={brainProgress!==null} onClick={()=>void act(data.brain_installed?'startBrain':'installBrain')}><Download size={17}/>{data.brain_installed?'Start STAR Brain':'Download & launch STAR Brain'}<ArrowRight size={17}/></button></div></Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">INSTALLATION STATUS</span><h2>Local engine</h2></div><Tag kind={data.brain_running?'green':'neutral'}>{data.brain_running?'Running':data.brain_installed?'Installed':'Not installed'}</Tag></div><p>{brainProgress?.phase||'Model downloads are saved on your PC and checked against published SHA-256 hashes.'}</p>{brainProgress&&<div className="progress-track"><motion.div animate={{width:brainProgress.total?`${Math.max(2,brainProgress.downloaded/brainProgress.total*100)}%`:'9%'}} transition={{duration:.25}}/></div>}<div className="brain-info"><span><HardDrive size={17}/> Several GB free space required</span><span><ShieldCheck size={17}/> Verified downloads</span><span><Monitor size={17}/> Tuned for smaller local models</span></div></Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">MODEL CONNECTION</span><h2>Installed model</h2></div><BrainCircuit size={20}/></div><p>{data.settings.model||'No model selected. Download STAR Brain to start.'}</p><small>{data.settings.endpoint}</small></Panel><Panel className="settings-section health-check-panel"><div className="section-heading"><div><span className="eyebrow">LIVE AI HEALTH CHECK</span><h2>Test a real response</h2></div><BrainCircuit size={20}/></div><p>Checking the model list does not prove that the AI can answer. Send a short, private test prompt to your selected local model and verify the chat template works.</p>
            <button type="button" className="secondary-button" disabled={modelChecking||inactive||!data.settings.model} onClick={()=>void testActualModel()}>{modelChecking?<LoaderCircle className="spin" size={16}/>:<Zap size={16}/>} {modelChecking?'Testing the model…':'Test actual AI response'}</button>
            {modelCheck&&<div className="health-result" role="status"><Check size={17}/><div><strong>Model answered successfully</strong><span>{modelCheck.sample}</span><small>{modelCheck.model}</small></div></div>}
            <small>Health checks run only on your configured localhost endpoint. No paid API or remote STAR server is required.</small>
           </Panel></div></div>}
         {tab==='tools'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="DEVELOPER WORKSPACE" title="Connect your tools" description="Give STAR only the project access it needs, then inspect and build with evidence."/><div className="two-up"><Panel className="settings-section"><div className="tool-icon"><Workflow size={22}/></div><h2>Roblox Studio</h2><p>Connect to the official Roblox Studio MCP server. Start in an unpublished test place.</p><button className="secondary-button" onClick={()=>void act('discoverStudio')}><RefreshCcw size={15}/> Discover Studio instances</button>{studio&&<pre className="tool-output">{truncate(studio,2400)}</pre>}</Panel><Panel className="settings-section"><div className="tool-icon"><Folder size={22}/></div><h2>Local workspace</h2><p>STAR can inspect a selected folder, and edit files only when you enable workspace write permissions.</p><Tag>{data.settings.workspace||'Not connected'}</Tag><button className="secondary-button" onClick={()=>nav('settings')}>Configure folder <ArrowRight size={14}/></button></Panel>
            </div>
            <div className="intelligence-heading"><div><span className="eyebrow">PROJECT INTELLIGENCE</span><h2>Knowledge, context & expert workflows</h2><p>Read only the information needed for your task. Nothing below grants shell access or runs downloaded skills.</p></div></div>
            <div className="intelligence-grid">
              <Panel className="settings-section integration-panel">
                <div className="integration-head"><div className="tool-icon"><BookOpen size={22}/></div><Tag kind={data.intelligence?.obsidian.enabled?'green':'neutral'}>{data.intelligence?.obsidian.enabled?'Read-only connected':'Off'}</Tag></div>
                <h2>Obsidian</h2><p>Search and read your local Markdown notes, design decisions and project research. Your vault stays on your PC.</p>
                <button className="secondary-button" onClick={()=>nav('settings')}>Configure vault <ArrowRight size={14}/></button>
              </Panel>
              <Panel className="settings-section integration-panel">
                <div className="integration-head"><div className="tool-icon"><Workflow size={22}/></div><Tag kind={data.intelligence?.graphify.export_detected?'green':'neutral'}>{data.intelligence?.graphify.export_detected?'Export detected':'No graph loaded'}</Tag></div>
                <h2>Graphify</h2><p>Trace the relationships between code, systems and dependencies from a generated <code>graphify-out/graph.json</code> file in your selected workspace.</p>
                <button className="secondary-button" onClick={()=>nav('settings')}>Project configuration <ArrowRight size={14}/></button>
              </Panel>
              <Panel className="settings-section integration-panel">
                <div className="integration-head"><div className="tool-icon"><BrainCircuit size={22}/></div><Tag kind={data.intelligence?.skills.enabled?'green':'neutral'}>{data.intelligence?.skills.enabled?'Available':'Off'}</Tag></div>
                <h2>Agent Skills</h2><p>{data.intelligence?.skills.count??0} local workflows discovered. STAR can load only the relevant instructions and references when a task requires them.</p>
                <button className="secondary-button" onClick={()=>nav('library')}>View knowledge library <ArrowRight size={14}/></button>
              </Panel>
            </div>
            <Panel className="settings-section"><h2><Shield size={18}/> Scoped access</h2><p>GitHub updates and model downloads never require your AI to see your private credentials. Publishing and unrestricted PC control are not enabled by default.</p><div className="toggle-line"><span>Studio edits</span><Tag kind={data.settings.studio_edit?'gold':'neutral'}>{data.settings.studio_edit?'Enabled':'Read only'}</Tag></div><div className="toggle-line"><span>Workspace writes</span><Tag kind={data.settings.workspace_edit?'gold':'neutral'}>{data.settings.workspace_edit?'Enabled':'Read only'}</Tag></div></Panel></div></div>}
         {tab==='library'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="PROJECT RESOURCES" title="Your library" description="Project references, verified decisions, conversation history, and generated files."/><div className="two-up"><Panel className="settings-section"><FolderOpen size={23} className="gold"/><h2>STAR data folder</h2><p>Local storage for saved conversations, checkpoints, images, and project knowledge.</p><button className="secondary-button" onClick={()=>void act('openDataFolder')}>Open local STAR files <ArrowRight size={15}/></button></Panel><Panel className="settings-section"><BookOpen size={23} className="gold"/><h2>Verified knowledge</h2><p>STAR only promotes reviewed, source-grounded knowledge into trusted project memory.</p><button className="secondary-button" onClick={()=>nav('projects')}>View projects <ArrowRight size={15}/></button></Panel></div><Panel className="settings-section"><h2>Image and media workflows</h2><p>STAR accepts image references, sampled video frames and optional audio transcripts in chat. Image generation uses an optional locally configured ComfyUI workflow.</p><button className="secondary-button" onClick={()=>void act('openLegacy')}>Open advanced Image Lab <ArrowRight size={15}/></button><small>Uses STAR's previous native tools while the React Image Lab is being migrated.</small></Panel></div></div>}
         {tab==='settings'&&<div className="scroll-region"><div className="page-wrap settings-page"><PageTitle eyebrow="PERSONALIZE YOUR WORKSPACE" title="Settings" description="Keep daily work simple; advanced integrations stay here when you need them."/><Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">MODEL ROUTING</span><h2>AI providers</h2></div><Globe size={20}/></div>
             <p>Keep STAR private with your on-device model, or connect a fast hosted model. Cloud providers receive the content you send to them. Free tiers have rate limits and may change.</p>
             <div className="field-grid"><label>Chat inference provider
               <select value={draft.provider} onChange={e=>{const id=e.target.value as AppSettings['provider'];const defaults:Record<string,string>={groq:'openai/gpt-oss-20b',openrouter:'openrouter/free',gemini:'gemini-2.5-flash-lite',cerebras:'gpt-oss-120b'};setDraft(d=>({...d,provider:id,model:defaults[id]||d.model,fast_model:'',reasoning_model:'',roblox_model:'',vision_model:''}))}}>
                 <option value="local">Local (llama.cpp / LM Studio)</option><option value="groq">GroqCloud · fast inference</option><option value="openrouter">OpenRouter · free model router</option><option value="gemini">Google Gemini API</option><option value="cerebras">Cerebras · fast inference</option>
               </select></label>
               <label>Credential to manage<select value={keyProvider} onChange={e=>{setKeyProvider(e.target.value);setProviderKey('')}}><option value="groq">Groq</option><option value="openrouter">OpenRouter</option><option value="gemini">Gemini API</option><option value="cerebras">Cerebras</option><option value="brave">Brave Search</option><option value="tavily">Tavily Search</option></select></label></div>
             <div className="provider-credential"><div><strong>{data.credentials?.[keyProvider]?'Credential configured':'Credential not configured'}</strong><small>Keys are stored in the operating system credential vault, never in your chat or project files.</small></div><Tag kind={data.credentials?.[keyProvider]?'green':'neutral'}>{data.credentials?.[keyProvider]?'Connected':'No key'}</Tag></div>
             <div className="credential-row"><input type="password" autoComplete="off" aria-label="New provider API key" value={providerKey} onChange={e=>setProviderKey(e.target.value)} placeholder="Paste API key (not shown after saving)"/><button className="secondary-button" disabled={!providerKey.trim()||inactive} onClick={()=>void saveKey()}><ShieldCheck size={15}/> Save key</button>{data.credentials?.[keyProvider]&&<button className="secondary-button" type="button" disabled={inactive} onClick={()=>void removeKey()}>Remove key</button>}</div>
             <small>After choosing a provider, save settings and test an actual response. Search keys enable the Web button in chat; keys do not enable automatic browsing. Your local Brain remains available when Cloud is selected.</small>
           </Panel><Panel className="settings-section"><div className="section-heading"><div><h2>AI model</h2><p>STAR Brain configures these automatically after installation.</p></div><BrainCircuit size={20}/></div><div className="field-grid"><label>Model ID<input list="star-known-models" value={draft.model} onChange={e=>setDraft(d=>({...d,model:e.target.value}))} placeholder="Installed model"/></label><label>Local endpoint<input value={draft.endpoint} onChange={e=>setDraft(d=>({...d,endpoint:e.target.value}))}/></label></div><button className="secondary-button" onClick={()=>void act('listModels')}>List available models <RefreshCcw size={14}/></button><button className="secondary-button" type="button" disabled={modelChecking||!draft.model} onClick={()=>void testActualModel()}>{modelChecking?<LoaderCircle className="spin" size={14}/>:<Zap size={14}/>} Test actual response</button>{modelCheck&&<div className="health-result"><Check size={16}/> <span>Live response: {modelCheck.sample}</span></div>}{modelList.length>0&&<small>Available: {modelList.join(', ')}</small>}</Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">SPECIALIST MODELS</span><h2>STAR model team</h2></div><BrainCircuit size={20}/></div><p>Optional model IDs for Fast, deeper reasoning, Roblox, and visual analysis. Leave fields blank to use your main model. Each ID must be available from the same selected inference provider; a standard single-model llama.cpp server cannot load several models just by naming them.</p><div className="field-grid"><label>Fast model<input list="star-known-models" value={draft.fast_model??''} placeholder="Default model" onChange={e=>setDraft(d=>({...d,fast_model:e.target.value}))}/></label><label>Reasoning model<input list="star-known-models" value={draft.reasoning_model??''} placeholder="Default model" onChange={e=>setDraft(d=>({...d,reasoning_model:e.target.value}))}/></label><label>Roblox specialist<input list="star-known-models" value={draft.roblox_model??''} placeholder="Reasoning model" onChange={e=>setDraft(d=>({...d,roblox_model:e.target.value}))}/></label><label>Vision specialist<input list="star-known-models" value={draft.vision_model??''} placeholder="Vision-capable model" onChange={e=>setDraft(d=>({...d,vision_model:e.target.value}))}/></label></div><datalist id="star-known-models">{modelList.map(id=><option key={id} value={id}/>)}</datalist><small>Auto selects a profile without another model call; Agent can delegate read-only drafts to the Fast model. No automatic cloud fallback or background model downloads. Use List available models above to see server-reported IDs. Test configured models before relying on them.</small>
             <div className="section-heading"><div><span className="eyebrow">LOCAL MODEL RUNTIME</span><h2>Managed GGUF models</h2></div><Tag kind={data.model_router_running?'green':'neutral'}>{data.model_router_running?'Router running':'Opt-in'}</Tag></div>
             <p>Choose a local folder of compatible GGUF models, then start the llama.cpp router. Only one large model stays loaded at a time to protect RAM. Models are not downloaded automatically and the current STAR Brain is never overwritten.</p>
             <div className="field-grid">
               <label>Local GGUF model folder<input aria-label="Local GGUF model folder" value={draft.router_models_dir??''} onChange={e=>setDraft(d=>({...d,router_models_dir:e.target.value}))} placeholder="C:\\Models\\STAR"/></label>
               <label>Model context tokens<input type="number" min="512" max="32768" step="512" value={draft.router_context??4096} onChange={e=>setDraft(d=>({...d,router_context:Number(e.target.value)}))}/></label>
               <label>GPU offload layers<input type="number" min="0" max="1000" value={draft.gpu_layers??25} onChange={e=>setDraft(d=>({...d,gpu_layers:Number(e.target.value)}))}/></label>
             </div>
             <div className="update-actions">
               <button className="secondary-button" type="button" disabled={routerBusy||inactive} onClick={async()=>{const result=await act('selectFolder');if(result&&typeof result==='object'&&'path' in result&&typeof result.path==='string'&&result.path){setDraft(d=>({...d,router_models_dir:result.path as string}))}}}><FolderOpen size={15}/> Choose folder</button>
               <button className="secondary-button" type="button" disabled={routerBusy||busy||inactive||draft.provider!=='local'||!draft.router_models_dir||data.brain_running} onClick={()=>void startLocalRouter()}>{routerBusy?<LoaderCircle className="spin" size={15}/>:<Zap size={15}/>} Start model router</button>
               <button className="secondary-button" type="button" disabled={routerBusy||busy||inactive||!data.brain_running} onClick={()=>void stopLocalBrain()}><SquarePen size={15}/> Stop managed Brain</button>
               <button className="secondary-button" type="button" disabled={teamChecking||busy||inactive||!draft.model} onClick={()=>void testSpecialists()}>{teamChecking?<LoaderCircle size={15} className="spin"/>:<ShieldCheck size={15}/>} Test model team</button>
             </div>
             {teamResult&&<div className="health-result"><div><strong>{teamResult.all_text_ready?'All configured models responded':'Some models need attention'}</strong>{Object.entries(teamResult.roles).map(([role,report])=><small key={role}>{role}: {report.model} — {report.ok?'Text reply verified':'Failed ('+(report.error_type||'unknown')+')'}</small>)}<small>{teamResult.note}</small></div></div>}
             <small>Save settings, start the router, choose a listed model and test a real response. Model team tests only basic text completion—not vision, tool calling, video understanding or Roblox editing. On a 32 GB system, benchmark a 27B quant before using it for everyday chat.</small>
           </Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">IMAGE STUDIO</span><h2>Generate images in chat</h2></div><ImagePlus size={20}/></div>
             <p>Connect a local ComfyUI server with an exported API-format workflow (core nodes only). The Image button in chat generates and displays a preview while keeping the original in STAR's data folder.</p>
             <div className="field-grid"><label>ComfyUI API workflow JSON<input value={draft.comfy_workflow} onChange={e=>setDraft(d=>({...d,comfy_workflow:e.target.value}))} placeholder="C:\\...\\workflow_api.json"/></label><label>CLIPTextEncode prompt node<input value={draft.comfy_prompt_node} onChange={e=>setDraft(d=>({...d,comfy_prompt_node:e.target.value}))} placeholder="6"/></label><label>Local ComfyUI port<input type="number" min="1" max="65535" value={draft.comfy_port} onChange={e=>setDraft(d=>({...d,comfy_port:Number(e.target.value)}))}/></label></div>
             <small>ComfyUI must already be running on 127.0.0.1. Generation is optional and does not require a paid image API. Changes take effect after Save settings.</small>
           </Panel><Panel className="settings-section"><h2>Developer permissions</h2><div className="field-grid"><label>Workspace folder<input value={draft.workspace} onChange={e=>setDraft(d=>({...d,workspace:e.target.value}))} placeholder="Choose a project folder"/></label><label>Roblox Studio instance ID<input value={draft.studio_id} onChange={e=>setDraft(d=>({...d,studio_id:e.target.value}))}/></label></div><label className="setting-switch"><span><strong>Allow workspace writes</strong><small>Only inside your selected workspace</small></span><input type="checkbox" checked={draft.workspace_edit} onChange={e=>setDraft(d=>({...d,workspace_edit:e.target.checked}))}/></label><label className="setting-switch"><span><strong>Allow Studio edits</strong><small>Use an unpublished disposable test place first</small></span><input type="checkbox" checked={draft.studio_edit} onChange={e=>setDraft(d=>({...d,studio_edit:e.target.checked}))}/></label></Panel>
           <Panel className="settings-section">
             <div className="section-heading"><div><span className="eyebrow">LOCAL INTELLIGENCE</span><h2>Knowledge & expert tools</h2></div><BookOpen size={20}/></div>
             <p>New tools are strictly read-only. STAR discovers them on demand to avoid slowing ordinary conversations.</p>
             <label className="setting-switch"><span><strong>Enable Agent Skills</strong><small>Load relevant local SKILL.md instructions; never auto-run bundled code.</small></span><input type="checkbox" checked={draft.skills_enabled??true} onChange={e=>setDraft(d=>({...d,skills_enabled:e.target.checked}))}/></label>
             <label className="setting-switch"><span><strong>Enable Graphify graph queries</strong><small>Use graphify-out/graph.json in your selected project workspace; generation is a separate local step.</small></span><input type="checkbox" checked={draft.graphify_enabled??true} onChange={e=>setDraft(d=>({...d,graphify_enabled:e.target.checked}))}/></label>
             <label className="setting-switch"><span><strong>Allow read-only Obsidian vault access</strong><small>STAR may search Markdown notes only in the folder you explicitly select.</small></span><input type="checkbox" checked={draft.obsidian_enabled??false} onChange={e=>setDraft(d=>({...d,obsidian_enabled:e.target.checked}))}/></label>
             <div className="intelligence-folder-row"><label>Obsidian vault folder<input aria-label="Obsidian vault folder" value={draft.obsidian_vault??''} onChange={e=>setDraft(d=>({...d,obsidian_vault:e.target.value}))} placeholder="Choose an Obsidian Markdown vault"/></label><button type="button" className="secondary-button" onClick={async()=>{const result=await act('selectFolder');if(result&&typeof result==='object'&&'path' in result&&typeof result.path==='string'&&result.path){setDraft(d=>({...d,obsidian_vault:result.path as string}))}}}><FolderOpen size={15}/> Browse folder</button></div>
             <small>Note contents stay local, are not promoted into trusted memory without review, and cannot override tool permissions.</small>
           </Panel>
           <Panel className="settings-section"><h2>Interface & performance</h2><label className="setting-switch"><span><strong>Reduce interface motion</strong><small>Respect your preference for quieter transitions</small></span><input type="checkbox" checked={draft.reduced_motion} onChange={e=>{setDraft(d=>({...d,reduced_motion:e.target.checked}));setThemeMotion(!e.target.checked)}}/></label><div className="field-grid"><label>Model turns per task<input type="number" min="1" max="30" value={draft.max_calls} onChange={e=>setDraft(d=>({...d,max_calls:Number(e.target.value)}))}/></label><label>Context character budget<input type="number" min="6000" max="80000" value={draft.context_chars} onChange={e=>setDraft(d=>({...d,context_chars:Number(e.target.value)}))}/></label></div></Panel><Panel className="settings-section updater-panel">
            <div className="section-heading"><div><span className="eyebrow">VERSION & UPDATES</span><h2>Stay up to date</h2></div><Tag kind={update?.available?'gold':'neutral'}>{update?.available?'Update ready':`v${data.version}`}</Tag></div>
            <p>STAR downloads official Windows releases, checks the exact file size and SHA-256 checksum, and replaces application files. Your chats, projects, memories, settings, and downloaded models remain in your local profile.</p>
            <div className="update-version-line"><span><strong>Installed</strong> v{data.version}</span><span><strong>Latest checked</strong> {update? `v${update.version}` : 'Not checked yet'}</span></div>
            {update?.available&&<div className="update-found"><Download size={18}/><div><strong>STAR v{update.version} is available</strong><small>Verify the installer, upgrade in place, and relaunch STAR.</small></div></div>}
            {update&&!update.available&&!update.requires_browser&&<div className="update-current"><Check size={16}/> You have the latest published STAR release.</div>}
            <div className="update-actions"><button className="secondary-button" type="button" disabled={updateBusy} onClick={()=>void checkForUpdates()}>{updateBusy&&!updateProgress?<LoaderCircle size={15} className="spin"/>:<RefreshCcw size={15}/>} {updateBusy&&!updateProgress?'Checking…':'Check for updates'}</button>
              {update?.available&&!update.requires_browser&&<button className="primary-button" type="button" disabled={updateBusy} onClick={()=>void installVerifiedUpdate()}><Download size={16}/> {updateBusy?'Preparing upgrade…':'Install & restart'}</button>}
              {update?.requires_browser&&<a className="secondary-button" href={WEBSITE_RELEASES} rel="noopener noreferrer" target="_blank"><ExternalLink size={15}/> Open public releases</a>}
            </div>
            {updateProgress&&<div className="update-download" role="status" aria-live="polite"><div className="update-download-label"><span>{updateProgress.phase}</span><strong>{updateProgress.total?Math.round(updateProgress.downloaded/updateProgress.total*100)+'%':'Preparing…'}</strong></div><div className="progress-track"><div className={updateProgress.total?'':'progress-indeterminate'} style={updateProgress.total?{width:`${Math.min(100,Math.round(updateProgress.downloaded/updateProgress.total*100))}%`}:undefined}/></div></div>}
            <small>Upgrades start only after you choose Install & restart. Installing does not erase your local data.</small>
           </Panel><button className="primary-button save-button" onClick={saveSettings}><Check size={17}/> Save settings</button></div></div>}
       </motion.main>
     </AnimatePresence>
     {notice&&<div role="status" className="toast"><Info size={16}/><span>{truncate(notice,240)}</span><button aria-label="Dismiss message" onClick={()=>setNotice('')}><X size={16}/></button></div>}
   </div>
   {leftOpen&&<button className="mobile-scrim" onClick={()=>setLeftOpen(false)} aria-label="Close navigation"/>}
 </div></MotionConfig>
}
function PageTitle({eyebrow,title,description}:{eyebrow:string;title:string;description:string}) {return <div className="page-intro"><span className="eyebrow">{eyebrow}</span><h1>{title}<span className="gold-dot">.</span></h1><p>{description}</p></div>}
