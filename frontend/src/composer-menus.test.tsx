// @vitest-environment jsdom
/**
 * The composer's menus and modes (Composer.tsx): which tools can be combined, what each mode
 * offers, keyboard and outside-press behaviour, and the connection popover. composer.test.tsx
 * covers sending, the mode radio group, image sizes and attachment removal.
 */
import {useRef,useState} from 'react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {Composer,type Availability,type ChatMode} from './Composer'
import type {Connection} from './connection'
import {MotionPolicy} from './MotionPolicy'

afterEach(cleanup)
const baseConnection:Connection={tone:'ready',label:'STAR Server · qwen',state:'Connected',provider:'STAR Server',model:'',endpoint:'http://127.0.0.1:8080/v1',note:'Answered a test message.'}
type Options={busy?:boolean;files?:string[];previews?:Record<string,string>;mode?:ChatMode;web?:Availability;team?:Availability;screen?:boolean;connection?:Partial<Connection>}
const actions=()=>({attach:vi.fn(),transcribe:vi.fn(),screen:vi.fn(),openConnection:vi.fn(),setup:vi.fn()})
function Harness({spy,options}:{spy:ReturnType<typeof actions>;options:Options}){
 const inputRef=useRef<HTMLTextAreaElement>(null)
 const [value,setValue]=useState('')
 const [mode,setMode]=useState<ChatMode>(options.mode??'auto')
 const [imageMode,setImageMode]=useState(false)
 const [teamMode,setTeamMode]=useState(false)
 const [research,setResearch]=useState(false)
 const [githubSource,setGithubSource]=useState(false)
 return <MotionPolicy reduced><div className="thread"><Composer inputRef={inputRef} value={value} onChange={setValue}
  onSend={vi.fn()} onStop={vi.fn()} busy={!!options.busy} stopping={false}
  files={options.files??[]} previews={options.previews} onRemoveFile={vi.fn()} onAttach={spy.attach} onTranscribe={spy.transcribe}
  mode={mode} onMode={setMode} imageMode={imageMode} onImageMode={setImageMode} imageReady={false} onImageSetup={spy.setup}
  imageSize="square" onImageSize={vi.fn()} teamMode={teamMode} onTeamMode={setTeamMode} team={options.team??{ok:true}}
  research={research} onResearch={setResearch} web={options.web??{ok:true}} githubSource={githubSource} onGithubSource={setGithubSource}
  connection={{...baseConnection,...options.connection}} onOpenConnection={spy.openConnection}
  onLookAtScreen={options.screen?spy.screen:undefined}/></div></MotionPolicy>
}
const launch=(options:Options={})=>{const spy=actions();render(<Harness spy={spy} options={options}/>);return spy}
const addButton=()=>screen.getByRole('button',{name:'Add files and tools'})
const openMenu=()=>fireEvent.click(addButton())
/** The open menu. A menu that is closing may still be fading out, so the newest one counts. */
const menu=()=>screen.getAllByRole('menu',{name:'Add to this message'}).at(-1) as HTMLElement
const items=()=>Array.from(menu().querySelectorAll<HTMLButtonElement>('[role^="menuitem"]'))
const item=(name:RegExp)=>{
 const found=items().find(entry=>name.test(entry.textContent||''))
 if(!found)throw new Error('No menu item '+name)
 return found
}
const hasItem=(name:RegExp)=>items().some(entry=>name.test(entry.textContent||''))
const showMore=()=>{if(!hasItem(/Use a team/))fireEvent.click(item(/^More$/))}
const choose=(name:RegExp)=>{openMenu();if(!hasItem(name))showMore();fireEvent.click(item(name))}
const isOpen=(trigger:HTMLElement)=>trigger.getAttribute('aria-expanded')==='true'
const prompt=()=>screen.getByLabelText('Message STAR',{selector:'textarea'}) as HTMLTextAreaElement

describe('tools that cannot be combined say why',()=>{
 it('blocks web search, teams and source reading while creating an image',()=>{
  launch({mode:'agent'})
  choose(/Create image/)
  expect(prompt().placeholder).toBe('Describe the image you want to create')
  openMenu()
  showMore()
  for(const [name,reason] of [[/Search the web/,'Not with images'],[/Use a team/,'Not with images'],[/Read STAR source/,'Not in this mode']] as const){
   const entry=item(name)
   expect(entry.getAttribute('aria-disabled')).toBe('true')
   expect(entry.textContent).toContain(reason)
   fireEvent.click(entry)                                   // a blocked item does nothing
  }
  expect(screen.queryByRole('button',{name:'Stop searching the web'})).toBeNull()
  expect(screen.queryByRole('button',{name:'Stop using a team'})).toBeNull()
 })
 it('keeps a team run text only and hides the mode picker',()=>{
  const spy=launch({screen:true})
  choose(/Use a team/)
  expect(prompt().placeholder).toBe('Give the team an objective')
  expect(screen.queryByRole('button',{name:/^Mode:/})).toBeNull()
  openMenu()
  fireEvent.click(item(/Add photos and files/))
  fireEvent.click(item(/Look at my screen/))
  expect(spy.attach).not.toHaveBeenCalled()
  expect(spy.screen).not.toHaveBeenCalled()
  expect(item(/Add photos and files/).textContent).toContain('Team runs are text only')
  fireEvent.click(screen.getByRole('button',{name:'Stop using a team'}))
  expect(prompt().placeholder).toBe('Message STAR')
 })
 it('offers reading STAR source only in Agent mode and shows it as a removable chip',()=>{
  launch({mode:'auto'})
  openMenu()
  showMore()
  expect(item(/Read STAR source/).textContent).toContain('Agent mode only')
  cleanup()
  launch({mode:'agent'})
  choose(/Read STAR source/)
  fireEvent.click(screen.getByRole('button',{name:'Stop reading STAR source'}))
  expect(screen.queryByRole('button',{name:'Stop reading STAR source'})).toBeNull()
 })
 it('shows why web search is unavailable instead of turning it on',()=>{
  launch({web:{ok:false,reason:'Turn on Research in Settings'}})
  openMenu()
  const web=item(/Search the web/)
  expect(web.textContent).toContain('Turn on Research in Settings')
  fireEvent.click(web)
  expect(screen.queryByRole('button',{name:'Stop searching the web'})).toBeNull()
 })
})

