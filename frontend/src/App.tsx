import {lazy,Suspense,useEffect,useState} from 'react'
import {initializeBridge,request} from './bridge'
import type {BootData} from './types'
import {Landing} from './Landing'

const query=new URLSearchParams(window.location.search)
const wantsPreview=query.has('preview')
/** The Qt shell always opens the bundle with ?desktop=1 and injects its transport before page scripts run. */
const expectsNativeHost=query.has('desktop')||Boolean(window.qt?.webChannelTransport)
/** The desktop workspace is its own chunk, so the public website never downloads the chat, charts or Markdown code. */
const loadDesktop=()=>import('./Desktop')
const Desktop=lazy(()=>loadDesktop().then(module=>({default:module.Desktop})))
// Start fetching the workspace while the native bridge is still connecting.
if(expectsNativeHost||wantsPreview)void loadDesktop().catch(()=>undefined)

const preparing=<div className="app-loading"><span className="loading-star">✦</span><span>Preparing STAR</span></div>

export function App(){
 const [boot,setBoot]=useState<BootData|null>(null)
 // A plain browser has no native host to wait for, so the public page renders on the first frame.
 const [ready,setReady]=useState(!expectsNativeHost)
 useEffect(()=>{
   let live=true
   initializeBridge().then(async connected=>{
     if(connected){const answer=await request<BootData>('bootstrap');if(live&&answer.ok&&answer.data)setBoot(answer.data)}
     if(live)setReady(true)
   }).catch(()=>{if(live)setReady(true)})
   return ()=>{live=false}
 },[])
 if(!ready)return preparing
 if(boot)return <Suspense fallback={preparing}><Desktop key={boot.project+'-desktop'} initial={boot}/></Suspense>
 if(wantsPreview)return <Suspense fallback={preparing}><Desktop preview/></Suspense>
 if(window.qt?.webChannelTransport)return <div className="app-loading"><span className="loading-star">✦</span><strong>STAR couldn't connect to its local engine.</strong><span>Restart STAR. If this continues, try --legacy-ui or report the error in GitHub Issues.</span></div>
 return <Landing/>
}
