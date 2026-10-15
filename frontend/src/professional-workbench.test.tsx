// @vitest-environment jsdom
/** The professional workbench must remain a real, usable STAR workspace.
 * These tests validate behavior and structure, NOT subjective aesthetics.
 */
import {afterEach, beforeAll, beforeEach, describe, expect, it} from 'vitest'
import {cleanup, render, screen, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {Desktop} from './Desktop'
import {installFakeDesktop, type FakeDesktop} from './fake-desktop'

let bridge: FakeDesktop
beforeAll(() => { bridge = installFakeDesktop() })
beforeEach(() => { bridge.reset(); try { localStorage.clear() } catch { /* optional */ } })
afterEach(cleanup)

describe('STAR professional desktop structure', () => {
  it('uses a single branded navigation and an editable task-first start canvas', async () => {
    render(<Desktop preview/>)
    const sidebar = screen.getByRole('complementary', {name: 'STAR navigation'})
    const brand = within(sidebar).getByRole('button', {name: 'STAR, back to chat'})
    expect(within(brand).getByText('STAR')).toBeTruthy()
    expect(within(brand).getByText('Intelligence')).toBeTruthy()
    expect(screen.getByRole('heading', {name: 'Make something worth keeping.'})).toBeTruthy()

    const actions = within(screen.getByRole('group', {name: 'Starting points'})).getAllByRole('button')
    expect(actions).toHaveLength(4)
    await userEvent.click(actions[0])
    expect((screen.getByRole('textbox', {name: 'Message STAR'}) as HTMLTextAreaElement).value)
      .toMatch(/native Roblox hierarchy/)
    // No model call or permission change is allowed by a starter click.
    expect(bridge.sent('sendMessage')).toHaveLength(0)
    expect(bridge.sent('saveSettings')).toHaveLength(0)
  })

  it('marks the actual current workspace rather than a decorative status badge', async () => {
    render(<Desktop preview/>)
    await userEvent.click(screen.getByRole('button', {name: /^Projects/}))
    const main = screen.getByRole('main')
    expect(within(main).getByRole('heading', {name: 'Your workspaces'})).toBeTruthy()
    const current = within(main).getByRole('button', {name: /STAR Current workspace/})
    expect(current.getAttribute('aria-current')).toBe('page')
    expect(within(main).getByRole('textbox', {name: 'New project name'})).toBeTruthy()
  })

  it('keeps advanced pages accessible without occupying the primary navigation', async () => {
    render(<Desktop preview/>)
    const nav = screen.getByRole('navigation', {name: 'Workspace'})
    expect(within(nav).queryByRole('button', {name: 'Analytics'})).toBeNull()
    await userEvent.click(within(nav).getByRole('button', {name: 'More'}))
    expect(within(nav).getByRole('button', {name: 'Analytics'})).toBeTruthy()
    expect(within(nav).getByRole('button', {name: 'Brain'})).toBeTruthy()
    expect(screen.getByRole('textbox', {name: 'Message STAR'})).toBeTruthy()
  })
})
