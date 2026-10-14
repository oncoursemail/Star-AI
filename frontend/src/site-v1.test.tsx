// @vitest-environment jsdom
import {afterEach,describe,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {existsSync,readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {renderToString} from 'react-dom/server'
import {Landing} from './Landing'
import {SiteDownload} from './SiteDownload'
import {SiteFeatures} from './SiteFeatures'
import media from './siteMedia.json'
import {LINKS,evaluation,featureGroups,learnSteps,limits,releaseFiles} from './siteContent'
import type {ReleaseInfo} from './githubPublic'

afterEach(()=>cleanup())
const html=renderToString(<Landing/>)
const page=new DOMParser().parseFromString(html,'text/html')
const release=(tag:string):ReleaseInfo=>({tag,name:'STAR',publishedAt:'2026-10-13T00:00:00Z',url:LINKS.latest,prerelease:false,assets:[]})

describe('website v1.0 claims',()=>{
 it('reports the measured v0.9.0 and v1.0.0 results as they are, without a combined or best-of score',()=>{
  expect(evaluation.rows.map(row=>[row.suite,row.before,row.after])).toEqual([
   ['Roblox scripting, development set','13 / 34','16 / 34'],
   ['Creation tasks','11 / 23','10 / 23'],
   ['Blind holdout, never used for tuning','8 / 24','Re-running'],
  ])
  for(const text of ['13 / 34','16 / 34','11 / 23','10 / 23','8 / 24','About the same','inconclusive','not a game-quality score'])
   expect(page.body.textContent?.replace(/\s+/g,' '),text).toContain(text)
  expect(html).not.toMatch(/smarter than|best[- ]in[- ]class|state[- ]of[- ]the[- ]art|29 \/ 57/i)
 })
 it('labels every feature with one honest status, and never shows an open pull request as available',()=>{
  const features=featureGroups.flatMap(group=>group.features)
  expect(features.length).toBeGreaterThanOrEqual(15)
  const soon=features.filter(feature=>feature.status==='soon').map(feature=>feature.name)
  expect(soon).toEqual(['Studio Lab','Blender on a server','Voice'])
  for(const feature of features){
   expect(['available','opt-in','soon']).toContain(feature.status)
   // Anything in the source names the release it first shipped in; coming-soon items name none.
   expect(Boolean(feature.since),feature.name).toBe(feature.status!=='soon')
  }
  const prefix=LINKS.repo+'/blob/main/'
  for(const feature of features)if(feature.doc){
   expect(feature.doc.startsWith(prefix),feature.name).toBe(true)
   expect(existsSync(resolve(process.cwd(),'..',feature.doc.slice(prefix.length))),feature.doc).toBe(true)
  }
  expect(existsSync(resolve(process.cwd(),'..',LINKS.notes.slice(prefix.length)))).toBe(true)
 })
 it('says when a feature is newer than the latest published release',()=>{
  render(<SiteFeatures latest={release('v0.9.0')}/>)
  expect(screen.getAllByText(/In v1\.0\.0, not in a published release yet/).length).toBeGreaterThan(5)
  cleanup()
  render(<SiteFeatures latest={release('v1.0.0')}/>)
  expect(screen.queryByText(/not in a published release yet/)).toBeNull()
 })
 it('describes the learning loop the code implements, including what it has not done yet',()=>{
  expect(learnSteps.map(step=>step.title)).toEqual(['Practise','Check','Propose','Gate','You decide'])
  const text=page.body.textContent||''
  for(const fact of ['300 practice tasks','14-day trial','inconclusive means no','The lesson file bundled with 1.0 is empty','model itself never changes'])
   expect(text,fact).toContain(fact)
  expect(page.querySelectorAll('svg.sw-loop[role="img"] title')).toHaveLength(2)
 })
 it('keeps the known limits on the page',()=>{
  expect(limits.length).toBeGreaterThanOrEqual(5)
  const text=page.body.textContent||''
  for(const fact of ['not code-signed','installing over v0.9.0','not a frontier model','no licence file','Windows 10 is untested'])
   expect(text.toLowerCase(),fact).toContain(fact.toLowerCase())
 })
})

describe('site navigation, assets and accessibility',()=>{
 it('has one first-level heading and never skips a heading level',()=>{
  const headings=[...page.querySelectorAll('h1,h2,h3,h4,h5,h6')]
  expect(headings.length).toBeGreaterThan(10)
  const levels=headings.map(node=>Number(node.tagName.slice(1)))
  expect(levels[0]).toBe(1)
  expect(levels.filter(level=>level===1)).toHaveLength(1)
  for(let i=1;i<levels.length;i++)expect(levels[i],headings[i].textContent||'').toBeLessThanOrEqual(levels[i-1]+1)
 })
 it('resolves every internal link and keeps ids unique',()=>{
  const ids=[...page.querySelectorAll('[id]')].map(node=>node.id)
  expect(ids).toHaveLength(new Set(ids).size)
  for(const anchor of page.querySelectorAll('a[href^="#"]'))expect(ids,anchor.textContent||'internal link').toContain(anchor.getAttribute('href')?.slice(1))
  expect(page.querySelector('a.sw-skip')?.getAttribute('href')).toBe('#main')
  for(const anchor of page.querySelectorAll('a[target="_blank"]'))expect(anchor.getAttribute('rel')).toContain('noopener')
 })
 it('gives every image alt text and real dimensions, and ships every capture in the manifest',()=>{
  const images=[...page.querySelectorAll('img')]
  expect(images.length).toBeGreaterThanOrEqual(6)
  for(const image of images){
   expect(image.getAttribute('alt'),image.getAttribute('src')||'').toBeTruthy()
   expect(Number(image.getAttribute('width'))).toBeGreaterThan(0)
  }
  for(const files of Object.values(media.images))for(const asset of files)
   expect(existsSync(resolve(process.cwd(),'public','site',asset.file)),asset.file).toBe(true)
  expect(media.sourceVersion).toBe('1.0.0')
 })
 it('keeps visible focus, skip navigation and reduced-motion rules',()=>{
  const css=readFileSync(resolve(process.cwd(),'src','site.css'),'utf8')
  expect(css).toContain('.sw :focus-visible')
  expect(css).toContain('.sw-skip:focus')
  expect(css).toContain('@media (prefers-reduced-motion:reduce)')
  expect(html).toContain('aria-label="Main"')
 })
})

describe('download section',()=>{
 it('offers the official release page, not fabricated ZIP or checksum URLs, when release data is missing',()=>{
  render(<SiteDownload latest={null} files={releaseFiles(null)} releaseLive={false} snapshotAt={null}/>)
  expect(screen.getByRole('link',{name:/Open the latest release/i}).getAttribute('href')).toBe(LINKS.latest)
  expect(screen.getByRole('link',{name:/View release assets/i}).getAttribute('href')).toBe(LINKS.latest)
  expect(screen.getByRole('link',{name:/Checksums on GitHub Releases/i}).getAttribute('href')).toBe(LINKS.latest)
  expect(screen.getByText(/Live release details unavailable/)).toBeTruthy()
  expect(screen.getByText(/If a release provides SHA256SUMS.txt/)).toBeTruthy()
 })
 it('lists the requirements, including the optional server',()=>{
  render(<SiteDownload latest={null} files={releaseFiles(null)} releaseLive={false} snapshotAt={null}/>)
  expect(screen.getByText('Or STAR Server')).toBeTruthy()
  expect(screen.getByText(/No graphics card needed/)).toBeTruthy()
 })
})
