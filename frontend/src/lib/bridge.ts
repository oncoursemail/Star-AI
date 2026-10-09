import type { BridgeReply, StarBridge, StarState, Analytics, Settings } from './types';

declare global {
  interface Window {
    qt?: { webChannelTransport: unknown };
    QWebChannel?: new (transport: unknown, cb: (channel: { objects: { starBridge: StarBridge } }) => void) => unknown;
  }
}

const DEFAULT_SETTINGS: Settings = {
  endpoint: 'http://127.0.0.1:8080/v1', model: '', project: 'STAR',
  workspace: '', studio_id: '', studio_edit: false, workspace_edit: false,
  max_calls: 12, context_chars: 26000, reduced_motion: false,
};

export const emptyAnalytics = (project = 'STAR'): Analytics => ({
  started: 0, succeeded: 0, failed: 0, tools: 0, rejected: 0, median_ms: null,
  messages: 0, project, trend: [], recent: [],
});

export const previewState: StarState = {
  version: '0.7.0', settings: DEFAULT_SETTINGS, messages: [], projects: ['STAR'],
  analytics: emptyAnalytics(),
  brain: { ready: false, state: 'Not connected', model: '', version: '' }, mode: 'preview',
};

function loadQtScript(): Promise<void> {
  if (window.QWebChannel) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'qrc:///qtwebchannel/qwebchannel.js';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('STAR desktop bridge could not load'));
    document.head.appendChild(script);
  });
}

export class StarClient {
  private bridge: StarBridge | undefined;
  private subscriptions = new Set<(event: { type: string; [key: string]: unknown }) => void>();
  private connected = false;

  async connect(): Promise<boolean> {
    if (!window.qt?.webChannelTransport) return false;
    await loadQtScript();
    if (!window.QWebChannel) return false;
    return new Promise<boolean>((resolve) => {
      new window.QWebChannel!(window.qt!.webChannelTransport, (channel) => {
        this.bridge = channel.objects.starBridge;
        this.connected = true;
        this.bridge.event.connect((raw) => {
          try {
            const value = JSON.parse(raw) as { type: string; [key: string]: unknown };
            for (const callback of this.subscriptions) callback(value);
          } catch { /* invalid event data is ignored, never executed */ }
        });
        resolve(true);
      });
    });
  }

  get isConnected(): boolean { return this.connected; }

  onEvent(listener: (event: { type: string; [key: string]: unknown }) => void): () => void {
    this.subscriptions.add(listener);
    return () => { this.subscriptions.delete(listener); };
  }

  async request(action: string, data: Record<string, unknown> = {}): Promise<BridgeReply> {
    if (!this.bridge) return { ok: false, error: 'This is a preview. Install STAR Desktop to use your local model and tools.' };
    return new Promise((resolve) => {
      this.bridge!.dispatch(JSON.stringify({ action, data }), (raw) => {
        try { resolve(JSON.parse(raw) as BridgeReply); }
        catch { resolve({ ok: false, error: 'STAR received an invalid local response.' }); }
      });
    });
  }
}

export const starClient = new StarClient();
