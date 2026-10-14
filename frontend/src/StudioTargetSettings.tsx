/**
 * Settings > Roblox Studio: which Studio STAR works in.
 *
 * Two choices: Roblox Studio on this PC, or the STAR Studio server (a Studio on the owner's server).
 * The choice is the saved `studio_target` (`saveSettings`). The server connection itself is set up by
 * the operator outside the app (docs/STUDIO_HOST_CONFIGURATION.md): this page only reads whether one
 * exists (`studioHostStatus`, star/studio_host.py) and never receives or stores its address or command.
 * "Test connection" is the host's own check (`discoverStudio`): it starts the connector, lists its
 * tools and the open places, and changes nothing in Studio.
 *
 * The sandbox rule is stated here in words because it is the thing the owner must be able to rely on;
 * the rule itself is code (star/studio_loop.py) and no setting on this page can widen it.
 * Choosing the open place and the edit permissions stays on the Tools page (StudioConnectionPanel).
 */
import {useCallback,useEffect,useRef,useState} from 'react'
import {LoaderCircle,RefreshCcw,ShieldCheck,Workflow} from 'lucide-react'
import {onBackendEvent,request} from './bridge'
import {plainError} from './VoiceSettings'
import type {AppSettings,StudioConnectionStatus,StudioHostStatus,StudioTarget} from './types'
import './learning.css'
import './media.css'
import './settings-ui.css'

/** The host allows itself 70 seconds for a check (star/studio_connections.py). */
const TEST_LIMIT_MS=80_000
const CHOICES:Array<{id:StudioTarget;label:string;note:string}>=[
  {id:'local_pc',label:'This PC',note:'Roblox Studio that is open on this PC. In Studio, open Assistant, Manage MCP Servers, and switch Studio on as an MCP server.'},
  {id:'host_launcher',label:'STAR Studio server',note:'A Roblox Studio that runs on your STAR server, signed in as STAR\'s own Roblox account. It needs a server connection that the operator set up on this PC.'},
]
const STAGES:Record<string,string>={
  configuration:'the stored connection could not be used',
  process_startup:'the command did not start',
  initialization:'the connector started but did not answer the first message',
  capability:'the connector does not offer Studio tools',
  tool_discovery:'the connector did not list its tools',
  instance_discovery:'the connector did not list the open places',
  probe:'the check did not finish',
  request:'a request to the connector failed',
  shutdown:'the connector did not close cleanly',
}
const stored=(host:StudioHostStatus|null)=>{
  if(!host)return ''
  if(host.source==='environment')return 'A server connection is set by the operator on this PC (STAR_STUDIO_MCP_COMMAND).'
  if(host.source==='settings')return 'A server connection is set up on this PC. Its address and command are not shown here.'
  if(host.source==='invalid')return 'The server connection file on this PC is damaged and is not used. The operator has to set it up again.'
  return 'No server connection is set up on this PC yet. It is set up by the operator, not from this page.'
}
const describe=(report:StudioConnectionStatus)=>{
  const places=report.instances.map(item=>item.name).join(', ')
  if(report.state==='connected')return `Connected. The Studio connector answered with ${report.tool_count} tools. Open in Studio: ${places}.`
  if(report.state==='no_instances')return 'The connector answered, but no Studio place is open on it. Open a place there and test again.'
  if(report.state==='unconfigured')return 'No server connection is set up on this PC, so nothing was started.'
  if(report.state==='unavailable'){
    const stage=report.diagnostic?.stage||''
    const why=report.diagnostic?.reason==='timeout'?'it took too long':report.diagnostic?.reason==='not_configured'?'no connection is stored':''
    return 'Could not connect'+(STAGES[stage]?`: ${STAGES[stage]}`:'')+(why?` (${why})`:'')+'. Nothing was changed. No other route was tried.'
  }
  return 'Not tested yet.'
}

