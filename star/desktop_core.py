"""STAR Desktop's local-only backend. The Qt GUI calls this from worker threads."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from .analytics import AnalyticsStore
from dataclasses import dataclass, asdict
from typing import Callable

from .agent import execute
from .media import image_part
from .memory import Memory
from .workspace import Workspace
from .providers import PROVIDERS, connection_for


def app_data() -> Path:
    # Don't store data beside the exe: installations under Program Files are read-only.
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
        return base / 'STAR'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'star-ai'


@dataclass
class Settings:
    endpoint: str = 'http://127.0.0.1:1234/v1'
    provider: str = 'local'
    model: str = ''
    project: str = 'STAR'
    workspace: str = ''
    studio_id: str = ''
    studio_edit: bool = False
    workspace_edit: bool = False
    max_calls: int = 12
    context_chars: int = 26000
    llama_server: str = ''
    gguf_model: str = ''
    gpu_layers: int = 25
    reduced_motion: bool = False
    comfy_workflow: str = ''
    comfy_prompt_node: str = '6'
    comfy_port: int = 8188

    @classmethod
    def load(cls, file: Path):
        if not file.exists():
            return cls()
        raw = json.loads(file.read_text(encoding='utf-8'))
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})

    def validate(self):
        if self.provider != 'local' and self.provider not in PROVIDERS:
            raise ValueError('Unknown model provider')
        if not re.fullmatch(r'http://(?:127\.0\.0\.1|localhost):\d{2,5}/v1/?', self.endpoint):
            raise ValueError('Use a loopback local inference URL ending in /v1')
        port = int(self.endpoint.split(':')[-1].split('/')[0])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid local inference port')
        if not self.project.strip() or len(self.project) > 100:
            raise ValueError('Project name is invalid')
        if self.workspace and (not Path(self.workspace).expanduser().is_dir()):
            raise ValueError('Choose an existing workspace directory')
        if self.studio_edit and not self.studio_id.strip():
            raise ValueError('Choose a disposable Studio instance before editing')
        if not 1 <= self.comfy_port <= 65535 or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', self.comfy_prompt_node):
            raise ValueError('Invalid local image generation configuration')
        if not 0 <= self.gpu_layers <= 1000:
            raise ValueError('GPU layers must be between 0 and 1000')
        if not 1 <= self.max_calls <= 30 or not 6000 <= self.context_chars <= 80000:
            raise ValueError('Invalid model call or context budget')

    def save(self, file: Path):
        self.validate()
        file.parent.mkdir(parents=True, exist_ok=True)
        # configuration is nonsecret; never write bearer tokens here
        file.write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')


class Conversations:
    def __init__(self, db: Path):
        db.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db, timeout=30)
        self.connection.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, role TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL)')
        self.connection.commit()

    def add(self, project: str, role: str, body: str):
        if role not in {'user', 'assistant', 'event'}:
            raise ValueError('Invalid message role')
        self.connection.execute('INSERT INTO messages (project,role,body,created) VALUES (?,?,?,?)',
                                (project, role, body, datetime.now(timezone.utc).isoformat()))
        self.connection.commit()

    def recent(self, project: str, limit: int = 70):
        return list(reversed(self.connection.execute('SELECT role,body,created FROM messages WHERE project=? ORDER BY id DESC LIMIT ?', (project, limit)).fetchall()))

    def projects(self):
        return [r[0] for r in self.connection.execute('SELECT DISTINCT project FROM messages ORDER BY project')]

    def close(self):
        self.connection.close()


def recent_context(recent: list[tuple[str, str, str]], current_prompt: str) -> str:
    """Exclude the current turn if the UI already saved it to the conversation DB.

    This prevents the local model receiving the exact same new user request
    as both system-context history and the actual user message.
    """
    turns = list(recent)
    if turns and turns[-1][0] == 'user' and turns[-1][1] == current_prompt:
        turns.pop()
    return '\n'.join(f'{role}: {body[:1500]}' for role, body, _ in turns)


def query_models(settings: Settings) -> list[str]:
    settings.validate()
    import httpx
    endpoint, key = connection_for(settings)
    with httpx.Client(timeout=8, trust_env=False) as client:
        response = client.get(endpoint.rstrip('/') + '/models', headers={'Authorization': f'Bearer {key}'})
        response.raise_for_status()
        data = response.json()
        return [str(item['id']) for item in data.get('data', []) if isinstance(item, dict) and item.get('id')]


def check_studio():
    from .studio import connect, list_tools
    async def run():
        async with connect() as session:
            tools = await list_tools(session)
            if 'list_roblox_studios' not in {t['name'] for t in tools}:
                raise RuntimeError('Installed Studio MCP does not expose list_roblox_studios')
            result = await session.call_tool('list_roblox_studios', arguments={})
            return result.model_dump(by_alias=True, exclude_none=True)
    return asyncio.run(run())


def redact_for_logs(value):
    """Image bytes are retained in the artifact store, not duplicated in transcripts."""
    if isinstance(value, dict):
        if value.get('type') == 'image_url':
            return {'type': 'image_url', 'image_url': '[media stored separately in approved project artifacts]'}
        return {str(k): redact_for_logs(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_for_logs(v) for v in value]
    return value


def needs_project_tools(prompt: str) -> bool:
    """Avoid loading expensive Studio/MCP tools for ordinary knowledge chat."""
    text = prompt.lower()
    mentions_project = any(term in text for term in ('studio', 'roblox', 'workspace', 'my project',
        'my game', 'my files', 'project folder', 'current place'))
    requests_action = any(term in text for term in ('inspect', 'modify', 'edit', 'read ', 'fix ',
        'create ', 'build ', 'implement', 'open ', 'scan ', 'add ', 'remove ', 'delete ', 'test '))
    return mentions_project and requests_action

def run_task(settings: Settings, prompt: str, images: list[Path] | None = None,
             on_event: Callable[[dict], None] | None = None,
             stream_tokens: bool = False, mode: str = 'auto', research: bool = False,
             cancel_event=None, github_enabled: bool = False) -> str:
    """User-controlled fast/automatic/agent routing; all hosted calls are opt-in."""
    from openai import AsyncOpenAI
    from .knowledge import KnowledgeStore
    from .studio import connect, list_tools
    settings.validate()
    if mode not in {'auto', 'fast', 'agent'}:
        raise ValueError('Invalid chat mode')
    if not settings.model.strip():
        raise ValueError('Select a model in Settings, then test the connection')
    images = images or []
    for image in images:
        image_part(Path(image))
    home = app_data()
    home.mkdir(parents=True, exist_ok=True)
    metrics = AnalyticsStore(home / 'analytics.sqlite3')
    started = time.monotonic()
    metrics.record(settings.project, 'run_started')
    def audited_event(event):
        if event.get('event') == 'tool_finished':
            metrics.record(settings.project, 'tool_completed', detail=str(event.get('tool', ''))[:80])
        elif event.get('event') == 'tool_rejected':
            metrics.record(settings.project, 'tool_rejected')
        if on_event:
            on_event(event)
    memory = Memory(home / 'checkpoints.sqlite3')
    knowledge = KnowledgeStore(home / 'knowledge')
    try:
        quick = mode == 'fast' or (mode == 'auto' and not needs_project_tools(prompt))
        reviewed = knowledge.find(settings.project, prompt, reviewed_only=True, limit=4 if quick else 8)
        notes = '\n'.join(f'[{n.kind} revision={n.revision} source={n.source}] {n.text}' for n in reviewed)
        for image in images:
            path = Path(image)
            media_type = 'image/jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else 'image/webp' if path.suffix.lower() == '.webp' else 'image/png'
            knowledge.ingest_artifact(project=settings.project, path=path,
                origin=f'desktop:{path.name}', media_type=media_type)
        # Every chat turn is independently callable, so supply a bounded recent
        # transcript from the persistent conversation DB as well as compacted memory.
        dialogue = Conversations(home / 'conversations.sqlite3')
        try:
            recent = dialogue.recent(settings.project, limit=6 if quick else 12)
            prior_turns = recent_context(recent, prompt)
        finally:
            dialogue.close()
        use_tools = mode == 'agent' or (mode == 'auto' and not quick)
        workspace = Workspace(Path(settings.workspace)) if use_tools and settings.workspace else None
        allow_studio = bool(use_tools and settings.studio_id)
        endpoint, key = connection_for(settings)
        async def run():
            from openai import AsyncOpenAI
            from .web_search import search_web, source_context
            import httpx
            snippets = ''
            if research:
                audited_event({'event': 'search_started'})
                found = await search_web(prompt[:600], limit=5)
                snippets = '\n\n' + source_context(found)
                audited_event({'event': 'search_finished'})
            timeout = httpx.Timeout(95.0 if settings.provider == 'local' else 55.0, connect=8.0)
            async with AsyncOpenAI(base_url=endpoint, api_key=key, timeout=timeout, max_retries=0) as client:
                memory_context = (memory.get(settings.project) + '\nREVIEWED KNOWLEDGE:\n' + notes
                    + '\nRECENT CONVERSATION (stored, may be incomplete):\n' + prior_turns)
                if quick:
                    memory_context = memory_context[-5000:]
                else:
                    memory_context = memory_context[-14000:]
                kwargs = dict(client=client, model=settings.model, prompt=prompt, image_paths=images,
                              project_memory=memory_context + snippets,
                              max_calls=(1 if quick else min(settings.max_calls, 5 if mode == 'auto' else 20)),
                              context_chars=settings.context_chars,
                              checkpoint=lambda s: memory.put(settings.project, s), on_event=audited_event,
                              workspace=workspace, workspace_edit=settings.workspace_edit and use_tools,
                              stream_tokens=stream_tokens, response_tokens=650 if quick else 1600,
                              web_search_enabled=bool(research and mode == 'agent'),
                              subagents_enabled=(mode == 'agent'),
                              subagent_parallelism=(1 if settings.provider == 'local' else 2),
                              github_enabled=bool(mode == 'agent' and github_enabled))
                audited_event({'event': 'model_started'})
                if allow_studio:
                    async with connect() as session:
                        return await execute(**kwargs, studio=session,
                            discovered=await list_tools(session), studio_id=settings.studio_id,
                            may_edit=settings.studio_edit)
                return await execute(**kwargs)
        # Bound an entire task, not just each of up to 12 individual model calls.
        task_timeout = (85 if settings.provider == 'local' else 55) if quick else 180 if mode == 'auto' else 480
        async def controlled_run():
            """Cooperative user cancellation interrupts active async API and Studio calls."""
            job = asyncio.create_task(run())
            deadline = time.monotonic() + task_timeout
            try:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise RuntimeError('STAR task cancelled by user')
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Task time limit exceeded')
                    done, _ = await asyncio.wait({job}, timeout=min(0.15, remaining))
                    if done:
                        return await job
            finally:
                if not job.done():
                    job.cancel()
                    await asyncio.gather(job, return_exceptions=True)
        try:
            answer, msgs, archive = asyncio.run(controlled_run())
        except TimeoutError as exc:
            raise TimeoutError(f'STAR exceeded its {task_timeout}s task budget. Try Fast mode, a smaller prompt, or a hosted provider.') from exc
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        runs = home / 'runs' / stamp
        runs.mkdir(parents=True, exist_ok=True)
        (runs / 'transcript.json').write_text(json.dumps(redact_for_logs({'messages': msgs, 'archive': archive}), ensure_ascii=False, default=str), encoding='utf-8')
        (runs / 'answer.md').write_text(answer, encoding='utf-8')
        memory.event(settings.project, {'run_id': stamp, 'answer': answer[:10000]})
        audited_event({'event': 'saved', 'run_id': stamp})
        metrics.record(settings.project, 'run_succeeded',elapsed_ms=int((time.monotonic()-started)*1000))
        return answer
    except Exception as exc:
        metrics.record(settings.project, 'run_failed', elapsed_ms=int((time.monotonic()-started)*1000),
                       detail=type(exc).__name__)
        raise
    finally:
        knowledge.close()
        memory.close()
        metrics.close()
