import {useEffect,useRef,useState} from 'react'
import {Check,ExternalLink,FolderOpen,RefreshCw,Unplug,Zap} from 'lucide-react'
import {onBackendEvent,request} from './bridge'
import './clip-interop.css'

type ClipMeta={id:string;name:string;relative:string;bytes:number;modified:string}
type FolderData={selected:boolean;folder?:string;clips:ClipMeta[];truncated?:boolean;message?:string;cancelled?:boolean}
type MomentsData={available?:boolean;registered?:string[];accepted?:boolean;message?:string}
type InteropAction='clipChooseFolder'|'clipListFolder'|'clipClearFolder'|'clipOpenFile'
 |'clipMomentsStatus'|'clipMomentsRegister'|'clipMomentsTrigger'

const emptyFolder:FolderData={selected:false,clips:[]}
const momentAction=(name:InteropAction)=>name.startsWith('clipMoments')
const formatSize=(bytes:number)=>bytes<1024*1024?Math.max(1,Math.ceil(bytes/1024))+' KB':(bytes/1024/1024).toFixed(1)+' MB'

/** Two opt-in integrations: local clip files, and developer-owned Moments events. */
export function ClipInteropPanel({disabled=false}:{disabled?:boolean}){
 const [folder,setFolder]=useState<FolderData>(emptyFolder)
 const [moments,setMoments]=useState<MomentsData>({})
 const [game,setGame]=useState('STAR_MY_GAME')
 const [ownsGame,setOwnsGame]=useState(false)
 const [error,setError]=useState('')
 const [message,setMessage]=useState('')
 const [busy,setBusy]=useState(false)
 const waiting=useRef<{id:string;action:InteropAction}|null>(null)

 useEffect(()=>onBackendEvent(event=>{
   const requested=waiting.current
   if(!requested||event.requestId!==requested.id||!['result','error'].includes(event.kind))return
   waiting.current=null
   setBusy(false)
   if(event.kind==='error'){
     setError(typeof event.data==='string'?event.data:'The integration could not complete this action.')
     return
   }
   const report=event.data as FolderData & MomentsData & {opened?:boolean}
   if(report&&typeof report==='object'){
     if(momentAction(requested.action)){
       setMoments(old=>({...old,...report}))
     }else if(typeof report.selected==='boolean'&&Array.isArray(report.clips)){
       setFolder(report)
     }
     setError('')
     setMessage(report.message||(report.opened?'Opened the selected video using Windows.':'Action complete.'))
   }else setError('STAR returned unexpected integration data.')
 }),[])

 async function run(action:InteropAction,body:Record<string,unknown>={}){
   if(disabled||busy)return
   setBusy(true);setError('');setMessage('')
   const id=crypto.randomUUID()
   waiting.current={id,action}
   const result=await request<FolderData & MomentsData & {opened?:boolean}>(
     action,body,id
   )
   if(!result.ok){
     waiting.current=null;setBusy(false)
     setError(result.error||'STAR could not reach the local integration.')
     return
   }
   if(result.pending)return
   waiting.current=null;setBusy(false)
   if(result.data?.cancelled){setMessage('Folder selection cancelled.');return}
   if(result.data&&typeof result.data.selected==='boolean'&&Array.isArray(result.data.clips))setFolder(result.data)
   if(result.data&&momentAction(action))setMoments(old=>({...old,...result.data}))
   setMessage(result.data?.message||'Action completed.')
 }

 const hasGame=/^STAR_[A-Z][A-Z0-9_]{1,31}$/.test(game)

 return <section className="star-interop" aria-label="STAR clip interoperability">
   <div className="star-interop__head">
     <h3>Recorder integrations</h3>
     <p>Connect your existing workflow instead of replacing it. These integrations do not upload clips.</p>
   </div>
   <div className="star-interop__grid">
     <section className="star-interop__module" aria-label="External clip files">
       <div className="star-interop__module-title"><FolderOpen size={16} aria-hidden="true"/><strong>Existing clips</strong></div>
       <p>Browse recordings from Medal, Outplayed, OBS, ShadowPlay, RePlays and other apps. Choose their local video folder; STAR only reads filenames and sizes.</p>
       <div className="star-interop__controls">
         <button type="button" className="secondary-button" disabled={disabled||busy} onClick={()=>void run('clipChooseFolder')}>
           <FolderOpen size={14} aria-hidden="true"/> Choose folder
         </button>
         <button type="button" className="secondary-button" disabled={disabled||busy||!folder.selected} onClick={()=>void run('clipListFolder')}>
           <RefreshCw size={14} aria-hidden="true"/> Refresh
         </button>
         {folder.selected&&<button type="button" className="secondary-button" disabled={disabled||busy} onClick={()=>void run('clipClearFolder',{confirm:true})}>
           <Unplug size={14} aria-hidden="true"/> Disconnect
         </button>}
       </div>
       {folder.selected
         ?<div className="star-interop__files">
           <div className="star-interop__list-heading"><strong>{folder.folder||'Chosen folder'}</strong><span>{folder.clips.length} indexed</span></div>
           {folder.clips.length===0?<p>No supported videos found within this folder and two subfolder levels.</p>:
           <ul className="star-interop__list">
             {folder.clips.slice(0,8).map(clip=><li key={clip.id}>
               <span className="star-interop__file"><strong title={clip.relative}>{clip.name}</strong><small>{formatSize(clip.bytes)}</small></span>
               <button type="button" aria-label={'Open '+clip.name} title="Open in your default video player"
                 disabled={disabled||busy} onClick={()=>void run('clipOpenFile',{id:clip.id,confirm:true})}>
                 <ExternalLink size={15} aria-hidden="true"/>
               </button>
             </li>)}
           </ul>}
           {folder.clips.length>8&&<small>Showing 8 recent clips. Narrow the chosen folder to see others.</small>}
           {folder.truncated&&<small>Large collection: only a bounded sample was indexed.</small>}
         </div>
         :<p className="star-interop__empty">No clip folder selected</p>}
     </section>
     <section className="star-interop__module" aria-label="SteelSeries Moments developer event">
       <div className="star-interop__module-title"><Zap size={16} aria-hidden="true"/><strong>SteelSeries Moments</strong></div>
       <p>For games you develop: register and trigger a documented local GameSense highlight event. Not a universal capture API for other developers' games.</p>
       <button type="button" className="secondary-button" disabled={disabled||busy} onClick={()=>void run('clipMomentsStatus')}>
         <RefreshCw size={14} aria-hidden="true"/> Check GameSense
       </button>
       {typeof moments.available==='boolean'&&<p className="star-interop__availability">{moments.message}</p>}
       <label className="star-interop__field">Development game ID
         <input type="text" value={game} maxLength={37} spellCheck={false} disabled={disabled||busy}
           onChange={event=>setGame(event.target.value.toUpperCase())} placeholder="STAR_MY_GAME"/>
       </label>
       <label className="star-interop__confirm">
         <input type="checkbox" checked={ownsGame} disabled={disabled||busy} onChange={event=>setOwnsGame(event.target.checked)}/>
         I develop this game and authorize its test highlight event.
       </label>
       <div className="star-interop__controls">
         <button type="button" className="secondary-button" disabled={disabled||busy||!ownsGame||!hasGame}
           onClick={()=>void run('clipMomentsRegister',{game,ownsGame:true,confirm:true})}>
           <Check size={14} aria-hidden="true"/> Register event
         </button>
         <button type="button" className="secondary-button"
           disabled={disabled||busy||!ownsGame||!hasGame||!(moments.registered||[]).includes(game)}
           onClick={()=>void run('clipMomentsTrigger',{game,ownsGame:true,confirm:true})}>
           <Zap size={14} aria-hidden="true"/> Send test event
         </button>
       </div>
       <p className="star-interop__caution">An accepted event is not proof that Moments recorded a video. You must also enable the rule and recording in SteelSeries GG.</p>
     </section>
   </div>
   {message&&<p role="status" className="star-interop__message">{message}</p>}
   {error&&<p role="alert" className="star-interop__error">{error}</p>}
 </section>
}
