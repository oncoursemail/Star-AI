/**
 * Download section. Every link points at an asset of the latest *published* GitHub release, taken from the
 * release data itself. The source version this site was built from is never offered as a download.
 */
import {useState} from 'react'
import {ArrowUpRight,Check,Copy,Download,FileArchive} from 'lucide-react'
import {compareVersions} from './githubPublic'
import type {ReleaseInfo} from './githubPublic'
import {LINKS,SOURCE_VERSION,formatBytes,formatDate} from './siteContent'
import type {ReleaseFiles} from './siteContent'
import type {ProgressStatus} from './siteHooks'

function CopyHash({value}:{value:string}){
 const [copied,setCopied]=useState(false)
 const copy=async()=>{
  try{
   await navigator.clipboard.writeText(value)
   setCopied(true)
   window.setTimeout(()=>setCopied(false),1600)
  }catch{/* Clipboard access can be refused; the hash stays selectable. */}
 }
 return <button type="button" className="sw-copy" onClick={()=>void copy()}>
  {copied?<Check size={15} aria-hidden="true"/>:<Copy size={15} aria-hidden="true"/>}
  <span aria-live="polite">{copied?'Copied':'Copy'}</span>
 </button>
}

export function SiteDownload({latest,files,status,snapshotAt}:{
 latest:ReleaseInfo|null;files:ReleaseFiles;status:ProgressStatus;snapshotAt:string|null
}){
 const sourceAhead=latest?compareVersions(SOURCE_VERSION,latest.tag)>0:false
 const confirmed=status.kind==='live'
 const setup=files.setup
 return <section className="sw-download" id="download" aria-labelledby="sw-download-title">
  <div className="sw-wrap">
   <div className="sw-download-grid">
    <div className="sw-download-main" data-reveal>
     <p className="sw-kicker">Download</p>
     <h2 id="sw-download-title">Get STAR for Windows.</h2>
     <p className="sw-lede">Free, from GitHub Releases. No account and no API key.</p>
     <div className="sw-cta">
      {setup
       ?<a className="sw-btn sw-btn-primary sw-btn-large" href={setup.url}><Download size={19} aria-hidden="true"/> Download Setup {latest?.tag}</a>
       :<a className="sw-btn sw-btn-primary sw-btn-large" href={LINKS.latest} target="_blank" rel="noopener noreferrer"><Download size={19} aria-hidden="true"/> Open the latest release</a>}
      <a className="sw-btn sw-btn-quiet sw-btn-large" href={files.zip?.url||LINKS.latestZip}><FileArchive size={18} aria-hidden="true"/> Portable ZIP</a>
     </div>
     <dl className="sw-file-facts">
      {setup&&<div><dt>Setup</dt><dd><code>{setup.name}</code> · {formatBytes(setup.size)}</dd></div>}
      {files.zip&&<div><dt>Portable</dt><dd><code>{files.zip.name}</code> · {formatBytes(files.zip.size)}</dd></div>}
      {latest&&<div><dt>Published</dt><dd>{formatDate(latest.publishedAt,'long')} · <a href={latest.url} target="_blank" rel="noopener noreferrer">Release notes<ArrowUpRight size={13} aria-hidden="true"/><span className="sw-sr"> (opens in a new tab)</span></a></dd></div>}
      <div><dt>Needs</dt><dd>Windows 11, 64-bit. About 4.3 GB free for the model.</dd></div>
     </dl>
     {!confirmed&&latest&&<p className="sw-note">Release details as of {formatDate(snapshotAt,'long')}. <a href={LINKS.latest} target="_blank" rel="noopener noreferrer">Check GitHub for a newer release</a>.</p>}
     {sourceAhead&&latest&&<p className="sw-note">The source is at v{SOURCE_VERSION}, which has not been released. These buttons give you {latest.tag}, the latest published build.</p>}
    </div>

    <div className="sw-verify" data-reveal>
     <h3>Check the file before you run it</h3>
     <p>Builds are not code-signed yet, so Windows may show a publisher warning. Compare the SHA-256 of what you
      downloaded with the one published on the release.</p>
     {setup?.sha256
      ?<div className="sw-hash">
        <span className="sw-hash-label">SHA-256 of {setup.name}</span>
        <code>{setup.sha256}</code>
        <CopyHash value={setup.sha256}/>
       </div>
      :<p className="sw-note">The checksum is listed in SHA256SUMS.txt on the release.</p>}
     <span className="sw-hash-label">In PowerShell</span>
     <pre className="sw-command"><code>Get-FileHash .\{setup?.name||'STAR-Setup-vX.Y.Z.exe'} -Algorithm SHA256</code></pre>
     <a className="sw-link" href={files.sums?.url||LINKS.latestSums}>SHA256SUMS.txt<ArrowUpRight size={14} aria-hidden="true"/></a>
    </div>
   </div>

   <dl className="sw-after" data-reveal>
    <div>
     <dt>Updating</dt>
     <dd>Install a newer Setup over the old one. Your chats, models and settings in <code>%APPDATA%\STAR</code> are kept.</dd>
    </div>
    <div>
     <dt>Something wrong?</dt>
     <dd><a href={LINKS.issues} target="_blank" rel="noopener noreferrer">Open an issue on GitHub</a> with a screenshot of the error. Leave out keys and passwords.</dd>
    </div>
    <div>
     <dt>Older builds</dt>
     <dd><a href={LINKS.releases} target="_blank" rel="noopener noreferrer">All releases</a> stay available, each with its own checksums.</dd>
    </div>
   </dl>
  </div>
 </section>
}
