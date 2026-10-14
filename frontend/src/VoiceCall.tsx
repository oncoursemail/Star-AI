/**
 * Voice call with Star: push-to-talk first, hands-free as an option.
 *
 * Contract with the desktop host (star/voice/bridge.py, docs/STAR_VOICE_CALLS.md):
 *  - `voiceStatus` before anything: is the voice engine installed, is a brain configured;
 *  - `voiceStartCall {micConsent: true, settings: {call_mode}}` only after the owner pressed Start on the consent
 *    step (the host refuses a start without micConsent); events arrive as kind "voice" keyed by that request id;
 *  - `voicePushToTalk {down}` while the talk button or the Space bar is held (push-to-talk calls only);
 *  - `voiceInterrupt` (Stop talking), `voiceStopCall` (Hang up, also when the window closes).
 *
 * Honesty rules: the microphone is opened by the host only after Start; the screen says which mode is listening;
 * nothing is shown as heard or said before the host reported it; latency numbers are the host's measurements.
 */
import {useCallback,useEffect,useRef,useState} from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import {Mic,PhoneCall,PhoneOff,ShieldCheck,Square,X} from 'lucide-react'
import {isDesktop,onBackendEvent,request} from './bridge'
import {stopReading} from './ReadAloud'
import type {VoiceEngineStatus} from './types'
import './voice-call.css'

type CallMode='push-to-talk'|'hands-free'
type Line={who:'you'|'star';text:string;interrupted?:boolean}
type Stages={total?:number|null;endpoint?:number|null;asr?:number|null;transcript_to_first_token?:number|null;first_token_to_first_audio?:number|null}
type VoiceEvent={type?:string;state?:string;message?:string;text?:string;mic?:number;heard_text?:string;stages?:Stages;end_reason?:string;barge_in?:boolean;reason?:string}

const STATE_TEXT:Record<string,string>={
  starting:'Getting ready…',listening:'Listening',user_speaking:'Hearing you',thinking:'Thinking',speaking:'Star is talking',ended:'Call ended',
}
const seconds=(value?:number|null)=>typeof value==='number'?`${value.toFixed(2)} s`:'–'
const plain=(error:unknown,fallback:string)=>{
  const text=(typeof error==='string'?error:'').replace(/^[A-Z][A-Za-z]*(?:Error|Exception):\s*/,'').trim()
  return text||fallback
}

/** Pure helper (tested): fold one host event into the transcript. */
export function applyCallEvent(lines:Line[],event:VoiceEvent):Line[]{
  if(event.type==='final_transcript'&&event.text)return [...lines,{who:'you',text:event.text}]
  if(event.type==='assistant_sentence'&&event.text){
    const last=lines[lines.length-1]
    if(last&&last.who==='star'&&!last.interrupted)return [...lines.slice(0,-1),{...last,text:`${last.text} ${event.text}`}]
    return [...lines,{who:'star',text:event.text}]
  }
  if(event.type==='interrupted'){
    const last=lines[lines.length-1]
    if(last&&last.who==='star')return [...lines.slice(0,-1),{...last,text:event.heard_text||last.text,interrupted:true}]
  }
  return lines
}

export function VoiceCallButton({disabled=false}:{disabled?:boolean}){
  const [open,setOpen]=useState(false)
  if(!isDesktop())return null
  return <>
    <button type="button" className="cmp-icon-button cmp-call" title="Voice call with Star" aria-label="Start a voice call with Star" disabled={disabled} onClick={()=>setOpen(true)}>
      <PhoneCall size={17} aria-hidden="true"/>
    </button>
    {open&&<VoiceCallDialog onClose={()=>setOpen(false)}/>}
  </>
}

