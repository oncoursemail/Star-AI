// @vitest-environment jsdom
/** Actual desktop accessibility regression tests, with its fake bridge. */
import {afterEach,beforeAll,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,render,screen,waitFor,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'
import {CorrectionBox} from './CorrectionBox'

let bridge:FakeDesktop
beforeAll(async()=>{bridge=installFakeDesktop();await import('./Desktop')},60000)
beforeEach(()=>{
 bridge.reset([{id:'one',role:'user',text:'Help with Roblox inventory',created:''},
  {id:'two',role:'assistant',text:'Use server-owned inventory.',created:''}])
 bridge.host({chats:[
 {id:'c1',title:'Inventory test',created:'2026-10-13T12:00:00Z',updated:'2026-10-13T12:00:00Z'},
 {id:'c2',title:'Lighting plan',created:'2026-10-13T11:00:00Z',updated:'2026-10-13T11:00:00Z'}]})
 try{localStorage.clear()}catch{/* optional */}
})
afterEach(()=>{cleanup();vi.useRealTimers()})
async function launch(){
 const user=userEvent.setup()
 render(<App/>)
 await screen.findByRole('textbox',{name:'Message STAR'})
 return user
}
const ROLES=['button','link','textbox','searchbox','combobox','spinbutton','checkbox',
 'radio','switch','menuitem','menuitemcheckbox','menuitemradio','tab'] as const
function audit(view:string){
 const scope=within(document.body)
 let total=0
 const unnamed:string[]=[]
 for(const role of ROLES){
  const all=scope.queryAllByRole(role)
  const named=new Set(scope.queryAllByRole(role,{name:/\S/}))
  total+=all.length
  for(const el of all)if(!named.has(el))unnamed.push(role+': '+el.outerHTML.slice(0,200))
 }
 console.info('STAR A11Y CONTROL AUDIT '+view+': '+total+' controls; '+unnamed.length+' unnamed')
 expect(unnamed).toEqual([])
 return total
}
it('names all controls in chat, sidebar, composer, mode and plus menus',async()=>{
 const user=await launch()
 expect(audit('chat')).toBeGreaterThan(10)
 await user.click(screen.getByRole('button',{name:'More options for Lighting plan'}))
 audit('row-menu')
 await user.keyboard('{Escape}')
 await user.click(screen.getByRole('button',{name:'Add files and tools'}))
 audit('plus-menu')
 await user.click(screen.getByRole('menuitem',{name:'More'}))
 audit('plus-extra')
 await user.keyboard('{Escape}')
 await user.click(screen.getByRole('button',{name:'Mode: Auto'}))
 audit('mode-picker')
})
it('names controls in settings, integrations, fleet, tools and correction form',async()=>{
 const user=await launch()
 await user.click(screen.getByRole('button',{name:/^Settings/}))
 expect(audit('settings')).toBeGreaterThan(15)
 await user.click(screen.getByRole('button',{name:'Tools'}))
 expect(audit('tools')).toBeGreaterThan(7)
 cleanup()
 render(<CorrectionBox onCorrect={vi.fn().mockResolvedValue(true)}/>)
 expect(audit('correction')).toBeGreaterThanOrEqual(2)
})
it('auditor rejects an intentionally nameless button',()=>{
 const bad=document.createElement('button');document.body.appendChild(bad)
 try{expect(()=>audit('mutation')).toThrow()}finally{bad.remove()}
})
it('chat row menu Enter and arrows work, Escape restores focus',async()=>{
 const user=await launch()
 const trigger=screen.getByRole('button',{name:'More options for Lighting plan'})
 trigger.focus();await user.keyboard('{Enter}')
 const menu=screen.getByRole('menu',{name:'Options for Lighting plan'})
 const first=within(menu).getByRole('menuitem',{name:'Rename'})
 const last=within(menu).getByRole('menuitem',{name:'Delete'})
 await waitFor(()=>expect(document.activeElement).toBe(first))
 await user.keyboard('{ArrowDown}');expect(document.activeElement).toBe(last)
 await user.keyboard('{ArrowUp}');expect(document.activeElement).toBe(first)
 await user.keyboard('{Escape}')
 expect(trigger.getAttribute('aria-expanded')).toBe('false')
 expect(document.activeElement).toBe(trigger)
})
it('mode pill opens on Space, arrow changes selection, Escape returns focus',async()=>{
 const user=await launch()
 const trigger=screen.getByRole('button',{name:'Mode: Auto'})
 trigger.focus();await user.keyboard(' ')
 const group=screen.getByRole('radiogroup',{name:'How STAR should work'})
 await waitFor(()=>expect(document.activeElement).toBe(within(group).getByRole('radio',{name:'Auto'})))
 await user.keyboard('{ArrowDown}')
 expect(document.activeElement).toBe(within(group).getByRole('radio',{name:'Agent'}))
 await user.keyboard('{Escape}')
 expect(screen.queryByRole('radiogroup',{name:'How STAR should work'})).toBeNull()
 expect(document.activeElement).toBe(screen.getByRole('button',{name:'Mode: Agent'}))
})
it('plus menu opens on Enter, moves on arrows, Escape restores focus',async()=>{
 const user=await launch(),trigger=screen.getByRole('button',{name:'Add files and tools'})
 trigger.focus();await user.keyboard('{Enter}')
 const menu=screen.getByRole('menu',{name:'Add to this message'})
 await waitFor(()=>expect(document.activeElement).toBe(within(menu).getByRole('menuitem',{name:/Add photos and files/})))
 await user.keyboard('{ArrowDown}')
 expect(document.activeElement).toBe(within(menu).getByRole('menuitem',{name:/Look at my screen/}))
 await user.keyboard('{Escape}')
 expect(trigger.getAttribute('aria-expanded')).toBe('false')
 expect(document.activeElement).toBe(trigger)
})
it('consent dialog traps keyboard, Escape cancels and focus returns to plus trigger',async()=>{
 const user=await launch(),opener=screen.getByRole('button',{name:'Add files and tools'})
 await user.click(opener)
 await user.click(screen.getByRole('menuitem',{name:/Look at my screen/}))
 const dialog=await screen.findByRole('dialog',{name:'Let STAR look at your screen?'})
 await waitFor(()=>expect(dialog.contains(document.activeElement)).toBe(true))
 within(dialog).getByRole('button',{name:'Cancel'}).focus()
 for(let i=0;i<5;i++){
  await user.tab()
  expect(dialog.contains(document.activeElement)).toBe(true)
 }
 await user.keyboard('{Escape}')
 await waitFor(()=>expect(screen.queryByRole('dialog',{name:'Let STAR look at your screen?'})).toBeNull())
 await waitFor(()=>expect(document.activeElement).toBe(opener))
 expect(bridge.sent('captureScreen')).toHaveLength(0)
})
