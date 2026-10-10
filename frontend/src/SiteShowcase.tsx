import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react'
import type {KeyboardEvent} from 'react'
import {Image as ImageIcon,Play} from 'lucide-react'
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
 chat:'The STAR chat screen. A sidebar lists New chat and the STAR project. The main area greets with "What can I help you with?", offers three suggestions, and holds a typed request in the message box next to Auto, Teams and Web controls.',
 brain:'The STAR Brain screen. A card titled "Set up your local AI" explains that a verified local model will be downloaded, with a "Download and start" button and an Offline status.',
 tools:'The Developer tools screen. Two cards, Roblox Studio and Local workspace, followed by read-only knowledge connections such as Obsidian.',
 projects:'The Projects screen. A field to create a workspace, the current STAR workspace, and a panel for approving project decisions.',
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
 const [live,setLive]=useState(false)
 const tabs=useRef<HTMLDivElement>(null)
 const [bar,setBar]=useState<{left:number;width:number}|null>(null)
 const view=tour.find(item=>item.id===current)||tour[0]

 const select=useCallback((id:TourId,focus=false)=>{
  setCurrent(id)
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
   <h2 id="sw-showcase-title" className="sw-sr">The STAR interface</h2>
   <div className="sw-tabs-row sw-enter" style={delay(300)}>
    <div className="sw-tabs" role="tablist" aria-label="Areas of the STAR interface" ref={tabs} onKeyDown={onKeys}>
     {tour.map(item=><button key={item.id} type="button" role="tab" id={'sw-tab-'+item.id}
      aria-selected={current===item.id} aria-controls="sw-tour-panel" tabIndex={current===item.id?0:-1}
      onClick={()=>select(item.id)}>{item.tab}</button>)}
     <span className="sw-tab-bar" aria-hidden="true" data-ready={bar!==null}
      style={bar?{transform:'translateX('+bar.left+'px) scaleX('+bar.width+')'}:undefined}/>
    </div>
    <button type="button" className="sw-btn sw-btn-quiet sw-btn-compact sw-live-toggle" aria-pressed={live} onClick={()=>setLive(on=>!on)}>
     {live?<><ImageIcon size={16} aria-hidden="true"/> Back to capture</>:<><Play size={16} aria-hidden="true"/> Open live preview</>}
    </button>
   </div>

   <div className="sw-tour sw-enter" style={delay(340)} role="tabpanel" id="sw-tour-panel" aria-labelledby={'sw-tab-'+current} tabIndex={0}>
    <div className="sw-plate">
     <i className="sw-crop sw-crop-tl" aria-hidden="true"/><i className="sw-crop sw-crop-tr" aria-hidden="true"/>
     <i className="sw-crop sw-crop-bl" aria-hidden="true"/><i className="sw-crop sw-crop-br" aria-hidden="true"/>
     <div className="sw-plate-frame sw-plate-screen">
      {live
       ?<iframe key={current} title={'Live, read-only preview of the STAR '+view.tab+' screen'} src={'./?preview=1&tab='+current} loading="lazy"/>
       :tour.filter(item=>seen.includes(item.id)).map(item=><div key={item.id} className="sw-shot" data-active={item.id===current} aria-hidden={item.id!==current}>
         <Capture id={item.id} eager={item.id==='chat'}/>
        </div>)}
     </div>
    </div>
    <div className="sw-tour-caption" key={current}>
     <div className="sw-tour-text">
      <h3>{view.title}</h3>
      <p>{view.body}</p>
     </div>
     <ul className="sw-tour-points">{view.points.map(point=><li key={point}>{point}</li>)}</ul>
    </div>
   </div>

   <p className="sw-note sw-plate-note">
    {live
     ?'This is the real interface running in your browser, read-only. It has no model and cannot see your files.'
     :'Captures of the real interface in browser preview mode, taken '+formatDate(media.capturedAt)+'. No model is connected, so every screen shows a fresh workspace.'}
    {ahead&&latest?' They come from source v'+media.sourceVersion+', which is newer than the current download ('+latest.tag+'). The released app has the same areas with an earlier layout.':''}
   </p>
  </div>
 </section>
}
