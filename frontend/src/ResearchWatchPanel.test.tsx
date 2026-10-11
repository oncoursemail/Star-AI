// @vitest-environment jsdom
/** Research Watch is an actual desktop bridge view, not fabricated preview metrics. */
import {afterEach,beforeAll,beforeEach,describe,expect,it,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {initializeBridge} from './bridge'
import {installFakeDesktop,type FakeDesktop} from './fake-desktop'
import {ResearchWatchPanel} from './ResearchWatchPanel'

let desktop:FakeDesktop
beforeAll(async()=>{desktop=installFakeDesktop();await initializeBridge()})
beforeEach(()=>desktop.reset())
afterEach(cleanup)

const source={
  source_id:'roblox-studio-mcp',
  url:'https://create.roblox.com/docs/studio/mcp',
  last_digest:null,checked_at:null,last_outcome:'never',error_code:'',
}
const initial={
  sources:[source],observations:[],candidate_count:0,
  trusted_automatically:0,can_publish:false,
}

describe('Research Watch candidate evidence',()=>{
  it('shows actual host state and only checks sources on the owner click',async()=>{
    let reported:object={...initial}
    desktop.onAction('researchStatus',()=>({ok:true,data:reported}))
    desktop.onAction('researchCheck',()=>({ok:true,pending:true}))
    desktop.onAction('researchEvidence',call=>({ok:true,data:{
      id:call.payload.observation,source_id:source.source_id,url:source.url,
      previous_digest:null,digest:'abc123',observed_at:'2026-10-11T16:00:00Z',
      status:'candidate',excerpt:'The official docs discuss read-only Studio inspections.',
      untrusted_reference_only:true,can_grant_permissions:false,
    }}))
    desktop.onAction('researchNominate',call=>({ok:true,data:{
      lesson_id:9,status:'candidate',reason:'',observation:call.payload.observation,
    }}))
    const user=userEvent.setup()
    render(<ResearchWatchPanel/>)
    expect(await screen.findByText('No research snapshots are recorded on this device yet.')).toBeTruthy()
    expect(desktop.sent('researchCheck')).toHaveLength(0)
    await user.click(screen.getByRole('button',{name:'Check official sources'}))
    await waitFor(()=>expect(desktop.sent('researchCheck')).toHaveLength(1))
    reported={
      ...initial,
      sources:[{...source,last_digest:'abc123',last_outcome:'baseline'}],
      candidate_count:1,
      observations:[{id:7,source_id:source.source_id,previous_digest:null,
        digest:'abc123',observed_at:'2026-10-11T16:00:00Z',status:'candidate' as const}],
    }
    desktop.emitRaw(desktop.requestOf('researchCheck'),'result',[{outcome:'baseline'}])
    expect(await screen.findByText('1 pending review')).toBeTruthy()
    await user.click(screen.getByRole('button',{name:'Inspect'}))
    expect(await screen.findByText('The official docs discuss read-only Studio inspections.')).toBeTruthy()
    expect(desktop.sent('researchEvidence')[0].payload).toEqual({observation:7})
    expect(screen.getByText(/Not approved as fact/)).toBeTruthy()
    expect(screen.getByText('Off')).toBeTruthy()
    await user.click(screen.getByRole('button',{name:'Send candidate to Learning review'}))
    expect(await screen.findByText(/Candidate added to Projects/)).toBeTruthy()
    expect(desktop.sent('researchNominate')[0].payload).toEqual({observation:7})
  })

  it('starts with background research off and only enables via owner setting',async()=>{
    const onChange=vi.fn()
    desktop.onAction('researchStatus',()=>({ok:true,data:initial}))
    const user=userEvent.setup()
    const {rerender}=render(<ResearchWatchPanel autoCheck={false} onAutoChange={onChange}/>)
    const checkbox=screen.getByRole('checkbox',{name:'Daily automatic research'})
    expect((checkbox as HTMLInputElement).checked).toBe(false)
    expect(desktop.sent('researchCheck')).toHaveLength(0)
    await user.click(checkbox)
    expect(onChange).toHaveBeenCalledWith(true)
    expect(desktop.sent('researchCheck')).toHaveLength(0)
    rerender(<ResearchWatchPanel autoCheck={true} onAutoChange={onChange}/>)
    expect((screen.getByRole('checkbox',{name:'Daily automatic research'}) as HTMLInputElement).checked).toBe(true)
  })

  it('does not connect to public docs in the inactive website preview',async()=>{
    render(<ResearchWatchPanel disabled/>)
    expect(screen.getByRole('button',{name:'Check official sources'}).hasAttribute('disabled')).toBe(true)
    expect(desktop.sent('researchStatus')).toHaveLength(0)
  })

  it('shows host-side refusal without inventing a successful check',async()=>{
    desktop.onAction('researchStatus',()=>({ok:true,data:initial}))
    desktop.onAction('researchCheck',()=>({ok:false,error:'Research check unavailable'}))
    const user=userEvent.setup()
    render(<ResearchWatchPanel/>)
    await screen.findByText('No research snapshots are recorded on this device yet.')
    await user.click(screen.getByRole('button',{name:'Check official sources'}))
    expect(await screen.findByRole('status')).toHaveProperty('textContent','Research check unavailable')
  })
})
