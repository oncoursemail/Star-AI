/**
 * Settings > Discord: is STAR's Discord bot running, and should STAR Desktop run it for you.
 *
 * The desktop host owns the bot process (star/discord_supervisor.py): it starts it, restarts it with a
 * growing pause after a crash, and stops it when STAR closes. This page asks for the state
 * (`discordStatus`, every few seconds while it is open), sends Start and Stop (`discordStart`,
 * `discordStop`) and stores the opt-in "Start the Discord bot with STAR" (`discordSetAutostart`).
 *
 * What it must stay honest about:
 *  - "Connected" is shown only when the bot itself reported it; a process that has merely started is
 *    "Starting";
 *  - the token, the owner's Discord IDs and the server key are never sent to this page, so it cannot
 *    show them; it only says which setting is still missing;
 *  - a bot that is already running in a terminal or Task Scheduler is shown as such and not duplicated;
 *  - nothing is reported as started, stopped or saved before the host confirmed it.
 */
import {useCallback,useEffect,useRef,useState} from 'react'
import {LoaderCircle,MessageCircle,Play,Square} from 'lucide-react'
import {request} from './bridge'
import {plainError} from './VoiceSettings'
import type {DiscordState,DiscordStatus} from './types'
import './learning.css'
import './media.css'
import './settings-ui.css'

const POLL_MS=4_000
const LABEL:Record<DiscordState,string>={
  not_configured:'Not configured',stopped:'Stopped',starting:'Starting…',connected:'Connected',
  backoff:'Restarting soon',error:'Error',external:'Running in another window'}

const known=(value:unknown):value is DiscordStatus=>
  !!value&&typeof value==='object'&&typeof (value as DiscordStatus).state==='string'&&(value as DiscordStatus).state in LABEL

export function DiscordSettings({disabled=false}:{disabled?:boolean}){
  const [status,setStatus]=useState<DiscordStatus|null>(null)
  const [loadError,setLoadError]=useState('')
  const [busy,setBusy]=useState('')
  const [failure,setFailure]=useState('')
  const mounted=useRef(true)

  const apply=useCallback((reply:{ok:boolean;data?:unknown;error?:string},fallback:string)=>{
    if(!mounted.current)return false
    if(reply.ok&&known(reply.data)){setStatus(reply.data);setLoadError('');return true}
    setLoadError(plainError(reply.error,fallback))
    return false
  },[])

  const refresh=useCallback(async()=>{
    if(disabled)return
    apply(await request('discordStatus'),'The Discord status could not be read.')
  },[apply,disabled])

  useEffect(()=>{
    mounted.current=true
    void refresh()
    const timer=disabled?undefined:setInterval(()=>void refresh(),POLL_MS)
    return ()=>{mounted.current=false;if(timer)clearInterval(timer)}
  },[refresh,disabled])

  const run=async(action:string,payload:Record<string,unknown>={})=>{
    if(disabled||busy)return
    setBusy(action);setFailure('')
    const reply=await request(action,payload)
    if(!reply.ok)setFailure(plainError(reply.error,'The request did not go through, so nothing was changed.'))
    else apply(reply,'The host did not confirm the change.')
    if(mounted.current)setBusy('')
  }

  const state=status?.state
  const waiting=state==='starting'||state==='backoff'
  const canStart=!!status&&(state==='stopped'||state==='error'||state==='not_configured'||(state==='external'&&!status.wantsRunning))
  const canStop=!!status&&(status.wantsRunning||(status.running&&!status.external))
  return <section className="learn" aria-label="Discord">
    <div className="learn-head"><MessageCircle size={20}/><div className="learn-title"><h2>Discord</h2>
      <p>Talk to Star from your phone through her own Discord bot. It answers only you. The bot's token and your Discord IDs stay in files on this PC; this page never shows them.</p></div></div>
    {disabled&&!status&&<p className="learn-help">Open STAR Desktop to see and change this.</p>}
    {!status&&!loadError&&!disabled&&<p className="learn-help">Reading the Discord status…</p>}
    {loadError&&<p role="alert" className="media-warning">The Discord status could not be shown: {loadError}</p>}
    {status&&<>
      <p className="voice-current" role="status">Status: <strong>{LABEL[status.state]}</strong>
        {state==='backoff'&&status.retryInSeconds!==null&&<> · next try in {status.retryInSeconds} s</>}
        {status.restarts>0&&<> · restarted {status.restarts} {status.restarts===1?'time':'times'} since STAR opened</>}</p>
      <p className="learn-help">{status.message}</p>
      {state==='not_configured'&&status.missing.length>0&&<p role="status" className="media-warning">Still missing: {status.missing.join(', ')}. Setup takes about ten minutes; the steps are in docs/STAR_DISCORD_SETUP.md.</p>}
      {state==='error'&&status.problem&&<p role="alert" className="media-warning">{status.problem}</p>}
      <div className="voice-actions">
        <button type="button" className="learn-button is-primary" disabled={disabled||!!busy||!canStart} onClick={()=>void run('discordStart')}>
          {busy==='discordStart'?<><LoaderCircle size={14} className="spin" aria-hidden="true"/> Starting…</>:<><Play size={14} aria-hidden="true"/> Start the bot</>}</button>
        <button type="button" className="learn-button" disabled={disabled||!!busy||!canStop} onClick={()=>void run('discordStop')}>
          {busy==='discordStop'?<><LoaderCircle size={14} className="spin" aria-hidden="true"/> Stopping…</>:<><Square size={14} aria-hidden="true"/> Stop the bot</>}</button>
      </div>
      {waiting&&<p className="learn-help">STAR starts the bot in the background. Connecting to Discord takes a few seconds.</p>}
      {failure&&<p role="alert" className="media-warning">{failure}</p>}
      <label className="learn-switch"><span><strong>Start the Discord bot with STAR</strong>
        <small>Off until you switch it on. When on, STAR starts the bot when it opens, starts it again after a crash (waiting longer each time), and stops it when STAR closes. Turning it off leaves a running bot alone; use Stop. To run the bot without STAR open, see the Task Scheduler steps in docs/STAR_DISCORD_SETUP.md.</small></span>
        <input type="checkbox" checked={status.autostart} disabled={disabled||!!busy} onChange={event=>void run('discordSetAutostart',{enabled:event.target.checked})}/></label>
      <p className="learn-help">The bot's log is {status.logFile} in STAR's log folder (Library, Open local STAR files, logs).</p>
    </>}
  </section>
}
