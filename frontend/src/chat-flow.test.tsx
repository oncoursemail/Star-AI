// @vitest-environment jsdom
/**
 * Chat behaviour, exercised through the real app root against a fake Qt bridge.
 *
 * Contract under test: bridge messages out (`sendMessage`, `cancelMessage`,
 * `bootstrap`), bridge events in (progress deltas, result, error) and the text
 * the user can read. Nothing here depends on class names, markup structure or
 * styling, so the interface can be redesigned without touching these tests.
 */
import {afterEach, beforeAll, beforeEach, describe, expect, it} from 'vitest'
import {cleanup, render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {backendSettings, installFakeDesktop, type FakeDesktop} from './fake-desktop'

let desktop: FakeDesktop
// App loads the desktop workspace as a lazy chunk; load it once up front so the first test's
// findBy* timeout measures the UI, not the module transform.
beforeAll(async () => { desktop = installFakeDesktop(); await import('./Desktop') }, 60_000)
beforeEach(() => desktop.reset())
afterEach(cleanup)

const composer = () => screen.getByRole('textbox', {name: /message star/i})
const sendButton = () => screen.queryByRole('button', {name: /send message/i})
const stopButton = () => screen.queryByRole('button', {name: /stop/i})
const retryButton = () => screen.queryByRole('button', {name: /retry/i})
const seen = (text: string) => screen.queryAllByText((_, node) => node?.textContent === text && !node.children.length)
const conversation = () => within(screen.getByRole('log'))

async function openChat(messages: Parameters<FakeDesktop['reset']>[0] = [], retry: Parameters<FakeDesktop['reset']>[1] = null, host?: Record<string, unknown>) {
  desktop.reset(messages, retry)
  if (host) desktop.host(host)
  const user = userEvent.setup()
  render(<App/>)
  await screen.findByRole('textbox', {name: /message star/i})
  await waitFor(() => expect(desktop.sent('bootstrap').length).toBeGreaterThan(0))
  return user
}
async function say(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.type(composer(), text)
  await user.keyboard('{Enter}')
}

describe('sending a message', () => {
  it('sends the typed text once, shows it immediately and clears the composer', async () => {
    const user = await openChat()
    await say(user, 'Plan a obby with three checkpoints')
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(1))
    expect(desktop.sent('sendMessage')[0].payload).toMatchObject({prompt: 'Plan a obby with three checkpoints'})
    expect(seen('Plan a obby with three checkpoints')).toHaveLength(1)
    expect((composer() as HTMLTextAreaElement).value).toBe('')
  })

  it('does not send an empty or whitespace-only message', async () => {
    const user = await openChat()
    expect(sendButton()).toHaveProperty('disabled', true)
    await user.type(composer(), '   ')
    await user.keyboard('{Enter}')
    expect(desktop.sent('sendMessage')).toHaveLength(0)
  })

  it('treats Shift+Enter as a newline, not a send', async () => {
    const user = await openChat()
    await user.type(composer(), 'line one{Shift>}{Enter}{/Shift}line two')
    expect(desktop.sent('sendMessage')).toHaveLength(0)
    expect((composer() as HTMLTextAreaElement).value).toBe('line one\nline two')
  })

  it('shows the work in progress and offers Stop instead of Send while the turn runs', async () => {
    const user = await openChat()
    await say(user, 'hello')
    await waitFor(() => expect(stopButton()).not.toBeNull())
    expect(sendButton()).toBeNull()
    desktop.phase(desktop.requestOf('sendMessage'), 'STAR · Fast chat')
    expect(await screen.findByText(/Fast chat/)).toBeTruthy()
  })
})

