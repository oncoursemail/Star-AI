import {describe,it,expect} from 'vitest'
import {blankTrend,examples,WEBSITE_RELEASES} from './constants'

describe('STAR interface data',()=>{
 it('uses real release destination for anonymous installers',()=>{expect(WEBSITE_RELEASES).toBe('https://github.com/oncoursemail/Star-AI/releases/latest')})
 it('has honest blank trend data',()=>{const trend=blankTrend();expect(trend).toHaveLength(14);expect(trend.every(x=>x.runs===0)).toBe(true)})
 it('keeps sample prompts read-only',()=>{expect(examples.length).toBeGreaterThanOrEqual(3);expect(examples.every(x=>x.prompt.length>20)).toBe(true)})
})
