import { useState } from 'react';
import { motion } from 'motion/react';
import {
  ArrowDownToLine, ArrowRight, ArrowUpRight, AudioLines, Boxes, BrainCircuit,
  CheckCircle2, ChevronRight, Code2, Command, Github, Layers3,
  LockKeyhole, Menu, MessageSquareText, Orbit, Play,
  ShieldCheck, Sparkles, X,
} from 'lucide-react';
import { Brand, StarGlyph } from '../components/Brand';

const DOWNLOAD = 'https://github.com/oncoursemail/Star-AI/releases/latest';
const REPO = 'https://github.com/oncoursemail/Star-AI';

const features = [
  { icon: BrainCircuit, title: 'Your own AI, on your machine', body: 'Run a supported local language model. Your conversations are kept in your STAR workspace.' },
  { icon: Code2, title: 'Built for real development', body: 'Roblox Studio MCP, source editing, project context, and tools designed around testable changes.' },
  { icon: Layers3, title: 'Remember the important things', body: 'Project history, checkpoints, and reviewed reference assets help long projects stay on track.' },
  { icon: AudioLines, title: 'More than text', body: 'Image references, optional local voice transcription, and sampled video analysis.' },
  { icon: ShieldCheck, title: 'You control the tools', body: 'Explicit project scopes, safer defaults, and a local-first architecture.' },
  { icon: Boxes, title: 'Built to evolve', body: 'Versioned GitHub releases, open source, and evaluated development work rather than unverified self-rewrites.' },
];

function ProductPreview() {
  return <div className="preview-shell" role="img" aria-label="Concept preview of STAR's dark conversation workspace">
    <div className="preview-top"><span className="preview-controls"><i/><i/><i/></span><span>STAR / Workspace</span><span className="preview-local"><span className="signal-dot"/>LOCAL</span></div>
    <div className="preview-body">
      <aside className="preview-nav"><span className="preview-nav-current"><MessageSquareText size={14}/> Chat</span><span><Boxes size={14}/> Projects</span><span><BrainCircuit size={14}/> Brain</span><span><Orbit size={14}/> Analytics</span><div className="preview-nav-bottom">v0.7 · Genesis</div></aside>
      <div className="preview-main"><div className="preview-welcome"><span className="preview-icon"><StarGlyph size={25}/></span><strong>Your next idea starts here.</strong><small>Plan, build and think with STAR.</small></div><div className="preview-msg"><span className="preview-user">YOU</span><span>Help me create a polished Roblox inventory UI</span></div><div className="preview-reply"><span className="preview-reply-icon"><StarGlyph size={16}/></span><span><b>Here's the plan</b><br/>First, we'll map the interface and define its components. Then we'll build and test it in Studio.</span></div><div className="preview-input"><span>Message STAR...</span><span className="preview-submit"><ArrowRight size={14}/></span></div></div>
    </div>
    <div className="preview-caption">INTERFACE PREVIEW <span>·</span> DEMONSTRATION CONTENT</div>
  </div>;
}

