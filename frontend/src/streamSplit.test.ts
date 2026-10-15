import {describe, expect, it} from 'vitest'
import {splitStreaming} from './streamSplit'

describe('splitStreaming: finished blocks of a streaming answer', () => {
  it('keeps everything live until the first paragraph is finished', () => {
    expect(splitStreaming('Hello wor')).toEqual(['', 'Hello wor'])
    expect(splitStreaming('Line one\nline two')).toEqual(['', 'Line one\nline two'])
  })

  it('cuts at the last blank line, and the two parts are the whole text', () => {
    const text = 'First paragraph.\n\nSecond paragraph.\n\nThird is still gro'
    const [done, live] = splitStreaming(text)
    expect(done).toBe('First paragraph.\n\nSecond paragraph.')
    expect(done + live).toBe(text)
    expect(live.trim()).toBe('Third is still gro')
  })

  it('never cuts inside an open code fence', () => {
    const text = 'Intro.\n\n```lua\nlocal a = 1\n\nlocal b = 2'
    expect(splitStreaming(text)).toEqual(['Intro.', '\n\n```lua\nlocal a = 1\n\nlocal b = 2'])
  })

  it('cuts after a closed code fence', () => {
    const text = '```lua\nlocal a = 1\n\nlocal b = 2\n```\n\nNow the expla'
    const [done, live] = splitStreaming(text)
    expect(done).toBe('```lua\nlocal a = 1\n\nlocal b = 2\n```')
    expect(live).toBe('\n\nNow the expla')
  })

  it('treats ~~~ fences and indented fences like ``` fences', () => {
    expect(splitStreaming('~~~\na\n\nb')[0]).toBe('')
    expect(splitStreaming('  ```\na\n\nb')[0]).toBe('')
  })

  it('does not cut on a trailing blank line that has nothing after it yet', () => {
    expect(splitStreaming('Only paragraph.\n\n')).toEqual(['', 'Only paragraph.\n\n'])
  })
})
