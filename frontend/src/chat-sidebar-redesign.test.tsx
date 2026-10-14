// @vitest-environment jsdom
/** Redesign 2026-10-13: ChatGPT-like chat management, "Look at my screen" with consent, quiet composer. */
import {afterEach,beforeAll,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'
import {MotionPolicy} from './MotionPolicy'
import {StarFace,starFaceSource} from './StarFace'

let bridge:FakeDesktop
beforeAll(async()=>{bridge=installFakeDesktop();await import('./Desktop')},60000)
const chats=[
 {id:'chat-1',title:'Test chat',created:'2026-10-13T12:00:00Z',updated:'2026-10-13T12:00:00Z'},
 {id:'chat-2',title:'Lantern model',created:'2026-10-13T11:00:00Z',updated:'2026-10-13T11:00:00Z'},
]
beforeEach(()=>{bridge.reset([{id:'',role:'user',text:'hello',created:''}]);bridge.host({chats});try{localStorage.clear()}catch{/* storage optional */}})
afterEach(()=>{cleanup();vi.useRealTimers()})

async function open(){
 const user=userEvent.setup()
 render(<App/>)
 await screen.findByRole('textbox',{name:/message star/i})
 return user
}
const sidebar=()=>within(screen.getByLabelText('Saved conversations'))

describe('sidebar chat menu',()=>{
 it('renames a chat in place and sends exactly one renameChat',async()=>{
  bridge.onAction('renameChat',call=>({ok:true,data:{chatId:call.payload.chatId,title:String(call.payload.title)}}))
  const user=await open()
  await user.click(sidebar().getByRole('button',{name:'More options for Lantern model'}))
  await user.click(screen.getByRole('menuitem',{name:'Rename'}))
  const input=screen.getByRole('textbox',{name:'Chat name'})
  await user.clear(input)
  await user.type(input,'Blender lantern{Enter}')
  expect(sidebar().getByRole('button',{name:'Blender lantern'})).toBeTruthy()
  expect(bridge.sent('renameChat')).toHaveLength(1)
  expect(bridge.sent('renameChat')[0].payload).toMatchObject({chatId:'chat-2',title:'Blender lantern'})
 })
 it('Escape cancels a rename without asking the host',async()=>{
  const user=await open()
  await user.click(sidebar().getByRole('button',{name:'More options for Lantern model'}))
  await user.click(screen.getByRole('menuitem',{name:'Rename'}))
  await user.type(screen.getByRole('textbox',{name:'Chat name'}),' changed{Escape}')
  expect(sidebar().getByRole('button',{name:'Lantern model'})).toBeTruthy()
  expect(bridge.sent('renameChat')).toHaveLength(0)
 })
 it('puts the old title back when the host refuses a rename',async()=>{
  bridge.onAction('renameChat',()=>({ok:false,error:'Conversation not found in this workspace'}))
  const user=await open()
  await user.click(sidebar().getByRole('button',{name:'More options for Lantern model'}))
  await user.click(screen.getByRole('menuitem',{name:'Rename'}))
  const input=screen.getByRole('textbox',{name:'Chat name'})
  await user.clear(input)
  await user.type(input,'Nope{Enter}')
  await waitFor(()=>expect(sidebar().getByRole('button',{name:'Lantern model'})).toBeTruthy())
 })
 it('hides a deleted chat at once, and Undo keeps it: nothing is sent to the host',async()=>{
  const user=await open()
  await user.click(sidebar().getByRole('button',{name:'More options for Lantern model'}))
  await user.click(screen.getByRole('menuitem',{name:'Delete'}))
  await waitFor(()=>expect(sidebar().queryByRole('button',{name:'Lantern model'})).toBeNull())
  const toast=screen.getByText(/Deleted/).closest('[role="status"]') as HTMLElement
  await user.click(within(toast).getByRole('button',{name:/Undo/}))
  expect(await sidebar().findByRole('button',{name:'Lantern model'})).toBeTruthy()
  expect(bridge.sent('deleteChat')).toHaveLength(0)
 })
 it('removes the chat for good only after the Undo window',async()=>{
  vi.useFakeTimers({shouldAdvanceTime:true})
  bridge.onAction('deleteChat',()=>({ok:true,data:{...bridge.snapshot(),chats:[chats[0]]}}))
  const user=userEvent.setup({advanceTimers:vi.advanceTimersByTime})
  render(<App/>)
  await screen.findByRole('textbox',{name:/message star/i})
  await user.click(sidebar().getByRole('button',{name:'More options for Lantern model'}))
  await user.click(screen.getByRole('menuitem',{name:'Delete'}))
  expect(bridge.sent('deleteChat')).toHaveLength(0)
  await act(async()=>{vi.advanceTimersByTime(6100)})
  await waitFor(()=>expect(bridge.sent('deleteChat')).toHaveLength(1))
  expect(bridge.sent('deleteChat')[0].payload).toEqual({chatId:'chat-2'})
  expect(sidebar().queryByRole('button',{name:'Lantern model'})).toBeNull()
 })
 it('deleting the open chat starts a fresh one straight away',async()=>{
  const user=await open()
  await user.click(sidebar().getByRole('button',{name:'More options for Test chat'}))
  await user.click(screen.getByRole('menuitem',{name:'Delete'}))
  await waitFor(()=>expect(bridge.sent('newChat')).toHaveLength(1))
 })
})

describe('look at my screen',()=>{
 it('asks first; Cancel captures nothing',async()=>{
  const user=await open()
  await user.click(screen.getByRole('button',{name:'Add files and tools'}))
  await user.click(screen.getByRole('menuitem',{name:/Look at my screen/}))
  const dialog=await screen.findByRole('dialog',{name:'Let STAR look at your screen?'})
  await user.click(within(dialog).getByRole('button',{name:'Cancel'}))
  expect(bridge.sent('captureScreen')).toHaveLength(0)
 })
 it('captures once with explicit consent and attaches the picture with a thumbnail',async()=>{
  bridge.onAction('captureScreen',()=>({ok:true,data:{path:'C:\\STAR\\screen-captures\\screen-20261013-120000.png',name:'screen-20261013-120000.png',width:1920,height:1080,preview:'data:image/jpeg;base64,AAAA'}}))
  const user=await open()
  await user.click(screen.getByRole('button',{name:'Add files and tools'}))
  await user.click(screen.getByRole('menuitem',{name:/Look at my screen/}))
  await user.click(await screen.findByRole('button',{name:'Take screenshot'}))
  await waitFor(()=>expect(bridge.sent('captureScreen')).toHaveLength(1))
  expect(bridge.sent('captureScreen')[0].payload).toEqual({consent:true})
  const files=await screen.findByRole('list',{name:'Attachments'})
  expect(files.textContent).toContain('screen-20261013-120000.png')
  expect(files.querySelector('img')?.getAttribute('src')).toBe('data:image/jpeg;base64,AAAA')
  expect((screen.getByRole('textbox',{name:/message star/i}) as HTMLTextAreaElement).value).toBe('What do you see on my screen?')
  await user.keyboard('{Enter}')
  await waitFor(()=>expect(bridge.sent('sendMessage')).toHaveLength(1))
  expect(bridge.sent('sendMessage')[0].payload.files).toEqual(['C:\\STAR\\screen-captures\\screen-20261013-120000.png'])
  expect(await screen.findByRole('img',{name:'Screenshot you attached'})).toBeTruthy()
 })
})

describe('quiet composer and sidebar',()=>{
 it('keeps advanced places folded under More and the mode in one pill',async()=>{
  const user=await open()
  const nav=within(screen.getByRole('navigation',{name:'Workspace'}))
  expect(nav.getByRole('button',{name:/Projects/})).toBeTruthy()
  expect(nav.getByRole('button',{name:'Tools'})).toBeTruthy()
  expect(nav.queryByRole('button',{name:'Analytics'})).toBeNull()
  expect(screen.queryByRole('radiogroup',{name:'How STAR should work'})).toBeNull()
  await user.click(screen.getByRole('button',{name:'Mode: Auto'}))
  await user.click(screen.getByRole('radio',{name:'Agent'}))
  expect(screen.getByRole('button',{name:'Mode: Agent'})).toBeTruthy()
  expect(screen.queryByRole('radiogroup',{name:'How STAR should work'})).toBeNull()
 })
 it('opens the + menu short, with the rarer tools behind More',async()=>{
  const user=await open()
  await user.click(screen.getByRole('button',{name:'Add files and tools'}))
  expect(screen.getByRole('menuitem',{name:/Add photos and files/})).toBeTruthy()
  expect(screen.getByRole('menuitemcheckbox',{name:/Create image/})).toBeTruthy()
  expect(screen.queryByRole('menuitem',{name:/Transcribe audio/})).toBeNull()
  await user.click(screen.getByRole('menuitem',{name:'More'}))
  expect(screen.getByRole('menuitem',{name:/Transcribe audio/})).toBeTruthy()
 })
})

describe('Star face',()=>{
 it('uses approved art for each mood and holds still with reduced motion',()=>{
  expect(starFaceSource('thinking')).toBe('./assets/mascot/faces/thinking.png')
  expect(starFaceSource('happy')).toBe('./assets/mascot/faces/happy.png')
  const {container,rerender}=render(<MotionPolicy reduced><StarFace mood="idle" label="Star"/></MotionPolicy>)
  const face=container.querySelector('.star-face') as HTMLElement
  expect(face.dataset.still).toBe('true')
  expect(container.querySelector('.star-face-blink')).toBeNull()
  rerender(<MotionPolicy reduced><StarFace mood="thinking" label="Star"/></MotionPolicy>)
  expect(container.querySelectorAll('.star-face-img')).toHaveLength(1)
  expect(container.querySelector('.star-face-img')?.getAttribute('src')).toBe('./assets/mascot/faces/thinking.png')
 })
 it('cross-fades and blinks when motion is allowed, and disappears if the art is missing',()=>{
  const {container,rerender}=render(<MotionPolicy reduced={false}><StarFace mood="idle"/></MotionPolicy>)
  expect(container.querySelector('.star-face-blink')).toBeTruthy()
  rerender(<MotionPolicy reduced={false}><StarFace mood="thinking"/></MotionPolicy>)
  expect(container.querySelector('.star-face-img.is-leaving')).toBeTruthy()
  fireEvent.error(container.querySelector('.star-face-img:not(.is-leaving)') as HTMLImageElement)
  expect(container.querySelector('.star-face')).toBeNull()
 })
})
