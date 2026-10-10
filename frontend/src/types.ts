export type Project = { name: string }
export type ChatMessage = { id: string; role: 'user'|'assistant'|'event'; text: string; created?: string; attachments?: string[]; image?: string; status?: 'failed'|'cancelled' }
/** The newest question that got no answer, as derived by the desktop host; survives restarts. */
export type RetryState = { status: 'failed'|'cancelled'|'interrupted'; detail: string; prompt: string; message_id: number; created: string }
export type AppSettings = { endpoint: string; provider: 'local'|'star_server'|'groq'|'openrouter'|'gemini'|'cerebras'; model: string; fast_model: string; reasoning_model: string; roblox_model: string; vision_model: string; router_models_dir: string; router_context: number; gpu_layers: number; project: string; workspace: string; studio_id: string; studio_edit: boolean; workspace_edit: boolean; max_calls: number; context_chars: number; reduced_motion: boolean; obsidian_vault: string; obsidian_enabled: boolean; skills_enabled: boolean; graphify_enabled: boolean; comfy_workflow: string; comfy_prompt_node: string; comfy_port: number; mcp_graphify_docs: boolean; mcp_graphify_local: boolean; mcp_graphify_port: number; mcp_obsidian_live: boolean; roblox_research_enabled: boolean; tool_workshop_enabled: boolean; specialists_enabled: boolean; specialist_parallelism: number; server_endpoint?: string; server_timeout?: number; server_parallel?: number; server_context_tokens?: number }
/** One timed step of the STAR Server check. The server key is never part of any report. */
export type ServerStep = { name:string; status:'ok'|'failed'|'skipped'; ms:number; detail:string }
export type ServerReport = { ok:boolean; code:string; message:string; steps:ServerStep[]; models:string[]; model:string; context_tokens:number|null; slots:number|null; first_token_ms:number|null; sample:string }
/** Nonsecret summary from the desktop host. `ok` is null until the server has been checked. */
export type ServerStatus = { selected:boolean; configured:boolean; key_present:boolean; model_selected:boolean; ok:boolean|null; code:string; checked_at:string }
export type Analytics = { started: number; succeeded: number; failed: number; tools: number; rejected: number; median_ms: number|null; messages: number; project: string; period_days: number; trend: Array<{date:string;runs:number}>; recent: Array<{type:string;at:string;duration_ms:number|null;detail:string}> }
export type IntelligenceStatus = {
  skills: {enabled:boolean;count:number;names:string[]};
  graphify: {enabled:boolean;export_detected:boolean;path:string;note:string};
  obsidian: {enabled:boolean;read_only:boolean;note:string};
  roblox_research?: {enabled:boolean}
}
export type McpStatus = { servers: Array<{name:string;enabled:boolean;protocol:string;credential_ready:boolean;state:string;read_only:boolean}> }
export type ChatThread = { id:string; title:string; created:string; updated:string }
export type CustomToolRecipe = { id:number;name:string;description:string;status:'pending'|'approved'|'rejected'|'disabled';tests:number;created_at:string;last_tested_at?:string|null;reviewed_at?:string|null;sources:string[] }
export type CustomToolCatalog = {project:string;tools:CustomToolRecipe[];notice:string}
export type WorkshopStatus = {pending:number;approved:number;rejected:number;disabled:number;read_only:boolean}
export type BuildInfo = {stamped:boolean; source_commit:string; head_commit:string; run_url:string; build_event:string; note:string}
export type BootData = { version:string; build?:BuildInfo; project:string; projects:string[]; messages:ChatMessage[]; active_chat:string; chats:ChatThread[]; settings:AppSettings; brain_installed:boolean; brain_running:boolean; model_router_running?:boolean; analytics:Analytics; release_url:string; intelligence?:IntelligenceStatus; credentials:Record<string,boolean>; mcp?:McpStatus; tool_workshop?:WorkshopStatus; server?:ServerStatus; retry?:RetryState|null }
export type BackendEvent = { requestId:string; kind:'result'|'progress'|'error'; data:unknown }
