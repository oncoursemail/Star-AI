import {describe, expect, it} from 'vitest'
import {applyProgress, formatElapsed, headline, isRich, settleRun, startRun, stateWord, toolLabel} from './activity'
import type {ActivityRun, ProgressPayload} from './activity'
import {classifyFailure, connectionTarget, describeConnection} from './connection'
import type {LastOutcome} from './connection'
import {brainStatus, runsOnOwnHardware} from './IntegrationPanels'
import type {ServerStatus} from './types'
import {FIXTURES} from './previewFixtures'

/** Replay sanitized progress payloads the way Desktop.tsx does, one second apart. */
function replay(mode: 'chat' | 'team', payloads: ProgressPayload[]): ActivityRun {
  let run = startRun('test', mode, 0)
  payloads.forEach((payload, index) => {
    run = applyProgress(run, payload, (index + 1) * 1000)
  })
  return run
}
const states = (run: ActivityRun) => run.steps.map(step => `${step.title}:${step.state}`)

describe('activity timeline is driven only by backend events', () => {
  it('shows nothing until the backend reports something', () => {
    const run = startRun('r', 'chat', 0)
    expect(run.steps).toEqual([])
    expect(isRich(run)).toBe(false)
  })

  it('records the model a message was sent to and then the one the server says answered', () => {
    const sent = replay('chat', [{phase: 'STAR · Fast answer', activity: {type: 'route', profile: 'fast', model: 'star-quick'}}])
    expect(sent.model).toBe('star-quick')
    const answered = applyProgress(sent, {phase: 'Finishing the answer', activity: {type: 'model', model: 'star-voice'}}, 9000)
    expect(answered.model).toBe('star-voice')
    // A fall-back says so and names the model that takes over; an event without a name changes nothing.
    const fallback = applyProgress(sent, {phase: 'x', activity: {type: 'route', fallback: true, model: 'star-fast'}}, 9000)
    expect(fallback.model).toBe('star-fast')
    expect(fallback.phase).toContain('not available')
    expect(applyProgress(answered, {phase: 'x', activity: {type: 'model'}}, 9500).model).toBe('star-voice')
    expect(settleRun(answered, 'done', 10000).model).toBe('star-voice')
  })

  it('keeps a plain answer to one status line, not a timeline', () => {
    const run = replay('chat', [
      {phase: 'STAR · Fast answer', activity: {type: 'route', profile: 'fast'}},
      {phase: 'Thinking', activity: {type: 'turn', step: 1, max_steps: 1}},
      {phase: 'Generating response', delta: 'Hello'},
      {phase: 'Generating response', delta: ' there'},
    ])
    expect(run.label).toBe('Fast answer')
    expect(states(run)).toEqual(['Thinking:done', 'Writing the answer:running'])
    expect(isRich(run)).toBe(false)
    // Further deltas must not create steps or new objects (no re-render per token).
    expect(applyProgress(run, {delta: 'more'}, 9000)).toBe(run)
  })

  it('renders tools, model turns and read-only specialists in the order they happened', () => {
    const run = replay('chat', [
      {activity: {type: 'route', profile: 'agent'}},
      {activity: {type: 'turn', step: 1, max_steps: 12}},
      {activity: {type: 'tool', state: 'running', tool: 'workspace_search'}},
      {activity: {type: 'tool', state: 'done', tool: 'workspace_search'}},
      {activity: {type: 'turn', step: 2, max_steps: 12}},
      {activity: {type: 'tool', state: 'running', tool: 'star_delegate_research'}},
      {activity: {type: 'agent', group: 'specialist', id: 'tabc', role: 'luau', state: 'running'}},
      {activity: {type: 'agent', group: 'specialist', id: 'tabc', role: 'luau', state: 'done'}},
      {activity: {type: 'tool', state: 'failed', tool: 'star_delegate_research'}},
      {activity: {type: 'tool', state: 'blocked'}},
    ])
    expect(states(run)).toEqual([
      'Thinking:done',
      'Searching your workspace:done',
      'Thinking:done',
      'Briefing specialists:failed',
      'Luau engineer:done',
      'A tool request was blocked:blocked',
    ])
    expect(run.steps[0].detail).toBe('Model call 1 of up to 12')
    expect(run.steps[1].endedAt! - run.steps[1].startedAt!).toBe(1000)
    expect(isRich(run)).toBe(true)
  })

  it('shows the team plan as queued stages, then real starts, finishes and blocks', () => {
    const run = replay('team', [
      {activity: {type: 'plan', group: 'team', steps: [
        {id: 'evidence', role: 'research', needs: []},
        {id: 'design', role: 'planner', needs: []},
        {id: 'critic', role: 'review', needs: []},
        {id: 'synthesis', role: 'integration', needs: ['evidence', 'design', 'critic']},
      ]}},
      {activity: {type: 'agent', group: 'team', id: 'evidence', role: 'research', state: 'running'}},
      {activity: {type: 'agent', group: 'team', id: 'design', role: 'planner', state: 'running'}},
      {activity: {type: 'agent', group: 'team', id: 'evidence', role: 'research', state: 'done', elapsed_ms: 5240}},
      {activity: {type: 'agent', group: 'team', id: 'critic', role: 'review', state: 'failed', elapsed_ms: 110000}},
      {activity: {type: 'agent', group: 'team', id: 'synthesis', role: 'integration', state: 'blocked'}},
    ])
    expect(states(run)).toEqual(['Evidence:done', 'Plan:running', 'Critique:failed', 'Synthesis:blocked'])
    expect(run.steps[0].elapsedMs).toBe(5240) // the backend's own measurement wins over the UI clock
    expect(run.steps[3].detail).toMatch(/did not finish/)
    expect(run.steps.find(step => step.title === 'Synthesis')!.role).toBe('Synthesis lead')
  })

  it('ignores unknown or malformed payloads instead of inventing progress', () => {
    const run = startRun('r', 'chat', 0)
    expect(applyProgress(run, null, 1).steps).toEqual([])
    expect(applyProgress(run, {activity: {type: 'mystery'}}, 1).steps).toEqual([])
    expect(applyProgress(run, {activity: {type: 'agent', state: 'running'}}, 1).steps).toEqual([])
    // An unrecognised state is never shown as success.
    const odd = applyProgress(run, {activity: {type: 'tool', state: 'excellent', tool: 'workspace_read'}}, 1)
    expect(odd.steps[0].state).toBe('failed')
  })

  it('settles open and queued steps truthfully when a run ends', () => {
    const live = replay('team', [
      {activity: {type: 'plan', group: 'team', steps: [{id: 'evidence', role: 'research'}, {id: 'synthesis', role: 'integration', needs: ['evidence']}]}},
      {activity: {type: 'agent', group: 'team', id: 'evidence', role: 'research', state: 'running'}},
    ])
    const stopped = settleRun(live, 'cancelled', 9000)
    expect(states(stopped)).toEqual(['Evidence:cancelled', 'Synthesis:cancelled'])
    expect(stateWord(stopped.steps[0])).toBe('Stopped')
    expect(stateWord(stopped.steps[1])).toBe('Not started')
    expect(headline(stopped, 9000)).toBe('Stopped after 9.0s')
    expect(states(settleRun(live, 'failed', 9000))[0]).toBe('Evidence:failed')
    // A finished run cannot be changed by late events.
    expect(applyProgress(stopped, {activity: {type: 'tool', state: 'running', tool: 'x'}}, 9500)).toBe(stopped)
  })

  it('formats elapsed time without jitter', () => {
    expect(formatElapsed(40)).toBe('<0.1s')
    expect(formatElapsed(4200)).toBe('4.2s')
    expect(formatElapsed(4200, true)).toBe('4s')
    expect(formatElapsed(42000)).toBe('42s')
    expect(formatElapsed(65000)).toBe('1m 05s')
  })

  it('never shows an unknown tool name as a friendly claim', () => {
    expect(toolLabel('star_web_search')).toBe('Searching the web')
    // Listing the catalogue loads no skill; the row must say what really ran.
    expect(toolLabel('star_skill_catalog')).toBe('Listing Agent Skills')
    expect(toolLabel('star_skill_load')).toBe('Loading an Agent Skill')
    expect(toolLabel('SomeStudioTool')).toBe('Using a tool')
    expect(toolLabel(undefined)).toBe('Using a tool')
  })
})

