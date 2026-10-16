import {useEffect,useState} from 'react'
import {BookOpen,ExternalLink,Search} from 'lucide-react'
import {Panel} from './components'
import {request} from './bridge'
import './game-lab-panel.css'

type Source={id:string;name:string;url:string;category:string;scope:string;kind:string;status:string;warning:string}
type Catalog={categories:string[];total:number;truncated:boolean;sources:Source[];note:string;checked_on:string}

/** Browser of pinned research only. No download/install/execution controls. */
export function GameLabPanel({disabled=false}:{disabled?:boolean}){
 const [expanded,setExpanded]=useState(false)
 const [category,setCategory]=useState('')
 const [query,setQuery]=useState('')
 const [result,setResult]=useState<Catalog|null>(null)
 const [error,setError]=useState('')
 const [loading,setLoading]=useState(false)
 useEffect(()=>{
   if(!expanded||disabled)return
   let cancelled=false
   const timer=window.setTimeout(()=>{
     setLoading(true)
     void request<Catalog>('gameLabCatalog',{query,category}).then(response=>{
       if(cancelled)return
       setLoading(false)
       if(response.ok&&response.data){setResult(response.data);setError('')}
       else setError(response.error||'Game Lab source catalog is unavailable.')
     })
   },180)
   return ()=>{cancelled=true;window.clearTimeout(timer)}
 },[expanded,query,category,disabled])

 return <Panel className="settings-section game-lab">
   <details open={expanded} onToggle={event=>setExpanded(event.currentTarget.open)}>
     <summary className="game-lab__summary">
       <BookOpen size={20} aria-hidden="true"/>
       <span><strong>Game Lab research library</strong><small>Game engines · 74-skill library · modding · recompilation · decompilation</small></span>
     </summary>
     <div className="game-lab__body">
       <p>Reviewed reference links only. STAR does not install third-party tools, download game binaries, run mods, or grant editor access from this library.</p>
       <div className="game-lab__filters">
         <label className="game-lab__search">
           <Search size={15} aria-hidden="true"/>
           <input aria-label="Search Game Lab sources" value={query} onChange={event=>setQuery(event.target.value)}
             placeholder="Search sources and capabilities" maxLength={120} disabled={disabled}/>
         </label>
         <select aria-label="Game Lab category" value={category} onChange={event=>setCategory(event.target.value)} disabled={disabled}>
           <option value="">All subjects</option>
           {(result?.categories||[]).map(name=><option key={name} value={name}>{name}</option>)}
         </select>
       </div>
       {loading&&<p role="status">Checking approved reference catalog…</p>}
       {error&&<p role="alert">{error}</p>}
       {result&&!loading&&<div className="game-lab__results">
         <small>{result.total} sources match · Research checked {result.checked_on}</small>
         <ul>
           {result.sources.map(item=><li key={item.id}>
             <a href={item.url} target="_blank" rel="noopener noreferrer">
               <strong>{item.name}</strong><ExternalLink size={13} aria-hidden="true"/>
             </a>
             <span className="game-lab__meta">{item.category.replace('-', ' ')} · {item.status.replaceAll('_',' ')}</span>
             <p>{item.scope}</p>
             {item.warning&&<small className="game-lab__warning">{item.warning}</small>}
           </li>)}
         </ul>
         {result.truncated&&<small>Results are capped. Narrow your search to view other sources.</small>}
         {result.total===0&&<p>No reviewed sources match your search.</p>}
       </div>}
     </div>
   </details>
 </Panel>
}