describe('streaming and completion', () => {
  it('renders streamed deltas as they arrive, then replaces them with exactly one final answer', async () => {
    const user = await openChat()
    await say(user, 'say hi')
    const id = await waitFor(() => desktop.requestOf('sendMessage'))

    desktop.delta(id, 'Hel')
    expect(await screen.findByText('Hel')).toBeTruthy()
    desktop.delta(id, 'lo there')
    expect(await screen.findByText('Hello there')).toBeTruthy()

    desktop.complete(id, 'Hello there, friend.')
    expect(await screen.findByText('Hello there, friend.')).toBeTruthy()
    await waitFor(() => expect(seen('Hello there')).toHaveLength(0)) // partial bubble is gone
    expect(seen('Hello there, friend.')).toHaveLength(1)
    expect(seen('say hi')).toHaveLength(1) // history was reloaded from the backend, not duplicated
    expect(stopButton()).toBeNull()
    expect(retryButton()).toBeNull()
    expect(composer()).toHaveProperty('disabled', false)
  })

  it('reloads the persisted conversation once the result arrives', async () => {
    const user = await openChat()
    const before = desktop.sent('bootstrap').length
    await say(user, 'save this')
    desktop.complete(await waitFor(() => desktop.requestOf('sendMessage')), 'Saved.')
    await waitFor(() => expect(desktop.sent('bootstrap').length).toBe(before + 1))
  })

  it('ignores stray events for requests it is not waiting on', async () => {
    const user = await openChat()
    await say(user, 'first')
    const id = await waitFor(() => desktop.requestOf('sendMessage'))
    desktop.complete(id, 'First answer.')
    await screen.findByText('First answer.')

    desktop.delta(id, 'LATE-TOKEN-FROM-FINISHED-TURN')       // same id, already finished
    desktop.delta('request-the-page-never-made', 'FOREIGN-TOKEN')
    desktop.emitRaw('request-the-page-never-made', 'error', 'FOREIGN-ERROR')
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(screen.queryByText(/LATE-TOKEN/)).toBeNull()
    expect(screen.queryByText(/FOREIGN/)).toBeNull()
    expect(stopButton()).toBeNull()
  })
})

describe('stopping a turn', () => {
  it('asks the backend to cancel and shows the stopped state once the backend confirms', async () => {
    const user = await openChat()
    await say(user, 'write a very long story')
    const id = await waitFor(() => desktop.requestOf('sendMessage'))
    desktop.delta(id, 'Once upon a')
    await screen.findByText('Once upon a')

    await user.click(await waitFor(() => stopButton()!))
    await waitFor(() => expect(desktop.sent('cancelMessage')).toHaveLength(1))
    expect(desktop.sent('sendMessage')).toHaveLength(1) // Stop must not start a new turn

    const stopped = 'Request stopped. The draft answer has not been saved as a completed result.'
    desktop.fail(id, stopped, 'cancelled')
    expect((await screen.findAllByText(stopped)).length).toBeGreaterThan(0)
    expect(stopButton()).toBeNull()
    expect(screen.queryByText('Once upon a')).toBeNull() // the unsaved draft is discarded
    expect(composer()).toHaveProperty('disabled', false)
    expect(retryButton()).not.toBeNull()
  })
})

