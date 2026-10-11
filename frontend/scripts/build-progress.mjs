#!/usr/bin/env node
/**
 * Writes frontend/src/progress.json: the build-time fallback for the website's release facts and progress board.
 *
 * - Reads only public GitHub REST data for oncoursemail/Star-AI.
 * - Keeps a fixed allowlist of fields. No e-mail addresses, bodies, tokens or headers are written.
 * - GITHUB_TOKEN (the workflow's own token) is optional and only raises the rate limit. It is sent to
 *   api.github.com and nowhere else, and it is never written to disk.
 * - Never fails the build: if GitHub cannot be read completely, the existing file is left as it is.
 *
 * `npm run build` calls it with --pages-only, which does nothing unless the build is the website deployment
 * (the website-pages.yml workflow) or STAR_REFRESH_PROGRESS=1 is set. Desktop and local builds therefore make no
 * network request and ship the committed snapshot.
 *
 * Usage: node frontend/scripts/build-progress.mjs [--out <file>] [--check] [--pages-only]
 */
import {readFile,writeFile} from 'node:fs/promises'
import {fileURLToPath,pathToFileURL} from 'node:url'
import path from 'node:path'

export const REPO_SLUG='oncoursemail/Star-AI'
export const API_ROOT='https://api.github.com/repos/'+REPO_SLUG
/** Must stay identical to ENDPOINTS in src/githubPublic.ts (a unit test compares them). */
export const ENDPOINTS={
 releases:'/releases?per_page=10',
 pulls:'/pulls?state=all&sort=updated&direction=desc&per_page=100',
 issues:'/issues?state=open&per_page=100',
 commits:'/commits?per_page=8',
 milestones:'/milestones?state=open&per_page=20'
}

const isDict=value=>typeof value==='object'&&value!==null&&!Array.isArray(value)
const str=(value,limit=300)=>typeof value==='string'?value.slice(0,limit):null
const num=value=>typeof value==='number'&&Number.isFinite(value)?value:null
const list=value=>Array.isArray(value)?value.filter(isDict):[]
const labels=value=>list(value).map(label=>({name:str(label.name,60)}))
const user=value=>isDict(value)?{login:str(value.login,80),type:str(value.type,20)}:null

/** The only fields that ever reach progress.json, named exactly as GitHub names them. */
export const PICK={
 releases:items=>list(items).filter(item=>item.draft!==true).map(item=>({
  tag_name:str(item.tag_name,40),name:str(item.name,120),html_url:str(item.html_url),
  published_at:str(item.published_at,40),prerelease:item.prerelease===true,draft:false,
  assets:list(item.assets).map(asset=>({
   name:str(asset.name,120),size:num(asset.size),
   browser_download_url:str(asset.browser_download_url),digest:str(asset.digest,80)
  }))
 })),
 pulls:items=>list(items).map(item=>({
  number:num(item.number),title:str(item.title),html_url:str(item.html_url),state:str(item.state,10),
  draft:item.draft===true,merged_at:str(item.merged_at,40),created_at:str(item.created_at,40),
  updated_at:str(item.updated_at,40),user:user(item.user),labels:labels(item.labels)
 })),
 issues:items=>list(items).map(item=>({
  number:num(item.number),title:str(item.title),html_url:str(item.html_url),state:str(item.state,10),
  created_at:str(item.created_at,40),updated_at:str(item.updated_at,40),comments:num(item.comments),
  labels:labels(item.labels),
  // Presence only: marks pull requests that GitHub lists among issues so the site can exclude them.
  ...(item.pull_request?{pull_request:true}:{})
 })),
 commits:items=>list(items).map(item=>({
  sha:str(item.sha,40),html_url:str(item.html_url),
  commit:{
   message:(str(isDict(item.commit)?item.commit.message:'',400)||'').split('\n')[0].slice(0,160),
   committer:{date:str(isDict(item.commit)&&isDict(item.commit.committer)?item.commit.committer.date:null,40)}
  }
 })),
 milestones:items=>list(items).map(item=>({
  number:num(item.number),title:str(item.title,120),html_url:str(item.html_url),state:str(item.state,10),
  due_on:str(item.due_on,40),open_issues:num(item.open_issues),closed_issues:num(item.closed_issues)
 }))
}

