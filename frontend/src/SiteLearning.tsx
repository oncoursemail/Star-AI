/**
 * "How STAR learns": the real loop from docs/SELF_LEARNING_LOOP.md, drawn as inline SVG.
 *
 * The track draws itself once when the section scrolls into view, the steps arrive in order along it, and one small
 * dot keeps travelling the loop to show that it repeats. Reduced motion and `?visualqa` show the finished drawing
 * without the dot. The SVG is a picture of the list that follows it; the list carries the words for screen readers.
 */
import {useEffect,useRef,useState} from 'react'
import {ArrowUpRight} from 'lucide-react'
import {LINKS,learnCorrections,learnSteps} from './siteContent'
import {first,srcSet} from './SiteFeatures'
import {staticMode} from './siteHooks'

type Node={id:string;label:string;x:number;y:number;n?:number;kind?:'gate'|'you'|'aside'}

const WIDE={
 view:'0 0 1120 450',
 track:'M200 90H920A120 120 0 0 1 920 330H200A120 120 0 0 1 200 90Z',
 nodes:[
  {id:'practise',label:'Practise',x:260,y:90,n:1},
  {id:'check',label:'Check',x:500,y:90,n:2},
  {id:'propose',label:'Propose',x:740,y:90,n:3},
  {id:'gate',label:'Gate',x:1040,y:210,n:4,kind:'gate'},
  {id:'decide',label:'You decide',x:740,y:330,n:5,kind:'you'},
  {id:'corrections',label:'Your corrections',x:400,y:410,kind:'aside'},
 ] as Node[],
 join:'M400 386V342',
 reject:{path:'M965 210H884',x:872,y:204,anchor:'end' as 'end'|'middle',lines:['Inconclusive','or worse: dropped']},
 centre:{x:500,y:204,lines:['The model itself never changes.','A lesson is text you can read, edit and remove.']},
 back:{x:430,y:316,text:'Kept lessons are used in answers and in the next practice'},
 chevrons:[{x:380,y:90,a:0},{x:620,y:90,a:0},{x:1000,y:122,a:40},{x:600,y:330,a:180},{x:80,y:210,a:270}],
}
const TALL={
 view:'0 0 360 720',
 track:'M110 92V560A85 85 0 0 0 280 560V92A85 85 0 0 0 110 92Z',
 nodes:[
  {id:'practise',label:'Practise',x:110,y:120,n:1},
  {id:'check',label:'Check',x:110,y:235,n:2},
  {id:'propose',label:'Propose',x:110,y:350,n:3},
  {id:'gate',label:'Gate',x:110,y:465,n:4,kind:'gate'},
  {id:'decide',label:'You decide',x:280,y:575,n:5,kind:'you'},
  {id:'corrections',label:'Corrections',x:280,y:235,kind:'aside'},
 ] as Node[],
 join:'',
 reject:{path:'M178 465H228',x:203,y:500,anchor:'middle' as 'end'|'middle',lines:['Inconclusive','is dropped']},
 centre:{x:195,y:690,lines:['The model never changes. Lessons are text.']},
 back:{x:0,y:0,text:''},
 chevrons:[{x:110,y:177,a:90},{x:110,y:292,a:90},{x:110,y:407,a:90},{x:280,y:410,a:270},{x:280,y:150,a:270}],
}
type Layout=typeof WIDE

