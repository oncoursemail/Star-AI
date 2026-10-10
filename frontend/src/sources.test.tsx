/** @vitest-environment jsdom */
/** Sources row and the two documentation stages in the activity timeline. */
import {afterEach, describe, expect, it} from 'vitest'
import {cleanup, render, screen, within} from '@testing-library/react'
import {Message} from './components'
import {applyProgress, isRich, startRun, toolLabel} from './activity'
import {SOURCES_MARKER, splitSources} from './sources'

afterEach(cleanup)

const FOOTER =
  '\n\n---\n' +
  SOURCES_MARKER +
  ' (official documentation)\n\n' +
  '1. [TweenService > Create](https://create.roblox.com/docs/reference/engine/classes/TweenService#Create) · cited\n' +
  '2. [Type checking](https://luau.org/typecheck) · retrieved, not cited\n' +
  '3. Local notes page · retrieved, not cited\n'
const ANSWER = 'Use `TweenService:Create` [1] TweenService:Create.\n\n**Luau check by STAR:** The code block compiles.' + FOOTER

describe('splitSources', () => {
  it('separates the stored sources list from the prose', () => {
    const {body, sources} = splitSources(ANSWER)
    expect(body.endsWith('The code block compiles.')).toBe(true)
    expect(body).not.toContain(SOURCES_MARKER)
    expect(sources).toEqual([
      {index: 1, title: 'TweenService > Create', url: 'https://create.roblox.com/docs/reference/engine/classes/TweenService#Create', cited: true},
      {index: 2, title: 'Type checking', url: 'https://luau.org/typecheck', cited: false},
      {index: 3, title: 'Local notes page', url: '', cited: false},
    ])
  })

  it('leaves an answer without the marker, or with a malformed list, untouched', () => {
    expect(splitSources('Plain answer.')).toEqual({body: 'Plain answer.', sources: []})
    const broken = 'Answer.\n\n---\n' + SOURCES_MARKER + '\n\n2. [Out of order](https://luau.org/x) · cited\n'
    expect(splitSources(broken)).toEqual({body: broken, sources: []})
    const prose = 'Answer.\n\n---\n' + SOURCES_MARKER + '\n\nSome sentence the model wrote instead of a list.\n'
    expect(splitSources(prose).sources).toEqual([])
  })

  it('never turns an unknown host or a non-https link into a link', () => {
    const text =
      'A.\n\n---\n' + SOURCES_MARKER + '\n\n1. [Evil](https://evil.example/x) · cited\n2. [Lookalike](https://create.roblox.com.evil.io/x) · cited\n'
    expect(splitSources(text).sources.map(source => source.url)).toEqual(['', ''])
    const http = 'A.\n\n---\n' + SOURCES_MARKER + '\n\n1. [Plain](http://luau.org/x) · cited\n'
    expect(splitSources(http)).toEqual({body: http, sources: []})
  })
})

describe('sources row under an answer', () => {
  it('renders the sources as a labelled row and keeps them out of the prose', () => {
    render(<Message entry={{id: 'a', role: 'assistant', text: ANSWER}} animated={false} />)
    const row = screen.getByRole('group', {name: 'Sources for this answer'})
    const items = within(row).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    const link = within(row).getByRole('link', {name: 'TweenService > Create'})
    expect(link.getAttribute('href')).toBe('https://create.roblox.com/docs/reference/engine/classes/TweenService#Create')
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(items[0].className).toBe('is-cited')
    expect(items[1].className).toBe('')
    expect(within(items[2]).queryByRole('link')).toBeNull()
    expect(document.querySelector('.msg-prose')?.textContent).not.toContain('Sources retrieved by STAR')
    expect(document.querySelector('.msg-prose')?.textContent).toContain('Luau check by STAR:')
  })

  it('shows no row for a plain answer, a streaming answer or a user message', () => {
    const {rerender} = render(<Message entry={{id: 'a', role: 'assistant', text: 'Plain.'}} animated={false} />)
    expect(screen.queryByRole('group', {name: 'Sources for this answer'})).toBeNull()
    rerender(<Message entry={{id: 'a', role: 'assistant', text: ANSWER}} animated={false} partial />)
    expect(screen.queryByRole('group', {name: 'Sources for this answer'})).toBeNull()
    rerender(<Message entry={{id: 'u', role: 'user', text: ANSWER}} animated={false} />)
    expect(screen.queryByRole('group', {name: 'Sources for this answer'})).toBeNull()
  })
})

describe('documentation and Luau check stages', () => {
  it('shows the documentation lookup as a real step with its result', () => {
    let run = applyProgress(startRun('r', 'chat', 0), {phase: 'x', activity: {type: 'docs', state: 'running'}}, 10)
    expect(run.steps).toMatchObject([{id: 'docs', kind: 'search', state: 'running', title: 'Reading the official documentation'}])
    expect(isRich(run)).toBe(true)
    run = applyProgress(run, {phase: 'x', activity: {type: 'docs', state: 'done', passages: 4, elapsed_ms: 220}}, 300)
    expect(run.steps[0]).toMatchObject({state: 'done', elapsedMs: 220, detail: '4 passages from the official documentation'})
    const failed = applyProgress(
      applyProgress(startRun('r', 'chat', 0), {activity: {type: 'docs', state: 'running'}}, 1),
      {activity: {type: 'docs', state: 'failed'}},
      2,
    )
    expect(failed.steps[0]).toMatchObject({state: 'failed', detail: 'The documentation service did not answer. STAR answers without it.'})
    const empty = applyProgress(
      applyProgress(startRun('r', 'chat', 0), {activity: {type: 'docs', state: 'running'}}, 1),
      {activity: {type: 'docs', state: 'done', passages: 0}},
      2,
    )
    expect(empty.steps[0].detail).toBe('Nothing in the indexed documentation matched.')
  })

  it('reports a Luau check only as what happened', () => {
    const start = applyProgress(startRun('r', 'chat', 0), {activity: {type: 'luau_check', state: 'running'}}, 1)
    expect(start.steps).toMatchObject([{id: 'luau-check', kind: 'tool', state: 'running', title: 'Checking the Luau code'}])
    const fixing = applyProgress(start, {activity: {type: 'luau_check', state: 'running', repair: true}}, 2)
    expect(fixing.steps[0].title).toBe('Fixing the Luau code')
    const repaired = applyProgress(fixing, {activity: {type: 'luau_check', state: 'done', result: 'repaired'}}, 3)
    expect(repaired.steps[0]).toMatchObject({state: 'done', title: 'Checking the Luau code', detail: 'A problem was found and corrected. The corrected code passes.'})
    const passed = applyProgress(start, {activity: {type: 'luau_check', state: 'done', result: 'passed'}}, 3)
    expect(passed.steps[0].detail).toBe('Compiles and passes type analysis. Not run.')
    const unavailable = applyProgress(start, {activity: {type: 'luau_check', state: 'failed', result: 'unavailable'}}, 3)
    expect(unavailable.steps[0]).toMatchObject({state: 'failed', detail: 'The check could not run. Nothing is claimed about the code.'})
  })

  it('names the three documentation tools', () => {
    expect(toolLabel('star_docs_search')).toBe('Searching the official documentation')
    expect(toolLabel('star_api_lookup')).toBe('Checking Roblox API names')
    expect(toolLabel('star_luau_check')).toBe('Checking Luau code')
  })
})
