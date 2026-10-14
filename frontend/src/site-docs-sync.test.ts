import {readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {describe,expect,it} from 'vitest'
import {LINKS,SOURCE_VERSION,modelLabelForRelease} from './siteContent'

const root=resolve(process.cwd(),'..')
const readme=readFileSync(resolve(root,'README.md'),'utf8')
const handoff=readFileSync(resolve(root,'docs','WEBSITE_RELEASE_CHECKLIST.md'),'utf8')

describe('published v1.0.0 website and README release status',()=>{
 it('derives model routing from the published release, not development source',()=>{
  const release={tag:'v0.8.1',name:'STAR',publishedAt:'2026-10-10T00:00:00Z',
   url:LINKS.latest,prerelease:false,assets:[]}
  expect(modelLabelForRelease(release)).toBe('On-device model option')
  expect(modelLabelForRelease({...release,tag:'v0.9.0'})).toBe('Local, LAN or opt-in hosted')
  expect(modelLabelForRelease(null)).toBe('Check GitHub')
  expect(modelLabelForRelease({...release,tag:'unverified'})).toBe('Check GitHub')
 })
 it('documents actual published v1.0.0 assets rather than a source candidate',()=>{
  expect(SOURCE_VERSION).toBe('1.0.0')
  expect(readme).toContain('**v1.0.0** was published')
  expect(readme).toContain('STAR-Setup-v1.0.0.exe')
  expect(readme).toContain('docs/release/v1.0/RELEASE_NOTES.md')
  expect(readme).toContain('STAR-Genesis-Windows-x64.zip')
  expect(readme).toContain('SHA256SUMS.txt')
  expect(readme).toContain('**PRs, CI artifacts and passing tests**')
  expect(readme).not.toContain('latest public binary is currently **STAR Genesis v0.8.1**')
  expect(readme).not.toContain('v0.9.0 is still a source candidate')
 })
 it('qualifies variable evaluation results and unreproduced creation scores',()=>{
  for(const phrase of ['13 / 34','16 / 34','18 / 34','13–18 / 34','11 / 23','single run varies','16 Roblox v2 tasks','not a game-quality score']){
   expect(readme.toLowerCase()).toContain(phrase.toLowerCase())
   expect(handoff.toLowerCase()).toContain(phrase.toLowerCase().replace('single run varies','single runs vary'))
  }
  expect(readme).not.toContain('29 / 57 (50.9%)')
 })
 it('keeps website handoff, licence warning and mascot provenance visible',()=>{
  expect(readme).toContain('[Website and release handoff checklist](docs/WEBSITE_RELEASE_CHECKLIST.md)')
  expect(readme.toLowerCase()).toContain('no licence file')
  for(const phrase of ['GitHub Pages','Windows release','Approved mascot assets','Website CI','PR #136','PR #151','not a deployed website'])
   expect(handoff).toContain(phrase)
 })
})