/** True for the website deployment build, or when a refresh is asked for explicitly. */
export function shouldRefresh(env){
 return env.STAR_REFRESH_PROGRESS==='1'||(env.GITHUB_WORKFLOW_REF||'').includes('/.github/workflows/website-pages.yml@')
}

export function pickProgress(answers,generatedAt){
 const raw={}
 for(const part of Object.keys(ENDPOINTS))raw[part]=PICK[part](answers[part])
 return {schema:1,repo:REPO_SLUG,generatedAt,raw}
}

async function readPart(part,token){
 const attempt=async withToken=>fetch(API_ROOT+ENDPOINTS[part],{
  headers:{
   Accept:'application/vnd.github+json','User-Agent':'star-site-progress',
   ...(withToken&&token?{Authorization:'Bearer '+token}:{})
  },
  signal:AbortSignal.timeout(20_000)
 })
 let response=await attempt(true)
 // A workflow token without access to an endpoint is not a reason to give up: the data is public.
 if(token&&[401,403,404].includes(response.status))response=await attempt(false)
 if(!response.ok)throw new Error(part+': GitHub returned '+response.status)
 const body=await response.json()
 if(!Array.isArray(body))throw new Error(part+': unexpected answer')
 return body
}

async function main(){
 const args=process.argv.slice(2)
 const here=path.dirname(fileURLToPath(import.meta.url))
 const outIndex=args.indexOf('--out')
 const out=outIndex>=0&&args[outIndex+1]?path.resolve(args[outIndex+1]):path.resolve(here,'..','src','progress.json')
 if(args.includes('--check')){
  const saved=JSON.parse(await readFile(out,'utf8'))
  if(saved.schema!==1||saved.repo!==REPO_SLUG||!isDict(saved.raw))throw new Error('progress.json is not a valid snapshot')
  console.log('progress.json is valid, generated '+saved.generatedAt)
  return
 }
 if(args.includes('--pages-only')&&!shouldRefresh(process.env)){
  console.log('progress.json: using the committed snapshot (not a website deployment build)')
  return
 }
 const token=process.env.GITHUB_TOKEN||''
 const parts=Object.keys(ENDPOINTS)
 const settled=await Promise.allSettled(parts.map(part=>readPart(part,token)))
 const failed=settled.map((result,index)=>result.status==='rejected'?parts[index]+' ('+result.reason.message+')':null).filter(Boolean)
 if(failed.length){
  // An incomplete snapshot would look like "nothing is open", so the previous file is kept instead.
  console.warn('progress.json left unchanged; could not read: '+failed.join(', '))
  return
 }
 const answers=Object.fromEntries(parts.map((part,index)=>[part,settled[index].value]))
 const snapshot=pickProgress(answers,new Date().toISOString())
 const serialised=JSON.stringify(snapshot,null,1)+'\n'
 if(/gh[pousr]_[A-Za-z0-9]{20}|github_pat_|BEGIN [A-Z ]*PRIVATE KEY/.test(serialised)||(token&&serialised.includes(token))){
  throw new Error('Refusing to write progress.json: it looks like it contains a credential')
 }
 await writeFile(out,serialised,'utf8')
 console.log('Wrote '+path.relative(process.cwd(),out)+': '+
  parts.map(part=>snapshot.raw[part].length+' '+part).join(', '))
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 main().catch(error=>{
  // The website must still build when this helper breaks; the committed snapshot stays in place.
  console.warn('progress.json left unchanged: '+(error&&error.message?error.message:error))
 })
}
