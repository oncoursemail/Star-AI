// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {ActivityTimeline,RunStatus} from './ActivityTimeline'
import type {ActivityRun} from './activity'
import {MotionPolicy} from './MotionPolicy'

afterEach(cleanup)
const run=(outcome:ActivityRun['outcome'],steps:ActivityRun['steps']=[]):ActivityRun=>({
 id:'run-1',mode:'chat',label:'Agent workflow',outcome,startedAt:Date.now()-1000,
 phase:'Checking code',streaming:false,model:'test-model',steps
})
const step:ActivityRun['steps'][number]={
 id:'tool-1',kind:'tool',state:'done',title:'Searching workspace',
 detail:'workspace_search',startedAt:100,endedAt:400
}
function show(activity:ActivityRun,onStop?:()=>void,stopping=false){
 return render(<MotionPolicy reduced><ActivityTimeline run={activity} onStop={onStop} stopping={stopping}/></MotionPolicy>)
}

describe('real activity timeline rendering',()=>{
 it('starts completed runs folded, and reveals a completed tool detail only on request',async()=>{
  const user=userEvent.setup()
  show(run('done',[step]))
  const region=screen.getByRole('region',{name:'What STAR did'})
  const toggle=within(region).getByRole('button',{expanded:false})
  expect(within(region).queryByText('Searching workspace')).toBeNull()
  await user.click(toggle)
  const tool=within(region).getByRole('button',{name:'Searching workspace'})
  expect(tool.getAttribute('aria-expanded')).toBe('false')
  expect(within(region).queryByText('workspace_search')).toBeNull()
  await user.click(tool)
  expect(within(region).getByText('workspace_search')).toBeTruthy()
  await user.click(tool)
  expect(within(region).queryByText('workspace_search')).toBeNull()
 })
 it('shows failure details without treating a failed tool as done',()=>{
  show(run('failed',[{...step,state:'failed',detail:'The source could not be read.'}]))
  const region=screen.getByRole('region',{name:'What STAR did'})
  expect(within(region).getByRole('button',{name:'Searching workspace'}).getAttribute('aria-expanded')).toBe('true')
  expect(within(region).getByText('The source could not be read.')).toBeTruthy()
  expect(within(region).queryByRole('button',{name:'Stop'})).toBeNull()
 })
 it('ignores the second click on a running Stop button and disables it while stopping',()=>{
  const stop=vi.fn()
  const current=run('running',[{...step,state:'running'}])
  const {rerender}=show(current,stop)
  const button=screen.getByRole('button',{name:'Stop'})
  fireEvent.click(button,{detail:2})
  expect(stop).not.toHaveBeenCalled()
  fireEvent.click(button,{detail:1})
  expect(stop).toHaveBeenCalledOnce()
  rerender(<MotionPolicy reduced><ActivityTimeline run={current} onStop={stop} stopping/></MotionPolicy>)
  expect(screen.getByRole('button',{name:'Stopping'})).toHaveProperty('disabled',true)
 })
 it('does not expand empty runs and keeps their phase readable as a status',()=>{
  show(run('done'))
  expect(screen.getByRole('region',{name:'What STAR did'}).querySelector('ol')).toBeNull()
  expect(screen.getByRole('button',{expanded:false})).toHaveProperty('disabled',true)
  cleanup()
  render(<MotionPolicy reduced><RunStatus run={run('running')} label="Writing the answer"/></MotionPolicy>)
  expect(screen.getByRole('status').textContent).toBe('Writing the answer')
 })
})
