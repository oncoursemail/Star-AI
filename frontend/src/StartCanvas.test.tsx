// @vitest-environment jsdom
import {afterEach, describe, expect, it, vi} from 'vitest'
import {cleanup, render, screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {StartCanvas, startActions} from './StartCanvas'

vi.mock('./StarFace', () => ({
  StarFace: ({label}:{label:string}) => <span role="img" aria-label={label}/>,
}))
afterEach(cleanup)

describe('creator workbench start state', () => {
  it('shows a single clear task hierarchy, the current project, and a labeled mascot', () => {
    render(<StartCanvas project="Ember Hollow" mood="idle" onStart={() => {}}/>)
    expect(screen.getByRole('heading', {level: 2, name: 'Make something worth keeping.'})).toBeTruthy()
    expect(screen.getByText('Ember Hollow')).toBeTruthy()
    expect(screen.getByRole('img', {name: "Star, STAR's mascot"})).toBeTruthy()
    expect(screen.getByRole('group', {name: 'Starting points'}).querySelectorAll('button')).toHaveLength(4)
    expect(screen.getByText('Nothing runs until you send it.', {exact: false})).toBeTruthy()
  })

  it('prepares an editable brief only when clicked; never executes a tool on mount', async () => {
    const onStart=vi.fn()
    render(<StartCanvas project="Design Lab" mood="listening" onStart={onStart}/>)
    expect(onStart).not.toHaveBeenCalled()
    await userEvent.setup().click(screen.getByRole('button', {name: /Debug a Luau script/i}))
    expect(onStart).toHaveBeenCalledTimes(1)
    expect(onStart).toHaveBeenCalledWith(startActions[1].prompt)
    expect(startActions[1].prompt).toContain('verification')
  })

  it('provides different, actionable directions rather than four cosmetic shortcuts', () => {
    const prompts=startActions.map(action=>action.prompt)
    expect(new Set(prompts).size).toBe(4)
    expect(prompts[0]).toContain('screenshot')
    expect(prompts[2]).toContain('citations')
    expect(prompts[3]).toContain('Blender')
  })
})
