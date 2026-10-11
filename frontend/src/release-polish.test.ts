import {describe, expect, it} from 'vitest'
import {describeConnection} from './connection'
import {formatStepTime} from './IntegrationPanels'

describe('release polish', () => {
  it('offers both real recovery paths when the on-device brain is stopped', () => {
    const status = describeConnection({
      settings: {provider: 'local', model: 'test-model', endpoint: 'http://127.0.0.1:8080/v1'},
      brain: {online: false, label: 'STAR Brain offline'},
      ownHardware: true, credentials: {}, preview: false, last: null,
    })
    expect(status.state).toBe('Offline')
    expect(status.note).toContain('Model page')
    expect(status.note).toContain('STAR Server in Settings')
    expect(status.note).not.toContain('Brain tab')
  })

  it('expresses long first-word latency in seconds with one decimal', () => {
    expect(formatStepTime(157580)).toBe('157.6 s')
    expect(formatStepTime(1000)).toBe('1.0 s')
    expect(formatStepTime(850)).toBe('850 ms')
  })
})
