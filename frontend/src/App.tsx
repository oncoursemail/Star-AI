import {useEffect,useState} from 'react'
import {initializeBridge,request} from './bridge'
import type {BootData} from './types'
import {Desktop} from './Desktop'
import {Landing} from './Landing'

const wantsPreview=new URLSearchParams(window.location.search).has('preview')
export function App(){
 const [boot,setBoot]=useState<BootData|null>(null)
 const [ready,setReady]=useState(false)
 useEffect(()=>{
   let live=true
   initializeBridge().then(async connected=>{
     if(connected){const answer=await request<BootData>('bootstrap');if(live&&answer.ok&&answer.data)setBoot(answer.data)}
     if(live)setReady(true)
   }).catch(()=>{if(live)setReady(true)})
   return ()=>{live=false}
 },[])
 if(!ready)return <div className="app-loading"><span className="loading-star">✦</span><span>Preparing STAR</span></div>
 if(boot)return <Desktop key={boot.project+'-desktop'} initial={boot}/>
 if(wantsPreview)return <Desktop preview/>
 if(window.qt?.webChannelTransport)return <div className="app-loading"><span className="loading-star">✦</span><strong>STAR couldn't connect to its local engine.</strong><span>Restart STAR. If this continues, try --legacy-ui or report the error in GitHub Issues.</span></div>
 return <Landing/>
}
