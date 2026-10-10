import {afterEach,describe,expect,it,vi} from 'vitest'
import {capabilities,filterCapabilities} from './starCatalog'
import {fetchPublicStatus,milestoneState} from './githubPublic'
import type {PublicStatus} from './githubPublic'

afterEach(()=>vi.unstubAllGlobals())

describe('public STAR capability catalog',()=>{
 it('tracks unique, typed capabilities rather than a fabricated intelligence score',()=>{
  expect(new Set(capabilities.map(item=>item.id)).size).toBe(capabilities.length)
  expect(capabilities.every(item=>['main','review','planned'].includes(item.stage))).toBe(true)
 })
 it('filters source status and accessible search text',()=>{
  expect(filterCapabilities('review','WEB')).toEqual(
   expect.arrayContaining([expect.objectContaining({id:'search'})])
  )
  expect(filterCapabilities('main','web')).toHaveLength(0)
  expect(filterCapabilities('all','nonexistent_unsupported_feature')).toHaveLength(0)
 })
})

describe('repository status logic',()=>{
 const snapshot:PublicStatus={
  fetchedAt:'2026-10-09T20:00:00Z',partial:false,
  stars:0,forks:0,openIssues:1,issuesCapped:false,
  openPRs:2,prsCapped:false,latestRelease:null,
  prs:[
   {number:27,title:'UI work',state:'open',mergedAt:null,url:'https://github.com/example/27'},
   {number:28,title:'Web work',state:'closed',mergedAt:'2026-10-09T22:00:00Z',url:'https://github.com/example/28'},
   {number:29,title:'Agent work',state:'closed',mergedAt:null,url:'https://github.com/example/29'}
  ],commits:[]
 }
 it('distinguishes open, merged and closed-unmerged PRs',()=>{
  expect(milestoneState(27,snapshot)).toBe('review')
  expect(milestoneState(28,snapshot)).toBe('merged')
  expect(milestoneState(29,snapshot)).toBe('closed')
  expect(milestoneState(99,snapshot)).toBe('unavailable')
  expect(milestoneState(27,null)).toBe('unavailable')
 })
 it('counts only GitHub issues, not PR objects',async()=>{
  const samples:Record<string,unknown>={
   '':{stargazers_count:0,forks_count:2},
   '/releases/latest':{tag_name:'v0.8.1',published_at:'2026-10-09T22:00:00Z',html_url:'https://example.invalid/release'},
   '/issues?state=open&per_page=100':[
    {number:15},{number:27,pull_request:{url:'https://example.invalid/pull'}}
   ],
   '/pulls?state=all&per_page=100':[
    {number:27,title:'UI',state:'open',merged_at:null,html_url:'https://example.invalid/27'},
    {number:28,title:'Web',state:'closed',merged_at:'2026-10-09T22:00:00Z',html_url:'https://example.invalid/28'}
   ],
   '/commits?per_page=5':[
    {sha:'abcdef0123456789',html_url:'https://example.invalid/commit',commit:{message:'Safe release\nDetailed change',committer:{date:'2026-10-09T21:00:00Z'}}}
   ]
  }
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>{
   const path=url.replace('https://api.github.com/repos/oncoursemail/Star-AI','')
   return new Response(JSON.stringify(samples[path]),{status:200})
  }))
  const result=await fetchPublicStatus()
  expect(result.openIssues).toBe(1)
  expect(result.openPRs).toBe(1)
  expect(result.latestRelease?.tag).toBe('v0.8.1')
  expect(result.commits[0].title).toBe('Safe release')
  expect(result.stars).toBe(0)
  expect(result.partial).toBe(false)
 })
 it('shows unavailable metrics rather than made-up values after partial API failure',async()=>{
  vi.stubGlobal('fetch',vi.fn(async (url:string)=>{
   if(url.endsWith('/releases/latest')){
    return new Response(JSON.stringify({tag_name:'v0.8.1',published_at:null,html_url:'https://example.invalid/release'}),{status:200})
   }
   throw new Error('Network unavailable')
  }))
  const result=await fetchPublicStatus()
  expect(result.stars).toBeNull()
  expect(result.openPRs).toBeNull()
  expect(result.openIssues).toBeNull()
  expect(result.partial).toBe(true)
 })
 it('does not claim successful status when all public requests fail',async()=>{
  vi.stubGlobal('fetch',vi.fn(async ()=>{throw new Error('Offline')}))
  await expect(fetchPublicStatus()).rejects.toThrow('temporarily unavailable')
 })
})
