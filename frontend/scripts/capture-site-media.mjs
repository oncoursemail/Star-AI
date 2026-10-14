#!/usr/bin/env node
/**
 * Captures the product images used on the public website from the real interface.
 *
 * It serves frontend/dist on loopback, opens the bundled desktop UI in its read-only browser preview
 * (`?preview=1`), and saves unmodified screenshots as WebP into frontend/public/site/. Nothing is drawn on top
 * and no element is hidden. The preview has no model and no local data, so the captures show a fresh workspace.
 *
 * Re-run after the desktop UI changes:
 *   1. npm run build                (from frontend/)
 *   2. node scripts/capture-site-media.mjs --tools <dir with playwright-core and sharp installed>
 *   (this PC: --tools ../worktrees/wt-website/.local/tools)
 *
 * The tools are deliberately not project dependencies; CI never runs this script.
 * Browser: an installed Edge or Chrome (`--channel msedge|chrome`, default msedge).
 */
import {createServer} from 'node:http'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
import {createRequire} from 'node:module'
import {fileURLToPath,pathToFileURL} from 'node:url'
import path from 'node:path'

const here=path.dirname(fileURLToPath(import.meta.url))
const frontend=path.resolve(here,'..')
const args=process.argv.slice(2)
const option=(name,fallback)=>{const index=args.indexOf('--'+name);return index>=0&&args[index+1]?args[index+1]:fallback}
const toolsDir=path.resolve(option('tools',path.resolve(frontend,'..','.local','tools')))
const channel=option('channel','msedge')
const dist=path.join(frontend,'dist')
const outDir=path.join(frontend,'public','site')

const require=createRequire(pathToFileURL(path.join(toolsDir,'package.json')))
const {chromium}=require('playwright-core')
const sharp=require('sharp')

