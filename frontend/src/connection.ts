/** Truthful model/provider status for the composer and error recovery.
 *
 *  Everything here is derived from state the desktop really reports
 *  (`bootstrap` settings, `brain_running`, saved-credential flags) plus what
 *  happened to the last request in this session. When STAR has not verified a
 *  connection it says "not checked" instead of guessing "ready" or "offline".
 */

export type ConnectionTone = 'ready' | 'unverified' | 'attention' | 'offline' | 'preview'
export type Connection = {
  tone: ConnectionTone
  /** Short label for the composer, e.g. "This PC · qwen3.5-4b". */
  label: string
  /** One word of state, always shown next to the dot so colour is never the only signal. */
  state: string
  provider: string
  model: string
  endpoint: string
  note: string
}
export type LastOutcome = {ok: boolean; at: number; kind?: FailureKind} | null

const PROVIDERS: Record<string, string> = {
  local: 'This PC',
  star_server: 'STAR Server',
  groq: 'GroqCloud',
  openrouter: 'OpenRouter',
  gemini: 'Google Gemini',
  cerebras: 'Cerebras',
}
export const providerLabel = (id: string) => PROVIDERS[id] || id || 'Unknown provider'

const clock = (at: number) => new Date(at).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'})
const hostOf = (url: unknown) => {
  if (typeof url !== 'string' || !url) return ''
  try {
    return new URL(url).host
  } catch {
    return ''
  }
}

export function describeConnection(input: {
  settings: {provider: string; model: string; endpoint: string} & Record<string, unknown>
  brainRunning: boolean
  credentials: Record<string, boolean>
  preview: boolean
  last: LastOutcome
}): Connection {
  const {settings, brainRunning, credentials, preview, last} = input
  const provider = providerLabel(settings.provider)
  const model = (settings.model || '').trim()
  const local = settings.provider === 'local'
  const hosted = !local && settings.provider !== 'star_server'
  const endpoint = local ? hostOf(settings.endpoint) : settings.provider === 'star_server' ? hostOf(settings.server_endpoint) : ''
  const base = {provider, model, endpoint}
  const label = model ? `${provider} · ${model}` : provider
  if (preview) {
    return {...base, tone: 'preview', label: 'Preview', state: 'No model', note: 'This browser preview is not connected to a model. Open STAR Desktop to chat.'}
  }
  if (!model) {
    return {...base, tone: 'attention', label: provider, state: 'No model selected', note: 'Choose a model in Model & connection before sending.'}
  }
  if (hosted && !credentials[settings.provider]) {
    return {...base, tone: 'attention', label, state: 'Key missing', note: `${provider} needs an API key. Add it in Settings.`}
  }
  if (last && !last.ok && (last.kind === 'unreachable' || last.kind === 'access')) {
    return {
      ...base,
      tone: 'offline',
      label,
      state: last.kind === 'access' ? 'Access refused' : 'Not reachable',
      note: `The last request at ${clock(last.at)} could not reach the model.`,
    }
  }
  if (last?.ok) {
    return {...base, tone: 'ready', label, state: 'Connected', note: `Answered at ${clock(last.at)}.`}
  }
  if (local && brainRunning) {
    return {...base, tone: 'ready', label, state: 'Running', note: 'The model on this PC is running.'}
  }
  return {
    ...base,
    tone: 'unverified',
    label,
    state: 'Not checked',
    note: local
      ? "STAR's own engine is not running on this PC. If your model runs elsewhere, send a message or test the connection."
      : 'Not checked in this session. Send a message or test the connection.',
  }
}

export type FailureKind = 'cancelled' | 'unreachable' | 'access' | 'slow' | 'limit' | 'setup' | 'other'
export type Failure = {kind: FailureKind; title: string; message: string; /** The backend's own wording, kept for the tooltip. */ detail?: string}

/** Turn a backend error string into a calm title, a readable sentence and a recovery class. */
export function classifyFailure(raw: string): Failure {
  const message = (raw || 'The task could not finish.').replace(/^[A-Za-z_]*(?:Error|Exception|Timeout):\s*/, '').trim()
  const text = raw.toLowerCase()
  if (text.includes('cancelled by user') || text.startsWith('request stopped')) {
    return {kind: 'cancelled', title: 'Stopped', message: 'You stopped this response.'}
  }
  if (/cannot reach|could not connect|connection (error|refused)|not respond(ing)?\b(?!.*in time)|is offline|unavailable/.test(text)) {
    return {kind: 'unreachable', title: "Can't reach the model", message: 'Your message was sent, but no model answered. Check that the model server is running and reachable, then test the connection.', detail: message}
  }
  if (/denied access|api key|needs an api key|401|403/.test(text)) {
    return {kind: 'access', title: 'The provider refused the request', message: 'The model provider rejected this request. Check its API key and model access in Settings.', detail: message}
  }
  if (/rate limit|quota|429/.test(text)) {
    return {kind: 'limit', title: 'The provider is rate-limiting requests', message}
  }
  if (/in time|time limit|task budget|timed out|timeout/.test(text)) {
    return {kind: 'slow', title: 'That took too long', message}
  }
  if (/select a model|choose a|workflow|not available on this provider/.test(text)) {
    return {kind: 'setup', title: 'Something needs setting up first', message}
  }
  if (text.includes('teams could not finish')) {
    return {kind: 'other', title: "The team couldn't finish", message: 'One stage did not complete, so there is no combined answer. The steps above show which one.', detail: message}
  }
  return {kind: 'other', title: "STAR couldn't finish that", message}
}