describe('failure and retry', () => {
  const offline = 'Cannot reach STAR Brain. Start it on the Model page, then test the connection again.'

  it('shows the failure, keeps the question, and Retry re-sends the same text', async () => {
    const user = await openChat()
    await say(user, 'build a shop UI')
    const first = await waitFor(() => desktop.requestOf('sendMessage'))
    desktop.fail(first, offline)

    expect((await screen.findAllByText(offline)).length).toBeGreaterThan(0)
    expect(seen('build a shop UI')).toHaveLength(1)
    expect(composer()).toHaveProperty('disabled', false)

    await user.click(retryButton()!)
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(2))
    expect(desktop.sent('sendMessage')[1].payload).toMatchObject({prompt: 'build a shop UI'})
    expect(retryButton()).toBeNull() // hidden while the retry runs

    const second = desktop.requestOf('sendMessage')
    expect(second).not.toBe(first)
    desktop.complete(second, 'Here is the shop UI.')
    expect(await screen.findByText('Here is the shop UI.')).toBeTruthy()
    expect(retryButton()).toBeNull()
    // The history is the truthful attempt log: ask, failure notice, ask again, answer.
    const kinds = conversation().getAllByRole('article').map(node => {
      const text = node.textContent ?? ''
      return /Cannot reach STAR Brain/.test(text) ? 'failure notice' : /Here is the shop UI/.test(text) ? 'answer'
        : /build a shop UI/.test(text) ? 'question' : 'other'
    })
    expect(kinds).toEqual(['question', 'failure notice', 'question', 'answer'])
  })

  it('recovers when the host refuses the request outright', async () => {
    const user = await openChat()
    desktop.onAction('sendMessage', () => ({ok: false, error: 'STAR is already handling a task'}))
    await say(user, 'second request')
    expect((await screen.findAllByText(/already handling a task/)).length).toBeGreaterThan(0)
    await waitFor(() => expect(retryButton()).not.toBeNull())
    expect(stopButton()).toBeNull()
    expect(composer()).toHaveProperty('disabled', false)

    desktop.reset([], null) // the host is free again
    await user.click(retryButton()!)
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(1))
    expect(desktop.sent('sendMessage')[0].payload).toMatchObject({prompt: 'second request'})
  })
})

describe('duplicate sends', () => {
  it('cannot send a second message while a turn is running', async () => {
    const user = await openChat()
    await say(user, 'first question')
    const id = await waitFor(() => desktop.requestOf('sendMessage'))

    await user.type(composer(), 'impatient follow-up')
    await user.keyboard('{Enter}{Enter}')
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(desktop.sent('sendMessage')).toHaveLength(1)
    expect((composer() as HTMLTextAreaElement).value).toBe('impatient follow-up') // nothing was lost

    desktop.complete(id, 'First answer.')
    await screen.findByText('First answer.')
    await waitFor(() => expect(sendButton()).not.toBeNull())
    await user.keyboard('{Enter}') // now it is allowed
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(2))
    expect(desktop.sent('sendMessage')[1].payload).toMatchObject({prompt: 'impatient follow-up'})
  })

  // Send and Stop share one place, so the second click of a double-click lands on Stop.
  // Stop ignores a click whose click count is above one; a later single click still stops the turn.
  it('a double-click on Send does not cancel the turn it just started', async () => {
    const user = await openChat()
    await user.type(composer(), 'hello')
    await user.dblClick(sendButton()!)
    await new Promise(resolve => setTimeout(resolve, 50))
    expect(desktop.sent('sendMessage')).toHaveLength(1)
    expect(desktop.sent('cancelMessage')).toHaveLength(0)
    // The turn is still running and can be stopped deliberately.
    await user.click(stopButton()!)
    await waitFor(() => expect(desktop.sent('cancelMessage')).toHaveLength(1))
  })

  it('sends one request when Enter is pressed repeatedly on a single message', async () => {
    const user = await openChat()
    await user.type(composer(), 'only once')
    await user.keyboard('{Enter}{Enter}{Enter}')
    await new Promise(resolve => setTimeout(resolve, 30))
    expect(desktop.sent('sendMessage')).toHaveLength(1)
  })
})

