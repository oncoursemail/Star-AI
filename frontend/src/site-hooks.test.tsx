// @vitest-environment jsdom
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,render,screen} from '@testing-library/react'
import {useActiveSection,useHeaderState} from './siteHooks'

const sections=['intro','studio'] as const
let frame:FrameRequestCallback|null=null

function HeaderProbe({locked=false}:{locked?:boolean}){
 const state=useHeaderState(locked)
 return <output data-testid="header">{JSON.stringify(state)}</output>
}
function SectionProbe(){
 const active=useActiveSection(sections)
 return <output data-testid="section">{active??'none'}</output>
}
const header=()=>JSON.parse(screen.getByTestId('header').textContent||'{}') as {solid:boolean;hidden:boolean;past:boolean}
const scroll=(to:number)=>{
 vi.stubGlobal('scrollY',to)
 act(()=>{
  window.dispatchEvent(new Event('scroll'))
  const callback=frame
  frame=null
  callback?.(0)
 })
}

beforeEach(()=>{
 frame=null
 vi.stubGlobal('scrollY',0)
 vi.stubGlobal('innerHeight',800)
 vi.stubGlobal('requestAnimationFrame',vi.fn((callback:FrameRequestCallback)=>{frame=callback;return 1}))
 vi.stubGlobal('cancelAnimationFrame',vi.fn())
})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

describe('website hooks used by the landing page and its sections',()=>{
 it('shows a solid, hidden header on a downward scroll, then restores it when scrolling up',()=>{
  render(<HeaderProbe/>)
  expect(header()).toEqual({solid:false,hidden:false,past:false})
  scroll(320)
  expect(header()).toEqual({solid:true,hidden:true,past:false})
  scroll(600)
  expect(header()).toEqual({solid:true,hidden:true,past:true})
  scroll(120)
  expect(header()).toEqual({solid:true,hidden:false,past:false})
  scroll(0)
  expect(header()).toEqual({solid:false,hidden:false,past:false})
 })
 it('keeps a locked header visible even when the page scrolls down',()=>{
  const {rerender}=render(<HeaderProbe/>)
  scroll(400)
  expect(header().hidden).toBe(true)
  rerender(<HeaderProbe locked/>)
  expect(header().hidden).toBe(false)
  scroll(700)
  expect(header()).toEqual({solid:true,hidden:false,past:true})
 })
 it('tracks only intersecting, present sections and stops observing on unmount',()=>{
  const observed:string[]=[]
  const disconnect=vi.fn()
  let notify:IntersectionObserverCallback|undefined
  class Observer{
   constructor(callback:IntersectionObserverCallback){notify=callback}
   observe(element:Element){observed.push(element.id)}
   disconnect(){disconnect()}
  }
  vi.stubGlobal('IntersectionObserver',Observer)
  const {unmount}=render(<><div id="intro"/><div id="studio"/><SectionProbe/></>)
  expect(observed).toEqual(['intro','studio'])
  expect(screen.getByTestId('section').textContent).toBe('none')
  act(()=>notify?.([{target:document.getElementById('studio')!,isIntersecting:false} as IntersectionObserverEntry],{} as IntersectionObserver))
  expect(screen.getByTestId('section').textContent).toBe('none')
  act(()=>notify?.([{target:document.getElementById('studio')!,isIntersecting:true} as IntersectionObserverEntry],{} as IntersectionObserver))
  expect(screen.getByTestId('section').textContent).toBe('studio')
  unmount()
  expect(disconnect).toHaveBeenCalledOnce()
 })
})
