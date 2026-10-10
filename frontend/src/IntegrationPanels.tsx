import {useEffect,useRef,useState} from 'react'
import {BookOpen,Check,ChevronDown,Globe,KeyRound,LoaderCircle,RefreshCcw,ShieldCheck,Workflow,X} from 'lucide-react'
import {onBackendEvent} from './bridge'
import type {AppSettings,McpStatus} from './types'
import './integrated-tools.css'

type Invoke=(action:string,params?:Record<string,unknown>)=>Promise<unknown|null>
const providers=['local','groq','openrouter','gemini','cerebras'] as const
type Provider=typeof providers[number]

export function ProviderPanel({draft,onChange,credentials,invoke,refresh,disabled=false}:{draft:AppSettings;onChange:(settings:AppSettings)=>void;credentials:Record<string,boolean>;invoke:Invoke;refresh:()=>void;disabled?:boolean}){
 const [selected,setSelected]=useState<Provider>('groq')
 const [apiKey,setApiKey]=useState('')
 const [pending,setPending]=useState(false)
 const [message,setMessage]=useState('')
 const save=async()=>{
   if(disabled||pending||!apiKey.trim())return
   setPending(true);setMessage('')
   try{
     const r=await invoke('saveProviderKey',{provider:selected,key:apiKey})
     if(r){setApiKey('');setMessage('Credential saved in your operating system keyring.');refresh()}
   }finally{setApiKey('');setPending(false)}
 }
 const clear=async()=>{
   if(disabled||pending)return
   setPending(true)
   try{const r=await invoke('clearProviderKey',{provider:selected});if(r){setMessage('Stored credential cleared.');refresh()}}
   finally{setPending(false)}
 }
 return <section className="integrated-panel" aria-label="AI provider settings">
   <div className="integrated-heading"><KeyRound size={18}/><div><strong>Model & provider</strong><span>Local by default. Cloud providers are optional and require your own key.</span></div></div>
   <label className="integrated-field">Inference provider
     <select value={draft.provider||'local'} disabled={disabled} onChange={e=>onChange({...draft,provider:e.target.value as Provider})}>
       {providers.map(x=><option value={x} key={x}>{x==='local'?'Local STAR Brain':x==='openrouter'?'OpenRouter':x==='groq'?'GroqCloud':x==='gemini'?'Gemini':'Cerebras'}</option>)}
     </select>
   </label>
   <p className="integrated-help">After changing provider, save Settings. STAR sends your prompt only to the provider you explicitly selected; ordinary local chat never silently falls back to a cloud model.</p>
   <div className="integrated-key-controls">
     <label className="integrated-field">Cloud key provider
       <select value={selected} disabled={disabled||pending} onChange={e=>setSelected(e.target.value as Provider)}>
         {providers.filter(x=>x!=='local').map(x=><option key={x} value={x}>{x==='groq'?'GroqCloud':x==='openrouter'?'OpenRouter':x==='gemini'?'Gemini':'Cerebras'}{credentials?.[x]?' — connected':''}</option>)}
       </select>
     </label>
     <label className="integrated-field">API key (never saved in STAR settings)
       <input type="password" autoComplete="off" disabled={disabled||pending} value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="Paste a provider key"/>
     </label>
   </div>
   <div className="integrated-actions">
     <button type="button" className="secondary-button" disabled={disabled||pending||!apiKey.trim()} onClick={()=>void save()}>{pending?<LoaderCircle size={14} className="spin"/>:<Check size={14}/>} Save key</button>
     <button type="button" className="secondary-button" disabled={disabled||pending||!credentials?.[selected]} onClick={()=>void clear()}><X size={14}/> Forget key</button>
     {credentials?.[selected]&&<span className="integrated-connected"><ShieldCheck size={14}/> Key present in OS vault</span>}
   </div>
   {message&&<p role="status" className="integrated-confirm">{message}</p>}
 </section>
}

const targets=[{name:'graphify_docs',flag:'mcp_graphify_docs',label:'Graphify documentation',note:'Fixed remote read-only Graphify documentation tools'},
 {name:'graphify_local',flag:'mcp_graphify_local',label:'Local Graphify MCP',note:'Explicit localhost Graphify MCP; read-only tools'},
 {name:'obsidian_live',flag:'mcp_obsidian_live',label:'Obsidian live MCP',note:'Existing local vault integration remains independently scoped'}] as const
type Flag=typeof targets[number]['flag']

