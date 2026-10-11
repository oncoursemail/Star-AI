// @vitest-environment jsdom
import {afterEach,beforeAll,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {useState} from 'react'
import {initializeBridge} from './bridge'
import {installFakeDesktop,backendSettings,type FakeDesktop} from './fake-desktop'
import {StudioConnectionPanel} from './StudioConnectionPanel'
import {Desktop} from './Desktop'
import type {AppSettings,StudioConnectionStatus,StudioTarget} from './types'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await initializeBridge()})
afterEach(()=>{cleanup();vi.useRealTimers()})
const settings=(over:Partial<AppSettings>={}):AppSettings=>({...backendSettings,...over} as AppSettings)
const report=(over:Partial<StudioConnectionStatus>={}):StudioConnectionStatus=>({
 target:'local_pc',label:'Roblox Studio on this PC',state:'connected',checked_at:'2026-10-11T07:00:00Z',
 tool_count:30,instances:[{id:'s1',name:'Blank Place'},{id:'s2',name:'STAR Test Place'}],
 selected_id:'',selected_valid:false,reason_code:'',local_mcp:'memory',server_name:'STAR local MCP',...over,
})
function host(initial=settings()){
 let current=initial,serial=0
 const calls:Array<{action:string;params:Record<string,unknown>;id:string}>=[]
 const invoke=vi.fn(async(action:string,params:Record<string,unknown>={})=>{
   const id=`studio-${++serial}`;calls.push({action,params,id})
   if(action==='saveSettings'){
     const changes=params.settings as Partial<AppSettings>
     const switched=changes.studio_target!==undefined&&changes.studio_target!==current.studio_target
     current={...current,...changes,...(switched?{studio_id:'',studio_edit:false,studio_luau:false}:{})}
     return current
   }
   if(action==='selectStudio')current={...current,studio_id:String(params.studio_id),studio_edit:false,studio_luau:false}
   return {pending:true,requestId:id}
 })
 return {invoke,calls,get settings(){return current}}
}
function Harness({backend,status}:{backend:ReturnType<typeof host>;status?:StudioConnectionStatus}){
 const [saved,setSaved]=useState(backend.settings)
 return <StudioConnectionPanel settings={saved} status={status} invoke={backend.invoke} onSaved={()=>setSaved({...backend.settings})}/>
}
async function discover(backend:ReturnType<typeof host>,value=report()){
 await userEvent.click(screen.getByRole('button',{name:'Test & discover Studio'}))
 const call=backend.calls.at(-1)!
 desktop.emitRaw(call.id,'result',value)
 return call
}

