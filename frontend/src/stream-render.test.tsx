// @vitest-environment jsdom
/** A streaming answer re-parses only its live tail, not the finished paragraphs (proposal #325 item 7). */
import {afterEach,beforeAll,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const parsed:string[]=[]
vi.mock('react-markdown',async importOriginal=>{
 const actual=await importOriginal<typeof import('react-markdown')>()
 const Real=actual.default
 return {...actual,default:(props:Parameters<typeof Real>[0])=>{parsed.push(String(props.children??''));return Real(props)}}
})

import {App} from './App'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'

let bridge:FakeDesktop
beforeAll(async()=>{bridge=installFakeDesktop();await import('./Desktop')},60000)
beforeEach(()=>{bridge.reset();parsed.length=0})
afterEach(cleanup)

it('parses a finished paragraph once while the answer keeps streaming',async()=>{
 const user=userEvent.setup()
 render(<App/>)
 const composer=await screen.findByRole('textbox',{name:/message star/i})
 await user.type(composer,'Explain spawning')
 await user.keyboard('{Enter}')
 const id=await waitFor(()=>bridge.requestOf('sendMessage'))
 bridge.delta(id,'First paragraph about spawning.\n\nSecond')
 await screen.findByText('Second')
 const words=[' one',' two',' three',' four',' five']
 let live='Second'
 for(const word of words){
  live+=word
  bridge.delta(id,word)
  await screen.findByText(live)
 }
 expect(screen.getByText('First paragraph about spawning.')).toBeTruthy()
 const withFirst=parsed.filter(text=>text.includes('First paragraph about spawning.'))
 // Before: every delta re-parsed the whole answer (6+ times). Now the finished block is parsed once.
 expect(withFirst.length).toBeLessThanOrEqual(2)
 bridge.complete(id,'First paragraph about spawning.\n\nSecond one two three four five six.')
 expect(await screen.findByText('Second one two three four five six.')).toBeTruthy()
})
