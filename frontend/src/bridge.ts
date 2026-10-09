import type { BackendEvent } from './types'

declare global {
  interface Window {
    qt?: { webChannelTransport: unknown }
    QWebChannel?: new (transport: unknown, callback:(channel: {objects: {starBridge: QtBridge}}) => void) => void
    starBridge?: QtBridge
  }
}
interface QtBridge {
  invoke: (serialized:string, callback:(result:string) => void) => void
  event: { connect:(callback:(event:string) => void) => void }
}

let bridge:QtBridge|null = null
const watchers = new Set<(event:BackendEvent) => void>()
export const isDesktop = () => bridge !== null

export function onBackendEvent(fn:(event:BackendEvent)=>void) {
  watchers.add(fn)
  return () => { watchers.delete(fn) }
}
function parseEvent(raw:string) {
  try { const event = JSON.parse(raw) as BackendEvent; watchers.forEach(fn=>fn(event)) }
  catch { /* Untrusted tool output cannot crash React. */ }
}
export function initializeBridge(): Promise<boolean> {
  if (!window.qt?.webChannelTransport) return Promise.resolve(false)
  return new Promise(resolve=>{
    const finish = () => {
      if (!window.QWebChannel) { resolve(false); return }
      new window.QWebChannel(window.qt!.webChannelTransport, channel=>{
        bridge = channel.objects.starBridge
        window.starBridge = bridge
        bridge.event.connect(parseEvent)
        resolve(true)
      })
    }
    if (window.QWebChannel) finish()
    else {
      const script=document.createElement('script')
      script.src='qrc:///qtwebchannel/qwebchannel.js'
      script.onload=finish
      script.onerror=()=>resolve(false)
      document.head.append(script)
    }
  })
}

export type BackendReply<T> = {ok:boolean;data?:T; pending?:boolean;requestId?:string;error?:string}
export function request<T=unknown>(action:string, payload:Record<string,unknown>={}, providedId?:string):Promise<BackendReply<T>> {
  if (!bridge) return Promise.resolve({ok:false,error:'Open STAR Desktop to use your local AI. This website is only a preview.'})
  return new Promise(resolve=>{
    const requestId=providedId||crypto.randomUUID()
    try {
      bridge!.invoke(JSON.stringify({requestId,action,...payload}), raw=>{
        try {resolve(JSON.parse(raw) as BackendReply<T>)}
        catch {resolve({ok:false,error:'STAR returned an invalid response.'})}
      })
    } catch {resolve({ok:false,error:'STAR desktop connection is unavailable.'})}
  })
}
