// @vitest-environment jsdom
/**
 * Wording on the Tools page that was wrong in the real desktop shell.
 * Each case was read off a screenshot of the Qt window with STAR Server selected.
 */
import {afterEach, describe, expect, it} from 'vitest'
import {cleanup, render, screen} from '@testing-library/react'
import {ReviewToolsPanel} from './ReviewToolsPanel'
import {backendSettings} from './fake-desktop'
import type {AppSettings} from './types'

afterEach(cleanup)
const nothing = () => {}
const panel = (provider: AppSettings['provider']) =>
  render(<ReviewToolsPanel settings={{...backendSettings, provider} as AppSettings} onChange={nothing} recipes={[]} query="" onQuery={nothing}
    preview="" busy="" disabled={false} refresh={nothing} runPreview={nothing} approve={nothing} disable={nothing}/>)

describe('specialist concurrency', () => {
  it('does not talk about this PC or its graphics memory while STAR Server runs the model', () => {
    panel('star_server')
    expect(screen.getByLabelText('Specialist concurrency')).toBeTruthy()
    expect(screen.queryByText(/VRAM|Local specialist/)).toBeNull()
    expect(screen.getByRole('option', {name: '1 specialist at a time'})).toBeTruthy()
    expect(screen.getByRole('option', {name: /2 specialists at a time \(needs 2 free server slots\)/})).toBeTruthy()
  })

  it('keeps the on-device wording for the model on this PC', () => {
    panel('local')
    expect(screen.getByLabelText('Local specialist concurrency')).toBeTruthy()
    expect(screen.getByRole('option', {name: /recommended for 8 GB VRAM/})).toBeTruthy()
  })
})
