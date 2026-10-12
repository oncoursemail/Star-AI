// @vitest-environment jsdom
import {afterEach,describe,expect,it} from 'vitest'
import {cleanup,render,screen} from '@testing-library/react'
import {readFileSync,existsSync} from 'node:fs'
import {resolve} from 'node:path'
import {renderToString} from 'react-dom/server'
import {Landing} from './Landing'
import {SiteDownload} from './SiteDownload'
import media from './siteMedia.json'
import {LINKS,capabilities,evalResults,releaseFiles} from './siteContent'

afterEach(()=>cleanup())

describe('website v0.9.0 claims',()=>{
 it('keeps source-backed feature descriptions with dated and qualified evaluation results',()=>{
  expect(capabilities.map(item=>item.name)).toEqual([
   'STAR Server on your network','Roblox answers with sources','Studio and Open Cloud',
   'Skills and the evaluation gate','Project learning','Voice calls','Images and video','Documents and tables'
  ])
  expect(capabilities.every(item=>item.since==='0.9.0')).toBe(true)
  expect(evalResults).toEqual([
   {suite:'Roblox v2 scripting (October 12 and earlier runs)',passed:'13–18 / 34',rate:'varies by run'},
   {suite:'Creation v1 (earlier; not reproduced on v0.9.0)',passed:'11 / 23 (historical)',rate:'unverified on release'}
  ])
  const prefix=LINKS.repo+'/blob/main/'
  for(const feature of capabilities){
   expect(feature.doc.startsWith(prefix),feature.name).toBe(true)
   const source=feature.doc.slice(prefix.length)
   expect(existsSync(resolve(process.cwd(),'..',source)),source).toBe(true)
  }
 })
 it('renders variable evaluation results without claiming a single best combined score',()=>{
  const html=renderToString(<Landing/>)
  expect(html).toContain('13–18 / 34')
  expect(html).toContain('varies by run')
  expect(html).toContain('11 / 23 (historical)')
  expect(html).not.toContain('29 / 57')
  expect(html).toContain('Three of 18 unchanged')
  expect(html).toContain('not a combined production benchmark')
  expect(html).toContain('Not in a release yet')
 })
})

describe('site navigation, assets and accessibility',()=>{
 const html=renderToString(<Landing/>)
 const document=new DOMParser().parseFromString(html,'text/html')
 it('has one first-level heading and never skips a heading level',()=>{
  const headings=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')]
  expect(headings.length).toBeGreaterThan(10)
  const levels=headings.map(node=>Number(node.tagName.slice(1)))
  expect(levels[0]).toBe(1)
  expect(levels.filter(level=>level===1)).toHaveLength(1)
  for(let i=1;i<levels.length;i++)expect(levels[i],headings[i].textContent||'').toBeLessThanOrEqual(levels[i-1]+1)
 })
 it('resolves every internal section link and keeps ids unique',()=>{
  const ids=[...document.querySelectorAll('[id]')].map(node=>node.id)
  expect(ids).toHaveLength(new Set(ids).size)
  for(const anchor of document.querySelectorAll('a[href^="#"]')){
   const target=anchor.getAttribute('href')?.slice(1)
   expect(ids,anchor.textContent||'internal link').toContain(target)
  }
  expect(document.querySelector('a.sw-skip')?.getAttribute('href')).toBe('#main')
 })
 it('provides image alt text and ships every capture named in the media manifest',()=>{
  const pictures=[...document.querySelectorAll('img')]
  expect(pictures.length).toBeGreaterThan(0)
  for(const img of pictures)expect(img.getAttribute('alt')).toBeTruthy()
  for(const files of Object.values(media.images))for(const asset of files){
   expect(asset.width).toBeGreaterThan(0)
   expect(asset.height).toBeGreaterThan(0)
   const path=resolve(process.cwd(),'public','site',asset.file)
   expect(existsSync(path),asset.file).toBe(true)
  }
  expect(existsSync(resolve(process.cwd(),'public','star-mark.svg'))).toBe(true)
 })
 it('retains visible keyboard focus, skip navigation and reduced-motion rules',()=>{
  const css=readFileSync(resolve(process.cwd(),'src','site.css'),'utf8')
  expect(css).toContain('.sw :focus-visible')
  expect(css).toContain('.sw-skip:focus')
  expect(css).toContain('@media (prefers-reduced-motion:reduce)')
  expect(html).toContain('aria-label="Main"')
 })
})

describe('GitHub release fallback',()=>{
 it('offers the official release page, not fabricated ZIP or checksum URLs',()=>{
  render(<SiteDownload latest={null} files={releaseFiles(null)} releaseLive={false} snapshotAt={null}/>)
  expect(screen.getByRole('link',{name:/Open the latest release/i}).getAttribute('href')).toBe(LINKS.latest)
  expect(screen.getByRole('link',{name:/Portable ZIP on GitHub/i}).getAttribute('href')).toBe(LINKS.latest)
  expect(screen.getByRole('link',{name:/Checksums on GitHub Releases/i}).getAttribute('href')).toBe(LINKS.latest)
  expect(screen.getByText(/Live release details unavailable/)).toBeTruthy()
 })
})
