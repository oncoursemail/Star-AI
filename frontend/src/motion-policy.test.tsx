// @vitest-environment jsdom
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {useState} from 'react'
import {AnimatePresence} from 'motion/react'
import {MotionPolicy,useEffectiveReducedMotion,useMotionVariants,useStarReducedMotion} from './MotionPolicy'
import {MotionSurface} from './MotionSurface'
import {collapse,menuIn,pageFade} from './motion'

let deviceReduced=false
let listeners:Set<()=>void>
const changeDevice=(value:boolean)=>act(()=>{deviceReduced=value;listeners.forEach(listener=>listener())})
beforeEach(()=>{
 deviceReduced=false
 listeners=new Set()
 vi.stubGlobal('matchMedia',vi.fn((media:string)=>({media,get matches(){return deviceReduced},
  addEventListener:(_event:string,listener:()=>void)=>listeners.add(listener),
  removeEventListener:(_event:string,listener:()=>void)=>listeners.delete(listener)})))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals();document.documentElement.removeAttribute('data-star-reduced-motion')})

function Evidence(){
 const reduced=useStarReducedMotion()
 const variants=useMotionVariants({...pageFade,...collapse,menu:menuIn.shown})
 return <output data-testid="policy">{JSON.stringify({reduced,variants})}</output>
}
function Workspace({saved}:{saved:boolean}){
 const effective=useEffectiveReducedMotion(saved)
 return <MotionPolicy reduced={effective}><Evidence/></MotionPolicy>
}
const evidence=()=>JSON.parse(screen.getByTestId('policy').textContent||'{}')
function TransitionProbe(){
 const [page,setPage]=useState('First page')
 const reduced=useEffectiveReducedMotion(false)
 return <MotionPolicy reduced={reduced}>
  <button onClick={()=>setPage('Second page')}>Next page</button>
  <AnimatePresence mode="wait"><MotionSurface key={page} as="main" variants={pageFade}><h1>{page}</h1></MotionSurface></AnimatePresence>
 </MotionPolicy>
}

describe('STAR motion preference',()=>{
 it.each([[false,false,false],[true,false,true],[false,true,true],[true,true,true]])(
  'combines device=%s and saved=%s into reduced=%s',(device,saved,reduced)=>{
   deviceReduced=device
   render(<Workspace saved={saved}/>)
   expect(evidence().reduced).toBe(reduced)
   expect(document.documentElement.getAttribute('data-star-reduced-motion')).toBe(String(reduced))
   // Opacity and height need an explicit instant transition; MotionConfig alone preserves opacity.
   const transition=evidence().variants.shown.transition
   expect(transition.duration).toBe(reduced?0:.16)
   expect(evidence().variants.menu.transition.duration).toBe(reduced?0:.16)
  })
 it('responds to live device changes, and the app cannot turn them back on',()=>{
  const {rerender}=render(<Workspace saved={false}/>)
  expect(evidence().reduced).toBe(false)
  changeDevice(true)
  expect(evidence().reduced).toBe(true)
  rerender(<Workspace saved={true}/>)
  changeDevice(false)
  expect(evidence().reduced).toBe(true)
  rerender(<Workspace saved={false}/>)
  expect(evidence().reduced).toBe(false)
 })
 it('cleans up the device subscription and restores the document portal policy',()=>{
  document.documentElement.setAttribute('data-star-reduced-motion','previous')
  const {unmount}=render(<Workspace saved={true}/>)
  expect(listeners.size).toBeGreaterThan(0)
  unmount()
  expect(listeners.size).toBe(0)
  expect(document.documentElement.getAttribute('data-star-reduced-motion')).toBe('previous')
 })
 it('releases a pending route exit when the device requests reduced motion',async()=>{
  render(<TransitionProbe/>)
  fireEvent.click(screen.getByRole('button',{name:'Next page'}))
  changeDevice(true)
  const next=await screen.findByRole('heading',{name:'Second page'})
  expect(screen.queryByRole('heading',{name:'First page'})).toBeNull()
  await waitFor(()=>expect(next.parentElement?.style.opacity).toBe('1'))
 })
 it('settles an opening disclosure without replacing its content or losing focus',async()=>{
  const tree=(reduced:boolean)=><MotionPolicy reduced={reduced}><MotionSurface variants={collapse}><button>Read this step</button></MotionSurface></MotionPolicy>
  const {rerender}=render(tree(false))
  const control=screen.getByRole('button',{name:'Read this step'})
  control.focus()
  rerender(tree(true))
  expect(screen.getByRole('button',{name:'Read this step'})).toBe(control)
  expect(document.activeElement).toBe(control)
  await waitFor(()=>{
   expect(control.parentElement?.style.opacity).toBe('1')
   expect(control.parentElement?.style.height).toBe('auto')
  })
 })
})
