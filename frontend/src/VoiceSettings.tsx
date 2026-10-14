/**
 * Settings > Voice: the voice picker.
 *
 * The desktop host owns the catalog (star/voice/voices.json through `voiceListVoices`): three speaking
 * styles, each a group of voices. This page lists them, plays one sample line per voice
 * (`voicePreviewVoice`, answered by a `preview_done` or `error` voice event with the same request id)
 * and stores the owner's choice (`voiceSelectVoice`).
 *
 * What it must stay honest about:
 *  - the commanding style is offered, never preselected: its voices appear only after the owner
 *    switches them on (or when one of them is already the saved voice);
 *  - a voice whose engine is not built into calls is listed, labelled, and cannot be played or chosen
 *    here; the reason is the host's own text;
 *  - when the voice engine is not installed nothing is played and the page says what is missing;
 *  - a preview that fails says so on the row it belongs to. Nothing is reported as played or saved
 *    before the host confirmed it.
 *
 * It also holds the two voice habits (`voiceGetSettings` / `voiceSaveSettings`): automatic read-aloud of new
 * replies (off by default) and how calls listen (push to talk by default, or hands-free).
 */
import {useCallback,useEffect,useRef,useState} from 'react'
import {Check,LoaderCircle,Play,Volume2} from 'lucide-react'
import {onBackendEvent,request} from './bridge'
import {setAutoReadAloud} from './ReadAloud'
import type {VoiceCatalog,VoiceEngineStatus,VoiceEntry} from './types'
import './learning.css'
import './media.css'
import './settings-ui.css'
import './voice-call.css'

const DEFAULT_STYLE='warm-caring'
const OPT_IN_STYLE='confident-commanding'
/** The first preview also loads the voice model, so this is generous. */
const PREVIEW_LIMIT_MS=60_000
const RECOMMENDED:Record<string,string>={live:'Best for live calls',quality:'Best quality'}

/** The host prefixes a refusal with its Python error class; the owner only needs the sentence. */
export const plainError=(error:unknown,fallback:string)=>{
  const text=(typeof error==='string'?error:'').replace(/^[A-Z][A-Za-z]*(?:Error|Exception|Unavailable):\s*/,'').trim()
  return text?(/[.!?…]$/.test(text)?text:text+'.'):fallback
}

const firstSound=(voice:VoiceEntry)=>{
  const seconds=voice.latency?.first_audio_seconds
  if(typeof seconds!=='number')return ''
  return `${seconds} s to first sound`+(voice.latency?.device?`, measured on ${voice.latency.device}`:'')
}

type VoiceHabits={read_aloud_auto:boolean;call_mode:'push-to-talk'|'hands-free'}

function VoiceHabitsPanel({disabled}:{disabled:boolean}){
  const [habits,setHabits]=useState<VoiceHabits|null>(null)
  const [message,setMessage]=useState('')
  useEffect(()=>{
    if(disabled)return
    void request<{settings?:Partial<VoiceHabits>}>('voiceGetSettings').then(reply=>{
      const saved=reply.data?.settings
      if(reply.ok&&saved)setHabits({read_aloud_auto:saved.read_aloud_auto===true,call_mode:saved.call_mode==='hands-free'?'hands-free':'push-to-talk'})
    })
  },[disabled])
  const save=async(change:Partial<VoiceHabits>)=>{
    if(!habits)return
    setMessage('')
    const reply=await request<{settings?:Partial<VoiceHabits>}>('voiceSaveSettings',{settings:change})
    const saved=reply.data?.settings
    if(!reply.ok||!saved){setMessage(plainError(reply.error,'That change could not be saved.'));return}
    const next={read_aloud_auto:saved.read_aloud_auto===true,call_mode:saved.call_mode==='hands-free'?'hands-free' as const:'push-to-talk' as const}
    setHabits(next)
    setAutoReadAloud(next.read_aloud_auto)
    setMessage('Saved.')
  }
  if(!habits)return null
  return <div className="media-capability voice-habits" role="group" aria-label="Read-aloud and calls">
    <label className="learn-switch"><span><strong>Read new replies aloud</strong>
      <small>Star reads each new reply in her voice as soon as it is finished. Code, links and tables are not read out; she says they are on screen. Every reply also has a Read aloud button.</small></span>
      <input type="checkbox" checked={habits.read_aloud_auto} disabled={disabled} onChange={event=>void save({read_aloud_auto:event.target.checked})}/></label>
    <label className="voice-habit-select"><span><strong>Voice calls listen</strong>
      <small>Push to talk: only while you hold the talk button or Space. Hands-free: the microphone stays open during the call.</small></span>
      <select value={habits.call_mode} disabled={disabled} onChange={event=>void save({call_mode:event.target.value as VoiceHabits['call_mode']})}>
        <option value="push-to-talk">Push to talk</option><option value="hands-free">Hands-free</option></select></label>
    {message&&<p role="status" className="learn-help">{message}</p>}
  </div>
}

