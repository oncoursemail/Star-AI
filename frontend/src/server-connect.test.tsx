import {readFileSync} from 'node:fs'
import {describe,it,expect} from 'vitest'

const source=(path:string)=>readFileSync(new URL(path,import.meta.url),'utf8')

describe('guided STAR Server connection',()=>{
  it('detects a key file via a native-only status action and explicitly imports it',()=>{
    const panel=source('./IntegrationPanels.tsx')
    expect(panel).toContain("invoke('serverKeyFileStatus')")
    expect(panel).toContain("invoke('importServerKeyFile')")
    expect(panel).toContain('A server key file was found on this PC')
    expect(panel).toContain('Use it')
    expect(panel).not.toContain('server_api_key')
  })
  it('keeps the existing provider until a full server test succeeds',()=>{
    const panel=source('./IntegrationPanels.tsx')
    expect(panel).toContain("if(!report?.ok||draft.provider==='star_server')return")
    expect(panel).toContain("const next={...draft,provider:'star_server'}")
    expect(panel).toContain("if(e.target.value==='star_server'){setConnecting(true)}")
  })
  it('registers native actions with nonsecret replies',()=>{
    const native=source('../../star/react_shell.py')
    const importer=source('../../star/server_key_file.py')
    expect(native).toContain("action=='serverKeyFileStatus'")
    expect(native).toContain("action=='importServerKeyFile'")
    expect(importer).toContain("return {'connected': True}")
  })
})
