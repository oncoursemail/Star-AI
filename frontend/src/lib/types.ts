export type Area = 'chat' | 'projects' | 'brain' | 'analytics' | 'tools' | 'settings';
export type Message = { id: string; role: 'user' | 'assistant' | 'event'; body: string; created: string };
export type TaskEvent = { event?: string; phase?: string; result?: string; message?: string; progress?: number; run_id?: string; [key: string]: unknown };
export type Analytics = {
  started: number; succeeded: number; failed: number; tools: number; rejected: number;
  median_ms: number | null; messages: number; project: string;
  trend: { date: string; runs: number }[];
  recent: { type: string; at: string; duration_ms: number | null; detail: string }[];
};
export type Settings = {
  endpoint: string; model: string; project: string; workspace: string; studio_id: string;
  studio_edit: boolean; workspace_edit: boolean; max_calls: number;
  context_chars: number; reduced_motion: boolean;
};
export type Brain = { ready: boolean; state: string; model: string; version: string };
export type StarState = {
  version: string; settings: Settings; messages: Message[]; projects: string[];
  analytics: Analytics; brain: Brain; mode: 'desktop' | 'preview';
};
export type Attachment = { token: string; name: string; kind: string };
export type BridgeReply = { ok: boolean; data?: unknown; error?: string; started?: boolean };
export type StarBridge = {
  dispatch(payload: string, callback: (reply: string) => void): void;
  event: { connect(cb: (evt: string) => void): void; disconnect(cb: (evt: string) => void): void };
};
