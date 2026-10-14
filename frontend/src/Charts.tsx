import {Area,AreaChart,CartesianGrid,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts'
import type {Analytics} from './types'
import type {CSSProperties} from 'react'
import {Activity,BookOpen,CheckCircle2,Clock3,MessageSquareText,ShieldCheck,Terminal,TriangleAlert} from 'lucide-react'
import {Panel,Tag} from './components'
import {EmptyState} from './states'
import {useStarReducedMotion} from './MotionPolicy'

const formatter=(value:number|null)=>value===null?'—':value<1000?`${value} ms`:`${(value/1000).toFixed(1)} s`
export function AnalyticsView({data}:{data:Analytics}) {
  const reducedMotion=useStarReducedMotion()
  const total=data.started||0
  const totalOutcomes=data.succeeded+data.failed
  const share=totalOutcomes?Math.round((data.succeeded/totalOutcomes)*100):0
  const points=data.trend||[]
  // Counted learning events (star/analytics.py). Missing on an older host: shown as zero, never guessed.
  const learning=data.learning||{captured:0,accepted:0,used:0}
  return <div className="scroll-region" tabIndex={0} role="region" aria-label="Analytics">
    <div className="page-wrap dashboard">
      <div className="page-intro"><h1>Analytics</h1><p>Real activity from your local workspace. No cloud tracking, no made-up numbers.</p></div>
      <div className="stat-grid">
        {[
          {icon:<Activity size={18}/>,label:'Task runs',value:total,meta:'Last 14 days'},
          {icon:<CheckCircle2 size={18}/>,label:'Successful',value:data.succeeded,meta:totalOutcomes?`${share}% of finished runs`:'No completed runs yet'},
          {icon:<MessageSquareText size={18}/>,label:'Messages',value:data.messages,meta:'Current project'},
          {icon:<Clock3 size={18}/>,label:'Median response',value:formatter(data.median_ms),meta:'Completed runs only'},
        ].map(item=><Panel key={item.label} className="metric-card"><div className="metric-top"><span>{item.label}</span>{item.icon}</div><strong>{item.value}</strong><small>{item.meta}</small></Panel>)}
      </div>
      <Panel className="chart-panel"><div className="section-heading"><div><span className="eyebrow">WORKSPACE ACTIVITY</span><h2>Execution trend</h2></div><Tag>Last 14 days</Tag></div>
        {total===0?<EmptyState icon={<Activity size={18}/>} title="No runs yet" description="Runs appear here after STAR finishes its first task in this project."/>:
        <div className="chart-area" role="img" aria-label="Runs per day over the last 14 days"><ResponsiveContainer width="100%" height="100%"><AreaChart data={points} margin={{top:10,right:5,left:-24,bottom:0}}><defs><linearGradient id="runFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#e9b954" stopOpacity={.25}/><stop offset="98%" stopColor="#e9b954" stopOpacity={0}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#252827" strokeDasharray="3 5"/><XAxis axisLine={false} tickLine={false} dataKey="date" tickFormatter={v=>v.slice(5)} tick={{fill:'#8c9297',fontSize:11}}/><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{fill:'#8c9297',fontSize:11}}/><Tooltip contentStyle={{background:'#17191b',border:'1px solid #353638',borderRadius:11,color:'#e9edef'}} itemStyle={{color:'#edc36b'}}/><Area type="monotone" dataKey="runs" stroke="#e9b954" strokeWidth={2.4} fill="url(#runFill)" dot={false} activeDot={{r:5}} isAnimationActive={reducedMotion?false:'auto'}/></AreaChart></ResponsiveContainer></div>}
      </Panel>
      <div className="two-up">
        <Panel className="detail-panel"><div className="section-heading"><div><span className="eyebrow">RELIABILITY</span><h2>Task outcomes</h2></div><ShieldCheck size={18}/></div><div className="outcome-chart"><div className="outcome-ring" style={{'--success':`${share}%`} as CSSProperties}><span>{totalOutcomes?`${share}%`:'—'}</span><small>success</small></div><div className="outcome-legend"><p><i className="green-bullet"/>Succeeded <strong>{data.succeeded}</strong></p><p><i className="red-bullet"/>Failed <strong>{data.failed}</strong></p><p><i className="yellow-bullet"/>Tool calls <strong>{data.tools}</strong></p></div></div></Panel>
        <Panel className="detail-panel"><div className="section-heading"><div><span className="eyebrow">EVENT LOG</span><h2>Recent activity</h2></div><Terminal size={18}/></div>{data.recent.length? <div className="event-list">{data.recent.slice(0,5).map((e,i)=><div key={`${e.at}-${i}`} className="event-row"><span className={e.type==='run_failed'?'event-mark failure':'event-mark'}>{e.type==='run_failed'?<TriangleAlert size={14}/>:<CheckCircle2 size={14}/>}</span><div><strong>{e.type.replaceAll('_',' ')}</strong><small>{new Date(e.at).toLocaleString()}</small></div></div>)}</div>:<EmptyState icon={<Terminal size={18}/>} title="Nothing recorded yet" description="Finished and failed runs are listed here as they happen."/>}</Panel>
      </div>
      <Panel className="detail-panel learn-stats"><div className="section-heading"><div><span className="eyebrow">LEARNING</span><h2>What STAR kept from your work</h2></div><BookOpen size={18}/></div>
        <p className="learn-stats-note">Lessons are local notes for this project, not model training. Counted on this PC.</p>
        <div className="stat-grid">
          {[
            {label:'Lessons captured',value:learning.captured,meta:'Last 14 days'},
            {label:'Lessons accepted',value:learning.accepted,meta:'Last 14 days'},
            {label:'Answers given with lessons',value:learning.used,meta:'Accepted lessons were in the prompt'},
            {label:'Waiting for review',value:learning.pending??0,meta:'Right now, on the Projects page'},
          ].map(item=><Panel key={item.label} className="metric-card"><div className="metric-top"><span>{item.label}</span></div><strong>{item.value}</strong><small>{item.meta}</small></Panel>)}
        </div>
      </Panel>
    </div>
  </div>
}