describe('history after a restart', () => {
  const failed = 'Cannot reach STAR Brain. Start it on the Model page, then test the connection again.'

  it('shows a persisted failure record next to the question it belongs to', async () => {
    await openChat(
      [{id: '', role: 'user', text: 'make the lobby', created: ''},
       {id: '', role: 'event', text: failed, created: '', status: 'failed'}],
      {status: 'failed', detail: failed, prompt: 'make the lobby', message_id: 1, created: ''})
    const texts = conversation().getAllByRole('article').map(node => node.textContent ?? '')
    expect(texts).toHaveLength(2)
    expect(texts[0]).toContain('make the lobby')
    expect(texts[1]).toContain(failed)
    expect(stopButton()).toBeNull()
    expect(composer()).toHaveProperty('disabled', false)
  })

  // Backend contract (star/react_shell.py _get_state): `retry` = {status, detail, prompt, ...} survives restarts.
  it('offers Retry for the unanswered question straight after a restart, using state.retry', async () => {
    const user = await openChat(
      [{id: '', role: 'user', text: 'make the lobby', created: ''},
       {id: '', role: 'event', text: failed, created: '', status: 'failed'}],
      {status: 'failed', detail: failed, prompt: 'make the lobby', message_id: 1, created: ''})
    await user.click(await waitFor(() => retryButton()!))
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(1))
    expect(desktop.sent('sendMessage')[0].payload).toMatchObject({prompt: 'make the lobby', retryMessageId: 1})
    expect(retryButton()).toBeNull() // hidden while the retry runs
  })

  it('offers Retry when STAR was closed before any reply or failure was recorded', async () => {
    const detail = 'No reply was recorded for this message. STAR may have been closed before it finished.'
    const user = await openChat(
      [{id: '', role: 'user', text: 'make the lobby', created: ''}],
      {status: 'interrupted', detail, prompt: 'make the lobby', message_id: 1, created: ''})
    expect((await screen.findAllByText(detail)).length).toBeGreaterThan(0)
    await user.click(retryButton()!)
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(1))
    expect(desktop.sent('sendMessage')[0].payload).toMatchObject({prompt: 'make the lobby', retryMessageId: 1})
    expect(seen('make the lobby')).toHaveLength(1)
    desktop.complete(desktop.requestOf('sendMessage'), 'Recovered reply.')
    expect(await screen.findByText('Recovered reply.')).toBeTruthy()
    expect(seen('make the lobby')).toHaveLength(1)
  })

  it('does not offer Retry on an old failure once a later question was answered', async () => {
    await openChat(
      [{id: '', role: 'user', text: 'make the lobby', created: ''},
       {id: '', role: 'event', text: failed, created: '', status: 'failed'},
       {id: '', role: 'user', text: 'make the lobby', created: ''},
       {id: '', role: 'assistant', text: 'Here is the lobby.', created: ''}],
      null)
    expect((await screen.findAllByText(failed)).length).toBeGreaterThan(0) // history keeps the failed attempt
    expect(retryButton()).toBeNull()
  })
})

