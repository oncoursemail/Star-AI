import type {ReactNode} from 'react'
import {useState} from 'react'
import {Check, CheckCheck, Copy, ArrowUpRight, Sparkles, LockKeyhole, Terminal} from 'lucide-react'
import {motion} from 'motion/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type {ChatMessage} from './types'
import {request} from './bridge'

export function Brand({small=false}:{small?:boolean}) {
  return <div className={'brand '+(small?'brand-small':'')}>
    <div className="brand-mark" aria-hidden="true"><svg width="29" height="29" viewBox="0 0 48 48"><path d="M24 3 29.4 18.6 45 24 29.4 29.4 24 45 18.6 29.4 3 24 18.6 18.6Z" fill="currentColor"/><circle cx="24" cy="24" r="2.9" fill="#111214"/></svg></div>
    <div className="brand-words"><strong>STAR</strong><span>INTELLIGENCE</span></div>
  </div>
}
export function Tag({children,kind='neutral'}:{children:ReactNode;kind?:'neutral'|'gold'|'green'|'red'}) {return <span className={'tag tag-'+kind}>{children}</span>}
export function Panel({children,className=''}:{children:ReactNode;className?:string}) {return <section className={'panel '+className}>{children}</section>}
export function EmptyState({icon,heading,description}:{icon:ReactNode;heading:string;description:string}) {return <div className="empty-state"><div className="empty-icon">{icon}</div><strong>{heading}</strong><span>{description}</span></div>}
export function LinkExternal({href,children}:{href:string;children:ReactNode}) {return <a target="_blank" rel="noopener noreferrer" href={href}>{children}<ArrowUpRight size={13} aria-hidden="true"/></a>}

export function Message({entry,animated=true}:{entry:ChatMessage;animated?:boolean}) {
  const [copied,setCopied]=useState(false)
  const isUser=entry.role==='user'
  const isError=entry.role==='event'
  return <motion.article initial={animated?{opacity:0,y:8}:false} animate={{opacity:1,y:0}} transition={{duration:.2}} className={'message '+(isUser?'message-user':isError?'message-event':'message-star')}>
    <div className={'message-avatar '+(isUser?'avatar-user':'avatar-star')} aria-hidden="true">{isUser?'Y':<Sparkles size={16}/>}</div>
    <div className="message-content">
      <div className="message-head"><strong>{isUser?'You':isError?'System':'STAR'}</strong><span>{entry.created?new Date(entry.created).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}):''}</span></div>
      <div className={'message-body '+(isError?'error-text':'')}>
        {isUser||isError?<p className="preserve-white-space">{entry.text}</p>:
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
            a: ({href,children})=><a href={href||'#'} rel="noopener noreferrer" target="_blank">{children}<ArrowUpRight size={12} aria-hidden="true"/></a>,
            code: ({className,children})=><code className={className}>{children}</code>,
            pre: ({children})=><div className="code-container"><div className="code-label"><Terminal size={13}/> Code</div><pre>{children}</pre></div>
          }}>{entry.text}</ReactMarkdown>}
      </div>
      {entry.attachments?.length? <div className="attachment-view">{entry.attachments.map(name=><span key={name}>{name}</span>)}</div>:null}
      {!isError&&!isUser&&<button className="message-copy" type="button" aria-label="Copy response" onClick={async()=>{try{await navigator.clipboard.writeText(entry.text)}catch{await request('copyText',{text:entry.text})}setCopied(true);setTimeout(()=>setCopied(false),1400)}}>{copied?<CheckCheck size={14}/>:<Copy size={14}/>} {copied?'Copied':'Copy'}</button>}
    </div>
  </motion.article>
}
export function PrivacyNote() {return <span className="privacy"><LockKeyhole size={13} aria-hidden="true"/> Local first. Your files stay yours.</span>}
export function Starlight(){return <span className="starlight" aria-hidden="true"><i/><i/><i/></span>}
