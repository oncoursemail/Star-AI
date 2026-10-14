import type {ReactNode} from 'react'
import {CircleAlert} from 'lucide-react'

/**
 * One small pattern for the three in-between states of any list or page:
 *   EmptyState   nothing here yet (or nothing matches): icon, short title, one sentence, optional action
 *   LoadingState still fetching: a calm skeleton, announced once to screen readers, still under reduced motion
 *   ErrorState   it failed: role="alert", says what happened and what to do, optional action (usually Try again)
 * Restrained on purpose: no illustrations, no exclamation marks. `compact` is for sidebars and panel insides.
 * Styles live in resilience.css (`.state*`).
 */
type Common = {
  /** A lucide icon element, drawn small and quiet. Decorative: hidden from screen readers. */
  icon?: ReactNode
  title: string
  /** One sentence. */
  description?: ReactNode
  /** A button or link, e.g. <button className="secondary-button">Try again</button>. */
  action?: ReactNode
  compact?: boolean
  className?: string
}

const classes = (kind: string, compact?: boolean, extra?: string) => ['state', 'state-' + kind, compact ? 'is-compact' : '', extra || ''].filter(Boolean).join(' ')

export function EmptyState({icon, title, description, action, compact, className}: Common) {
  return (
    <div className={classes('empty', compact, className)}>
      {icon ? <span className="state-icon" aria-hidden="true">{icon}</span> : null}
      <div className="state-copy">
        <p className="state-title">{title}</p>
        {description ? <p className="state-text">{description}</p> : null}
      </div>
      {action ? <div className="state-action">{action}</div> : null}
    </div>
  )
}

/** `label` is what a screen reader hears ("Loading lessons"); sighted users see only the skeleton lines. */
export function LoadingState({label, lines = 3, compact, className}: {label: string; lines?: number; compact?: boolean; className?: string}) {
  const count = Math.max(1, Math.min(6, Math.round(lines)))
  return (
    <div className={classes('loading', compact, className)} role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      <div className="state-skeleton" aria-hidden="true">
        {Array.from({length: count}, (_, index) => <span key={index} className="state-line" />)}
      </div>
    </div>
  )
}

export function ErrorState({icon, title, description, action, compact, className}: Common) {
  return (
    <div className={classes('error', compact, className)} role="alert">
      <span className="state-icon" aria-hidden="true">{icon ?? <CircleAlert size={compact ? 15 : 18} />}</span>
      <div className="state-copy">
        <p className="state-title">{title}</p>
        {description ? <p className="state-text">{description}</p> : null}
      </div>
      {action ? <div className="state-action">{action}</div> : null}
    </div>
  )
}
