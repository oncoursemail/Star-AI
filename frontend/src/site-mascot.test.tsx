// @vitest-environment jsdom
import {afterEach,describe,expect,it} from 'vitest'
import {cleanup,fireEvent,render} from '@testing-library/react'
import {existsSync,readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {renderToString} from 'react-dom/server'
import {Landing} from './Landing'
import {SiteMascotHero,SiteMascotFooter} from './SiteMascot'

afterEach(()=>cleanup())
const css=readFileSync(resolve(process.cwd(),'src','site.css'),'utf8')

describe('Star mascot on the public site',()=>{
 it('uses resized copies of the approved art, with dimensions and alt text',()=>{
  const page=new DOMParser().parseFromString(renderToString(<Landing/>),'text/html')
  const hero=page.querySelector('.sw-star img')!
  expect(hero.getAttribute('src')).toBe('./site/star-hero-480.webp')
  expect(hero.getAttribute('srcset')).toContain('./site/star-hero-900.webp 900w')
  expect(hero.getAttribute('alt')).toMatch(/^Star, STAR's mascot/)
  // The hero is the largest image above the fold: never lazy, and visible from the prerendered first paint.
  expect(hero.getAttribute('loading')).toBe('eager')
  expect(hero.closest('.sw-art')?.getAttribute('data-loaded')).toBe('true')
  for(const image of page.querySelectorAll('.sw-footer-star img')){
   expect(image.getAttribute('loading')).toBe('lazy')
   expect(Number(image.getAttribute('width'))).toBeGreaterThan(0)
  }
  for(const file of ['star-hero-480.webp','star-hero-900.webp','pose-stand.webp','pose-wave-a.webp'])
   expect(existsSync(resolve(process.cwd(),'public','site',file)),file).toBe(true)
  // The originals stay where the desktop app loads them from.
  expect(existsSync(resolve(process.cwd(),'public','assets','mascot','star-hero.png'))).toBe(true)
 })
 it('falls back to the mark when the hero art fails, and recovers when it loads',()=>{
  const {container}=render(<SiteMascotHero/>)
  const art=container.querySelector('.sw-star-art')!
  const image=art.querySelector('img')!
  fireEvent.error(image)
  expect(art.getAttribute('data-loaded')).toBe('false')
  expect(art.querySelector('.sw-art-fallback svg')).toBeTruthy()
  fireEvent.load(image)
  expect(art.getAttribute('data-loaded')).toBe('true')
 })
 it('keeps every glint decorative and hidden from assistive technology',()=>{
  const {container}=render(<SiteMascotHero/>)
  const glints=container.querySelectorAll('svg.sw-glint')
  expect(glints).toHaveLength(4)
  for(const glint of glints)expect(glint.getAttribute('aria-hidden')).toBe('true')
 })
 it('waves in the footer only once the wave pose has loaded',()=>{
  const {container}=render(<SiteMascotFooter/>)
  const footer=container.querySelector('.sw-footer-star')!
  const wave=footer.querySelector('.sw-footer-pose-wave img')!
  expect(footer.getAttribute('tabindex')).toBe('0')
  expect(footer.getAttribute('data-can-wave')).toBe('false')
  fireEvent.load(wave)
  expect(footer.getAttribute('data-can-wave')).toBe('true')
  fireEvent.error(wave)
  expect(footer.getAttribute('data-can-wave')).toBe('false')
 })
 it('animates only transform and opacity, and stops for reduced motion and screenshots',()=>{
  for(const name of ['sw-float','sw-glint','sw-twinkle','sw-arrive','sw-shadow']){
   const body=css.match(new RegExp('@keyframes '+name+'\\{(.*?)\\}\\}'))?.[1]||''
   expect(body,name).not.toBe('')
   expect(body.replace(/transform:[^;}]*|opacity:[^;}]*/g,'').replace(/from|to|[\d.%,;{}\s]/g,''),name).toBe('')
  }
  expect(css).toContain('@media (prefers-reduced-motion:reduce)')
  expect(css).toMatch(/prefers-reduced-motion:reduce\)\{[^@]*animation:none!important/)
  expect(css).toContain('.sw-still .sw-glint{display:none}')
  expect(css).toContain('@media (hover:hover) and (pointer:fine)')
 })
})
