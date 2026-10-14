// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {StarConstruction,StarLockup,StarMark,StarWordmark} from './SiteBrand'

afterEach(cleanup)

describe('site brand artwork',()=>{
 it('exposes a deliberately named mark and hides decorative marks from assistive technology',()=>{
  render(<><StarMark size={23} title="STAR symbol"/><StarMark size={24} title="Large STAR symbol"/><StarMark/></>)
  const compact=screen.getByRole('img',{name:'STAR symbol'})
  const detailed=screen.getByRole('img',{name:'Large STAR symbol'})
  expect(compact.getAttribute('width')).toBe('23')
  expect(detailed.getAttribute('width')).toBe('24')
  // The small mark has two readable facets; the full-size artwork keeps all eight.
  expect(compact.querySelectorAll('path')).toHaveLength(2)
  expect(detailed.querySelectorAll('path')).toHaveLength(8)
  expect(screen.getAllByRole('img')).toHaveLength(2)
 })
 it('keeps the lockup decorative while its enclosing navigation control stays usable',async()=>{
  const home=vi.fn()
  const user=userEvent.setup()
  render(<button type="button" aria-label="Back to chat" onClick={home}><StarLockup size={30}/></button>)
  expect(screen.queryByRole('img')).toBeNull()
  const button=screen.getByRole('button',{name:'Back to chat'})
  expect(button.querySelectorAll('svg')).toHaveLength(2)
  await user.click(button)
  expect(home).toHaveBeenCalledOnce()
 })
 it('keeps the construction illustration and standalone wordmark decorative',()=>{
  render(<><StarConstruction/><StarWordmark height={18}/></>)
  expect(screen.queryByRole('img')).toBeNull()
  expect(document.querySelector('svg.sw-construct')?.getAttribute('aria-hidden')).toBe('true')
  expect(document.querySelector('svg.sw-construct')?.getAttribute('focusable')).toBe('false')
 })
})