describe('image mode',()=>{
 it('guides through editing: picture, then mask, then a prompt for the masked area',()=>{
  const spy=launch({files:['C:\\Users\\me\\Pictures\\castle.png']})
  choose(/Create image/)
  expect(prompt().placeholder).toBe('Describe how to change the attached picture')
  fireEvent.click(screen.getByRole('button',{name:'Add a mask (white = the part to change)'}))
  expect(spy.attach).toHaveBeenCalledOnce()
  fireEvent.click(screen.getByRole('button',{name:/Set up image creation/}))
  expect(spy.setup).toHaveBeenCalledOnce()
  cleanup()
  launch({files:['a.png','mask.png']})
  choose(/Create image/)
  expect(prompt().placeholder).toBe('Describe what should appear in the masked area')
  expect(screen.queryByRole('button',{name:/Add a mask/})).toBeNull()
 })
})

describe('the add menu',()=>{
 it('opens short every time: the extra tools fold away when it closes',()=>{
  launch()
  openMenu()
  showMore()
  expect(item(/Transcribe audio/)).toBeTruthy()
  openMenu()                                               // close
  openMenu()                                               // reopen
  expect(hasItem(/Transcribe audio/)).toBe(false)
 })
 it('walks its items with the arrow keys, Home and End',()=>{
  launch({screen:true})
  openMenu()
  const all=items()
  expect(document.activeElement).toBe(all[0])              // the first item takes focus
  fireEvent.keyDown(menu(),{key:'ArrowUp'})
  expect(document.activeElement).toBe(all[all.length-1])
  fireEvent.keyDown(menu(),{key:'Home'})
  expect(document.activeElement).toBe(all[0])
  fireEvent.keyDown(menu(),{key:'ArrowDown'})
  expect(document.activeElement).toBe(all[1])
  fireEvent.keyDown(menu(),{key:'End'})
  expect(document.activeElement).toBe(all[all.length-1])
 })
 it('closes on a press outside it, but not on a press inside it',()=>{
  launch()
  openMenu()
  fireEvent.pointerDown(menu())
  expect(isOpen(addButton())).toBe(true)
  fireEvent.pointerDown(document.body)
  expect(isOpen(addButton())).toBe(false)
 })
 it('runs the chosen action once and closes',()=>{
  const spy=launch({screen:true})
  choose(/Transcribe audio/)
  expect(spy.transcribe).toHaveBeenCalledOnce()
  expect(isOpen(addButton())).toBe(false)
  choose(/Look at my screen/)
  expect(spy.screen).toHaveBeenCalledOnce()
 })
 it('leaves out "Look at my screen" where it cannot work, and is disabled while STAR answers',()=>{
  launch()
  openMenu()
  expect(hasItem(/Look at my screen/)).toBe(false)
  cleanup()
  launch({busy:true})
  expect((screen.getByRole('button',{name:'Add files and tools'}) as HTMLButtonElement).disabled).toBe(true)
  expect((screen.getByRole('button',{name:/^Mode:/}) as HTMLButtonElement).disabled).toBe(true)
 })
})

describe('attachments and the connection popover',()=>{
 it('names attachments by file name and shows a thumbnail when there is one',()=>{
  const path='C:\\Users\\me\\Desktop\\shot.png'
  launch({files:[path,'/home/me/notes.txt'],previews:{[path]:'data:image/png;base64,AAAA'}})
  const list=screen.getByRole('list',{name:'Attachments'})
  expect(within(list).getByText('shot.png')).toBeTruthy()
  expect(within(list).getByText('notes.txt')).toBeTruthy()
  expect(list.querySelectorAll('img.cmp-file-thumb')).toHaveLength(1)
 })
 it('shows provider, model, answering model and address, and links to the settings page',()=>{
  const spy=launch({connection:{answeredBy:'qwen3-coder'}})
  fireEvent.click(screen.getByRole('button',{name:/STAR Server · qwen/}))
  const pop=screen.getByRole('dialog',{name:'Model connection'})
  expect(within(pop).getByText('None selected')).toBeTruthy()
  expect(within(pop).getByText('qwen3-coder')).toBeTruthy()
  expect(within(pop).getByText('http://127.0.0.1:8080/v1')).toBeTruthy()
  fireEvent.click(within(pop).getByRole('button',{name:/Model & connection/}))
  expect(spy.openConnection).toHaveBeenCalledOnce()
  expect(isOpen(screen.getByRole('button',{name:/STAR Server · qwen/}))).toBe(false)
 })
 it('keeps one popover open at a time',()=>{
  launch()
  const status=screen.getByRole('button',{name:/STAR Server · qwen/})
  const modeButton=screen.getByRole('button',{name:/^Mode:/})
  fireEvent.click(status)
  openMenu()
  expect([isOpen(status),isOpen(addButton()),isOpen(modeButton)]).toEqual([false,true,false])
  fireEvent.click(modeButton)
  expect([isOpen(status),isOpen(addButton()),isOpen(modeButton)]).toEqual([false,false,true])
  fireEvent.click(status)
  expect([isOpen(status),isOpen(addButton()),isOpen(modeButton)]).toEqual([true,false,false])
 })
})
