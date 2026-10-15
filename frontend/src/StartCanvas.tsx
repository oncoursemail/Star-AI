/** STAR's editorial, action-first home screen.
 * Each suggestion writes a draft to the existing composer; no tools run,
 * no permissions change and no server request happens on selection.
 */
import {ArrowUpRight, Box, Braces, LayoutDashboard, Search} from 'lucide-react'
import {StarFace, type StarMood} from './StarFace'

export const startActions = [
  {
    title: 'Design a game interface',
    detail: 'Layout, states, responsive behavior and implementation.',
    Icon: LayoutDashboard,
    prompt: 'Design a distinctive Roblox interface for my game. Start with the player goal and UI references. Define visual hierarchy, typography, spacing, responsive layouts, states, native Roblox hierarchy, and an independent screenshot review before calling it finished.',
  },
  {
    title: 'Debug a Luau script',
    detail: 'Find the cause. Prove the fix before shipping.',
    Icon: Braces,
    prompt: 'Review this Luau script. Identify reproducible bugs, exploitable remotes and performance risks. Propose the smallest safe fix, explain how to run the verification, and distinguish tested results from assumptions.\n\n',
  },
  {
    title: 'Research a game or tool',
    detail: 'Compare primary sources and show what is uncertain.',
    Icon: Search,
    prompt: 'Research this game development topic using current primary sources. Compare alternatives, include dates and citations, note uncertainty, and propose a small experiment to verify the recommendation: ',
  },
  {
    title: 'Build a 3D asset',
    detail: 'Original shape, practical geometry and clean export.',
    Icon: Box,
    prompt: 'Plan an original Blender asset for my game. Start from a specific art direction, proportion sheet and useful references. Give modeling, UV/PBR, animation-ready topology and export steps, plus visual QA from multiple angles: ',
  },
] as const

export function StartCanvas({
  project,
  mood,
  onStart,
}: {
  project: string
  mood: StarMood
  onStart: (prompt: string) => void
}) {
  return (
    <section className="start-canvas" aria-labelledby="start-canvas-title">
      <div className="start-hero">
        <div className="start-hero-copy">
          <div className="start-project"><span className="start-project-mark" aria-hidden="true"/>In <strong dir="auto" title={project}>{project}</strong></div>
          <h2 id="start-canvas-title">Make something <span>worth keeping.</span></h2>
          <p>Ideas are easy. The details make them good. Show STAR what you're building, and work through the design, code and evidence together.</p>
        </div>
        <div className="start-portrait">
          <StarFace mood={mood} size={124} follow className="start-portrait-face" label="Star, STAR's mascot"/>
          <span>Ready when you are.</span>
        </div>
      </div>
      <div className="start-section-heading">
        <h3>Where to begin</h3>
        <span>Choose a direction, then edit your brief</span>
      </div>
      <div className="start-actions" role="group" aria-label="Starting points">
        {startActions.map(({title, detail, prompt, Icon}) => (
          <button
            className="start-action"
            key={title}
            type="button"
            onClick={() => onStart(prompt)}
          >
            <span className="start-action-icon" aria-hidden="true"><Icon size={19} strokeWidth={1.7}/></span>
            <span className="start-action-copy"><strong>{title}</strong><small>{detail}</small></span>
            <ArrowUpRight className="start-action-arrow" size={16} strokeWidth={1.7} aria-hidden="true"/>
          </button>
        ))}
      </div>
      <p className="start-footer">These open a draft in your message box. Nothing runs until you send it.</p>
    </section>
  )
}