describe('preview fixtures use the real event contract', () => {
  it('every scripted progress event is understood by the reducer', () => {
    for (const [name, fixture] of Object.entries(FIXTURES)) {
      if (!fixture.script) continue
      let run = startRun(name, fixture.script.action === 'runTeam' ? 'team' : 'chat', 0)
      let clock = 0
      for (const event of fixture.script.events) {
        clock += event.wait
        if (event.kind === 'progress') run = applyProgress(run, event.data as ProgressPayload, clock)
      }
      const last = fixture.script.events[fixture.script.events.length - 1]
      expect(['result', 'error'], name).toContain(last.kind)
      const settled = settleRun(run, last.kind === 'result' ? 'done' : 'failed', clock)
      expect(settled.steps.every(step => step.state !== 'running' && step.state !== 'queued'), name).toBe(true)
    }
  })
})

describe('connection status and failures are stated truthfully', () => {
  const local = {provider: 'local', model: 'qwen', endpoint: 'http://127.0.0.1:8080/v1'}
  const lan = {provider: 'star_server', model: 'qwen-large', endpoint: '', server_endpoint: 'http://192.168.1.20:8080/v1'}
  /** Build the inputs the way Desktop.tsx does, from the app-wide `brainStatus` helper. */
  const status = (state: {settings: typeof local | typeof lan | {provider: string; model: string; endpoint: string}; brain_running?: boolean; server?: ServerStatus; credentials?: Record<string, boolean>; preview?: boolean; last?: LastOutcome}) =>
    describeConnection({
      settings: state.settings,
      brain: brainStatus(state),
      server: state.server,
      ownHardware: runsOnOwnHardware(state.settings),
      credentials: state.credentials || {},
      preview: !!state.preview,
      last: state.last ?? null,
    })
  const server = (ok: boolean | null, configured = true): ServerStatus => ({selected: true, configured, key_present: true, model_selected: true, ok, code: '', checked_at: ''})

  it('follows the shared brain status for the model on this PC', () => {
    expect(status({settings: local, brain_running: true}).tone).toBe('ready')
    const off = status({settings: local, brain_running: false})
    expect(off.tone).toBe('offline')
    expect(off.state).toBe('Offline')
    // A real answer is stronger evidence than the engine flag; a real failure overrides it too.
    expect(status({settings: local, brain_running: false, last: {ok: true, at: 0}}).tone).toBe('ready')
    expect(status({settings: local, brain_running: true, last: {ok: false, at: 0, kind: 'unreachable'}}).tone).toBe('offline')
  })

  it('never calls an unchecked STAR Server offline, and never calls it ready without a check', () => {
    const unchecked = status({settings: lan, server: server(null)})
    expect(unchecked.tone).toBe('unverified')
    expect(unchecked.state).toBe('Not checked')
    expect(unchecked.label).toBe('STAR Server · qwen-large')
    expect(unchecked.endpoint).toBe('192.168.1.20:8080')
    expect(status({settings: lan, server: server(true)}).tone).toBe('ready')
    expect(status({settings: lan, server: server(false)}).state).toBe('Needs attention')
    expect(status({settings: lan, server: server(null, false)}).state).toBe('No server address')
    // The on-device engine running says nothing about the server.
    expect(status({settings: lan, brain_running: true, server: server(null)}).tone).toBe('unverified')
  })

  it('names the model that answered when it is not the selected one', () => {
    const target = connectionTarget(lan)
    const routed = status({settings: lan, server: server(true), last: {ok: true, at: 0, target, model: 'star-voice'}})
    expect(routed.answeredBy).toBe('star-voice')
    expect(routed.note).toContain('star-voice answered at')
    expect(routed.model).toBe('qwen-large')
    // The selected model itself answering needs no extra line, and an answer for another target is ignored.
    expect(status({settings: lan, server: server(true), last: {ok: true, at: 0, target, model: 'qwen-large'}}).answeredBy).toBeUndefined()
    expect(status({settings: {...lan, model: 'other'}, server: server(true), last: {ok: true, at: 0, target, model: 'star-voice'}}).answeredBy).toBeUndefined()
    expect(status({settings: lan, server: server(true), last: {ok: false, at: 0, kind: 'other', target, model: 'star-voice'}}).answeredBy).toBeUndefined()
  })

  it('does not carry an answer or a failure over to another address, model or provider', () => {
    const answered: LastOutcome = {ok: true, at: 0, target: connectionTarget(lan)}
    expect(status({settings: lan, server: server(null), last: answered}).state).toBe('Connected')
    const moved = {...lan, server_endpoint: 'http://192.168.1.30:8080/v1'}
    expect(status({settings: moved, server: server(null), last: answered})).toMatchObject({state: 'Not checked', tone: 'unverified'})
    expect(status({settings: {...lan, model: 'another-model'}, server: server(null), last: answered}).state).toBe('Not checked')
    expect(status({settings: local, brain_running: false, last: answered}).state).toBe('Offline')
    // A failure against the old address does not paint the new one red either.
    const failed: LastOutcome = {ok: false, at: 0, kind: 'unreachable', target: connectionTarget(lan)}
    expect(status({settings: lan, server: server(null), last: failed}).state).toBe('Not reachable')
    expect(status({settings: moved, server: server(null), last: failed}).state).toBe('Not checked')
    // The same address written with a trailing slash is the same target.
    expect(connectionTarget({...lan, server_endpoint: lan.server_endpoint + '/'})).toBe(connectionTarget(lan))
    expect(connectionTarget(local)).not.toBe(connectionTarget({...local, endpoint: 'http://127.0.0.1:8081/v1'}))
  })

  it('reports missing setup before anything else', () => {
    expect(status({settings: {...local, model: ''}, brain_running: true}).state).toBe('No model selected')
    const hosted = {provider: 'groq', model: 'openai/gpt-oss-20b', endpoint: ''}
    expect(status({settings: hosted, credentials: {groq: false}}).state).toBe('Key missing')
    // A hosted provider is not "ready" just because the local engine happens to be running.
    expect(status({settings: hosted, brain_running: true, credentials: {groq: true}}).tone).toBe('unverified')
    expect(status({settings: local, brain_running: true, preview: true}).tone).toBe('preview')
  })

  it('classifies real backend error strings into recoveries and shows the backend sentence', () => {
    expect(classifyFailure('RuntimeError: STAR task cancelled by user').kind).toBe('cancelled')
    const stopped = 'Request stopped. The draft answer has not been saved as a completed result.'
    expect(classifyFailure(stopped)).toMatchObject({kind: 'cancelled', message: stopped})
    expect(classifyFailure('No reply was recorded for this message. STAR may have been closed before it finished.').kind).toBe('cancelled')
    const offline = 'Cannot reach STAR Brain. Start it in the Brain tab, then test the connection again.'
    expect(classifyFailure(offline)).toMatchObject({kind: 'unreachable', message: offline})
    expect(classifyFailure('STAR local bridge did not respond. Restart the desktop app and try again.').kind).toBe('unreachable')
    expect(classifyFailure('STAR Brain did not respond in time. The model may still be loading or your machine may be low on memory.').kind).toBe('slow')
    expect(classifyFailure('TimeoutError: STAR exceeded its 85s task budget. Try Fast mode, a smaller prompt, or a hosted provider.').kind).toBe('slow')
    expect(classifyFailure('Your selected model provider denied access. Check its API key, model access and account limits in Settings.').kind).toBe('access')
    expect(classifyFailure('The AI provider reached its rate limit. Free tiers are limited; try again when your quota resets, or switch provider in Settings.').kind).toBe('limit')
    // STAR Server wording from star/model_health.py SERVER_FAILURES.
    expect(classifyFailure('Cannot reach STAR Server. Check that the server is switched on, that this PC is on the same network, and that the address and port are right.').kind).toBe('unreachable')
    expect(classifyFailure('STAR Server did not answer in time. It may be busy with another request or still loading its model. Try again, or raise the server timeout in Settings.').kind).toBe('slow')
    expect(classifyFailure('STAR Server refused the API key (401). Paste the correct server key in Settings → STAR Server.').kind).toBe('access')
    expect(classifyFailure('STAR Server needs its API key. Paste it in Settings → STAR Server and save it.').kind).toBe('setup')
    expect(classifyFailure('STAR Server is busy (429). Wait for the current request to finish, then try again.').kind).toBe('limit')
    expect(classifyFailure('STAR Server is reachable but still loading its model (503). Wait a minute, then test again.').title).toBe('The model is still loading')
    const team = classifyFailure('RuntimeError: STAR Teams could not finish: critic:failed, synthesis:blocked')
    expect(team.title).toBe("The team couldn't finish")
    expect(team.message).toBe('STAR Teams could not finish: critic:failed, synthesis:blocked') // the exception class is not shown to people
    expect(classifyFailure('ValueError: Message must be 1–30,000 characters').message).toBe('Message must be 1–30,000 characters')
  })
})
