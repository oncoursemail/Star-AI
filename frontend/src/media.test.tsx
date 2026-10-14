// @vitest-environment jsdom
/**
 * Media in the interface: the "where STAR generates" choices, a project's visual references,
 * and creating or changing a picture from the composer.
 *
 * Contract under test: what the page sends to the desktop host (`saveSettings`, `mediaStartComfy`,
 * `pinReference`, `compareReference`, `generateImage` with its picture, mask and size) and the text
 * the owner reads. Speeds and reasons are the host's words; the page must show them unchanged.
 */
import {afterEach, beforeAll, beforeEach, describe, expect, it, vi} from 'vitest'
import {cleanup, render, screen, waitFor, within} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {App} from './App'
import {MediaPlaces, ReferencesPanel} from './MediaPanel'
import {backendSettings, installFakeDesktop, type FakeDesktop} from './fake-desktop'
import type {AppSettings, MediaReference, MediaStatus} from './types'

let desktop: FakeDesktop
beforeAll(async () => { desktop = installFakeDesktop(); await import('./Desktop') }, 60_000)
beforeEach(() => desktop.reset())
afterEach(cleanup)

const settings = backendSettings as unknown as AppSettings
const status = (over: Partial<MediaStatus> = {}): MediaStatus => ({
  places: [
    {id: 'images', title: 'Images', field: 'media_images', chosen: 'pc', options: [
      {id: 'servers', label: 'STAR Brains (servers)', available: false, fixable: false, note: '', reason: 'Not available: no image model is installed on the servers, and they have no graphics card. Estimated at 8 to 25 minutes.'},
      {id: 'pc', label: 'This PC (your GPU)', available: true, note: 'Measured on this PC (RTX 3060 Ti, 8 GB, 2026-10-11): 1024x1024 in 6.8 s.', reason: ''}]},
    {id: 'voice', title: 'Voice', field: 'media_voice', chosen: 'pc', options: [
      {id: 'servers', label: 'STAR Brains (servers)', available: false, fixable: false, note: '', reason: 'Not available: no speech recogniser or voice is installed on the servers.'},
      {id: 'pc', label: 'This PC (your GPU)', available: true, note: 'Speech recognition and Star\'s voice run on this PC.', reason: ''}]},
    {id: 'video', title: 'Video understanding', field: 'media_video', chosen: 'servers', options: [
      {id: 'servers', label: 'STAR Brains (servers)', available: true, note: 'Measured (2026-10-11): a 16 s clip, 4 frames plus its transcript, answered in 93 s.', reason: ''},
      {id: 'pc', label: 'This PC (your GPU)', available: true, note: 'The on-device brain reads the frames. Not measured yet on this PC.', reason: ''}]},
  ],
  images: {running: false, ready: false, missing: [], model: 'FLUX.2 klein 4B (distilled, fp8)', message: 'ComfyUI is not running on this PC (127.0.0.1:8188). Start it.'},
  sizes: [{id: 'square', label: 'Square 1024 x 1024'}], can_start: true, ffmpeg: {found: true, message: 'FFmpeg found.'},
  measured_on: '2026-10-11', references: 0, ...over})

function mediaHost(initial: MediaStatus) {
  let current = initial
  const calls: Array<{action: string; params: Record<string, unknown>}> = []
  const invoke = vi.fn(async (action: string, params: Record<string, unknown> = {}) => {
    calls.push({action, params})
    if (action === 'mediaStatus') return current
    if (action === 'saveSettings') return params.settings
    if (action === 'mediaStartComfy') { current = {...current, images: {...current.images, running: true, ready: true, version: '0.39.0', message: 'Ready.'}}; return {started: true, running: true, message: 'ComfyUI started on this PC (127.0.0.1 only).'} }
    if (action === 'mediaFreeMemory') return {freed: true}
    return {}
  })
  return {invoke, calls, sent: (action: string) => calls.filter(c => c.action === action)}
}

