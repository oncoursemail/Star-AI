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

type Corner='bottom-right'|'bottom-left'|'top-right'|'top-left'
const corners:Corner[]=['bottom-right','bottom-left','top-right','top-left']
function savedCorner():Corner {
 try {const value=localStorage.getItem('star.pet.corner');return corners.includes(value as Corner)?value as Corner:'bottom-right'}catch{return 'bottom-right'}
}
export function StarPet({state,visible=true,reducedMotion=false}:{state:PetState;visible?:boolean;reducedMotion?:boolean}) {
 const [corner,setCorner]=useState<Corner>(savedCorner)
 const [bubble,setBubble]=useState(false)
 const [alternate,setAlternate]=useState(false)
 const [failed,setFailed]=useState(false)
 const origin=useRef<{x:number;y:number}|null>(null)
 useEffect(()=>{
  if(reducedMotion)return
  const delay=state==='idle'?4000:state==='streaming'?650:0
  if(!delay)return
  const timer=setInterval(()=>setAlternate(v=>!v),delay)
  return ()=>clearInterval(timer)
 },[state,reducedMotion])
 const image=petImage(state,reducedMotion?false:alternate)
 const showPose=['streaming','thinking','sleepy','asleep','update'].includes(state)
 const source=showPose?'/mascot/poses/'+image.pose+'.png':'/mascot/faces/'+image.face+'.png'
 useEffect(()=>{setFailed(false)},[source])
 if(!visible||failed)return null
 return <div className={'star-pet star-pet--'+corner} data-testid="star-pet" data-state={state}>
  {bubble&&<div role="status" className="star-pet__bubble">{image.status}</div>}
  <button type="button" className="star-pet__button" aria-label="Star mascot" title="Star" onPointerDown={event=>{origin.current={x:event.clientX,y:event.clientY}}} onPointerUp={event=>{
   const start=origin.current;origin.current=null
   if(start&&Math.hypot(event.clientX-start.x,event.clientY-start.y)>24&&!reducedMotion){
    const next:Corner=(event.clientY<window.innerHeight/2?'top':'bottom')+'-'+(event.clientX<window.innerWidth/2?'left':'right') as Corner
    setCorner(next)
    try{localStorage.setItem('star.pet.corner',next)}catch{/* optional preference */}
   }else setBubble(v=>!v)
  }}>
   <img className="star-pet__image" src={source} alt="" draggable={false} onError={()=>setFailed(true)}/>
  </button>
 </div>
}
