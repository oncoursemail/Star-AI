#!/usr/bin/env node
/**
 * Prerenders the public landing page into frontend/dist/index.html, so a visitor sees the page as soon as the
 * HTML and CSS arrive instead of after the JavaScript has run. The browser then hydrates the same markup.
 *
 * `npm run build` calls it with --pages-only, which does nothing unless the build is the website deployment
 * (the website-pages.yml workflow) or STAR_SITE_BUILD=1 is set. Desktop builds keep an empty #root.
 *
 * It never fails a build: on any error dist/index.html is left as Vite wrote it and the page renders in the
 * browser as before.
 *
 * Usage: node frontend/scripts/prerender-site.mjs [--pages-only]
 */
import {readFile,writeFile} from 'node:fs/promises'
import {fileURLToPath,pathToFileURL} from 'node:url'
import path from 'node:path'

const here=path.dirname(fileURLToPath(import.meta.url))
const frontend=path.resolve(here,'..')
const EMPTY_ROOT='<div id="root"></div>'

/** True for the website deployment build, or when the site build is asked for explicitly. */
export function isSiteBuild(env){
 return env.STAR_SITE_BUILD==='1'||(env.GITHUB_WORKFLOW_REF||'').includes('/.github/workflows/website-pages.yml@')
}

/** Puts rendered markup into the built document. Returns null when the document is not the expected shape. */
export function injectMarkup(document,markup){
 if(document.split(EMPTY_ROOT).length!==2||!markup.startsWith('<div class="sw'))return null
 return document.replace(EMPTY_ROOT,()=>'<div id="root">'+markup+'</div>')
}

async function main(){
 if(process.argv.includes('--pages-only')&&!isSiteBuild(process.env)){
  console.log('prerender: skipped (not a website deployment build)')
  return
 }
 const indexFile=path.join(frontend,'dist','index.html')
 const document=await readFile(indexFile,'utf8')
 const {createServer}=await import('vite')
 const vite=await createServer({root:frontend,configFile:path.join(frontend,'vite.config.ts'),appType:'custom',logLevel:'error',
  server:{middlewareMode:true,hmr:false,watch:null},optimizeDeps:{noDiscovery:true,include:[]}})
 try{
  const {Landing}=await vite.ssrLoadModule('/src/Landing.tsx')
  const {createElement}=await import('react')
  const {renderToString}=await import('react-dom/server')
  const result=injectMarkup(document,renderToString(createElement(Landing)))
  if(!result)throw new Error('dist/index.html does not have an empty #root, or the page did not render')
  await writeFile(indexFile,result,'utf8')
  console.log('prerender: landing page written into dist/index.html ('+Math.round(result.length/1024)+' kB)')
 }finally{await vite.close()}
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 main().catch(error=>{
  console.warn('prerender: skipped, the page will render in the browser instead ('+(error&&error.message?error.message:error)+')')
 })
}
