// @vitest-environment jsdom
/**
 * useProgress: when the website asks GitHub, what it shows meanwhile, and what it never does
 * (overwrite a complete board with a partial one, ignore a rate limit, poll in a hidden tab).
 * GitHub itself is replaced by a controllable fetchLiveProgress; timers are fake.
 */
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import type {LiveResult,ProgressSnapshot,RawProgress} from './githubPublic'

const live=vi.hoisted(()=>({fetch:vi.fn()}))
vi.mock('./githubPublic',async importOriginal=>{
 const actual=await importOriginal<typeof import('./githubPublic')>()
 return {...actual,fetchLiveProgress:live.fetch}
})

import {CACHE_KEY,FRESH_MS,RETRY_KEY,RateLimitError,normalizeProgress,writeCachedProgress} from './githubPublic'
import {RECHECK_MS,builtSnapshot,useProgress} from './siteHooks'

const NOW=Date.parse('2026-10-13T12:00:00Z')
const raw=(title:string):Partial<RawProgress>=>({
 releases:[],issues:[],commits:[],milestones:[],
 pulls:[{number:7,title,html_url:'https://github.com/oncoursemail/Star-AI/pull/7',state:'open',draft:false,
  merged_at:null,created_at:'2026-10-12T10:00:00Z',updated_at:'2026-10-12T11:00:00Z',user:{login:'a',type:'User'},labels:[]}]
})
const result=(title:string,at:number,partial=false):LiveResult=>{
 const body=raw(title)
 return {raw:body,partial,snapshot:normalizeProgress(body,new Date(at).toISOString(),'live')}
}
let resolveFetch:((value:LiveResult)=>void)|null=null
let rejectFetch:((reason:unknown)=>void)|null=null
const pendingFetch=()=>live.fetch.mockImplementation(()=>new Promise<LiveResult>((resolve,reject)=>{resolveFetch=resolve;rejectFetch=reject}))

type Shown={status:{kind:string;partial?:boolean;retryAt?:number};origin:string|null;at:string|null;first:string|null}
function Probe(){
 const {snapshot,status,refresh}=useProgress()
 const shown:Shown={status,origin:snapshot?.origin??null,at:snapshot?.generatedAt??null,first:snapshot?.pulls?.[0]?.title??null}
 return <><output data-testid="progress">{JSON.stringify(shown)}</output><button onClick={refresh}>refresh</button></>
}
const shown=()=>JSON.parse(screen.getByTestId('progress').textContent||'{}') as Shown
const advance=async(ms:number)=>{await act(async()=>{await vi.advanceTimersByTimeAsync(ms)})}
const settle=async()=>{await act(async()=>{await Promise.resolve()})}
const setVisibility=(state:'visible'|'hidden')=>Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>state})

beforeEach(()=>{
 vi.useFakeTimers({toFake:['setTimeout','clearTimeout','setInterval','clearInterval','Date']})
 vi.setSystemTime(NOW)
 window.localStorage.clear()
 window.history.replaceState({},'','/')
 setVisibility('visible')
 live.fetch.mockReset()
 resolveFetch=rejectFetch=null
})
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals()})

