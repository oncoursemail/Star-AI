/**
 * The public STAR website. It never talks to the native Qt bridge and never reads local data:
 * everything on the page is editorial content, captures of the interface, or public GitHub data.
 */
import {Suspense,useEffect,useMemo,useRef,useState} from 'react'
import {ArrowDown,ArrowUpRight,Github,Menu,X} from 'lucide-react'
import {StarConstruction,StarLockup,StarMark} from './SiteBrand'
import {SiteShowcase} from './SiteShowcase'
import {SiteChapters,SiteLimits} from './SiteChapters'
import {SiteProgress} from './SiteProgress'
import {SiteDownload} from './SiteDownload'
import {LINKS,SOURCE_VERSION,formatBytes,formatDate,releaseFiles} from './siteContent'
import {latestStable} from './githubPublic'
import {delay,staticMode,useActiveSection,useHeaderState,useProgress,useReveal} from './siteHooks'
import './site.css'

const sections=[
 {id:'product',label:'Product'},
 {id:'roblox',label:'Roblox'},
 {id:'how',label:'How it works'},
 {id:'progress',label:'Progress'},
 {id:'download',label:'Download'}
] as const
const sectionIds=sections.map(section=>section.id)

export function Landing(){
 const root=useRef<HTMLDivElement>(null)
 const menuButton=useRef<HTMLButtonElement>(null)
 const [menu,setMenu]=useState(false)
 const progress=useProgress()
 const latest=useMemo(()=>latestStable(progress.snapshot),[progress.snapshot])
 const files=useMemo(()=>releaseFiles(latest),[latest])
 const header=useHeaderState(menu)
 const active=useActiveSection(sectionIds)
 // `?visualqa` freezes motion for screenshots. Read after mount so prerendered markup matches the first render.
 const [still,setStill]=useState(false)
 useEffect(()=>{setStill(staticMode())},[])
 useReveal(root)

 useEffect(()=>{
  if(!menu)return
  const onKey=(event:KeyboardEvent)=>{
   if(event.key==='Escape'){setMenu(false);menuButton.current?.focus()}
  }
  window.addEventListener('keydown',onKey)
  return ()=>window.removeEventListener('keydown',onKey)
 },[menu])

 const closeMenu=()=>setMenu(false)
 return <div className={'sw'+(still?' sw-still':'')} id="top" ref={root}>
  <a className="sw-skip" href="#main">Skip to content</a>

  <header className="sw-header" data-solid={header.solid||menu} data-hidden={header.hidden} data-past={header.past}>
   <div className="sw-wrap sw-header-row">
    <a className="sw-brand" href="#top" aria-label="STAR Intelligence, back to top"><StarLockup size={26}/></a>
    <nav className="sw-nav" id="sw-nav" aria-label="Main" data-open={menu}>
     <ul>
      {sections.map(section=><li key={section.id}>
       <a href={'#'+section.id} aria-current={active===section.id?'true':undefined} onClick={closeMenu}>{section.label}</a>
      </li>)}
      <li className="sw-nav-out"><a href={LINKS.repo} target="_blank" rel="noopener noreferrer" onClick={closeMenu}>
       <Github size={16} aria-hidden="true"/> GitHub <ArrowUpRight size={14} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span>
      </a></li>
     </ul>
    </nav>
    <div className="sw-header-actions">
     <a className="sw-btn sw-btn-primary sw-btn-compact" href="#download">Download</a>
     <button ref={menuButton} type="button" className="sw-menu-button" aria-label={menu?'Close menu':'Open menu'}
      aria-expanded={menu} aria-controls="sw-nav" onClick={()=>setMenu(open=>!open)}>
      {menu?<X size={20} aria-hidden="true"/>:<Menu size={20} aria-hidden="true"/>}
     </button>
    </div>
   </div>
  </header>

  <main id="main" tabIndex={-1}>
   <section className="sw-hero" aria-labelledby="sw-hero-title">
    <div className="sw-wrap sw-hero-grid">
     <div className="sw-hero-copy">
      <p className="sw-kicker sw-enter" style={delay(0)}>STAR INTELLIGENCE / LOCAL-FIRST AI</p>
      <h1 id="sw-hero-title" className="sw-enter" style={delay(0)}>Make the things you&nbsp;imagine.</h1>
      <p className="sw-lede sw-enter" style={delay(90)}>
       STAR is a local-first AI workspace for Windows. It runs a model on your own hardware, works inside
       Roblox Studio with your permission, and keeps your chats and projects on your&nbsp;disk.
      </p>
      <div className="sw-cta sw-enter" style={delay(170)}>
       <a className="sw-btn sw-btn-primary" href="#download"><ArrowDown size={18} aria-hidden="true"/> Download for Windows</a>
       <a className="sw-btn sw-btn-quiet" href="#product">See STAR in action</a>
      </div>
      <ul className="sw-hero-facts sw-enter" style={delay(220)} aria-label="Local workspace essentials">
       <li>Windows workspace</li><li>Local model option</li><li>Your project context</li>
      </ul>
     </div>
     <div className="sw-hero-side">
     <StarConstruction/>
     <dl className="sw-spec sw-enter" style={delay(240)} aria-label="Current release">
      <div><dt>Release</dt><dd>{latest?<a href={latest.url} target="_blank" rel="noopener noreferrer">{latest.tag}</a>:'See GitHub'}</dd></div>
      <div><dt>Published</dt><dd>{latest?formatDate(latest.publishedAt):'unavailable'}</dd></div>
      <div><dt>Platform</dt><dd>Windows 11 · x64</dd></div>
      <div><dt>Installer</dt><dd>{files.setup?formatBytes(files.setup.size):'on GitHub'}</dd></div>
      <div><dt>Model</dt><dd>Runs locally</dd></div>
      <div><dt>Status</dt><dd>Early software</dd></div>
     </dl>
     </div>
    </div>
   </section>

   {/* Each boundary hydrates as its own task, so the prerendered page never blocks input for long. */}
   <Suspense><SiteShowcase latest={latest}/></Suspense>
   <Suspense><SiteChapters latest={latest} setupSize={files.setup?.size??null}/></Suspense>
   <Suspense><SiteProgress progress={progress}/></Suspense>
   <Suspense><SiteLimits/></Suspense>
   <Suspense><SiteDownload latest={latest} files={files} status={progress.status} snapshotAt={progress.snapshot?.generatedAt??null}/></Suspense>
  </main>

  <footer className="sw-footer">
   <div className="sw-wrap sw-footer-grid">
    <div className="sw-footer-brand">
     <span className="sw-footer-mark"><StarMark size={22}/><strong>STAR Intelligence</strong></span>
     <p>A local-first AI workspace for Windows. Built in the open.</p>
     <p className="sw-fine">This site sets no cookies and runs no analytics. Repository data comes from GitHub's public API.</p>
    </div>
    <nav aria-label="Product">
     <h2>Product</h2>
     <ul>
      <li><a href="#download">Download</a></li>
      <li><a href={LINKS.releases} target="_blank" rel="noopener noreferrer">Release notes</a></li>
      <li><a href={LINKS.commits} target="_blank" rel="noopener noreferrer">Changelog</a></li>
      <li><a href="#progress">Progress</a></li>
     </ul>
    </nav>
    <nav aria-label="Documentation">
     <h2>Docs</h2>
     <ul>
      <li><a href={LINKS.start} target="_blank" rel="noopener noreferrer">Getting started</a></li>
      <li><a href={LINKS.security} target="_blank" rel="noopener noreferrer">Security and autonomy</a></li>
      <li><a href={LINKS.docs} target="_blank" rel="noopener noreferrer">All documents</a></li>
     </ul>
    </nav>
    <nav aria-label="Project">
     <h2>Project</h2>
     <ul>
      <li><a href={LINKS.repo} target="_blank" rel="noopener noreferrer">Source on GitHub</a></li>
      <li><a href={LINKS.issues} target="_blank" rel="noopener noreferrer">Report a problem</a></li>
      <li><a href={LINKS.newIssue} target="_blank" rel="noopener noreferrer">Suggest an idea</a></li>
     </ul>
    </nav>
   </div>
   <div className="sw-wrap">
    <div className="sw-footer-base">
     <span>© 2026 STAR Intelligence</span>
     <span>No licence file has been published yet. Icons: Lucide (ISC).</span>
     <span>Site built from source v{SOURCE_VERSION}</span>
    </div>
   </div>
  </footer>
 </div>
}