function Diagram({layout,id,moving}:{layout:Layout;id:string;moving:boolean}){
 const pillWidth=(node:Node)=>node.kind==='aside'?(id==='tall'?132:172):node.kind==='you'?(id==='tall'?132:150):132
 return <svg className={'sw-loop sw-loop-'+id} viewBox={layout.view} role="img" aria-labelledby={'sw-loop-'+id+'-title'} focusable="false">
  <title id={'sw-loop-'+id+'-title'}>STAR's learning loop: practise, check, propose, a statistical gate, then you decide; kept lessons and your corrections feed the next round.</title>
  <defs>
   <marker id={'sw-arrow-'+id} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M1 1 9 5 1 9" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
   </marker>
  </defs>
  <path className="sw-loop-track-base" d={layout.track}/>
  <path className="sw-loop-track" d={layout.track} pathLength={1} id={'sw-track-'+id}/>
  {layout.chevrons.map(c=><path key={c.x+'-'+c.y} className="sw-loop-chevron" d="M-4 -5 2 0-4 5" transform={'translate('+c.x+' '+c.y+') rotate('+c.a+')'}/>)}
  {layout.join&&<path className="sw-loop-join" d={layout.join} markerEnd={'url(#sw-arrow-'+id+')'}/>}
  <path className="sw-loop-reject" d={layout.reject.path} markerEnd={'url(#sw-arrow-'+id+')'}/>
  <text className="sw-loop-reject-label" x={layout.reject.x} y={layout.reject.y} textAnchor={layout.reject.anchor}>
   {layout.reject.lines.map((line,index)=><tspan key={line} x={layout.reject.x} dy={index?18:0}>{line}</tspan>)}
  </text>
  {layout.back.text&&<text className="sw-loop-back" x={layout.back.x} y={layout.back.y} textAnchor="middle">{layout.back.text}</text>}
  <text className="sw-loop-centre" x={layout.centre.x} y={layout.centre.y} textAnchor="middle">
   {layout.centre.lines.map((line,index)=><tspan key={line} x={layout.centre.x} dy={index?22:0}>{line}</tspan>)}
  </text>
  {moving&&<circle className="sw-loop-dot" r="4.5"><animateMotion dur="11s" repeatCount="indefinite" rotate="auto"><mpath href={'#sw-track-'+id}/></animateMotion></circle>}
  {layout.nodes.map((node,index)=>{
   const width=pillWidth(node)
   return <g className={'sw-loop-node'+(node.kind?' sw-loop-node-'+node.kind:'')} key={node.id} style={{animationDelay:200+index*170+'ms'}}
    transform={'translate('+node.x+' '+node.y+')'}>
    <rect x={-width/2} y={-24} width={width} height={48} rx={24}/>
    {node.n&&<><circle className="sw-loop-num" cx={-width/2+24} cy={0} r={12}/><text className="sw-loop-num-text" x={-width/2+24} y={4.5} textAnchor="middle">{node.n}</text></>}
    <text className="sw-loop-label" x={node.n?-width/2+46:0} y={5} textAnchor={node.n?'start':'middle'}>{node.label}</text>
   </g>
  })}
 </svg>
}

export function SiteLearning(){
 const figure=useRef<HTMLElement>(null)
 const [allowed,setAllowed]=useState(false)
 const [visible,setVisible]=useState(false)
 useEffect(()=>{
  const reduce=window.matchMedia?.('(prefers-reduced-motion: reduce)')
  const update=()=>setAllowed(!staticMode()&&!reduce?.matches)
  update()
  reduce?.addEventListener?.('change',update)
  return ()=>reduce?.removeEventListener?.('change',update)
 },[])
 // The travelling dot exists only while the diagram is on screen.
 useEffect(()=>{
  const node=figure.current
  if(!node||!('IntersectionObserver' in window))return
  const observer=new IntersectionObserver(([entry])=>setVisible(entry.isIntersecting))
  observer.observe(node)
  return ()=>observer.disconnect()
 },[])
 const moving=allowed&&visible
 const learned=first('learned')
 return <section className="sw-learn" id="learning" aria-labelledby="sw-learn-title">
  <div className="sw-wrap">
   <header className="sw-section-head">
    <h2 id="sw-learn-title">How STAR learns</h2>
    <p>Every night your STAR Server is idle, STAR practises, checks its own work and proposes lessons. Most never
     make it through. The ones that do are put in front of you, and you can take any of them back.</p>
   </header>
   <figure className="sw-loop-figure" data-reveal ref={figure}>
    <Diagram layout={WIDE} id="wide" moving={moving}/>
    <Diagram layout={TALL} id="tall" moving={moving}/>
   </figure>
   <ol className="sw-loop-steps">
    {learnSteps.map((step,index)=><li key={step.id}>
     <h3><span className="sw-loop-step-n" aria-hidden="true">{index+1}</span>{step.title}</h3>
     <p>{step.body}</p>
    </li>)}
    <li className="sw-loop-step-aside">
     <h3>{learnCorrections.title}</h3>
     <p>{learnCorrections.body}</p>
    </li>
   </ol>
   <div className="sw-learn-proof">
    {learned&&<figure className="sw-shot sw-shot-crop" data-reveal>
     <picture>
     <source media="(max-width: 640px)" srcSet={srcSet('learned-phone')} sizes="calc(100vw - 32px)"/>
     <img src={'./site/'+learned.file} srcSet={srcSet('learned')} sizes="(max-width: 860px) calc(100vw - 48px), 560px"
      width={learned.width} height={learned.height} loading="lazy" decoding="async"
      alt="The What STAR learned this week panel, showing 0 lessons in use, and the Your corrections panel, showing 0 waiting"/>
     </picture>
     <figcaption>“What STAR learned this week” and “Your corrections” in the app. Empty here, because the preview has no data.</figcaption>
    </figure>}
    <div className="sw-learn-honest">
     <h3>Where this stands in 1.0</h3>
     <p>The machinery is in: night school, the 300 practice tasks, the paired gate, the weekly review with Undo, and
      corrections that become tests. The lesson file bundled with 1.0 is empty, so night school has not changed
      1.0's answers yet. Lessons from the server arrive as candidates you review.</p>
     <a className="sw-link" href={LINKS.learning} target="_blank" rel="noopener noreferrer">How the loop works, in detail<ArrowUpRight size={14} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span></a>
    </div>
   </div>
  </div>
 </section>
}
