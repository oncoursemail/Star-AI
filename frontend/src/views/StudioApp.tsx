import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, BarChart3, BookOpen,
  BrainCircuit, Check, CheckCheck, ChevronDown, CircleHelp,
  Clock3, Code2, Copy, Cpu, FileCode2, FileImage, FolderClosed,
  History, Keyboard, LayoutGrid, Menu, MessageSquareText,
  MoreHorizontal, Paperclip, PanelRightClose, PanelRightOpen, Plus, RotateCcw,
  Settings2, ShieldCheck, Sparkles, SquareTerminal, X,
} from 'lucide-react';
import { AreaChart, Area, CartesianGrid, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import { Brand, StarGlyph } from '../components/Brand';
import { emptyAnalytics, previewState, starClient } from '../lib/bridge';
import type { Analytics, Area as AreaType, Attachment, Message, Settings, StarState } from '../lib/types';

const RELEASES = 'https://github.com/oncoursemail/Star-AI/releases/latest';
const REPO = 'https://github.com/oncoursemail/Star-AI';
const NAV: { id: AreaType; title: string; icon: typeof MessageSquareText }[] = [
  { id: 'chat', title: 'Chat', icon: MessageSquareText },
  { id: 'projects', title: 'Projects', icon: LayoutGrid },
  { id: 'brain', title: 'STAR Brain', icon: BrainCircuit },
  { id: 'analytics', title: 'Analytics', icon: BarChart3 },
  { id: 'tools', title: 'Developer tools', icon: SquareTerminal },
  { id: 'settings', title: 'Settings', icon: Settings2 },
];
const STARTERS = [
  { title: 'Design an interface', detail: 'Turn my UI reference into a Roblox layout plan', icon: LayoutGrid },
  { title: 'Build a Roblox feature', detail: 'Plan and code a secure server-side inventory system', icon: Code2 },
  { title: 'Explore a problem', detail: 'Research robust animations and smooth motion blending in Roblox', icon: Sparkles },
];

function prettyDate(date: string): string {
  const d = new Date(date);
  return Number.isNaN(+d) ? '' : d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function ContentMarkdown({ text }: { text: string }) {
  return <div className="markdown-content"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    a: ({ href, children }) => <a href={href?.startsWith('https://') ? href : '#'} target="_blank" rel="noopener noreferrer">{children}</a>,
    img: () => null,
    pre: ({ children }) => <pre className="code-block">{children}</pre>,
  }}>{text}</ReactMarkdown></div>;
}

function MessageRow({ item }: { item: Message }) {
  const isUser = item.role === 'user';
  const isEvent = item.role === 'event';
  const [copied, setCopied] = useState(false);
  const doCopy = async () => {
    try { await navigator.clipboard.writeText(item.body); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }
    catch { /* Clipboard access may not be available in older Windows WebEngine. */ }
  };
  return <motion.article className={`message-row ${isUser ? 'message-user' : ''} ${isEvent ? 'message-event' : ''}`}
      initial={{ opacity: 0, y: 9 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .22 }}>
    <div className={`message-avatar ${isUser ? 'user-avatar' : ''}`}>{isUser ? 'Y' : <StarGlyph size={17}/>}</div>
    <div className="message-main"><div className="message-meta"><span>{isUser ? 'You' : isEvent ? 'STAR activity' : 'STAR'}</span><time>{prettyDate(item.created)}</time></div>
      {isUser ? <p className="plain-message">{item.body}</p> : <ContentMarkdown text={item.body}/>}
      <button className="message-copy" onClick={doCopy} aria-label={copied ? 'Copied' : 'Copy message'} title="Copy message">{copied ? <Check size={15}/> : <Copy size={15}/>}<span>{copied ? 'Copied' : 'Copy'}</span></button>
    </div>
  </motion.article>;
}

function SummaryCard({ icon: Icon, label, value, detail }: { icon: typeof Activity; label: string; value: number | string; detail: string }) {
  return <div className="metric"><div className="metric-top"><span>{label}</span><Icon size={18}/></div><strong>{value}</strong><small>{detail}</small></div>;
}

