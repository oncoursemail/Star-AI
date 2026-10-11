import {
 ArrowUpRight,Ban,Check,CircleDashed,Cloud,Database,Eye,FileJson,Folder,Monitor,PencilLine,Server
} from 'lucide-react'
import media from './siteMedia.json'
import {
 LINKS,brainRoutes,connections,dataFolder,faqs,formatBytes,limits,requirements,steps,studioScopes
} from './siteContent'
import {availability} from './githubPublic'
import type {ReleaseInfo} from './githubPublic'
import {delay} from './siteHooks'

type MediaFile={file:string;width:number;height:number}
const images=media.images as Record<string,MediaFile[]>

/** Says in words whether something is in the download today. Colour is never the only signal. */
function Status({since,latest}:{since:string;latest:ReleaseInfo|null}){
 const state=availability(since,latest)
 if(state==='released')return <span className="sw-status sw-status-on"><Check size={14} aria-hidden="true"/> In {latest?.tag}</span>
 if(state==='upcoming')return <span className="sw-status sw-status-next"><CircleDashed size={14} aria-hidden="true"/> Not in a release yet</span>
 return <span className="sw-status">Status on GitHub</span>
}

/**
 * An element-level capture. Phones get the same element captured at a narrow window, so the text stays readable.
 * `narrowOnly` uses that narrow capture at every width, for elements that read best stacked.
 */
function Crop({id,alt,sizes,narrowOnly=false}:{id:string;alt:string;sizes:string;narrowOnly?:boolean}){
 const narrow=(images[id+'-narrow']||[])[0]
 const files=narrowOnly&&narrow?[narrow]:images[id]||[]
 const base=files[0]
 if(!base)return null
 return <picture>
  {narrow&&!narrowOnly&&<source media="(max-width: 640px)" srcSet={'./site/'+narrow.file} width={narrow.width} height={narrow.height}/>}
  <img src={'./site/'+base.file} srcSet={files.map(file=>'./site/'+file.file+' '+file.width+'w').join(', ')} sizes={sizes}
   width={base.width} height={base.height} alt={alt} loading="lazy" decoding="async"/>
 </picture>
}

const routeIcons={pc:Monitor,server:Server,cloud:Cloud} as const
const scopeIcons=[Eye,PencilLine,Ban] as const

