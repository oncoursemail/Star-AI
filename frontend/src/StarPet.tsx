import {useEffect,useRef,useState} from 'react'
import './StarPet.css'
import {useEffectiveReducedMotion} from './MotionPolicy'

/** The one shipped copy of the art (frontend/public/assets/mascot); relative so the packaged app can load it from a local file. */
const assets='./assets/mascot'
export type PetState='idle'|'typing'|'thinking'|'streaming'|'finished'|'error'|'cancelled'|'sleepy'|'asleep'|'update'
export type PetImage={face:string;pose:string;status:string}
/** All displayed art uses approved full-body poses sharing a 600px foot baseline. */
const poses=['stand','blink','breathe-out','look-a','think','wave-a','wave-b','jump','sad','sleep-sit','sleep-lie','letter'] as const
export function petPosePath(pose:unknown):string {
 const safe=typeof pose==='string'&&(poses as readonly string[]).includes(pose)?pose:'stand'
 return assets+'/poses/'+safe+'.png'
}
export function petImage(state:PetState,alternate=false):PetImage {
 switch(state){
  case 'typing': return {face:'focused',pose:'look-a',status:'I’m listening.'}
  case 'thinking': return {face:'thinking',pose:'think',status:'Thinking about your request…'}
  case 'streaming': return {face:'focused',pose:'think',status:'Writing an answer…'}
  case 'finished': return {face:'happy',pose:'jump',status:'All done!'}
  case 'error': return {face:'nervous',pose:'sad',status:'Something went wrong.'}
  case 'cancelled': return {face:'surprised',pose:'stand',status:'Stopped that turn.'}
  case 'sleepy': return {face:'sleepy',pose:'sleep-sit',status:'Getting sleepy…'}
  case 'asleep': return {face:'asleep',pose:'sleep-lie',status:'Zzz…'}
  case 'update': return {face:'normal',pose:'letter',status:'An update is available!'}
  default: return {face:alternate?'content':'normal',pose:alternate?'blink':'stand',status:'Ready when you are.'}
 }
}

/** The pet owns its clock; ticking must not re-render the whole Desktop. */
export function usePetIdleMs(active:boolean):number {
 const [idleMs,setIdleMs]=useState(0)
 useEffect(()=>{
  setIdleMs(0)
  if(!active)return
  const activity=()=>setIdleMs(0)
  window.addEventListener('pointerdown',activity);window.addEventListener('keydown',activity)
  const timer=window.setInterval(()=>setIdleMs(ms=>Math.min(700000,ms+30000)),30000)
  return ()=>{window.removeEventListener('pointerdown',activity);window.removeEventListener('keydown',activity);window.clearInterval(timer)}
 },[active])
 return idleMs
}

