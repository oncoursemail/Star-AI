/**
 * What is in STAR 1.0: two chapters with real captures of the app, then the full feature index with an honest
 * status for every line. Captures come from scripts/capture-site-media.mjs (the app's browser preview, unedited).
 */
import {ArrowUpRight} from 'lucide-react'
import media from './siteMedia.json'
import {availability} from './githubPublic'
import type {ReleaseInfo} from './githubPublic'
import {STATUS_LABEL,featureGroups} from './siteContent'
import type {Feature,FeatureStatus} from './siteContent'

type MediaFile={file:string;width:number;height:number}
const images=media.images as Record<string,MediaFile[]>
const src=(file:string)=>'./site/'+file
export const srcSet=(id:string)=>(images[id]||[]).map(file=>src(file.file)+' '+file.width+'w').join(', ')
export const first=(id:string)=>images[id]?.[0]

export function StatusMark({status}:{status:FeatureStatus}){
 return <span className={'sw-status sw-status-'+status}><span className="sw-status-dot" aria-hidden="true"/>{STATUS_LABEL[status]}</span>
}

/** A feature that is in the source but newer than the latest published release says so. */
function releaseNote(feature:Feature,latest:ReleaseInfo|null){
 if(feature.status==='soon'||!feature.since)return null
 const state=availability(feature.since,latest)
 if(state==='upcoming')return 'In v'+feature.since+', not in a published release yet'
 return null
}

export function SiteFeatures({latest}:{latest:ReleaseInfo|null}){
 const chat=first('chat')
 const phone=first('chat-phone')
 const plus=images.plus?.[images.plus.length-1]
 const consent=images.consent?.[images.consent.length-1]
 return <section className="sw-features" id="features" aria-labelledby="sw-features-title">
  <div className="sw-wrap">
   <header className="sw-section-head">
    <h2 id="sw-features-title">What is in 1.0</h2>
    <p>A chat app first. Everything that can reach your files, your screen, Roblox Studio or the internet is off or
     asks first, and every feature below says whether it is on, waiting for you, or not finished yet.</p>
   </header>

   <article className="sw-chapter" aria-labelledby="sw-chat-title">
    <div className="sw-chapter-text">
     <h3 id="sw-chat-title">A chat that stays out of the way.</h3>
     <p>Your chats sit on the left, grouped by day. Rename one in place, delete it with six seconds to undo, or search
      them all. Leave a chat while STAR is answering and the answer is still there when you come back.</p>
    </div>
    {chat&&phone&&<figure className="sw-shot sw-shot-wide" data-reveal>
     <picture>
      <source media="(max-width: 640px)" srcSet={srcSet('chat-phone')} sizes="calc(100vw - 32px)"/>
      <img src={src(chat.file)} srcSet={srcSet('chat')} sizes="(max-width: 1248px) calc(100vw - 48px), 1200px"
       width={chat.width} height={chat.height} loading="lazy" decoding="async"
       alt="STAR's chat window: a sidebar of saved chats grouped by Today, Yesterday and older, with the Rename and Delete menu open on one chat, next to a long answer about a Roblox inventory interface"/>
     </picture>
     <figcaption>The app's browser preview with its sample conversation. No model was running.</figcaption>
    </figure>}
   </article>

   <article className="sw-chapter sw-chapter-split" aria-labelledby="sw-plus-title">
    <div className="sw-chapter-text">
     <h3 id="sw-plus-title">One + for everything.</h3>
     <p>Attach a file, ask for a picture, search the web or show STAR your screen from the same box. Showing your
      screen asks first, every time, and the screenshot waits in your message until you send it or take it out.</p>
    </div>
    <div className="sw-shot-pair">
     {plus&&<figure className="sw-shot sw-shot-crop" data-reveal>
      <img src={src(plus.file)} srcSet={srcSet('plus')} sizes="(max-width: 860px) calc(100vw - 48px), 340px"
       width={plus.width} height={plus.height} loading="lazy" decoding="async"
       alt="The + menu: Add photos and files, Look at my screen (asks first), Create image, Search the web, and More"/>
      <figcaption>The + menu. Search is greyed out here because the preview has no search source set up.</figcaption>
     </figure>}
     {consent&&<figure className="sw-shot sw-shot-crop" data-reveal>
      <img src={src(consent.file)} srcSet={srcSet('consent')} sizes="(max-width: 860px) calc(100vw - 48px), 420px"
       width={consent.width} height={consent.height} loading="lazy" decoding="async"
       alt="A dialog titled Let STAR look at your screen? explaining that STAR takes one screenshot only after you choose Take screenshot, with Cancel and Take screenshot buttons"/>
      <figcaption>Look at my screen, before anything is captured.</figcaption>
     </figure>}
    </div>
   </article>

   <div className="sw-index" aria-labelledby="sw-index-title">
    <div className="sw-index-head">
     <h3 id="sw-index-title">Everything else, with its status</h3>
     <ul className="sw-legend" aria-label="What the statuses mean">
      <li><StatusMark status="available"/> on when you install</li>
      <li><StatusMark status="opt-in"/> you switch it on or set it up</li>
      <li><StatusMark status="soon"/> an open pull request, not in 1.0</li>
     </ul>
    </div>
    {featureGroups.map(group=><section className="sw-index-group" key={group.id} aria-labelledby={'sw-group-'+group.id}>
     <h4 id={'sw-group-'+group.id}>{group.title}</h4>
     <ul>
      {group.features.map(feature=>{
       const note=releaseNote(feature,latest)
       return <li className="sw-index-row" key={feature.name} data-status={feature.status}>
        <span className="sw-index-name">{feature.doc
         ?<a href={feature.doc} target="_blank" rel="noopener noreferrer">{feature.name}<ArrowUpRight size={13} aria-hidden="true"/><span className="sw-sr"> (documentation, opens in a new tab)</span></a>
         :feature.name}</span>
        <span className="sw-index-what">{feature.what}{note&&<span className="sw-index-note"> {note}.</span>}</span>
        <StatusMark status={feature.status}/>
       </li>
      })}
     </ul>
    </section>)}
   </div>
  </div>
 </section>
}
