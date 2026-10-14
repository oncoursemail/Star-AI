// @vitest-environment jsdom
import {useRef,useState} from 'react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {Composer,type Availability,type ChatMode} from './Composer'
import type {Connection} from './connection'
import {MotionPolicy} from './MotionPolicy'

afterEach(cleanup)
const connection:Connection={tone:'unverified',label:'This PC · demo',state:'Not checked',provider:'This PC',model:'demo',endpoint:'',note:'No response has been checked.'}
const callbacks=()=>({send:vi.fn(),stop:vi.fn(),attach:vi.fn(),transcribe:vi.fn(),setup:vi.fn(),openConnection:vi.fn()})
type Actions=ReturnType<typeof callbacks>
type Options={busy?:boolean;stopping?:boolean;files?:string[];web?:Availability;team?:Availability}
function Harness({actions,options={}}:{actions:Actions;options?:Options}){
 const inputRef=useRef<HTMLTextAreaElement>(null)
 const [value,onChange]=useState('')
 const [files,setFiles]=useState(options.files??[])
 const [mode,setMode]=useState<ChatMode>('auto')
 const [imageMode,setImageMode]=useState(false)
 const [imageSize,setImageSize]=useState('square')
 const [teamMode,setTeamMode]=useState(false)
 const [research,setResearch]=useState(false)
 const [githubSource,setGithubSource]=useState(false)
 return <MotionPolicy reduced><Composer inputRef={inputRef} value={value} onChange={onChange}
  onSend={actions.send} onStop={actions.stop} busy={!!options.busy} stopping={!!options.stopping}
  files={files} onRemoveFile={index=>setFiles(current=>current.filter((_,i)=>i!==index))}
  onAttach={actions.attach} onTranscribe={actions.transcribe}
  mode={mode} onMode={next=>{setMode(next);if(next!=='agent')setGithubSource(false)}}
  imageMode={imageMode} onImageMode={setImageMode} imageReady={false} onImageSetup={actions.setup}
  imageSize={imageSize} onImageSize={setImageSize}
  teamMode={teamMode} onTeamMode={setTeamMode} team={options.team??{ok:true}}
  research={research} onResearch={setResearch} web={options.web??{ok:true}}
  githubSource={githubSource} onGithubSource={setGithubSource}
  connection={connection} onOpenConnection={actions.openConnection}/></MotionPolicy>
}
const launch=(options:Options={})=>{
 const actions=callbacks()
 render(<Harness actions={actions} options={options}/>)
 return actions
}

describe('composer controls used by the desktop chat',()=>{
 it('never sends whitespace, supports Shift+Enter, and sends nonempty text on Enter',async()=>{
  const actions=launch()
  const user=userEvent.setup()
  const input=screen.getByRole('textbox',{name:'Message STAR'})
  expect(screen.getByRole('button',{name:'Send message'})).toHaveProperty('disabled',true)
  await user.type(input,'   ')
  await user.keyboard('{Enter}')
  expect(actions.send).not.toHaveBeenCalled()
  await user.type(input,'Check my Luau')
  await user.keyboard('{Shift>}{Enter}{/Shift}')
  expect((input as HTMLTextAreaElement).value).toContain('\n')
  expect(actions.send).not.toHaveBeenCalled()
  await user.keyboard('{Enter}')
  expect(actions.send).toHaveBeenCalledOnce()
 })
 it('switches modes with arrow keys and exposes the requested mode to assistive technology',()=>{
  launch()
  // The mode is one small pill; its choices open in a picker.
  fireEvent.click(screen.getByRole('button',{name:'Mode: Auto'}))
  const modes=screen.getByRole('radiogroup',{name:'How STAR should work'})
  const selected=within(modes).getByRole('radio',{name:'Auto'})
  expect(selected.getAttribute('aria-checked')).toBe('true')
  selected.focus()
  fireEvent.keyDown(modes,{key:'ArrowRight'})
  const agent=within(modes).getByRole('radio',{name:'Agent'})
  expect(agent.getAttribute('aria-checked')).toBe('true')
  expect(document.activeElement).toBe(agent)
 })
 it('does not enable an unavailable web tool, and Escape closes the menu and restores focus',async()=>{
  const actions=launch({web:{ok:false,reason:'Web is not configured'}})
  const user=userEvent.setup()
  const add=screen.getByRole('button',{name:'Add files and tools'})
  await user.click(add)
  const blocked=screen.getByRole('menuitemcheckbox',{name:/Search the web/})
  expect(blocked.getAttribute('aria-disabled')).toBe('true')
  expect(screen.getByText('Web is not configured')).toBeTruthy()
  await user.click(blocked)
  expect(screen.queryByRole('button',{name:'Stop searching the web'})).toBeNull()
  expect(actions.send).not.toHaveBeenCalled()
  await user.keyboard('{Escape}')
  expect(add.getAttribute('aria-expanded')).toBe('false')
  expect(document.activeElement).toBe(add)
 })
 it('offers all image sizes and asks for setup without sending a chat message',async()=>{
  const actions=launch()
  const user=userEvent.setup()
  await user.click(screen.getByRole('button',{name:'Add files and tools'}))
  await user.click(screen.getByRole('menuitemcheckbox',{name:/Create image/}))
  expect(screen.getByPlaceholderText('Describe the image you want to create')).toBeTruthy()
  const size=screen.getByRole('combobox',{name:'Image size'})
  await user.selectOptions(size,'tall')
  expect((size as HTMLSelectElement).value).toBe('tall')
  expect(within(size).getAllByRole('option')).toHaveLength(4)
  await user.click(screen.getByRole('button',{name:/Set up image creation/}))
  expect(actions.setup).toHaveBeenCalledOnce()
  expect(actions.send).not.toHaveBeenCalled()
 })
 it('removes only the selected attachment and prevents accidental double-click cancellation',async()=>{
  const actions=launch({files:['C:\\game\\map.rbxl','/project/ref.png'],busy:true})
  const user=userEvent.setup()
  expect(screen.getByRole('list',{name:'Attachments'}).textContent).toContain('map.rbxl')
  await user.click(screen.getByRole('button',{name:'Remove map.rbxl'}))
  expect(screen.getByRole('list',{name:'Attachments'}).textContent).toContain('ref.png')
  expect(screen.getByRole('list',{name:'Attachments'}).textContent).not.toContain('map.rbxl')
  const stop=screen.getByRole('button',{name:'Stop response'})
  fireEvent.click(stop,{detail:2})
  expect(actions.stop).not.toHaveBeenCalled()
  fireEvent.click(stop,{detail:1})
  expect(actions.stop).toHaveBeenCalledOnce()
 })
})
