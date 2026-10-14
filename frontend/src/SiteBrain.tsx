/**
 * "STAR's brain": STAR's code structure as Graphify maps it, and how it grew from release to release.
 *
 * The map is data from scripts/build_brain_graph.py (frontend/src/brainGraph.json, a precomputed force-directed
 * layout of the most connected files). The page first shows the static SVG of the same layout; the interactive canvas
 * and its data load only when the section comes near the viewport. Hover (or touch) names a file and lights up its
 * links. Reduced motion skips the settle-in animation. Nothing here calls the network.
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

function BrainCanvas({data}:{data:BrainData}){
 const canvas=useRef<HTMLCanvasElement>(null)
 const box=useRef<HTMLDivElement>(null)
 const [hover,setHover]=useState<number|null>(null)
 const [size,setSize]=useState({w:0,h:0})
 const progress=useRef(1)
 const neighbours=useRef<Map<number,Set<number>>>(new Map())
 if(!neighbours.current.size){
  for(const [a,b] of data.links){
   if(!neighbours.current.has(a))neighbours.current.set(a,new Set())
   if(!neighbours.current.has(b))neighbours.current.set(b,new Set())
   neighbours.current.get(a)!.add(b);neighbours.current.get(b)!.add(a)
  }
 }
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
  if(!element||!size.w)return
  const ratio=Math.min(window.devicePixelRatio||1,2)
  element.width=Math.round(size.w*ratio);element.height=Math.round(size.h*ratio)
  const context=element.getContext('2d')
  if(!context)return
  context.setTransform(ratio,0,0,ratio,0,0)
  context.clearRect(0,0,size.w,size.h)
  const t=1-Math.pow(1-progress.current,3)
  const lit=hover===null?null:neighbours.current.get(hover)||new Set<number>()
  context.lineWidth=1
  for(const [a,b] of data.links){
   const on=hover!==null&&(a===hover||b===hover)
   context.strokeStyle=on?'rgba(232,191,118,.75)':hover===null?'rgba(138,145,150,.16)':'rgba(138,145,150,.06)'
   const [x1,y1]=point(a,size.w,size.h,t),[x2,y2]=point(b,size.w,size.h,t)
   context.beginPath();context.moveTo(x1,y1);context.lineTo(x2,y2);context.stroke()
  }
  const scale=Math.max(.7,Math.min(1.15,size.w/900))
  data.nodes.forEach((node,index)=>{
   const [x,y]=point(index,size.w,size.h,t)
   const dim=lit!==null&&index!==hover&&!lit.has(index)
   context.globalAlpha=dim?.22:.92
   context.fillStyle=data.areas[node.a]?.color||'#8A9196'
   context.beginPath();context.arc(x,y,radius(node.s)*scale*(index===hover?1.35:1),0,Math.PI*2);context.fill()
  })
  context.globalAlpha=1
 }
 useEffect(draw)
 useEffect(()=>{
  if(staticMode()||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return
  let frame=0
  const start=performance.now()
  progress.current=0
  const tick=(now:number)=>{
   progress.current=Math.min(1,(now-start)/1100)
   draw()
   if(progress.current<1)frame=requestAnimationFrame(tick)
  }
  frame=requestAnimationFrame(tick)
  return ()=>{cancelAnimationFrame(frame);progress.current=1}
  // Runs once, when the canvas first has a size.
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
      {summary.areas.filter(area=>area.files>0).map(area=><li key={area.id}><span style={{background:area.color}} aria-hidden="true"/>{area.label}<em>{number(area.files)}</em></li>)}
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
