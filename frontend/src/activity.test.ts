import {describe, expect, it} from 'vitest'
import {applyProgress, formatElapsed, headline, isRich, settleRun, startRun, stateWord, toolLabel} from './activity'
import type {ActivityRun, ProgressPayload} from './activity'
import {classifyFailure, describeConnection} from './connection'
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
  const settings = {provider: 'local', model: 'qwen', endpoint: 'http://127.0.0.1:8080/v1'}
  it('does not claim a connection it has not seen', () => {
    const unknown = describeConnection({settings, brainRunning: false, credentials: {}, preview: false, last: null})
    expect(unknown.tone).toBe('unverified')
    expect(unknown.state).toBe('Not checked')
    expect(describeConnection({settings, brainRunning: true, credentials: {}, preview: false, last: null}).tone).toBe('ready')
    expect(describeConnection({settings, brainRunning: false, credentials: {}, preview: false, last: {ok: true, at: 0}}).tone).toBe('ready')
    expect(describeConnection({settings, brainRunning: true, credentials: {}, preview: false, last: {ok: false, at: 0, kind: 'unreachable'}}).tone).toBe('offline')
  })
  it('reports missing setup before anything else', () => {
    expect(describeConnection({settings: {...settings, model: ''}, brainRunning: true, credentials: {}, preview: false, last: null}).state).toBe('No model selected')
    const hosted = {provider: 'groq', model: 'openai/gpt-oss-20b', endpoint: ''}
    expect(describeConnection({settings: hosted, brainRunning: false, credentials: {groq: false}, preview: false, last: null}).state).toBe('Key missing')
    expect(describeConnection({settings: hosted, brainRunning: false, credentials: {groq: true}, preview: false, last: null}).tone).toBe('unverified')
    expect(describeConnection({settings, brainRunning: true, credentials: {}, preview: true, last: null}).tone).toBe('preview')
  })
  it('labels a LAN server provider without knowing its internals', () => {
    const lan = {provider: 'star_server', model: 'qwen-large', endpoint: '', server_endpoint: 'http://10.17.0.146:8080/v1'}
    const status = describeConnection({settings: lan, brainRunning: false, credentials: {}, preview: false, last: {ok: true, at: 0}})
    expect(status.label).toBe('STAR Server · qwen-large')
    expect(status.endpoint).toBe('10.17.0.146:8080')
  })
  it('classifies real backend error strings into recoveries', () => {
    expect(classifyFailure('RuntimeError: STAR task cancelled by user').kind).toBe('cancelled')
    expect(classifyFailure('RuntimeError: STAR Teams request cancelled by user').kind).toBe('cancelled')
    expect(classifyFailure('Cannot reach STAR Brain. Start it in the Brain tab, then test the connection again.').kind).toBe('unreachable')
    expect(classifyFailure('STAR local bridge did not respond. Restart the desktop app and try again.').kind).toBe('unreachable')
    expect(classifyFailure('STAR Brain did not respond in time. The model may still be loading or your machine may be low on memory.').kind).toBe('slow')
    expect(classifyFailure('TimeoutError: STAR exceeded its 85s task budget. Try Fast mode, a smaller prompt, or a hosted provider.').kind).toBe('slow')
    expect(classifyFailure('Your selected model provider denied access. Check its API key, model access and account limits in Settings.').kind).toBe('access')
    expect(classifyFailure('The AI provider reached its rate limit. Free tiers are limited; try again when your quota resets, or switch provider in Settings.').kind).toBe('limit')
    const other = classifyFailure('RuntimeError: STAR Teams could not finish: critic:failed, synthesis:blocked')
    expect(other.kind).toBe('other')
    expect(other.detail).toBe('STAR Teams could not finish: critic:failed, synthesis:blocked') // exception class is not shown to people
    expect(classifyFailure('ValueError: Message must be 1–30,000 characters').message).toBe('Message must be 1–30,000 characters')
  })
})
