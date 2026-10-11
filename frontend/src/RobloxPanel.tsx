import {useCallback,useEffect,useRef,useState} from 'react'
import {Check,Gamepad2,LoaderCircle,Minus,RefreshCcw,ShieldCheck,X} from 'lucide-react'
import {onBackendEvent} from './bridge'
import type {AppSettings,RobloxAction,RobloxCheck,RobloxState,RobloxStatus} from './types'
import './integrated-tools.css'

type Invoke=(action:string,params?:Record<string,unknown>)=>Promise<unknown|null>
type Outcome={ok:boolean;data:unknown}

export const robloxStateLabel:Record<RobloxState,string>={
 no_key:'No key',unchecked:'Key stored, not tested yet',valid:'Valid',missing_permission:'Missing permission',
 invalid:'Not a key',revoked:'Revoked',unreachable:'Roblox could not be reached'}
const sourceText:Record<string,string>={keyring:"saved in this PC's credential store",file:'read from your key file',environment:'read from the environment'}
const good=(state:RobloxState)=>state==='valid'

/** One line a person can check before approving: what would be sent, to which place. */
export function describeAction(action:RobloxAction):string{
 const where=`${action.target.name||'test experience'} (place ${action.target.place_id})`
 const detail=action.detail||{}
 if(action.kind==='publish')return `Publish a place file to ${where} as a saved version: ${Number(detail.bytes)||0} bytes, ${Array.isArray(detail.files)?detail.files.length:0} source files`
 return `Run ${detail.standard_harness?'the standard test harness':'a test script'} (${Number(detail.script_chars)||0} characters) in ${where}${detail.version?`, version ${detail.version}`:''}`
}
/** What came back, in a sentence. Never invents a success. */
export function describeResult(action:RobloxAction):string{
 const result=action.result||{}
 if(action.status==='rejected')return 'You rejected this.'
 if(action.status==='expired')return 'Expired before a decision.'
 if(action.status==='running')return 'Running now.'
 if(typeof result.error==='string'&&result.error)return result.error
 if(action.kind==='publish'&&typeof result.version==='number')return `Published as saved version ${result.version}.`
 if(typeof result.state==='string')return `Test run ended as ${result.state}${typeof result.log_lines==='number'?` with ${result.log_lines} log lines`:''}.`
 return ''
}

/** Starts an action that answers later (it talks to Roblox on a worker) and resolves with its one result. */
function useLater(invoke:Invoke){
 const waiting=useRef(new Map<string,(outcome:Outcome)=>void>())
 const early=useRef(new Map<string,Outcome>())
 useEffect(()=>onBackendEvent(event=>{
   if(event.kind==='progress')return
   const outcome={ok:event.kind==='result',data:event.data}
   const done=waiting.current.get(event.requestId)
   if(done){waiting.current.delete(event.requestId);done(outcome)}
   else{early.current.set(event.requestId,outcome);if(early.current.size>20)early.current.clear()}
 }),[])
 return useCallback(async(action:string,params:Record<string,unknown>={}):Promise<Outcome>=>{
   const reply=await invoke(action,params) as {pending?:boolean;requestId?:string}|null
   if(!reply)return {ok:false,data:'STAR could not start this.'}
   if(!reply.pending||!reply.requestId)return {ok:true,data:reply}
   const id=reply.requestId
   const already=early.current.get(id)
   if(already){early.current.delete(id);return already}
   return new Promise(resolve=>waiting.current.set(id,resolve))
 },[invoke])
}

/** The Roblox key, its test, the one test experience, the actions that wait for the owner, and the Studio switches.
 *  The key is read from the input element once and handed to the host; it is never kept in React state. */
