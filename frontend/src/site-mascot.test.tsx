// @vitest-environment jsdom
import {afterEach,describe,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import {resolve} from 'node:path'
import {renderToString} from 'react-dom/server'
import {Landing} from './Landing'
import {SiteMascotHero,SiteMascotMeet,SiteMascotFooter} from './SiteMascot'

afterEach(()=>cleanup())

describe('Star mascot on the public site',()=>{
 it('reserves image dimensions with alt text and lazy loading for every mascot image',()=>{
  const html=renderToString(<Landing/>)
  const page=new DOMParser().parseFromString(html,'text/html')
  const images=[...page.querySelectorAll('img[src^="./assets/mascot/"]')]
  expect(images).toHaveLength(13)
  for(const image of images){
   expect(image.getAttribute('alt')).toBeTruthy()
   expect(image.getAttribute('loading')).toBe('lazy')
   expect(Number(image.getAttribute('width'))).toBeGreaterThan(0)
   expect(Number(image.getAttribute('height'))).toBeGreaterThan(0)
   expect(image.closest('.sw-mascot-art')?.getAttribute('data-loaded')).toBe('false')
  }
  expect(images.find(image=>image.getAttribute('src')==='./assets/mascot/star-hero.png')?.getAttribute('width')).toBe('1086')
  expect(images.find(image=>image.getAttribute('src')==='./assets/mascot/star-hero.png')?.getAttribute('height')).toBe('1448')
  expect(page.querySelector('.sw-mascot-hero')).toBeTruthy()
  expect(page.querySelector('#meet-star h2')?.textContent).toBe('Meet Star.')
  expect(page.querySelectorAll('#meet-star figure')).toHaveLength(8)
  expect(page.querySelectorAll('#meet-star figure[tabindex="0"]')).toHaveLength(8)
  expect(page.querySelector('.sw-footer-mascot[tabindex="0"]')).toBeTruthy()
 })
 it('does not require the artwork files to exist before rendering a complete fallback',()=>{
  const {container}=render(<SiteMascotHero/>)
  const art=container.querySelector('.sw-mascot-hero-art')!
  const image=art.querySelector('img')!
  expect(art.getAttribute('data-loaded')).toBe('false')
  expect(art.querySelector('.sw-construct')).toBeTruthy()
  fireEvent.error(image)
  expect(art.getAttribute('data-loaded')).toBe('false')
  expect(art.querySelector('.sw-mascot-fallback')).toBeTruthy()
  fireEvent.load(image)
  expect(art.getAttribute('data-loaded')).toBe('true')
 })
 it('shows exactly eight named faces even before any artwork arrives',()=>{
  render(<SiteMascotMeet/>)
  const gallery=screen.getByRole('list',{name:'Eight expressions of Star'})
  expect(gallery.querySelectorAll('figure')).toHaveLength(8)
  expect([...gallery.querySelectorAll('figcaption')].map(node=>node.textContent?.replace(/^\d\d/,'').trim())).toEqual([
   'Normal','Happy','Content','Puppy eyes','Surprised','Thinking','Focused','Proud'
  ])
 })
 it('uses the alternate expression for the blink and the wave pose for hover/focus',()=>{
  const {container}=render(<><SiteMascotHero/><SiteMascotFooter/></>)
  expect(container.querySelector('.sw-mascot-blink-alt img')?.getAttribute('src')).toBe('./assets/mascot/faces/content.png')
  const footer=container.querySelector('.sw-footer-mascot')!
  const wave=footer.querySelector('.sw-footer-pose-wave img')!
  expect(footer.getAttribute('data-can-wave')).toBe('false')
  fireEvent.load(wave)
  expect(footer.getAttribute('data-can-wave')).toBe('true')
  fireEvent.error(wave)
  expect(footer.getAttribute('data-can-wave')).toBe('false')
 })
 it('has desktop, mobile, fallback, screenshot and reduced-motion styles',()=>{
  const css=readFileSync(resolve(process.cwd(),'src','site.css'),'utf8')
  expect(css).toContain('.sw-mascot-art[data-loaded="false"]>img{opacity:0;visibility:hidden}')
  expect(css).toContain('@keyframes sw-mascot-float')
  expect(css).toContain('@keyframes sw-mascot-blink')
  expect(css).toContain('@media (max-width:900px)')
  expect(css).toContain('@media (max-width:640px)')
  expect(css).toContain('.sw-still .sw-mascot-blink-alt{opacity:0!important}')
  expect(css).toContain('.sw-mascot-blink-alt{opacity:0!important}')
  expect(css).toContain('.sw-mascot-face-card:focus-visible')
 })
})
