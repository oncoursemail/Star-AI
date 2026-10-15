import {describe,expect,it} from 'vitest'
import {initialCompanion,applyCompanionEvent,chooseCompanionScene,setAnimalForm} from './companionDirector'

describe('STAR companions truthful activity contract',()=>{
 it('follows real ordered agent events, not fake completions',()=>{
   const idle=initialCompanion('claude')
   const working=applyCompanionEvent(idle,{actorId:'claude',runId:'r1',sequence:0,at:10,phase:'thinking'})
   expect(working.phase).toBe('thinking')
   expect(applyCompanionEvent(working,{actorId:'claude',runId:'r1',sequence:0,at:20,phase:'finished'})).toBe(working)
   expect(applyCompanionEvent(working,{actorId:'wrong',runId:'r1',sequence:1,at:20,phase:'finished'})).toBe(working)
   expect(applyCompanionEvent(working,{actorId:'claude',runId:'r2',sequence:0,at:20,phase:'finished'})).toBe(working)
   const complete=applyCompanionEvent(working,{actorId:'claude',runId:'r1',sequence:1,at:21,phase:'finished'})
   expect(complete.phase).toBe('finished')
   expect(applyCompanionEvent(complete,{actorId:'claude',runId:'r2',sequence:0,at:25,phase:'thinking'}).runId).toBe('r2')
 })
 it('defaults to human form and only transforms on explicit approval',()=>{
   const base=initialCompanion('star')
   expect(base.form).toBe('human')
   expect(setAnimalForm(base,'cat',false)).toBe(base)
   expect(setAnimalForm(base,'dog',true).form).toBe('dog')
 })
 it('never interrupts model work or reduced motion',()=>{
   const a=initialCompanion('star',0),b=initialCompanion('claude',0)
   const opts={enabled:true,affection:true,romance:true,reducedMotion:false,now:120000}
   expect(chooseCompanionScene([a,b],{...opts,enabled:false})).toBeNull()
   expect(chooseCompanionScene([a,b],{...opts,reducedMotion:true})).toBeNull()
   expect(chooseCompanionScene([a,b],{...opts,now:30000})).toBeNull()
   const working=applyCompanionEvent(a,{actorId:'star',runId:'r1',sequence:0,at:50000,phase:'tool'})
   expect(chooseCompanionScene([working,b],opts)).toBeNull()
 })
 it('uses non-romantic scenes by default and requires two opt-ins for kisses',()=>{
   const a=initialCompanion('star'),b=initialCompanion('claude')
   const common={enabled:true,now:300000,reducedMotion:false}
   const plain=chooseCompanionScene([a,b],{...common,affection:false,romance:false})
   expect(plain?.action).not.toBe('hug')
   expect(plain?.action).not.toBe('kiss')
   const withLove=Array.from({length:30},(_,i)=>chooseCompanionScene([a,b],{...common,now:300000+i*60000,affection:true,romance:true})?.action)
   expect(withLove).toContain('hug')
   expect(withLove).toContain('kiss')
   const noKisses=Array.from({length:30},(_,i)=>chooseCompanionScene([a,b],{...common,now:300000+i*60000,affection:true,romance:false})?.action)
   expect(noKisses).not.toContain('kiss')
 })
})
