import {startTransition,useCallback,useEffect,useRef,useState,useSyncExternalStore} from 'react'
import type {CSSProperties} from 'react'
import buildSnapshot from './progress.json'
import {
 FRESH_MS,RateLimitError,fetchLiveProgress,isFresh,newest,parseStoredProgress,
 readCachedProgress,readRetryAt,writeCachedProgress,writeRetryAt
} from './githubPublic'
import type {ProgressSnapshot} from './githubPublic'

/** `?visualqa` renders every final state immediately, for screenshots and audits. */
export const staticMode=()=>typeof window!=='undefined'&&new URLSearchParams(window.location.search).has('visualqa')
const prefersReducedMotion=()=>typeof window!=='undefined'&&window.matchMedia?.('(prefers-reduced-motion: reduce)').matches===true

/* ---------- progress data ---------- */

export type ProgressStatus=
 |{kind:'snapshot'}                       // last known data; no live answer yet
 |{kind:'loading'}                        // asking GitHub; last known data stays on screen
 |{kind:'live';partial:boolean}           // read from GitHub within the last few minutes
 |{kind:'limited';retryAt:number}         // GitHub's anonymous rate limit; showing last known data
 |{kind:'failed'}                         // could not reach GitHub; showing last known data
export type ProgressState={snapshot:ProgressSnapshot|null;status:ProgressStatus;refresh:()=>void}

/** The snapshot written at build time. Always present, so the page is never empty. */
export const builtSnapshot:ProgressSnapshot|null=parseStoredProgress(buildSnapshot as unknown,'build')

const MIN_MANUAL_GAP_MS=15_000

const noSubscription=()=>()=>undefined
/**
 * False while React is hydrating prerendered HTML, true afterwards (and always true without prerendering).
 * Anything that depends on the visitor's clock or time zone waits for it, so server and browser markup agree.
 */
export const useHydrated=()=>useSyncExternalStore(noSubscription,()=>true,()=>false)

export function useProgress():ProgressState{
 // The first render always uses the build-time snapshot, which is also what the prerendered HTML contains.
 const [snapshot,setSnapshotNow]=useState<ProgressSnapshot|null>(builtSnapshot)
 const [status,setStatusNow]=useState<ProgressStatus>({kind:'snapshot'})
 // Transitions let sections that are still hydrating finish first instead of being re-rendered from scratch.
 const snapshotRef=useRef<ProgressSnapshot|null>(builtSnapshot)
 const setSnapshot=useCallback((value:ProgressSnapshot|null)=>{
  snapshotRef.current=value
  startTransition(()=>setSnapshotNow(value))
 },[])
 const setStatus=useCallback((value:ProgressStatus)=>startTransition(()=>setStatusNow(value)),[])
 const busy=useRef(false)
 const lastAttempt=useRef(0)

 const load=useCallback((manual:boolean)=>{
  const now=Date.now()
  if(busy.current)return
  // A copy this browser read more recently than the site was built replaces the build-time snapshot.
  const cached=readCachedProgress()
  if(cached&&newest(snapshotRef.current,cached)===cached)setSnapshot(cached)
  const retryAt=readRetryAt(now)
  if(retryAt){setStatus({kind:'limited',retryAt});return}
  if(!manual&&isFresh(snapshotRef.current,now)){setStatus({kind:'live',partial:false});return}
  if(manual&&now-lastAttempt.current<MIN_MANUAL_GAP_MS)return
  busy.current=true
  lastAttempt.current=now
  setStatus({kind:'loading'})
  fetchLiveProgress().then(result=>{
   // A partial answer never replaces a complete last-known state; it would make open work look finished.
   if(!result.partial||!snapshotRef.current){
    writeCachedProgress(result)
    setSnapshot(result.snapshot)
    setStatus({kind:'live',partial:result.partial})
   }else setStatus({kind:'failed'})
  }).catch((error:unknown)=>{
   if(error instanceof RateLimitError){writeRetryAt(error.retryAt);setStatus({kind:'limited',retryAt:error.retryAt})}
   else setStatus({kind:'failed'})
  }).finally(()=>{busy.current=false})
 },[setSnapshot,setStatus])

 useEffect(()=>{
  if(staticMode()){return}
  // Wait for the first paint, then ask GitHub. The page already shows the build-time snapshot.
  const canIdle='requestIdleCallback' in window
  const idle=canIdle
   ?window.requestIdleCallback(()=>load(false),{timeout:2500})
   :window.setTimeout(()=>load(false),1200)
  const onVisible=()=>{if(document.visibilityState==='visible')load(false)}
  document.addEventListener('visibilitychange',onVisible)
  // An open tab re-checks on its own, so the board follows the repository without a reload.
  const timer=window.setInterval(()=>{if(document.visibilityState==='visible')load(false)},FRESH_MS)
  return ()=>{
   if(canIdle)window.cancelIdleCallback(idle)
   else window.clearTimeout(idle)
   document.removeEventListener('visibilitychange',onVisible)
   window.clearInterval(timer)
  }
 },[load])

 const refresh=useCallback(()=>load(true),[load])
 return {snapshot,status,refresh}
}

