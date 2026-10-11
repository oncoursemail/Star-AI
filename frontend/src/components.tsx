import {splitSources, type AnswerSource} from './sources'
import type {ReactNode} from 'react'
import {isValidElement, memo, useState} from 'react'
import {ArrowUpRight, Check, CircleAlert, CircleSlash, Copy, Image as ImageIcon, LoaderCircle, LockKeyhole, Pencil, RotateCcw, ThumbsDown, ThumbsUp, X} from 'lucide-react'
import * as Dialog from '@radix-ui/react-dialog'
import {motion} from 'motion/react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type {ChatMessage} from './types'
import {request} from './bridge'
import {messageIn} from './motion'
import {classifyFailure} from './connection'

/** The STAR glyph: a drawn four-point star, used wherever the brand appears on the desktop. */
export function StarMark({size = 20}: {size?: number}) {
  return (
    <svg className="star-mark" width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path d="M24 3 29.4 18.6 45 24 29.4 29.4 24 45 18.6 29.4 3 24 18.6 18.6Z" fill="currentColor" />
    </svg>
  )
}
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
export function PrivacyNote() {return <span className="privacy"><LockKeyhole size={13} aria-hidden="true"/> Local first. Your files stay yours.</span>}
export function Starlight(){return <span className="starlight" aria-hidden="true"><i/><i/><i/></span>}

function safeExternalUrl(href?: string) {
  if (!href) return null
  try {
    const target = new URL(href, window.location.href)
    return ['http:', 'https:', 'mailto:'].includes(target.protocol) ? target.href : null
  } catch {
    return null
  }
}
function toCodeText(children: ReactNode): string {
  if (typeof children === 'string' || typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(toCodeText).join('')
  if (isValidElement<{children?: ReactNode}>(children)) return toCodeText(children.props.children)
  return ''
}
/** Clipboard first; Qt WebEngine on file:// may deny it, so fall back to the native copyText action. */
export async function copySafe(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through to the native bridge */
  }
  const reply = await request('copyText', {text})
  return reply.ok
}

function CopyButton({text, label, className}: {text: string; label: string; className: string}) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      className={className}
      aria-label={copied ? 'Copied' : label}
      title={label}
      onClick={async () => {
        if (await copySafe(text)) {
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1400)
        }
      }}
    >
      {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      <span>{copied ? 'Copied' : 'Copy'}</span>
    </button>
  )
}

function CodeBlock({children}: {children: ReactNode}) {
  const code = toCodeText(children).replace(/\n$/, '')
  const language = isValidElement<{className?: string}>(children) ? String(children.props.className || '').replace(/^language-/, '') : ''
  return (
    <div className="codeblock">
      <div className="codeblock-head">
        <span>{language || 'code'}</span>
        <CopyButton text={code} label="Copy code" className="codeblock-copy" />
      </div>
      <pre tabIndex={0}>{children}</pre>
    </div>
  )
}

/** Rendered Markdown never executes HTML: react-markdown escapes it, links are protocol-checked, remote images are not loaded. */
const Prose = memo(function Prose({text}: {text: string}) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({href, children}) => {
          const safe = safeExternalUrl(href)
          return safe ? (
            <a href={safe} rel="noopener noreferrer" target="_blank">
              {children}
            </a>
          ) : (
            <span>{children}</span>
          )
        },
        img: ({alt}) => <span className="md-image-note">{alt || 'External image'} (not loaded; open the original reference instead)</span>,
        code: ({className, children}) => <code className={className}>{children}</code>,
        pre: ({children}) => <CodeBlock>{children}</CodeBlock>,
        table: ({children}) => (
          <div className="md-table" tabIndex={0}>
            <table>{children}</table>
          </div>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  )
})