export function StudioApp({ preview }: { preview: boolean }) {
  const [state, setState] = useState<StarState>(previewState);
  const [area, setArea] = useState<AreaType>('chat');
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [status, setStatus] = useState('Ready to create');
  const [notice, setNotice] = useState('');
  const [drawer, setDrawer] = useState(true);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [brainProgress, setBrainProgress] = useState(0);
  const [settingsDraft, setSettingsDraft] = useState<Settings>(previewState.settings);
  const [newProject, setNewProject] = useState('');
  const [models, setModels] = useState<string[]>([]);
  const [updateInfo, setUpdateInfo] = useState<{ available?: boolean; version?: string; url?: string; requires_browser?: boolean } | null>(null);
  const [studioResult, setStudioResult] = useState('No Studio inspection yet.');
  const [elapsed, setElapsed] = useState(0);
  const scroller = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const startedRef = useRef(0);

  const showNotice = useCallback((message: string) => { setNotice(message); window.setTimeout(() => setNotice(''), 4600); }, []);
  const refresh = useCallback(async () => {
    const result = await starClient.request('bootstrap');
    if (result.ok && result.data && typeof result.data === 'object') {
      const fresh = result.data as StarState;
      setState(fresh); setSettingsDraft(fresh.settings);
    }
  }, []);

  useEffect(() => {
    if (preview) { setLoading(false); return; }
    let alive = true;
    starClient.connect().then(ok => {
      if (!alive) return;
      setConnected(ok); setLoading(false);
      if (ok) void refresh(); else showNotice('STAR Desktop connection unavailable. Try restarting STAR.');
    }).catch(() => {
      if (alive) { setLoading(false); showNotice('Could not connect to the desktop engine.'); }
    });
    const remove = starClient.onEvent(evt => {
      if (!alive) return;
      const type = String(evt.type ?? '');
      if (type === 'task_progress') {
        const value = evt.data;
        if (value && typeof value === 'object' && 'event' in value) setStatus(`STAR · ${String((value as {event?:string}).event).replaceAll('_',' ')}`);
      }
      if (type === 'task_done') {
        setBusy(false); setStatus('Response ready'); void refresh();
      }
      if (type === 'task_failed') { setBusy(false); const message = String(evt.error ?? 'Task could not complete'); setStatus('Task needs attention'); showNotice(message); void refresh(); }
      if (type === 'brain_progress') {
        const data = evt.data as { overall_total?: number; overall_downloaded?: number; phase?: string } | undefined;
        if (data?.overall_total) setBrainProgress(Math.min(99, Math.round((data.overall_downloaded ?? 0) / data.overall_total * 100)));
        if (data?.phase) setStatus(data.phase);
      }
      if (type === 'brain_ready') { setBusy(false); setBrainProgress(100); setStatus('STAR Brain is ready'); void refresh(); }
      if (type === 'brain_failed') { setBusy(false); showNotice(String(evt.error ?? 'STAR Brain could not start')); }
      if (type === 'models_ready') setModels(Array.isArray(evt.models) ? evt.models.map(String) : []);
      if (type === 'studio_ready') setStudioResult(JSON.stringify(evt.data ?? {}, null, 2));
      if (type === 'update_ready') setUpdateInfo(evt.data as typeof updateInfo);
      if (type === 'error') showNotice(String(evt.error ?? 'Something went wrong'));
    });
    return () => { alive = false; remove(); };
  }, [preview, refresh, showNotice]);

  useEffect(() => { if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight; }, [state.messages, busy, area]);
  useEffect(() => {
    if (!busy) return;
    const id = window.setInterval(() => setElapsed(Math.round((Date.now()-startedRef.current)/1000)), 1000);
    return () => clearInterval(id);
  }, [busy]);

  const request = async (action: string, data: Record<string, unknown> = {}) => {
    if (preview || !connected) { showNotice('You are viewing the interface preview. Open the STAR Desktop app to use its local AI tools.'); return { ok: false, error: 'Preview only' }; }
    const result = await starClient.request(action, data);
    if (!result.ok) showNotice(result.error ?? 'STAR could not complete that action');
    return result;
  };

  const send = async () => {
    if (busy || !prompt.trim()) return;
    const message = prompt.trim();
    if (preview || !connected) { showNotice('Preview only — download STAR to chat with your local AI.'); return; }
    setPrompt(''); setBusy(true); setElapsed(0); startedRef.current = Date.now(); setStatus('STAR is working on it…');
    setState(prev => ({ ...prev, messages: [...prev.messages, { id: `pending-${Date.now()}`, role: 'user', body: message, created: new Date().toISOString() }] }));
    const sent = await request('chat_send', { message, attachment_tokens: attachments.map(x => x.token) });
    setAttachments([]);
    if (!sent.ok) { setBusy(false); setStatus('Send failed'); }
  };

  const browseAttachments = async () => {
    const result = await request('select_attachments');
    if (result.ok && Array.isArray(result.data)) setAttachments(a => [...a, ...(result.data as Attachment[])].slice(0, 8));
  };
  const save = async () => {
    const r = await request('save_settings', { settings: settingsDraft });
    if (r.ok) { showNotice('Settings saved'); await refresh(); }
  };
  const brainDownload = async () => {
    const result = await request('brain_install');
    if (result.ok) { setBusy(true); setBrainProgress(0); setStatus('Setting up STAR Brain…'); }
  };
  const chooseArea = (next: AreaType) => { setArea(next); setMobileMenu(false); if (next === 'analytics') void refresh(); };
  const label = NAV.find(n => n.id === area)?.title ?? 'Chat';

  const analytics = state.analytics ?? emptyAnalytics(state.settings.project);

  return <div className="studio-root">
    <div className={`studio-sidebar ${mobileMenu ? 'sidebar-open' : ''}`}>
      <div className="sidebar-head"><Brand compact animated/><button className="icon-action menu-mobile-close" aria-label="Close menu" onClick={()=>setMobileMenu(false)}><X size={19}/></button></div>
      <div className="sidebar-workspace"><span className="sidebar-workspace-icon"><LayoutGrid size={17}/></span><span><strong>{state.settings.project}</strong><small>Workspace</small></span><ChevronDown size={15}/></div>
      <button className="new-chat-button" onClick={() => { chooseArea('chat'); setPrompt(''); textarea.current?.focus(); }}><Plus size={17}/> New conversation <span>⌘ K</span></button>
      <div className="sidebar-section-label">WORKSPACE</div>
      <nav className="sidebar-nav" aria-label="STAR sections">{NAV.map(({ id, title, icon: Icon }) => <button key={id} className={`nav-item ${area===id ? 'nav-selected' : ''}`} onClick={()=>chooseArea(id)} aria-current={area===id ? 'page' : undefined}><Icon size={18} strokeWidth={1.8}/><span>{title}</span>{area===id && <motion.span className="nav-selected-mark" layoutId="selected-nav" />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-status"><span className={`health-dot ${state.brain.ready?'health-green':''}`}/><span><strong>{state.brain.ready ? 'Local AI ready' : 'STAR Brain offline'}</strong><small>{state.brain.ready ? state.brain.model : 'Setup in STAR Brain'}</small></span></div><div className="sidebar-bottom-links"><span>GENESIS</span><span>v{state.version}</span></div></div>
    </div>
    {mobileMenu && <button className="mobile-backdrop" aria-label="Close navigation" onClick={()=>setMobileMenu(false)}/>}

    <div className="studio-main">
      <header className="studio-topbar"><div className="topbar-title"><button className="icon-action mobile-menu-open" aria-label="Open navigation" onClick={()=>setMobileMenu(true)}><Menu size={21}/></button><span>Workspace</span><span className="crumb-slash">/</span><strong>{label}</strong></div><div className="topbar-right"><span className={`topbar-brain-chip ${state.brain.ready ? 'online' : ''}`}><span className="signal-dot"/>{state.brain.ready ? 'BRAIN ONLINE' : 'LOCAL MODE'}</span><button className="icon-action" title="Toggle activity panel" aria-label="Toggle activity panel" onClick={()=>setDrawer(!drawer)}>{drawer ? <PanelRightClose size={18}/> : <PanelRightOpen size={18}/>}</button></div></header>
      <div className="studio-center">
        <div className="studio-content">
          <AnimatePresence mode="wait">
            {area === 'chat' && <motion.section className="chat-view" key="chat" initial={{opacity:0,y:6}} animate={{opacity:1,y:0}} exit={{opacity:0,y:-4}} transition={{duration:.16}}>
              <div className="chat-scroller" ref={scroller}>
                {state.messages.length===0 && !busy ? <div className="chat-empty"><div className="chat-empty-mark"><StarGlyph size={41} animated/></div><span className="micro-label">YOUR THINKING SPACE</span><h1>What are we <span>building?</span></h1><p>Bring the idea. STAR helps you think it through, then build with the right tools.</p><div className="starter-grid">{STARTERS.map(({title,detail,icon:Icon})=><button key={title} onClick={()=>{setPrompt(detail);textarea.current?.focus();}} className="starter-card"><Icon size={20}/><strong>{title}</strong><span>{detail}</span><ArrowRight className="starter-arrow" size={16}/></button>)}</div></div> : <div className="conversation-list">{state.messages.map(item=><MessageRow key={item.id} item={item}/>)}{busy && <div className="thinking-row"><span className="small-star"><StarGlyph size={20}/></span><span className="thinking-dots"><i/><i/><i/></span><span>STAR is working <span className="thinking-clock">{elapsed}s</span></span></div>}</div>}
              </div>
              <div className="chat-compose-wrap"><div className="composer-shell"><textarea ref={textarea} value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder="Message STAR…" rows={2} aria-label="Message STAR" onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){e.preventDefault();void send();}}}/>
                {attachments.length>0 && <div className="attachments-list">{attachments.map(a=><span className="attachment-tag" key={a.token}><FileImage size={14}/>{a.name}<button onClick={()=>setAttachments(x=>x.filter(y=>y.token!==a.token))} aria-label={`Remove ${a.name}`}><X size={12}/></button></span>)}</div>}
                <div className="composer-footer"><div><button className="composer-tool" onClick={browseAttachments} title="Attach image, audio, or video"><Paperclip size={18}/> Attach</button><span className="composer-mode"><Sparkles size={15}/> Assist</span></div><button className="composer-submit" onClick={()=>void send()} disabled={!prompt.trim()||busy} aria-label="Send message"><ArrowRight size={19}/></button></div></div><div className="compose-hint"><span>STAR can make mistakes. Review important changes.</span><span><Keyboard size={13}/> Ctrl+Enter to send</span></div></div>
            </motion.section>}
            {area === 'analytics' && <motion.section key="analytics" className="page-scroll" initial={{opacity:0,y:7}} animate={{opacity:1,y:0}} exit={{opacity:0}}><div className="page-title"><div><span className="micro-label">INSIGHTS / YOUR ACTIVITY</span><h1>Analytics</h1><p>What STAR actually did, measured on this computer. No synthetic numbers.</p></div><button className="soft-button" onClick={()=>void refresh()}><RotateCcw size={16}/> Refresh</button></div><div className="metric-grid"><SummaryCard icon={Activity} label="Tasks started" value={analytics.started} detail="In the last 14 days"/><SummaryCard icon={CheckCheck} label="Completed" value={analytics.succeeded} detail="Recorded successes"/><SummaryCard icon={SquareTerminal} label="Tool actions" value={analytics.tools} detail="Completed operations"/><SummaryCard icon={Clock3} label="Median runtime" value={analytics.median_ms===null?'—':`${Math.round(analytics.median_ms/1000)}s`} detail="For completed tasks"/></div>
              <div className="analytics-grid"><div className="surface-card analytics-chart"><div className="card-heading"><div><span className="micro-label">ACTIVITY TREND</span><h2>14-day overview</h2></div><span className="chart-badge">RUNS</span></div>{analytics.started===0 ? <div className="chart-zero"><BarChart3 size={32}/><strong>No activity recorded yet</strong><p>Your first completed task will appear here.</p></div> : <div className="chart-container"><ResponsiveContainer width="100%" height={254}><AreaChart data={analytics.trend}><defs><linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#eebd64" stopOpacity={.22}/><stop offset="100%" stopColor="#eebd64" stopOpacity={0}/></linearGradient></defs><CartesianGrid vertical={false} stroke="#2a2b31" strokeDasharray="3 5"/><XAxis dataKey="date" tickFormatter={x=>x.slice(5)} tickLine={false} axisLine={false} tick={{fill:'#8e9299',fontSize:11}}/><Tooltip contentStyle={{background:'#181b20',border:'1px solid #373940',borderRadius:12,color:'#f1f1ed'}}/><Area type="monotone" dataKey="runs" stroke="#efbe65" strokeWidth={2.6} fill="url(#trend-fill)" activeDot={{r:4,stroke:'#efbe65'}}/></AreaChart></ResponsiveContainer></div>}</div><div className="surface-card activity-summary"><div className="card-heading"><div><span className="micro-label">PROJECT HEALTH</span><h2>At a glance</h2></div><Activity size={19}/></div><div className="summary-row"><span>Messages sent</span><strong>{analytics.messages}</strong></div><div className="summary-row"><span>Failed tasks</span><strong>{analytics.failed}</strong></div><div className="summary-row"><span>Rejected actions</span><strong>{analytics.rejected}</strong></div><div className="summary-row"><span>Current project</span><strong>{analytics.project}</strong></div><div className="summary-tip"><ShieldCheck size={17}/><span>All measurements are stored locally. STAR does not upload analytics to a dashboard server.</span></div></div></div><div className="surface-card recent-activity"><div className="card-heading"><div><span className="micro-label">TASK HISTORY</span><h2>Recent events</h2></div><History size={18}/></div>{analytics.recent.length ? analytics.recent.map((event,i)=><div className="activity-line" key={i}><span className="activity-line-dot"/><div><strong>{event.type.replaceAll('_',' ')}</strong><small>{event.detail || 'No additional detail'}</small></div><time>{prettyDate(event.at)}</time></div>) : <p className="empty-note">No task events have been recorded yet. Start a chat to see real activity here.</p>}</div></motion.section>}
            {area === 'brain' && <motion.section key="brain" className="page-scroll" initial={{opacity:0,y:7}} animate={{opacity:1,y:0}} exit={{opacity:0}}><div className="page-title"><div><span className="micro-label">YOUR LOCAL INTELLIGENCE</span><h1>STAR Brain</h1><p>Your AI model, running on your computer. No cloud-model API key needed.</p></div></div><div className="brain-hero surface-card"><div className="brain-orb"><StarGlyph size={60} animated/></div><div className="brain-hero-copy"><span className="micro-label">LOCAL-FIRST BY DESIGN</span><h2>{state.brain.ready ? 'Your brain is online.' : 'Give STAR its brain.'}</h2><p>{state.brain.ready ? `Running ${state.brain.model}. You can return to Chat whenever you are ready.` : 'Download and launch a compatible model in STAR, without setting up another AI application.'}</p><button className="gold-button" onClick={brainDownload} disabled={busy||state.brain.ready}><ArrowDownToLine size={18}/>{state.brain.ready ? 'Brain ready' : busy ? 'Preparing your AI…' : 'Download & launch STAR Brain'}</button></div></div><div className="two-up"><div className="surface-card padded"><span className="micro-label">DOWNLOAD / MODEL STATUS</span><h2>Setup progress</h2><div className="progress-track"><motion.div animate={{width:`${brainProgress}%`}} className="progress-fill"/></div><p className="setting-help">{brainProgress}% complete · Downloading the model may take several gigabytes. Downloads are verified and kept on this device.</p></div><div className="surface-card padded"><span className="micro-label">YOUR COMPUTING RESOURCES</span><h2>Local inference</h2><div className="summary-row"><span>Model</span><strong>{state.brain.model || 'Not installed'}</strong></div><div className="summary-row"><span>Engine status</span><strong>{state.brain.state}</strong></div><div className="summary-row"><span>Privacy</span><strong>On-device</strong></div></div></div></motion.section>}
            {area === 'projects' && <motion.section key="projects" className="page-scroll" initial={{opacity:0,y:7}} animate={{opacity:1,y:0}} exit={{opacity:0}}><div className="page-title"><div><span className="micro-label">ORGANIZE YOUR WORK</span><h1>Projects</h1><p>Keep conversations and task history scoped to the right project.</p></div></div><div className="surface-card padded"><span className="micro-label">CURRENT WORKSPACE</span><h2>{state.settings.project}</h2><p className="setting-help">Choose a project below or create a new workspace. Past conversations are stored locally.</p><div className="project-grid">{state.projects.map(p=><button className={`project-tile ${p===state.settings.project?'project-active':''}`} key={p} onClick={()=>{const next={...settingsDraft,project:p};setSettingsDraft(next);void request('save_settings',{settings:next}).then(res=>{if(res.ok)void refresh();});}}><FolderClosed size={23}/><span>{p}</span>{p===state.settings.project&&<Check size={16}/>}</button>)}</div><div className="project-create"><input value={newProject} onChange={e=>setNewProject(e.target.value)} maxLength={100} placeholder="New project name" aria-label="New project name"/><button className="gold-button" onClick={()=>{if(!newProject.trim())return;const next={...settingsDraft,project:newProject.trim()};setSettingsDraft(next);void request('save_settings',{settings:next}).then(res=>{if(res.ok){setNewProject('');void refresh();}});}}><Plus size={16}/> Create</button></div></div></motion.section>}
            {area === 'tools' && <motion.section key="tools" className="page-scroll" initial={{opacity:0,y:7}} animate={{opacity:1,y:0}} exit={{opacity:0}}><div className="page-title"><div><span className="micro-label">DEVELOPMENT ENVIRONMENT</span><h1>Tools & integrations</h1><p>Connect STAR to your Roblox projects and authorized local files.</p></div></div><div className="two-up"><div className="surface-card padded"><div className="feature-heading"><span className="feature-pill"><Code2 size={20}/></span><strong>Roblox Studio MCP</strong></div><p className="setting-help">Open a disposable Roblox place, enable Studio MCP, and discover connected instances. Editing stays disabled until you enable it.</p><button className="soft-button" onClick={()=>void request('studio_discover')}><RotateCcw size={16}/> Find Studio instances</button><pre className="result-pre">{studioResult}</pre></div><div className="surface-card padded"><div className="feature-heading"><span className="feature-pill"><FileCode2 size={20}/></span><strong>Local workspace</strong></div><p className="setting-help">STAR can inspect only the directory you've chosen. File writing is separate and off by default.</p><div className="detail-field"><span>Workspace</span><strong>{state.settings.workspace || 'No workspace chosen'}</strong></div><button className="soft-button" onClick={async()=>{const r=await request('choose_workspace');if(r.ok){await refresh();}}}><FolderClosed size={16}/> Choose a folder</button></div></div></motion.section>}
            {area === 'settings' && <motion.section key="settings" className="page-scroll" initial={{opacity:0,y:7}} animate={{opacity:1,y:0}} exit={{opacity:0}}><div className="page-title"><div><span className="micro-label">MAKE STAR YOURS</span><h1>Preferences</h1><p>Easy defaults, powerful tools when you need them.</p></div><button className="gold-button" onClick={save}><Check size={17}/> Save changes</button></div><div className="settings-grid"><div className="surface-card padded"><h2>Local AI</h2><p className="setting-help">Normally STAR Brain configures these fields automatically.</p><label className="form-row">Model identifier<input value={settingsDraft.model} onChange={e=>setSettingsDraft({...settingsDraft,model:e.target.value})} placeholder="Installed model ID"/></label><label className="form-row">Local endpoint<input value={settingsDraft.endpoint} onChange={e=>setSettingsDraft({...settingsDraft,endpoint:e.target.value})}/></label><button className="soft-button" onClick={()=>void request('models_list')}><Cpu size={16}/> Detect local models</button>{models.length>0&&<div className="model-pills">{models.map(m=><button key={m} onClick={()=>setSettingsDraft({...settingsDraft,model:m})}>{m}</button>)}</div>}</div><div className="surface-card padded"><h2>Workspace access</h2><p className="setting-help">Choose a test project first. STAR never needs full computer access to inspect your Roblox place.</p><label className="form-row">Studio instance ID<input value={settingsDraft.studio_id} onChange={e=>setSettingsDraft({...settingsDraft,studio_id:e.target.value})} placeholder="From Tools → Find Studio instances"/></label><label className="toggle-row"><span><strong>Allow Studio editing</strong><small>Only in the selected instance</small></span><input type="checkbox" checked={settingsDraft.studio_edit} onChange={e=>setSettingsDraft({...settingsDraft,studio_edit:e.target.checked})}/></label><label className="toggle-row"><span><strong>Allow workspace file edits</strong><small>Restricted to your selected folder</small></span><input type="checkbox" checked={settingsDraft.workspace_edit} onChange={e=>setSettingsDraft({...settingsDraft,workspace_edit:e.target.checked})}/></label></div><div className="surface-card padded"><h2>Experience</h2><label className="toggle-row"><span><strong>Reduce animations</strong><small>Less movement throughout STAR</small></span><input type="checkbox" checked={settingsDraft.reduced_motion} onChange={e=>setSettingsDraft({...settingsDraft,reduced_motion:e.target.checked})}/></label><label className="form-row">Model turn limit<input type="number" min="1" max="30" value={settingsDraft.max_calls} onChange={e=>setSettingsDraft({...settingsDraft,max_calls:Number(e.target.value)})}/></label></div><div className="surface-card padded"><h2>Updates & version</h2><div className="detail-field"><span>Installed release</span><strong>v{state.version}</strong></div><p className="setting-help">STAR checks its public GitHub Releases for verified downloads.</p><button className="soft-button" onClick={()=>void request('check_updates')}><RotateCcw size={16}/> Check for updates</button>{updateInfo?.available ? <button className="gold-button" onClick={()=>void request('update_install')}><ArrowDownToLine size={17}/> Install v{updateInfo.version}</button> : <span className="status-copy">{updateInfo ? 'No newer public release found.' : 'No check performed yet.'}</span>}<a className="text-link-small" href={RELEASES} target="_blank" rel="noopener noreferrer">View GitHub Releases <ArrowUpRight size={14}/></a></div></div></motion.section>}
          </AnimatePresence>
        </div>
        {drawer&&<aside className="activity-rail" aria-label="STAR activity"><div className="rail-header"><span>Activity</span><MoreHorizontal size={18}/></div><div className="rail-section"><span className="micro-label">CURRENT SESSION</span><div className="rail-session"><span className={`session-indicator ${busy?'active':''}`}/><div><strong>{busy ? 'Working on request' : state.brain.ready?'Ready for your next task':'STAR is standing by'}</strong><small>{status}</small></div></div></div><div className="rail-section rail-project"><span className="micro-label">WORKSPACE</span><div className="rail-project-row"><FolderClosed size={17}/>{state.settings.project}</div><div className="rail-datum"><span>Local model</span><b>{state.brain.ready?'Active':'Offline'}</b></div><div className="rail-datum"><span>Tasks run</span><b>{analytics.started}</b></div><div className="rail-datum"><span>Tasks completed</span><b>{analytics.succeeded}</b></div></div><div className="rail-help"><CircleHelp size={18}/><p>Your project data stays local. Analytics are based on real activity.</p></div></aside>}
      </div>
    </div>
    <AnimatePresence>{notice && <motion.div className="toast-message" role="status" initial={{opacity:0,y:15}} animate={{opacity:1,y:0}} exit={{opacity:0,y:10}}><span>{notice}</span><button onClick={()=>setNotice('')} aria-label="Dismiss"><X size={16}/></button></motion.div>}</AnimatePresence>
    {loading&&<div className="loading-screen"><span className="loading-star"><StarGlyph size={44}/></span><span>Starting STAR…</span></div>}
    {preview&&<div className="preview-ribbon"><span>INTERACTIVE UI PREVIEW</span><a href={RELEASES}>Get the real STAR <ArrowUpRight size={13}/></a></div>}
  </div>;
}
