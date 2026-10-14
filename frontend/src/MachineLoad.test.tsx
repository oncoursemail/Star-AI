// @vitest-environment jsdom
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeAll,describe,expect,it} from 'vitest'
import {initializeBridge} from './bridge'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'
import {MachineLoad,type PlannerSnapshot} from './MachineLoad'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await initializeBridge()})
afterEach(()=>{cleanup();desktop.reset()})

const live:PlannerSnapshot={available:true,
 machines:[
  {name:'brain1',cpu:0.52,memFreeGiB:71.6,memTotalGiB:125.6,ageSeconds:1,chatActive:true,ownerBusy:'',quietLock:'',gpu:null,studios:0,slots:{'star-fast':{busy:1,total:2}}},
  {name:'pc',cpu:0.1,memFreeGiB:13.3,memTotalGiB:31.9,ageSeconds:5,chatActive:false,ownerBusy:'game running: cs2.exe',quietLock:'',gpu:0.9,studios:0,slots:{}}],
 jobs:[{jobClass:'nightschool',holder:'nightschool',machine:'brain1',seconds:40}],
 queue:[{jobClass:'gpu-train',holder:'pc-training',machine:'pc'}]}

describe('Machines and jobs panel',()=>{
 it('shows per-machine load, chat and the queue',()=>{
  render(<MachineLoad load={false} snapshot={live}/>)
  expect(screen.getByText('Brain 1 (main models)')).toBeTruthy()
  expect(screen.getByText('CPU 52% · RAM free 71.6/125.6 GiB')).toBeTruthy()
  expect(screen.getByText('Slots busy: star-fast 1/2')).toBeTruthy()
  expect(screen.getByText(/chat active/)).toBeTruthy()
  expect(screen.getByText(/owner busy: game running: cs2.exe/)).toBeTruthy()
  expect(screen.getByText('Running: nightschool on brain1')).toBeTruthy()
  expect(screen.getByText('Waiting: gpu-train for pc')).toBeTruthy()
  expect(screen.getByRole('meter',{name:'CPU brain1'}).getAttribute('aria-valuenow')).toBe('52')
 })
 it('says plainly when the planner is not reachable',async()=>{
  desktop.onAction('plannerStatus',()=>({ok:true,data:{available:false,reason:'the resource planner did not answer'}}))
  render(<MachineLoad/>)
  expect(await screen.findByText('Resource planner not reachable (the resource planner did not answer).')).toBeTruthy()
  await waitFor(()=>expect(desktop.sent('plannerStatus').length).toBeGreaterThanOrEqual(1))
  expect(desktop.sent('plannerStatus')[0].payload).toEqual({})
 })
 it('treats a refused request as not reachable, never as idle machines',async()=>{
  desktop.onAction('plannerStatus',()=>({ok:false,error:'nope'}))
  render(<MachineLoad/>)
  expect(await screen.findByText('Resource planner not reachable.')).toBeTruthy()
  expect(screen.queryByText(/CPU/)).toBeNull()
 })
})