export function RobloxPanel({status,draft,onChange,invoke,disabled=false}:{status?:RobloxStatus;draft:AppSettings;onChange:(settings:AppSettings)=>void;invoke:Invoke;disabled?:boolean}){
 const [current,setCurrent]=useState<RobloxStatus|undefined>(status)
 const [check,setCheck]=useState<RobloxCheck|null>(null)
 const [actions,setActions]=useState<RobloxAction[]>([])
 const [busy,setBusy]=useState('')
 const [note,setNote]=useState('')
 const [problem,setProblem]=useState('')
 const [universe,setUniverse]=useState('')
 const [place,setPlace]=useState('')
 const keyField=useRef<HTMLInputElement>(null)
 const later=useLater(invoke)
 useEffect(()=>{if(status)setCurrent(status)},[status])
 const state:RobloxState=current?.state||'no_key'
 const locked=disabled||busy!==''

 const loadActions=useCallback(async()=>{
   const reply=await invoke('robloxListActions') as {actions?:RobloxAction[]}|null
   if(reply&&Array.isArray(reply.actions))setActions(reply.actions)
 },[invoke])
 useEffect(()=>{if(!disabled&&current?.key_present)void loadActions()},[disabled,current?.key_present,loadActions])

 const run=async(label:string,work:()=>Promise<void>)=>{
   if(locked)return
   setBusy(label);setNote('');setProblem('')
   try{await work()}finally{setBusy('')}
 }
 const adopt=(value:unknown)=>{
   const next=value as RobloxStatus|null
   if(next&&typeof next.state==='string'){setCurrent(next);if(next.check)setCheck(next.check)}
 }
 const saveKey=()=>run('save',async()=>{
   const field=keyField.current
   const typed=field?.value.trim()||''
   if(field)field.value=''
   if(!typed){setProblem('Paste the API key first.');return}
   const saved=await invoke('robloxSaveKey',{key:typed})
   if(saved){adopt(saved);setCheck(null);setNote('Key saved. Press Test to check it.')}
 })
 const forgetKey=()=>run('forget',async()=>{
   const cleared=await invoke('robloxClearKey')
   if(cleared){adopt(cleared);setCheck(null);setNote('Stored key removed.')}
 })
 const test=()=>run('test',async()=>{
   const outcome=await later('robloxTestKey')
   if(outcome.ok)adopt(outcome.data);else setProblem(String(outcome.data||'The test could not run.').slice(0,300))
 })
 const useExperience=()=>run('experience',async()=>{
   if(!/^\d{1,19}$/.test(universe.trim())||!/^\d{1,19}$/.test(place.trim())){setProblem('Enter the universe ID and the place ID as numbers.');return}
   // `approved` says: the owner pressed this button. The host refuses the action without it.
   const outcome=await later('robloxSetTestExperience',{universe_id:Number(universe.trim()),place_id:Number(place.trim()),approved:true})
   if(outcome.ok){adopt(outcome.data);setUniverse('');setPlace('');setNote('Test experience saved.')}
   else setProblem(String(outcome.data||'Roblox did not confirm this experience.').slice(0,300))
 })
 const clearExperience=()=>run('experience',async()=>{adopt(await invoke('robloxClearTestExperience'))})
 const decide=(action:RobloxAction,decision:'approve'|'reject')=>run(action.id,async()=>{
   const outcome=await later('robloxDecideAction',{id:action.id,decision,approved:true})
   if(!outcome.ok)setProblem(String(outcome.data||'The action could not be carried out.').slice(0,300))
   await loadActions()
 })

 const experience=current?.test_experience
 const account=check?.account||current?.last_check?.account
 const pending=actions.filter(action=>action.status==='pending')
 const finished=actions.filter(action=>action.status!=='pending').slice(0,4)
 return <section className="integrated-panel" aria-label="Roblox settings">
   <div className="integrated-heading"><Gamepad2 size={18}/><div><strong>Roblox</strong><span>Connect an Open Cloud API key made on STAR's own Roblox account. STAR reads with it. Publishing a place and running a test wait for your approval, and only ever go to the one private test experience you choose below.</span></div></div>
   <p className={good(state)?'integrated-confirm':state==='no_key'||state==='unchecked'?'integrated-help':'integrated-error'} role="status"><strong>Key: {robloxStateLabel[state]}.</strong> {check?.message||current?.message||''}{current?.key_present&&current.source?` The key is ${sourceText[current.source]||current.source}.`:''}{account?.user_id?` Account: ${account.name||'user'} (${account.user_id}).`:''}</p>
   <label className="integrated-field">Open Cloud API key (never saved in STAR settings, never shown again)
     <input ref={keyField} type="password" autoComplete="off" spellCheck={false} disabled={locked} placeholder="Paste the key from create.roblox.com, Credentials"/>
   </label>
   <div className="integrated-actions">
     <button type="button" className="secondary-button" disabled={locked} onClick={()=>void saveKey()}>{busy==='save'?<LoaderCircle size={14} className="spin"/>:<Check size={14}/>} Save key</button>
     <button type="button" className="secondary-button" disabled={locked||!current?.key_present} onClick={()=>void test()}>{busy==='test'?<LoaderCircle size={14} className="spin"/>:<ShieldCheck size={14}/>} Test</button>
     <button type="button" className="secondary-button" disabled={locked||current?.source!=='keyring'} onClick={()=>void forgetKey()}><X size={14}/> Forget key</button>
   </div>
   {note&&<p role="status" className="integrated-confirm">{note}</p>}
   {problem&&<p role="alert" className="integrated-error">{problem}</p>}
   {check&&check.capabilities.length>0&&<div className="integrated-notes"><strong>What this key can do</strong>
     {check.capabilities.map(item=><div className="integrated-note" key={item.id}>
       <span>{item.granted?<Check size={13} aria-label="Allowed"/>:<Minus size={13} aria-label="Not allowed"/>} {item.label}{item.needs.length?`: needs ${item.needs.join(', ')}`:''}</span>
       <small>{item.status!==null&&item.status!==undefined?`HTTP ${item.status}`:item.evidence}</small>
     </div>)}
     {(check.missing||[]).length>0&&<p className="integrated-error">Add in the Creator Dashboard: {(check.missing||[]).join(', ')}</p>}
     {(check.warnings||[]).map(text=><p className="integrated-help" key={text}>{text}</p>)}
   </div>}
   <div className="integrated-notes"><strong>Test experience</strong>
     {experience?<div className="integrated-note"><span>{experience.name||'Unnamed experience'}: universe {experience.universe_id}, place {experience.place_id}, private, owned by the key's account. Checked {experience.verified_at}.</span><button type="button" disabled={locked} onClick={()=>void clearExperience()}>Stop using it</button></div>
     :<>
       <p className="integrated-help">Roblox cannot create an experience through an API key. In Roblox Studio, signed in as STAR's own account, publish a new Baseplate as a new private experience. Then copy its Universe ID and Start Place ID from create.roblox.com, Creations.</p>
       <div className="integrated-key-controls">
         <label className="integrated-field">Universe ID<input inputMode="numeric" value={universe} disabled={locked} onChange={e=>setUniverse(e.target.value)}/></label>
         <label className="integrated-field">Place ID<input inputMode="numeric" value={place} disabled={locked} onChange={e=>setPlace(e.target.value)}/></label>
       </div>
       <div className="integrated-actions"><button type="button" className="secondary-button" disabled={locked||!current?.key_present} onClick={()=>void useExperience()}>{busy==='experience'?<LoaderCircle size={14} className="spin"/>:<Check size={14}/>} Use this experience</button><span>STAR accepts it only if Roblox confirms it is private and owned by the key's account.</span></div>
     </>}
   </div>
   <div className="integrated-notes"><strong>Actions waiting for you ({pending.length})</strong>
     {pending.length===0&&<p className="integrated-help">Nothing is waiting. When STAR wants to publish to the test experience or run a test there, the request appears here first.</p>}
     {pending.map(action=><div className="integrated-note" key={action.id}>
       <span><strong>{action.summary}</strong><br/>{describeAction(action)}{typeof action.detail.sha256==='string'?<><br/><small>SHA-256 {action.detail.sha256.slice(0,16)}</small></>:null}{typeof action.detail.script_preview==='string'?<details><summary>Show the script{Number(action.detail.script_chars)>action.detail.script_preview.length?` (first ${action.detail.script_preview.length} of ${Number(action.detail.script_chars)} characters)`:''}</summary><pre className="tool-output">{action.detail.script_preview}</pre></details>:null}<br/><small>Expires {action.expires}</small></span>
       <span className="integrated-actions"><button type="button" disabled={locked} onClick={()=>void decide(action,'approve')}>{busy===action.id?'Working':'Approve'}</button><button type="button" disabled={locked} onClick={()=>void decide(action,'reject')}>Reject</button></span>
     </div>)}
     {finished.map(action=><div className="integrated-note" key={action.id}><span>{action.summary}: {action.status}. {describeResult(action)}</span></div>)}
     <div className="integrated-actions"><button type="button" className="secondary-button" disabled={locked||!current?.key_present} onClick={()=>void loadActions()}><RefreshCcw size={14}/> Refresh</button></div>
   </div>
   <div className="integrated-notes"><strong>Roblox Studio</strong>
     <p className="integrated-help">STAR only reads the place that is open in Studio, unless you switch edits on AND the place is a blank, unsaved Baseplate. It never edits another published place, never saves and never publishes. Press Save settings below after changing these.</p>
     <label className="integrated-field">Studio instance ID (from Tools, Discover Studio instances)<input value={draft.studio_id} disabled={disabled} onChange={e=>onChange({...draft,studio_id:e.target.value})}/></label>
     <label className="toggle-line"><input type="checkbox" checked={draft.studio_edit} disabled={disabled} onChange={e=>onChange({...draft,studio_edit:e.target.checked})}/> <span>Studio edits in a blank, unsaved place</span></label>
     <label className="toggle-line"><input type="checkbox" checked={!!draft.studio_own_places} disabled={disabled||!draft.studio_edit} onChange={e=>onChange({...draft,studio_own_places:e.target.checked})}/> <span>Also places of STAR's own account (the account of the tested key)</span></label>
     <label className="toggle-line"><input type="checkbox" checked={!!draft.studio_luau} disabled={disabled||!draft.studio_edit} onChange={e=>onChange({...draft,studio_luau:e.target.checked})}/> <span>Let STAR run Luau in the sandbox (needed to create parts and UI)</span></label>
   </div>
 </section>
}
