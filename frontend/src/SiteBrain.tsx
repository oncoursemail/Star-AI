/**
 * "STAR's brain": STAR's code structure as Graphify maps it, and how it grew from release to release.
 *
 * The map is data from scripts/build_brain_graph.py (frontend/src/brainGraph.json, a precomputed force-directed
 * layout of the most connected files). The page first shows the static SVG of the same layout; the interactive canvas
 * and its data load only when the section comes near the viewport. Hover (or touch) names a file and lights up its
 * links. Dots glow and drift slowly while the map is on screen; reduced motion shows it still. Nothing here calls
 * the network.
 */
import {useEffect,useRef,useState} from 'react'
import type {CSSProperties,PointerEvent as ReactPointerEvent} from 'react'
import {ArrowUpRight} from 'lucide-react'
import {LINKS,brainCounts,formatDate} from './siteContent'
import {staticMode} from './siteHooks'
import summary from './brainSummary.json'

type BrainData={generatedAt:string;current:{version:string;commit:string;nodes:number;edges:number;files:number;communities:number}
 areas:{id:string;label:string;color:string;files:number}[];shown:{files:number;links:number}
 nodes:{f:string;a:number;s:number;x:number;y:number}[];links:[number,number,number][]
 history:{version:string;nodes:number;edges:number;files:number;communities:number;commit:string}[]}

const ASPECT=1000/640
const radius=(symbols:number)=>Math.min(2+Math.sqrt(symbols)*.75,13)
const number=(value:number)=>value.toLocaleString('en')

/** A soft round glow in one colour, drawn once and stamped behind every dot of that colour. */
function glowSprite(color:string){
 const sprite=document.createElement('canvas')
 sprite.width=sprite.height=64
 const context=sprite.getContext('2d')
 if(context){
  const gradient=context.createRadialGradient(32,32,0,32,32,32)
  gradient.addColorStop(0,color+'99');gradient.addColorStop(.35,color+'33');gradient.addColorStop(1,color+'00')
  context.fillStyle=gradient;context.fillRect(0,0,64,64)
 }
 return sprite
}
const HOT='#FFD98A'

