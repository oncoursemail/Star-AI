import {useEffect,useState} from 'react'
import type {CSSProperties} from 'react'
import buildSnapshot from './progress.json'
import {parseStoredProgress} from './githubPublic'
import type {ProgressSnapshot} from './githubPublic'

/** `?visualqa` renders every final state immediately, for screenshots and audits. */
export const staticMode=()=>typeof window!=='undefined'&&new URLSearchParams(window.location.search).has('visualqa')
const prefersReducedMotion=()=>typeof window!=='undefined'&&window.matchMedia?.('(prefers-reduced-motion: reduce)').matches===true

/* ---------- release data ---------- */

/**
 * The public repository snapshot written at build time (scripts/build-progress.mjs). The page reads only its latest
 * stable release, so the download section is complete before any network request; Landing then asks GitHub for the
 * latest release directly.
 */
export const builtSnapshot:ProgressSnapshot|null=parseStoredProgress(buildSnapshot as unknown,'build')

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
