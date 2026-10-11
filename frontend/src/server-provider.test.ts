import {readFileSync} from 'node:fs'
import {describe,expect,it} from 'vitest'
import {createElement} from 'react'
import {renderToStaticMarkup} from 'react-dom/server'
import {ServerRoles,brainStatus,formatStepTime,runsOnOwnHardware,usesStarServer} from './IntegrationPanels'
import type {AppSettings,ServerReport,ServerStatus} from './types'

const source=(name:string)=>readFileSync(new URL(name,import.meta.url),'utf8')
const status=(ok:boolean|null):ServerStatus=>({selected:true,configured:true,key_present:true,model_selected:true,ok,code:ok?'ok':'',checked_at:''})

describe('STAR Server provider helpers',()=>{
 it('treats the LAN server as private hardware and never as a cloud vendor',()=>{
  expect(usesStarServer({provider:'star_server'})).toBe(true)
  expect(usesStarServer({provider:'local'})).toBe(false)
  expect(usesStarServer(null)).toBe(false)
  expect(runsOnOwnHardware({provider:'local'})).toBe(true)
  expect(runsOnOwnHardware({provider:'star_server'})).toBe(true)
  for(const cloud of ['groq','openrouter','gemini','cerebras'])expect(runsOnOwnHardware({provider:cloud})).toBe(false)
 })
 it('never reports a selected server as an offline local brain',()=>{
  expect(brainStatus({settings:{provider:'local'},brain_running:false})).toEqual({online:false,label:'STAR Brain offline'})
  expect(brainStatus({settings:{provider:'local'},brain_running:true})).toEqual({online:true,label:'STAR Brain ready'})
  expect(brainStatus({settings:{provider:'star_server'},brain_running:false,server:status(true)})).toEqual({online:true,label:'STAR Server ready'})
  expect(brainStatus({settings:{provider:'star_server'},brain_running:false,server:status(false)})).toEqual({online:false,label:'STAR Server needs attention'})
  // Not checked yet is neutral: it is neither "offline" nor a prompt to download a model.
  expect(brainStatus({settings:{provider:'star_server'},brain_running:false,server:status(null)})).toEqual({online:false,label:'STAR Server selected'})
  expect(brainStatus({settings:{provider:'star_server'},brain_running:true}).label).toBe('STAR Server selected')
 })
 it('lists the models by job only once the server or the owner chose one',()=>{
  const html=(roles?:ServerStatus['roles'])=>renderToStaticMarkup(createElement(ServerRoles,{roles}))
  expect(html(undefined)).toBe('')
  expect(html([{role:'quick',label:'Quick chat',model:'star-fast',source:'default'}])).toBe('')
  const shown=html([
   {role:'quick',label:'Quick chat',model:'my-quick',source:'manual'},
   {role:'code',label:'Roblox, code and tools',model:'star-fast',source:'server'},
   {role:'deep',label:'Best quality (slow, on request)',model:'star-deep',source:'server'}])
  expect(shown).toContain('Quick chat: my-quick (set by you)')
  expect(shown).toContain('Roblox, code and tools: star-fast ·')
  expect(shown).toContain('/deep')
 })
 it('formats step timings for people',()=>{
  expect(formatStepTime(6)).toBe('6 ms')
  expect(formatStepTime(999.4)).toBe('999 ms')
  expect(formatStepTime(1000)).toBe('1.0 s')
  expect(formatStepTime(35100)).toBe('35.1 s')
  expect(formatStepTime(-3)).toBe('0 ms')
 })
 it('keeps the server fields optional so saved settings from older builds still type-check',()=>{
  const older:AppSettings={endpoint:'http://127.0.0.1:8080/v1',provider:'star_server',model:'',fast_model:'',reasoning_model:'',roblox_model:'',vision_model:'',router_models_dir:'',router_context:4096,gpu_layers:25,project:'STAR',workspace:'',studio_id:'',studio_edit:false,workspace_edit:false,max_calls:12,context_chars:26000,reduced_motion:false,obsidian_vault:'',obsidian_enabled:false,skills_enabled:true,graphify_enabled:true,comfy_workflow:'',comfy_prompt_node:'6',comfy_port:8188,mcp_graphify_docs:false,mcp_graphify_local:false,mcp_graphify_port:8931,mcp_obsidian_live:false,roblox_research_enabled:true,tool_workshop_enabled:true,specialists_enabled:true,specialist_parallelism:1}
  expect(older.server_endpoint).toBeUndefined()
  const report:ServerReport={ok:false,code:'wrong_key',message:'x',steps:[{name:'health',status:'ok',ms:5,detail:'Server is up'}],models:[],model:'',context_tokens:null,slots:null,first_token_ms:null,sample:''}
  expect(Object.keys(report)).not.toContain('key')
 })
})

describe('STAR Server interface source',()=>{
 const panel=source('./IntegrationPanels.tsx')
 it('offers the provider, address, key and a Test server action',()=>{
  expect(panel).toContain("star_server:'STAR Server (LAN)'")
  expect(panel).toContain("invoke('testServer')")
  expect(panel).toContain('Test server')
  expect(panel).toContain('Server key (stored in Windows Credential Manager)')
  // An example address is placeholder text only; no address is a built-in value.
  expect(panel).toContain('placeholder="http://192.168.1.20:8080/v1"')
  expect(panel).not.toMatch(/server_endpoint\s*:\s*['"]http/)
  expect(source('./Desktop.tsx')).not.toContain('server_endpoint')
 })
 it('never holds the server key in React state',()=>{
  // The key input is uncontrolled: it is read once from the element and cleared.
  expect(panel).toContain("invoke('saveProviderKey',{provider:'star_server',key:field.value.trim()})")
  expect(panel).toContain("field.value='';setKeyTyped(false)")
  expect(panel).toMatch(/<input ref=\{keyInput\} type="password"/)
  const setup=panel.slice(panel.indexOf('function ServerSetup'),panel.indexOf('export function ServerBrainPanel'))
  expect(setup).not.toMatch(/useState<string>|setApiKey|value=\{[a-zA-Z]*[kK]ey[a-zA-Z]*\}/)
  expect(setup).not.toContain('localStorage')
 })
 it('does not ask a server user to download or start a local model',()=>{
  const brain=panel.slice(panel.indexOf('export function ServerBrainPanel'),panel.indexOf('export function ProviderPanel'))
  expect(brain).toContain('Nothing needs to be downloaded to this PC.')
  expect(brain).toContain('Optional: on-device backup brain')
  expect(brain).not.toMatch(/installBrain|startBrain|Download and start/)
  const desktop=source('./Desktop.tsx')
  expect(desktop).toContain('{serverMode&&<ServerBrainPanel')
  expect(desktop).toContain('<LocalBrainFallback optional={serverMode}>')
  expect(desktop).toContain('!runsOnOwnHardware(data.settings)')
  const fleet=source('./ModelFleetPanel.tsx')
  expect(fleet).toContain("const onServer=draft.provider==='star_server'")
  expect(fleet).toContain('STAR Server manages its own models.')
 })
})
