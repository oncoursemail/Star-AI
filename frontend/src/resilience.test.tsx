// @vitest-environment jsdom
/**
 * Resilience (2026-10-13): worst-case data, right-to-left text, narrow widths and the shared
 * empty / loading / error states. jsdom does not lay out or apply CSS, so layout fixes are pinned
 * by reading resilience.css; behaviour is tested through the real components.
 */
import {readFileSync} from 'node:fs'
import {afterEach,describe,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {LearnedThisWeek} from './LearnedThisWeek'
import {CircleAlert,Search} from 'lucide-react'
import {Desktop} from './Desktop'
import {EmptyState,ErrorState,LoadingState} from './states'
import {ChatRow} from './ChatRow'
import {FIXTURES,stressChats,stressProject,stressTitles,stressUserMessage} from './previewFixtures'

const source=(name:string)=>readFileSync(new URL(name,import.meta.url),'utf8').replace(/\r\n/g,'\n')
afterEach(()=>{cleanup();window.history.replaceState(null,'','/')})

describe('stress fixture',()=>{
 it('holds the worst cases it promises',()=>{
  const stress=FIXTURES.stress
  expect(stress.chats!.length).toBeGreaterThan(60)
  expect(stressTitles.unbroken).toMatch(/^a{120}$/)
  expect(stressTitles.url.length).toBeGreaterThanOrEqual(120)
  expect(stressTitles.one).toHaveLength(1)
  expect(stressTitles.arabic).toMatch(/[؀-ۿ]/)
  expect(stressTitles.hebrew).toMatch(/[֐-׿]/)
  expect(stressTitles.mixed).toMatch(/[؀-ۿ].*[A-Za-z]/)
  expect(stressUserMessage.length).toBeGreaterThan(4000)
  expect(stress.messages.some(m=>m.role==='assistant'&&/\| --- \|/.test(m.text)&&/```lua/.test(m.text))).toBe(true)
  expect(stress.messages.some(m=>m.role==='event'&&m.text.length>300)).toBe(true)
  expect(stressProject.length).toBeGreaterThan(80)
 })

 it('renders in the preview without throwing, with every title direction-aware',async()=>{
  window.history.replaceState(null,'','/?preview=1&fixture=stress')
  render(<Desktop preview/>)
  const title=await screen.findByRole('heading',{level:1,name:stressTitles.open})
  expect(title.getAttribute('dir')).toBe('auto')
  const sidebar=within(screen.getByLabelText('Saved conversations'))
  // The sidebar shows a window of 60 and says so; search still reaches the rest.
  expect(sidebar.getByText(/Showing the 60 most recent chats/)).toBeTruthy()
  for(const name of [stressTitles.arabic,stressTitles.hebrew,stressTitles.mixed,stressTitles.unbroken,stressTitles.emoji]){
   const row=sidebar.getByRole('button',{name})
   expect(row.querySelector('span')!.getAttribute('dir')).toBe('auto')
  }
  // The project name in the top bar and the sidebar is direction-aware too.
  expect(document.querySelector('.bar-crumb')!.getAttribute('dir')).toBe('auto')
  expect(screen.getAllByText(stressProject).some(node=>node.getAttribute('dir')==='auto')).toBe(true)
  // The huge message and the long error are on screen, with recovery offered for the failure.
  expect(screen.getAllByRole('article').length).toBeGreaterThanOrEqual(3)
  expect(screen.getByRole('button',{name:/retry/i})).toBeTruthy()
 })

 it('shows long project names direction-aware and in full on hover',async()=>{
  window.history.replaceState(null,'','/?preview=1&fixture=stress&tab=projects')
  render(<Desktop preview/>)
  const card=await screen.findByRole('button',{name:/مشروع البقاء/})
  const name=card.querySelector('strong')!
  expect(name.getAttribute('dir')).toBe('auto')
  expect(name.getAttribute('title')).toBe('مشروع البقاء في الغابة المظلمة')
 })
})

describe('chat row',()=>{
 it('marks the title and the rename field dir="auto"',()=>{
  const chat=stressChats.find(c=>c.title===stressTitles.hebrew)!
  render(<ChatRow chat={chat} current={false} onOpen={()=>{}} onRename={()=>{}} onDelete={()=>{}}/>)
  expect(screen.getByText(stressTitles.hebrew).getAttribute('dir')).toBe('auto')
  fireEvent.doubleClick(screen.getByRole('button',{name:stressTitles.hebrew}))
  expect(screen.getByRole('textbox',{name:'Chat name'}).getAttribute('dir')).toBe('auto')
 })
})

describe('shared states',()=>{
 it('EmptyState is quiet: no role, an icon hidden from screen readers, title, sentence and action',()=>{
  const {container}=render(<EmptyState icon={<Search size={16}/>} title="No chats match that search." description="Try a shorter word." action={<button type="button">Clear search</button>}/>)
  const root=container.firstElementChild!
  expect(root.getAttribute('role')).toBeNull()
  expect(root.querySelector('.state-icon')!.getAttribute('aria-hidden')).toBe('true')
  expect(screen.getByText('No chats match that search.')).toBeTruthy()
  expect(screen.getByText('Try a shorter word.')).toBeTruthy()
  expect(screen.getByRole('button',{name:'Clear search'})).toBeTruthy()
 })
 it('LoadingState is a polite busy status with a spoken label and a decorative skeleton',()=>{
  render(<LoadingState label="Loading lessons" lines={9}/>)
  const status=screen.getByRole('status')
  expect(status.getAttribute('aria-busy')).toBe('true')
  expect(status.getAttribute('aria-live')).toBe('polite')
  expect(within(status).getByText('Loading lessons')).toBeTruthy()
  const skeleton=status.querySelector('.state-skeleton')!
  expect(skeleton.getAttribute('aria-hidden')).toBe('true')
  expect(skeleton.children).toHaveLength(6) // capped
 })
 it('ErrorState is an alert that says what to do, with a default icon',()=>{
  render(<ErrorState title="Lessons could not be loaded." description="STAR Desktop did not answer. Try again in a moment." action={<button type="button">Try again</button>}/>)
  const alert=screen.getByRole('alert')
  expect(within(alert).getByText('Lessons could not be loaded.')).toBeTruthy()
  expect(within(alert).getByRole('button',{name:'Try again'})).toBeTruthy()
  expect(alert.querySelector('svg')).toBeTruthy()
  render(<ErrorState icon={<CircleAlert/>} title="x"/>)
 })
 it('copy stays restrained: no exclamation marks in the shared states or their uses',()=>{
  for(const file of ['./states.tsx','./Charts.tsx','./LearningPanel.tsx','./LearnedThisWeek.tsx']){
   const titles=[...source(file).matchAll(/(?:title|description)="([^"]*)"/g)].map(m=>m[1])
   for(const text of titles)expect(text,file).not.toMatch(/!/)
  }
 })
})

describe('first read of a panel',()=>{
 it('shows loading, then an error with Try again instead of claiming nothing was learned',async()=>{
  let answer:(value:unknown)=>void=()=>{}
  const calls:string[]=[]
  const invoke=(action:string)=>{calls.push(action);return action==='learnedThisWeek'?new Promise(resolve=>{answer=resolve}):Promise.resolve(null)}
  render(<LearnedThisWeek invoke={invoke as never} project="STAR"/>)
  const status=screen.getByRole('status')
  expect(status.getAttribute('aria-busy')).toBe('true')
  expect(within(status).getByText('Loading what STAR learned this week')).toBeTruthy()
  expect(screen.queryByText(/Nothing new this week/)).toBeNull()
  answer(null)
  const alert=await screen.findByRole('alert')
  expect(within(alert).getByText(/could not be loaded/)).toBeTruthy()
  fireEvent.click(within(alert).getByRole('button',{name:'Try again'}))
  await waitFor(()=>expect(calls.filter(c=>c==='learnedThisWeek')).toHaveLength(2))
  answer({items:[]})
  expect(await screen.findByText('Nothing new this week.')).toBeTruthy()
  expect(screen.queryByRole('alert')).toBeNull()
 })
})

describe('resilience.css',()=>{
 const css=source('./resilience.css')
 it('is imported once, after redesign.css, so it wins',()=>{
  const desktop=source('./Desktop.tsx')
  expect(desktop.match(/import '\.\/resilience\.css'/g)).toHaveLength(1)
  expect(desktop.indexOf("import './resilience.css'")).toBeGreaterThan(desktop.indexOf("import './redesign.css'"))
 })
 it('gives message text per-paragraph direction (the CSS form of dir="auto")',()=>{
  const rule=css.match(/([^{}]*\.msg-bubble[^{}]*)\{([^}]*)\}/)
  expect(rule).not.toBeNull()
  expect(rule![1]).toMatch(/\.msg-prose :is\(p, li/)
  expect(rule![2]).toMatch(/unicode-bidi:\s*plaintext/)
  expect(rule![2]).toMatch(/text-align:\s*start/)
 })
 it('wraps unbreakable project names and lets the phone grid shrink',()=>{
  expect(css).toMatch(/\.project-card strong\s*\{[^}]*overflow-wrap:\s*anywhere/)
  expect(css).toMatch(/\.project-grid,[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\)/)
 })
 it('removes the 8px that scrolled the whole conversation sideways on narrow screens',()=>{
  expect(css).toMatch(/@media \(max-width: 850px\) \{\s*(?:\/\*[\s\S]*?\*\/\s*)?\.shell \.msg-user \.msg-actions \{\s*margin-right: 0;/)
 })
 it('raises touch targets to 32px where touch is likely',()=>{
  const block=css.slice(css.indexOf('@media (max-width: 850px), (pointer: coarse)'))
  for(const selector of ['.msg-action','.rail-chat-more','.bar-back','.learn-button','.act-step-line'])expect(block).toContain(selector)
  expect(block).toMatch(/\.rail-chat-more \{[^}]*width: 32px;[^}]*height: 32px;/)
 })
 it('stops the loading sheen under reduced motion (system setting and STAR setting)',()=>{
  expect(css).toMatch(/\.shell\[data-reduced-motion='true'\] \.state-line \{\s*animation: none;/)
  expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\.shell \.state-line \{\s*animation: none;/)
 })
})
