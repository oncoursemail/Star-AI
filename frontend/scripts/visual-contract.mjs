/**
 * STAR visual-contract evaluator: deterministic geometry checks, NOT an aesthetic score.
 * Runs on snapshots taken from an actual rendered browser. Independent of Playwright,
 * network access, source edits and the Qt desktop application.
 */
const finite = v => typeof v === 'number' && Number.isFinite(v)

function normalBox(rect) {
  if (!rect || ![rect.x, rect.y, rect.width, rect.height].every(finite) ||
      rect.width <= 0 || rect.height <= 0) return null
  return rect
}

export function auditLayoutSnapshot(input) {
  if (!input || !input.viewport || !finite(input.viewport.width) ||
      !finite(input.viewport.height) || input.viewport.width < 240 ||
      input.viewport.height < 240 || !Array.isArray(input.controls) ||
      input.controls.length > 800) throw new TypeError('Invalid or oversized visual snapshot')

  const viewport = input.viewport
  const issues = []
  const add = (type, severity, ids, detail) =>
    issues.push({type, severity, elements: ids, detail})

  if (finite(input.documentWidth) && input.documentWidth > viewport.width + 3) {
    add('horizontal-overflow', 'error', [], 
      'Document exceeds viewport by ' + Math.round(input.documentWidth - viewport.width) + ' px')
  }
  const controls = input.controls.filter(item =>
    item && typeof item.id === 'string' && item.id.length <= 100 &&
    item.visible !== false && normalBox(item.rect))
  for (const item of controls) {
    const rect = item.rect
    // Not every element outside the visible screen is broken: scroll containers
    // and the collapsed sidebar intentionally keep nodes offscreen.
    if (rect.x + rect.width <= 0 || rect.x >= viewport.width ||
        rect.y + rect.height <= 0 || rect.y >= viewport.height) continue

    if ((rect.width < 24 || rect.height < 24) && item.role !== 'link-inline') {
      add('small-interactive-target', 'warning', [item.id],
          'Interactive target below 24 x 24 CSS px; verify pointer/touch access')
    }
    if (item.textClipped === true) {
      add('clipped-control-label', 'warning', [item.id],
          'Control text overflows its rendered box without a deliberate ellipsis')
    }
    if (item.role === 'button' && !String(item.label || '').trim()) {
      add('unlabeled-control', 'error', [item.id],
          'Visible button has no accessible name; verify with axe and keyboard')
    }
  }
  const MAX_PAIRS = 25_000
  let pairs = 0
  for (let i = 0; i < controls.length; i++) {
    const a = controls[i]
    const x = a.rect
    for (let j = i + 1; j < controls.length && pairs < MAX_PAIRS; j++) {
      pairs++
      const b = controls[j]
      const y = b.rect
      // A nested interactive element is an accessibility problem, but should
      // not be misclassified as two sibling controls overlapping.
      if ((a.ancestors || []).includes(b.id) ||
          (b.ancestors || []).includes(a.id)) continue
      // Evaluate only substantial overlaps actually within the viewport.
      const left = Math.max(x.x, y.x, 0)
      const top = Math.max(x.y, y.y, 0)
      const right = Math.min(x.x + x.width, y.x + y.width, viewport.width)
      const bottom = Math.min(x.y + x.height, y.y + y.height, viewport.height)
      if (right <= left || bottom <= top) continue
      const overlap = (right - left) * (bottom - top)
      const smaller = Math.min(x.width * x.height, y.width * y.height)
      if (overlap >= 70 && overlap / smaller > 0.4) {
        add('interactive-overlap', 'error', [a.id, b.id],
            'Rendered interactive targets substantially overlap (' +
            Math.round(overlap / smaller * 100) + '% of smaller target)')
      }
    }
  }

  return {
    status: issues.length ? 'issues_found' : 'no_issues_detected_in_measured_checks',
    measured: ['horizontal-overflow', 'interactive-overlap', 'unlabeled-control',
               'small-interactive-target', 'clipped-control-label'],
    viewport,
    inspectedControls: controls.length,
    issues,
    // This report does not verify visual appeal, interactions, a11y, Qt WebEngine,
    // Roblox Studio, or that any asset/code change is editable or performant.
    limitations: 'Geometry heuristics only; review screenshots and run native application tests.',
  }
}