export function McpPanel({draft,onChange,status,invoke,disabled=false}:{draft:AppSettings;onChange:(settings:AppSettings)=>void;status?:McpStatus;invoke:Invoke;disabled?:boolean}){
 const [pending,setPending]=useState('')
 const [results,setResults]=useState<Record<string,string>>({})
 const pendingId=useRef('')
 useEffect(()=>onBackendEvent(event=>{
   if(!pendingId.current||event.requestId!==pendingId.current||event.kind==='progress')return
   setPending('');pendingId.current=''
   if(event.kind==='error'){setResults(prev=>({...prev,error:String(event.data||'Connection test failed').slice(0,240)}));return}
   const value=event.data as {server?:string;read_tool_count?:number;protocol?:string}|null
   if(value?.server){const name=value.server;setResults(prev=>({...prev,[name]:String(value.read_tool_count??0)+' read tools / '+String(value.protocol||'unknown')}))}
 }),[])
 const probe=async(name:string)=>{
   if(pending||disabled)return
   setPending(name)
   const reply=await invoke('testMcpConnection',{server:name}) as {pending?:boolean;requestId?:string}|null
   if(!reply){setPending('');return}
   if(reply.pending&&reply.requestId)pendingId.current=reply.requestId
   else setPending('')
 }
 return <section className="integrated-panel" aria-label="MCP integrations">
   <div className="integrated-heading"><Workflow size={18}/><div><strong>Connected research tools</strong><span>Read-only, explicitly enabled MCP connections. Never arbitrary public servers.</span></div></div>
   <div className="integrated-connectors">
     {targets.map(target=>{
       const active=Boolean(draft[target.flag]);const info=status?.servers?.find(s=>s.name===target.name)
       return <div className="integrated-connector" key={target.name}>
         <div><strong>{target.label}</strong><small>{target.note}</small>
           {results[target.name]&&<small className="integrated-connected">{results[target.name]}</small>}
           {info&&<small>Protocol: {info.protocol} · {info.state}</small>}
         </div>
         <div className="integrated-connector-actions">
           <label className="integrated-switch"><input type="checkbox" disabled={disabled} checked={active} onChange={e=>onChange({...draft,[target.flag]:e.target.checked})}/><span>Enable</span></label>
           <button type="button" className="secondary-button" disabled={disabled||!!pending||!active}
             onClick={()=>void probe(target.name)}>{pending===target.name?<LoaderCircle className="spin" size={14}/>:<RefreshCcw size={14}/>} Test</button>
         </div>
       </div>
     })}
   </div>
   <label className="integrated-field">Local Graphify port
     <input type="number" min={1024} max={65535} disabled={disabled} value={draft.mcp_graphify_port} onChange={e=>onChange({...draft,mcp_graphify_port:Number(e.target.value)})}/>
   </label>
   {results.error&&<p role="alert" className="integrated-error">{results.error}</p>}
   <p className="integrated-help">Save Settings before testing connections. A successful test confirms read-only tool discovery—not that an answer was factually correct.</p>
 </section>
}

export function LearningPanel({project,invoke,disabled=false}:{project:string;invoke:Invoke;disabled?:boolean}){
 const [notes,setNotes]=useState<Array<{id:number;text:string;kind:string;created:string}>>([])
 const [text,setText]=useState('')
 const [replaces,setReplaces]=useState<number|null>(null)
 const [pending,setPending]=useState(false)
 const [notice,setNotice]=useState('')
 const load=async()=>{if(disabled)return;const d=await invoke('listLearning') as {notes?:typeof notes}|null;if(d?.notes)setNotes(d.notes)}
 useEffect(()=>{void load()},[project,disabled,invoke])
 const save=async()=>{
   const entry=text.trim();if(disabled||pending||entry.length<3)return
   setPending(true);setNotice('')
   try{
     const result=await invoke('rememberDecision',{text:entry,kind:'decision',replaces_note_id:replaces,approved:true})
     if(result){setText('');setReplaces(null);setNotice('Your approved decision was saved for this project.');await load()}
   }finally{setPending(false)}
 }
 return <section className="integrated-panel integrated-learning" aria-label="Verified learning">
   <div className="integrated-heading"><BookOpen size={19}/><div><strong>Teach STAR what matters</strong><span>Only decisions you approve become trusted project memory.</span></div></div>
   <p className="integrated-help">STAR learns your verified project requirements and corrections through local memory. It does not secretly retrain its foundation model or rewrite files.</p>
   {replaces!==null&&<div className="integrated-confirm">Correcting note #{replaces}. <button type="button" onClick={()=>{setReplaces(null);setText('')}}>Cancel</button></div>}
   <label className="integrated-field">Approved project decision
     <textarea rows={3} maxLength={1200} disabled={disabled||pending} value={text} onChange={e=>setText(e.target.value)}
       placeholder="Example: Use a clean OLED UI and preserve the approved Roblox avatar proportions."/>
   </label>
   <div className="integrated-actions"><span>{text.length}/1200</span><button className="primary-button" disabled={disabled||pending||text.trim().length<3} onClick={()=>void save()}>{pending?<LoaderCircle className="spin" size={15}/>:<Check size={15}/>} {replaces!==null?'Approve correction':'Approve & remember'}</button></div>
   {notice&&<p className="integrated-confirm" role="status">{notice}</p>}
   {notes.length>0&&<div className="integrated-notes"><strong>Reviewed decisions</strong>{notes.map(n=><div key={n.id} className="integrated-note"><span>{n.text}</span><button type="button" disabled={disabled||pending} onClick={()=>{setReplaces(n.id);setText(n.text)}}>Correct</button></div>)}</div>}
 </section>
}