type Corner='bottom-right'|'bottom-left'|'top-right'|'top-left'
const corners:Corner[]=['bottom-right','bottom-left','top-right','top-left']
function savedCorner():Corner {
 try {const value=localStorage.getItem('star.pet.corner');return corners.includes(value as Corner)?value as Corner:'bottom-right'}catch{return 'bottom-right'}
}
export function StarPet({state,visible=true,reducedMotion=false,idleEnabled=true}:{state:PetState;visible?:boolean;reducedMotion?:boolean;idleEnabled?:boolean}) {
 const motionOff=useEffectiveReducedMotion(reducedMotion)
 const [corner,setCorner]=useState<Corner>(savedCorner)
 const [bubble,setBubble]=useState(false)
 const [failed,setFailed]=useState(false)
 const [previous,setPrevious]=useState<string|null>(null)
 const [greeting,setGreeting]=useState(()=>visible&&state==='idle'&&!motionOff)
 const origin=useRef<{x:number;y:number}|null>(null)
 const dragged=useRef(false)
 const wasVisible=useRef(visible)
 // Typing, in-flight work and terminal states all end the previous idle period.
 const idleMs=usePetIdleMs(visible&&idleEnabled&&state==='idle')
 const currentState:PetState=state==='idle'?(idleMs>=660000?'asleep':idleMs>=600000?'sleepy':'idle'):state
 const image=petImage(currentState)
 const source=petPosePath(image.pose)
 const visualKey=source+'|'+image.face
 const displayed=useRef({key:visualKey,src:source})
 // Remember the outgoing sprite only for a 230ms transition; no idle JS animation loop.
 useEffect(()=>{
  const old=displayed.current
  displayed.current={key:visualKey,src:source}
  if(!visible||motionOff){setPrevious(null);return}
  if(old.key===visualKey)return
  setPrevious(old.src)
  const timer=window.setTimeout(()=>setPrevious(null),230)
  return ()=>window.clearTimeout(timer)
 },[visualKey,source,visible,motionOff])
 // One welcome wave when the chat opens, never a repeating timer.
 useEffect(()=>{
  if(visible&&!wasVisible.current&&currentState==='idle'&&!motionOff)setGreeting(true)
  wasVisible.current=visible
 },[visible,currentState,motionOff])
 useEffect(()=>{
  if(!greeting)return
  if(!visible||motionOff||currentState!=='idle'){setGreeting(false);return}
  const timer=window.setTimeout(()=>setGreeting(false),980)
  return ()=>window.clearTimeout(timer)
 },[greeting,currentState,visible,motionOff])
 useEffect(()=>{setFailed(false)},[source])
 if(!visible||failed)return null
 const idlePose=currentState==='idle'
 return <div className={'star-pet star-pet--'+corner+(idlePose?' star-pet--idle':'')} data-testid="star-pet" data-state={currentState} data-face={image.face} data-motion={motionOff?'off':'on'} data-greeting={greeting&&idlePose&&!motionOff}>
  {bubble&&<div role="status" className="star-pet__bubble">{image.status}</div>}
  <button type="button" className="star-pet__button" aria-label="Star mascot" aria-expanded={bubble} title="Star" onPointerDown={event=>{
   origin.current={x:event.clientX,y:event.clientY};dragged.current=false
   event.currentTarget.setPointerCapture?.(event.pointerId)
  }} onPointerUp={event=>{
   const start=origin.current;origin.current=null
   dragged.current=!!start&&Math.hypot(event.clientX-start.x,event.clientY-start.y)>24
   if(dragged.current&&!motionOff){
    const next:Corner=(event.clientY<window.innerHeight/2?'top':'bottom')+'-'+(event.clientX<window.innerWidth/2?'left':'right') as Corner
    setCorner(next)
    try{localStorage.setItem('star.pet.corner',next)}catch{/* optional preference */}
   }
  }} onPointerCancel={()=>{origin.current=null;dragged.current=false}} onClick={event=>{
   // Keyboard/assistive activation has detail 0 and must never be swallowed by a previous drag.
   const skip=dragged.current&&event.detail!==0
   dragged.current=false
   if(!skip)setBubble(v=>!v)
  }}>
   <span className="star-pet__body" aria-hidden="true">
    {previous&&!motionOff&&<img className="star-pet__image star-pet__image--previous" src={previous} alt="" draggable={false}/>}
    <img key={visualKey} className={'star-pet__image star-pet__image--current'+(motionOff?'':' is-animated')} src={source} alt="" draggable={false} onError={()=>setFailed(true)}/>
    {idlePose&&!motionOff&&!greeting&&<>
     <img className="star-pet__image star-pet__exhale" src={petPosePath('breathe-out')} alt="" draggable={false}/>
     <img className="star-pet__image star-pet__blink" src={petPosePath(petImage('idle',true).pose)} alt="" draggable={false}/>
    </>}
    {greeting&&idlePose&&!motionOff&&<>
     <img className="star-pet__image star-pet__wave--a" src={petPosePath('wave-a')} alt="" draggable={false} onError={()=>setGreeting(false)}/>
     <img className="star-pet__image star-pet__wave--b" src={petPosePath('wave-b')} alt="" draggable={false} onError={()=>setGreeting(false)}/>
    </>}
   </span>
  </button>
 </div>
}
