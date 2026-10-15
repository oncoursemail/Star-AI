/**
 * The longest prompt STAR Desktop accepts for each kind of request. These mirror the checks in
 * star/react_shell.py (sendMessage, runTeam, generateImage): a longer prompt is refused there, so the
 * composer stops it before it becomes a failed turn that Retry cannot fix.
 */
export const PROMPT_LIMITS = {chat: 30000, team: 12000, image: 1500} as const
export type PromptKind = keyof typeof PROMPT_LIMITS

/** The counter appears once a prompt passes this share of its limit. */
export const COUNTER_FROM = 0.8

/** Length as the host counts it: Python's len() of the trimmed text, i.e. Unicode code points (an emoji is 1). */
export function promptLength(text: string): number {
  let count = 0
  for (const _ of text.trim()) count++
  return count
}

export function promptKind(imageMode: boolean, teamMode: boolean): PromptKind {
  return imageMode ? 'image' : teamMode ? 'team' : 'chat'
}

const NOUN: Record<PromptKind, string> = {chat: 'a message', team: 'a team objective', image: 'an image description'}
const ADVICE: Record<PromptKind, string> = {
  chat: 'Attach long text as a .txt file instead.',
  team: 'Shorten it, or turn Team off to send it as a chat message.',
  image: 'Describe the picture more briefly.',
}

/** null when the prompt fits, else a plain sentence saying by how much it is over and what to do. */
export function overLimitMessage(text: string, kind: PromptKind): string | null {
  const length = promptLength(text)
  const limit = PROMPT_LIMITS[kind]
  if (length <= limit) return null
  const over = length - limit
  return `Too long for ${NOUN[kind]}: ${over.toLocaleString('en-US')} character${over === 1 ? '' : 's'} over the ${limit.toLocaleString('en-US')} limit. ${ADVICE[kind]}`
}
