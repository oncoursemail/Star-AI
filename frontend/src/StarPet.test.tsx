import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {fireEvent,render,screen,cleanup} from '@testing-library/react'
import {StarPet,petImage} from './StarPet'

beforeEach(()=>{localStorage.clear()})
afterEach(()=>{cleanup();vi.useRealTimers()})
describe('Star mascot',()=>{
 it('maps all activity states to approved art names',()=>{
  expect(petImage('idle').face).toBe('normal')
  expect(petImage('idle',true).face).toBe('content')
  expect(petImage('typing').face).toBe('focused')
  expect(petImage('thinking').pose).toBe('think')
  expect(petImage('streaming').pose).toBe('type-1')
  expect(petImage('streaming',true).pose).toBe('type-2')
  expect(petImage('finished').face).toBe('happy')
  expect(petImage('error').face).toBe('nervous')
  expect(petImage('cancelled').face).toBe('surprised')
  expect(petImage('sleepy').face).toBe('sleepy')
  expect(petImage('asleep').face).toBe('asleep')
  expect(petImage('update').pose).toBe('letter')
 })
 it('hides entirely when disabled',()=>{
  const {rerender}=render(<StarPet state="idle"/>)
  expect(screen.getByTestId('star-pet')).toBeTruthy()
  rerender(<StarPet state="idle" visible={false}/>)
  expect(screen.queryByTestId('star-pet')).toBeNull()
 })
 it('hides when artwork is missing',()=>{
  render(<StarPet state="idle"/>)
  fireEvent.error(document.querySelector('.star-pet__image') as HTMLImageElement)
  expect(screen.queryByTestId('star-pet')).toBeNull()
 })
 it('does not alternate art with reduced motion',()=>{
  vi.useFakeTimers()
  const {container}=render(<StarPet state="streaming" reducedMotion/>)
  expect(container.querySelector('.star-pet__image')?.getAttribute('src')).toContain('type-1.png')
  vi.advanceTimersByTime(10000)
  expect(container.querySelector('.star-pet__image')?.getAttribute('src')).toContain('type-1.png')
 })
 it('shows status when clicked',()=>{
  render(<StarPet state="update"/>)
  fireEvent.pointerUp(screen.getByRole('button',{name:'Star mascot'}),{clientX:50,clientY:50})
  expect(screen.getByRole('status').textContent).toContain('update')
 })
})