describe('the website progress board',()=>{
 it('shows the build-time snapshot first, then asks GitHub once after the first paint',async()=>{
  pendingFetch()
  render(<Probe/>)
  expect(shown().status.kind).toBe('snapshot')
  expect(shown().at).toBe(builtSnapshot?.generatedAt)
  expect(live.fetch).not.toHaveBeenCalled()                 // nothing before the page has painted
  await advance(1200)
  expect(live.fetch).toHaveBeenCalledOnce()
  expect(shown().status.kind).toBe('loading')
  expect(shown().origin).toBe('build')                      // the last known data stays on screen
  await act(async()=>{resolveFetch?.(result('Live board',NOW))})
  expect(shown()).toMatchObject({status:{kind:'live',partial:false},origin:'live',first:'Live board'})
  expect(JSON.parse(window.localStorage.getItem(CACHE_KEY)||'{}').generatedAt).toBe(new Date(NOW).toISOString())
 })

 it('waits for an idle moment when the browser offers one',async()=>{
  let idle:(()=>void)|null=null
  vi.stubGlobal('requestIdleCallback',vi.fn((callback:()=>void)=>{idle=callback;return 5}))
  vi.stubGlobal('cancelIdleCallback',vi.fn())
  pendingFetch()
  const {unmount}=render(<Probe/>)
  await advance(5000)
  expect(live.fetch).not.toHaveBeenCalled()
  await act(async()=>{idle?.()})
  expect(live.fetch).toHaveBeenCalledOnce()
  unmount()
  expect(window.cancelIdleCallback).toHaveBeenCalledWith(5)
 })

 it('never lets a partial answer replace the complete board on screen',async()=>{
  live.fetch.mockResolvedValue(result('Half a board',NOW,true))
  render(<Probe/>)
  await advance(1200)
  expect(shown().status.kind).toBe('failed')
  expect(shown().origin).toBe('build')
  expect(window.localStorage.getItem(CACHE_KEY)).toBeNull()
 })

 it('respects the rate limit: says when to come back and does not ask again before then',async()=>{
  const retryAt=NOW+30*60_000
  live.fetch.mockRejectedValue(new RateLimitError(retryAt))
  render(<Probe/>)
  await advance(1200)
  expect(shown().status).toEqual({kind:'limited',retryAt})
  expect(Number(window.localStorage.getItem(RETRY_KEY))).toBe(retryAt)
  live.fetch.mockClear()
  await act(async()=>{document.dispatchEvent(new Event('visibilitychange'))})
  fireEvent.click(screen.getByText('refresh'))
  await settle()
  expect(live.fetch).not.toHaveBeenCalled()
  expect(shown().status.kind).toBe('limited')
 })

 it('shows a failure without dropping the last known data',async()=>{
  live.fetch.mockRejectedValue(new Error('offline'))
  render(<Probe/>)
  await advance(1200)
  expect(shown().status.kind).toBe('failed')
  expect(shown().at).toBe(builtSnapshot?.generatedAt)
 })

 it('reuses a fresh copy from this browser instead of asking GitHub again',async()=>{
  writeCachedProgress(result('Cached board',NOW-60_000))
  render(<Probe/>)
  await advance(1200)
  expect(live.fetch).not.toHaveBeenCalled()
  expect(shown()).toMatchObject({status:{kind:'live',partial:false},first:'Cached board'})
 })

 it('shows an older cached copy at once and then refreshes it',async()=>{
  writeCachedProgress(result('Yesterday',NOW-FRESH_MS-1))
  pendingFetch()
  render(<Probe/>)
  await advance(1200)
  expect(shown()).toMatchObject({status:{kind:'loading'},first:'Yesterday'})
  await act(async()=>{resolveFetch?.(result('Today',NOW+1200))})
  expect(shown().first).toBe('Today')
 })

 it('sends one request at a time, however often the tab becomes visible',async()=>{
  writeCachedProgress(result('Old',NOW-FRESH_MS-1))
  pendingFetch()
  render(<Probe/>)
  await advance(1200)
  for(let i=0;i<3;i+=1)await act(async()=>{document.dispatchEvent(new Event('visibilitychange'))})
  expect(live.fetch).toHaveBeenCalledOnce()
  await act(async()=>{rejectFetch?.(new Error('offline'))})
  await act(async()=>{document.dispatchEvent(new Event('visibilitychange'))})
  expect(live.fetch).toHaveBeenCalledTimes(2)              // free again once the first one ended
 })

 it('limits manual refreshes to one every 15 seconds',async()=>{
  live.fetch.mockResolvedValue(result('Board',NOW))
  render(<Probe/>)
  await advance(1200)
  expect(live.fetch).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByText('refresh'))
  await settle()
  expect(live.fetch).toHaveBeenCalledTimes(1)              // 1.2 s after the automatic check
  await advance(15_000)
  fireEvent.click(screen.getByText('refresh'))
  await settle()
  expect(live.fetch).toHaveBeenCalledTimes(2)
 })

 it('refreshes an open, visible tab soon after its answer goes stale, but not a hidden one',async()=>{
  live.fetch.mockImplementation(async()=>result('Board',Date.now()))
  render(<Probe/>)
  await advance(1200)
  expect(live.fetch).toHaveBeenCalledTimes(1)
  await advance(FRESH_MS-RECHECK_MS)
  expect(live.fetch).toHaveBeenCalledTimes(1)              // still fresh: no request
  await advance(2*RECHECK_MS)
  // Regression: checking only every FRESH_MS found the answer just short of stale, so this took 20 minutes.
  expect(live.fetch).toHaveBeenCalledTimes(2)
  setVisibility('hidden')
  await advance(FRESH_MS*3)
  await act(async()=>{document.dispatchEvent(new Event('visibilitychange'))})
  expect(live.fetch).toHaveBeenCalledTimes(2)
 })

 it('retries a failing network at most once per freshness window',async()=>{
  live.fetch.mockRejectedValue(new Error('offline'))
  render(<Probe/>)
  await advance(1200)
  await advance(FRESH_MS*3)
  expect(live.fetch).toHaveBeenCalledTimes(3)              // 0:01, 11:00 and 21:00; never every minute
  expect(shown().status.kind).toBe('failed')
 })

 it('stops every timer and listener when the page goes away',async()=>{
  live.fetch.mockResolvedValue(result('Board',NOW))
  const {unmount}=render(<Probe/>)
  unmount()
  await advance(FRESH_MS*2)
  document.dispatchEvent(new Event('visibilitychange'))
  expect(live.fetch).not.toHaveBeenCalled()
 })

 it('never contacts GitHub in visual QA mode',async()=>{
  window.history.replaceState({},'','/?visualqa=1')
  live.fetch.mockResolvedValue(result('Board',NOW))
  render(<Probe/>)
  await advance(FRESH_MS*2)
  expect(live.fetch).not.toHaveBeenCalled()
  expect(shown().status.kind).toBe('snapshot')
 })
})

describe('the build-time snapshot the page starts from',()=>{
 it('is present, dated and from the build',()=>{
  const snapshot=builtSnapshot as ProgressSnapshot
  expect(snapshot.origin).toBe('build')
  expect(Number.isNaN(Date.parse(snapshot.generatedAt))).toBe(false)
 })
})
