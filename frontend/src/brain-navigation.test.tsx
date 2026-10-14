// @vitest-environment jsdom
import {afterEach,beforeAll,beforeEach,describe,expect,it} from 'vitest'
import {cleanup,render,screen,waitFor,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {initializeBridge,request} from './bridge'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'
import {Desktop} from './Desktop'
import type {BootData} from './types'
import type {BrainSnapshot} from './BrainOverview'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await initializeBridge()})
beforeEach(()=>{desktop.reset();window.localStorage.clear()})
afterEach(cleanup)

const snapshot:BrainSnapshot={provider:'local',models:['model-one'],roles:[],knowledge:[],skills:{enabled:false,count:0,names:[]},lessons:{candidate:0,accepted:0,retired:0},tools:[],evaluation:null}

describe('Brain sidebar navigation',()=>{
 it('adds Brain after Analytics without replacing the Model connection page',async()=>{
  desktop.onAction('brainSnapshot',()=>({ok:true,data:snapshot}))
  const boot=await request<BootData>('bootstrap')
  expect(boot.ok).toBe(true)
  expect(boot.data).toBeTruthy()
  render(<Desktop initial={boot.data!}/>)
  const nav=within(screen.getByRole('navigation',{name:'Workspace'}))
  // Brain, Model, Analytics and Library are folded under "More" so the sidebar stays about chats.
  expect(nav.queryByRole('button',{name:'Brain'})).toBeNull()
  await userEvent.click(nav.getByRole('button',{name:'More'}))
  const brain=nav.getByRole('button',{name:'Brain'})
  const model=nav.getByRole('button',{name:'Model'})
  expect(nav.getByRole('button',{name:'Analytics'}).nextElementSibling).toBe(brain)
  expect(desktop.sent('brainSnapshot')).toHaveLength(0)

  await userEvent.click(brain)
  expect(await screen.findByText('Provider: local')).toBeTruthy()
  expect(brain.getAttribute('aria-current')).toBe('page')
  expect(model.getAttribute('aria-current')).toBeNull()
  expect(desktop.sent('brainSnapshot')).toHaveLength(1)
  expect(screen.queryByText('Which model STAR talks to, and whether it is answering.')).toBeNull()

  await userEvent.click(model)
  expect(await screen.findByText('Which model STAR talks to, and whether it is answering.')).toBeTruthy()
  await waitFor(()=>expect(screen.queryByRole('region',{name:'STAR Brain overview'})).toBeNull())
  expect(model.getAttribute('aria-current')).toBe('page')
  expect(brain.getAttribute('aria-current')).toBeNull()
  expect(desktop.sent('brainSnapshot')).toHaveLength(1)
  expect(desktop.sent('saveSettings')).toHaveLength(0)
 })
 it('keeps preview navigation offline instead of requesting a real snapshot',async()=>{
  render(<Desktop preview/>)
  await userEvent.click(screen.getByRole('button',{name:'More'}))
  await userEvent.click(screen.getByRole('button',{name:'Brain'}))
  expect(await screen.findByRole('region',{name:'STAR Brain overview'})).toBeTruthy()
  expect(screen.getAllByText('not set up').length).toBeGreaterThanOrEqual(6)
  expect(desktop.sent('brainSnapshot')).toHaveLength(0)
  await userEvent.click(screen.getByRole('button',{name:'Model'}))
  expect(await screen.findByText('Which model STAR talks to, and whether it is answering.')).toBeTruthy()
 })
})