export function StudioTargetSettings({settings,disabled=false,onSaved,openTools}:{
  settings:AppSettings;disabled?:boolean;onSaved?:()=>void;openTools?:()=>void
}){
  const [target,setTarget]=useState<StudioTarget>(settings.studio_target??'local_pc')
  const [host,setHost]=useState<StudioHostStatus|null>(null)
  const [busy,setBusy]=useState<''|'target'|'test'>('')
  const [report,setReport]=useState<StudioConnectionStatus|null>(null)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const test=useRef<{requestId:string;target:StudioTarget;timer:ReturnType<typeof setTimeout>}|null>(null)
  const saved=useRef(onSaved);saved.current=onSaved

  const endTest=useCallback((result:StudioConnectionStatus|null,failure='')=>{
    const current=test.current
    if(!current)return
    clearTimeout(current.timer)
    test.current=null
    setBusy('')
    if(result&&result.target===current.target&&Array.isArray(result.instances)){setReport(result);setError('');saved.current?.()}
    else{setReport(null);setError(failure||'The test did not return a usable result. Nothing was changed.')}
  },[])

  const loadHost=useCallback(async()=>{
    if(disabled)return
    const reply=await request<StudioHostStatus>('studioHostStatus')
    if(reply.ok&&reply.data)setHost(reply.data)
  },[disabled])
  useEffect(()=>{void loadHost()},[loadHost])
  useEffect(()=>{setTarget(settings.studio_target??'local_pc')},[settings.studio_target])
  useEffect(()=>onBackendEvent(event=>{
    const current=test.current
    if(!current||event.requestId!==current.requestId||event.kind==='progress'||event.kind==='voice')return
    if(event.kind==='error')endTest(null,plainError(event.data,'The test failed.')+' Nothing was changed.')
    else endTest(event.data as StudioConnectionStatus|null)
  }),[endTest])
  useEffect(()=>()=>{if(test.current)clearTimeout(test.current.timer)},[])

  const locked=disabled||!!busy
  const choose=async(next:StudioTarget)=>{
    if(locked||next===target)return
    setBusy('target');setError('');setNotice('');setReport(null)
    const reply=await request<Partial<AppSettings>>('saveSettings',{settings:{studio_target:next}})
    setBusy('')
    if(!reply.ok||reply.data?.studio_target!==next){setError(plainError(reply.error,'The choice could not be saved.'));return}
    setTarget(next)
    setNotice('Saved. The chosen place and its edit permissions were cleared, because they belong to the other Studio.')
    saved.current?.()
  }
  const runTest=async()=>{
    if(locked)return
    const requestId=crypto.randomUUID()
    test.current={requestId,target,timer:setTimeout(()=>endTest(null,'The test did not answer in time. Nothing was changed.'),TEST_LIMIT_MS)}
    setBusy('test');setError('');setNotice('');setReport(null)
    const reply=await request<StudioConnectionStatus>('discoverStudio',{target},requestId)
    if(test.current?.requestId!==requestId)return
    if(!reply.ok)endTest(null,plainError(reply.error,'The test could not start.')+' Nothing was changed.')
    else if(!reply.pending)endTest(reply.data??null)
  }

  const server=target==='host_launcher'
  return <section className="learn" aria-label="Roblox Studio">
    <div className="learn-head"><Workflow size={20}/><div className="learn-title"><h2>Roblox Studio</h2>
      <p>Choose which Roblox Studio STAR works in. This is separate from the AI model connection and from the Roblox key.</p></div></div>
    <p className="studio-rule"><ShieldCheck size={16} aria-hidden="true"/><span><strong>The sandbox rule.</strong> STAR only builds in its own test place: a blank place that was never published, or a place owned by STAR's own Roblox account once you allow those under Roblox in these settings. Every other place is read-only whatever is chosen here, and STAR never saves or publishes a place from Studio.</span></p>
    <div className="media-capability" role="radiogroup" aria-label="Studio STAR works in">
      <div className="media-options">
        {CHOICES.map(choice=>{
          const chosen=target===choice.id
          return <label key={choice.id} className={'media-option'+(chosen?' is-chosen':'')}>
            <input type="radio" name="studio-target" checked={chosen} disabled={locked} onChange={()=>void choose(choice.id)}/>
            <span className="media-option-text"><strong>{choice.label}</strong><small>{choice.note}</small></span>
          </label>
        })}
      </div>
    </div>
    {server&&<div className="media-capability" role="group" aria-label="STAR Studio server connection">
      <h3>Server connection</h3>
      <p className="voice-summary">The connection to the STAR Studio server is set up by the operator on this PC, outside this page. STAR never asks for or stores a password for it.</p>
      <div className="media-engine">
        <span className="media-engine-state">{stored(host)||'Reading the state…'}</span>
      </div>
    </div>}
    <div className="media-engine">
      <span role="status" className={'media-engine-state'+(report?.state==='connected'?' is-ready':'')}>{busy==='test'?`Testing ${server?'the STAR Studio server':'Roblox Studio on this PC'}… this can take up to a minute.`:report?describe(report):'Not tested yet. The test lists the connector\'s tools and the open places; it changes nothing in Studio.'}</span>
      <button type="button" className="learn-button" disabled={locked} onClick={()=>void runTest()}>{busy==='test'?<LoaderCircle size={14} className="spin" aria-hidden="true"/>:<RefreshCcw size={14} aria-hidden="true"/>} Test connection</button>
    </div>
    {report?.state==='connected'&&<p className="learn-help">{report.selected_valid?'The place chosen earlier is still open. ':'No place is chosen for this connection yet. '}Choosing the place and allowing edits is done under Tools.{openTools&&<> <button type="button" className="learn-button" onClick={openTools}>Open Tools</button></>}</p>}
    {notice&&<p role="status" className="learn-notice">{notice}</p>}
    {error&&<p role="alert" className="media-warning">{error}</p>}
  </section>
}
