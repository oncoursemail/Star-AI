/**
 * What STAR has learned for the current project, and the owner's control over it.
 *
 * STAR's model is never retrained. A lesson is a local note with a source: the
 * owner's own words are accepted for the project (unless "review everything" is
 * on); anything STAR inferred waits here until the owner approves it. Every
 * button below is an explicit review action sent to the desktop host.
 */
import {useCallback,useEffect,useRef,useState} from 'react'
import {BookOpen,Check,Download,LoaderCircle,Pencil,RotateCcw,Sparkles,Trash2,X} from 'lucide-react'
import {onBackendEvent} from './bridge'
import {Tag} from './components'
import type {AppSettings,Lesson,LessonCounts,LessonStatus} from './types'
import './learning.css'

type Invoke=(action:string,params?:Record<string,unknown>)=>Promise<unknown|null>
type View='waiting'|'accepted'|'aside'
type Listing={lessons?:Lesson[];counts?:LessonCounts}
type DigestReport={created?:number;skipped?:string;error?:string;cancelled?:boolean;raw?:number}

const views:Array<{id:View;label:string;has:LessonStatus[]}>=[
 {id:'waiting',label:'Waiting',has:['candidate']},
 {id:'accepted',label:'Accepted',has:['accepted']},
 {id:'aside',label:'Set aside',has:['rejected','superseded','merged']},
]
const kindNames:Record<string,string>={preference:'Preference',correction:'Correction',pitfall:'Pitfall',fact:'Fact',decision:'Decision',requirement:'Requirement',fix:'Fix'}
const statusNames:Record<LessonStatus,string>={candidate:'Waiting for review',accepted:'Accepted',rejected:'Rejected',superseded:'Replaced by a newer lesson',merged:'Folded into a summary'}
const emptyText:Record<View,string>={
 waiting:'Nothing is waiting. Notes STAR works out for itself appear here and are not used until you approve them.',
 accepted:'No lessons yet. Tell STAR a preference or correct an answer, and it is kept for this project.',
 aside:'Nothing has been rejected or replaced.',
}
const day=(stamp:string)=>{const time=Date.parse(stamp);return Number.isNaN(time)?'':new Date(time).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'})}
/** Why the background step did nothing, in the owner's terms. */
const skipReasons:Record<string,string>={
 nothing_waiting:'There are no raw notes to summarise.',no_spare_model:'No spare model is available for a background summary.',off:'Background summaries are turned off.',
 cloud:'Background summaries are off while a hosted provider is selected.',no_model:'Select a model first.',settings:'Check your model settings first.',
}
export function describeDigest(report:DigestReport):string{
 if(report.error)return 'The summary could not run: the model did not answer. Nothing was changed.'
 if(report.cancelled)return 'The summary was stopped. Nothing was changed.'
 if(report.skipped)return skipReasons[report.skipped]||'Nothing was summarised.'
 if(!report.created)return 'The model found nothing worth keeping in those notes.'
 return `${report.created===1?'1 suggested lesson is':report.created+' suggested lessons are'} waiting for your review.`
}

export function LearningPanel({project,settings,counts,invoke,disabled=false,refresh}:{project:string;settings:AppSettings;counts?:LessonCounts;invoke:Invoke;disabled?:boolean;refresh?:()=>void}){
 const [lessons,setLessons]=useState<Lesson[]>([])
 const [totals,setTotals]=useState<LessonCounts|undefined>(counts)
 const [view,setView]=useState<View>('waiting')
 const [editing,setEditing]=useState<number|null>(null)
 const [draft,setDraft]=useState('')
 const [confirming,setConfirming]=useState<number|null>(null)
 const [pending,setPending]=useState('')
 const [notice,setNotice]=useState('')
 const [teach,setTeach]=useState('')
 const digestId=useRef('')
 const load=useCallback(async()=>{
   if(disabled)return
   const found=await invoke('listLessons') as Listing|null
   if(found?.lessons){setLessons(found.lessons);setTotals(found.counts)}
 },[disabled,invoke])
 useEffect(()=>{void load()},[load,project])
 // The background summary answers later, as an event: show what it did and re-read the list.
 useEffect(()=>onBackendEvent(event=>{
   if(!digestId.current||event.requestId!==digestId.current||event.kind==='progress')return
   digestId.current='';setPending('')
   setNotice(event.kind==='error'?String(event.data||'The summary could not run.').slice(0,240):describeDigest((event.data||{}) as DigestReport))
   void load()
 }),[load])
 const review=async(op:'approve'|'edit'|'reject'|'delete'|'restore',lesson:Lesson,text?:string)=>{
   if(disabled||pending)return
   setPending(op+':'+lesson.id);setNotice('')
   try{
     // `approved` is the owner's click on this button; the host refuses a review without it.
     const done=await invoke('reviewLesson',{op,id:lesson.id,approved:true,...(text!==undefined?{text}:{})}) as {counts?:LessonCounts}|null
     if(done){
       setEditing(null);setConfirming(null)
       setNotice({approve:'Accepted. STAR will use it in this project.',edit:'Wording saved.',reject:'Rejected. STAR will not use it.',delete:'Deleted.',restore:'Restored. STAR will use it again.'}[op])
       await load();refresh?.()
     }
   }finally{setPending('')}
 }
 const remember=async()=>{
   const entry=teach.trim();if(disabled||pending||entry.length<3)return
   setPending('teach');setNotice('')
   try{
     const done=await invoke('rememberDecision',{text:entry,kind:'decision',approved:true})
     if(done){setTeach('');setNotice('Saved for this project.');setView('accepted');await load();refresh?.()}
   }finally{setPending('')}
 }
 const exportAll=async()=>{
   if(disabled||pending)return
   setPending('export');setNotice('')
   try{
     const done=await invoke('exportLessons') as {cancelled?:boolean;filename?:string;count?:number}|null
     if(done&&!done.cancelled)setNotice(`Exported ${done.count??lessons.length} ${(done.count??lessons.length)===1?'lesson':'lessons'}${done.filename?' to '+done.filename:''}.`)
   }finally{setPending('')}
 }
 const summarise=async()=>{
   if(disabled||pending)return
   setPending('digest');setNotice('')
   const reply=await invoke('digestLessons') as {pending?:boolean;requestId?:string}|null
   if(reply?.pending&&reply.requestId)digestId.current=reply.requestId
   else setPending('')
 }
 const change=async(key:'learning_auto_accept'|'learning_digest'|'learning_digest_cloud',value:boolean)=>{
   if(disabled)return
   const saved=await invoke('saveSettings',{settings:{[key]:value}})
   if(saved)refresh?.()
 }
 const waiting=totals?.pending??lessons.filter(l=>l.status==='candidate').length
 const shown=lessons.filter(l=>views.find(v=>v.id===view)!.has.includes(l.status))
 // The host counts every record; the page holds the newest of each status (star/lessons.py LIST_WINDOW).
 const countOf=(v:View)=>{const has=views.find(x=>x.id===v)!.has;return totals?has.reduce((sum,status)=>sum+(totals[status]??0),0):lessons.filter(l=>has.includes(l.status)).length}
 const raw=lessons.some(l=>l.status==='candidate'&&l.source_type!=='summary'&&l.source_type!=='user')
 const cloud=!['local','star_server'].includes(settings.provider)
 const autoAccept=settings.learning_auto_accept??true
 return <section className="learn" aria-label="What STAR has learned">
   <div className="learn-head">
     <BookOpen size={18} aria-hidden="true"/>
     <div className="learn-title"><h2>What STAR has learned</h2><p>Notes for the project “{project}”. STAR does not retrain its model: it keeps lessons you can read, change and remove, and uses the accepted ones in later answers.</p></div>
     <Tag kind={waiting?'gold':'neutral'}>{waiting} waiting for review</Tag>
   </div>
   <div className="learn-tabs" role="tablist" aria-label="Lessons by status">
     {views.map(v=><button key={v.id} type="button" role="tab" aria-selected={view===v.id} className={'learn-tab'+(view===v.id?' is-current':'')} onClick={()=>{setView(v.id);setEditing(null);setConfirming(null)}}>{v.label} <span>{countOf(v.id)}</span></button>)}
   </div>
   {shown.length===0?<p className="learn-empty">{disabled?'Open STAR Desktop to see what it has learned.':emptyText[view]}</p>
   :<ul className="learn-list">{shown.map(lesson=>{
     const busy=pending.endsWith(':'+lesson.id)
     return <li key={lesson.id} className="lesson">
       <div className="lesson-top"><span className="lesson-kind">{kindNames[lesson.kind]||lesson.kind}</span><span className="lesson-origin">{lesson.origin}{day(lesson.created)?' · '+day(lesson.created):''}{lesson.uses?` · used in ${lesson.uses} ${lesson.uses===1?'answer':'answers'}`:''}</span></div>
       {editing===lesson.id
         ?<label className="lesson-edit">New wording<textarea rows={3} maxLength={600} value={draft} autoFocus onChange={e=>setDraft(e.target.value)}/></label>
         :<p className="lesson-text">{lesson.text}</p>}
       {view==='aside'&&<p className="lesson-state">{statusNames[lesson.status]}</p>}
       {lesson.evidence&&editing!==lesson.id&&<details className="lesson-evidence"><summary>Where it came from</summary><p>{lesson.evidence}</p></details>}
       <div className="lesson-actions">
         {editing===lesson.id?<>
           <button type="button" className="learn-button is-primary" disabled={busy||draft.trim().length<3} onClick={()=>void review(lesson.status==='candidate'?'approve':'edit',lesson,draft.trim())}><Check size={14} aria-hidden="true"/> {lesson.status==='candidate'?'Save and accept':'Save wording'}</button>
           <button type="button" className="learn-button" onClick={()=>setEditing(null)}><X size={14} aria-hidden="true"/> Cancel</button>
         </>:confirming===lesson.id?<>
           <span className="lesson-confirm">Delete this lesson for good?</span>
           <button type="button" className="learn-button is-danger" disabled={busy} onClick={()=>void review('delete',lesson)}><Trash2 size={14} aria-hidden="true"/> Yes, delete</button>
           <button type="button" className="learn-button" onClick={()=>setConfirming(null)}>Keep</button>
         </>:<>
           {lesson.status==='candidate'&&<button type="button" className="learn-button is-primary" disabled={busy||disabled} onClick={()=>void review('approve',lesson)}>{busy?<LoaderCircle className="spin" size={14}/>:<Check size={14} aria-hidden="true"/>} Approve</button>}
           {(lesson.status==='rejected'||lesson.status==='superseded')&&<button type="button" className="learn-button" disabled={busy||disabled} onClick={()=>void review('restore',lesson)}><RotateCcw size={14} aria-hidden="true"/> Restore</button>}
           {(lesson.status==='candidate'||lesson.status==='accepted')&&<button type="button" className="learn-button" disabled={busy||disabled} onClick={()=>{setEditing(lesson.id);setDraft(lesson.text);setConfirming(null)}}><Pencil size={14} aria-hidden="true"/> Edit</button>}
           {(lesson.status==='candidate'||lesson.status==='accepted')&&<button type="button" className="learn-button" disabled={busy||disabled} onClick={()=>void review('reject',lesson)}><X size={14} aria-hidden="true"/> {lesson.status==='accepted'?'Stop using':'Reject'}</button>}
           <button type="button" className="learn-button" disabled={busy||disabled} onClick={()=>{setConfirming(lesson.id);setEditing(null)}}><Trash2 size={14} aria-hidden="true"/> Delete</button>
         </>}
       </div>
     </li>})}</ul>}
   {shown.length>0&&shown.length<countOf(view)&&<p className="learn-help">Showing the newest {shown.length} of {countOf(view)}. Review or delete some to see older ones; Export saves all of them.</p>}
   {notice&&<p className="learn-notice" role="status">{notice}</p>}
   <div className="learn-tools">
     <button type="button" className="learn-button" disabled={disabled||!!pending||!raw} title={raw?'Ask the fast model to reword raw notes into short suggestions':'There are no raw notes to summarise'} onClick={()=>void summarise()}>{pending==='digest'?<LoaderCircle className="spin" size={14}/>:<Sparkles size={14} aria-hidden="true"/>} {pending==='digest'?'Summarising…':'Summarise raw notes'}</button>
     <button type="button" className="learn-button" disabled={disabled||!!pending||!lessons.length} onClick={()=>void exportAll()}><Download size={14} aria-hidden="true"/> Export</button>
   </div>
   <label className="learn-teach">Teach STAR something for this project
     <textarea rows={2} maxLength={1200} disabled={disabled||pending==='teach'} value={teach} onChange={e=>setTeach(e.target.value)} placeholder="Example: Use a clean OLED interface and keep the approved avatar proportions."/>
   </label>
   <div className="learn-tools"><button type="button" className="learn-button is-primary" disabled={disabled||!!pending||teach.trim().length<3} onClick={()=>void remember()}><Check size={14} aria-hidden="true"/> Save as accepted</button><span className="learn-count">{teach.length}/1200</span></div>
   <div className="learn-settings">
     <label className="learn-switch"><span><strong>Accept my own corrections automatically</strong><small>{autoAccept?'What you state in your own words is kept at once. Everything STAR infers still waits for review.':'Review everything: even your own statements wait here until you approve them.'}</small></span><input type="checkbox" disabled={disabled} checked={autoAccept} onChange={e=>void change('learning_auto_accept',e.target.checked)}/></label>
     <label className="learn-switch"><span><strong>Summarise raw notes in the background</strong><small>After an answer, the spare fast model of a STAR Server may reword raw notes. It never runs on the model you chat with; use “Summarise raw notes” for that. Its suggestions always wait for review.</small></span><input type="checkbox" disabled={disabled} checked={settings.learning_digest??true} onChange={e=>void change('learning_digest',e.target.checked)}/></label>
     {cloud&&<label className="learn-switch"><span><strong>Also summarise with a hosted provider</strong><small>Off by default: the notes quote your chats and would be sent to the selected provider.</small></span><input type="checkbox" disabled={disabled} checked={settings.learning_digest_cloud??false} onChange={e=>void change('learning_digest_cloud',e.target.checked)}/></label>}
   </div>
   <p className="learn-help">Lessons are plain notes. They cannot grant permissions or change settings, and anything that looks like a key or password is refused.</p>
 </section>
}
