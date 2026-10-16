// @vitest-environment jsdom
/**
 * Settings > Answers > Start thinking while I type, through the real app root against a fake Qt bridge.
 *
 * Contract: with the setting on, a pause in typing sends `warmDraft` with the trimmed draft and the chat mode;
 * small additions are not re-sent; with it off (the default) nothing is sent; Enter still sends `sendMessage`.
 */
import {afterEach, beforeAll, beforeEach, describe, expect, it} from 'vitest'
import {cleanup, render, screen, waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {backendSettings, installFakeDesktop, type FakeDesktop} from './fake-desktop'
import {DRAFT_PAUSE_MS, draftToWarm} from './draftWarm'

let desktop: FakeDesktop
beforeAll(async () => { desktop = installFakeDesktop(); await import('./Desktop') }, 60_000)
beforeEach(() => desktop.reset())
afterEach(cleanup)

const pause = () => new Promise(resolve => setTimeout(resolve, DRAFT_PAUSE_MS + 250))

async function composer(prefill: boolean) {
  desktop.host({settings: {...backendSettings, prefill_while_typing: prefill}})
  const user = userEvent.setup()
  render(<App/>)
  const box = await screen.findByRole('textbox', {name: /message star/i})
  await waitFor(() => expect(desktop.sent('bootstrap').length).toBeGreaterThan(0))
  return {user, box}
}

describe('draftToWarm', () => {
  it('sends a long enough new draft, trimmed, and skips small growth', () => {
    expect(draftToWarm('', '  How do I make  ')).toBe('How do I make')
    expect(draftToWarm('', 'hi there')).toBe('')                                   // too short
    expect(draftToWarm('How do I make', 'How do I make a')).toBe('')              // grew by 2
    expect(draftToWarm('How do I make', 'How do I make a red door')).toBe('How do I make a red door')
    expect(draftToWarm('How do I make a door', 'How do I make a doo')).toBe('How do I make a doo')   // an edit
    expect(draftToWarm('How do I make a door', 'How do I make a door')).toBe('')
  })
})

describe('Start thinking while I type', () => {
  it('sends the draft after a pause, then the message on Enter', async () => {
    const {user, box} = await composer(true)
    await user.type(box, 'How do I make a door open')
    await pause()
    expect(desktop.sent('warmDraft').map(call => call.payload)).toEqual(
      [{prompt: 'How do I make a door open', mode: 'auto', research: false}])
    await user.type(box, ' ok')                                                    // small growth: not re-sent
    await pause()
    expect(desktop.sent('warmDraft')).toHaveLength(1)
    await user.type(box, '{Enter}')
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(1))
    expect(desktop.sent('sendMessage')[0].payload.prompt).toBe('How do I make a door open ok')
  }, 20_000)

  it('sends nothing while switched off', async () => {
    const {user, box} = await composer(false)
    await user.type(box, 'How do I make a door open')
    await pause()
    expect(desktop.sent('warmDraft')).toHaveLength(0)
  }, 20_000)
})
