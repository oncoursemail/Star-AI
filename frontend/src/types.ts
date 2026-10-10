export type Project = { name: string }
export type ChatMessage = { id: string; role: 'user'|'assistant'|'event'; text: string; created?: string; attachments?: string[] }
export type AppSettings = { endpoint: string; model: string; project: string; workspace: string; studio_id: string; studio_edit: boolean; workspace_edit: boolean; max_calls: number; context_chars: number; reduced_motion: boolean }
export type Analytics = { started: number; succeeded: number; failed: number; tools: number; rejected: number; median_ms: number|null; messages: number; project: string; period_days: number; trend: Array<{date:string;runs:number}>; recent: Array<{type:string;at:string;duration_ms:number|null;detail:string}> }
export type ChatThread = { id:string; title:string; created:string; updated:string }
export type BootData = { version:string; project:string; projects:string[]; messages:ChatMessage[]; active_chat:string; chats:ChatThread[]; settings:AppSettings; brain_installed:boolean; brain_running:boolean; analytics:Analytics; release_url:string }
export type BackendEvent = { requestId:string; kind:'result'|'progress'|'error'; data:unknown }