describe('where STAR generates', () => {
  it('shows the places for each capability, with the host\'s measured notes and reasons unchanged', async () => {
    const host = mediaHost(status())
    render(<MediaPlaces settings={settings} invoke={host.invoke}/>)
    const video = await screen.findByRole('radiogroup', {name: 'Video understanding'})
    expect(within(video).getAllByRole('radio')).toHaveLength(2)
    expect(screen.getByText(/Measured on this PC \(RTX 3060 Ti, 8 GB, 2026-10-11\): 1024x1024 in 6\.8 s\./)).toBeTruthy()
    expect(screen.getByText(/they have no graphics card\. Estimated at 8 to 25 minutes\./)).toBeTruthy()
    expect(screen.getByText(/answered in 93 s\./)).toBeTruthy()
  })

  it('states where images and voice run instead of offering a place this install can never use', async () => {
    const host = mediaHost(status())
    render(<MediaPlaces settings={settings} invoke={host.invoke}/>)
    for (const [name, reason] of [['Images', /no image model is installed on the servers/], ['Voice', /no speech recogniser or voice is installed/]] as const) {
      const group = await screen.findByRole('group', {name})
      expect(within(group).queryAllByRole('radio')).toHaveLength(0)
      expect(within(group).getByText('Runs on this PC (your GPU)')).toBeTruthy()
      expect(within(group).queryByText(/\(unavailable\)/)).toBeNull()
      // The reason is still there, one click away, in the host's own words.
      const why = within(group).getByText('Why not the STAR Brains?').closest('details') as HTMLDetailsElement
      expect(why.open).toBe(false)
      expect(within(why).getByText(reason)).toBeTruthy()
    }
    expect(screen.queryByRole('radiogroup', {name: 'Images'})).toBeNull()
  })

  it('still shows a place a setting could make available as unavailable, with its reason', async () => {
    const offline = status()
    offline.places[2].options[0] = {...offline.places[2].options[0], available: false, fixable: true, note: '', reason: 'Not available: no STAR Server is connected. Add its address and key in Settings → STAR Server.'}
    offline.places[2].chosen = 'pc'
    render(<MediaPlaces settings={settings} invoke={mediaHost(offline).invoke}/>)
    const video = await screen.findByRole('radiogroup', {name: 'Video understanding'})
    const [servers] = within(video).getAllByRole('radio') as HTMLInputElement[]
    expect(servers.disabled).toBe(true)
    expect(within(video).getByText(/no STAR Server is connected/)).toBeTruthy()
  })

  it('does not let an unavailable place be chosen (a host that does not say whether it can be fixed)', async () => {
    const older = status()
    for (const place of older.places) for (const option of place.options) delete option.fixable
    const host = mediaHost(older)
    render(<MediaPlaces settings={settings} invoke={host.invoke}/>)
    const images = await screen.findByRole('radiogroup', {name: 'Images'})
    const [servers, pc] = within(images).getAllByRole('radio') as HTMLInputElement[]
    expect(servers.disabled).toBe(true)
    expect(pc.checked).toBe(true)
    expect(within(images).getByText(/STAR Brains \(servers\) \(unavailable\)/)).toBeTruthy()
    await userEvent.setup().click(servers)
    expect(host.sent('saveSettings')).toHaveLength(0)
  })

  it('saves the chosen place for one capability only', async () => {
    const host = mediaHost(status())
    const user = userEvent.setup()
    render(<MediaPlaces settings={settings} invoke={host.invoke}/>)
    const video = await screen.findByRole('radiogroup', {name: 'Video understanding'})
    await user.click(within(video).getAllByRole('radio')[1])
    await waitFor(() => expect(host.sent('saveSettings')).toHaveLength(1))
    expect(host.sent('saveSettings')[0].params).toEqual({settings: {media_video: 'pc'}})
  })

  it('says a saved but unavailable choice will stop with its reason', async () => {
    const stuck = status()
    stuck.places[0].chosen = 'servers'
    render(<MediaPlaces settings={settings} invoke={mediaHost(stuck).invoke}/>)
    expect(await screen.findByText(/The chosen place is not available, so images will stop with that explanation/)).toBeTruthy()
  })

  it('shows the image engine state, starts ComfyUI and frees graphics memory', async () => {
    const host = mediaHost(status())
    const user = userEvent.setup()
    render(<MediaPlaces settings={settings} invoke={host.invoke}/>)
    expect(await screen.findByText(/ComfyUI is not running on this PC \(127\.0\.0\.1:8188\)/)).toBeTruthy()
    await user.click(screen.getByRole('button', {name: /start comfyui/i}))
    await waitFor(() => expect(host.sent('mediaStartComfy')).toHaveLength(1))
    expect(await screen.findByText(/Ready: FLUX\.2 klein 4B \(distilled, fp8\) on ComfyUI 0\.39\.0\./)).toBeTruthy()
    await user.click(screen.getByRole('button', {name: /free graphics memory/i}))
    expect(await screen.findByText(/the graphics memory is free again/)).toBeTruthy()
  })

  it('cannot start ComfyUI before its folder is set', async () => {
    render(<MediaPlaces settings={settings} invoke={mediaHost(status({can_start: false})).invoke}/>)
    const start = await screen.findByRole('button', {name: /start comfyui/i}) as HTMLButtonElement
    expect(start.disabled).toBe(true)
    expect(start.title).toMatch(/Set the ComfyUI folder/)
  })

  it('says which ComfyUI folder it found on its own, and lets the owner start it', async () => {
    render(<MediaPlaces settings={settings} invoke={mediaHost(status({can_start: true, detected_home: 'C:/Projects/media/ComfyUI'})).invoke}/>)
    expect(await screen.findByText(/Found automatically: C:\/Projects\/media\/ComfyUI/)).toBeTruthy()
    expect((screen.getByRole('button', {name: /start comfyui/i}) as HTMLButtonElement).disabled).toBe(false)
  })

  it('saves the picture size the brain reads and the references switch', async () => {
    const host = mediaHost(status())
    const user = userEvent.setup()
    render(<MediaPlaces settings={settings} invoke={host.invoke}/>)
    await user.selectOptions(await screen.findByRole('combobox', {name: /picture size the brain reads/i}), '1024')
    await user.click(screen.getByRole('checkbox', {name: /use this project's visual references/i}))
    await waitFor(() => expect(host.sent('saveSettings')).toHaveLength(2))
    expect(host.sent('saveSettings').map(call => call.params.settings)).toEqual([{picture_max_side: 1024}, {media_use_references: false}])
  })
})

const reference = (over: Partial<MediaReference> = {}): MediaReference => ({
  id: 'aaaaaaaaaaaa', label: 'Main menu', note: 'approved', width: 1280, height: 720, added: '2026-10-11T06:00:00Z',
  preview: 'data:image/webp;base64,AAAA', ...over})

function referenceHost(initial: MediaReference[], compare: Record<string, unknown> | null = null) {
  let items = initial.slice()
  const calls: Array<{action: string; params: Record<string, unknown>}> = []
  const invoke = vi.fn(async (action: string, params: Record<string, unknown> = {}) => {
    calls.push({action, params})
    if (action === 'listReferences') return {references: items, limit: 12, enabled: true}
    if (action === 'pickFiles') return ['C:/art/shop-ui.png']
    if (action === 'pinReference') { items = [...items, reference({id: 'bbbbbbbbbbbb', label: 'shop-ui'})]; return {pinned: 'bbbbbbbbbbbb', references: items} }
    if (action === 'unpinReference') { items = items.filter(item => item.id !== params.id); return {removed: true, references: items} }
    if (action === 'compareReference') return compare
    return {}
  })
  return {invoke, calls, sent: (action: string) => calls.filter(c => c.action === action)}
}

describe('visual references', () => {
  it('pins an image the owner picked to the current project', async () => {
    const host = referenceHost([])
    const user = userEvent.setup()
    render(<ReferencesPanel project="Island Shop" invoke={host.invoke}/>)
    expect(await screen.findByText(/No references yet for this project/)).toBeTruthy()
    await user.click(screen.getByRole('button', {name: /pin an image/i}))
    await waitFor(() => expect(host.sent('pinReference')).toHaveLength(1))
    expect(host.sent('pickFiles')[0].params).toEqual({kind: 'image'})
    expect(host.sent('pinReference')[0].params).toEqual({file: 'C:/art/shop-ui.png'})
    expect(await screen.findByText(/1 reference pinned to Island Shop/)).toBeTruthy()
    expect(screen.getByRole('img', {name: 'Reference: shop-ui'})).toBeTruthy()
  })

  it('compares the latest image with a reference and lists the differences beside the measured facts', async () => {
    const host = referenceHost([reference()], {
      reference: {id: 'aaaaaaaaaaaa', label: 'Main menu'}, image: 'data:image/webp;base64,BBBB', saved: '20261011T060000-aaaaaaaaaaaa.png',
      candidate: 'star-20261011-060000-00001.png', differences: ['The title is centred instead of left.', 'The Play button is blue, not gold.'],
      measured: {lines: ['The output is 12% darker overall (average colour #202020 against #404040).']}, model: 'star-vision', seconds: 51.9, model_error: ''})
    const user = userEvent.setup()
    render(<ReferencesPanel project="Island Shop" invoke={host.invoke}/>)
    await user.click(await screen.findByRole('button', {name: /compare latest image/i}))
    const result = await screen.findByLabelText('Comparison with the reference')
    expect(host.sent('compareReference')[0].params).toEqual({id: 'aaaaaaaaaaaa'})
    expect(within(result).getByText('The title is centred instead of left.')).toBeTruthy()
    expect(within(result).getByText('The Play button is blue, not gold.')).toBeTruthy()
    expect(within(result).getByText(/The output is 12% darker overall/)).toBeTruthy()
    expect(within(result).getByText(/star-vision, 51\.9 s/)).toBeTruthy()
    expect(within(result).getByRole('img').getAttribute('alt')).toMatch(/Reference Main menu beside STAR's output/)
  })

  it('keeps the measured facts and says so when the vision model cannot be asked', async () => {
    const host = referenceHost([reference()], {
      reference: {id: 'aaaaaaaaaaaa', label: 'Main menu'}, image: 'data:image/webp;base64,BBBB', saved: 'x.png', candidate: 'out.png',
      differences: [], measured: {lines: ['Shape differs: the reference is 1280x720 (ratio 1.78), the output is 1024x1024 (ratio 1.00).']},
      model: '', seconds: 0, model_error: 'APIConnectionError: Connection error.'})
    const user = userEvent.setup()
    render(<ReferencesPanel project="Island Shop" invoke={host.invoke}/>)
    await user.click(await screen.findByRole('button', {name: /compare latest image/i}))
    expect(await screen.findByText(/The vision model could not be asked \(APIConnectionError: Connection error\.\)/)).toBeTruthy()
    expect(screen.getByText(/Shape differs: the reference is 1280x720/)).toBeTruthy()
  })

  it('removes a reference only after a second, explicit click', async () => {
    const host = referenceHost([reference()])
    const user = userEvent.setup()
    render(<ReferencesPanel project="Island Shop" invoke={host.invoke}/>)
    await user.click(await screen.findByRole('button', {name: 'Remove reference Main menu'}))
    expect(host.sent('unpinReference')).toHaveLength(0)
    await user.click(screen.getByRole('button', {name: /remove for good/i}))
    await waitFor(() => expect(host.sent('unpinReference')).toHaveLength(1))
    expect(await screen.findByText(/Your own file was not touched/)).toBeTruthy()
  })
})

describe('creating and changing a picture from the composer', () => {
  const composer = () => screen.getByRole('textbox', {name: /message star/i})
  async function openImageMode() {
    const user = userEvent.setup()
    render(<App/>)
    await screen.findByRole('textbox', {name: /message star/i})
    await waitFor(() => expect(desktop.sent('bootstrap').length).toBeGreaterThan(0))
    await user.click(screen.getByRole('button', {name: /add files and tools/i}))
    await user.click(await screen.findByRole('menuitemcheckbox', {name: /create image/i}))
    return user
  }

  it('creates an image with no workflow file configured, at the chosen size', async () => {
    const user = await openImageMode()
    await user.selectOptions(screen.getByRole('combobox', {name: /image size/i}), 'wide')
    await user.type(composer(), 'a lighthouse at dusk')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(desktop.sent('generateImage')).toHaveLength(1))
    expect(desktop.sent('generateImage')[0].payload).toEqual({prompt: 'a lighthouse at dusk', files: [], size: 'wide'})
  })

  it('sends an attached picture and its mask with the instruction', async () => {
    const picked = [['C:/art/room.png'], ['C:/art/room-mask.png']]
    desktop.onAction('pickFiles', () => ({ok: true, data: picked.shift() || []}))
    const user = await openImageMode()
    await user.click(screen.getByRole('button', {name: /attach a picture to edit it/i}))
    await user.click(await screen.findByRole('button', {name: /add a mask/i}))
    await waitFor(() => expect(desktop.sent('pickFiles')).toHaveLength(2))
    expect(desktop.sent('pickFiles').every(call => call.payload.kind === 'image')).toBe(true)
    await waitFor(() => expect((composer() as HTMLTextAreaElement).placeholder).toMatch(/masked area/))
    await user.type(composer(), 'a red door with a round window')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(desktop.sent('generateImage')).toHaveLength(1))
    expect(desktop.sent('generateImage')[0].payload).toEqual({
      prompt: 'a red door with a round window', files: ['C:/art/room.png', 'C:/art/room-mask.png'], size: 'square'})
  })

  it('offers "Set up image creation" only when the host says no picture can be made yet', async () => {
    // Not running, and no ComfyUI folder to start it from: the same case the host refuses before generating.
    desktop.onAction('mediaStatus', () => ({ok: true, data: status({can_start: false})}))
    const user = await openImageMode()
    await waitFor(() => expect(desktop.sent('mediaStatus').length).toBeGreaterThan(0))
    const setup = await screen.findByRole('button', {name: /set up image creation/i})
    await user.click(setup)
    expect((await screen.findAllByRole('heading', {name: 'Settings', level: 1})).length).toBeGreaterThan(0)
    expect(desktop.sent('generateImage')).toHaveLength(0)
  })

  it('does not offer setup when ComfyUI can be started or is ready', async () => {
    desktop.onAction('mediaStatus', () => ({ok: true, data: status({can_start: true})}))
    await openImageMode()
    await waitFor(() => expect(desktop.sent('mediaStatus').length).toBeGreaterThan(0))
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(screen.queryByRole('button', {name: /set up image creation/i})).toBeNull()
  })

  it('reads a slow answer from the host too (the status arrives as an event)', async () => {
    desktop.onAction('mediaStatus', () => ({ok: true, pending: true}))
    await openImageMode()
    await waitFor(() => expect(desktop.sent('mediaStatus').length).toBeGreaterThan(0))
    expect(screen.queryByRole('button', {name: /set up image creation/i})).toBeNull()
    const missing = status({images: {running: true, ready: false, missing: ['flux-2-klein-4b-fp8.safetensors'], model: 'FLUX.2 klein', message: 'ComfyUI is running but model files are missing'}})
    await desktop.emitRaw(desktop.requestOf('mediaStatus'), 'result', missing)
    expect(await screen.findByRole('button', {name: /set up image creation/i})).toBeTruthy()
  })

  it('shows the host\'s own explanation when the image engine is not running', async () => {
    const user = await openImageMode()
    await user.type(composer(), 'a teapot')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(desktop.sent('generateImage')).toHaveLength(1))
    const reason = 'ComfyUI is not running on this PC (127.0.0.1:8188). Start it in Settings → Where STAR generates → Start ComfyUI (or run scripts/media/start_comfyui.sh), then try again.'
    await desktop.fail(desktop.requestOf('generateImage'), reason)
    expect(await screen.findByText(reason)).toBeTruthy()
  })
})