export function Landing() {
  const [menuOpen, setMenuOpen] = useState(false);
  return <div className="landing-root">
    <div className="landing-glow" aria-hidden="true"/>
    <header className="site-header"><div className="site-header-inner">
      <a className="brand-link" href="#home" aria-label="STAR Intelligence home"><Brand/></a>
      <nav className={menuOpen ? 'site-nav site-nav-open' : 'site-nav'} aria-label="Main navigation">
        <a href="#features" onClick={()=>setMenuOpen(false)}>Features</a><a href="#workflow" onClick={()=>setMenuOpen(false)}>How it works</a>
        <a href={REPO} target="_blank" rel="noopener noreferrer">GitHub <ArrowUpRight size={14}/></a>
      </nav>
      <div className="site-header-actions"><a className="header-download" href={DOWNLOAD}><ArrowDownToLine size={15}/> Download STAR</a>
        <button className="nav-menu-btn icon-button" onClick={()=>setMenuOpen(!menuOpen)} aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen}>{menuOpen ? <X size={21}/> : <Menu size={21}/>}</button></div>
    </div></header>

    <main id="home">
      <section className="landing-hero section-wrap">
        <div className="hero-copy">
          <motion.div className="eyebrow" initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{duration:.38}}><span className="eyebrow-dot"/> YOUR AI. YOUR WORKSPACE. YOUR NEXT CHAPTER.</motion.div>
          <motion.h1 initial={{opacity:0,y:14}} animate={{opacity:1,y:0}} transition={{duration:.42,delay:.05}}>Intelligence<br/>that <span className="gold-text">builds with you.</span></motion.h1>
          <motion.p className="hero-description" initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{duration:.42,delay:.12}}>Meet STAR. A thoughtfully designed, local-first AI workspace for creating, coding, and exploring ambitious ideas. From first spark to finished project.</motion.p>
          <motion.div className="hero-actions" initial={{opacity:0}} animate={{opacity:1}} transition={{delay:.18}}><a className="button-gold" href={DOWNLOAD}><ArrowDownToLine size={18}/> Download for Windows <ArrowRight size={17}/></a><a className="button-quiet" href="?demo=1"><Play size={16}/> Explore the interface</a></motion.div>
          <p className="hero-footnote"><CheckCircle2 size={14}/> Windows 11 <span className="footer-split"/> Local model option <span className="footer-split"/> No required cloud-model API key</p>
        </div>
        <motion.div className="hero-preview" initial={{opacity:0,y:20,scale:.98}} animate={{opacity:1,y:0,scale:1}} transition={{duration:.6,delay:.15}}><div className="hero-preview-light"/><ProductPreview/></motion.div>
      </section>
      <div className="credibility section-wrap"><span>THOUGHTFUL SOFTWARE FOR AMBITIOUS WORK</span><div><span><Command size={16}/> Keyboard friendly</span><span><LockKeyhole size={16}/> Local-first</span><span><Github size={16}/> Public development</span><span><Sparkles size={16}/> Built to improve</span></div></div>
      <section id="features" className="features-section section-wrap"><div className="section-intro"><span className="kicker">WHAT STAR CAN DO</span><h2>Everything you need to<br/><span>get started.</span></h2><p>A serious workspace, with the calm focus of a great productivity app and the creative energy of something new.</p></div><div className="features-grid">{features.map(({icon:Icon,title,body},index)=><motion.article key={title} className="feature-tile" initial={{opacity:0,y:14}} whileInView={{opacity:1,y:0}} viewport={{once:true,margin:'-60px'}} transition={{delay:index*.045}}><span className="feature-icon"><Icon size={23} strokeWidth={1.7}/></span><h3>{title}</h3><p>{body}</p><span className="feature-tile-arrow"><ArrowUpRight size={17}/></span></motion.article>)}</div></section>
      <section id="workflow" className="workflow-section section-wrap"><div className="workflow-copy"><span className="kicker">THE WAY IT SHOULD WORK</span><h2>Start simple.<br/><span>Go surprisingly far.</span></h2><p>STAR is designed to remove setup friction. The development environment stays powerful; the interface stays human.</p><a href="?demo=1" className="text-link">Explore the STAR workspace <ArrowRight size={18}/></a></div><div className="steps-list">{[{n:'01',title:'Install STAR',body:'Download a normal Windows installer. Open STAR like any other desktop app.'},{n:'02',title:'Set up your local brain',body:'Get started from one friendly screen. STAR walks you through downloading a compatible model.'},{n:'03',title:'Make something real',body:'Chat, attach references, connect Roblox Studio, and preserve project context.'}].map(s=><div className="step" key={s.n}><span>{s.n}</span><div><h3>{s.title}</h3><p>{s.body}</p></div><ChevronRight size={18}/></div>)}</div></section>
      <section className="landing-final section-wrap"><span className="final-star"><StarGlyph size={39} animated/></span><span className="kicker">FROM A SPARK TO INTELLIGENCE</span><h2>Your next big idea<br/>starts with <span>STAR.</span></h2><p>Build something worth making.</p><div className="final-actions"><a className="button-gold" href={DOWNLOAD}>Get STAR for Windows <ArrowDownToLine size={17}/></a><a className="button-quiet" href={REPO} target="_blank" rel="noopener noreferrer">View GitHub <Github size={18}/></a></div></section>
    </main>
    <footer className="site-footer section-wrap"><Brand compact/><span>Built with purpose. Made to grow.</span><span>© 2026 STAR Intelligence · <a href={REPO}>GitHub</a></span></footer>
  </div>;
}