/** Official documentation STAR retrieved for this answer. Links are https and host-checked in sources.ts. */
function SourcesRow({sources}: {sources: AnswerSource[]}) {
  return (
    <div className="msg-sources" role="group" aria-label="Sources for this answer">
      <span className="msg-sources-label">Sources</span>
      <ol>
        {sources.map(source => (
          <li key={source.index} className={source.cited ? 'is-cited' : undefined}>
            <span className="msg-source-index" aria-hidden="true">
              {source.index}
            </span>
            {source.url ? (
              <a href={source.url} rel="noopener noreferrer" target="_blank" title={source.url}>
                {source.title}
              </a>
            ) : (
              <span>{source.title}</span>
            )}
            <span className="sr-only">{source.cited ? ' (cited in the answer)' : ' (retrieved, not cited)'}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

export type MessageProps = {
  entry: ChatMessage
  /** The answer is still streaming: no actions yet, and screen readers are told it is busy. */
  partial?: boolean
  /** Keep the action row visible (the newest turn) instead of revealing it on hover or focus. */
  pinned?: boolean
  animated?: boolean
  /** Put this turn's text back in the composer. */
  onEdit?: () => void
  /** Re-send the question behind a failed or stopped turn. Only offered on the newest one. */
  onRetry?: () => void
  /** Ask the last question again after a finished answer. */
  onAskAgain?: () => void
  onConnection?: () => void
  /** Rate a saved answer: 'up', 'down', or '' to take the rating back. STAR keeps it as a note to review. */
  onFeedback?: (value: 'up' | 'down' | '') => void
}

/** A turn that ended without an answer. The backend stores this row, so it reads the same after a restart. */
function TurnNotice({entry, animated, onRetry, onEdit, onConnection}: MessageProps) {
  const failure = classifyFailure(entry.text)
  const failed = entry.status === 'failed'
  const actionable = Boolean(onRetry || onEdit)
  const connectionFirst = failed && (failure.kind === 'unreachable' || failure.kind === 'access' || failure.kind === 'setup')
  return (
    <motion.article
      variants={messageIn}
      initial={animated ? 'hidden' : false}
      animate="shown"
      className={'msg msg-note is-' + (entry.status || 'plain') + (actionable ? ' is-actionable' : '')}
      aria-label={failed ? 'STAR could not answer' : entry.status === 'cancelled' ? 'Stopped' : 'STAR notice'}
    >
      {failed ? <CircleAlert size={16} className="note-icon" aria-hidden="true" /> : entry.status ? <CircleSlash size={16} className="note-icon" aria-hidden="true" /> : null}
      <div className="note-main">
        {failed && <strong>{failure.title}</strong>}
        <p>{failure.message}</p>
        {actionable && (
          <div className="note-actions">
            {connectionFirst && onConnection && (
              <button type="button" className="note-button is-primary" onClick={onConnection}>
                Model &amp; connection
              </button>
            )}
            {onRetry && (
              <button type="button" className={'note-button' + (failed && !connectionFirst ? ' is-primary' : '')} onClick={onRetry}>
                <RotateCcw size={14} aria-hidden="true" /> Retry
              </button>
            )}
            {onEdit && (
              <button type="button" className="note-button" onClick={onEdit}>
                <Pencil size={14} aria-hidden="true" /> Edit message
              </button>
            )}
          </div>
        )}
      </div>
    </motion.article>
  )
}

export function Message(props: MessageProps) {
  const {entry, partial = false, pinned = false, animated = true, onEdit, onAskAgain, onFeedback} = props
  if (entry.role === 'event') return <TurnNotice {...props} animated={animated} />
  const isUser = entry.role === 'user'
  const hasImage = Boolean(entry.image?.startsWith('data:image/webp;base64,'))
  // The sources list is part of the stored answer; show it as a row, not as prose.
  const {body, sources} = isUser || partial ? {body: entry.text, sources: []} : splitSources(entry.text)
  return (
    <motion.article
      variants={messageIn}
      initial={animated ? 'hidden' : false}
      animate="shown"
      className={'msg ' + (isUser ? 'msg-user' : 'msg-star') + (pinned ? ' is-pinned' : '')}
      aria-label={isUser ? 'You said' : 'STAR said'}
      aria-busy={partial || undefined}
    >
      {isUser && entry.attachments?.length ? (
        <ul className="msg-files" aria-label="Attached files">
          {entry.attachments.map(name => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      ) : null}
      {isUser ? (
        <div className="msg-bubble">{entry.text}</div>
      ) : (
        <div className="msg-prose">
          <Prose text={body} />
        </div>
      )}
      {sources.length > 0 && <SourcesRow sources={sources} />}
      {hasImage && (
        <Dialog.Root>
          <Dialog.Trigger asChild>
            <button type="button" className="generated-image-button" aria-label="Expand generated image">
              <img src={entry.image} alt="Art generated by STAR" loading="lazy" />
            </button>
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="star-layer star-image-overlay" />
            <Dialog.Content className="star-layer star-image-dialog" aria-describedby={undefined}>
              <Dialog.Title className="sr-only">STAR generated image preview</Dialog.Title>
              <Dialog.Close className="star-image-close" aria-label="Close image preview">
                <X size={18} />
              </Dialog.Close>
              <img src={entry.image} alt="Expanded artwork generated by STAR" />
              <p>The original image is saved in your local STAR files.</p>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      )}
      {partial && (
        <div className="msg-actions is-live" aria-hidden="true">
          <LoaderCircle size={14} className="act-spin" />
          <span>Writing</span>
        </div>
      )}
      {!partial && (
        <div className="msg-actions">
          <CopyButton text={entry.text} label={isUser ? 'Copy your message' : 'Copy response'} className="msg-action" />
          {onEdit && (
            <button type="button" className="msg-action" title="Put this message back in the composer" onClick={onEdit}>
              <Pencil size={14} aria-hidden="true" />
              <span>Edit</span>
            </button>
          )}
          {onAskAgain && (
            <button type="button" className="msg-action" title="Send your last message again" onClick={onAskAgain}>
              <RotateCcw size={14} aria-hidden="true" />
              <span>Ask again</span>
            </button>
          )}
          {onFeedback && !isUser && (
            <>
              <button type="button" className="msg-action msg-rate" aria-label="Helpful" title="Helpful" aria-pressed={entry.feedback === 'up'}
                onClick={() => onFeedback(entry.feedback === 'up' ? '' : 'up')}>
                <ThumbsUp size={14} aria-hidden="true" />
              </button>
              <button type="button" className="msg-action msg-rate" aria-label="Not helpful" title="Not helpful" aria-pressed={entry.feedback === 'down'}
                onClick={() => onFeedback(entry.feedback === 'down' ? '' : 'down')}>
                <ThumbsDown size={14} aria-hidden="true" />
              </button>
            </>
          )}
          {hasImage && (
            <span className="msg-meta">
              <ImageIcon size={14} aria-hidden="true" /> Saved locally
            </span>
          )}
        </div>
      )}
    </motion.article>
  )
}
