import {useEffect,useRef,useState} from 'react'
import {Clapperboard, CircleHelp, HardDriveDownload, Link2, Play, Square, Unplug} from 'lucide-react'
import {onBackendEvent,request} from './bridge'
import {Panel} from './components'
import './clip-panel.css'

type ClipReport={
 connected:boolean
 buffer_active:boolean
 message?:string
 save_requested?:boolean
}
type ClipAction='clipConnect'|'clipStatus'|'clipStartBuffer'|'clipSaveReplay'|'clipStopBuffer'|'clipDisconnect'

/** Uses an external OBS installation; there is no native game hook or upload path. */
export function ClipPanel({disabled=false}:{disabled?:boolean}){
 const [password,setPassword]=useState('')
 const [report,setReport]=useState<ClipReport>({connected:false,buffer_active:false})
 const [busy,setBusy]=useState(false)
 const [feedback,setFeedback]=useState('')
 const [error,setError]=useState('')
 const pending=useRef<string|null>(null)

 useEffect(()=>onBackendEvent(event=>{
   if(event.requestId!==pending.current||!['result','error'].includes(event.kind))return
   pending.current=null
   setBusy(false)
   if(event.kind==='error'){
     setError(typeof event.data==='string'?event.data:'OBS could not complete the action.')
     return
   }
   const next=event.data as ClipReport
   if(next&&typeof next.connected==='boolean'){
     setReport(next)
     setFeedback(next.message||'OBS answered.')
     setError('')
   }else setError('STAR received an unexpected OBS response.')
 }),[])

 const invoke=async(action:ClipAction,body:Record<string,unknown>={})=>{
   if(disabled||busy)return
   setBusy(true);setFeedback('');setError('')
   const requestId=crypto.randomUUID()
   pending.current=requestId
   const response=await request<ClipReport>(action,{...body,confirm:true},requestId)
   if(!response.ok){
     pending.current=null;setBusy(false)
     setError(response.error||'STAR could not contact its desktop recording bridge.')
   }else if(!response.pending){
     pending.current=null;setBusy(false)
     if(response.data){setReport(response.data);setFeedback(response.data.message||'OBS answered.')}
   }
 }

 return <Panel className="settings-section star-clips">
   <div className="star-clips__intro">
     <div className="tool-icon"><Clapperboard size={22} aria-hidden="true"/></div>
     <div>
       <h2>STAR Clips</h2>
       <p>Instant replay through your own OBS Studio. Recording is off until you start it.</p>
     </div>
   </div>
   <p className="star-clips__hint">Run OBS 28+ and enable its authenticated WebSocket in Tools → WebSocket Server Settings (port 4455). Choose the game capture scene, replay length, quality and audio sources inside OBS first.</p>
   <form className="star-clips__connect" onSubmit={event=>{
     event.preventDefault()
     if(password.trim()){
       void invoke('clipConnect',{password})
       setPassword('') // Never store the credential in localStorage, a chat or a settings file.
     }
   }}>
     <label htmlFor="star-clips-obs-password">OBS WebSocket password</label>
     <div className="star-clips__connection-controls">
       <input id="star-clips-obs-password" type="password" value={password} autoComplete="off" placeholder="From OBS connection info"
         disabled={disabled||busy||report.connected} onChange={event=>setPassword(event.target.value)} maxLength={256}/>
       {report.connected
         ?<button type="button" className="secondary-button" disabled={disabled||busy} onClick={()=>void invoke('clipDisconnect')}><Unplug size={15}/> Disconnect</button>
         :<button type="submit" className="primary-button" disabled={disabled||busy||!password.trim()}><Link2 size={15}/> Connect</button>}
     </div>
   </form>
   <div className="star-clips__status" role="status" aria-live="polite">
     <span className={'star-clips__dot'+(report.buffer_active?' is-running':'')} aria-hidden="true"/>
     <span>{report.buffer_active?'Replay buffer running':report.connected?'Connected — replay stopped':'Not connected'}</span>
     {busy&&<span> · Working…</span>}
   </div>
   <div className="star-clips__actions">
     <button type="button" className="secondary-button" disabled={disabled||busy||!report.connected}
       onClick={()=>void invoke('clipStatus')}>Refresh OBS status</button>
     <button type="button" className="secondary-button" disabled={disabled||busy||!report.connected||report.buffer_active} onClick={()=>void invoke('clipStartBuffer')}>
       <Play size={15}/> Start replay
     </button>
     <button type="button" className="primary-button" disabled={disabled||busy||!report.buffer_active} onClick={()=>void invoke('clipSaveReplay')}>
       <HardDriveDownload size={15}/> Clip that!
     </button>
     <button type="button" className="secondary-button" disabled={disabled||busy||!report.buffer_active} onClick={()=>void invoke('clipStopBuffer')}>
       <Square size={14}/> Stop replay
     </button>
   </div>
   {feedback&&<p className="star-clips__feedback" role="status">{feedback}</p>}
   {error&&<p className="star-clips__error" role="alert">{error}</p>}
   <p className="star-clips__footnote"><CircleHelp size={14} aria-hidden="true"/> OBS decides what pixels and audio are recorded, and saves files in its configured recording folder. STAR does not upload them. Voice activation, automatic game-event clips, editing and companion reactions are future stages.</p>
 </Panel>
}
