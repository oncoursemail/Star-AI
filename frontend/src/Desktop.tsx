import {useCallback,useEffect,useRef,useState} from 'react'
import {AnimatePresence,MotionConfig,motion} from 'motion/react'
import {Activity,ArrowRight,ArrowUp,BookOpen,Boxes,BrainCircuit,Check,ChevronDown,ChevronRight,Command,Copy,Download,ExternalLink,File,Folder,FolderOpen,Globe,HardDrive,ImagePlus,Info,LayoutDashboard,LoaderCircle,MessageCircleMore,Mic,Monitor,MoreHorizontal,Plus,RefreshCcw,Search,Send,Settings2,Shield,ShieldCheck,SlidersHorizontal,Sparkles,SquarePen,Star,Terminal,Trash2,Upload,Workflow,X, Zap} from 'lucide-react'
import {AnalyticsView} from './Charts'
import {Brand,EmptyState,Message,Panel,PrivacyNote,Starlight,Tag} from './components'
import {examples,WEBSITE_RELEASES,WEBSITE_REPO} from './constants'
import {onBackendEvent,request} from './bridge'
import type {Analytics,AppSettings,BackendEvent,BootData,ChatMessage} from './types'
import './desktop-v2.css'
import './stellar-ui.css'

type Tab='chat'|'projects'|'brain'|'analytics'|'tools'|'image'|'library'|'settings'
type UpdateInfo={available:boolean;version:string;url:string;requires_browser?:boolean;explanation?:string}
const sections:[Tab,string,typeof MessageCircleMore][]=[['chat','Chat',MessageCircleMore],['projects','Projects',Boxes],['brain','STAR Brain',BrainCircuit],['analytics','Analytics',Activity],['tools','Developer tools',Workflow],['image','Image Lab',ImagePlus],['library','Library',BookOpen],['settings','Settings',Settings2]]
const truncate=(s:string,n=90)=>s.length>n?s.slice(0,n-1)+'…':s
const friendly=(v:unknown)=>typeof v==='string'?v:JSON.stringify(v,null,2)
const defaultSettings:AppSettings={endpoint:'http://127.0.0.1:8080/v1',model:'',project:'STAR',workspace:'',studio_id:'',studio_edit:false,workspace_edit:false,max_calls:12,context_chars:26000,reduced_motion:false}
const makeMsg=(role:ChatMessage['role'],text:string,attachments?:string[]):ChatMessage=>({id:crypto.randomUUID(),role,text,created:new Date().toISOString(),attachments})
const emptyAnalytics:Analytics={started:0,succeeded:0,failed:0,tools:0,rejected:0,median_ms:null,messages:0,project:'STAR',period_days:14,trend:[],recent:[]}

