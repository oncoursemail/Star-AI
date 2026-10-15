/**
 * Star, the mascot, on the public site. Owner-approved art only (frontend/public/assets/mascot, resized copies in
 * frontend/public/site).
 *
 * Motion in the hero has one job: say that STAR is a character, not a logo. She rises in once when the page opens,
 * floats slowly, the star in her hand glints now and then, she leans toward the pointer on a spring, and she hops
 * when you press her. Reduced motion, touch-only pointers and `?visualqa` keep her still.
 */
import {useEffect,useRef,useState} from 'react'
import type {ReactNode} from 'react'
import {motion,useSpring} from 'motion/react'
import {StarMark} from './SiteBrand'
import {staticMode} from './siteHooks'

/** The one shipped copy of the approved art; the page asks for resized webp copies of it in ./site via srcSet, and the
 * original stays the `src` fallback for browsers without srcset (tests/test_mascot_assets.py checks both). */
const assets='./assets/mascot'
const site='./site'

type MascotArtProps={src:string;srcSet?:string;sizes?:string;alt:string;width:number;height:number;className?:string;
 eager?:boolean;fallback?:ReactNode;onReady?:(ready:boolean)=>void}

/** Image is invisible until loaded, including during hydration and after a failed request. */
function MascotArt({src,srcSet,sizes,alt,width,height,className='',eager=false,fallback,onReady}:MascotArtProps){
 const image=useRef<HTMLImageElement>(null)
 // The eager hero art is visible from the first paint (prerendered); lazy art waits until it has loaded.
 const [loaded,setLoaded]=useState(eager)
 useEffect(()=>{
  // A prerendered image can finish loading before React attaches its load handler.
  if(image.current?.complete){
   const ready=image.current.naturalWidth>0
   setLoaded(ready)
   onReady?.(ready)
  }
 },[src,onReady])
 const ready=(value:boolean)=>{setLoaded(value);onReady?.(value)}
 return <span className={'sw-art '+className} data-loaded={loaded}>
  <span className="sw-art-fallback" aria-hidden="true">{fallback||<StarMark size={54}/>}</span>
  <img ref={image} src={src} srcSet={srcSet} sizes={sizes} width={width} height={height} alt={alt}
   loading={eager?'eager':'lazy'} decoding="async"
   onLoad={()=>ready(true)} onError={()=>ready(false)}/>
 </span>
}

/** A four-ray glint in the brand's star shape. Purely decorative. */
function Glint({className}:{className:string}){
 return <svg className={'sw-glint '+className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
  <path d="M12 0c.7 6.2 5.1 10.6 12 12-6.9 1.4-11.3 5.8-12 12-.7-6.2-5.1-10.6-12-12C6.9 10.6 11.3 6.2 12 0Z"/>
 </svg>
}

const reducedMotion=()=>typeof window!=='undefined'&&window.matchMedia?.('(prefers-reduced-motion: reduce)').matches===true
const finePointer=()=>typeof window!=='undefined'&&window.matchMedia?.('(hover: hover) and (pointer: fine)').matches===true

export function SiteMascotHero(){
 const root=useRef<HTMLDivElement>(null)
 const body=useRef<HTMLSpanElement>(null)
 const spring={stiffness:110,damping:15,mass:.7}
 const x=useSpring(0,spring)
 const y=useSpring(0,spring)
 const rotate=useSpring(0,spring)
 useEffect(()=>{
  if(staticMode()||reducedMotion()||!finePointer())return
  let frame=0
  const onMove=(event:PointerEvent)=>{
   cancelAnimationFrame(frame)
   frame=requestAnimationFrame(()=>{
    const box=root.current?.getBoundingClientRect()
    if(!box||box.bottom<0||box.top>window.innerHeight)return
    const clamp=(value:number)=>Math.max(-1,Math.min(1,value))
    const dx=clamp((event.clientX-(box.left+box.width/2))/(window.innerWidth/2))
    const dy=clamp((event.clientY-(box.top+box.height/2))/(window.innerHeight/2))
    x.set(dx*10);y.set(dy*6);rotate.set(dx*3)
   })
  }
  const settle=()=>{x.set(0);y.set(0);rotate.set(0)}
  window.addEventListener('pointermove',onMove,{passive:true})
  document.documentElement.addEventListener('pointerleave',settle)
  return ()=>{cancelAnimationFrame(frame);window.removeEventListener('pointermove',onMove);document.documentElement.removeEventListener('pointerleave',settle)}
 },[x,y,rotate])
 // Her loops pause while she is off screen: no work for motion nobody can see.
 useEffect(()=>{
  const node=root.current
  if(!node||!('IntersectionObserver' in window))return
  const observer=new IntersectionObserver(([entry])=>{
   if(entry.isIntersecting)node.removeAttribute('data-paused')
   else node.setAttribute('data-paused','')
  })
  observer.observe(node)
  return ()=>observer.disconnect()
 },[])
 // A press is a rare, playful moment, so it may be a little springy. Ignored while a hop is still running.
 const hop=()=>{
  const node=body.current
  if(!node||staticMode()||reducedMotion()||node.getAnimations().some(animation=>animation.id==='hop'))return
  const animation=node.animate([
   {transform:'translateY(0) scale(1,1)'},
   {transform:'translateY(2px) scale(1.03,.97)',offset:.18},
   {transform:'translateY(-18px) scale(.98,1.02)',offset:.55},
   {transform:'translateY(0) scale(1,1)'}
  ],{duration:520,easing:'cubic-bezier(.23,1,.32,1)'})
  animation.id='hop'
  root.current?.setAttribute('data-hop','')
  animation.onfinish=()=>root.current?.removeAttribute('data-hop')
 }
 return <div className="sw-star" ref={root} onPointerDown={hop}>
  <span className="sw-star-halo" aria-hidden="true"/>
  <Glint className="sw-glint-a"/><Glint className="sw-glint-b"/><Glint className="sw-glint-c"/>
  <motion.span className="sw-star-lean" style={{x,y,rotate}}>
   <span className="sw-star-float">
    <span className="sw-star-body" ref={body}>
     <MascotArt className="sw-star-art" eager src={assets+'/star-hero.png'}
      srcSet={site+'/star-hero-480.webp 480w, '+site+'/star-hero-900.webp 900w'}
      sizes="(max-width: 860px) 80vw, 450px" width={900} height={1200}
      alt="Star, STAR's mascot: a cheerful chibi girl in a black dress with gold bows, holding up a small glowing star"/>
     <Glint className="sw-glint-hand"/>
    </span>
   </span>
  </motion.span>
  <span className="sw-star-shadow" aria-hidden="true"/>
 </div>
}

export function SiteMascotFooter(){
 const [canWave,setCanWave]=useState(false)
 return <div className="sw-footer-star" role="img" aria-label="Star waves hello on hover or keyboard focus"
  tabIndex={0} data-can-wave={canWave}>
  <span className="sw-footer-star-poses" aria-hidden="true">
   <MascotArt className="sw-footer-pose sw-footer-pose-stand" src={assets+'/poses/stand.png'} srcSet={site+'/pose-stand.webp 160w'} sizes="64px" width={160} height={200} alt="Star standing"/>
   <MascotArt className="sw-footer-pose sw-footer-pose-wave" src={assets+'/poses/wave-a.png'} srcSet={site+'/pose-wave-a.webp 160w'} sizes="64px" width={160} height={200} alt="Star waving" onReady={setCanWave}/>
  </span>
 </div>
}
