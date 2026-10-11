import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react'
import type {KeyboardEvent} from 'react'
import {ArrowUpRight,Image as ImageIcon,Play,RotateCcw,Sparkles} from 'lucide-react'
import {StarMark} from './SiteBrand'
import {useEffectiveReducedMotion} from './MotionPolicy'
import media from './siteMedia.json'
import {tour,formatDate} from './siteContent'
import type {TourId} from './siteContent'
import {compareVersions} from './githubPublic'
import type {ReleaseInfo} from './githubPublic'
import {delay} from './siteHooks'

type MediaFile={file:string;width:number;height:number}
const images=media.images as Record<string,MediaFile[]>
const src=(file:string)=>'./site/'+file

const alt:Record<TourId,string>={
 chat:'The STAR chat screen. A sidebar lists New chat and the STAR workspace. Four prompts offer Roblox interface design, script review, research and Blender planning. The message box holds a request to inspect a test place before editing.',
 brain:'The Model and connection screen. The local connection has no model selected. A Model on this PC card explains the verified model download and offers Download and start.',
 tools:'The Developer tools screen. Two cards, Roblox Studio and Local workspace, followed by read-only knowledge connections such as Obsidian.',
 projects:'The Projects screen. A field to create a workspace, the current STAR workspace, and local lessons waiting for review.',
 analytics:'The Analytics screen. Four counters for task runs, successful runs, messages and median response, all at zero, above an empty execution trend chart.'
}

/** Wide and narrow captures of one screen. The first screen is the page's largest image, so it loads eagerly. */
function Capture({id,eager}:{id:TourId;eager:boolean}){
 const wide=images[id]||[]
 const narrow=(images[id+'-narrow']||[])[0]
 const base=wide[0]
 if(!base)return null
 return <picture>
  {narrow&&<source media="(max-width: 640px)" srcSet={src(narrow.file)} width={narrow.width} height={narrow.height}/>}
  <img src={src(base.file)} srcSet={wide.map(file=>src(file.file)+' '+file.width+'w').join(', ')}
   sizes="(max-width: 1296px) calc(100vw - 64px), 1200px" width={base.width} height={base.height}
   alt={alt[id]} decoding="async" loading={eager?'eager':'lazy'} fetchPriority={eager?'high':undefined}/>
 </picture>
}

