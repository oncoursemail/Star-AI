import {BrainCircuit,Check,FolderOpen,LoaderCircle,Play,Square,ShieldCheck} from 'lucide-react'
import type {AppSettings} from './types'

export type ModelTeamReport = {
  all_text_ready: boolean
  note: string
  roles: Record<string,{model:string;ok:boolean;sample?:string;error_type?:string}>
}

type Props = {
  draft: AppSettings
  onChange: (draft:AppSettings)=>void
  models: string[]
  routerRunning: boolean
  brainRunning: boolean
  disabled: boolean
  busy: boolean
  routerBusy: boolean
  teamChecking: boolean
  teamResult: ModelTeamReport|null
  chooseFolder: ()=>void
  startRouter: ()=>void
  stopBrain: ()=>void
  testTeam: ()=>void
}

/** Advanced model controls live in Settings, never in a second chat interface. */
export function ModelFleetPanel({draft,onChange,models,routerRunning,brainRunning,disabled,busy,
  routerBusy,teamChecking,teamResult,chooseFolder,startRouter,stopBrain,testTeam}:Props){
  const isLocal=draft.provider==='local'
  const update=(key:keyof AppSettings,value:string|number)=>{
    onChange({...draft,[key]:value})
  }
  return <section className="integrated-panel" aria-label="STAR model fleet">
    <div className="integrated-heading"><BrainCircuit size={19}/><div>
      <strong>STAR model team</strong>
      <span>One conversation, with specialist models selected for specific work.</span>
    </div></div>
    <p className="integrated-help">Optional model IDs must exist on your selected provider. Leave a specialist blank to use the main model. STAR never switches to a different provider silently.</p>
    <div className="integrated-key-controls">
      {([
        ['fast_model','Fast answers'],['reasoning_model','Deeper reasoning'],
        ['roblox_model','Roblox engineering'],['vision_model','Image understanding'],
      ] as const).map(([key,title])=><label className="integrated-field" key={key}>{title}
        <input list="star-model-ids" value={draft[key]??''} placeholder="Use primary model"
          disabled={disabled} onChange={e=>update(key,e.target.value)}/>
      </label>)}
    </div>
    <datalist id="star-model-ids">{models.map(id=><option key={id} value={id}/>)}</datalist>
    <div className="integrated-heading"><ShieldCheck size={18}/><div>
      <strong>Managed local GGUF runtime</strong>
      <span>{routerRunning?'Model router is running':'Optional; current single-model STAR Brain still works'}</span>
    </div></div>
    <p className="integrated-help">A real llama.cpp router loads from a folder you select, with only one resident model to limit RAM usage. No automatic weight downloads. Stop your current managed Brain before starting the router.</p>
    <label className="integrated-field">GGUF model folder
      <input value={draft.router_models_dir??''} placeholder="C:\\Models\\STAR" disabled={disabled}
        onChange={e=>update('router_models_dir',e.target.value)}/>
    </label>
    <div className="integrated-key-controls">
      <label className="integrated-field">Context tokens
        <input type="number" min={512} max={32768} step={512}
          value={draft.router_context??4096} disabled={disabled}
          onChange={e=>update('router_context',Number(e.target.value))}/>
      </label>
      <label className="integrated-field">GPU offload layers
        <input type="number" min={0} max={1000} value={draft.gpu_layers??25}
          disabled={disabled} onChange={e=>update('gpu_layers',Number(e.target.value))}/>
      </label>
    </div>
    <div className="integrated-actions">
      <button type="button" className="secondary-button" onClick={chooseFolder}
        disabled={disabled||routerBusy}><FolderOpen size={15}/> Choose folder</button>
      <button type="button" className="secondary-button" onClick={startRouter}
        disabled={disabled||routerBusy||busy||brainRunning||!isLocal||!draft.router_models_dir}>
        {routerBusy?<LoaderCircle size={15} className="spin"/>:<Play size={15}/>} Start router
      </button>
      <button type="button" className="secondary-button" onClick={stopBrain}
        disabled={disabled||routerBusy||busy||!brainRunning}><Square size={14}/> Stop managed Brain</button>
      <button type="button" className="secondary-button" onClick={testTeam}
        disabled={disabled||teamChecking||busy||!draft.model}>
        {teamChecking?<LoaderCircle size={15} className="spin"/>:<ShieldCheck size={15}/>} Test team
      </button>
    </div>
    {teamResult&&<div className="integrated-confirm" role="status">
      <strong>{teamResult.all_text_ready?'Text responses verified':'One or more models failed the text test'}</strong>
      {Object.entries(teamResult.roles).map(([role,entry])=><small key={role}>
        {role}: {entry.model} — {entry.ok?'Text response OK':entry.error_type||'Unavailable'}
      </small>)}
      <small>{teamResult.note}</small>
    </div>}
    <p className="integrated-help"><Check size={13}/> A text response is not proof of image, tools or Roblox Studio capability. Benchmark Qwen3.8-27B locally before assigning it to everyday requests.</p>
  </section>
}
