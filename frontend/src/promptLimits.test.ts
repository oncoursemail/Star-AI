import {describe,expect,it} from 'vitest'
import {PROMPT_LIMITS,overLimitMessage,promptKind,promptLength} from './promptLimits'

describe('prompt limits',()=>{
 it('counts trimmed code points like Python len(str.strip())',()=>{
  expect(promptLength('  hi  ')).toBe(2)
  expect(promptLength('\u{1F600}\u{1F600}')).toBe(2)
  expect(promptLength('')).toBe(0)
 })
 it('picks the request kind the host will check',()=>{
  expect(promptKind(false,false)).toBe('chat')
  expect(promptKind(false,true)).toBe('team')
  expect(promptKind(true,false)).toBe('image')
  expect(promptKind(true,true)).toBe('image')
 })
 it('reports only prompts over the limit, with the amount',()=>{
  expect(overLimitMessage('a'.repeat(PROMPT_LIMITS.chat),'chat')).toBeNull()
  expect(overLimitMessage(' '+'a'.repeat(PROMPT_LIMITS.chat)+'  ','chat')).toBeNull()
  expect(overLimitMessage('a'.repeat(PROMPT_LIMITS.team+2500),'team')).toBe('Too long for a team objective: 2,500 characters over the 12,000 limit. Shorten it, or turn Team off to send it as a chat message.')
 })
})