export function VoiceSettings({disabled=false}:{disabled?:boolean}){
  const [catalog,setCatalog]=useState<VoiceCatalog|null>(null)
  const [engine,setEngine]=useState<VoiceEngineStatus|null>(null)
  const [loadError,setLoadError]=useState('')
  const [previewing,setPreviewing]=useState('')
  const [failed,setFailed]=useState<{id:string;message:string}|null>(null)
  const [saving,setSaving]=useState('')
  const [notice,setNotice]=useState('')
  const [offerCommanding,setOfferCommanding]=useState(false)
  const preview=useRef<{id:string;requestId:string;timer:ReturnType<typeof setTimeout>}|null>(null)

  const endPreview=useCallback((failure?:string)=>{
    const current=preview.current
    if(!current)return
    clearTimeout(current.timer)
    preview.current=null
    setPreviewing('')
    if(failure)setFailed({id:current.id,message:failure})
  },[])

  const load=useCallback(async()=>{
    if(disabled)return
    const [voices,status]=await Promise.all([request<VoiceCatalog>('voiceListVoices'),request<VoiceEngineStatus>('voiceStatus')])
    if(voices.ok&&voices.data&&Array.isArray(voices.data.voices)&&Array.isArray(voices.data.styles)){
      setCatalog(voices.data);setLoadError('')
      if(voices.data.selected?.style===OPT_IN_STYLE)setOfferCommanding(true)
    }else setLoadError(plainError(voices.error,'The voice list could not be read.'))
    if(status.ok&&status.data)setEngine(status.data)
  },[disabled])
  useEffect(()=>{void load()},[load])

  useEffect(()=>onBackendEvent(event=>{
    const current=preview.current
    if(!current||event.kind!=='voice'||event.requestId!==current.requestId)return
    const data=(event.data||{}) as {type?:string;message?:string}
    if(data.type==='preview_done')endPreview()
    else if(data.type==='error')endPreview(plainError(data.message,'The voice engine reported an error.'))
  }),[endPreview])
  useEffect(()=>()=>{if(preview.current)clearTimeout(preview.current.timer)},[])

  const play=async(voice:VoiceEntry)=>{
    if(disabled||preview.current||saving)return
    const requestId=crypto.randomUUID()
    // Subscribe before asking: a short line can finish before the reply is handled.
    preview.current={id:voice.id,requestId,timer:setTimeout(()=>endPreview('No sound was confirmed within a minute. Check the voice engine and try again.'),PREVIEW_LIMIT_MS)}
    setPreviewing(voice.id);setFailed(null);setNotice('')
    const reply=await request('voicePreviewVoice',{voiceId:voice.id},requestId)
    if(!reply.ok&&preview.current?.requestId===requestId)endPreview(plainError(reply.error,'The preview could not start.'))
  }

  const choose=async(voice:VoiceEntry)=>{
    if(disabled||saving||preview.current)return
    setSaving(voice.id);setNotice('');setFailed(null)
    const reply=await request<{settings?:{voice?:string;voice_style?:string;voice_id?:string;speed?:number};appliesToNextCall?:boolean}>('voiceSelectVoice',{voiceId:voice.id})
    setSaving('')
    const saved=reply.data?.settings
    if(!reply.ok||!saved||saved.voice_id!==voice.id){
      setFailed({id:voice.id,message:plainError(reply.error,'The choice could not be confirmed, so nothing was changed.')})
      return
    }
    setCatalog(current=>current&&{...current,selected:{voiceId:voice.id,voice:saved.voice||'',style:saved.voice_style||voice.style,speed:saved.speed??current.selected.speed}})
    setNotice(`${voice.name} is now Star's voice.`+(reply.data?.appliesToNextCall?' The call that is running keeps its voice; the new one starts with the next call.':''))
  }

  const engineMissing=!!engine&&!engine.available
  // A profile that never chose a voice has no catalog id yet: its default recipe name is the catalog voice of that name.
  const selectedId=catalog?(catalog.selected.voiceId||(catalog.voices.some(voice=>voice.id===catalog.selected.voice)?catalog.selected.voice:'')):''
  const selected=catalog?.voices.find(voice=>voice.id===selectedId)
  const selectedStyle=catalog?.styles.find(style=>style.id===(selected?.style||catalog.selected.style))
  return <section className="learn" aria-label="Star's voice">
    <div className="learn-head"><Volume2 size={20}/><div className="learn-title"><h2>Star's voice</h2>
      <p>Choose how Star sounds when she reads replies aloud and in voice calls. Each style also changes how she words what she says on a call. Every voice here is an original synthetic voice; none of them copies a real person.</p></div></div>
    <VoiceHabitsPanel disabled={disabled}/>
    {!catalog&&!loadError&&<p className="learn-help">{disabled?'Open STAR Desktop to see and change this.':'Reading the voice list…'}</p>}
    {loadError&&<p role="alert" className="media-warning">The voice list could not be shown: {loadError}</p>}
    {engineMissing&&<p role="status" className="media-warning">The voice engine is not installed on this PC, so no voice can be played here yet.
      {engine!.missingPackages.length>0&&<> Missing program parts: {engine!.missingPackages.join(', ')}.</>}
      {engine!.missingModels.length>0&&<> Missing model files: {engine!.missingModels.join(', ')}.</>}
      {' '}You can still choose a voice; it is used once the engine is installed.</p>}
    {engine?.inCall&&<p role="status" className="learn-help">A voice call is running. Previews wait until it ends, and a new choice starts with the next call.</p>}
    {catalog&&<p className="voice-current">Current voice: <strong>{selected?selected.name:(catalog.selected.voice||'not set')}</strong>
      {selected?<> · {selectedStyle?.name}</>:catalog.selected.voice?' · a custom recipe that is not in this list':''}</p>}
    {notice&&<p role="status" className="learn-notice">{notice}</p>}
    {catalog?.styles.map(style=>{
      const voices=catalog.voices.filter(voice=>voice.style===style.id)
      const optIn=style.id===OPT_IN_STYLE
      const usable=voices.filter(voice=>voice.callable)
      const others=voices.filter(voice=>!voice.callable)
      const row=(voice:VoiceEntry)=>{
        const chosen=selectedId===voice.id
        const playing=previewing===voice.id
        const speed=firstSound(voice)
        return <li key={voice.id} className={'voice-row'+(chosen?' is-chosen':'')+(voice.callable?'':' is-unavailable')}>
          <div className="voice-text">
            <strong>{voice.name}</strong>
            <span className="voice-tags">
              {chosen&&<span className="voice-tag is-chosen"><Check size={12} aria-hidden="true"/> Selected</span>}
              {voice.recommended_for.map(use=>RECOMMENDED[use]&&<span key={use} className="voice-tag">{RECOMMENDED[use]}</span>)}
              {!voice.callable&&<span className="voice-tag is-off">Not usable in live calls yet</span>}
            </span>
            {voice.notes&&<small>{voice.notes}</small>}
            {!voice.callable&&voice.reason&&<small className="media-unavailable">{voice.reason}</small>}
            {speed&&<small>{speed}</small>}
            {failed?.id===voice.id&&<small role="alert" className="media-unavailable">Preview or choice failed: {failed.message}</small>}
          </div>
          <div className="voice-actions">
            <button type="button" className="learn-button" aria-label={`Preview ${voice.name}`}
              disabled={disabled||!voice.callable||engineMissing||!!engine?.inCall||!!previewing||!!saving} onClick={()=>void play(voice)}>
              {playing?<><LoaderCircle size={14} className="spin" aria-hidden="true"/> Playing…</>:<><Play size={14} aria-hidden="true"/> Preview</>}</button>
            <button type="button" className="learn-button is-primary" aria-label={`Use ${voice.name}`}
              disabled={disabled||!voice.callable||chosen||!!saving||!!previewing} onClick={()=>void choose(voice)}>
              {saving===voice.id?'Saving…':chosen?'In use':'Use this voice'}</button>
          </div>
        </li>
      }
      return <div key={style.id} className="media-capability" role="group" aria-label={style.name}>
        <h3 className="voice-style">{style.name}
          {style.id===DEFAULT_STYLE&&<span className="voice-tag">Default</span>}
          {optIn&&<span className="voice-tag">Optional</span>}</h3>
        <p className="voice-summary">{style.summary}</p>
        {optIn&&<label className="learn-switch voice-opt-in"><span><strong>Offer the confident and commanding voices</strong>
          <small>Off until you switch it on, and never the default. It is a manner of speaking only: mature, calm and firm. In this style Star is told to stay a mentor: nothing romantic, no role-play.</small></span>
          <input type="checkbox" checked={offerCommanding} disabled={disabled} onChange={event=>setOfferCommanding(event.target.checked)}/></label>}
        {(!optIn||offerCommanding)&&<>
          <p className="voice-count">{voices.length} voices, {usable.length} usable in live calls today. Sample line: “{style.preview_line}”</p>
          {usable.length>0&&<ul className="voice-list">{usable.map(row)}</ul>}
          {others.length>0&&<details className="voice-more">
            <summary>{others.length} more {others.length===1?'voice that is':'voices that are'} not usable in live calls yet</summary>
            <p className="voice-count">Their voice engines are not built into calls yet, so they cannot be played or chosen here. They are listed so you know they exist.</p>
            <ul className="voice-list">{others.map(row)}</ul>
          </details>}
        </>}
      </div>
    })}
  </section>
}
