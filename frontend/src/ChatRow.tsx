import {useEffect,useRef,useState} from 'react'
import {AnimatePresence,motion} from 'motion/react'
import {Ellipsis,Pencil,Trash2} from 'lucide-react'
import type {ChatThread} from './types'
import {useDismiss} from './Composer'
import {menuIn} from './motion'
import {useMotionVariants,useStarReducedMotion} from './MotionPolicy'

/**
 * One saved conversation in the sidebar, ChatGPT-style: the title opens it, a "More" button
 * (visible on hover, focus, or while it is the open chat) offers Rename and Delete.
 * Rename edits the title in place (Enter saves, Escape cancels). Delete hands the chat to
 * the parent, which hides it at once and offers Undo before anything is removed.
 */
export function ChatRow({chat,current,disabled,onOpen,onRename,onDelete}:{chat:ChatThread;current:boolean;disabled?:boolean;onOpen:()=>void;onRename:(title:string)=>void;onDelete:()=>void}){
 const [menu,setMenu]=useState(false)
 const [editing,setEditing]=useState(false)
 const [draft,setDraft]=useState(chat.title)
 const wrap=useRef<HTMLDivElement>(null)
 const trigger=useRef<HTMLButtonElement>(null)
 const input=useRef<HTMLInputElement>(null)
 const variants=useMotionVariants(menuIn)
 const reduced=useStarReducedMotion()
 useDismiss(menu,()=>setMenu(false),wrap,trigger)
 useEffect(()=>{if(editing){setDraft(chat.title);window.requestAnimationFrame(()=>{input.current?.focus();input.current?.select()})}},[editing,chat.title])
 useEffect(()=>{if(menu)wrap.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus()},[menu])
 const finish=(save:boolean)=>{
  const next=draft.trim()
  setEditing(false)
  if(save&&next&&next!==chat.title)onRename(next)
  window.requestAnimationFrame(()=>trigger.current?.focus())
 }
 if(editing)return <div className="rail-chat-row is-editing">
  <input ref={input} className="rail-rename" aria-label="Chat name" dir="auto" value={draft} maxLength={80}
   onChange={event=>setDraft(event.target.value)} onBlur={()=>finish(true)}
   onKeyDown={event=>{
    if(event.key==='Enter'){event.preventDefault();finish(true)}
    else if(event.key==='Escape'){event.preventDefault();event.stopPropagation();finish(false)}
   }}/>
 </div>
 return <div ref={wrap} className={'rail-chat-row'+(current?' is-current':'')+(menu?' is-menu':'')}>
  <button type="button" title={chat.title} className={'rail-item rail-chat '+(current?'is-current':'')} aria-current={current?'page':undefined} onClick={onOpen}
   onDoubleClick={()=>{if(!disabled)setEditing(true)}}><span dir="auto">{chat.title}</span></button>
  <button ref={trigger} type="button" className="rail-chat-more" aria-label={'More options for '+chat.title} title="More options" aria-haspopup="menu" aria-expanded={menu} onClick={()=>setMenu(open=>!open)}>
   <Ellipsis size={16} aria-hidden="true"/>
  </button>
  <AnimatePresence>
   {menu&&<motion.div className="rail-chat-menu" role="menu" aria-label={'Options for '+chat.title} variants={variants} initial={reduced?false:'hidden'} animate="shown" exit="exit"
    onKeyDown={event=>{
     if(event.key!=='ArrowDown'&&event.key!=='ArrowUp')return
     event.preventDefault()
     const items=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitem"]'))
     const at=items.indexOf(document.activeElement as HTMLButtonElement)
     items[(at+(event.key==='ArrowDown'?1:-1)+items.length)%items.length]?.focus()
    }}>
    <button type="button" role="menuitem" className="rail-chat-menu-item" disabled={disabled} onClick={()=>{setMenu(false);setEditing(true)}}><Pencil size={15} aria-hidden="true"/> Rename</button>
    <button type="button" role="menuitem" className="rail-chat-menu-item is-danger" disabled={disabled} onClick={()=>{setMenu(false);onDelete()}}><Trash2 size={15} aria-hidden="true"/> Delete</button>
   </motion.div>}
  </AnimatePresence>
 </div>
}
