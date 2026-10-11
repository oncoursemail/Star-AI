/** The sources list STAR appends to an answer that was grounded in the official documentation.
 *
 *  The backend (star/doc_grounding.py::sources_footer) writes it as plain Markdown at the very
 *  end of the stored answer, so it survives a restart, a copy and an export with no extra
 *  storage. This module only recognises that fixed shape and hands the chat a typed list.
 *  Anything that does not match is left in the answer text exactly as it was.
 */

export type AnswerSource = {index: number; title: string; url: string; cited: boolean}

export const SOURCES_MARKER = '**Sources retrieved by STAR**'
/** Documentation hosts the backend may link to (star/doc_knowledge.py::_SOURCE_HOSTS). */
const HOSTS = new Set(['create.roblox.com', 'luau.org', 'github.com'])
const ITEM = /^(\d{1,2})\. (?:\[([^\]\n]{1,160})\]\((https:\/\/[^\s)]{1,400})\)|([^\n[\]]{1,160}?)) · (cited|retrieved, not cited)$/

function safeUrl(value: string | undefined): string {
  if (!value) return ''
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password && HOSTS.has(url.hostname) ? url.href : ''
  } catch {
    return ''
  }
}

/** Split a stored answer into its prose and its sources. No marker, or a malformed list: no sources. */
export function splitSources(text: string): {body: string; sources: AnswerSource[]} {
  const at = text.lastIndexOf('\n---\n' + SOURCES_MARKER)
  if (at < 0) return {body: text, sources: []}
  const lines = text
    .slice(at + 5)
    .split('\n')
    .slice(1)
    .map(line => line.trim())
    .filter(Boolean)
  const sources: AnswerSource[] = []
  for (const line of lines) {
    const match = ITEM.exec(line)
    if (!match || Number(match[1]) !== sources.length + 1) return {body: text, sources: []}
    sources.push({index: sources.length + 1, title: (match[2] || match[4]).trim(), url: safeUrl(match[3]), cited: match[5] === 'cited'})
  }
  if (!sources.length || sources.length > 10) return {body: text, sources: []}
  return {body: text.slice(0, at).replace(/\s+$/, ''), sources}
}
