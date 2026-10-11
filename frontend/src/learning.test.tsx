// @vitest-environment jsdom
/**
 * Learning in the interface: thumbs on answers, the review list, and the counts.
 *
 * Contract under test: what the page sends to the desktop host (`messageFeedback`,
 * `listLessons`, `reviewLesson` with the owner's explicit `approved`, `saveSettings`)
 * and the text the owner reads. No class names, no markup structure.
 */
import {afterEach, beforeAll, beforeEach, describe, expect, it, vi} from 'vitest'
import {cleanup, render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {AnalyticsView} from './Charts'
import {LearningPanel, describeDigest} from './LearningPanel'
import {backendSettings, installFakeDesktop, type FakeDesktop} from './fake-desktop'
import type {Analytics, AppSettings, Lesson, LessonCounts} from './types'

let desktop: FakeDesktop
beforeAll(async () => { desktop = installFakeDesktop(); await import('./Desktop') }, 60_000)
beforeEach(() => desktop.reset())
afterEach(cleanup)

const lesson = (over: Partial<Lesson>): Lesson => ({
  id: 1, project: 'STAR', kind: 'preference', text: 'Always use task.wait instead of wait.', status: 'accepted',
  source: 'chat:c1#4', source_type: 'user', evidence: '', created: '2026-10-10T12:00:00+00:00', updated: '2026-10-10T12:00:00+00:00',
  supersedes_id: null, merged_into: null, uses: 0, last_used: '', origin: 'You said this in a chat (message 4)', ...over})
const counted = (lessons: Lesson[]): LessonCounts => {
  const of = (status: string) => lessons.filter(l => l.status === status).length
  return {candidate: of('candidate'), accepted: of('accepted'), rejected: of('rejected'), superseded: of('superseded'),
    merged: of('merged'), pending: of('candidate'), uses: lessons.reduce((sum, l) => sum + l.uses, 0)}
}
const settings = backendSettings as unknown as AppSettings

/** A host that keeps lessons in memory and answers the review actions like star/lessons.py. */
function lessonHost(initial: Lesson[]) {
  let lessons = initial.slice()
  const calls: Array<{action: string; params: Record<string, unknown>}> = []
  const invoke = vi.fn(async (action: string, params: Record<string, unknown> = {}) => {
    calls.push({action, params})
    if (action === 'listLessons') return {lessons, counts: counted(lessons)}
    if (action === 'reviewLesson') {
      if (params.approved !== true) return null
      const target = lessons.find(l => l.id === params.id)
      if (!target) return null
      if (params.op === 'delete') lessons = lessons.filter(l => l !== target)
      else lessons = lessons.map(l => l !== target ? l : {...l,
        text: typeof params.text === 'string' ? params.text : l.text,
        status: params.op === 'reject' ? 'rejected' : params.op === 'edit' ? l.status : 'accepted'})
      return {lesson: null, counts: counted(lessons)}
    }
    if (action === 'saveSettings') return params.settings
    if (action === 'exportLessons') return {filename: 'STAR-lessons-STAR-20261010.json', count: lessons.length}
    return {}
  })
  return {invoke, calls, sent: (action: string) => calls.filter(c => c.action === action)}
}

describe('rating an answer', () => {
  const saved = [
    {id: '', role: 'user' as const, text: 'How do I debounce a button?', created: ''},
    {id: '', role: 'assistant' as const, text: 'Use a boolean flag.', created: '', mid: 42},
  ]

  it('sends the thumb for that stored answer and shows it as chosen', async () => {
    desktop.reset(saved)
    desktop.onAction('messageFeedback', call => ({ok: true, data: {messageId: call.payload.messageId, value: call.payload.value,
      counts: {candidate: 1, accepted: 0, rejected: 0, superseded: 0, merged: 0, pending: 1, uses: 0}}}))
    const user = userEvent.setup()
    render(<App/>)
    const down = await screen.findByRole('button', {name: 'Not helpful'})
    expect(down.getAttribute('aria-pressed')).toBe('false')
    await user.click(down)
    await waitFor(() => expect(desktop.sent('messageFeedback')).toHaveLength(1))
    expect(desktop.sent('messageFeedback')[0].payload).toEqual({messageId: 42, value: 'down'})
    await waitFor(() => expect(screen.getByRole('button', {name: 'Not helpful'}).getAttribute('aria-pressed')).toBe('true'))
    expect(screen.getByRole('button', {name: 'Helpful'}).getAttribute('aria-pressed')).toBe('false')
    // Pressing the chosen thumb again takes the rating back.
    await user.click(screen.getByRole('button', {name: 'Not helpful'}))
    await waitFor(() => expect(desktop.sent('messageFeedback')).toHaveLength(2))
    expect(desktop.sent('messageFeedback')[1].payload).toEqual({messageId: 42, value: ''})
    await waitFor(() => expect(screen.getByRole('button', {name: 'Not helpful'}).getAttribute('aria-pressed')).toBe('false'))
  })

  it('restores a stored rating after a restart and offers no thumbs on the owner\'s own messages', async () => {
    desktop.reset([saved[0], {...saved[1], feedback: 'up'}])
    render(<App/>)
    const up = await screen.findByRole('button', {name: 'Helpful'})
    expect(up.getAttribute('aria-pressed')).toBe('true')
    expect(screen.getAllByRole('button', {name: 'Helpful'})).toHaveLength(1)
  })

  it('leaves the thumb unchanged when the host refuses', async () => {
    desktop.reset(saved)
    desktop.onAction('messageFeedback', () => ({ok: false, error: 'Feedback must be about one of STAR\'s answers in this project'}))
    const user = userEvent.setup()
    render(<App/>)
    await user.click(await screen.findByRole('button', {name: 'Helpful'}))
    await waitFor(() => expect(desktop.sent('messageFeedback')).toHaveLength(1))
    expect(screen.getByRole('button', {name: 'Helpful'}).getAttribute('aria-pressed')).toBe('false')
  })

  it('says once what a turn taught, from the counts the host reports', async () => {
    const user = userEvent.setup()
    render(<App/>)
    const box = await screen.findByRole('textbox', {name: /message star/i})
    await user.type(box, 'No, use task.wait instead of wait.')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(desktop.sent('sendMessage')).toHaveLength(1))
    await desktop.emitRaw(desktop.requestOf('sendMessage'), 'result', {answer: 'Understood.', learned: {accepted: 1, candidates: 0}})
    expect(await screen.findByText('Noted for this project: 1 lesson from what you said. Review it under Projects.')).toBeTruthy()
  })
})

