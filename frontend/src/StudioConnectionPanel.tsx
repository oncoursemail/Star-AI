import {useEffect,useRef,useState} from 'react'
import {LoaderCircle,RefreshCcw,Workflow} from 'lucide-react'
import {onBackendEvent} from './bridge'
import type {AppSettings,BackendEvent,StudioConnectionStatus,StudioTarget} from './types'

type Invoke=(action:string,params?:Record<string,unknown>)=>Promise<unknown>
type Permissions={studio_edit:boolean;studio_luau:boolean}
type Operation={id:string;target:StudioTarget;action:string;permissions?:Permissions;studioId?:string}
const permissionsFor=(settings:AppSettings):Permissions=>({studio_edit:settings.studio_edit===true,
 studio_luau:settings.studio_edit===true&&settings.studio_luau===true})
const labels={local_pc:'This PC · your Studio',host_launcher:'Practice Studio · configured host'}
const states={not_checked:'MCP not checked yet',unconfigured:'Practice connection not configured',
 connected:'Studio MCP responded',no_instances:'No open Studio connected',unavailable:'Studio MCP unavailable'}

export function StudioConnectionPanel({settings,status,invoke,onSaved,disabled=false}:{
 settings:AppSettings;status?:StudioConnectionStatus;invoke:Invoke;onSaved?:()=>void;disabled?:boolean
}){
 const [target,setTarget]=useState<StudioTarget>(settings.studio_target??'local_pc')
 const [report,setReport]=useState(status)
 const [pending,setPending]=useState('')
 const [error,setError]=useState('')
 const [permissions,setPermissions]=useState(()=>permissionsFor(settings))
 const operation=useRef<Operation|null>(null)
 const early=useRef(new Map<string,BackendEvent>())
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null)
 const currentTarget=useRef(target);currentTarget.current=target
 const saved=useRef(onSaved);saved.current=onSaved
 const finish=useRef<(event:BackendEvent)=>void>(()=>{})
 const clear=()=>{operation.current=null;setPending('');early.current.clear();if(timer.current)clearTimeout(timer.current)}
 const failure=()=>{
   const savingPermissions=!!operation.current?.permissions
   if(!savingPermissions)setReport(undefined)
   setError(savingPermissions?'Studio permission save could not be confirmed. Recheck before starting a Studio task.'
     :'The connection could not be verified. Check Studio and test again.')
   clear()
 }
 const acceptSave=(active:Operation,value:unknown)=>{
   const reply=value as Partial<AppSettings>|null
   if(!reply||reply.studio_target!==active.target){failure();return}
   if(active.permissions){
     if(reply.studio_id!==active.studioId||reply.studio_edit!==active.permissions.studio_edit
       ||reply.studio_luau!==active.permissions.studio_luau){failure();return}
     setPermissions(active.permissions)
   }else{
     setTarget(active.target);setReport(undefined);setPermissions({studio_edit:false,studio_luau:false})
   }
   setError('');clear();saved.current?.()
 }
 finish.current=event=>{
   const active=operation.current
   if(!active||event.requestId!==active.id||event.kind==='progress')return
   if(active.target!==currentTarget.current){clear();return}
   if(event.kind==='error'){failure();return}
   if(active.action==='saveSettings'){acceptSave(active,event.data);return}
   const result=event.data as StudioConnectionStatus|null
   if(!result||result.target!==active.target||!Array.isArray(result.instances)||!Object.hasOwn(states,result.state)){
     failure();return
   }
   setReport(result);if(active.action==='selectStudio')setPermissions({studio_edit:false,studio_luau:false})
   setError('');clear();saved.current?.()
 }
 useEffect(()=>onBackendEvent(event=>{
   const active=operation.current
   if(!active)return
   if(!active.id){early.current.set(event.requestId,event);if(early.current.size>8)early.current.delete(early.current.keys().next().value!)}
   else finish.current(event)
 }),[])
 useEffect(()=>{
   const next=settings.studio_target??'local_pc'
   if(next!==currentTarget.current){clear();setTarget(next);setError('')}
   setReport(status)
 },[settings.studio_target,status])
 useEffect(()=>setPermissions(permissionsFor(settings)),
   [settings.studio_target,settings.studio_id,settings.studio_edit,settings.studio_luau])
 useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);operation.current=null},[])
 const run=async(action:string,payload:Record<string,unknown>,selectedTarget=target,permissionSave?:Permissions)=>{
   if(disabled||operation.current)return
   const active:Operation={id:'',target:selectedTarget,action,
     ...(permissionSave?{permissions:permissionSave,studioId:settings.studio_id}:{})}
   operation.current=active;setPending(action);setError('')
   if(action==='discoverStudio')setReport(undefined)
   timer.current=setTimeout(()=>{if(operation.current===active)failure()},20000)
   try{
     const reply=await invoke(action,payload) as {pending?:boolean;requestId?:string;studio_target?:StudioTarget}|null
     if(operation.current!==active)return
     if(!reply){failure();return}
     if(reply.pending&&reply.requestId){
       active.id=reply.requestId
       const event=early.current.get(active.id);early.current.clear();if(event)finish.current(event)
     }else if(action==='saveSettings'){
       acceptSave(active,reply)
     }else{
       active.id='immediate';finish.current({requestId:'immediate',kind:'result',data:reply})
     }
   }catch{if(operation.current===active)failure()}
 }
 const changeTarget=(next:StudioTarget)=>{
   setReport(undefined)
   void run('saveSettings',{settings:{studio_target:next}},next)
 }
 const visible=report?.target===target?report:undefined
 const connected=visible?.state==='connected'
 const selected=connected&&visible.selected_valid?visible.selected_id:''
 const canChangePermissions=!!selected&&selected===settings.studio_id&&!disabled&&!pending
 const savePermissions=(next:Permissions)=>{
   if(!canChangePermissions)return
   void run('saveSettings',{settings:next},target,next)
 }
 return <section className="integrated-panel" aria-label="Roblox Studio connection">
   <div className="integrated-heading"><Workflow size={18}/><div><strong>STAR local MCP · Roblox Studio</strong>
     <span>Your Studio connection is separate from the AI model connection.</span></div></div>
   <label className="integrated-field">Studio connection
     <select value={target} disabled={disabled||!!pending} onChange={e=>changeTarget(e.target.value as StudioTarget)}>
       <option value="local_pc">{labels.local_pc}</option><option value="host_launcher">{labels.host_launcher}</option>
     </select>
   </label>
   {target==='local_pc'?<p className="integrated-help">Open Roblox Studio on this PC. In Assistant → Manage MCP Servers, enable Studio as an MCP server. Keep your place open, then test the connection. <a href="https://create.roblox.com/docs/studio/mcp">Roblox setup guide</a></p>
     :<p className="integrated-help">This is a separate operator-configured practice connection. A practice result does not approve changes to your game on this PC. Background practice and self-learning are not verified by this connection test.</p>}
   <div className="integrated-connector-actions"><button className="secondary-button" disabled={disabled||!!pending}
     onClick={()=>void run('discoverStudio',{target})}>{pending==='discoverStudio'?<LoaderCircle size={14} className="spin"/>:<RefreshCcw size={14}/>} Test & discover Studio</button></div>
   <p role="status" className="integrated-help">{pending?(operation.current?.permissions?'Saving Studio permissions…':'Checking the selected connection…'):states[visible?.state??'not_checked']}
     {visible?.local_mcp==='memory'&&<> · STAR local MCP answered · {visible.tool_count} tools discovered</>}
   </p>
   {visible?.checked_at&&<p className="integrated-help">Last check: {new Date(visible.checked_at).toLocaleTimeString()}. The connection is rechecked for each Studio task.</p>}
   {connected&&<label className="integrated-field">Open Studio instance
     <select value={selected} disabled={disabled||!!pending} onChange={e=>{if(e.target.value)void run('selectStudio',{target,studio_id:e.target.value})}}>
       <option value="">Choose the open place to connect</option>
       {visible.instances.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
     </select>
   </label>}
   {selected&&<p className="integrated-connected">Selected: {visible!.instances.find(item=>item.id===selected)?.name}. Verified for read access at the last check; edits still require scoped permission and a verified safe place.</p>}
   {selected&&<div className="integrated-help" aria-label="Studio permissions">
     <label className="setting-switch"><span><strong>Allow edits in the selected Studio</strong><small>Only when STAR verifies an eligible safe place</small></span>
       <input type="checkbox" checked={permissions.studio_edit} disabled={!canChangePermissions}
         onChange={e=>savePermissions({studio_edit:e.target.checked,studio_luau:e.target.checked&&permissions.studio_luau})}/></label>
     <label className="setting-switch"><span><strong>Allow Luau and instance building</strong><small>Separate permission to execute generated Luau in the Edit DataModel</small></span>
       <input type="checkbox" checked={permissions.studio_luau} disabled={!canChangePermissions||!permissions.studio_edit}
         onChange={e=>savePermissions({studio_edit:true,studio_luau:e.target.checked})}/></label>
   </div>}
   {visible?.state==='no_instances'&&<p className="integrated-help">The connector answered, but no Studio instance was listed. Open your place and check the MCP switch before testing again.</p>}
   {error&&<p role="alert" className="integrated-error">{error}</p>}
   <p className="integrated-help">Changing connection or instance clears edit and Luau permissions. A successful test verifies tool discovery, not a completed build.</p>
 </section>
}
