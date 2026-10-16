// @vitest-environment jsdom
/** The workbench home (#418) is opt-in: the classic empty-chat home stays the default. */
import {afterEach,beforeAll,beforeEach,describe,expect,it,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await import('./Desktop')},60000)
beforeEach(()=>{desktop.reset();localStorage.clear()})
afterEach(()=>{cleanup();vi.restoreAllMocks();localStorage.clear()})

async function openChat(){
 const user=userEvent.setup()
 const view=render(<App/>)
 await screen.findByRole('textbox',{name:/message star/i})
 await waitFor(()=>expect(desktop.sent('bootstrap').length).toBeGreaterThan(0))
 return {user,view}
}

describe('Workbench home setting',()=>{
 it('shows the classic home by default and the workbench only after the Settings switch',async()=>{
  const {user,view}=await openChat()
  expect(screen.getByRole('heading',{name:'What are we making?'})).toBeTruthy()
  expect(document.querySelector('.is-crafted-home')).toBeNull()
  expect(localStorage.getItem('star.home.workbench')).toBe('off')
  await user.click(screen.getByRole('button',{name:/^settings/i}))
  await user.click(await screen.findByRole('tab',{name:'General'}))
  const toggle=screen.getByRole('checkbox',{name:'Workbench home screen'})
  expect(toggle).toHaveProperty('checked',false)
  await user.click(toggle)
  expect(localStorage.getItem('star.home.workbench')).toBe('on')
  await user.click(screen.getByRole('button',{name:'Chat'}))
  await waitFor(()=>expect(document.querySelector('.is-crafted-home')).not.toBeNull())
  view.unmount()
  await openChat()
  expect(document.querySelector('.is-crafted-home')).not.toBeNull()
 })
})