const TYPES={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.json':'application/json','.webp':'image/webp','.png':'image/png'}
function serve(){
 const server=createServer(async(request,response)=>{
  try{
   const url=new URL(request.url||'/','http://127.0.0.1')
   const relative=decodeURIComponent(url.pathname).replace(/^\/+/,'')||'index.html'
   const file=path.resolve(dist,relative)
   if(!file.startsWith(dist+path.sep)&&file!==dist)throw new Error('outside dist')
   const body=await readFile(file)
   response.writeHead(200,{'content-type':TYPES[path.extname(file)]||'application/octet-stream','cache-control':'no-store'})
   response.end(body)
  }catch{response.writeHead(404);response.end('Not found')}
 })
 return new Promise(resolve=>server.listen(0,'127.0.0.1',()=>resolve(server)))
}

const DESKTOP={width:1280,height:800}
const PHONE={width:390,height:844}

/** Scrolls the conversation so the answer's first heading sits near the top, as a reader would see it. */
async function showAnswerTop(page){
 await page.evaluate(()=>{
  const heading=[...document.querySelectorAll('h2')].find(node=>/Inventory for Ember Hollow/.test(node.textContent||''))
  let box=heading?.parentElement||null
  while(box&&box.scrollHeight<=box.clientHeight+4)box=box.parentElement
  if(heading&&box)box.scrollTop+=heading.getBoundingClientRect().top-box.getBoundingClientRect().top-24
 })
}
/** Union of the boxes of several elements, padded, for a crop that keeps a popover with its trigger. */
async function unionClip(page,selectors,pad){
 const boxes=[]
 for(const selector of selectors){const box=await page.locator(selector).first().boundingBox();if(box)boxes.push(box)}
 const x=Math.max(0,Math.min(...boxes.map(b=>b.x))-pad),y=Math.max(0,Math.min(...boxes.map(b=>b.y))-pad)
 const right=Math.max(...boxes.map(b=>b.x+b.width))+pad,bottom=Math.max(...boxes.map(b=>b.y+b.height))+pad
 return {x,y,width:right-x,height:bottom-y}
}

/**
 * Each shot: the page query, a viewport, optional steps through the real controls, and either the viewport or a
 * crop. `fixture=chat` is the preview's scripted sample conversation; the app labels it "Preview fixture".
 */
const SHOTS=[
 {id:'chat',query:'tab=chat&fixture=chat',viewport:DESKTOP,widths:[1280,2560],prepare:async page=>{
   await showAnswerTop(page)
   await page.getByRole('button',{name:'More options for Inventory UI for Ember Hollow'}).click()
 }},
 {id:'chat-phone',query:'tab=chat&fixture=chat',viewport:PHONE,widths:[780],prepare:showAnswerTop},
 {id:'plus',query:'tab=chat',viewport:DESKTOP,crop:true,prepare:async page=>{
   await page.getByRole('button',{name:'Add files and tools'}).click()
   await page.waitForTimeout(250)
   return unionClip(page,['[role="menu"]'],1)
 }},
 {id:'consent',query:'tab=chat',viewport:DESKTOP,crop:true,prepare:async page=>{
   await page.getByRole('button',{name:'Add files and tools'}).click()
   await page.getByRole('menuitem',{name:/Look at my screen/}).click()
   await page.waitForTimeout(300)
   return unionClip(page,['[role="dialog"]'],24)
 }},
 {id:'learned',query:'tab=brain',viewport:{width:1100,height:900},crop:true,prepare:async page=>{
   await page.locator('.learn-brain').first().scrollIntoViewIfNeeded()
   return unionClip(page,['.learn-brain'],0)
 }},
 {id:'learned-phone',query:'tab=brain',viewport:PHONE,crop:true,prepare:async page=>{
   await page.locator('.learn-brain').first().scrollIntoViewIfNeeded()
   return unionClip(page,['.learn-brain'],0)
 }}
]

async function settle(page){
 await page.waitForSelector('[data-preview="true"]',{timeout:20_000})
 await page.evaluate(()=>document.fonts.ready)
 await page.waitForTimeout(450)
}
async function save(buffer,name,widths){
 const meta=await sharp(buffer).metadata()
 const made=[]
 for(const width of widths){
  if(width>meta.width)continue
  const file=name+'-'+width+'.webp'
  const info=await sharp(buffer).resize({width}).webp({quality:84,effort:6}).toFile(path.join(outDir,file))
  made.push({file,width:info.width,height:info.height,bytes:info.size})
 }
 return made
}

const server=await serve()
const base='http://127.0.0.1:'+server.address().port+'/'
const browser=await chromium.launch({channel,headless:true})
const manifest={capturedAt:new Date().toISOString(),sourceVersion:JSON.parse(await readFile(path.join(frontend,'package.json'),'utf8')).version,images:{}}
try{
 await mkdir(outDir,{recursive:true})
 for(const shot of SHOTS){
  const context=await browser.newContext({viewport:shot.viewport,deviceScaleFactor:2,reducedMotion:'reduce',colorScheme:'dark'})
  const page=await context.newPage()
  await page.goto(base+'?preview=1&'+shot.query,{waitUntil:'networkidle'})
  await settle(page)
  const clip=shot.prepare?await shot.prepare(page):undefined
  await page.waitForTimeout(200)
  const png=await page.screenshot({type:'png',...(shot.crop&&clip?{clip}:{})})
  const {width}=await sharp(png).metadata()
  manifest.images[shot.id]=await save(png,shot.id,shot.widths||[Math.round(width/2),width])
  await context.close()
 }
}finally{
 await browser.close()
 server.close()
}
await writeFile(path.join(frontend,'src','siteMedia.json'),JSON.stringify(manifest,null,1)+'\n','utf8')
for(const [name,files] of Object.entries(manifest.images)){
 console.log(name.padEnd(18),files.map(file=>file.width+'w '+Math.round(file.bytes/1024)+' kB').join(', '))
}
