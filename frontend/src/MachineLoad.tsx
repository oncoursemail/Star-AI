import {useEffect,useState} from 'react'
import {request} from './bridge'

export type PlannerMachine = {
 name:string
 cpu:number
 memFreeGiB:number
 memTotalGiB:number
 ageSeconds:number
 chatActive:boolean
 ownerBusy:string
 quietLock:string
 gpu:number|null
 studios:number
 slots:Record<string,{busy:number;total:number}>
}
export type PlannerJob = {jobClass:string;holder:string;machine:string;seconds?:number}
export type PlannerSnapshot = {available:boolean;reason?:string;machines?:PlannerMachine[];jobs?:PlannerJob[];queue?:PlannerJob[]}

const LABELS:Record<string,string>={brain1:'Brain 1 (main models)',brain2:'Brain 2 (Studio + CPU work)',pc:'This PC (GPU)'}
const pct=(x:number)=>`${Math.round(Math.max(0,Math.min(1,x))*100)}%`

function Machine({m}:{m:PlannerMachine}) {
 const slots=Object.entries(m.slots).map(([model,s])=>`${model} ${s.busy}/${s.total}`)
 const notes=[m.chatActive?'chat active':'',m.ownerBusy?`owner busy: ${m.ownerBusy}`:'',m.quietLock?`quiet lock: ${m.quietLock}`:'',
  m.studios?`${m.studios} Studio attached`:'',m.gpu!==null?`GPU ${pct(m.gpu)}`:'',m.ageSeconds>60?`data ${Math.round(m.ageSeconds)} s old`:''].filter(Boolean)
 return <section className="machine-load-card" aria-label={LABELS[m.name]||m.name}>
  <h3>{LABELS[m.name]||m.name}</h3>
  <div className="machine-load-meter" role="meter" aria-label={`CPU ${m.name}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(m.cpu*100)}>
   <span style={{width:pct(m.cpu)}}/>
  </div>
  <p>CPU {pct(m.cpu)} · RAM free {m.memFreeGiB}/{m.memTotalGiB} GiB</p>
  {slots.length>0&&<p>Slots busy: {slots.join(', ')}</p>}
  {notes.length>0&&<p className="machine-load-notes">{notes.join(' · ')}</p>}
 </section>
}

export function MachineLoad({snapshot,load=true}:{snapshot?:PlannerSnapshot;load?:boolean}) {
 const [data,setData]=useState<PlannerSnapshot|null>(snapshot||null)
 useEffect(()=>{
  if(!load)return
  let active=true
  const ask=()=>void request<PlannerSnapshot>('plannerStatus').then(result=>{if(active)setData(result.ok&&result.data?result.data:{available:false})})
  ask()
  const timer=window.setInterval(ask,15000)
  return ()=>{active=false;window.clearInterval(timer)}
 },[load])
 if(!data)return null
 if(!data.available)return <section className="machine-load" aria-label="Machines and jobs"><h3>Machines and jobs</h3><p className="machine-load-off">Resource planner not reachable{data.reason?` (${data.reason})`:''}.</p></section>
 const jobs=data.jobs||[]
 const queue=data.queue||[]
 return <section className="machine-load" aria-label="Machines and jobs">
  <h3>Machines and jobs</h3>
  <div className="machine-load-grid">{(data.machines||[]).map(m=><Machine key={m.name} m={m}/>)}</div>
  <p>Running: {jobs.length?jobs.map(j=>`${j.jobClass} on ${j.machine}`).join(', '):'nothing'}</p>
  <p>Waiting: {queue.length?queue.map(j=>`${j.jobClass} for ${j.machine}`).join(', '):'nothing'}</p>
 </section>
}
