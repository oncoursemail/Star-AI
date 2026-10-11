// @vitest-environment jsdom
import {beforeAll,afterEach,describe,it,expect,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {useState} from 'react'
import {initializeBridge} from './bridge'
import {installFakeDesktop,backendSettings,type FakeDesktop} from './fake-desktop'
import {ProviderPanel} from './IntegrationPanels'
import type {AppSettings,ServerReport} from './types'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await initializeBridge()})
afterEach(()=>cleanup())
const okReport:ServerReport={ok:true,code:'ok',message:'STAR Server is ready.',steps:[],models:['model-one'],
  model:'model-one',context_tokens:null,slots:null,first_token_ms:null,sample:''}
function host(){
 const calls:Array<{action:string;params:Record<string,unknown>}>=[]
 const invoke=vi.fn(async(action:string,params:Record<string,unknown>={})=>{
   calls.push({action,params})
   if(action==='serverKeyFileStatus')return {found:true}
   if(action==='importServerKeyFile')return {connected:true}
   if(action==='saveProviderKey')return {connected:true}
   if(action==='saveSettings')return {saved:true}
   if(action==='testServer')return {pending:true,requestId:'server-connect-test'}
   return null
 })
 return {calls,invoke}
}
function Harness({backend}:{backend:ReturnType<typeof host>}){
 const [draft,setDraft]=useState(backendSettings as AppSettings)
 return <ProviderPanel draft={draft} onChange={setDraft} credentials={{}} invoke={backend.invoke} refresh={()=>{}}/>
}
describe('guided STAR Server connection',()=>{
 it('discovers local key file, imports only on click, and never supplies file contents to React',async()=>{
   const backend=host()
   render(<Harness backend={backend}/>)
   await userEvent.click(screen.getByRole('button',{name:'Connect to STAR Server'}))
   expect(await screen.findByText('A server key file was found on this PC')).toBeTruthy()
   expect(backend.calls.filter(c=>c.action==='importServerKeyFile')).toHaveLength(0)
   await userEvent.click(screen.getByRole('button',{name:'Use it'}))
   await waitFor(()=>expect(backend.calls.filter(c=>c.action==='importServerKeyFile')).toHaveLength(1))
   expect(backend.calls.find(c=>c.action==='importServerKeyFile')?.params).toEqual({})
 })
 it('keeps local selected after a rejected server test',async()=>{
   const backend=host()
   render(<Harness backend={backend}/>)
   await userEvent.click(screen.getByRole('button',{name:'Connect to STAR Server'}))
   await userEvent.type(screen.getByRole('textbox',{name:'Server address'}),'http://192.168.1.20:8080/v1')
   await userEvent.click(screen.getByRole('button',{name:'Test server'}))
   await waitFor(()=>expect(backend.calls.some(c=>c.action==='testServer')).toBe(true))
   expect(backend.calls.find(c=>c.action==='saveSettings')?.params.settings).toMatchObject({provider:'local'})
   desktop.emitRaw('server-connect-test','result',{...okReport,ok:false,code:'wrong_key',message:'Key rejected'})
   expect(await screen.findByText('Key rejected')).toBeTruthy()
   expect(backend.calls.filter(c=>c.action==='saveSettings')).toHaveLength(1)
 })
 it('selects STAR Server only after successful real test response',async()=>{
   const backend=host()
   render(<Harness backend={backend}/>)
   await userEvent.click(screen.getByRole('button',{name:'Connect to STAR Server'}))
   await userEvent.type(screen.getByRole('textbox',{name:'Server address'}),'http://192.168.1.20:8080/v1')
   await userEvent.click(screen.getByRole('button',{name:'Test server'}))
   await waitFor(()=>expect(backend.calls.some(c=>c.action==='testServer')).toBe(true))
   desktop.emitRaw('server-connect-test','result',okReport)
   await waitFor(()=>expect(backend.calls.filter(c=>c.action==='saveSettings').at(-1)?.params.settings).toMatchObject({provider:'star_server'}))
 })

 it('never promotes a server address changed after the successful probe began',async()=>{
   const backend=host()
   render(<Harness backend={backend}/>)
   await userEvent.click(screen.getByRole('button',{name:'Connect to STAR Server'}))
   await userEvent.type(screen.getByRole('textbox',{name:'Server address'}),'http://192.168.1.20:8080/v1')
   await userEvent.click(screen.getByRole('button',{name:'Test server'}))
   await waitFor(()=>expect(backend.calls.filter(c=>c.action==='saveSettings')).toHaveLength(1))
   await userEvent.clear(screen.getByRole('textbox',{name:'Server address'}))
   await userEvent.type(screen.getByRole('textbox',{name:'Server address'}),'http://192.168.1.99:8080/v1')
   desktop.emitRaw('server-connect-test','result',okReport)
   expect(await screen.findByText('Server settings changed during the test. Test again before connecting.')).toBeTruthy()
   expect(backend.calls.filter(c=>c.action==='saveSettings')).toHaveLength(1)
 })
})