describe('connection status with a STAR Server', () => {
  const server = {...backendSettings, provider: 'star_server', model: 'star-fast', server_endpoint: 'http://192.168.1.20:8080/v1'}
  const check = (ok: boolean | null) => ({selected: true, configured: true, key_present: true, model_selected: true, ok, code: '', checked_at: ''})
  /** The composer's status control; its title is "<provider · model> — <state>". */
  const statusLine = () => screen.getByTitle(/^STAR Server/).getAttribute('title') ?? ''

  it('asks the host to check the server at start and shows the result without a message being sent', async () => {
    desktop.reset()
    desktop.host({settings: server, server: check(null)})
    desktop.onAction('warmUp', () => ({ok: true, pending: true}))
    render(<App/>)
    await screen.findByRole('textbox', {name: /message star/i})
    expect(statusLine()).toMatch(/Not checked$/)
    const id = await waitFor(() => desktop.requestOf('warmUp'))
    expect(desktop.sent('warmUp')).toHaveLength(1)
    // The host finished its cheap check; priming the prompt cache is still running.
    desktop.host({server: check(true)})
    await desktop.emitRaw(id, 'progress', {phase: 'Server checked'})
    await waitFor(() => expect(statusLine()).toMatch(/Ready$/))
    await desktop.emitRaw(id, 'result', {primed: true, ok: true})
    // It was not a turn: nothing was sent, nothing was added to the conversation, no notice.
    expect(desktop.sent('sendMessage')).toHaveLength(0)
    expect(screen.queryByText(/primed|Server checked/)).toBeNull()
    expect(sendButton()).not.toBeNull()
    expect(desktop.sent('warmUp')).toHaveLength(1)
  })

  it('stops saying Connected once another server address is saved', async () => {
    const user = await openChat([], null, {settings: server, server: check(null)})
    expect(statusLine()).toMatch(/Not checked$/)
    await say(user, 'hello')
    desktop.complete(await waitFor(() => desktop.requestOf('sendMessage')), 'Hi.')
    await waitFor(() => expect(statusLine()).toMatch(/Connected$/))

    // The owner saves another address. Nothing has talked to it yet, so the answer above proves nothing about it.
    const moved = {...server, server_endpoint: 'http://192.168.1.21:8080/v1'}
    desktop.onAction('saveSettings', () => { desktop.host({settings: moved}); return {ok: true, data: moved} })
    await user.click(screen.getByRole('button', {name: /^Settings/}))
    await user.click(await screen.findByRole('button', {name: /save settings/i}))
    await waitFor(() => expect(desktop.sent('saveSettings')).toHaveLength(1))
    await user.click(screen.getByRole('button', {name: /back to chat/i}))
    await waitFor(() => expect(statusLine()).toMatch(/Not checked$/))
  })

  it('tells the Model page about a failed send, so the page the failure row leads to agrees with the chat', async () => {
    const unreachable = 'Cannot reach STAR Server. Check that the server is switched on, that this PC is on the same network, and that the address and port are right.'
    const user = await openChat([], null, {settings: server, server: check(null)})
    await say(user, 'hello')
    const id = await waitFor(() => desktop.requestOf('sendMessage'))
    desktop.host({server: check(false)}) // the host records the failed request before it emits the error
    desktop.fail(id, unreachable)
    expect((await screen.findAllByText(unreachable)).length).toBeGreaterThan(0)
    expect(seen('hello')).toHaveLength(1) // re-reading the connection must not touch the conversation

    await user.click(conversation().getByRole('button', {name: 'Model & connection'}))
    expect(await screen.findByText(/Status: needs attention/)).toBeTruthy()
    expect(screen.queryByText(/Status: not checked yet/)).toBeNull()
  })

  it('tells the Model page about a passed "Test actual response"', async () => {
    const user = await openChat([], null, {settings: server, server: check(null)})
    desktop.onAction('testModel', () => ({ok: true, pending: true})) // the real host answers on a worker thread
    await user.click(screen.getByRole('button', {name: /^Settings/}))
    await user.click(await screen.findByRole('button', {name: /test actual response/i}))
    const id = await waitFor(() => desktop.requestOf('testModel'))
    desktop.host({server: check(true)})
    desktop.emitRaw(id, 'result', {ok: true, model: 'star-fast', sample: 'STAR is ready.'})
    await user.click(screen.getByRole('button', {name: 'Model'}))
    expect(await screen.findByText(/Status: ready/)).toBeTruthy()
  })
})

describe('notices', () => {
  it('does not carry a notice from another page over the conversation', async () => {
    const user = await openChat([{id: '', role: 'user', text: 'hello', created: ''}, {id: '', role: 'assistant', text: 'Hi.', created: ''}])
    desktop.onAction('saveSettings', call => ({ok: true, data: call.payload.settings}))
    await user.click(screen.getByRole('button', {name: /^Settings/}))
    await user.click(await screen.findByRole('button', {name: /save settings/i}))
    expect(await screen.findByText('Settings saved.')).toBeTruthy()

    await user.click(screen.getByRole('button', {name: /back to chat/i}))
    await screen.findByRole('textbox', {name: /message star/i})
    expect(screen.queryByText('Settings saved.')).toBeNull()
    expect(seen('Hi.')).toHaveLength(1)
  })
})
