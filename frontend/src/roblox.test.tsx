// @vitest-environment jsdom
/**
 * Roblox in Settings: the API key option, its Test, the test experience, approvals and the Studio switches.
 *
 * Contract under test: what the panel sends to the desktop host and the text the owner reads.
 * The key must leave the page once (to the host) and never be shown or kept.
 */
import {readFileSync} from 'node:fs'
import {afterEach, beforeAll, describe, expect, it, vi} from 'vitest'
import {cleanup, render, screen, waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {useState} from 'react'
import {initializeBridge} from './bridge'
import {RobloxPanel, describeAction, describeResult, robloxStateLabel} from './RobloxPanel'
import {backendSettings, installFakeDesktop, type FakeDesktop} from './fake-desktop'
import type {AppSettings, RobloxAction, RobloxCheck, RobloxStatus} from './types'

const KEY = 'FakeRobloxKey0123456789+/abcdefghijklmnopqrstuvwxyz=='
let desktop: FakeDesktop
beforeAll(async () => { desktop = installFakeDesktop(); await initializeBridge() })
afterEach(cleanup)

const status = (over: Partial<RobloxStatus> = {}): RobloxStatus => ({
  key_present: false, source: '', state: 'no_key', message: 'No Roblox API key is connected.', last_check: null,
  test_experience: null, pending_actions: 0, denied_place_ids: [129870808752914], ...over})
const stored = status({key_present: true, source: 'keyring', state: 'unchecked', message: 'A key is stored. Press Test to check it.'})
const check: RobloxCheck = {
  state: 'valid', message: 'The key works and has what the test pipeline needs.', checked_at: '2026-10-11T06:00:00Z', source: 'keyring',
  account: {user_id: 4242, name: 'StarOwnAccount'},
  capabilities: [
    {id: 'experience_info', label: 'Read experience and place information', granted: true, needs: [], status: 200, evidence: 'read call'},
    {id: 'publish_place', label: 'Publish a place file to the test experience', granted: true, needs: ['universe-places:write'], status: null, evidence: "the key's scope list"},
    {id: 'publish_message', label: 'Send a message to live servers (not used by STAR)', granted: false, needs: ['universe-messaging-service:publish'], status: null, evidence: "the key's scope list"}],
  calls: [{call: 'the key describes itself', status: 200}], missing: [],
  warnings: ['This key also carries 2 permission groups STAR never uses (for example legacy-universe.badge). A key with only the permissions listed under \'needs\' is safer.']}
const experience = {universe_id: 7001, place_id: 9001, name: 'STAR Test Place', visibility: 'PRIVATE', verified_at: '2026-10-11T06:01:00Z', owner_user_id: 4242}
const waiting: RobloxAction = {
  id: 'a1b2c3d4e5f6', kind: 'publish', status: 'pending', summary: 'Publish the shop', created: '2026-10-11T06:02:00Z', expires: '2026-10-11T06:17:00Z',
  target: {universe_id: 7001, place_id: 9001, name: 'STAR Test Place'},
  detail: {sha256: '022437e08a59b6749ced9b3c37d8e3b9910443d5d961685c577e9ce5ba50ee0a', bytes: 4692, files: ['a.luau', 'b.luau', 'c.luau']}}

/** A host that answers like star/roblox_cloud.py: three actions answer later, through an event. */
function host(initial: RobloxStatus, actions: RobloxAction[] = []) {
  let now = initial
  let list = actions.slice()
  const calls: Array<{action: string; params: Record<string, unknown>}> = []
  let serial = 0
  const invoke = vi.fn(async (action: string, params: Record<string, unknown> = {}) => {
    calls.push({action, params})
    if (action === 'robloxSaveKey') { now = stored; return now }
    if (action === 'robloxClearKey') { now = status(); return now }
    if (action === 'robloxListActions') return {actions: list}
    if (action === 'robloxClearTestExperience') { now = {...now, test_experience: null}; return now }
    return {pending: true, requestId: `later-${++serial}`}
  })
  const settings = backendSettings as unknown as AppSettings
  const drafts: AppSettings[] = []
  function Mounted() {
    const [draft, setDraft] = useState(settings)
    return <RobloxPanel status={initial} draft={draft} invoke={invoke} onChange={next => { drafts.push(next); setDraft(next) }}/>
  }
  render(<Mounted/>)
  return {
    calls, drafts, sent: (action: string) => calls.filter(c => c.action === action),
    answer: (data: unknown, kind: 'result' | 'error' = 'result') => desktop.emitRaw(`later-${serial}`, kind, data),
    setActions(next: RobloxAction[]) { list = next },
    current: () => now,
  }
}

describe('Roblox API key option', () => {
  it('starts honest: no key, nothing to test, nothing waiting', () => {
    host(status())
    expect(screen.getByText(/Key: No key\./)).toBeTruthy()
    expect((screen.getByRole('button', {name: /Test/}) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', {name: /Use this experience/}) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/Actions waiting for you \(0\)/)).toBeTruthy()
  })

  it('hands the pasted key to the host once and keeps it nowhere on the page', async () => {
    const user = userEvent.setup()
    const page = host(status())
    const field = screen.getByLabelText(/Open Cloud API key/) as HTMLInputElement
    expect(field.type).toBe('password')
    await user.type(field, `  ${KEY}  `)
    await user.click(screen.getByRole('button', {name: /Save key/}))
    await waitFor(() => expect(screen.getByText(/Key: Key stored, not tested yet\./)).toBeTruthy())
    expect(page.sent('robloxSaveKey')).toEqual([{action: 'robloxSaveKey', params: {key: KEY}}])
    expect(field.value).toBe('')
    expect(document.body.innerHTML).not.toContain(KEY)
    expect(page.drafts).toEqual([])                              // the key never enters the settings draft
    expect(screen.getByText(/saved in this PC's credential store\./)).toBeTruthy()
  })

  it('refuses an empty key without calling the host', async () => {
    const user = userEvent.setup()
    const page = host(status())
    await user.click(screen.getByRole('button', {name: /Save key/}))
    expect(screen.getByRole('alert').textContent).toContain('Paste the API key first')
    expect(page.sent('robloxSaveKey')).toEqual([])
  })

  it('shows the test result: state, account, each capability with what proved it, and warnings', async () => {
    const user = userEvent.setup()
    const page = host(stored)
    await user.click(screen.getByRole('button', {name: /Test/}))
    expect(page.sent('robloxTestKey').length).toBe(1)
    await page.answer({...stored, state: 'valid', check})
    await waitFor(() => expect(screen.getByText(/Key: Valid\./)).toBeTruthy())
    expect(screen.getByText(/Account: StarOwnAccount \(4242\)/)).toBeTruthy()
    expect(screen.getByText(/Read experience and place information/).closest('div')?.textContent).toContain('HTTP 200')
    expect(screen.getByText(/Publish a place file to the test experience: needs universe-places:write/).closest('div')?.textContent).toContain("the key's scope list")
    expect(screen.getAllByLabelText('Allowed').length).toBe(2)
    expect(screen.getAllByLabelText('Not allowed').length).toBe(1)
    expect(screen.getByText(/2 permission groups STAR never uses/)).toBeTruthy()
  })

  it.each([
    ['missing_permission', 'Missing permission'], ['revoked', 'Revoked'], ['invalid', 'Not a key'], ['unreachable', 'Roblox could not be reached'],
  ] as const)('names the %s state plainly', async (state, label) => {
    const user = userEvent.setup()
    const page = host(stored)
    await user.click(screen.getByRole('button', {name: /Test/}))
    await page.answer({...stored, state, message: 'From the host.', check: {...check, state, message: 'From the host.', capabilities: [], warnings: [], missing: state === 'missing_permission' ? ['universe-places:write'] : []}})
    await waitFor(() => expect(screen.getByText(new RegExp(`Key: ${label}\\.`))).toBeTruthy())
    expect(robloxStateLabel[state]).toBe(label)
  })

  it('says so when the test itself could not run', async () => {
    const user = userEvent.setup()
    const page = host(stored)
    await user.click(screen.getByRole('button', {name: /Test/}))
    await page.answer('CloudError: Roblox could not be reached (ConnectError)', 'error')
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('could not be reached'))
    expect(screen.getByText(/Key: Key stored, not tested yet\./)).toBeTruthy()
  })
})

describe('Roblox test experience and approvals', () => {
  it('sends the two IDs with the owner\'s explicit approval and shows what Roblox confirmed', async () => {
    const user = userEvent.setup()
    const page = host(stored)
    await user.type(screen.getByLabelText('Universe ID'), '7001')
    await user.type(screen.getByLabelText('Place ID'), 'abc')
    await user.click(screen.getByRole('button', {name: /Use this experience/}))
    expect(screen.getByRole('alert').textContent).toContain('as numbers')
    expect(page.sent('robloxSetTestExperience')).toEqual([])
    await user.clear(screen.getByLabelText('Place ID'))
    await user.type(screen.getByLabelText('Place ID'), '9001')
    await user.click(screen.getByRole('button', {name: /Use this experience/}))
    expect(page.sent('robloxSetTestExperience')[0].params).toEqual({universe_id: 7001, place_id: 9001, approved: true})
    await page.answer({...stored, test_experience: experience})
    await waitFor(() => expect(screen.getByText(/STAR Test Place: universe 7001, place 9001, private/)).toBeTruthy())
    await user.click(screen.getByRole('button', {name: /Stop using it/}))
    await waitFor(() => expect(screen.getByLabelText('Universe ID')).toBeTruthy())
  })

  it('shows a refusal from the host as the reason, not as success', async () => {
    const user = userEvent.setup()
    const page = host(stored)
    await user.type(screen.getByLabelText('Universe ID'), '1')
    await user.type(screen.getByLabelText('Place ID'), '11')
    await user.click(screen.getByRole('button', {name: /Use this experience/}))
    await page.answer('CloudError: That experience is not owned by the account this key belongs to.', 'error')
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('not owned by the account'))
    expect(screen.queryByText(/Test experience saved/)).toBeNull()
  })

  it('lists what STAR asked for and sends nothing until the owner decides', async () => {
    const user = userEvent.setup()
    const page = host({...stored, test_experience: experience, pending_actions: 1}, [waiting])
    await waitFor(() => expect(screen.getByText(/Actions waiting for you \(1\)/)).toBeTruthy())
    expect(screen.getByText('Publish the shop')).toBeTruthy()
    expect(screen.getByText(/Publish a place file to STAR Test Place \(place 9001\) as a saved version: 4692 bytes, 3 source files/)).toBeTruthy()
    expect(screen.getByText(/SHA-256 022437e08a59b674/)).toBeTruthy()
    expect(page.sent('robloxDecideAction')).toEqual([])
    page.setActions([{...waiting, status: 'done', result: {version: 4, http_status: 200}}])
    await user.click(screen.getByRole('button', {name: 'Approve'}))
    expect(page.sent('robloxDecideAction')[0].params).toEqual({id: 'a1b2c3d4e5f6', decision: 'approve', approved: true})
    await page.answer({action: {...waiting, status: 'done', result: {version: 4}}})
    await waitFor(() => expect(screen.getByText(/Publish the shop: done\. Published as saved version 4\./)).toBeTruthy())
    expect(screen.getByText(/Actions waiting for you \(0\)/)).toBeTruthy()
  })

  it('rejects with the same explicit decision', async () => {
    const user = userEvent.setup()
    const page = host({...stored, test_experience: experience}, [{...waiting, kind: 'run_test', summary: 'Run the tests', detail: {script_chars: 1900, standard_harness: true, version: 4, script_preview: 'local HttpService'}}])
    await waitFor(() => expect(screen.getByText(/Run the standard test harness \(1900 characters\) in STAR Test Place \(place 9001\), version 4/)).toBeTruthy())
    await user.click(screen.getByRole('button', {name: 'Reject'}))
    expect(page.sent('robloxDecideAction')[0].params).toEqual({id: 'a1b2c3d4e5f6', decision: 'reject', approved: true})
  })

  it('describes outcomes without inventing a success', () => {
    expect(describeAction(waiting)).toContain('as a saved version')
    expect(describeResult({...waiting, status: 'failed', result: {error: 'Publishing failed: the key lacks the permission for this (HTTP 403)'}})).toContain('HTTP 403')
    expect(describeResult({...waiting, status: 'rejected'})).toBe('You rejected this.')
    expect(describeResult({...waiting, status: 'expired'})).toBe('Expired before a decision.')
    expect(describeResult({...waiting, kind: 'run_test', status: 'failed', result: {state: 'FAILED', log_lines: 3}})).toBe('Test run ended as FAILED with 3 log lines.')
    expect(describeResult({...waiting, status: 'done', result: {}})).toBe('')
  })
})

describe('Roblox Studio switches', () => {
  it('are off by default, depend on Studio edits, and only change the settings draft', async () => {
    const user = userEvent.setup()
    const page = host(status())
    const edits = screen.getByLabelText(/Studio edits in a blank, unsaved place/) as HTMLInputElement
    const own = screen.getByLabelText(/Also places of STAR's own account/) as HTMLInputElement
    const luau = screen.getByLabelText(/Let STAR run Luau in the sandbox/) as HTMLInputElement
    expect([edits.checked, own.checked, luau.checked]).toEqual([false, false, false])
    expect([own.disabled, luau.disabled]).toEqual([true, true])
    await user.click(edits)
    await user.click(screen.getByLabelText(/Also places of STAR's own account/))
    await user.click(screen.getByLabelText(/Let STAR run Luau in the sandbox/))
    expect(page.drafts.at(-1)).toMatchObject({studio_edit: true, studio_own_places: true, studio_luau: true})
    expect(page.calls.filter(c => c.action !== 'robloxListActions')).toEqual([])
    expect(screen.getByText(/never edits another published place, never saves and never publishes/)).toBeTruthy()
  })
})

describe('Roblox interface source', () => {
  const read = (name: string) => readFileSync(new URL(name, import.meta.url), 'utf8')
  it('is part of Settings and never puts the key into React state or settings', () => {
    expect(read('./Desktop.tsx')).toContain('<RobloxPanel status={data.roblox}')
    const panel = read('./RobloxPanel.tsx')
    expect(panel).toContain("invoke('robloxSaveKey',{key:typed})")
    expect(panel).not.toMatch(/useState[^\n]*[Kk]ey\b/)
    expect(panel).not.toContain('localStorage')
    expect(panel).toContain("type=\"password\"")
  })
})
