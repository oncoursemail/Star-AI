/**
 * Edge cases of the public GitHub reader (githubPublic.ts) that site-progress.test.ts does not reach:
 * resolved links, the other rate-limit signals, malformed records and storage that throws.
 */
import {afterEach,describe,expect,it,vi} from 'vitest'
import {
 CACHE_KEY,RateLimitError,REPO_SLUG,REPO_URL,buildBoard,fetchLatestStableRelease,fetchLiveProgress,normalizeProgress,
 parseStoredProgress,readCachedProgress,readRetryAt,repoUrl,writeCachedProgress,writeRetryAt
} from './githubPublic'
import type {LiveResult} from './githubPublic'

afterEach(()=>vi.unstubAllGlobals())
const NOW=Date.parse('2026-10-13T12:00:00Z')
const reply=(status:number,headers:Record<string,string>={})=>vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}',{status,headers})))

describe('links stay inside this repository',()=>{
 it('judges the address the browser will actually open, not just its first characters',()=>{
  // Regression: these passed the prefix test but open github.com/evil/repo once dot segments resolve.
  expect(repoUrl(REPO_URL+'/../../evil/repo')).toBe(REPO_URL)
  expect(repoUrl(REPO_URL+'/%2e%2e/%2E%2E/evil/repo')).toBe(REPO_URL)
  expect(repoUrl(REPO_URL+'/./../Star-AI-fork/pulls','fallback')).toBe('fallback')
  // Dot segments that stay inside the repository, and ordinary links, are kept as they are.
  expect(repoUrl(REPO_URL+'/pull/1/../2')).toBe(REPO_URL+'/pull/1/../2')
  expect(repoUrl(REPO_URL+'/releases/tag/v1.0.0')).toBe(REPO_URL+'/releases/tag/v1.0.0')
 })
 it('refuses non-strings, other hosts and look-alike repository names',()=>{
  for(const value of [null,42,{href:REPO_URL+'/x'},REPO_URL,REPO_URL+'-fork/pull/1','http://github.com/'+REPO_SLUG+'/x'])
   expect(repoUrl(value)).toBe(REPO_URL)
 })
})

describe('the other ways GitHub says "slow down"',()=>{
 it('uses Retry-After when GitHub sends it',async()=>{
  reply(403,{'retry-after':'120'})
  const error=await fetchLatestStableRelease(undefined,NOW).catch((reason:unknown)=>reason)
  expect(error).toBeInstanceOf(RateLimitError)
  expect((error as RateLimitError).retryAt).toBe(NOW+120_000)
 })
 it('backs off five minutes on a bare 429',async()=>{
  reply(429)
  const error=await fetchLatestStableRelease(undefined,NOW).catch((reason:unknown)=>reason)
  expect((error as RateLimitError).retryAt).toBe(NOW+5*60_000)
 })
 it('waits at least a minute even when the reset time has already passed',async()=>{
  reply(403,{'x-ratelimit-remaining':'0','x-ratelimit-reset':String(Math.round(NOW/1000)-30)})
  const error=await fetchLatestStableRelease(undefined,NOW).catch((reason:unknown)=>reason)
  expect((error as RateLimitError).retryAt).toBe(NOW+60_000)
 })
 it('treats a 403 without rate-limit headers as a plain failure, not a reason to wait',async()=>{
  reply(403,{'x-ratelimit-remaining':'12'})
  const error=await fetchLatestStableRelease(undefined,NOW).catch((reason:unknown)=>reason)
  expect(error).not.toBeInstanceOf(RateLimitError)
  expect((error as Error).message).toMatch('unavailable')
 })
 it('lets one throttled endpoint stop the whole live read',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string)=>url.includes('/issues')
   ?new Response('{}',{status:429})
   :new Response('[]',{status:200})))
  await expect(fetchLiveProgress(undefined,NOW)).rejects.toBeInstanceOf(RateLimitError)
 })
})

