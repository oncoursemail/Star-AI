// @vitest-environment jsdom
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeAll,describe,expect,it} from 'vitest'
import {initializeBridge} from './bridge'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'
import {BrainOverview,type BrainSnapshot} from './BrainOverview'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await initializeBridge()})
afterEach(()=>{cleanup();desktop.reset()})

const empty:BrainSnapshot={provider:'',models:[],roles:[],knowledge:[],skills:{enabled:false,count:0,names:[]},lessons:{candidate:0,accepted:0,retired:0},tools:[],evaluation:null}
const full:BrainSnapshot={...empty,provider:'local',models:['model-one'],roles:[{role:'quick',label:'Fast',model:'model-one',source:'manual'}],knowledge:[{name:'Obsidian',connected:true}],skills:{enabled:true,count:2,names:['Luau','UI']},lessons:{candidate:1,accepted:2,retired:3},tools:['search','read'],evaluation:{passed:4,total:5}}

describe('Brain overview',()=>{
 it('shows real groups with full data',()=>{
  render(<BrainOverview load={false} snapshot={full}/>)
  expect(screen.getByText('Provider: local')).toBeTruthy()
  expect(screen.getByText('Fast: model-one')).toBeTruthy()
  expect(screen.getByText('Obsidian')).toBeTruthy()
  expect(screen.getByText('3 retired')).toBeTruthy()
  expect(screen.getByText('passed: 4')).toBeTruthy()
 })
 it('shows partial connections only',()=>{
  render(<BrainOverview load={false} snapshot={{...empty,knowledge:[{name:'Obsidian',connected:false},{name:'Graphify',connected:true}]}}/>)
  expect(screen.getByText('Graphify')).toBeTruthy()
  expect(screen.queryByText('Obsidian')).toBeNull()
 })
 it('uses not set up for empty groups',()=>{
  render(<BrainOverview load={false} snapshot={empty}/>)
  expect(screen.getAllByText('not set up').length).toBeGreaterThanOrEqual(6)
 })
 it.each([
  ['full',full],
  ['partial',{...empty,knowledge:[{name:'Graphify',connected:true}]}],
  ['empty',empty],
 ] as const)('loads %s data through the desktop bridge',async(_name,snapshot)=>{
  desktop.onAction('brainSnapshot',()=>({ok:true,data:snapshot}))
  render(<BrainOverview/>)
  await waitFor(()=>expect(desktop.sent('brainSnapshot')).toHaveLength(1))
  await waitFor(()=>expect(screen.queryByRole('alert')).toBeNull())
  if(snapshot.provider)expect(await screen.findByText('Provider: local')).toBeTruthy()
  if(snapshot.knowledge.length)expect(await screen.findByText(snapshot.knowledge[0].name)).toBeTruthy()
  if(snapshot===empty)expect(screen.getAllByText('not set up').length).toBeGreaterThanOrEqual(6)
  expect(desktop.sent('brainSnapshot')[0].payload).toEqual({})
  expect(desktop.sent('saveSettings')).toHaveLength(0)
 })
 it('reports a refused snapshot without inventing data',async()=>{
  desktop.onAction('brainSnapshot',()=>({ok:false,error:'Snapshot unavailable'}))
  render(<BrainOverview/>)
  expect((await screen.findByRole('alert')).textContent).toBe('Brain information could not be loaded.')
  expect(screen.queryByText('Provider: local')).toBeNull()
  expect(screen.getAllByText('not set up').length).toBeGreaterThanOrEqual(6)
 })
})