function initialPreviewTab(preview:boolean):Tab {
 const value=new URLSearchParams(window.location.search).get('tab')
 if(preview&&value&&['chat','projects','brain','analytics','tools','image','library','settings'].includes(value))return value as Tab
 return 'chat'
}
export function Desktop({initial=null,preview=false}:{initial?:BootData|null;preview?:boolean}) {
 const [tab,setTab]=useState<Tab>(()=>initialPreviewTab(preview))
 const [data,setData]=useState<BootData>(initial??{version:'0.8.1',project:'STAR',projects:[],messages:[],active_chat:'',chats:[],settings:defaultSettings,brain_installed:false,brain_running:false,analytics:emptyAnalytics,release_url:WEBSITE_RELEASES})
 const [messages,setMessages]=useState<ChatMessage[]>(initial?.messages??[])
 const [prompt,setPrompt]=useState('')
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
 const [brainProgress,setBrainProgress]=useState<{phase:string;downloaded:number;total:number}|null>(null)
 const [update,setUpdate]=useState<UpdateInfo|null>(null)
 const [updateBusy,setUpdateBusy]=useState(false)
 const [updateProgress,setUpdateProgress]=useState<{phase:string;downloaded:number;total:number}|null>(null)
 const [studio,setStudio]=useState('')
 const [draft,setDraft]=useState<AppSettings>(initial?.settings??defaultSettings)
 const [newProject,setNewProject]=useState('')
 const [leftOpen,setLeftOpen]=useState(false)
 const [showJump,setShowJump]=useState(false)
 const [workflowPath,setWorkflowPath]=useState('')
 const [imagePrompt,setImagePrompt]=useState('')
 const [imageNode,setImageNode]=useState('')
 const [imagePort,setImagePort]=useState('8188')
 const [imageBusy,setImageBusy]=useState(false)
 const [generatedImages,setGeneratedImages]=useState<Array<{filename:string;preview:string}>>([])
 const [modelList,setModelList]=useState<string[]>([])
 const [themeMotion,setThemeMotion]=useState(!initial?.settings?.reduced_motion)
 const running=useRef<Map<string,string>>(new Map())
 const chatScroll=useRef<HTMLDivElement>(null)
 const followBottom=useRef(true)
 const composerRef=useRef<HTMLTextAreaElement>(null)
 const lastSent=useRef('')
 const lastProject=useRef(data.project)
 const inactive=preview||!initial
 const sync=useCallback(async()=>{
   if(inactive)return
   const r=await request<BootData>('bootstrap')
   if(r.ok&&r.data){setData(r.data);setDraft(r.data.settings);setMessages(r.data.messages);setThemeMotion(!r.data.settings.reduced_motion)}
 },[inactive])
 useEffect(()=>{if(!inactive) void sync()},[sync,inactive])
 useEffect(()=>{
   const node=chatScroll.current
   if(tab==='chat'&&node&&followBottom.current){node.scrollTop=node.scrollHeight;setShowJump(false)}
 },[messages.length,streamingText,busy,tab,data.active_chat])
 useEffect(()=>{
   const node=composerRef.current
   if(!node)return
   node.style.height='auto'
   node.style.height=Math.min(Math.max(node.scrollHeight,48),176)+'px'
 },[prompt,files.length])
 const onChatScroll=()=>{
   const node=chatScroll.current
   if(!node)return
   const atBottom=node.scrollHeight-node.scrollTop-node.clientHeight<125
   followBottom.current=atBottom
   setShowJump(!atBottom)
 }
 const jumpToLatest=()=>{
   followBottom.current=true
   if(chatScroll.current)chatScroll.current.scrollTo({top:chatScroll.current.scrollHeight,behavior:themeMotion?'smooth':'auto'})
   setShowJump(false)
 }
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
     }else if(action==='sendMessage'){
       const info=(event.data||{}) as {phase?:string;delta?:string}
       if(typeof info.delta==='string'&&info.delta){
         setStreamingText(previous=>previous+info.delta)
         setWorkPhase('Writing your response…')
       }else{
         const detail=typeof event.data==='string'?event.data:String(info.phase||'STAR is working…')
         setWorkPhase(truncate(detail,120))
       }
     }else if(action==='installUpdate'){
       const detail=(event.data||{}) as {phase?:string;downloaded?:number;total?:number}
       setUpdateProgress({phase:String(detail.phase||'Downloading update'),downloaded:Number(detail.downloaded||0),total:Number(detail.total||0)})
     }
     return
   }
   running.current.delete(event.requestId)
   if(event.kind==='error'){
     const msg=typeof event.data==='string'?event.data:String((event.data as {error?:string})?.error||'Task could not finish.')
     setNotice(msg);if(action==='sendMessage'){setBusy(false);setWorkPhase('');setStreamingText('');setRetryText(lastSent.current);setMessages(m=>[...m,makeMsg('event',msg)])}
     if(action==='testModel')setModelChecking(false)
     if(action==='generateImage')setImageBusy(false)
     if(action==='checkUpdates'||action==='installUpdate'){setUpdateBusy(false);setUpdateProgress(null)}
     if(action==='installBrain'||action==='startBrain')setBrainProgress(null)
     return
   }
   const result=event.data as Record<string,unknown>
   if(action==='sendMessage'){
     setBusy(false);setWorkPhase('');setStreamingText('');setRetryText('');setNotice('');setMessages(m=>[...m,makeMsg('assistant',String(result?.answer||''))]);void sync()
   }else if(action==='installBrain'||action==='startBrain'){
     setBrainProgress(null);setNotice('STAR Brain is ready to use.');void sync()
   }else if(action==='testModel'){
     setModelChecking(false);setModelCheck(result as {ok:boolean;model:string;sample:string});setNotice('STAR Brain responded successfully to a real prompt.')
   }else if(action==='checkUpdates'){
     setUpdateBusy(false)
     setUpdate(result as unknown as UpdateInfo)
     if(result.requires_browser)setNotice(String(result.explanation||'Download this version from GitHub Releases.'))
     else setNotice(result.available?`STAR v${result.version} is ready to install.`:'STAR is up to date.')
   }else if(action==='installUpdate'){
     setUpdateBusy(false);setUpdateProgress(null)
     setNotice('Verified setup launched. STAR will restart after installation.')
   }
   else if(action==='generateImage'){
     setImageBusy(false)
     const pictures:Array<{filename:string;preview:string}>=Array.isArray(result.images)?result.images.filter((x:unknown)=>x&&typeof x==='object').map((x:unknown)=>{const image=x as {filename?:string;preview?:string};return {filename:String(image.filename||'Generated image'),preview:String(image.preview||'')}}):[]
     setGeneratedImages(pictures)
     setNotice(pictures.length?`${pictures.length} image${pictures.length===1?'':'s'} saved to your local STAR generated folder.`:'Image Lab finished without a generated image.')
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
   followBottom.current=true;setShowJump(false)
   setRetryText('');setStreamingText('');setChatSearch('');setShowChatSearch(false)
   setMessages(m=>[...m,makeMsg('user',value,selected.map(f=>f.split(/[\\/]/).pop()||f))]);setFiles([]);setPrompt('');setBusy(true);setWorkPhase('Preparing your response…');setNotice('');setTab('chat')
   const res=await act('sendMessage',{prompt:value,files:selected})
   if(!res){setBusy(false);setWorkPhase('');setRetryText(value);setMessages(m=>[...m,makeMsg('event','Could not connect to STAR Brain. Open STAR Brain and test the actual model response.')])}
 },[prompt,busy,files,inactive,act])

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
 const applyBoot=(b:BootData)=>{setData(b);setDraft(b.settings);setMessages(b.messages);followBottom.current=true;setShowJump(false);setTab('chat');setLeftOpen(false)}
 const changeProject=async(name:string)=>{if(busy)return;const v=await act('switchProject',{project:name});if(v){applyBoot(v as BootData);lastProject.current=name}setLeftOpen(false)}
 const startNewChat=async()=>{if(busy)return;const v=await act('newChat');if(v){applyBoot(v as BootData);setPrompt('');setFiles([]);composerRef.current?.focus()}}
 const openChat=async(id:string)=>{if(busy||id===data.active_chat){setTab('chat');return}const v=await act('switchChat',{chatId:id});if(v)applyBoot(v as BootData)}
 const chooseWorkflow=async()=>{const v=await act('pickFiles',{kind:'workflow'});if(Array.isArray(v)&&v[0]){setWorkflowPath(String(v[0]));setGeneratedImages([])}}
 const createImage=async()=>{
   if(imageBusy||!workflowPath||!imagePrompt.trim()||!imageNode.trim())return
   setImageBusy(true);setGeneratedImages([]);setNotice('')
   const result=await act('generateImage',{workflow:workflowPath,prompt:imagePrompt,node:imageNode,port:Number(imagePort)})
   if(!result)setImageBusy(false)
 }
 const saveSettings=async()=>{const v=await act('saveSettings',{settings:draft});if(v){setNotice('Settings saved.');setModelCheck(null);void sync()}}
 const testActualModel=async()=>{
   if(modelChecking)return
   setModelChecking(true);setModelCheck(null)
   const response=await act('testModel')
   if(!response)setModelChecking(false)
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
 const chatTitle=data.chats.find(c=>c.id===data.active_chat)?.title||'New chat'
 return <MotionConfig reducedMotion={themeMotion?'user':'always'}><div className={wrapper} data-preview={preview}>
   <aside className="sidebar" aria-label="STAR navigation">
      <div className="brand-area"><Brand/><button className="sidebar-collapse icon-button" aria-label="Close menu" onClick={()=>setLeftOpen(false)}><X size={18}/></button></div>
      <div className="sidebar-content-scroll">
        <div className="workspace-selector"><button type="button" onClick={()=>nav('projects')} title="Change workspace"><span className="workspace-tile"><Folder size={18}/></span><span className="workspace-label"><strong>{data.project}</strong><small>Current workspace</small></span><ChevronDown size={16}/></button></div>
        <div className="sidebar-new"><button className="new-chat-button" type="button" onClick={()=>void startNewChat()} disabled={busy||inactive} title="Start a fresh conversation"><SquarePen size={18}/><span>New chat</span><Plus size={16}/></button></div>
        <div className="nav-block"><span className="nav-label">WORKSPACE</span>{sections.slice(0,4).map(([id,name,Icon])=><button type="button" key={id} className={'nav-item '+(tab===id?'active':'')} onClick={()=>nav(id)} aria-current={tab===id?'page':undefined}><Icon size={18} strokeWidth={1.8}/><span>{name}</span>{tab===id?<motion.span className="nav-marker" layoutId="active-nav" transition={{type:'spring',stiffness:440,damping:37}}/>:null}</button>)}</div>
        <div className="sidebar-history"><div className="history-heading"><span>RECENT CHATS</span><span>{data.chats.length}</span></div><div className="history-list">{data.chats.slice(0,8).map(chat=><button type="button" key={chat.id} title={chat.title} className={'history-item '+(data.active_chat===chat.id&&tab==='chat'?'selected':'')} onClick={()=>void openChat(chat.id)} disabled={busy}><MessageCircleMore size={14}/><span>{chat.title}</span></button>)}{!data.chats.length&&<span className="history-empty">Conversations will appear here.</span>}</div></div>
        <div className="nav-block nav-dev"><span className="nav-label">YOUR TOOLKIT</span>{sections.slice(4).map(([id,name,Icon])=><button type="button" key={id} className={'nav-item '+(tab===id?'active':'')} onClick={()=>nav(id)} aria-current={tab===id?'page':undefined}><Icon size={18} strokeWidth={1.8}/><span>{name}</span>{tab===id?<motion.span className="nav-marker" layoutId="active-nav" transition={{type:'spring',stiffness:440,damping:37}}/>:null}</button>)}</div>
      </div>
      <div className="sidebar-footer"><button type="button" className="sidebar-engine" onClick={()=>nav('brain')}><span className={'status-dot '+(data.brain_running?'ok':'')}/><span>{data.brain_running?'Local intelligence ready':'Start your local AI'}</span><ChevronRight size={14}/></button><div className="sidebar-version"><span>STAR INTELLIGENCE</span><span>GENESIS · v{data.version}</span></div></div>
    </aside>
   <div className="shell-main">
     <header className="topbar">
        <div className="topbar-left"><button className="hamburger icon-button" aria-label="Open navigation" onClick={()=>setLeftOpen(true)}><MoreHorizontal size={20}/></button><span className="crumb-muted">STAR</span><ChevronRight size={13}/><strong>{sections.find(x=>x[0]===tab)?.[1]}</strong></div>
        <div className="topbar-right"><button type="button" className="topbar-command" onClick={()=>{nav('chat');composerRef.current?.focus()}} title="Focus STAR chat (Ctrl+K)"><Search size={15}/><span>Ask STAR</span><kbd>Ctrl K</kbd></button><span className="topbar-private"><ShieldCheck size={15}/> Private on your PC</span><button className="topbar-system" type="button" onClick={()=>nav('brain')} title="View local model status"><span className={'status-dot '+(data.brain_running?'ok':'')}/>{data.brain_running?'Model online':'Model offline'}</button><button className="avatar-button" onClick={()=>nav('settings')} title="Open settings" aria-label="Open settings"><Settings2 size={17}/></button></div>
      </header>
     {preview&&<div className="demo-ribbon"><Info size={14}/> Interactive interface preview — real AI features are available only in STAR Desktop.</div>}
     <AnimatePresence mode="wait" initial={false}>
       <motion.main key={tab} className="page-stage" initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-5}} transition={{duration:.16}}>
         {tab==='chat'&&<div className="chat-page">
            <div className="chat-topline">
              <div className="chat-top-context"><span className="eyebrow">{data.project} / CONVERSATION</span><strong>{chatTitle}</strong><small>{data.brain_running?'Your local assistant is ready.':'Your conversation is saved locally.'}</small></div>
              <div className="chat-top-actions">
                {showChatSearch&&<input type="search" aria-label="Search this conversation" className="chat-find-input" autoFocus placeholder="Search this chat…" value={chatSearch} onChange={e=>setChatSearch(e.target.value)}/>}
                <button className={'chat-tool-button'+(showChatSearch?' is-active':'')} type="button" title="Find in this chat" aria-label="Find in this chat" onClick={()=>{setShowChatSearch(v=>!v);setChatSearch('')}}><Search size={17}/></button>
                <button className="chat-tool-button chat-copy-control" type="button" title="Copy conversation" aria-label="Copy conversation" disabled={!messages.length} onClick={()=>void copyConversation()}><Copy size={16}/></button>
                <button className="chat-new-action" type="button" onClick={()=>void startNewChat()} disabled={busy||inactive}><Plus size={17}/><span>New chat</span></button>
              </div>
            </div>
            <div className="chat-scroll" ref={chatScroll} onScroll={onChatScroll}>
              <div className="chat-inner">
                {!messages.length?
                  <div className="welcome">
                    <div className="welcome-emblem"><span className="welcome-emblem-back"/><Star size={33} fill="currentColor" strokeWidth={1.2}/></div>
                    <div className="welcome-eyebrow"><span className="welcome-status"/>{data.brain_running?'STAR BRAIN READY':'YOUR CREATIVE WORKSPACE'}</div>
                    <h1>Every great idea <span>starts somewhere.</span></h1>
                    <p>Your own intelligence workspace for better ideas, deeper research, code, game development and everything in between.</p>
                    <div className="welcome-prompt">What are we making today?</div>
                    <div className="suggestions">{examples.map((ex,index)=><button key={ex.title} type="button" onClick={()=>void send(ex.prompt)} disabled={busy}><span className="suggestion-icon">{index===0?<Sparkles size={18}/>:index===1?<Workflow size={18}/>:<Terminal size={18}/>}</span><strong>{ex.title}</strong><small>{ex.description}</small><ArrowRight className="suggest-arrow" size={17}/></button>)}</div>
                    <span className="welcome-caption"><ShieldCheck size={13}/> Local-first by default. Your projects stay yours.</span>
                  </div>:
                  <div className="conversation" role="log" aria-label="Conversation messages">
                    {matchingMessages.map(m=><Message key={m.id} entry={m}/>)}
                    {showChatSearch&&chatSearch.trim()&&!matchingMessages.length&&<div className="chat-no-results"><Search size={20}/><strong>No matching messages</strong><small>Try another phrase.</small></div>}
                    {busy&&streamingText&&<Message animated={false} key="stream-live" entry={{id:'stream-live',role:'assistant',text:streamingText}} partial/>}
                    {busy&&<div className={'thinking '+(streamingText?'thinking-compact':'')} role="status" aria-live="off"><span className="pulse-bar"><i/><i/><i/></span><div><strong>{streamingText?'STAR is responding':'STAR is thinking'}</strong><small>{workPhase||'Preparing a thoughtful response…'}</small></div></div>}
                    {!busy&&retryText&&<div className="chat-recovery"><span>The last response could not finish. Your prompt has been saved.</span><button type="button" onClick={()=>void send(retryText)}><RefreshCcw size={14}/> Retry message</button></div>}
                  </div>}
              </div>
            </div>
            {showJump&&messages.length>0&&<button className="chat-jump" type="button" onClick={jumpToLatest}><ChevronDown size={17}/> Jump to latest</button>}
            <div className="composer-zone">
              <div className="composer">
                {!!files.length&&<div className="file-chips">{files.map((f,i)=><span key={f}><File size={14}/>{truncate(f.split(/[\\/]/).pop()||f,40)}<button type="button" title="Remove attachment" aria-label="Remove attachment" onClick={()=>setFiles(x=>x.filter((_,j)=>i!==j))}><X size={13}/></button></span>)}</div>}
                <label className="sr-only" htmlFor="star-prompt">Message STAR</label>
                <textarea ref={composerRef} id="star-prompt" rows={1} placeholder="Message STAR…" value={prompt} onChange={e=>setPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void send()}}}/>
                <div className="composer-tools">
                  <div className="composer-left">
                    <button className="composer-action attach-button" type="button" onClick={()=>void attach()} title="Attach images, audio or video"><Plus size={17}/><span>Attach</span></button>
                    <button className="composer-action composer-mic" type="button" title="Transcribe an audio file" aria-label="Transcribe audio" onClick={async()=>{const r=await act('pickFiles',{kind:'audio'});if(Array.isArray(r)&&r[0])void act('transcribe',{file:r[0]})}}><Mic size={17}/></button>
                    <button className="composer-model" type="button" onClick={()=>nav('brain')} title="View or change your installed model"><span className={'status-dot '+(data.brain_running?'ok':'')}/><span>{truncate(data.settings.model||'Select local model',25)}</span><ChevronDown size={13}/></button>
                  </div>
                  <div className="composer-right"><span className="composer-enter">Enter <ArrowRight size={12}/></span><button className="send-button" type="button" aria-label={busy?'STAR is responding':'Send message'} disabled={!prompt.trim()||busy} onClick={()=>void send()}>{busy?<LoaderCircle className="spin" size={19}/>:<ArrowUp size={20}/>}</button></div>
                </div>
              </div>
              <div className="composer-hint"><span>STAR can make mistakes. Review important results.</span><span>Shift + Enter for a new line</span></div>
            </div>
          </div>}
          {tab==='analytics'&&<AnalyticsView data={data.analytics}/>}
         {tab==='projects'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="PROJECT MANAGEMENT" title="Your workspaces" description="Separate contexts, conversations, and design decisions for every project."/><div className="project-create"><input aria-label="New project name" value={newProject} onChange={e=>setNewProject(e.target.value)} placeholder="New project name" maxLength={60} onKeyDown={e=>{if(e.key==='Enter'&&newProject.trim()){void changeProject(newProject.trim());setNewProject('')}}}/><button className="primary-button" onClick={()=>{if(newProject.trim()){void changeProject(newProject.trim());setNewProject('')}}}><Plus size={17}/> New workspace</button></div><div className="project-grid">{[...new Set([data.project,...data.projects])].map(name=><button className={'project-card '+(name===data.project?'project-current':'')} key={name} onClick={()=>changeProject(name)}><FolderOpen size={25}/><strong>{name}</strong><span>{name===data.project?'Current workspace':'Open workspace'}</span><ArrowRight size={18}/></button>)}</div></div></div>}
         {tab==='brain'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="YOUR AI, ON YOUR PC" title="STAR Brain" description="One click to your private local intelligence. No separate chat application. No paid model API key."/><Panel className="brain-hero"><div className="brain-art"><div className="brain-core"><Star size={38} fill="currentColor"/></div><span className="brain-orbit orbit-one"/><span className="brain-orbit orbit-two"/></div><div><Tag kind={data.brain_running?'green':'gold'}>{data.brain_running?'Ready to create':'LOCAL INTELLIGENCE'}</Tag><h2>{data.brain_installed?'Your brain is installed.':'A real AI, running on your machine.'}</h2><p>Download a small vision-capable model with a verified engine. STAR manages the model and stores it locally.</p><button className="primary-button" disabled={brainProgress!==null} onClick={()=>void act(data.brain_installed?'startBrain':'installBrain')}><Download size={17}/>{data.brain_installed?'Start STAR Brain':'Download & launch STAR Brain'}<ArrowRight size={17}/></button></div></Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">INSTALLATION STATUS</span><h2>Local engine</h2></div><Tag kind={data.brain_running?'green':'neutral'}>{data.brain_running?'Running':data.brain_installed?'Installed':'Not installed'}</Tag></div><p>{brainProgress?.phase||'Model downloads are saved on your PC and checked against published SHA-256 hashes.'}</p>{brainProgress&&<div className="progress-track"><motion.div animate={{width:brainProgress.total?`${Math.max(2,brainProgress.downloaded/brainProgress.total*100)}%`:'9%'}} transition={{duration:.25}}/></div>}<div className="brain-info"><span><HardDrive size={17}/> Several GB free space required</span><span><ShieldCheck size={17}/> Verified downloads</span><span><Monitor size={17}/> Tuned for smaller local models</span></div></Panel>
           <Panel className="settings-section"><div className="section-heading"><div><span className="eyebrow">MODEL CONNECTION</span><h2>Installed model</h2></div><BrainCircuit size={20}/></div><p>{data.settings.model||'No model selected. Download STAR Brain to start.'}</p><small>{data.settings.endpoint}</small></Panel><Panel className="settings-section health-check-panel"><div className="section-heading"><div><span className="eyebrow">LIVE AI HEALTH CHECK</span><h2>Test a real response</h2></div><BrainCircuit size={20}/></div><p>Checking the model list does not prove that the AI can answer. Send a short, private test prompt to your selected local model and verify the chat template works.</p>
            <button type="button" className="secondary-button" disabled={modelChecking||inactive||!data.settings.model} onClick={()=>void testActualModel()}>{modelChecking?<LoaderCircle className="spin" size={16}/>:<Zap size={16}/>} {modelChecking?'Testing the model…':'Test actual AI response'}</button>
            {modelCheck&&<div className="health-result" role="status"><Check size={17}/><div><strong>Model answered successfully</strong><span>{modelCheck.sample}</span><small>{modelCheck.model}</small></div></div>}
            <small>Health checks run only on your configured localhost endpoint. No paid API or remote STAR server is required.</small>
           </Panel></div></div>}
         {tab==='tools'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="DEVELOPER WORKSPACE" title="Connect your tools" description="Give STAR only the project access it needs, then inspect and build with evidence."/><div className="two-up"><Panel className="settings-section"><div className="tool-icon"><Workflow size={22}/></div><h2>Roblox Studio</h2><p>Connect to the official Roblox Studio MCP server. Start in an unpublished test place.</p><button className="secondary-button" onClick={()=>void act('discoverStudio')}><RefreshCcw size={15}/> Discover Studio instances</button>{studio&&<pre className="tool-output">{truncate(studio,2400)}</pre>}</Panel><Panel className="settings-section"><div className="tool-icon"><Folder size={22}/></div><h2>Local workspace</h2><p>STAR can inspect a selected folder, and edit files only when you enable workspace write permissions.</p><Tag>{data.settings.workspace||'Not connected'}</Tag><button className="secondary-button" onClick={()=>nav('settings')}>Configure folder <ArrowRight size={14}/></button></Panel></div><Panel className="settings-section"><h2><Shield size={18}/> Scoped access</h2><p>GitHub updates and model downloads never require your AI to see your private credentials. Publishing and unrestricted PC control are not enabled by default.</p><div className="toggle-line"><span>Studio edits</span><Tag kind={data.settings.studio_edit?'gold':'neutral'}>{data.settings.studio_edit?'Enabled':'Read only'}</Tag></div><div className="toggle-line"><span>Workspace writes</span><Tag kind={data.settings.workspace_edit?'gold':'neutral'}>{data.settings.workspace_edit?'Enabled':'Read only'}</Tag></div></Panel></div></div>}
         {tab==='image'&&<div className="scroll-region"><div className="page-wrap image-page">
            <PageTitle eyebrow="CREATIVE STUDIO / LOCAL GENERATION" title="Image Lab" description="Generate artwork right inside STAR using your existing local ComfyUI workflow. No separate STAR window."/>
            <div className="image-layout">
              <Panel className="image-lab-form">
                <div className="image-panel-header"><div className="image-panel-icon"><ImagePlus size={25}/></div><div><span className="eyebrow">YOUR CREATIVE ENGINE</span><h2>Create an image</h2><p>Powered by a locally running ComfyUI instance and an approved API-format workflow.</p></div></div>
                <div className="image-workflow"><span className="field-name">API workflow</span><button type="button" className="workflow-picker" onClick={()=>void chooseWorkflow()} disabled={imageBusy}><FolderOpen size={18}/><span>{workflowPath?truncate(workflowPath.split(/[\\/]/).pop()||workflowPath,55):'Choose ComfyUI workflow (.json)'}</span><ChevronRight size={16}/></button><small>Only workflows using STAR's reviewed core-node allowlist are accepted.</small></div>
                <label className="image-field"><span className="field-name">Your prompt</span><textarea rows={5} maxLength={1500} value={imagePrompt} onChange={e=>setImagePrompt(e.target.value)} placeholder="Describe the image you want to create. Include subject, lighting, composition and materials…"/></label>
                <div className="image-settings-row"><label className="image-field"><span className="field-name">CLIPTextEncode node ID</span><input type="text" inputMode="numeric" placeholder="e.g. 6" value={imageNode} onChange={e=>setImageNode(e.target.value)}/></label><label className="image-field"><span className="field-name">Local ComfyUI port</span><input type="number" min="1" max="65535" value={imagePort} onChange={e=>setImagePort(e.target.value)}/></label></div>
                <button type="button" className="primary-button image-generate" disabled={imageBusy||inactive||!workflowPath||!imagePrompt.trim()||!imageNode.trim()} onClick={()=>void createImage()}>{imageBusy?<LoaderCircle className="spin" size={18}/>:<Sparkles size={18}/>} {imageBusy?'Generating locally…':'Generate image'}<ArrowRight size={17}/></button>
                <p className="image-safety"><ShieldCheck size={14}/> Your prompt and outputs remain on your PC. No hosted image API is used.</p>
              </Panel>
              <Panel className="image-output-panel">
                <div className="image-output-heading"><span>OUTPUT / LOCAL FILES</span><button className="icon-button" type="button" title="Open the STAR data folder" onClick={()=>void act('openDataFolder')}><FolderOpen size={19}/></button></div>
                {generatedImages.length?<div className="image-files"><div className="image-finished"><Check size={18}/><div><strong>Generation complete</strong><span>{generatedImages.length} image file{generatedImages.length>1?'s':''} saved under STAR / generated</span></div></div><div className="image-results-grid">{generatedImages.map(result=><div className="image-result-card" key={result.filename}>{result.preview?<img src={result.preview} alt={'STAR generated artwork: '+result.filename} loading="lazy"/>:<div className="image-thumbnail-fallback"><ImagePlus size={25}/></div>}<span><File size={14}/>{result.filename}</span></div>)}</div><button type="button" className="secondary-button" onClick={()=>void act('openDataFolder')}><FolderOpen size={16}/> Open STAR files</button></div>:
                 <div className="image-output-empty"><div className="output-emblem"><ImagePlus size={31}/></div><strong>{imageBusy?'Your image is being generated':'Your next creation goes here'}</strong><p>{imageBusy?'STAR is waiting for ComfyUI to finish. This can take a few minutes.':'Choose a workflow, write a prompt and create. Your finished images will be stored locally.'}</p>{imageBusy&&<span className="image-wait"><LoaderCircle size={15} className="spin"/> Local generation in progress</span>}</div>}
              </Panel>
            </div>
          </div></div>}
          {tab==='library'&&<div className="scroll-region"><div className="page-wrap"><PageTitle eyebrow="PROJECT RESOURCES" title="Your library" description="Project references, verified decisions, conversation history, and generated files."/><div className="two-up"><Panel className="settings-section"><FolderOpen size={23} className="gold"/><h2>STAR data folder</h2><p>Local storage for saved conversations, checkpoints, images, and project knowledge.</p><button className="secondary-button" onClick={()=>void act('openDataFolder')}>Open local STAR files <ArrowRight size={15}/></button></Panel><Panel className="settings-section"><BookOpen size={23} className="gold"/><h2>Verified knowledge</h2><p>STAR only promotes reviewed, source-grounded knowledge into trusted project memory.</p><button className="secondary-button" onClick={()=>nav('projects')}>View projects <ArrowRight size={15}/></button></Panel></div><Panel className="settings-section"><h2>Image and media workflows</h2><p>Attach image, audio and video references in chat. Generate artwork in STAR's built-in Image Lab with a locally configured ComfyUI workflow.</p><button className="secondary-button" onClick={()=>nav('image')}><ImagePlus size={16}/> Open Image Lab <ArrowRight size={15}/></button><small>The Image Lab now runs inside the same STAR desktop window.</small></Panel></div></div>}
         {tab==='settings'&&<div className="scroll-region"><div className="page-wrap settings-page"><PageTitle eyebrow="PERSONALIZE YOUR WORKSPACE" title="Settings" description="Keep daily work simple; advanced integrations stay here when you need them."/><Panel className="settings-section"><div className="section-heading"><div><h2>Local model</h2><p>STAR Brain configures these automatically after installation.</p></div><BrainCircuit size={20}/></div><div className="field-grid"><label>Model ID<input value={draft.model} onChange={e=>setDraft(d=>({...d,model:e.target.value}))} placeholder="Installed model"/></label><label>Local endpoint<input value={draft.endpoint} onChange={e=>setDraft(d=>({...d,endpoint:e.target.value}))}/></label></div><button className="secondary-button" onClick={()=>void act('listModels')}>List available models <RefreshCcw size={14}/></button><button className="secondary-button" type="button" disabled={modelChecking||!draft.model} onClick={()=>void testActualModel()}>{modelChecking?<LoaderCircle className="spin" size={14}/>:<Zap size={14}/>} Test actual response</button>{modelCheck&&<div className="health-result"><Check size={16}/> <span>Live response: {modelCheck.sample}</span></div>}{modelList.length>0&&<small>Available: {modelList.join(', ')}</small>}</Panel>
           <Panel className="settings-section"><h2>Developer permissions</h2><div className="field-grid"><label>Workspace folder<input value={draft.workspace} onChange={e=>setDraft(d=>({...d,workspace:e.target.value}))} placeholder="Choose a project folder"/></label><label>Roblox Studio instance ID<input value={draft.studio_id} onChange={e=>setDraft(d=>({...d,studio_id:e.target.value}))}/></label></div><label className="setting-switch"><span><strong>Allow workspace writes</strong><small>Only inside your selected workspace</small></span><input type="checkbox" checked={draft.workspace_edit} onChange={e=>setDraft(d=>({...d,workspace_edit:e.target.checked}))}/></label><label className="setting-switch"><span><strong>Allow Studio edits</strong><small>Use an unpublished disposable test place first</small></span><input type="checkbox" checked={draft.studio_edit} onChange={e=>setDraft(d=>({...d,studio_edit:e.target.checked}))}/></label></Panel>
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
