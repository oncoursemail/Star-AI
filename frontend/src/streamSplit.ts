/**
 * A streaming answer re-renders on every delta. Splitting it at the last finished block lets the
 * finished part keep one memoized Markdown render while only the live tail is parsed again,
 * instead of re-parsing the whole growing answer each time (proposal #325 item 7).
 *
 * The cut is the start of the last blank line that is outside a code fence and has text after it,
 * so `done + live === text` always. The final answer is still rendered whole once it completes.
 */
export function splitStreaming(text: string): [string, string] {
  let cut = -1
  let inFence = false
  let offset = 0
  const lines = text.split('\n')
  let lastText = lines.length - 1
  while (lastText >= 0 && lines[lastText].trim() === '') lastText--
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]
    if (/^ {0,3}(```|~~~)/.test(line)) inFence = !inFence
    else if (!inFence && line.trim() === '' && index > 0 && index < lastText) {
      // Start of this blank line, minus the newline that ended the previous line.
      cut = offset - 1
    }
    offset += line.length + 1
  }
  return cut > 0 ? [text.slice(0, cut), text.slice(cut)] : ['', text]
}
