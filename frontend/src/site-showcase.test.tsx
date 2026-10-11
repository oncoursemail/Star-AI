// @vitest-environment jsdom
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {SiteShowcase} from './SiteShowcase'

let reduced=false
let listeners:Set<()=>void>
beforeEach(()=>{
 reduced=false;listeners=new Set()
 vi.stubGlobal('matchMedia',vi.fn((media:string)=>({media,get matches(){return reduced},
  addEventListener:(_event:string,listener:()=>void)=>listeners.add(listener),
  removeEventListener:(_event:string,listener:()=>void)=>listeners.delete(listener)})))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
const frame=()=>screen.getByTitle('Scripted STAR conversation sample. No model is running.')

describe('the website product tour',()=>{
 it('starts with a capture and plays a labelled sample only on request',()=>{
  render(<SiteShowcase latest={null}/>)
  expect(screen.queryByTitle(/Scripted STAR/)).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'Watch a sample run'}))
  expect(frame().getAttribute('src')).toBe('./?preview=1&fixture=streaming')
  expect(screen.getByText(/answer and timing are examples/)).toBeTruthy()
  const first=frame()
  fireEvent.click(screen.getByRole('button',{name:'Replay sample'}))
  expect(frame()).not.toBe(first)
  fireEvent.click(screen.getByRole('button',{name:'Back to capture'}))
  expect(screen.queryByTitle(/Scripted STAR/)).toBeNull()
 })
 it('uses a finished conversation for reduced motion, including a live preference change',()=>{
  render(<SiteShowcase latest={null}/>)
  fireEvent.click(screen.getByRole('button',{name:'Watch a sample run'}))
  act(()=>{reduced=true;listeners.forEach(listener=>listener())})
  expect(frame().getAttribute('src')).toBe('./?preview=1&fixture=chat')
 })
 it('supports roving tab focus and removes a chat sample when another area is selected',()=>{
  render(<SiteShowcase latest={null}/>)
  fireEvent.click(screen.getByRole('button',{name:'Watch a sample run'}))
  const chat=screen.getByRole('tab',{name:'Chat'})
  chat.focus()
  fireEvent.keyDown(chat,{key:'ArrowRight'})
  const brain=screen.getByRole('tab',{name:'Brain'})
  expect(document.activeElement).toBe(brain)
  expect(brain.getAttribute('aria-selected')).toBe('true')
  expect(screen.queryByTitle(/Scripted STAR/)).toBeNull()
  fireEvent.keyDown(brain,{key:'End'})
  expect(document.activeElement).toBe(screen.getByRole('tab',{name:'Analytics'}))
  fireEvent.keyDown(document.activeElement!,{key:'Home'})
  expect(document.activeElement).toBe(chat)
 })
})