/* ---------- motion ---------- */

/**
 * One-shot section reveals. Content is visible by default: only elements that are still below the fold when the
 * page starts are held back, and each is released once by an IntersectionObserver. Reduced motion, `?visualqa`
 * and browsers without the observer skip the effect entirely.
 */
export function useReveal(rootRef:{current:HTMLElement|null}){
 useEffect(()=>{
  const root=rootRef.current
  if(!root||staticMode()||prefersReducedMotion()||!('IntersectionObserver' in window))return
  const fold=window.innerHeight*.94
  const pending=Array.from(root.querySelectorAll<HTMLElement>('[data-reveal]')).filter(element=>element.getBoundingClientRect().top>fold)
  if(!pending.length)return
  const release=(element:Element)=>{element.classList.remove('sw-pre');element.classList.add('sw-in')}
  const observer=new IntersectionObserver(entries=>{
   for(const entry of entries){
    if(entry.isIntersecting){release(entry.target);observer.unobserve(entry.target)}
   }
  },{rootMargin:'0px 0px -6% 0px',threshold:.06})
  pending.forEach(element=>{element.classList.add('sw-pre');observer.observe(element)})
  return ()=>{observer.disconnect();pending.forEach(element=>element.classList.remove('sw-pre'))}
 },[rootRef])
}

/**
 * Header state: `solid` once the page has moved, `hidden` while scrolling down so the content keeps the viewport,
 * `past` once the hero and its primary button are out of view.
 */
export function useHeaderState(locked:boolean){
 const [state,setState]=useState({solid:false,hidden:false,past:false})
 useEffect(()=>{
  let last=window.scrollY
  let frame=0
  const update=()=>{
   frame=0
   const y=window.scrollY
   const delta=y-last
   setState(previous=>{
    const solid=y>8
    const past=y>Math.min(520,window.innerHeight*.7)
    const hidden=locked?false:y<280?false:delta>6?true:delta<-6?false:previous.hidden
    return solid===previous.solid&&hidden===previous.hidden&&past===previous.past?previous:{solid,hidden,past}
   })
   if(Math.abs(delta)>6)last=y
  }
  const onScroll=()=>{if(!frame)frame=window.requestAnimationFrame(update)}
  update()
  window.addEventListener('scroll',onScroll,{passive:true})
  return ()=>{window.removeEventListener('scroll',onScroll);if(frame)window.cancelAnimationFrame(frame)}
 },[locked])
 return state
}

/** Which page section is under the middle of the viewport, for `aria-current` in the navigation. */
export function useActiveSection(ids:readonly string[]){
 const [active,setActive]=useState<string|null>(null)
 useEffect(()=>{
  if(!('IntersectionObserver' in window))return
  const observer=new IntersectionObserver(entries=>{
   for(const entry of entries){
    if(entry.isIntersecting)setActive(entry.target.id)
   }
  },{rootMargin:'-45% 0px -50% 0px'})
  ids.forEach(id=>{const element=document.getElementById(id);if(element)observer.observe(element)})
  return ()=>observer.disconnect()
 },[ids])
 return active
}

/** Stagger for entrance and reveal animations, read by CSS as `animation-delay`. */
export const delay=(ms:number)=>({'--sw-d':ms+'ms'}) as CSSProperties
