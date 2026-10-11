/** Candidate-only, source-provenanced research updates in the real STAR desktop. */
import {useCallback,useEffect,useRef,useState} from 'react'
import {BookOpen,ChevronRight,ExternalLink,LoaderCircle,RefreshCcw,ShieldCheck} from 'lucide-react'
import {onBackendEvent,request} from './bridge'
import {Panel,Tag} from './components'

type Source = {
  source_id:string
  url:string
  last_digest:string|null
  checked_at:string|null
  last_outcome:string
  error_code:string
}
type Observation = {
  id:number
  source_id:string
  previous_digest:string|null
  digest:string
  observed_at:string
  status:'candidate'
}
type ResearchStatus = {
  sources:Source[]
  observations:Observation[]
  candidate_count:number
  trusted_automatically:0
  can_publish:false
}
type Evidence = Observation&{url:string;excerpt:string;untrusted_reference_only:true;can_grant_permissions:false}

const sourceTitle=(value:string)=>value.split('-').map(part=>part.toUpperCase()==='MCP'?'MCP':part.charAt(0).toUpperCase()+part.slice(1)).join(' ')
const lastChecked=(value:string|null)=>value?new Date(value).toLocaleString():'Never checked'

/** All network requests require an operator click. Nothing observed is made trusted. */
export function ResearchWatchPanel({disabled=false}:{disabled?:boolean}) {
  const [status,setStatus]=useState<ResearchStatus|null>(null)
  const [evidence,setEvidence]=useState<Evidence|null>(null)
  const [checking,setChecking]=useState(false)
  const [message,setMessage]=useState('')
  const [nominated,setNominated]=useState('')
  const pending=useRef('')
  const refresh=useCallback(async()=>{
    const reply=await request<ResearchStatus>('researchStatus')
    if(reply.ok&&reply.data)setStatus(reply.data)
    else setMessage(reply.error||'Research history is not available on this device.')
  },[])

  useEffect(()=>{
    if(!disabled)void refresh()
  },[disabled,refresh])

  useEffect(()=>onBackendEvent(event=>{
    if(!pending.current||event.requestId!==pending.current||event.kind==='progress')return
    pending.current=''
    setChecking(false)
    if(event.kind==='error')setMessage(typeof event.data==='string'?event.data:'Research check failed.')
    else {
      const outcomes=Array.isArray(event.data)?event.data as Array<{outcome:string}>:[]
      setMessage(outcomes.length?
        outcomes.filter(item=>item.outcome==='changed'||item.outcome==='baseline').length+
        ' source snapshots added as untrusted candidates.':'Research check completed.')
    }
    void refresh()
  }),[refresh])

  const check=async()=>{
    if(disabled||checking)return
    setChecking(true);setMessage('Checking approved official documentation…')
    const id=crypto.randomUUID()
    pending.current=id
    const reply=await request('researchCheck',{},id)
    if(!reply.ok){
      pending.current=''
      setChecking(false)
      setMessage(reply.error||'Research check was refused.')
    }else if(!reply.pending){
      pending.current=''
      setChecking(false)
      void refresh()
    }
  }

  const showEvidence=async(id:number)=>{
    setEvidence(null)
    setNominated('')
    const reply=await request<Evidence>('researchEvidence',{observation:id})
    if(reply.ok&&reply.data)setEvidence(reply.data)
    else setMessage(reply.error||'Could not read that observation.')
  }

  const nominate=async()=>{
    if(!evidence||disabled)return
    const reply=await request<{status:string;reason:string;lesson_id:number|null}>(
      'researchNominate',{observation:evidence.id}
    )
    if(!reply.ok||!reply.data)setNominated(reply.error||'Could not queue this evidence.')
    else if(reply.data.status==='candidate')setNominated('Candidate added to Projects → Learning for your review.')
    else if(reply.data.status==='duplicate')setNominated('This candidate is already in your Learning review.')
    else setNominated('Candidate refused by the local lesson safety rules: '+reply.data.reason)
  }

  return <Panel className="settings-section integration-panel">
    <div className="integration-head">
      <div className="tool-icon"><BookOpen size={22}/></div>
      <Tag kind="neutral">Candidate-only</Tag>
    </div>
    <h2>Research Watch</h2>
    <p>Check approved Roblox, Luau and GitHub documentation for revisions. STAR retains source hashes and candidate evidence locally; this never edits code, approves lessons, or publishes releases.</p>
    <div className="conn-actions">
      <button className="secondary-button" type="button" disabled={disabled||checking} onClick={()=>void check()}>
        {checking?<LoaderCircle size={15} className="spin"/>:<RefreshCcw size={15}/>}
        {checking?'Checking sources…':'Check official sources'}
      </button>
      <button className="secondary-button" type="button" disabled={disabled||checking} onClick={()=>void refresh()}>
        Refresh history
      </button>
    </div>
    {message&&<p role="status">{message}</p>}
    <div className="toggle-line"><span><strong>Research observations</strong></span><Tag>{status?.candidate_count??0} pending review</Tag></div>
    <div className="toggle-line"><span><strong>Automatic trust promotion</strong></span><Tag kind="neutral">Off</Tag></div>
    {status?.sources.map(source=><div className="toggle-line" key={source.source_id}>
      <div><strong>{sourceTitle(source.source_id)}</strong><small> {lastChecked(source.checked_at)}{source.error_code?' · '+source.error_code:''}</small></div>
      <a href={source.url} rel="noopener noreferrer" target="_blank" aria-label={'Open '+sourceTitle(source.source_id)+' source'}><ExternalLink size={15}/></a>
      <Tag kind={source.last_outcome==='changed'?'gold':'neutral'}>{source.last_outcome}</Tag>
    </div>)}
    {status?.observations.length?<>
      <h3>Recent evidence</h3>
      {status.observations.slice(0,8).map(item=><div className="toggle-line" key={item.id}>
        <div><strong>{sourceTitle(item.source_id)}</strong><small> {item.digest.slice(0,12)} · {lastChecked(item.observed_at)}</small></div>
        <button className="secondary-button" type="button" disabled={disabled} onClick={()=>void showEvidence(item.id)}>
          Inspect <ChevronRight size={14}/>
        </button>
      </div>)}
    </>:<p>No research snapshots are recorded on this device yet.</p>}
    {evidence&&<section aria-label="Research evidence">
      <h3>{sourceTitle(evidence.source_id)}</h3>
      <p><ShieldCheck size={15}/> Untrusted source excerpt. Not approved as fact or executable instruction.</p>
      <p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxHeight:320,overflow:'auto'}}>{evidence.excerpt}</p>
      <button className="secondary-button" type="button" disabled={disabled} onClick={()=>void nominate()}>Send candidate to Learning review</button>
      {nominated&&<p role="status">{nominated}</p>}
    </section>}
  </Panel>
}
