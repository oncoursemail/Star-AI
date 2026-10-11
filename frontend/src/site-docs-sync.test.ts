import {readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {describe,expect,it} from 'vitest'
import {LINKS,SOURCE_VERSION,evalResults,modelLabelForRelease} from './siteContent'

const root=resolve(process.cwd(),'..')
const readme=readFileSync(resolve(root,'README.md'),'utf8')
const handoff=readFileSync(resolve(root,'docs','WEBSITE_RELEASE_CHECKLIST.md'),'utf8')

describe('README and website release transparency',()=>{
 it('does not advertise v0.9 LAN and hosted models as shipped in v0.8.1',()=>{
  const release={tag:'v0.8.1',name:'STAR',publishedAt:'2026-10-10T00:00:00Z',
   url:LINKS.latest,prerelease:false,assets:[]}
  expect(modelLabelForRelease(release)).toBe('On-device model option')
  expect(modelLabelForRelease({...release,tag:'v0.9.0'})).toBe('Local, LAN or opt-in hosted')
  expect(modelLabelForRelease(null)).toBe('Check GitHub')
  expect(modelLabelForRelease({...release,tag:'unverified'})).toBe('Check GitHub')
 })
 it('separates development source from a public Windows installer',()=>{
  expect(readme).toContain('[Latest published Windows release]('+LINKS.latest+')')
  expect(readme).toContain('v'+SOURCE_VERSION+' is a source candidate')
  expect(readme).toContain('currently downloadable v0.8.1 binary')
  expect(readme).toContain('PRs, CI artifacts and passing tests')
  expect(readme.toLowerCase()).toContain('no licence file')
 })
 it('aligns the public baseline numbers and their limits',()=>{
  for(const result of evalResults){
   expect(readme).toContain(result.passed)
   expect(readme).toContain(result.rate.replace(' ',''))
  }
  expect(readme).toContain('16 Roblox v2 tasks')
  expect(readme).toContain('not a game-quality score')
 })
 it('links to the release handoff and keeps its unverified gates visible',()=>{
  expect(readme).toContain('[Website and release handoff checklist](docs/WEBSITE_RELEASE_CHECKLIST.md)')
  for(const phrase of ['GitHub Pages','Windows release','Approved mascot assets','Website CI'])
   expect(handoff).toContain(phrase)
  expect(handoff).toContain('not a deployed website')
 })
})
