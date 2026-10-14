// @vitest-environment jsdom
/**
 * How a chat turn is rendered (components.tsx): model text is Markdown that must never run code,
 * load remote images or open unsafe links; copying falls back to the desktop host; only local
 * image data is shown; and turns that ended without an answer offer the right next step.
 */
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import type {ChatMessage} from './types'

const bridge=vi.hoisted(()=>({request:vi.fn()}))
vi.mock('./bridge',async importOriginal=>({...await importOriginal<typeof import('./bridge')>(),request:bridge.request}))

import {Message,copySafe} from './components'

const star=(text:string,extra:Partial<ChatMessage>={}):ChatMessage=>({id:'a1',role:'assistant',text,...extra})
const user=(text:string,extra:Partial<ChatMessage>={}):ChatMessage=>({id:'u1',role:'user',text,...extra})
const PNG='data:image/png;base64,iVBORw0KGgo='
const WEBP='data:image/webp;base64,UklGRg=='

let clipboard:{writeText:ReturnType<typeof vi.fn>}
beforeEach(()=>{
 bridge.request.mockReset()
 bridge.request.mockResolvedValue({ok:true})
 clipboard={writeText:vi.fn(async()=>undefined)}
 Object.defineProperty(navigator,'clipboard',{configurable:true,value:clipboard})
})
afterEach(()=>{cleanup();vi.useRealTimers()})

describe('model text is shown as safe Markdown',()=>{
 it('opens only http(s) and mailto links, in a new window without an opener',()=>{
  render(<Message animated={false} entry={star('[docs](https://create.roblox.com/docs) [mail](mailto:owner@example.com) [bad](javascript:alert(1)) [data](data:text/html,hi)')}/>)
  const docs=screen.getByRole('link',{name:'docs'})
  expect(docs.getAttribute('href')).toBe('https://create.roblox.com/docs')
  expect(docs.getAttribute('target')).toBe('_blank')
  expect(docs.getAttribute('rel')).toBe('noopener noreferrer')
  expect(screen.getByRole('link',{name:'mail'})).toBeTruthy()
  expect(screen.queryByRole('link',{name:'bad'})).toBeNull()
  expect(screen.queryByRole('link',{name:'data'})).toBeNull()
  expect(screen.getByText('bad').tagName).toBe('SPAN')            // the words stay, the link does not
 })
 it('never renders raw HTML or loads a remote image',()=>{
  const {container}=render(<Message animated={false} entry={star('Before <img src="x" onerror="alert(1)"> after\n\n![enemy model](https://evil.example/track.png)')}/>)
  expect(container.querySelector('img')).toBeNull()
  expect(container.querySelector('[onerror]')).toBeNull()
  expect(screen.getByText(/enemy model \(not loaded/)).toBeTruthy()
 })
 it('labels a code block with its language and copies exactly the code',async()=>{
  render(<Message animated={false} entry={star('Try this:\n\n```lua\nlocal part = Instance.new("Part")\nprint(part)\n```\n')}/>)
  expect(screen.getByText('lua')).toBeTruthy()
  await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Copy code'}))})
  expect(clipboard.writeText).toHaveBeenCalledWith('local part = Instance.new("Part")\nprint(part)')
 })
 it('wraps tables so wide ones scroll instead of breaking the layout',()=>{
  const {container}=render(<Message animated={false} entry={star('| a | b |\n|---|---|\n| 1 | 2 |')}/>)
  expect(container.querySelector('.md-table > table')).not.toBeNull()
 })
})

describe('copying',()=>{
 it('shows "Copied" briefly after a successful copy',async()=>{
  vi.useFakeTimers()
  render(<Message animated={false} entry={star('Hello')}/>)
  await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Copy response'}))})
  expect(screen.getByRole('button',{name:'Copied'})).toBeTruthy()
  await act(async()=>{vi.advanceTimersByTime(1400)})
  expect(screen.getByRole('button',{name:'Copy response'})).toBeTruthy()
 })
 it('falls back to the desktop host when the browser clipboard refuses',async()=>{
  clipboard.writeText.mockRejectedValue(new Error('denied on file://'))
  expect(await copySafe('text')).toBe(true)
  expect(bridge.request).toHaveBeenCalledWith('copyText',{text:'text'})
 })
 it('does not claim a copy that the host could not make either',async()=>{
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined})
  bridge.request.mockResolvedValue({ok:false,error:'Open STAR Desktop'})
  render(<Message animated={false} entry={user('My question')}/>)
  await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Copy your message'}))})
  expect(screen.queryByRole('button',{name:'Copied'})).toBeNull()
 })
})