export function VoiceCallDialog({onClose}:{onClose:()=>void}){
  const [engine,setEngine]=useState<VoiceEngineStatus|null>(null)
  const [mode,setMode]=useState<CallMode>('push-to-talk')
  const [callId,setCallId]=useState('')
  const [state,setState]=useState('idle')
  const [progress,setProgress]=useState('')
  const [error,setError]=useState('')
  const [lines,setLines]=useState<Line[]>([])
  const [partial,setPartial]=useState('')
  const [level,setLevel]=useState(0)
  const [talking,setTalking]=useState(false)
  const [last,setLast]=useState<Stages|null>(null)
  const [turns,setTurns]=useState<number[]>([])
  const call=useRef('')
  const held=useRef(false)

  useEffect(()=>{
    void request<{settings?:{call_mode?:string}}>('voiceGetSettings').then(reply=>{
      if(reply.ok&&reply.data?.settings?.call_mode==='hands-free')setMode('hands-free')
    })
    void request<VoiceEngineStatus>('voiceStatus').then(reply=>{if(reply.ok&&reply.data)setEngine(reply.data)})
  },[])

  useEffect(()=>onBackendEvent(event=>{
    if(event.kind!=='voice'||!call.current||event.requestId!==call.current)return
    const data=(event.data||{}) as VoiceEvent
    if(data.type==='state'&&data.state)setState(data.state)
    else if(data.type==='progress')setProgress(data.message||'')
    else if(data.type==='level')setLevel(Math.max(0,Math.min(1,Number(data.mic)||0)))
    else if(data.type==='partial_transcript')setPartial(data.text||'')
    else if(data.type==='error')setError(plain(data.message,'The call reported an error.'))
    else if(data.type==='turn_metrics'){
      setLast(data.stages||null)
      if(typeof data.stages?.total==='number')setTurns(list=>[...list,data.stages!.total as number])
    }else if(data.type==='ended'){
      setState('ended');call.current='';setCallId('');held.current=false;setTalking(false)
    }
    if(data.type==='final_transcript')setPartial('')
    setLines(current=>applyCallEvent(current,data))
  }),[])

  const start=async()=>{
    setError('');setLines([]);setLast(null);setTurns([]);setProgress('')
    await stopReading()
    const requestId=crypto.randomUUID()
    call.current=requestId;setCallId(requestId);setState('starting')
    const reply=await request('voiceStartCall',{micConsent:true,settings:{call_mode:mode}},requestId)
    if(!reply.ok){call.current='';setCallId('');setState('idle');setError(plain(reply.error,'The call could not start.'))}
  }

  const hangUp=useCallback(async()=>{
    if(call.current)await request('voiceStopCall')
    call.current='';setCallId('')
  },[])
  const close=()=>{void hangUp();onClose()}
  useEffect(()=>()=>{if(call.current)void request('voiceStopCall')},[])

  const ptt=useCallback((down:boolean)=>{
    if(!call.current||mode!=='push-to-talk'||held.current===down)return
    held.current=down;setTalking(down)
    void request('voicePushToTalk',{down}).then(reply=>{if(!reply.ok)setError(plain(reply.error,'Push-to-talk did not reach the call.'))})
  },[mode])

  // Space bar = talk button while the call window has focus (not while typing in a field).
  useEffect(()=>{
    if(!callId||mode!=='push-to-talk')return
    const typing=(target:EventTarget|null)=>target instanceof HTMLElement&&(target.isContentEditable||['INPUT','TEXTAREA','SELECT'].includes(target.tagName))
    const down=(event:KeyboardEvent)=>{if(event.code==='Space'&&!typing(event.target)){event.preventDefault();if(!event.repeat)ptt(true)}}
    const up=(event:KeyboardEvent)=>{if(event.code==='Space'){event.preventDefault();ptt(false)}}
    const blur=()=>ptt(false)
    window.addEventListener('keydown',down);window.addEventListener('keyup',up);window.addEventListener('blur',blur)
    return ()=>{window.removeEventListener('keydown',down);window.removeEventListener('keyup',up);window.removeEventListener('blur',blur)}
  },[callId,mode,ptt])

  const live=!!callId
  const missing=engine&&!engine.available
  const average=turns.length?turns.reduce((a,b)=>a+b,0)/turns.length:null
  return <Dialog.Root open onOpenChange={next=>{if(!next)close()}}>
    <Dialog.Portal>
      <Dialog.Overlay className="star-layer consent-overlay"/>
      <Dialog.Content className="star-layer consent-dialog voice-call" aria-describedby="voice-call-text">
        <Dialog.Close className="voice-call-close" aria-label="Close the call window"><X size={16}/></Dialog.Close>
        <span className="consent-icon" aria-hidden="true"><PhoneCall size={20}/></span>
        <Dialog.Title className="consent-title">{live?'On a call with Star':'Talk with Star?'}</Dialog.Title>
        {!live&&<>
          <p id="voice-call-text" className="consent-text">Star will use your <strong>microphone</strong> only while this call is open, and speaks her replies out loud. What you say is turned into text on this PC and sent to Star's brain like a typed message; the call's text is added to this chat. No audio is saved.</p>
          <fieldset className="voice-call-modes">
            <legend>How Star listens</legend>
            <label><input type="radio" name="voice-call-mode" checked={mode==='push-to-talk'} onChange={()=>setMode('push-to-talk')}/>
              <span><strong>Push to talk</strong> (recommended)<small>She only listens while you hold the talk button or the Space bar.</small></span></label>
            <label><input type="radio" name="voice-call-mode" checked={mode==='hands-free'} onChange={()=>setMode('hands-free')}/>
              <span><strong>Hands-free</strong><small>The microphone stays open and Star notices when you start and stop talking. Best with headphones.</small></span></label>
          </fieldset>
          {missing&&<p role="alert" className="media-warning">The voice engine is not installed on this PC yet.
            {engine!.missingPackages.length>0&&<> Missing program parts: {engine!.missingPackages.join(', ')}.</>}
            {engine!.missingModels.length>0&&<> Missing model files: {engine!.missingModels.join(', ')}.</>}</p>}
          {engine&&!engine.serverConfigured&&<p className="consent-note">Calls use the quick model on your STAR Server. Add its address and key in Settings first.</p>}
          <p className="consent-note"><ShieldCheck size={14} aria-hidden="true"/> Nothing listens until you press Start call. Hang up or close this window and the microphone is closed.</p>
          {error&&<p role="alert" className="media-warning">{error}</p>}
          <div className="consent-actions">
            <button type="button" className="consent-button" onClick={close}>Not now</button>
            <button type="button" className="consent-button is-primary" disabled={!engine||!!missing||state==='starting'} onClick={()=>void start()}>Start call</button>
          </div>
        </>}
        {live&&<>
          <p id="voice-call-text" className="voice-call-state" role="status" aria-live="polite">
            <span className={'voice-call-dot is-'+state} aria-hidden="true"/>{state==='starting'&&progress?progress:(STATE_TEXT[state]||state)}
            <span className="voice-call-mode-tag">{mode==='push-to-talk'?'Push to talk':'Hands-free: listening'}</span>
          </p>
          <div className="voice-call-level" aria-hidden="true"><span style={{transform:`scaleX(${level})`}}/></div>
          <ol className="voice-call-lines" aria-label="Call transcript">
            {lines.map((line,index)=><li key={index} className={'is-'+line.who}><strong>{line.who==='you'?'You':'Star'}</strong> {line.text}{line.interrupted?' (stopped)':''}</li>)}
            {partial&&<li className="is-you is-partial"><strong>You</strong> {partial}…</li>}
          </ol>
          {last&&<p className="voice-call-latency">Last reply: first sound {seconds(last.total)} after you stopped talking
            {' '}(transcript {seconds(last.asr)}, brain {seconds(last.transcript_to_first_token)}, voice {seconds(last.first_token_to_first_audio)}){average!==null&&turns.length>1?` · average ${average.toFixed(2)} s over ${turns.length} replies`:''}</p>}
          {error&&<p role="alert" className="media-warning">{error}</p>}
          {mode==='push-to-talk'&&<button type="button" className={'voice-call-talk'+(talking?' is-held':'')} aria-pressed={talking} disabled={state==='starting'}
            onPointerDown={event=>{event.preventDefault();event.currentTarget.setPointerCapture?.(event.pointerId);ptt(true)}}
            onPointerUp={()=>ptt(false)} onPointerCancel={()=>ptt(false)} onLostPointerCapture={()=>ptt(false)}
            onKeyDown={event=>{if((event.key==='Enter')&&!event.repeat)ptt(true)}} onKeyUp={event=>{if(event.key==='Enter')ptt(false)}}>
            <Mic size={20} aria-hidden="true"/> {talking?'Listening… let go when you are done':'Hold to talk (or hold Space)'}
          </button>}
          <div className="consent-actions">
            <button type="button" className="consent-button" disabled={state!=='speaking'&&state!=='thinking'} onClick={()=>void request('voiceInterrupt')}><Square size={12} fill="currentColor" aria-hidden="true"/> Stop talking</button>
            <button type="button" className="consent-button is-danger" onClick={()=>void hangUp()}><PhoneOff size={14} aria-hidden="true"/> Hang up</button>
          </div>
        </>}
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