describe('malformed records are dropped or bounded, never trusted',()=>{
 it('keeps only published semantic-version releases, newest first, with clean checksums',()=>{
  const snapshot=normalizeProgress({releases:[
   {tag_name:'v1.0.0',published_at:'2026-10-01T00:00:00Z',html_url:REPO_URL+'/releases/tag/v1.0.0',assets:[
    {name:'STAR-Setup.exe',size:-5,digest:'sha256:'+'AB'.repeat(32),browser_download_url:REPO_URL+'/releases/download/v1.0.0/STAR-Setup.exe'},
    {name:'',size:1,browser_download_url:REPO_URL+'/releases/download/v1.0.0/unnamed'},
    {name:'elsewhere.exe',size:1,browser_download_url:REPO_URL+'/archive/elsewhere.exe'}
   ]},
   {tag_name:'v1.1.0',published_at:'2026-10-05T00:00:00Z',draft:true},
   {tag_name:'nightly',published_at:'2026-10-06T00:00:00Z'},
   {tag_name:'v1.0.1',published_at:'not a date',html_url:'https://evil.example/'},
   'not a record'
  ]},new Date(NOW).toISOString(),'live')
  expect(snapshot.releases?.map(release=>release.tag)).toEqual(['v1.0.0','v1.0.1'])
  const [first,second]=snapshot.releases!
  expect(first.name).toBe('v1.0.0')                                  // no name: the tag stands in
  expect(first.assets).toEqual([{name:'STAR-Setup.exe',size:0,url:REPO_URL+'/releases/download/v1.0.0/STAR-Setup.exe',sha256:'ab'.repeat(32)}])
  expect(second.publishedAt).toBeNull()
  expect(second.url).toBe(REPO_URL+'/releases')
 })
 it('bounds titles and labels and drops commits without a real hash',()=>{
  const snapshot=normalizeProgress({
   pulls:[{number:3,title:'x'.repeat(500),labels:Array.from({length:20},(_,i)=>({name:'label-'+i+'-'+'y'.repeat(80)}))},{number:0,title:'no number'}],
   commits:[{sha:'not-a-sha',commit:{message:'bad'}},{sha:'ABCDEF1234567',commit:{message:'First line\nSecond line',committer:{date:'2026-10-12T00:00:00Z'}}}],
   issues:'not a list'
  },new Date(NOW).toISOString(),'live')
  const [pull]=snapshot.pulls!
  expect(snapshot.pulls).toHaveLength(1)
  expect(pull.title).toHaveLength(300)
  expect(pull.labels).toHaveLength(12)
  expect(pull.labels.every(label=>label.length===60)).toBe(true)
  expect(snapshot.commits).toEqual([{sha:'ABCDEF1',title:'First line',date:'2026-10-12T00:00:00.000Z',url:REPO_URL+'/commits'}])
  expect(snapshot.issues).toBeNull()
 })
 it('rejects stored snapshots that are undated, foreign, of another schema or empty',()=>{
  const base={schema:1,repo:REPO_SLUG,generatedAt:'2026-10-13T10:00:00Z',raw:{pulls:[]}}
  expect(parseStoredProgress(base,'build')?.origin).toBe('build')
  expect(parseStoredProgress({...base,generatedAt:'yesterday'},'build')).toBeNull()
  expect(parseStoredProgress({...base,schema:2},'build')).toBeNull()
  expect(parseStoredProgress({...base,raw:[]},'build')).toBeNull()
  expect(parseStoredProgress({...base,raw:{commits:[]}},'build')).toBeNull()  // nothing a board can show
  expect(parseStoredProgress('{"schema":1}','build')).toBeNull()
 })
 it('builds an empty board, not an error, when nothing is known',()=>{
  const board=buildBoard(null)
  expect(board).toMatchObject({latest:null,releases:[],active:[],unreleased:[],tasks:[],ideas:[],draftCount:0})
 })
})

describe('browser storage that refuses to cooperate',()=>{
 const throwing={getItem:()=>{throw new Error('denied')},setItem:()=>{throw new Error('quota')},removeItem:()=>{throw new Error('denied')}}
 const complete:LiveResult={partial:false,raw:{pulls:[]},snapshot:normalizeProgress({pulls:[]},new Date(NOW).toISOString(),'live')}
 it('costs only the cache: reads give nothing and writes are dropped silently',()=>{
  expect(readCachedProgress(throwing)).toBeNull()
  expect(readRetryAt(NOW,throwing)).toBeNull()
  expect(()=>writeCachedProgress(complete,throwing)).not.toThrow()
  expect(()=>writeRetryAt(NOW+1000,throwing)).not.toThrow()
 })
 it('forgets a retry time once it has passed, and ignores junk',()=>{
  const data=new Map<string,string>()
  const store={getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>{data.set(key,value)},removeItem:(key:string)=>{data.delete(key)}}
  writeRetryAt(NOW+1000.6,store)
  expect(readRetryAt(NOW,store)).toBe(NOW+1001)
  expect(readRetryAt(NOW+2000,store)).toBeNull()
  expect(data.size).toBe(0)
  store.setItem('star.site.progress.retryAt','soon')
  expect(readRetryAt(NOW,store)).toBeNull()
  writeCachedProgress(complete,store)
  expect(JSON.parse(data.get(CACHE_KEY)||'{}')).toMatchObject({schema:1,repo:REPO_SLUG})
 })
})
