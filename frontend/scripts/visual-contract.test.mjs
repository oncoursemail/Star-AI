import {describe, expect, it} from 'vitest'
import {auditLayoutSnapshot} from './visual-contract.mjs'

const base = (controls = [], extra = {}) => ({
  viewport: {width:390, height:844}, documentWidth:390, controls, ...extra
})
const control = (id, x, y, width=100, height=44, extra={}) => ({
  id, role:'button', label:id, rect:{x,y,width,height},
  ancestors:[], visible:true, ...extra
})

describe('actual-render snapshot geometry contract', () => {
  it('reports a clean screen without claiming artistic quality', () => {
    const result = auditLayoutSnapshot(base([
      control('send', 200, 700), control('cancel', 80, 700),
    ]))
    expect(result.issues).toEqual([])
    expect(result.status).toContain('no_issues')
    expect(result.limitations).toMatch(/Geometry heuristics/)
    expect(result.inspectedControls).toBe(2)
  })

  it('catches overlapping sibling interactive controls', () => {
    const found = auditLayoutSnapshot(base([
      control('send', 100, 100, 80, 50),
      control('delete', 140, 100, 80, 50),
    ]))
    expect(found.issues.map(row => row.type)).toContain('interactive-overlap')
    const issue = found.issues.find(row => row.type === 'interactive-overlap')
    expect(issue.severity).toBe('error')
    expect(issue.elements).toEqual(['send', 'delete'])
  })

  it('does not confuse a nested control with sibling collision', () => {
    const result = auditLayoutSnapshot(base([
      control('outer', 100, 100, 200, 90),
      control('inner', 120, 115, 45, 45, {ancestors:['outer']}),
    ]))
    expect(result.issues.filter(row => row.type === 'interactive-overlap')).toEqual([])
  })

  it('reports horizontal overflow, missing button label, small target and text clipping', () => {
    const result = auditLayoutSnapshot(base([
      control('tiny', 20, 20, 18, 18, {label:'', textClipped:true}),
    ], {documentWidth:470}))
    expect(new Set(result.issues.map(row => row.type))).toEqual(new Set([
      'horizontal-overflow', 'small-interactive-target', 'clipped-control-label',
      'unlabeled-control',
    ]))
  })

  it('ignores intentionally offscreen controls in overlap/touch checks', () => {
    const result = auditLayoutSnapshot(base([
      control('drawer-hidden', -400, 10, 60, 60),
      control('offscreen-below', 20, 1100, 10, 12),
    ]))
    expect(result.issues).toEqual([])
  })

  it('refuses malformed and oversized snapshots', () => {
    expect(() => auditLayoutSnapshot({})).toThrow(TypeError)
    expect(() => auditLayoutSnapshot(base(Array.from({length:801}, (_,i) =>
      control(String(i), 0, 0))))).toThrow(TypeError)
    expect(() => auditLayoutSnapshot({viewport:{width:50,height:50},controls:[]}))
      .toThrow(TypeError)
  })
})