describe('reviewing lessons', () => {
  const stored = () => [
    lesson({id: 1}),
    lesson({id: 2, kind: 'pitfall', status: 'candidate', source_type: 'retry', text: 'A request failed and was sent again.',
      origin: 'A request failed and you sent it again (message 7)', evidence: 'Failure shown to the owner: timed out'}),
    lesson({id: 3, kind: 'fact', status: 'candidate', source_type: 'summary', text: 'Large shop requests time out.',
      origin: 'Summarised by the fast model from raw captures'}),
    lesson({id: 4, status: 'superseded', text: 'Always use gold accents.'}),
  ]
  const open = (host: ReturnType<typeof lessonHost>, over: Partial<AppSettings> = {}) => {
    const refresh = vi.fn()
    render(<LearningPanel project="STAR" settings={{...settings, ...over}} invoke={host.invoke} refresh={refresh}/>)
    return {user: userEvent.setup(), refresh}
  }

  it('lists what is waiting with its source and the pending count', async () => {
    const host = lessonHost(stored())
    open(host)
    expect(await screen.findByText('A request failed and was sent again.')).toBeTruthy()
    expect(screen.getByText('2 waiting for review')).toBeTruthy()
    expect(screen.getByText(/A request failed and you sent it again \(message 7\)/)).toBeTruthy()
    expect(screen.getByText('Failure shown to the owner: timed out')).toBeTruthy()
    expect(screen.getByText('Large shop requests time out.')).toBeTruthy()
    expect(screen.queryByText('Always use task.wait instead of wait.')).toBeNull()   // accepted: on its own tab
    expect(screen.getByRole('tab', {name: /Waiting 2/}).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('tab', {name: /Accepted 1/})).toBeTruthy()
    expect(screen.getByRole('tab', {name: /Set aside 1/})).toBeTruthy()
  })

  it('shows the host\'s counts and says so when only the newest notes are loaded', async () => {
    // The host sends the newest notes of each status and the true totals (star/lessons.py LIST_WINDOW).
    const many = Array.from({length: 200}, (_, i) => lesson({id: 1000 - i, status: 'candidate', source_type: 'chat-correction',
      text: `No, make part ${i} blue`, origin: 'You said this about one answer'}))
    const invoke = vi.fn(async (action: string) => action === 'listLessons'
      ? {lessons: [...many, lesson({id: 1, uses: 3})], counts: {candidate: 520, accepted: 1, rejected: 0, superseded: 0, merged: 0, pending: 520, uses: 3}}
      : {})
    render(<LearningPanel project="STAR" settings={settings} invoke={invoke}/>)
    expect(await screen.findByText('No, make part 0 blue')).toBeTruthy()
    expect(screen.getByText('520 waiting for review')).toBeTruthy()
    expect(screen.getByRole('tab', {name: /Waiting 520/})).toBeTruthy()
    expect(screen.getByText(/Showing the newest 200 of 520\./)).toBeTruthy()
    expect(screen.getAllByRole('button', {name: /Approve/})).toHaveLength(200)
    // The accepted lesson is on its tab even though 520 newer notes exist, and that tab is complete.
    await userEvent.setup().click(screen.getByRole('tab', {name: /Accepted 1/}))
    expect(screen.getByText('Always use task.wait instead of wait.')).toBeTruthy()
    expect(screen.queryByText(/Showing the newest/)).toBeNull()
    // The count says the lesson was in the prompt, not that the model followed it.
    expect(screen.getByText(/sent with 3 answers/)).toBeTruthy()
    expect(screen.queryByText(/used in 3 answers/)).toBeNull()
  })

  it('approves a candidate only with the owner\'s explicit confirmation flag', async () => {
    const host = lessonHost(stored())
    const {user, refresh} = open(host)
    const row = (await screen.findByText('A request failed and was sent again.')).closest('li') as HTMLElement
    await user.click(within(row).getByRole('button', {name: /approve/i}))
    await waitFor(() => expect(host.sent('reviewLesson')).toHaveLength(1))
    expect(host.sent('reviewLesson')[0].params).toEqual({op: 'approve', id: 2, approved: true})
    expect(await screen.findByText('1 waiting for review')).toBeTruthy()
    expect(screen.getByText(/Accepted\. STAR will use it in this project\./)).toBeTruthy()
    expect(refresh).toHaveBeenCalled()
    await user.click(screen.getByRole('tab', {name: /Accepted 2/}))
    expect(screen.getByText('A request failed and was sent again.')).toBeTruthy()
  })

  it('lets the owner reword a candidate before accepting it', async () => {
    const host = lessonHost(stored())
    const {user} = open(host)
    const row = (await screen.findByText('Large shop requests time out.')).closest('li') as HTMLElement
    await user.click(within(row).getByRole('button', {name: /edit/i}))
    const box = within(row).getByRole('textbox', {name: /new wording/i})
    await user.clear(box)
    await user.type(box, 'Build large shop UIs in parts.')
    await user.click(within(row).getByRole('button', {name: /save and accept/i}))
    await waitFor(() => expect(host.sent('reviewLesson')).toHaveLength(1))
    expect(host.sent('reviewLesson')[0].params).toEqual({op: 'approve', id: 3, approved: true, text: 'Build large shop UIs in parts.'})
  })

  it('rejects, and deletes only after a second confirmation', async () => {
    const host = lessonHost(stored())
    const {user} = open(host)
    const row = () => screen.getByText('A request failed and was sent again.').closest('li') as HTMLElement
    await screen.findByText('A request failed and was sent again.')
    await user.click(within(row()).getByRole('button', {name: /delete/i}))
    expect(host.sent('reviewLesson')).toHaveLength(0)                      // nothing happens on the first press
    expect(within(row()).getByText('Delete this lesson for good?')).toBeTruthy()
    await user.click(within(row()).getByRole('button', {name: /keep/i}))
    await user.click(within(row()).getByRole('button', {name: /reject/i}))
    await waitFor(() => expect(host.sent('reviewLesson')).toHaveLength(1))
    expect(host.sent('reviewLesson')[0].params).toEqual({op: 'reject', id: 2, approved: true})
    await user.click(await screen.findByRole('tab', {name: /Set aside 2/}))
    const aside = screen.getByText('A request failed and was sent again.').closest('li') as HTMLElement
    await user.click(within(aside).getByRole('button', {name: /delete/i}))
    await user.click(within(aside).getByRole('button', {name: /yes, delete/i}))
    await waitFor(() => expect(host.sent('reviewLesson')).toHaveLength(2))
    expect(host.sent('reviewLesson')[1].params).toEqual({op: 'delete', id: 2, approved: true})
    await waitFor(() => expect(screen.queryByText('A request failed and was sent again.')).toBeNull())
  })

  it('restores a replaced lesson and stops using an accepted one', async () => {
    const host = lessonHost(stored())
    const {user} = open(host)
    await screen.findByText('Large shop requests time out.')
    await user.click(screen.getByRole('tab', {name: /Set aside 1/}))
    expect(screen.getByText('Replaced by a newer lesson')).toBeTruthy()
    await user.click(screen.getByRole('button', {name: /restore/i}))
    await waitFor(() => expect(host.sent('reviewLesson')).toHaveLength(1))
    expect(host.sent('reviewLesson')[0].params).toEqual({op: 'restore', id: 4, approved: true})
    await user.click(await screen.findByRole('tab', {name: /Accepted 2/}))
    const row = screen.getByText('Always use task.wait instead of wait.').closest('li') as HTMLElement
    await user.click(within(row).getByRole('button', {name: /stop using/i}))
    await waitFor(() => expect(host.sent('reviewLesson')).toHaveLength(2))
    expect(host.sent('reviewLesson')[1].params).toEqual({op: 'reject', id: 1, approved: true})
  })

  it('saves the review-everything choice at once and exports on request', async () => {
    const host = lessonHost(stored())
    const {user, refresh} = open(host)
    await screen.findByText('Large shop requests time out.')
    const auto = screen.getByRole('checkbox', {name: /accept my own corrections automatically/i}) as HTMLInputElement
    expect(auto.checked).toBe(true)
    await user.click(auto)
    await waitFor(() => expect(host.sent('saveSettings')).toHaveLength(1))
    expect(host.sent('saveSettings')[0].params).toEqual({settings: {learning_auto_accept: false}})
    expect(refresh).toHaveBeenCalled()
    expect(screen.queryByRole('checkbox', {name: /hosted provider/i})).toBeNull()   // own hardware: no cloud switch
    await user.click(screen.getByRole('button', {name: /export/i}))
    expect(await screen.findByText('Exported 4 lessons to STAR-lessons-STAR-20261010.json.')).toBeTruthy()
  })

  it('shows the review-everything state and the hosted-provider switch when they apply', async () => {
    const host = lessonHost([])
    open(host, {learning_auto_accept: false, provider: 'groq'})
    expect(await screen.findByText(/Review everything: even your own statements wait here/)).toBeTruthy()
    expect((screen.getByRole('checkbox', {name: /hosted provider/i}) as HTMLInputElement).checked).toBe(false)
    expect(screen.getByText('0 waiting for review')).toBeTruthy()
    expect(screen.getByText(/Nothing is waiting/)).toBeTruthy()
    expect((screen.getByRole('button', {name: /summarise raw notes/i}) as HTMLButtonElement).disabled).toBe(true)
  })

  it('reports the background summary truthfully', () => {
    expect(describeDigest({created: 2, raw: 5})).toBe('2 suggested lessons are waiting for your review.')
    expect(describeDigest({created: 1})).toBe('1 suggested lesson is waiting for your review.')
    expect(describeDigest({created: 0, raw: 3})).toMatch(/nothing worth keeping/)
    expect(describeDigest({created: 0, skipped: 'cloud'})).toMatch(/hosted provider/)
    expect(describeDigest({created: 0, error: 'APIConnectionError'})).toMatch(/Nothing was changed/)
  })

  it('is reachable from the Projects page of the app', async () => {
    desktop.onAction('listLessons', () => ({ok: true, data: {lessons: stored(), counts: counted(stored())}}))
    const user = userEvent.setup()
    render(<App/>)
    await screen.findByRole('textbox', {name: /message star/i})
    await user.click(screen.getByRole('button', {name: /projects/i}))
    expect(await screen.findByText('2 waiting for review')).toBeTruthy()
    expect(desktop.sent('listLessons').length).toBeGreaterThan(0)
  })
})

describe('learning counts in Analytics', () => {
  const base: Analytics = {started: 0, succeeded: 0, failed: 0, tools: 0, rejected: 0, median_ms: null, messages: 0,
    project: 'STAR', period_days: 14, trend: [], recent: []}
  const value = (label: string) => (screen.getByText(label).closest('section') as HTMLElement).querySelector('strong')?.textContent

  it('shows the counted numbers the host reports', () => {
    render(<AnalyticsView data={{...base, learning: {captured: 7, accepted: 3, used: 12, pending: 2}}}/>)
    expect(value('Lessons captured')).toBe('7')
    expect(value('Lessons accepted')).toBe('3')
    expect(value('Answers given with lessons')).toBe('12')
    expect(value('Waiting for review')).toBe('2')
    expect(screen.getByText(/not model training/)).toBeTruthy()
  })

  it('shows zeros, not invented activity, when nothing was learned', () => {
    render(<AnalyticsView data={base}/>)
    for (const label of ['Lessons captured', 'Lessons accepted', 'Answers given with lessons', 'Waiting for review']) expect(value(label)).toBe('0')
  })
})
