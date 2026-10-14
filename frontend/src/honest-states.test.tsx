// @vitest-environment jsdom
/**
 * Honest states: what the composer offers and where "What STAR learned this week" lives.
 *
 * Contract under test: `webSearchAvailability` follows star/web_search.py (`web_search_available`),
 * `imageReadiness` follows the checks the host runs before it makes a picture, the + menu shows the
 * reason in words that say what to do, and the Model page links to the one learned-this-week list.
 */
import {afterEach,beforeAll,beforeEach,describe,expect,it} from 'vitest'
import {cleanup,render,screen,waitFor,within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {initializeBridge,request} from './bridge'
import {backendSettings,installFakeDesktop,type FakeDesktop} from './fake-desktop'
import {Desktop} from './Desktop'
import {imageReadiness,webSearchAvailability} from './availability'
import type {BootData,MediaStatus} from './types'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await initializeBridge()})
beforeEach(()=>{desktop.reset();window.localStorage.clear()})
afterEach(cleanup)

const media=(over:Partial<MediaStatus>={}):MediaStatus=>({
 places:[{id:'images',title:'Images',field:'media_images',chosen:'pc',options:[
   {id:'servers',label:'STAR Brains (servers)',available:false,fixable:false,note:'',reason:'Not available.'},
   {id:'pc',label:'This PC (your GPU)',available:true,fixable:true,note:'',reason:''}]}],
 images:{running:false,ready:false,missing:[],model:'FLUX.2 klein',message:'ComfyUI is not running on this PC.'},
 sizes:[],can_start:false,ffmpeg:{found:true,message:''},measured_on:'',references:0,...over})

describe('web search availability (mirrors web_search_available)',()=>{
 it('is available with a Brave or Tavily key, whatever the provider',()=>{
  expect(webSearchAvailability({},{brave:true})).toEqual({ok:true})
  expect(webSearchAvailability({search_endpoint:'off'},{tavily:true})).toEqual({ok:true})
 })
 it('needs the STAR Server key when the search goes through STAR Server',()=>{
  expect(webSearchAvailability({server_endpoint:'http://server.lan:8080'},{})).toEqual({ok:false,reason:'Add your STAR Server key in Settings'})
  expect(webSearchAvailability({server_endpoint:'http://server.lan:8080'},{star_server:true})).toEqual({ok:true})
  expect(webSearchAvailability({search_endpoint:'http://search.lan:8092'},{star_server:true})).toEqual({ok:true})
 })
 it('says when search is switched off, and what to do when nothing is set up',()=>{
  expect(webSearchAvailability({search_endpoint:'off',server_endpoint:'http://server.lan:8080'},{star_server:true})).toEqual({ok:false,reason:'Web search is off in Settings'})
  expect(webSearchAvailability({},{})).toEqual({ok:false,reason:'Connect STAR Server or add a search key in Settings'})
  expect(webSearchAvailability(null,null).ok).toBe(false)
 })
})

describe('image readiness (mirrors the host checks before a picture)',()=>{
 it('is ready until the host has answered, so no setup link is shown on a guess',()=>{
  expect(imageReadiness(null)).toBe(true)
 })
 it('is ready when ComfyUI runs with its models, or can be started from a known folder',()=>{
  expect(imageReadiness(media({images:{running:true,ready:true,missing:[],model:'m',message:'Ready.'}}))).toBe(true)
  expect(imageReadiness(media({can_start:true}))).toBe(true)
 })
 it('is not ready with nothing to start, with missing model files, or with an unavailable chosen place',()=>{
  expect(imageReadiness(media())).toBe(false)
  expect(imageReadiness(media({images:{running:true,ready:false,missing:['model.safetensors'],model:'m',message:''}}))).toBe(false)
  const servers=media({can_start:true})
  servers.places[0].chosen='servers'
  expect(imageReadiness(servers)).toBe(false)
 })
})

async function boot(extra:Record<string,unknown>={}){
 desktop.host(extra)
 const answer=await request<BootData>('bootstrap')
 render(<Desktop initial={answer.data!}/>)
 await screen.findByRole('textbox',{name:/message star/i})
}

describe('the + menu says what web search needs',()=>{
 it('does not offer web search on STAR Server without its key, and says to add it',async()=>{
  await boot({settings:{...backendSettings,provider:'star_server',server_endpoint:'http://server.lan:8080'},credentials:{}})
  const user=userEvent.setup()
  await user.click(screen.getByRole('button',{name:'Add files and tools'}))
  const web=await screen.findByRole('menuitemcheckbox',{name:/Search the web/})
  expect(web.getAttribute('aria-disabled')).toBe('true')
  expect(within(web).getByText('Add your STAR Server key in Settings')).toBeTruthy()
 })
 it('offers web search on STAR Server once the key is present',async()=>{
  await boot({settings:{...backendSettings,provider:'star_server',server_endpoint:'http://server.lan:8080'},credentials:{star_server:true}})
  const user=userEvent.setup()
  await user.click(screen.getByRole('button',{name:'Add files and tools'}))
  const web=await screen.findByRole('menuitemcheckbox',{name:/Search the web/})
  expect(web.getAttribute('aria-disabled')).not.toBe('true')
 })
})

describe('What STAR learned this week appears once',()=>{
 it('lives on the Projects page; the Model page links there',async()=>{
  await boot()
  const user=userEvent.setup()
  const nav=within(screen.getByRole('navigation',{name:'Workspace'}))
  await user.click(nav.getByRole('button',{name:'More'}))
  await user.click(nav.getByRole('button',{name:'Model'}))
  const link=await screen.findByRole('region',{name:'What STAR learned'})
  expect(within(link).queryByText('What STAR learned this week')).toBeNull()
  expect(within(link).getByText(/on the Projects page/)).toBeTruthy()
  expect(desktop.sent('learnedThisWeek')).toHaveLength(0)
  await user.click(within(link).getByRole('button',{name:/Open/}))
  expect(await screen.findByRole('heading',{name:'Your workspaces',level:1})).toBeTruthy()
  await waitFor(()=>expect(screen.getAllByRole('region',{name:'What STAR learned this week'})).toHaveLength(1))
 })
})