describe('pictures in a turn',()=>{
 it('shows only local PNG, JPEG or WebP screenshots the owner attached',()=>{
  render(<Message animated={false} entry={user('See',{previews:[PNG,'https://evil.example/a.png','data:image/svg+xml;base64,PHN2Zz4=',WEBP],attachments:['notes.txt']})}/>)
  const thumbs=within(screen.getByLabelText('Attached screenshots')).getAllByRole('img')
  expect(thumbs.map(img=>img.getAttribute('src'))).toEqual([PNG,WEBP])
  expect(within(screen.getByLabelText('Attached files')).getByText('notes.txt')).toBeTruthy()
 })
 it('offers a generated image only when it is local WebP data',()=>{
  const {rerender}=render(<Message animated={false} entry={star('Here it is',{image:WEBP})}/>)
  expect(screen.getByRole('button',{name:'Expand generated image'})).toBeTruthy()
  expect(screen.getByText('Saved locally')).toBeTruthy()
  rerender(<Message animated={false} entry={star('Here it is',{image:'https://evil.example/a.webp'})}/>)
  expect(screen.queryByRole('button',{name:'Expand generated image'})).toBeNull()
 })
})

describe('actions on a finished answer',()=>{
 it('toggles a rating off when the same thumb is pressed again',()=>{
  const onFeedback=vi.fn()
  const {rerender}=render(<Message animated={false} entry={star('Answer')} onFeedback={onFeedback}/>)
  fireEvent.click(screen.getByRole('button',{name:'Helpful'}))
  expect(onFeedback).toHaveBeenLastCalledWith('up')
  rerender(<Message animated={false} entry={star('Answer',{feedback:'up'})} onFeedback={onFeedback}/>)
  expect(screen.getByRole('button',{name:'Helpful'}).getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(screen.getByRole('button',{name:'Helpful'}))
  expect(onFeedback).toHaveBeenLastCalledWith('')
  fireEvent.click(screen.getByRole('button',{name:'Not helpful'}))
  expect(onFeedback).toHaveBeenLastCalledWith('down')
 })
 it('never offers ratings on the owner\'s own message, nor actions while writing',()=>{
  const {rerender}=render(<Message animated={false} entry={user('Mine')} onFeedback={vi.fn()} onEdit={vi.fn()}/>)
  expect(screen.queryByRole('button',{name:'Helpful'})).toBeNull()
  expect(screen.getByText('Edit')).toBeTruthy()
  rerender(<Message animated={false} partial entry={star('Half an ans')} onFeedback={vi.fn()} onAskAgain={vi.fn()}/>)
  expect(screen.getByLabelText('STAR said').getAttribute('aria-busy')).toBe('true')
  expect(screen.queryByRole('button',{name:'Copy response'})).toBeNull()
  expect(screen.queryByText('Ask again')).toBeNull()
 })
})

describe('turns that ended without an answer',()=>{
 it('leads with the connection page when the model could not be reached',()=>{
  const onConnection=vi.fn(),onRetry=vi.fn()
  render(<Message animated={false} entry={{id:'e1',role:'event',status:'failed',text:'ConnectionError: Cannot reach the STAR Server'}}
   onRetry={onRetry} onConnection={onConnection}/>)
  const article=screen.getByLabelText('STAR could not answer')
  expect(within(article).getByText("Can't reach the model")).toBeTruthy()
  expect(within(article).getByText('Cannot reach the STAR Server')).toBeTruthy()   // the error class name is dropped
  const connection=screen.getByRole('button',{name:'Model & connection'})
  expect(connection.className).toContain('is-primary')
  expect(screen.getByRole('button',{name:'Retry'}).className).not.toContain('is-primary')
  fireEvent.click(connection)
  expect(onConnection).toHaveBeenCalledOnce()
 })
 it('makes Retry the main action for other failures and offers no connection detour',()=>{
  render(<Message animated={false} entry={{id:'e2',role:'event',status:'failed',text:'TimeoutError: STAR exceeded its 600s task budget.'}}
   onRetry={vi.fn()} onConnection={vi.fn()} onEdit={vi.fn()}/>)
  expect(screen.getByText('That took too long')).toBeTruthy()
  expect(screen.queryByRole('button',{name:'Model & connection'})).toBeNull()
  expect(screen.getByRole('button',{name:'Retry'}).className).toContain('is-primary')
  expect(screen.getByRole('button',{name:'Edit message'})).toBeTruthy()
 })
 it('marks a stopped turn as stopped, with no actions on older turns',()=>{
  render(<Message animated={false} entry={{id:'e3',role:'event',status:'cancelled',text:'Request stopped by the owner.'}}/>)
  expect(screen.getByLabelText('Stopped')).toBeTruthy()
  expect(screen.queryByRole('button')).toBeNull()
 })
})
