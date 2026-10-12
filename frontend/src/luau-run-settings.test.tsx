// @vitest-environment jsdom
import {afterEach,beforeAll,beforeEach,expect,it} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {backendSettings,installFakeDesktop,type FakeDesktop} from './fake-desktop'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await import('./Desktop')},60_000)
beforeEach(()=>desktop.reset())
afterEach(cleanup)

async function openSettings(){
 const user=userEvent.setup()
 render(<App/>)
 await screen.findByRole('textbox',{name:/message star/i})
 await user.click(screen.getByRole('button',{name:/^settings$/i}))
 return user
}
const toggle=()=>screen.getByRole('checkbox',{name:'Run my Luau before answering'})

it('is off for old/default settings and does not save a grant just by opening Settings',async()=>{
 await openSettings()
 expect(toggle()).toHaveProperty('checked',false)
 expect(desktop.sent('saveSettings')).toHaveLength(0)
 expect(screen.getByText(/runs only on that server, never on this PC/i)).toBeTruthy()
})

it('saves explicit consent, restores it from the bridge, and saves revocation',async()=>{
 desktop.onAction('saveSettings',call=>{
  desktop.host({settings:call.payload.settings})
  return {ok:true,data:{saved:true}}
 })
 const user=await openSettings()
 await user.click(toggle())
 expect(toggle()).toHaveProperty('checked',true)
 expect(desktop.sent('saveSettings')).toHaveLength(0)
 await user.click(screen.getByRole('button',{name:/save settings/i}))
 await waitFor(()=>expect(desktop.sent('saveSettings')).toHaveLength(1))
 expect(desktop.sent('saveSettings')[0].payload.settings).toMatchObject({luau_run_before_answer:true,studio_edit:false})
 cleanup()
 await openSettings()
 expect(toggle()).toHaveProperty('checked',true)
 await user.click(toggle())
 await user.click(screen.getByRole('button',{name:/save settings/i}))
 await waitFor(()=>expect(desktop.sent('saveSettings')).toHaveLength(2))
 expect(desktop.sent('saveSettings')[1].payload.settings).toMatchObject({luau_run_before_answer:false})
})

it('never treats a malformed truthy value as consent',async()=>{
 desktop.host({settings:{...backendSettings,luau_run_before_answer:'false'}})
 await openSettings()
 expect(toggle()).toHaveProperty('checked',false)
})