describe('Studio connection in the downloaded app',()=>{
 it('opens the guided local Studio connection directly from the chat dock',async()=>{
   desktop.reset()
   render(<Desktop/> )
   await userEvent.click(await screen.findByRole('button',{name:/Studio: this PC/}))
   expect(await screen.findByLabelText('Studio connection')).toBeTruthy()
   expect(screen.getByRole('button',{name:'Test & discover Studio'})).toBeTruthy()
   expect(screen.getByText(/Assistant → Manage MCP Servers/)).toBeTruthy()
 })
 it('defaults to this PC and explains the real Studio switch without claiming enablement',()=>{
   render(<Harness backend={host(settings({studio_target:undefined}))}/> )
   expect((screen.getByLabelText('Studio connection') as HTMLSelectElement).value).toBe('local_pc')
   expect(screen.getByText(/Assistant → Manage MCP Servers/)).toBeTruthy()
   expect(screen.getByRole('link',{name:'Roblox setup guide'}).getAttribute('href')).toBe('https://create.roblox.com/docs/studio/mcp')
   expect(screen.getByRole('status').textContent).toContain('MCP not checked yet')
   expect(screen.queryByLabelText('Open Studio instance')).toBeNull()
   expect(screen.queryByText('STAR local MCP answered')).toBeNull()
   expect(screen.queryByRole('checkbox')).toBeNull()
 })
 it('shows actual discovered instances and persists only an explicit selection',async()=>{
   const backend=host(settings({studio_edit:true,studio_luau:true}))
   render(<Harness backend={backend}/> )
   expect((await discover(backend)).params).toEqual({target:'local_pc'})
   expect(screen.getByRole('status').textContent).toContain('STAR local MCP answered')
   expect((screen.getByLabelText('Open Studio instance') as HTMLSelectElement).value).toBe('')
   await userEvent.selectOptions(screen.getByLabelText('Open Studio instance'),'s2')
   const selected=backend.calls.at(-1)!
   expect(selected.action).toBe('selectStudio')
   expect(selected.params).toEqual({target:'local_pc',studio_id:'s2'})
   desktop.emitRaw(selected.id,'result',report({selected_id:'s2',selected_valid:true}))
   await waitFor(()=>expect((screen.getByLabelText('Open Studio instance') as HTMLSelectElement).value).toBe('s2'))
   expect(backend.settings.studio_edit).toBe(false);expect(backend.settings.studio_luau).toBe(false)
   expect((screen.getByRole('checkbox',{name:/Allow edits in/}) as HTMLInputElement).checked).toBe(false)
   expect((screen.getByRole('checkbox',{name:/Allow Luau/}) as HTMLInputElement).disabled).toBe(true)
   expect(screen.getByText(/Verified for read access at the last check/)).toBeTruthy()
 })
 it('clears stale choices after a failed probe and never displays its raw diagnostic',async()=>{
   const backend=host();render(<Harness backend={backend}/> )
   await discover(backend)
   expect(screen.getByRole('option',{name:'STAR Test Place'})).toBeTruthy()
   await userEvent.click(screen.getByRole('button',{name:'Test & discover Studio'}))
   desktop.emitRaw(backend.calls.at(-1)!.id,'error','private endpoint/token/raw response')
   expect(screen.queryByLabelText('Open Studio instance')).toBeNull()
   expect(screen.getByRole('alert').textContent).not.toContain('private')
   expect(screen.getByRole('status').textContent).not.toContain('responded')
 })
 it('keeps an empty instance list separate from a successful Studio connection',async()=>{
   const backend=host();render(<Harness backend={backend}/> )
   await discover(backend,report({state:'no_instances',instances:[]}))
   expect(screen.getByRole('status').textContent).toContain('No open Studio connected')
   expect(screen.queryByLabelText('Open Studio instance')).toBeNull()
 })
 it('labels the remote choice as separate practice and saves no launcher command',async()=>{
   const backend=host(settings({studio_id:'s1',studio_edit:true,studio_luau:true}))
   render(<Harness backend={backend} status={report({selected_id:'s1',selected_valid:true})}/> )
   await userEvent.selectOptions(screen.getByLabelText('Studio connection'),'host_launcher')
   await waitFor(()=>expect((screen.getByLabelText('Studio connection') as HTMLSelectElement).value).toBe('host_launcher'))
   expect(backend.calls[0]).toMatchObject({action:'saveSettings',params:{settings:{studio_target:'host_launcher'}}})
   expect(backend.settings.studio_id).toBe('');expect(backend.settings.studio_edit).toBe(false)
   expect(backend.settings.studio_luau).toBe(false)
   expect(screen.queryByRole('checkbox')).toBeNull()
   expect(screen.getByText(/practice result does not approve changes/)).toBeTruthy()
   expect(screen.getByText(/Background practice and self-learning are not verified/)).toBeTruthy()
   expect(document.body.textContent).not.toContain('ssh')
 })
 it('ignores a result for an older connection after the host changed routes',async()=>{
   const backend=host()
   const view=render(<StudioConnectionPanel settings={settings()} invoke={backend.invoke}/>)
   await userEvent.click(screen.getByRole('button',{name:'Test & discover Studio'}))
   const stale=backend.calls.at(-1)!.id
   view.rerender(<StudioConnectionPanel settings={settings({studio_target:'host_launcher'})} invoke={backend.invoke}/>)
   desktop.emitRaw(stale,'result',report())
   expect((screen.getByLabelText('Studio connection') as HTMLSelectElement).value).toBe('host_launcher')
   expect(screen.queryByLabelText('Open Studio instance')).toBeNull()
 })
 it('accepts a fast result that arrives before the pending response callback',async()=>{
   const invoke=vi.fn(async()=>{
     desktop.emitRaw('very-fast','result',report())
     return {pending:true,requestId:'very-fast'}
   })
   render(<StudioConnectionPanel settings={settings()} invoke={invoke}/>)
   await userEvent.click(screen.getByRole('button',{name:'Test & discover Studio'}))
   await waitFor(()=>expect(screen.getByLabelText('Open Studio instance')).toBeTruthy())
 })
 it('bounds a lost worker response and ignores later stale success',async()=>{
   vi.useFakeTimers()
   const invoke=vi.fn(async()=>({pending:true,requestId:'lost'}))
   render(<StudioConnectionPanel settings={settings()} invoke={invoke}/>)
   fireEvent.click(screen.getByRole('button',{name:'Test & discover Studio'}))
   await act(async()=>{await vi.advanceTimersByTimeAsync(20000)})
   expect(screen.getByRole('alert')).toBeTruthy()
   desktop.emitRaw('lost','result',report())
   expect(screen.queryByLabelText('Open Studio instance')).toBeNull()
 })
 it('saves edits and Luau as separate explicit grants while keeping the verified instance',async()=>{
   const backend=host(settings({studio_id:'s1',studio_edit:false,studio_luau:false}))
   render(<Harness backend={backend} status={report({selected_id:'s1',selected_valid:true})}/> )
   const edits=screen.getByRole('checkbox',{name:/Allow edits in/}) as HTMLInputElement
   const luau=screen.getByRole('checkbox',{name:/Allow Luau/}) as HTMLInputElement
   expect(luau.disabled).toBe(true)
   await userEvent.click(edits)
   await waitFor(()=>expect(edits.checked).toBe(true))
   expect(backend.calls[0]).toMatchObject({action:'saveSettings',params:{settings:{studio_edit:true,studio_luau:false}}})
   expect(luau.checked).toBe(false);expect(luau.disabled).toBe(false)
   await userEvent.click(luau)
   await waitFor(()=>expect(luau.checked).toBe(true))
   expect(backend.calls[1].params).toEqual({settings:{studio_edit:true,studio_luau:true}})
   expect((screen.getByLabelText('Open Studio instance') as HTMLSelectElement).value).toBe('s1')
   expect(screen.getByRole('status').textContent).toContain('STAR local MCP answered')
   expect(backend.settings.studio_id).toBe('s1')
   await userEvent.click(edits)
   await waitFor(()=>expect(edits.checked).toBe(false))
   expect(backend.calls[2].params).toEqual({settings:{studio_edit:false,studio_luau:false}})
   expect(luau.checked).toBe(false);expect(luau.disabled).toBe(true)
 })
 it('revokes both saved grants when selecting a different discovered instance',async()=>{
   const backend=host(settings({studio_id:'s1',studio_edit:true,studio_luau:true}))
   render(<Harness backend={backend} status={report({selected_id:'s1',selected_valid:true})}/> )
   await userEvent.selectOptions(screen.getByLabelText('Open Studio instance'),'s2')
   desktop.emitRaw(backend.calls.at(-1)!.id,'result',report({selected_id:'s2',selected_valid:true}))
   await waitFor(()=>expect((screen.getByLabelText('Open Studio instance') as HTMLSelectElement).value).toBe('s2'))
   expect((screen.getByRole('checkbox',{name:/Allow edits in/}) as HTMLInputElement).checked).toBe(false)
   expect((screen.getByRole('checkbox',{name:/Allow Luau/}) as HTMLInputElement).checked).toBe(false)
   expect(backend.settings.studio_edit).toBe(false);expect(backend.settings.studio_luau).toBe(false)
 })
 it('disables permission changes while the desktop is busy',async()=>{
   const invoke=vi.fn()
   render(<StudioConnectionPanel settings={settings({studio_id:'s1'})} status={report({selected_id:'s1',selected_valid:true})} invoke={invoke} disabled/> )
   const edits=screen.getByRole('checkbox',{name:/Allow edits in/}) as HTMLInputElement
   expect(edits.disabled).toBe(true)
   await userEvent.click(edits)
   expect(invoke).not.toHaveBeenCalled()
 })
 it('waits for confirmed permission save and prevents another change while pending',async()=>{
   let confirm!:(value:unknown)=>void
   const invoke=vi.fn(()=>new Promise(resolve=>{confirm=resolve}))
   render(<StudioConnectionPanel settings={settings({studio_id:'s1'})} status={report({selected_id:'s1',selected_valid:true})} invoke={invoke}/> )
   const edits=screen.getByRole('checkbox',{name:/Allow edits in/}) as HTMLInputElement
   await userEvent.click(edits)
   expect(edits.checked).toBe(false);expect(edits.disabled).toBe(true)
   expect((screen.getByLabelText('Open Studio instance') as HTMLSelectElement).disabled).toBe(true)
   await userEvent.click(edits)
   expect(invoke).toHaveBeenCalledTimes(1)
   await act(async()=>confirm(settings({studio_id:'s1',studio_edit:true,studio_luau:false})))
   expect(edits.checked).toBe(true);expect(edits.disabled).toBe(false)
   expect(screen.getByRole('status').textContent).toContain('STAR local MCP answered')
 })
 it('does not show a failed permission save as a grant or lose its connection evidence',async()=>{
   const invoke=vi.fn(async()=>{throw new Error('private endpoint/token')})
   render(<StudioConnectionPanel settings={settings({studio_id:'s1'})} status={report({selected_id:'s1',selected_valid:true})} invoke={invoke}/> )
   const edits=screen.getByRole('checkbox',{name:/Allow edits in/}) as HTMLInputElement
   await userEvent.click(edits)
   expect(screen.getByRole('alert').textContent).toContain('permission save could not be confirmed')
   expect(screen.getByRole('alert').textContent).not.toContain('private')
   expect(edits.checked).toBe(false)
   expect((screen.getByLabelText('Open Studio instance') as HTMLSelectElement).value).toBe('s1')
   expect(screen.getByRole('status').textContent).toContain('STAR local MCP answered')
 })
 it.each([{studio_id:'other'},{studio_edit:false}])('requires the host to confirm the same instance and requested grants: %j',async wrong=>{
   const invoke=vi.fn(async()=>settings({studio_id:'s1',studio_edit:true,studio_luau:false,...wrong}))
   render(<StudioConnectionPanel settings={settings({studio_id:'s1'})} status={report({selected_id:'s1',selected_valid:true})} invoke={invoke}/> )
   const edits=screen.getByRole('checkbox',{name:/Allow edits in/}) as HTMLInputElement
   await userEvent.click(edits)
   expect(edits.checked).toBe(false)
   expect(screen.getByRole('alert').textContent).toContain('permission save could not be confirmed')
 })
})
