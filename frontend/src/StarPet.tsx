import {useEffect,useRef,useState} from 'react'
import './StarPet.css'

export type PetState='idle'|'typing'|'thinking'|'streaming'|'finished'|'error'|'cancelled'|'sleepy'|'asleep'|'update'
export type PetImage={face:string;pose:string;status:string}
export function petImage(state:PetState,alternate=false):PetImage {
 switch(state){
  case 'typing': return {face:'focused',pose:'stand',status:'I’m listening.'}
  case 'thinking': return {face:'thinking',pose:'think',status:'Thinking about your request…'}
  case 'streaming': return {face:'focused',pose:alternate?'type-2':'type-1',status:'Writing an answer…'}
  case 'finished': return {face:'happy',pose:'wave-a',status:'All done!'}
  case 'error': return {face:'nervous',pose:'stand',status:'Something went wrong.'}
  case 'cancelled': return {face:'surprised',pose:'stand',status:'Stopped that turn.'}
  case 'sleepy': return {face:'sleepy',pose:'sleep-sit',status:'Getting sleepy…'}
  case 'asleep': return {face:'asleep',pose:'sleep-sit',status:'Zzz…'}
  case 'update': return {face:'normal',pose:'letter',status:'An update is available!'}
  default: return {face:alternate?'content':'normal',pose:'stand',status:'Ready when you are.'}
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
 const [corner,setCorner]=useState<Corner>(savedCorner)
 const [bubble,setBubble]=useState(false)
 const [alternate,setAlternate]=useState(false)
 const [failed,setFailed]=useState(false)
 const origin=useRef<{x:number;y:number}|null>(null)
 const dragged=useRef(false)
 // Typing, in-flight work and terminal states all end the previous idle period.
 const idleMs=usePetIdleMs(visible&&idleEnabled&&state==='idle')
 const currentState:PetState=state==='idle'?(idleMs>=660000?'asleep':idleMs>=600000?'sleepy':'idle'):state
 useEffect(()=>{
  if(!visible||reducedMotion)return
  const delay=currentState==='idle'?4000:currentState==='streaming'?650:0
  if(!delay)return
  const timer=window.setInterval(()=>setAlternate(v=>!v),delay)
  return ()=>window.clearInterval(timer)
 },[currentState,visible,reducedMotion])
 const image=petImage(currentState,reducedMotion?false:alternate)
 const showPose=['streaming','thinking','sleepy','asleep','update'].includes(currentState)
 const source=showPose?'./mascot/poses/'+image.pose+'.png':'./mascot/faces/'+image.face+'.png'
 useEffect(()=>{setFailed(false)},[source])
 if(!visible||failed)return null
 return <div className={'star-pet star-pet--'+corner} data-testid="star-pet" data-state={currentState}>
  {bubble&&<div role="status" className="star-pet__bubble">{image.status}</div>}
  <button type="button" className="star-pet__button" aria-label="Star mascot" aria-expanded={bubble} title="Star" onPointerDown={event=>{
   origin.current={x:event.clientX,y:event.clientY};dragged.current=false
   event.currentTarget.setPointerCapture?.(event.pointerId)
  }} onPointerUp={event=>{
   const start=origin.current;origin.current=null
   dragged.current=!!start&&Math.hypot(event.clientX-start.x,event.clientY-start.y)>24
   if(dragged.current&&!reducedMotion){
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
   <img className="star-pet__image" src={source} alt="" draggable={false} onError={()=>setFailed(true)}/>
  </button>
 </div>
}