function BrainCanvas({data}:{data:BrainData}){
 const canvas=useRef<HTMLCanvasElement>(null)
 const box=useRef<HTMLDivElement>(null)
 const [hover,setHover]=useState<number|null>(null)
 const [size,setSize]=useState({w:0,h:0})
 const progress=useRef(1)
 // The animation loop reads these, so a frame never draws with a stale hover or size.
 const live=useRef({hover:null as number|null,size:{w:0,h:0},time:0,drift:0})
 live.current.hover=hover;live.current.size=size
 const neighbours=useRef<Map<number,Set<number>>>(new Map())
 if(!neighbours.current.size){
  for(const [a,b] of data.links){
   if(!neighbours.current.has(a))neighbours.current.set(a,new Set())
   if(!neighbours.current.has(b))neighbours.current.set(b,new Set())
   neighbours.current.get(a)!.add(b);neighbours.current.get(b)!.add(a)
  }
 }
 const sprites=useRef<HTMLCanvasElement[]|null>(null)
 useEffect(()=>{
  const node=box.current
  if(!node)return
  const observer=new ResizeObserver(([entry])=>setSize({w:entry.contentRect.width,h:entry.contentRect.height||entry.contentRect.width/ASPECT}))
  observer.observe(node)
  return ()=>observer.disconnect()
 },[])
 const point=(index:number,w:number,h:number,t:number)=>{
  const node=data.nodes[index]
  const pad=Math.max(14,w*.028)
  // Settle-in: every file starts at the centre of the map and eases out to its place.
  const x=pad+node.x*(w-2*pad),y=pad+node.y*(h-2*pad)
  return [w/2+(x-w/2)*t,h/2+(y-h/2)*t] as const
 }
 const draw=()=>{
  const element=canvas.current
  const {hover,size,time,drift}=live.current
  if(!element||!size.w)return
  const ratio=Math.min(window.devicePixelRatio||1,2)
  const width=Math.round(size.w*ratio),height=Math.round(size.h*ratio)
  if(element.width!==width||element.height!==height){element.width=width;element.height=height}
  const context=element.getContext('2d')
  if(!context)return
  if(!sprites.current)sprites.current=data.areas.map(area=>glowSprite(area.color))
  context.setTransform(ratio,0,0,ratio,0,0)
  context.clearRect(0,0,size.w,size.h)
  const t=1-Math.pow(1-progress.current,3)
  const lit=hover===null?null:neighbours.current.get(hover)||new Set<number>()
  const scale=Math.max(.7,Math.min(1.15,size.w/900))
  // Each dot drifts a few pixels on its own slow loop (amplitude 0 when motion is off).
  const at=data.nodes.map((_,index)=>{
   const [x,y]=point(index,size.w,size.h,t)
   if(!drift)return [x,y]
   const phase=index*2.399
   return [x+Math.sin(time*(.21+(index%7)*.023)+phase)*drift,y+Math.cos(time*(.17+(index%5)*.029)+phase*1.7)*drift]
  })
  // Links: a wide faint stroke under a thin bright one, added together so crossings glow.
  context.globalCompositeOperation='lighter'
  context.lineCap='round'
  const byArea=data.areas.map(()=>new Path2D())
  const hot=new Path2D()
  for(const [a,b] of data.links){
   const target=hover!==null&&(a===hover||b===hover)?hot:byArea[data.nodes[a].a]
   target.moveTo(at[a][0],at[a][1]);target.lineTo(at[b][0],at[b][1])
  }
  const quiet=hover!==null
  // Small maps pack the same links into less space, so each one is fainter there or the core turns white.
  const dense=Math.max(.5,Math.min(1,size.w/1000))
  data.areas.forEach((area,index)=>{
   context.strokeStyle=area.color
   context.globalAlpha=(quiet?.025:.07)*dense;context.lineWidth=3.2;context.stroke(byArea[index])
   context.globalAlpha=(quiet?.06:.3)*dense;context.lineWidth=1;context.stroke(byArea[index])
  })
  if(hover!==null){
   context.strokeStyle=HOT
   context.globalAlpha=.35;context.lineWidth=6;context.stroke(hot)
   context.globalAlpha=1;context.lineWidth=1.8;context.stroke(hot)
  }
  // Dots: a soft glow that breathes slowly, then the solid dot on top.
  data.nodes.forEach((node,index)=>{
   const dim=lit!==null&&index!==hover&&!lit.has(index)
   const on=index===hover||(lit!==null&&lit.has(index))
   const r=radius(node.s)*scale*(index===hover?1.4:1)
   const pulse=drift?.8+.2*Math.sin(time*.9+index*1.3):.9
   const g=r*(on?4.2:3.4)
   context.globalAlpha=dim?.12:on?1:pulse
   context.drawImage(sprites.current![node.a]||sprites.current![0],at[index][0]-g,at[index][1]-g,g*2,g*2)
  })
  context.globalCompositeOperation='source-over'
  data.nodes.forEach((node,index)=>{
   const dim=lit!==null&&index!==hover&&!lit.has(index)
   context.globalAlpha=dim?.28:1
   context.fillStyle=index===hover?'#FFF6E0':data.areas[node.a]?.color||'#A3B1BD'
   context.beginPath();context.arc(at[index][0],at[index][1],radius(node.s)*scale*(index===hover?1.4:1),0,Math.PI*2);context.fill()
  })
  context.globalAlpha=1
 }
 useEffect(draw)
 useEffect(()=>{
  if(!size.w||staticMode()||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return
  const element=box.current
  let frame=0,visible=true,last=0
  const start=performance.now()
  progress.current=0
  live.current.drift=Math.max(1.6,Math.min(3,size.w/400))
  const tick=(now:number)=>{
   frame=0
   if(!visible||document.hidden)return
   frame=requestAnimationFrame(tick)
   // Settle-in at full frame rate, then about 30 frames a second for the slow drift.
   if(progress.current>=1&&now-last<32)return
   last=now
   progress.current=Math.min(1,(now-start)/1100)
   live.current.time=now/1000
   draw()
  }
  const resume=()=>{if(!frame&&visible&&!document.hidden)frame=requestAnimationFrame(tick)}
  const observer=element&&'IntersectionObserver' in window
   ?new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;resume()}):null
  if(element)observer?.observe(element)
  document.addEventListener('visibilitychange',resume)
  resume()
  return ()=>{cancelAnimationFrame(frame);observer?.disconnect();document.removeEventListener('visibilitychange',resume);progress.current=1;live.current.drift=0}
  // Starts once the canvas has a size; a resize keeps the running loop.
 },[size.w>0])
 const pick=(event:ReactPointerEvent<HTMLCanvasElement>)=>{
  const rect=event.currentTarget.getBoundingClientRect()
  const x=event.clientX-rect.left,y=event.clientY-rect.top
  let best:number|null=null,bestDistance=event.pointerType==='touch'?24:14
  data.nodes.forEach((_,index)=>{
   const [nx,ny]=point(index,size.w,size.h,1)
   const distance=Math.hypot(nx-x,ny-y)
   if(distance<bestDistance){best=index;bestDistance=distance}
  })
  setHover(best)
 }
 const shown=hover===null?null:data.nodes[hover]
 const [tipX,tipY]=hover===null?[0,0]:point(hover,size.w,size.h,1)
 return <div className="sw-brain-canvas" ref={box}>
  <canvas ref={canvas} style={{width:size.w,height:size.h}} aria-hidden="true"
   onPointerMove={pick} onPointerDown={pick} onPointerLeave={()=>setHover(null)}/>
  {shown&&<div className="sw-brain-tip" role="status" style={{left:Math.min(Math.max(tipX,90),size.w-90),top:tipY}}>
   <code>{shown.f}</code>
   <span>{data.areas[shown.a]?.label}, {number(shown.s)} functions and classes, {neighbours.current.get(hover!)?.size||0} linked files</span>
  </div>}
 </div>
}

