import {useEffect, useRef} from 'react'

/** Settings > Start thinking while I type (star/prefill_warm.py). After a short pause in typing, the host lets the
 *  model server read the conversation and the draft, so the answer starts sooner on Enter. Never changes the answer. */
export const DRAFT_PAUSE_MS = 600
/** Shorter drafts are not sent (the host has the same floor). */
export const DRAFT_MIN_CHARS = 12
/** A draft that only grew by fewer characters than this since the last one sent is not worth another request. */
export const DRAFT_MIN_NEW = 8

/** The draft to send now, or '' when the last one sent already covers it. */
export function draftToWarm(lastSent: string, value: string): string {
  const text = value.trim()
  if (text.length < DRAFT_MIN_CHARS || text === lastSent) return ''
  if (lastSent && text.startsWith(lastSent) && text.length - lastSent.length < DRAFT_MIN_NEW) return ''
  return text
}

/** Sends `warmDraft` after each pause in typing while `enabled`. */
export function useDraftWarm(enabled: boolean, value: string, send: (text: string) => void) {
  const lastSent = useRef('')
  const sendRef = useRef(send)
  sendRef.current = send
  useEffect(() => {
    if (!value.trim()) lastSent.current = ''   // sent or cleared: the next draft starts afresh
    if (!enabled) return
    const timer = window.setTimeout(() => {
      const text = draftToWarm(lastSent.current, value)
      if (!text) return
      lastSent.current = text
      sendRef.current(text)
    }, DRAFT_PAUSE_MS)
    return () => window.clearTimeout(timer)
  }, [enabled, value])
}
