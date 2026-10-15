/**
 * First contract for STAR's future multi-agent companion stage.
 * Pure and render-agnostic: it never invents an agent run, a tool success,
 * a relationship, speech, or a recording. Existing StarPet remains unchanged.
 */
export type WorkPhase='idle'|'thinking'|'tool'|'speaking'|'finished'|'failed'
export type AnimalForm='human'|'cat'|'dog'
export type CompanionEvent={
  actorId:string
  runId:string
  sequence:number
  at:number
  phase:Exclude<WorkPhase,'idle'>
}
export type CompanionState={
  actorId:string
  runId:string
  sequence:number
  phase:WorkPhase
  lastChangedAt:number
  form:AnimalForm
}
export type SceneAction='wave'|'tag'|'high-five'|'hug'|'kiss'
export type CompanionScene={actorId:string;partnerId:string;action:SceneAction}

const phaseMap:Readonly<Record<CompanionEvent['phase'],WorkPhase>>={
  thinking:'thinking',tool:'tool',speaking:'speaking',
  finished:'finished',failed:'failed'
}
const done=new Set<WorkPhase>(['finished','failed'])
export const initialCompanion=(actorId:string,at=0):CompanionState=>({
  actorId,runId:'',sequence:-1,phase:'idle',lastChangedAt:at,form:'human'
})

/** Apply only events emitted by an actual STAR agent run. Ignore duplicate and out-of-order data. */
export function applyCompanionEvent(state:CompanionState,event:CompanionEvent):CompanionState {
  if(state.actorId!==event.actorId||!event.runId||!Number.isSafeInteger(event.sequence)||
     event.sequence<0||!Number.isFinite(event.at))return state
  if(state.runId===event.runId&&event.sequence<=state.sequence)return state
  if(state.runId!==event.runId&&state.phase!=='idle'&&!done.has(state.phase))return state
  return {...state,runId:event.runId,sequence:event.sequence,
    phase:phaseMap[event.phase],lastChangedAt:Math.max(state.lastChangedAt,event.at)}
}

/** No automatic animal transformation. The owner chooses it explicitly. */
export function setAnimalForm(state:CompanionState,form:AnimalForm,approved:boolean):CompanionState{
 if(!approved||!(['human','cat','dog'] as const).includes(form))return state
 return {...state,form}
}

/**
 * Decorative, clearly non-agent activity. No motion when reduced-motion is on,
 * the owner is working, a character is not idle, or idle time is too short.
 * The director returns a deterministic scene idea, not animation assets.
 */
export function chooseCompanionScene(
  states:ReadonlyArray<CompanionState>,
  options:{enabled:boolean;affection:boolean;romance:boolean;reducedMotion:boolean;now:number}
):CompanionScene|null {
 if(!options.enabled||options.reducedMotion||!Number.isFinite(options.now))return null
 const available=states.filter(s=>s.phase==='idle'&&options.now-s.lastChangedAt>=45000)
 if(available.length<2||available.length!==states.length)return null
 const sorted=[...available].sort((a,b)=>a.actorId.localeCompare(b.actorId))
 const turn=Math.floor(options.now/60000)
 const from=sorted[turn%sorted.length],to=sorted[(turn+1)%sorted.length]
 const actions:SceneAction[]=['wave','tag','high-five']
 if(options.affection)actions.push('hug')
 if(options.romance&&options.affection)actions.push('kiss')
 return {actorId:from.actorId,partnerId:to.actorId,action:actions[turn%actions.length]}
}
