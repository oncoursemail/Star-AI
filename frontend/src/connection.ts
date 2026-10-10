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
  /** The app-wide status light (`brainStatus` in IntegrationPanels): on-device brain or STAR Server. */
  brain: {online: boolean; label: string}
  /** STAR Server check summary from the host; `ok` is null until the server has been checked. */
  server?: {ok: boolean | null; configured?: boolean; key_present?: boolean} | null
  /** True for the on-device brain and STAR Server; false for hosted providers. */
  ownHardware: boolean
  credentials: Record<string, boolean>
  preview: boolean
  last: LastOutcome
}): Connection {
  const {settings, brain, server, ownHardware, credentials, preview, last} = input
  const provider = providerLabel(settings.provider)
  const model = (settings.model || '').trim()
  const local = settings.provider === 'local'
  const lan = settings.provider === 'star_server'
  const endpoint = local ? hostOf(settings.endpoint) : lan ? hostOf(settings.server_endpoint) : ''
  const base = {provider, model, endpoint}
  const label = model ? `${provider} · ${model}` : provider
  if (preview) {
    return {...base, tone: 'preview', label: 'Preview', state: 'No model', note: 'This browser preview is not connected to a model. Open STAR Desktop to chat.'}
  }
  if (lan && server && server.configured === false) {
    return {...base, tone: 'attention', label: provider, state: 'No server address', note: 'Enter the address of your STAR Server in Settings.'}
  }
  if (!model) {
    return {...base, tone: 'attention', label: provider, state: 'No model selected', note: 'Choose a model in Model & connection before sending.'}
  }
  if (!ownHardware && !credentials[settings.provider]) {
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
  if (ownHardware && brain.online) {
    return {...base, tone: 'ready', label, state: 'Ready', note: brain.label + '.'}
  }
  if (lan) {
    // A server that was never checked is not called offline.
    return server?.ok === false
      ? {...base, tone: 'offline', label, state: 'Needs attention', note: 'The last check of your STAR Server failed. Test it in Model & connection.'}
      : {...base, tone: 'unverified', label, state: 'Not checked', note: 'Your STAR Server has not been checked in this session. Send a message or test the connection.'}
  }
  if (local) {
    return {...base, tone: 'offline', label, state: 'Offline', note: 'The model on this PC is not running. Start it in Model & connection.'}
  }
  return {...base, tone: 'unverified', label, state: 'Not checked', note: 'Not checked in this session. Send a message or test the connection.'}
}

export type FailureKind = 'cancelled' | 'unreachable' | 'access' | 'slow' | 'limit' | 'setup' | 'other'
/** `message` is the backend's own sentence without the Python exception class; `title` is the UI's short reading of it. */
export type Failure = {kind: FailureKind; title: string; message: string}

/** Turn a backend error string into a calm title, a readable sentence and a recovery class. */
export function classifyFailure(raw: string): Failure {
  const message = (raw || 'The task could not finish.').replace(/^[A-Za-z_]*(?:Error|Exception|Timeout):\s*/, '').trim()
  const text = raw.toLowerCase()
  if (text.includes('cancelled by user') || text.startsWith('request stopped') || text.startsWith('no reply was recorded')) {
    return {kind: 'cancelled', title: 'Stopped', message}
  }
  if (/cannot reach|could not connect|connection (error|refused)|not respond(ing)?\b(?!.*in time)|is offline|unavailable/.test(text)) {
    return {kind: 'unreachable', title: "Can't reach the model", message}
  }
  if (/needs (its|an) api key/.test(text)) {
    return {kind: 'setup', title: 'A key is needed first', message}
  }
  if (/denied access|refused the api key|api key|401|403/.test(text)) {
    return {kind: 'access', title: 'The key or access was refused', message}
  }
  if (/rate limit|quota|429|is busy/.test(text)) {
    return {kind: 'limit', title: 'The model is busy right now', message}
  }
  if (/in time|time limit|task budget|timed out/.test(text)) {
    return {kind: 'slow', title: 'That took too long', message}
  }
  if (/still loading|503/.test(text)) {
    return {kind: 'slow', title: 'The model is still loading', message}
  }
  if (/select a model|choose a|workflow|not available on this provider/.test(text)) {
    return {kind: 'setup', title: 'Something needs setting up first', message}
  }
  if (text.includes('teams could not finish')) {
    return {kind: 'other', title: "The team couldn't finish", message}
  }
  return {kind: 'other', title: "STAR couldn't finish that", message}
}