function GrowthChart(){
 const rows=summary.history
 const max=Math.max(...rows.map(row=>row.nodes))
 return <figure className="sw-growth">
  <figcaption id="sw-growth-title">Functions and classes in STAR's code, per release</figcaption>
  <table aria-labelledby="sw-growth-title">
   <thead className="sw-sr"><tr><th scope="col">Release</th><th scope="col">Functions and classes</th><th scope="col">Links</th><th scope="col">Files</th><th scope="col">Clusters</th></tr></thead>
   <tbody>
    {rows.map((row,index)=><tr key={row.version} data-current={index===rows.length-1||undefined}>
     <th scope="row">v{row.version}</th>
     <td className="sw-growth-bar"><span style={{'--p':Math.max(.015,row.nodes/max)} as CSSProperties} aria-hidden="true"/><strong>{number(row.nodes)}</strong></td>
     <td>{number(row.edges)} links</td>
     <td>{number(row.files)} files</td>
     <td>{number(row.communities)} clusters</td>
    </tr>)}
   </tbody>
  </table>
 </figure>
}

export function SiteBrain(){
 const section=useRef<HTMLElement>(null)
 const [data,setData]=useState<BrainData|null>(null)
 useEffect(()=>{
  const node=section.current
  if(!node)return
  let cancelled=false
  const load=()=>{import('./brainGraph.json').then(module=>{if(!cancelled)setData(module.default as unknown as BrainData)}).catch(()=>undefined)}
  if(!('IntersectionObserver' in window)){load();return ()=>{cancelled=true}}
  const observer=new IntersectionObserver(([entry])=>{if(entry.isIntersecting){observer.disconnect();load()}},{rootMargin:'600px 0px'})
  observer.observe(node)
  return ()=>{cancelled=true;observer.disconnect()}
 },[])
 const current=summary.current
 return <section className="sw-brain" id="brain" ref={section} aria-labelledby="sw-brain-title">
  <div className="sw-wrap">
   <header className="sw-section-head">
    <h2 id="sw-brain-title">STAR's brain, as a map</h2>
    <p>Every dot is a file in STAR's code, sized by how many functions and classes it holds; every line is code in
     one file calling or importing another. Graphify drew it from the source. It shows structure, not neurons, and a
     bigger map does not mean a smarter STAR.</p>
   </header>
   <figure className="sw-brain-figure">
    <div className="sw-brain-stage" data-ready={data?'true':undefined}>
     <img className="sw-brain-fallback" src="./site/brain-graph.svg" width={1000} height={640} loading="lazy" decoding="async"
      alt={'A map of STAR\'s code: the '+summary.shown.files+' most connected files as coloured dots joined by lines, a dense core of Python files with a separate cluster for the interface'}/>
     {data&&<BrainCanvas data={data}/>}
    </div>
    <figcaption>
     <ul className="sw-brain-legend" aria-label="Colours">
      {summary.areas.filter(area=>area.files>0).map(area=><li key={area.id}><span style={{background:area.color,boxShadow:'0 0 8px '+area.color}} aria-hidden="true"/>{area.label}<em>{number(area.files)}</em></li>)}
     </ul>
     <p className="sw-note">The {summary.shown.files} most connected of {number(current.files)} files and {summary.shown.links} of their
      strongest links, from {number(current.nodes)} functions and classes and {number(current.edges)} links in v{current.version} source
      (commit {current.commit}). Built with <code>graphify extract . --code-only</code> on {formatDate(summary.generatedAt,'long')}.</p>
    </figcaption>
   </figure>

   <div className="sw-brain-grid">
    <GrowthChart/>
    <div className="sw-brain-counts">
     <h3>What its learning systems hold</h3>
     <dl>
      {brainCounts.items.map(item=><div key={item.label}><dt>{item.label}</dt><dd><strong>{item.value}</strong>{item.note}</dd></div>)}
     </dl>
     <p className="sw-note">{brainCounts.asOf} <a href={LINKS.learning} target="_blank" rel="noopener noreferrer">How the loop works<ArrowUpRight size={13} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span></a></p>
    </div>
   </div>
  </div>
 </section>
}
