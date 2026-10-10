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
const NARROW={width:430,height:620}
const VIEWS=[
 {id:'chat',prepare:async page=>{
   // Typed into the real composer. The preview never sends it anywhere.
   await page.locator('.composer textarea').first().fill('Inspect my Roblox Studio test place, then plan a responsive inventory UI. Do not edit anything yet.')
   await page.locator('.composer textarea').first().blur()
 }},
 {id:'brain'},
 {id:'tools'},
 {id:'projects'},
 {id:'analytics'}
]
/** Element-level crops used inside the feature chapters. The Studio cards are only captured stacked. */
const CROPS=[
 {id:'studio-narrow',tab:'tools',selector:'.two-up',viewport:{width:430,height:900}},
 {id:'setup',tab:'brain',selector:'.brain-simple',viewport:{width:980,height:800}},
 {id:'setup-narrow',tab:'brain',selector:'.brain-simple',viewport:{width:430,height:800}}
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
 for(const view of VIEWS){
  for(const [suffix,viewport,widths] of [['',DESKTOP,[1280,2560]],['-narrow',NARROW,[860]]]){
   const context=await browser.newContext({viewport,deviceScaleFactor:2,reducedMotion:'reduce',colorScheme:'dark'})
   const page=await context.newPage()
   await page.goto(base+'?preview=1&tab='+view.id,{waitUntil:'networkidle'})
   await settle(page)
   if(view.prepare)await view.prepare(page)
   await page.waitForTimeout(150)
   manifest.images[view.id+suffix]=await save(await page.screenshot({type:'png'}),view.id+suffix,widths)
   await context.close()
  }
 }
 for(const crop of CROPS){
  const context=await browser.newContext({viewport:crop.viewport,deviceScaleFactor:2,reducedMotion:'reduce',colorScheme:'dark'})
  const page=await context.newPage()
  await page.goto(base+'?preview=1&tab='+crop.tab,{waitUntil:'networkidle'})
  await settle(page)
  const target=page.locator(crop.selector).first()
  await target.scrollIntoViewIfNeeded()
  const shot=await target.screenshot({type:'png'})
  const {width}=await sharp(shot).metadata()
  manifest.images[crop.id]=await save(shot,crop.id,crop.id.endsWith('-narrow')?[width]:[Math.round(width/2),width])
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