export function SiteChapters({latest,setupSize}:{latest:ReleaseInfo|null;setupSize:number|null}){
 const shipped=connections.filter(item=>availability(item.since,latest)==='released')
 const pending=connections.filter(item=>availability(item.since,latest)!=='released')
 return <>
  <section className="sw-chapter" id="brain" aria-labelledby="sw-brain-title">
   <div className="sw-wrap sw-chapter-grid">
    <div className="sw-chapter-copy" data-reveal>
     <p className="sw-kicker">STAR Brain</p>
     <h2 id="sw-brain-title">A brain that runs where you choose.</h2>
     <p>STAR Brain is a model server that STAR installs and manages for you. Your prompts travel over loopback to a
      model on your own machine, not to someone else's cloud.</p>
     <p>One button downloads the engine and the model, checks each file, and asks for a real reply before it calls
      itself ready.</p>
    </div>
    <div className="sw-routes" data-reveal style={delay(80)}>
     <p className="sw-routes-origin"><span className="sw-routes-dot" aria-hidden="true"/>Your prompt, from STAR on your PC</p>
     <ol>
      {brainRoutes.map((route,index)=>{
       const Icon=routeIcons[route.icon]
       const state=availability(route.since,latest)
       return <li key={route.id} className="sw-route" data-state={state} style={delay(160+index*90)}>
        <span className="sw-route-icon" aria-hidden="true"><Icon size={20} strokeWidth={1.6}/></span>
        <div className="sw-route-body">
         <h3>{route.title}{route.note&&<span className="sw-route-note">{route.note}</span>}</h3>
         <p>{route.body}</p>
        </div>
        <Status since={route.since} latest={latest}/>
       </li>
      })}
     </ol>
    </div>
   </div>
  </section>

  <section className="sw-chapter sw-chapter-flip" id="roblox" aria-labelledby="sw-roblox-title">
   <div className="sw-wrap sw-chapter-grid">
    <div className="sw-chapter-copy" data-reveal>
     <p className="sw-kicker">Roblox Studio</p>
     <h2 id="sw-roblox-title">Works inside Studio, on your terms.</h2>
     <p>STAR talks to Roblox's <a href={LINKS.robloxMcp} target="_blank" rel="noopener noreferrer">official Studio MCP server<span className="sw-sr"> (opens in a new tab)</span></a>.
      Point it at an unpublished test place, let it look around, and decide yourself when it may change anything.</p>
     <ol className="sw-scopes">
      {studioScopes.map((scope,index)=>{
       const Icon=scopeIcons[index]
       return <li key={scope.level} data-level={scope.level.toLowerCase()}>
        <span className="sw-scope-icon" aria-hidden="true"><Icon size={18} strokeWidth={1.7}/></span>
        <div><h3>{scope.level} <span>{scope.state}</span></h3><p>{scope.body}</p></div>
       </li>
      })}
     </ol>
    </div>
    <figure className="sw-figure sw-figure-slim" data-reveal style={delay(80)}>
     <div className="sw-plate">
      <i className="sw-crop sw-crop-tl" aria-hidden="true"/><i className="sw-crop sw-crop-tr" aria-hidden="true"/>
      <i className="sw-crop sw-crop-bl" aria-hidden="true"/><i className="sw-crop sw-crop-br" aria-hidden="true"/>
      <div className="sw-plate-frame">
       <Crop id="studio" narrowOnly sizes="(max-width: 480px) calc(100vw - 56px), 400px"
        alt="Two cards from the Developer tools screen. Roblox Studio: connect to the official Roblox Studio MCP server and start in an unpublished test place. Local workspace: STAR can inspect a selected folder and edits files only with write permission."/>
      </div>
     </div>
     <figcaption className="sw-note">Developer tools, captured from the real interface. It assists inside a Studio
      session; it is not a game factory, and what it writes still needs playtesting.</figcaption>
    </figure>
   </div>
  </section>

  <section className="sw-chapter" id="yours" aria-labelledby="sw-yours-title">
   <div className="sw-wrap sw-chapter-grid">
    <div className="sw-chapter-copy" data-reveal>
     <p className="sw-kicker">Your data</p>
     <h2 id="sw-yours-title">Your projects stay yours.</h2>
     <p>Everything STAR knows about your work is a file on your disk. There is no account and nothing to sign in to.
      With the local brain, your prompts and files are processed on your PC.</p>
     <p>Installing a new version replaces the app and leaves this folder alone.</p>
    </div>
    <div className="sw-tree" data-reveal style={delay(80)} role="group" aria-label="What STAR stores, and where">
     <p className="sw-tree-root"><Folder size={16} aria-hidden="true"/> %APPDATA%\STAR\</p>
     <ul>
      {dataFolder.map(item=>{
       const Icon=item.name.endsWith('\\')?Folder:item.name.endsWith('.json')?FileJson:Database
       return <li key={item.name}><Icon size={15} aria-hidden="true"/><code>{item.name}</code><span>{item.what}</span></li>
      })}
     </ul>
    </div>
   </div>
  </section>

  <section className="sw-chapter sw-chapter-wide" id="tools" aria-labelledby="sw-tools-title">
   <div className="sw-wrap">
    <div className="sw-chapter-head" data-reveal>
     <p className="sw-kicker">Connections</p>
     <h2 id="sw-tools-title">Connect what you already use.</h2>
     <p>Each connection is off until you turn it on, and each one says what it may read. The status column is
      checked against the latest published release, so it changes when a release does.</p>
    </div>
    <div className="sw-ledger" data-reveal style={delay(80)}>
     <table>
      <caption className="sw-sr">STAR connections and whether each is in the current download</caption>
      <thead><tr><th scope="col">Connection</th><th scope="col">What it does</th><th scope="col">Status</th></tr></thead>
      <tbody>
       {[...shipped,...pending].map(item=><tr key={item.name}>
        <th scope="row">{item.name}</th><td>{item.what}</td><td><Status since={item.since} latest={latest}/></td>
       </tr>)}
      </tbody>
     </table>
    </div>
   </div>
  </section>

  <section className="sw-how" id="how" aria-labelledby="sw-how-title">
   <div className="sw-wrap">
    <div className="sw-chapter-head" data-reveal>
     <p className="sw-kicker">How it works</p>
     <h2 id="sw-how-title">From download to first reply.</h2>
    </div>
    <ol className="sw-steps">
     {steps.map((step,index)=><li key={step.title} data-reveal style={delay(index*70)}>
      <span className="sw-step-number" aria-hidden="true">{index+1}</span>
      <h3>{step.title}</h3>
      <p>{step.body}</p>
      <p className="sw-step-fact">{step.fact==='installer'?(setupSize?formatBytes(setupSize)+' installer':'Installer on GitHub Releases'):step.fact}</p>
     </li>)}
    </ol>
    <div className="sw-how-detail">
     <figure className="sw-figure" data-reveal>
      <div className="sw-plate">
       <i className="sw-crop sw-crop-tl" aria-hidden="true"/><i className="sw-crop sw-crop-tr" aria-hidden="true"/>
       <i className="sw-crop sw-crop-bl" aria-hidden="true"/><i className="sw-crop sw-crop-br" aria-hidden="true"/>
       <div className="sw-plate-frame">
        <Crop id="setup" sizes="(max-width: 960px) calc(100vw - 64px), 560px"
          alt='The Model on this PC card. No local model is installed. Installing downloads a verified model of a few gigabytes. A Download and start button begins setup.'/>
       </div>
      </div>
      <figcaption className="sw-note">Step two as it looks in the app before the model is installed.</figcaption>
     </figure>
     <dl className="sw-reqs" data-reveal style={delay(80)}>
      {requirements.map(item=><div key={item.term}><dt>{item.term}</dt><dd>{item.detail}</dd></div>)}
     </dl>
    </div>
   </div>
  </section>
 </>
}

export function SiteLimits(){
 return <section className="sw-limits" id="limits" aria-labelledby="sw-limits-title">
  <div className="sw-wrap sw-limits-grid">
   <div data-reveal>
    <p className="sw-kicker">Known limits</p>
    <h2 id="sw-limits-title">What STAR is not, yet.</h2>
    <ul className="sw-limit-list">
     {limits.map(item=><li key={item.title}>
      <h3>{item.title}</h3>
      <p>{item.body}{'link' in item&&item.link?<> <a href={item.link.href} target="_blank" rel="noopener noreferrer">{item.link.label}<ArrowUpRight size={13} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span></a></>:null}</p>
     </li>)}
    </ul>
   </div>
   <div data-reveal style={delay(80)}>
    <p className="sw-kicker">Straight answers</p>
    <div className="sw-faq">
     {faqs.map(item=><details key={item.q}><summary>{item.q}</summary><p>{item.a}</p></details>)}
    </div>
   </div>
  </div>
 </section>
}
