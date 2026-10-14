/**
 * Under an answer the owner marked "Not helpful": say what was wrong. STAR keeps it as a correction
 * that waits in the Learning panel; only the owner can turn it into a regression test there.
 */
import {useState} from 'react'
import {Check,LoaderCircle} from 'lucide-react'

export function CorrectionBox({onCorrect}:{onCorrect:(text:string)=>Promise<boolean>|void}){
 const [draft,setDraft]=useState('')
 const [busy,setBusy]=useState(false)
 const [saved,setSaved]=useState(false)
 const save=async()=>{
   const text=draft.trim()
   if(busy||text.length<3)return
   setBusy(true)
   try{
     const done=await onCorrect(text)
     if(done!==false){setSaved(true);setDraft('')}
   }finally{setBusy(false)}
 }
 if(saved)return <p className="msg-correction-saved" role="status">Correction saved. It waits in the Learning panel, where you can make it a test.</p>
 return <div className="msg-correction">
   <label>What was wrong? (optional)
     <textarea rows={2} maxLength={1000} value={draft} disabled={busy} onChange={e=>setDraft(e.target.value)} placeholder="Example: use task.wait instead of wait, and the door should tween open."/>
   </label>
   <button type="button" className="msg-action" disabled={busy||draft.trim().length<3} onClick={()=>void save()}>{busy?<LoaderCircle className="spin" size={14}/>:<Check size={14} aria-hidden="true"/>} Save correction</button>
 </div>
}
