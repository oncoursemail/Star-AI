// @vitest-environment jsdom
import {afterEach,beforeAll,beforeEach,expect,it} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'

let bridge:FakeDesktop
beforeAll(async()=>{bridge=installFakeDesktop();await import('./Desktop')},60000)
beforeEach(()=>bridge.reset())
afterEach(cleanup)

async function start(){
 const user=userEvent.setup()
 render(<App/>)
 const composer=await screen.findByRole('textbox',{name:/message star/i})
 await user.type(composer,'Explain the terrain')
 await user.keyboard('{Enter}')
 const id=await waitFor(()=>bridge.requestOf('sendMessage'))
 bridge.delta(id,'Building the ')
 await screen.findByText('Building the ')
 return {user,id}
}

for(const page of ['Analytics','Settings','Model']){
 it('keeps streaming when visiting '+page+' and returning',async()=>{
  const {user,id}=await start()
  await user.click(screen.getByRole('button',{name:page,exact:true}))
  bridge.delta(id,'mountains')
  expect(bridge.sent('cancelMessage')).toHaveLength(0)
  await user.click(screen.getByRole('button',{name:'Chat',exact:true}))
  expect(await screen.findByText('Building the mountains')).toBeTruthy()
  bridge.complete(id,'Building the mountains')
  expect(await screen.findByText('Building the mountains')).toBeTruthy()
  expect(bridge.sent('cancelMessage')).toHaveLength(0)
 })
}

it('keeps a running turn in its original chat when another chat is viewed',async()=>{
 const chats=[
  {id:'chat-1',title:'Test chat',created:'2026-10-11T12:00:00Z',updated:'2026-10-11T12:00:00Z'},
  {id:'chat-2',title:'Other chat',created:'2026-10-11T12:00:00Z',updated:'2026-10-11T12:00:00Z'}
 ]
 bridge.host({chats})
 bridge.onAction('bootstrap',()=>({ok:true,data:{...bridge.snapshot(),messages:bridge.snapshot().active_chat==='chat-1'?bridge.saved():[]}}))
 bridge.onAction('switchChat',call=>{
  const id=String(call.payload.chatId)
  bridge.host({active_chat:id,messages:id==='chat-2'?[]:bridge.saved()})
  return {ok:true,data:bridge.snapshot()}
 })
 const {user,id}=await start()
 await user.click(screen.getByRole('button',{name:'Other chat'}))
 await waitFor(()=>expect(bridge.sent('switchChat')).toHaveLength(1))
 bridge.delta(id,'mountains')
 expect(screen.queryByText('Building the mountains')).toBeNull()
 expect(bridge.sent('cancelMessage')).toHaveLength(0)
 await user.click(screen.getByRole('button',{name:'Test chat'}))
 expect(await screen.findByText('Building the mountains')).toBeTruthy()
 bridge.complete(id,'Finished terrain guide')
 expect(await screen.findByText('Finished terrain guide')).toBeTruthy()
 expect(bridge.sent('cancelMessage')).toHaveLength(0)
})
