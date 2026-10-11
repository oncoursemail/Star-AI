/**
 * Star's website appearances. The illustration assets are supplied separately by the project lead.
 * Until then, the original STAR mark and the reserved image frames keep the page visually complete.
 */
import {useEffect,useRef,useState} from 'react'
import type {ReactNode} from 'react'
import {StarConstruction,StarMark} from './SiteBrand'

const assets='./assets/mascot'
const faces=[
 {id:'normal',name:'Normal',alt:'Star with a calm, neutral expression'},
 {id:'happy',name:'Happy',alt:'Star smiling happily'},
 {id:'content',name:'Content',alt:'Star with a contented, eyes-closed smile'},
 {id:'puppy-eyes',name:'Puppy eyes',alt:'Star with a hopeful, puppy-eyed expression'},
 {id:'surprised',name:'Surprised',alt:'Star looking surprised'},
 {id:'thinking',name:'Thinking',alt:'Star pausing to think'},
 {id:'focused',name:'Focused',alt:'Star concentrating'},
 {id:'proud',name:'Proud',alt:'Star looking proud'}
] as const

type MascotArtProps={
 src:string
 alt:string
 width:number
 height:number
 className?:string
 fallback?:ReactNode
 onReady?:(ready:boolean)=>void
}

/** Image is invisible until loaded, including during hydration and after a failed request. */
function MascotArt({src,alt,width,height,className='',fallback,onReady}:MascotArtProps){
 const image=useRef<HTMLImageElement>(null)
 const [loaded,setLoaded]=useState(false)
 useEffect(()=>{
  // A prerendered image can finish loading before React attaches its load handler.
  if(image.current?.complete){
   const ready=image.current.naturalWidth>0
   setLoaded(ready)
   onReady?.(ready)
  }
 },[src,onReady])
 const ready=(value:boolean)=>{
  setLoaded(value)
  onReady?.(value)
 }
 return <span className={'sw-mascot-art '+className} data-loaded={loaded}>
  <span className="sw-mascot-fallback" aria-hidden="true">{fallback||<StarMark size={54}/>}</span>
  <img ref={image} src={src} width={width} height={height} alt={alt} loading="lazy" decoding="async"
   onLoad={()=>ready(true)} onError={()=>ready(false)}/>
 </span>
}

export function SiteMascotHero(){
 return <div className="sw-mascot-hero sw-enter">
  <MascotArt className="sw-mascot-hero-art" src={assets+'/star-hero.png'} width={1086} height={1448}
   alt="Star, STAR Intelligence's chibi mascot, in a black dress with gold accents"
   fallback={<span className="sw-mascot-placeholder"><StarConstruction/><span>STAR / MASCOT</span></span>}/>
  <div className="sw-mascot-hero-expression" aria-hidden="true">
   <MascotArt className="sw-mascot-hero-face" src={assets+'/faces/normal.png'} width={320} height={320}
    alt="Star's neutral expression"/>
   <MascotArt className="sw-mascot-hero-face sw-mascot-blink-alt" src={assets+'/faces/content.png'}
    width={320} height={320} alt="Star's content expression"/>
  </div>
 </div>
}

export function SiteMascotMeet(){
 return <section className="sw-meet" id="meet-star" aria-labelledby="sw-meet-title">
  <div className="sw-wrap">
   <div className="sw-meet-head">
    <p className="sw-kicker">A familiar face for the workbench</p>
    <h2 id="sw-meet-title">Meet Star.</h2>
    <p>Star is the little mascot of STAR Intelligence: curious, expressive and always ready to cheer on your next idea.
     She's a friendly face for the creative process; your projects and the decisions about them stay yours.</p>
   </div>
   <ul className="sw-mascot-faces" aria-label="Eight expressions of Star">
    {faces.map((face,index)=><li key={face.id}>
     <figure className="sw-mascot-face-card" tabIndex={0}>
      <MascotArt className="sw-mascot-tile-art" src={assets+'/faces/'+face.id+'.png'} width={320} height={320} alt={face.alt}/>
      <figcaption><span aria-hidden="true">{String(index+1).padStart(2,'0')}</span>{face.name}</figcaption>
     </figure>
    </li>)}
   </ul>
  </div>
 </section>
}

export function SiteMascotFooter(){
 const [canWave,setCanWave]=useState(false)
 return <div className="sw-footer-mascot" role="img" aria-label="Star the mascot waves hello on hover or keyboard focus"
  tabIndex={0} data-can-wave={canWave}>
  <span className="sw-footer-mascot-poses" aria-hidden="true">
   <MascotArt className="sw-footer-pose sw-footer-pose-stand" src={assets+'/poses/stand.png'}
    width={240} height={320} alt="Star standing"/>
   <MascotArt className="sw-footer-pose sw-footer-pose-wave" src={assets+'/poses/wave-a.png'}
    width={240} height={320} alt="Star waving" onReady={setCanWave}/>
  </span>
  <span className="sw-footer-mascot-caption" aria-hidden="true">Say hi to Star</span>
 </div>
}
