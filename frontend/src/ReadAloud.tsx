/**
 * Read-aloud: Star reads a chat reply in her voice (the voice chosen in Settings > Star's voice).
 *
 * The desktop host does the work (`voiceSpeak` in star/voice/bridge.py): it turns the Markdown into speech text
 * (no headings, code or links read out) and answers with `speak_started`, then `speak_done` or `error`, as voice
 * events carrying the same request id. One reply speaks at a time: pressing Read aloud on another reply, or Stop,
 * cuts the current one short.
 *
 * Automatic read-aloud is opt-in (`read_aloud_auto` in the voice settings, switched in Settings) and only applies
 * to a reply that was just streamed in front of the owner (the live answer ended a moment ago and this is the
 * newest reply), never to history. Each live answer is read at most once.
 */
import {useEffect,useRef,useSyncExternalStore} from 'react'
import {Square,Volume2} from 'lucide-react'
import {isDesktop,onBackendEvent,request} from './bridge'

type ReadState={speakingId:string;requestId:string;started:boolean;errorId:string;error:string;auto:boolean}
let state:ReadState={speakingId:'',requestId:'',started:false,errorId:'',error:'',auto:false}
const listeners=new Set<()=>void>()
const autoSpoken=new Set<string>()
/** When the last live (streaming) answer finished, ms since epoch; 0 once an automatic read has used it. */
let liveEndedAt=0
const LIVE_WINDOW_MS=8000
let watching:(()=>void)|null=null
let autoLoaded=false

function update(next:Partial<ReadState>){
  state={...state,...next}
  listeners.forEach(fn=>fn())
}
function subscribe(fn:()=>void){
  listeners.add(fn)
  return ()=>{listeners.delete(fn)}
}
const snapshot=()=>state

const errorText=(error:unknown,fallback:string)=>{
  const text=(typeof error==='string'?error:'').replace(/^[A-Z][A-Za-z]*(?:Error|Exception):\s*/,'').trim()
  return text||fallback
}

function watchEvents(){
  if(watching)return
  watching=onBackendEvent(event=>{
    if(event.kind!=='voice'||!state.requestId||event.requestId!==state.requestId)return
    const data=(event.data||{}) as {type?:string;message?:string}
    if(data.type==='speak_started')update({started:true})
    else if(data.type==='speak_done')update({speakingId:'',requestId:'',started:false})
    else if(data.type==='error')update({speakingId:'',requestId:'',started:false,errorId:state.speakingId,error:errorText(data.message,'The voice engine reported an error.')})
  })
}

/** Speak one reply; pressing it again on the reply that is speaking stops it. */
export async function readAloud(id:string,text:string){
  watchEvents()
  if(state.speakingId===id){await stopReading();return}
  const requestId=crypto.randomUUID()
  update({speakingId:id,requestId,started:false,errorId:'',error:''})
  const reply=await request('voiceSpeak',{text},requestId)
  if(!reply.ok&&state.requestId===requestId)
    update({speakingId:'',requestId:'',started:false,errorId:id,error:errorText(reply.error,'Read-aloud could not start.')})
}

export async function stopReading(){
  update({speakingId:'',requestId:'',started:false})
  await request('voiceStopSpeaking')
}

/** Settings calls this after saving, so the chat follows the switch without a reload. */
export function setAutoReadAloud(on:boolean){
  autoLoaded=true
  update({auto:on})
}

async function loadAuto(){
  if(autoLoaded||!isDesktop())return
  autoLoaded=true
  const reply=await request<{settings?:{read_aloud_auto?:boolean}}>('voiceGetSettings')
  if(reply.ok)update({auto:reply.data?.settings?.read_aloud_auto===true})
}

/** Rendered inside the live (streaming) answer: remembers when it finished. */
export function LiveAnswerMarker(){
  useEffect(()=>()=>{liveEndedAt=Date.now()},[])
  return null
}

/** For tests: forget everything between renders of a fresh app. */
export function resetReadAloud(){
  state={speakingId:'',requestId:'',started:false,errorId:'',error:'',auto:false}
  autoSpoken.clear()
  liveEndedAt=0
  autoLoaded=false
  watching?.()
  watching=null
}

export function useReadAloud(){
  return useSyncExternalStore(subscribe,snapshot,snapshot)
}

/**
 * The "Read aloud" action under one assistant reply. `newest` is true for the newest reply in the chat; with
 * automatic read-aloud on, it is read once if a live answer finished just before it appeared.
 */
export function ReadAloudButton({id,text,newest=false}:{id:string;text:string;newest?:boolean}){
  const read=useReadAloud()
  const autoTried=useRef(false)
  useEffect(()=>{void loadAuto()},[])
  useEffect(()=>{
    if(!newest||!read.auto||autoTried.current||autoSpoken.has(id)||!text.trim())return
    if(!liveEndedAt||Date.now()-liveEndedAt>LIVE_WINDOW_MS)return
    liveEndedAt=0
    autoTried.current=true
    autoSpoken.add(id)
    void readAloud(id,text)
  },[newest,read.auto,id,text])
  if(!isDesktop())return null
  const speaking=read.speakingId===id
  const failed=read.errorId===id&&read.error
  return <>
    <button type="button" className={'msg-action'+(speaking?' is-speaking':'')} aria-pressed={speaking}
      title={speaking?'Stop reading aloud':'Read this reply aloud in Star’s voice'} onClick={()=>void readAloud(id,text)}>
      {speaking?<Square size={12} fill="currentColor" aria-hidden="true"/>:<Volume2 size={14} aria-hidden="true"/>}
      <span>{speaking?(read.started?'Stop':'Starting…'):'Read aloud'}</span>
    </button>
    {failed&&<span className="msg-meta" role="alert">{read.error}</span>}
  </>
}
