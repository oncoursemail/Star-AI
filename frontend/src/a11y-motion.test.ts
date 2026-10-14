/**
 * Reduced motion and focus, read from the CSS sources (jsdom applies no stylesheets).
 * The browser audit for the PR checked the same in Edge: no running animations under prefers-reduced-motion
 * or STAR's own Reduced motion setting, and a visible change on every focusable control.
 */
import {readFileSync} from 'node:fs'
import {describe, expect, it} from 'vitest'

const source = (name: string) => readFileSync(new URL(name, import.meta.url), 'utf8').replace(/\r\n/g, '\n')

describe('reduced motion', () => {
  const tokens = source('./tokens.css')
  it('stops every animation and transition for the OS setting and for STAR\'s own setting', () => {
    expect(tokens).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*?animation-iteration-count: 1 !important/)
    expect(tokens).toMatch(/\.shell\[data-reduced-motion='true'\] \*,[\s\S]*?animation-duration: 0\.01ms !important;[\s\S]*?transition-duration: 0\.01ms !important/)
  })
  it('turns off the press scale both ways', () => {
    const polish = source('./polish.css')
    expect(polish).toMatch(/@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?:active \{\s*transform: none;/)
    expect(polish).toMatch(/\.shell\[data-reduced-motion='true'\][^{]*:active \{\s*transform: none;/)
  })
})

describe('focus', () => {
  it('keeps a visible ring on the switches and gives Windows high contrast the system control back', () => {
    const polish = source('./polish.css')
    expect(polish).toMatch(/\.setting-switch input\[type='checkbox'\]:focus-visible \{\s*outline: 2px solid/)
    expect(polish).toMatch(/@media \(forced-colors: active\) \{[\s\S]*?appearance: auto;/)
  })
  it('shows the skip link when it is focused', () => {
    expect(source('./polish.css')).toMatch(/\.skip-link:focus,\n\.shell \.skip-link:focus-visible \{\s*transform: none;/)
  })
})
