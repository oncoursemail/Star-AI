// @vitest-environment jsdom
/** Instant routing is opt-in; observed answer statistics are visible independently. */
import {afterEach, beforeAll, beforeEach, describe, expect, it} from 'vitest'
import {cleanup, render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {applyProgress, settleRun, startRun} from './activity'
import {backendSettings, installFakeDesktop, type FakeDesktop} from './fake-desktop'

let desktop: FakeDesktop
beforeAll(async () => { desktop = installFakeDesktop(); await import('./Desktop') }, 60_000)
beforeEach(() => desktop.reset())
afterEach(cleanup)

async function openChat(host?: Record<string, unknown>) {
  if (host) desktop.host(host)
  const user = userEvent.setup()
  render(<App/>)
  await screen.findByRole('textbox', {name: /message star/i})
  await waitFor(() => expect(desktop.sent('bootstrap').length).toBeGreaterThan(0))
  return user
}

async function say(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.type(screen.getByRole('textbox', {name: /message star/i}), text)
  await user.keyboard('{Enter}')
  return await waitFor(() => desktop.requestOf('sendMessage'))
}

const seen = (text: string) => screen.queryAllByText((_, node) => node?.textContent === text && !node.children.length)


describe('instant setting disclosure and persistence', () => {
  it.each([false, null, undefined])('treats %s as off and discloses context loss before opting in', async value => {
    let settings = {...backendSettings, instant_route_enabled: value as boolean | null | undefined}
    desktop.onAction('saveSettings', call => {
      settings = {...settings, ...(call.payload.settings as Partial<typeof settings>)}
      desktop.host({settings})
      return {ok: true, data: settings}
    })
    const user = await openChat({settings})
    await user.click(screen.getByRole('button', {name: /^Settings/}))
    await user.click(await screen.findByText('Advanced settings'))
    const control = await screen.findByRole('checkbox', {name: /^Instant answers on this PC/})
    expect(control).toHaveProperty('checked', false)
    expect(await screen.findByText(/Instant answers do not use the conversation, lessons or memory\./)).toBeTruthy()
    expect(desktop.sent('saveSettings')).toHaveLength(0)

    await user.click(control)
    expect(control).toHaveProperty('checked', true)
    await user.click(screen.getByRole('button', {name: /^Save settings$/}))
    await waitFor(() => expect(desktop.sent('saveSettings')).toHaveLength(1))
    expect(desktop.sent('saveSettings')[0].payload.settings).toMatchObject({instant_route_enabled: true})
    await screen.findByText('Settings saved.')
    expect(desktop.snapshot().settings).toMatchObject({instant_route_enabled: true})

    await user.click(control)
    await user.click(screen.getByRole('button', {name: /^Save settings$/}))
    await waitFor(() => expect(desktop.sent('saveSettings')).toHaveLength(2))
    expect(desktop.sent('saveSettings')[1].payload.settings).toMatchObject({instant_route_enabled: false})
  })
})


describe('instant answer origin and speed', () => {
  it('shows the actual PC brain, measured speed and one persisted answer', async () => {
    const user = await openChat({
      settings: {...backendSettings, provider: 'star_server', instant_route_enabled: true},
      brain_installed: true, brain_running: true,
    })
    const id = await say(user, 'What is a palindrome?')
    desktop.emitRaw(id, 'progress', {phase: 'STAR · Fast answer',
      activity: {type: 'route', profile: 'fast', model: 'server-model'}})
    desktop.emitRaw(id, 'progress', {phase: 'Answering on this PC',
      activity: {type: 'instant', model: 'pc-small'}})
    desktop.emitRaw(id, 'progress', {phase: 'Answer complete',
      activity: {type: 'answer_stats', brain: 'pc', model: 'pc-small',
        first_token_ms: 80, tokens_per_second: 20.0, estimated_tokens: false}})
    desktop.complete(id, 'It reads the same backwards.')
    expect(await screen.findByText('It reads the same backwards.')).toBeTruthy()
    const activity = within(await screen.findByRole('region', {name: 'What STAR did'}))
    expect(activity.getByText(/answered on this PC/)).toBeTruthy()
    expect(activity.getByText(/80 ms first token/)).toBeTruthy()
    expect(activity.getByText(/20\.0 tok\/s/)).toBeTruthy()
    expect(activity.queryByText(/≈/)).toBeNull()
    expect(seen('It reads the same backwards.')).toHaveLength(1)
    expect(desktop.sent('sendMessage')).toHaveLength(1)
    expect(desktop.saved().filter(row => row.role === 'assistant')).toHaveLength(1)
  })

  it('shows the server model and explicitly estimated rate after instant fallback', async () => {
    const user = await openChat({settings: {...backendSettings, provider: 'star_server', instant_route_enabled: true}})
    const id = await say(user, 'What is a palindrome?')
    desktop.emitRaw(id, 'progress', {phase: 'On-device answer unavailable; using STAR Server',
      activity: {type: 'instant_fallback', model: 'server-model'}})
    desktop.emitRaw(id, 'progress', {phase: 'Answer complete',
      activity: {type: 'answer_stats', brain: 'server', model: 'server-model',
        first_token_ms: 215, tokens_per_second: 14.3, estimated_tokens: true}})
    desktop.complete(id, 'Server reply.')
    expect(await screen.findByText('Server reply.')).toBeTruthy()
    const activity = within(await screen.findByRole('region', {name: 'What STAR did'}))
    expect(activity.getByText(/server-model/)).toBeTruthy()
    expect(activity.getByText(/215 ms first token/)).toBeTruthy()
    expect(activity.getByText(/≈14\.3 tok\/s/)).toBeTruthy()
    expect(seen('Server reply.')).toHaveLength(1)
    expect(desktop.sent('sendMessage')).toHaveLength(1)
    expect(desktop.saved().filter(row => row.role === 'assistant')).toHaveLength(1)
  })

  it('keeps ordinary server statistics visible with instant routing disabled', async () => {
    const user = await openChat({settings: {...backendSettings, provider: 'star_server', instant_route_enabled: false}})
    const id = await say(user, 'Hello')
    // No instant-selection or fallback event: telemetry is independent of the opt-in switch.
    desktop.emitRaw(id, 'progress', {activity: {type: 'answer_stats', brain: 'server',
      model: 'server-model', first_token_ms: 125, tokens_per_second: 8.0, estimated_tokens: true}})
    desktop.complete(id, 'Ordinary server answer.')
    expect(await screen.findByText('Ordinary server answer.')).toBeTruthy()
    const activity = within(await screen.findByRole('region', {name: 'What STAR did'}))
    expect(activity.getByText(/server-model/)).toBeTruthy()
    expect(activity.getByText(/125 ms first token/)).toBeTruthy()
    expect(activity.getByText(/≈8\.0 tok\/s/)).toBeTruthy()
    expect(activity.queryByText(/answered on this PC/)).toBeNull()
  })
})


it('reduces observed PC and fallback statistics without inventing work steps', () => {
  let local = startRun('local', 'chat', 0)
  local = applyProgress(local, {activity: {type: 'route', profile: 'fast', model: 'server-model'}}, 1)
  local = applyProgress(local, {activity: {type: 'instant', model: 'pc-small'}}, 2)
  expect(local.phase).toBe('Answering on this PC')
  local = applyProgress(local, {activity: {type: 'answer_stats', brain: 'pc', model: 'pc-small',
    first_token_ms: 80, tokens_per_second: 20, estimated_tokens: false}}, 3)
  expect(local).toMatchObject({brain: 'pc', model: 'pc-small', firstTokenMs: 80,
    tokensPerSecond: 20, estimatedTokens: false})
  expect(local.steps).toHaveLength(0)
  expect(settleRun(local, 'done', 4).model).toBe('pc-small')

  let fallback = startRun('fallback', 'chat', 0)
  fallback = applyProgress(fallback, {activity: {type: 'instant_fallback', model: 'server-model'}}, 1)
  expect(fallback.phase).toBe('Using STAR Server')
  fallback = applyProgress(fallback, {activity: {type: 'answer_stats', brain: 'server', model: 'server-model',
    first_token_ms: 123, tokens_per_second: 12.5, estimated_tokens: true}}, 2)
  expect(fallback).toMatchObject({brain: 'server', model: 'server-model', firstTokenMs: 123,
    tokensPerSecond: 12.5, estimatedTokens: true})
  expect(fallback.steps).toHaveLength(0)
})