export function SiteShowcase({latest}:{latest:ReleaseInfo|null}){
 const [current,setCurrent]=useState<TourId>('chat')
 const [seen,setSeen]=useState<TourId[]>(['chat'])
 const [mode,setMode]=useState<'capture'|'preview'|'sample'>('capture')
 const [replay,setReplay]=useState(0)
 const reducedMotion=useEffectiveReducedMotion(false)
 const tabs=useRef<HTMLDivElement>(null)
 const [bar,setBar]=useState<{left:number;width:number}|null>(null)
 const view=tour.find(item=>item.id===current)||tour[0]

 const select=useCallback((id:TourId,focus=false)=>{
  setCurrent(id)
  setMode(value=>value==='sample'&&id!=='chat'?'capture':value)
  setSeen(list=>list.includes(id)?list:[...list,id])
  if(focus)document.getElementById('sw-tab-'+id)?.focus()
 },[])
 const onKeys=(event:KeyboardEvent<HTMLDivElement>)=>{
  const index=tour.findIndex(item=>item.id===current)
  const next=event.key==='ArrowRight'?(index+1)%tour.length
   :event.key==='ArrowLeft'?(index-1+tour.length)%tour.length
   :event.key==='Home'?0:event.key==='End'?tour.length-1:-1
  if(next<0)return
  event.preventDefault()
  select(tour[next].id,true)
 }

 // The gold bar under the active tab moves with a transform only.
 const measure=useCallback(()=>{
  const tab=tabs.current?.querySelector<HTMLElement>('[aria-selected="true"]')
  if(tab)setBar({left:tab.offsetLeft,width:tab.offsetWidth})
 },[])
 useLayoutEffect(measure,[measure,current])
 useEffect(()=>{
  if(!('ResizeObserver' in window)||!tabs.current)return
  const observer=new ResizeObserver(measure)
  observer.observe(tabs.current)
  return ()=>observer.disconnect()
 },[measure])

 const ahead=latest?compareVersions(media.sourceVersion,latest.tag)>0:false
 return <section className="sw-showcase" id="product" aria-labelledby="sw-showcase-title">
  <div className="sw-wrap">
   <div className="sw-showcase-head sw-enter" style={delay(260)}>
    <div><p className="sw-kicker">THE CREATIVE WORKBENCH</p><h2 id="sw-showcase-title">A place for your next idea.</h2></div>
    <p>Conversation, context and tools. <br/>One workspace, on your own terms.</p>
   </div>
   <div className="sw-tabs-row sw-enter" style={delay(300)}>
    <div className="sw-tabs" role="tablist" aria-label="Areas of the STAR interface" ref={tabs} onKeyDown={onKeys}>
     {tour.map((item,index)=><button key={item.id} type="button" role="tab" id={'sw-tab-'+item.id}
      aria-selected={current===item.id} aria-controls="sw-tour-panel" tabIndex={current===item.id?0:-1}
      onClick={()=>select(item.id)}><span className="sw-tab-number" aria-hidden="true">0{index+1}</span>{item.tab}</button>)}
     <span className="sw-tab-bar" aria-hidden="true" data-ready={bar!==null}
      style={bar?{transform:'translateX('+bar.left+'px) scaleX('+bar.width+')'}:undefined}/>
    </div>
    <div className="sw-showcase-actions">
     {current==='chat'&&<button type="button" className="sw-btn sw-btn-quiet sw-btn-compact" onClick={()=>{setMode('sample');setReplay(value=>value+1)}}>
      {mode==='sample'?<RotateCcw size={15} aria-hidden="true"/>:<Play size={15} aria-hidden="true"/>}
      {mode==='sample'?'Replay sample':reducedMotion?'Open sample conversation':'Watch a sample run'}
     </button>}
     <button type="button" className="sw-btn sw-btn-quiet sw-btn-compact sw-live-toggle" aria-pressed={mode==='preview'} onClick={()=>setMode(value=>value==='capture'?'preview':'capture')}>
      {mode!=='capture'?<><ImageIcon size={15} aria-hidden="true"/> Back to capture</>:<>Explore the interface <ArrowUpRight size={15} aria-hidden="true"/></>}
     </button>
    </div>
   </div>

   <div className="sw-tour sw-enter" style={delay(340)} role="tabpanel" id="sw-tour-panel" aria-labelledby={'sw-tab-'+current} tabIndex={0}>
    <div className="sw-plate">
     <i className="sw-crop sw-crop-tl" aria-hidden="true"/><i className="sw-crop sw-crop-tr" aria-hidden="true"/>
     <i className="sw-crop sw-crop-bl" aria-hidden="true"/><i className="sw-crop sw-crop-br" aria-hidden="true"/>
     <div className="sw-workbench-bar">
      <span className="sw-workbench-title"><StarMark size={16}/><strong>STAR</strong><span>/</span>{view.tab}</span>
      <span className="sw-workbench-mode"><span aria-hidden="true"/>{mode==='sample'?'Scripted sample':mode==='preview'?'Read-only preview':'Interface capture'}</span>
     </div>
     <div className="sw-plate-frame sw-plate-screen">
      {mode!=='capture'
       ?<iframe key={current+'-'+mode+'-'+replay+'-'+reducedMotion} title={mode==='sample'?'Scripted STAR conversation sample. No model is running.':'Read-only preview of the STAR '+view.tab+' screen'} src={mode==='sample'?'./?preview=1&fixture='+(reducedMotion?'chat':'streaming'):'./?preview=1&tab='+current} loading="lazy"/>
       :tour.filter(item=>seen.includes(item.id)).map(item=><div key={item.id} className="sw-shot" data-active={item.id===current} aria-hidden={item.id!==current}>
         <Capture id={item.id} eager={item.id==='chat'}/>
        </div>)}
     </div>
    </div>
    <div className="sw-tour-caption" key={current}>
     <div className="sw-tour-text">
      <span className="sw-tour-index" aria-hidden="true">0{tour.findIndex(item=>item.id===current)+1} / 05</span>
      <h3>{view.title}</h3>
      <p>{view.body}</p>
     </div>
     <ul className="sw-tour-points">{view.points.map(point=><li key={point}><Sparkles size={13} aria-hidden="true"/>{point}</li>)}</ul>
    </div>
   </div>

   <p className="sw-note sw-plate-note">
    {mode==='sample'
     ?'A scripted design sample, using the real chat interface. No model is running; the answer and timing are examples, not a performance measurement.'
     :mode==='preview'
     ?'This is the real interface running in your browser, read-only. It has no model and cannot see your files.'
     :'Captures of the real interface in browser preview mode, taken '+formatDate(media.capturedAt)+'. No model is connected, so every screen shows a fresh workspace.'}
    {ahead&&latest?' They come from source v'+media.sourceVersion+', which is newer than the current download ('+latest.tag+'). The released app has the same areas with an earlier layout.':''}
   </p>
  </div>
 </section>
}
