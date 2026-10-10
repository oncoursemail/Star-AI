export type Project = { name: string }
export type ChatMessage = { id: string; role: 'user'|'assistant'|'event'; text: string; created?: string; attachments?: string[]; image?: string }
export type AppSettings = { endpoint: string; provider: 'local'|'groq'|'openrouter'|'gemini'|'cerebras'; model: string; project: string; workspace: string; studio_id: string; studio_edit: boolean; workspace_edit: boolean; max_calls: number; context_chars: number; reduced_motion: boolean; comfy_workflow: string; comfy_prompt_node: string; comfy_port: number; obsidian_vault: string; obsidian_enabled: boolean; skills_enabled: boolean; graphify_enabled: boolean }
export type Analytics = { started: number; succeeded: number; failed: number; tools: number; rejected: number; median_ms: number|null; messages: number; project: string; period_days: number; trend: Array<{date:string;runs:number}>; recent: Array<{type:string;at:string;duration_ms:number|null;detail:string}> }
export type IntelligenceStatus = {
  skills: {enabled:boolean;count:number;names:string[]};
  graphify: {enabled:boolean;export_detected:boolean;path:string;note:string};
  obsidian: {enabled:boolean;read_only:boolean;note:string}
}
export type BootData = { version:string; project:string; projects:string[]; messages:ChatMessage[]; settings:AppSettings; brain_installed:boolean; brain_running:boolean; analytics:Analytics; release_url:string; credentials:Record<string,boolean>; intelligence?: IntelligenceStatus }
export type BackendEvent = { requestId:string; kind:'result'|'progress'|'error'; data:unknown }
