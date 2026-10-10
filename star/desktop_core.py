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
from .intelligence import for_settings
from .mcp_connections import MCPGateway
from .tool_workshop import ToolWorkshop
from .specialist_agents import ResearchTeam
from .providers import PROVIDERS, connection_for
from .brain_router import select_route, validate_alias, is_roblox_task, ROBLOX_QUALITY_NOTES


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
    fast_model: str = ''
    reasoning_model: str = ''
    roblox_model: str = ''
    vision_model: str = ''
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
    router_models_dir: str = ''
    router_context: int = 4096
    reduced_motion: bool = False
    comfy_workflow: str = ''
    comfy_prompt_node: str = '6'
    comfy_port: int = 8188
    obsidian_vault: str = ''
    obsidian_enabled: bool = False
    skills_enabled: bool = True
    graphify_enabled: bool = True
    roblox_research_enabled: bool = True
    tool_workshop_enabled: bool = True
    specialists_enabled: bool = True
    specialist_parallelism: int = 1
    mcp_graphify_docs: bool = False
    mcp_graphify_local: bool = False
    mcp_graphify_port: int = 8931
    mcp_obsidian_live: bool = False

    @classmethod
    def load(cls, file: Path):
        if not file.exists():
            return cls()
        raw = json.loads(file.read_text(encoding='utf-8'))
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})

    def validate(self):
        for field in ('model', 'fast_model', 'reasoning_model', 'roblox_model', 'vision_model'):
            validate_alias(getattr(self, field), field=field)
        if self.provider != 'local' and self.provider not in PROVIDERS:
            raise ValueError('Unknown model provider')
        if not re.fullmatch(r'http://(?:127\.0\.0\.1|localhost):\d{2,5}/v1/?', self.endpoint):
            raise ValueError('Use a loopback local inference URL ending in /v1')
        port = int(self.endpoint.split(':')[-1].split('/')[0])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid local inference port')
        if not self.project.strip() or len(self.project) > 100:
            raise ValueError('Project name is invalid')
        if any(type(getattr(self, key)) is not bool
               for key in ('obsidian_enabled', 'skills_enabled', 'graphify_enabled',
                            'mcp_graphify_docs','mcp_graphify_local','mcp_obsidian_live',
                            'roblox_research_enabled', 'tool_workshop_enabled',
                            'specialists_enabled')):
            raise ValueError('Tool access settings must be true or false')
        if self.obsidian_vault and not Path(self.obsidian_vault).expanduser().is_dir():
            raise ValueError('Obsidian vault must be an existing folder')
        if self.obsidian_enabled and not self.obsidian_vault:
            raise ValueError('Select an Obsidian vault before enabling read access')
        if self.workspace and (not Path(self.workspace).expanduser().is_dir()):
            raise ValueError('Choose an existing workspace directory')
        if type(self.specialist_parallelism) is not int or self.specialist_parallelism not in (1,2):
            raise ValueError('Limit specialists to 1 or 2 concurrent model calls')
        if type(self.mcp_graphify_port) is not int or not 1024 <= self.mcp_graphify_port <= 65535:
            raise ValueError('Invalid local Graphify MCP port')
        if self.studio_edit and not self.studio_id.strip():
            raise ValueError('Choose a disposable Studio instance before editing')
        if not 1 <= self.comfy_port <= 65535 or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', self.comfy_prompt_node):
            raise ValueError('Invalid local image generation configuration')
        if type(self.gpu_layers) is not int or not 0 <= self.gpu_layers <= 1000:
            raise ValueError('GPU layers must be between 0 and 1000')
        if type(self.router_context) is not int or not 512 <= self.router_context <= 32768:
            raise ValueError('Router context must be between 512 and 32768')
        if (not isinstance(self.router_models_dir, str)
                or len(self.router_models_dir) > 2048
                or '\x00' in self.router_models_dir
                or self.router_models_dir.lower().startswith(('http:', 'https:', 'file:'))):
            raise ValueError('Choose a local folder for the GGUF model router')
        if not 1 <= self.max_calls <= 30 or not 6000 <= self.context_chars <= 80000:
            raise ValueError('Invalid model call or context budget')

    def save(self, file: Path):
        self.validate()
        file.parent.mkdir(parents=True, exist_ok=True)
        # configuration is nonsecret; never write bearer tokens here
        file.write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')


class Conversations:
    """Persistent, project-scoped chat threads.

    Existing messages are migrated in-place into a legacy thread without deleting
    or rewriting their content. Callers that omit chat_id retain the historical
    project-wide recent() behavior; React explicitly selects a thread.
    """
    def __init__(self, db: Path):
        import sqlite3
        db.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db, timeout=30)
        self.connection.execute(
            'CREATE TABLE IF NOT EXISTS messages '
            '(id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, '
            'role TEXT NOT NULL, body TEXT NOT NULL, created TEXT NOT NULL)'
        )
        columns = {row[1] for row in self.connection.execute('PRAGMA table_info(messages)')}
        if 'chat_id' not in columns:
            self.connection.execute(
                "ALTER TABLE messages ADD COLUMN chat_id TEXT NOT NULL DEFAULT 'legacy'"
            )
        self.connection.execute(
            'CREATE TABLE IF NOT EXISTS chats '
            '(project TEXT NOT NULL, id TEXT NOT NULL, title TEXT NOT NULL, '
            'created TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY (project,id))'
        )
        self.connection.execute(
            'CREATE TABLE IF NOT EXISTS active_chats '
            '(project TEXT PRIMARY KEY, chat_id TEXT NOT NULL)'
        )
        self.connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_chat_messages '
            'ON messages(project,chat_id,id)'
        )
        # A pre-upgrade conversation is preserved verbatim under one stable ID.
        self.connection.execute(
            "INSERT OR IGNORE INTO chats (project,id,title,created,updated) "
            "SELECT project,'legacy','Previous conversation',MIN(created),MAX(created) "
            "FROM messages WHERE chat_id='legacy' GROUP BY project"
        )
        self.connection.commit()

    def new_chat(self, project: str) -> str:
        import uuid
        # Reuse an already blank active thread instead of filling the history with
        # duplicate untitled chats when the New chat button is clicked repeatedly.
        current = self.connection.execute(
            'SELECT a.chat_id FROM active_chats a JOIN chats c '
            'ON c.project=a.project AND c.id=a.chat_id '
            'WHERE a.project=? AND NOT EXISTS '
            '(SELECT 1 FROM messages m WHERE m.project=a.project AND m.chat_id=a.chat_id)',
            (project,)
        ).fetchone()
        if current:
            return current[0]
        chat_id = uuid.uuid4().hex
        created = datetime.now(timezone.utc).isoformat()
        with self.connection:
            self.connection.execute(
                'INSERT INTO chats(project,id,title,created,updated) VALUES (?,?,?,?,?)',
                (project, chat_id, 'New chat', created, created)
            )
            self.connection.execute(
                'INSERT INTO active_chats(project,chat_id) VALUES (?,?) '
                'ON CONFLICT(project) DO UPDATE SET chat_id=excluded.chat_id',
                (project, chat_id)
            )
        return chat_id

    def active_chat(self, project: str) -> str:
        found = self.connection.execute(
            'SELECT a.chat_id FROM active_chats a INNER JOIN chats c '
            'ON c.project=a.project AND c.id=a.chat_id WHERE a.project=?',
            (project,)
        ).fetchone()
        if found:
            return found[0]
        newest = self.connection.execute(
            'SELECT id FROM chats WHERE project=? ORDER BY updated DESC LIMIT 1',
            (project,)
        ).fetchone()
        if newest:
            self.switch_chat(project, newest[0])
            return newest[0]
        return self.new_chat(project)

    def switch_chat(self, project: str, chat_id: str) -> None:
        found = self.connection.execute(
            'SELECT 1 FROM chats WHERE project=? AND id=?', (project, chat_id)
        ).fetchone()
        if not found:
            raise ValueError('Conversation not found in this workspace')
        with self.connection:
            self.connection.execute(
                'INSERT INTO active_chats(project,chat_id) VALUES (?,?) '
                'ON CONFLICT(project) DO UPDATE SET chat_id=excluded.chat_id',
                (project, chat_id)
            )

    def list_chats(self, project: str, limit: int = 60) -> list[dict]:
        return [
            {'id': chat_id, 'title': title, 'created': created, 'updated': updated}
            for chat_id, title, created, updated in self.connection.execute(
                'SELECT id,title,created,updated FROM chats WHERE project=? '
                'ORDER BY updated DESC LIMIT ?', (project, limit)
            )
        ]

    def add(self, project: str, role: str, body: str, chat_id: str | None = None):
        if role not in {'user', 'assistant', 'event'}:
            raise ValueError('Invalid message role')
        stamp = datetime.now(timezone.utc).isoformat()
        target = chat_id if chat_id is not None else 'legacy'
        with self.connection:
            if chat_id is None:
                self.connection.execute(
                    'INSERT OR IGNORE INTO chats(project,id,title,created,updated) '
                    'VALUES (?,?,?,?,?)',
                    (project, 'legacy', 'Previous conversation', stamp, stamp)
                )
            elif not self.connection.execute(
                'SELECT 1 FROM chats WHERE project=? AND id=?', (project, chat_id)
            ).fetchone():
                raise ValueError('Cannot save to a missing conversation')
            self.connection.execute(
                'INSERT INTO messages(project,role,body,created,chat_id) '
                'VALUES (?,?,?,?,?)', (project, role, body, stamp, target)
            )
            # Name new chats from their first prompt, without altering legacy titles.
            if role == 'user' and target != 'legacy':
                first_line = ' '.join(body.split())[:64].strip() or 'New chat'
                self.connection.execute(
                    'UPDATE chats SET title=? WHERE project=? AND id=? AND title=?',
                    (first_line, project, target, 'New chat')
                )
            self.connection.execute(
                'UPDATE chats SET updated=? WHERE project=? AND id=?',
                (stamp, project, target)
            )

    def recent(self, project: str, limit: int = 70, chat_id: str | None = None):
        if chat_id is None:
            rows = self.connection.execute(
                'SELECT role,body,created FROM messages '
                'WHERE project=? ORDER BY id DESC LIMIT ?', (project, limit)
            ).fetchall()
        else:
            rows = self.connection.execute(
                'SELECT role,body,created FROM messages '
                'WHERE project=? AND chat_id=? ORDER BY id DESC LIMIT ?',
                (project, chat_id, limit)
            ).fetchall()
        return list(reversed(rows))

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


def needs_project_tools(prompt: str, prior_user_turns: list[str] | None = None) -> bool:
    """Load task tools on explicit request or scoped short edit follow-up.

    User context hints are not permissions; executable scopes remain enforced.
    """
    text = prompt.lower()
    scopes = ('studio', 'roblox', 'workspace', 'my project', 'my game', 'my files',
              'project folder', 'current place')
    actions = ('inspect', 'modify', 'edit', 'read ', 'fix ', 'fix it', 'change ',
               'create ', 'build ', 'implement', 'open ', 'scan ', 'add ',
               'remove ', 'delete ', 'test ', 'make it', 'update ')
    explicit_mcp = bool(re.search(r'\b(mcp|connected tools?|graphify docs|live obsidian)\b', text))
    requests_action = any(x in text for x in actions)
    if explicit_mcp:
        return True
    # Public Roblox game research is an explicit request for source-backed
    # information, not a Studio edit; load read-only tools when relevant.
    if (re.search(r'\b(?:roblox|luau|devforum)\b', text)
            and re.search(r'\b(?:games?|experiences?|visits|statistics|stats|playing|'
                          r'popular|compare|research|search|news|apis?|forums?|trends?)\b', text)):
        return True
    if (re.search(r'\b(?:create|propose|build|make|design)\b', text)
            and re.search(r'\b(?:custom|research|my|new|own)\s+tools?\b', text)):
        return True
    if not requests_action:
        return False
    if any(x in text for x in scopes):
        return True
    return bool(len(text) <= 160 and prior_user_turns
                and any(any(x in turn.lower() for x in scopes)
                        for turn in prior_user_turns[-3:] if isinstance(turn,str)))

def run_task(settings: Settings, prompt: str, images: list[Path] | None = None,
             on_event: Callable[[dict], None] | None = None,
             stream_tokens: bool = False, mode: str = 'auto', research: bool = False,
             cancel_event=None, github_enabled: bool = False, chat_id: str | None = None) -> str:
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
    first_visible_token = False
    metrics.record(settings.project, 'run_started')
    def audited_event(event):
        nonlocal first_visible_token
        if event.get('event') == 'assistant_delta' and not first_visible_token and str(event.get('text','')).strip():
            first_visible_token = True
            # Approximate first *visible* text delta from request start; no prompt
            # or model output is persisted in this operational metric.
            metrics.record(settings.project, 'first_token', elapsed_ms=int((time.monotonic()-started)*1000))
        if event.get('event') == 'tool_finished':
            metrics.record(settings.project, 'tool_completed', detail=str(event.get('tool', ''))[:80])
        elif event.get('event') == 'tool_rejected':
            metrics.record(settings.project, 'tool_rejected')
        if on_event:
            on_event(event)
    memory = Memory(home / 'checkpoints.sqlite3')
    memory_scope = settings.project if chat_id in (None, 'legacy') else settings.project + '::chat::' + chat_id
    knowledge = KnowledgeStore(home / 'knowledge')
    workshop = None
    try:
        dialogue = Conversations(home / 'conversations.sqlite3')
        try:
            recent_all = dialogue.recent(settings.project, limit=12, chat_id=chat_id)
        finally:
            dialogue.close()
        route_history = (
            recent_all[:-1] if recent_all and recent_all[-1][0] == 'user'
            and recent_all[-1][1] == prompt else recent_all
        )
        recent_users = [body for role,body,_ in route_history if role=='user']
        project_tools = needs_project_tools(prompt, recent_users)
        referential = len(prompt) <= 160 and bool(re.search(
            r'\b(?:it|this|that|same|continue|again|those|these)\b', prompt, re.I))
        roblox_context = bool(project_tools and referential
                              and any(is_roblox_task(turn) for turn in recent_users[-3:]))
        route = select_route(settings,prompt,mode=mode,image_count=len(images),
                             research=research,project_tools=project_tools,
                             roblox_context=roblox_context)
        audited_event({'event':'route_selected','profile':route.profile,
                       'description':route.description})
        quick = route.quick
        reviewed = knowledge.find_contextual(settings.project, prompt, limit=4 if quick else 8)
        notes = '\n'.join(f'[{n.kind} revision={n.revision} source={n.source}] {n.text}' for n in reviewed)
        for image in images:
            path = Path(image)
            media_type = 'image/jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else 'image/webp' if path.suffix.lower() == '.webp' else 'image/png'
            knowledge.ingest_artifact(project=settings.project, path=path,
                origin=f'desktop:{path.name}', media_type=media_type)
        # Every chat turn is independently callable, so supply a bounded recent
        # transcript from the persistent conversation DB as well as compacted memory.
        prior_turns = recent_context(recent_all[-(6 if quick else 12):], prompt)
        use_tools = route.use_tools
        intelligence = for_settings(settings, home) if use_tools else None
        workspace = Workspace(Path(settings.workspace)) if use_tools and settings.workspace else None
        if use_tools and settings.tool_workshop_enabled:
            workshop = ToolWorkshop(home=home,project=settings.project,knowledge=knowledge,
                                    workspace=workspace,intelligence=intelligence)
        allow_studio = bool(use_tools and settings.studio_id)
        mcp_gateway = MCPGateway(settings) if use_tools else None
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
                specialists = (ResearchTeam(
                    client=client,model=route.subagent_model,project=settings.project,
                    knowledge=knowledge,workspace=workspace,intelligence=intelligence,
                    parallelism=settings.specialist_parallelism,on_event=audited_event
                ) if use_tools and settings.specialists_enabled else None)
                memory_context = (memory.get(memory_scope) + '\nREVIEWED KNOWLEDGE:\n' + notes
                    + '\nRECENT CONVERSATION (stored, may be incomplete):\n' + prior_turns)
                if quick:
                    memory_context = memory_context[-5000:]
                else:
                    memory_context = memory_context[-14000:]
                kwargs = dict(client=client, model=route.model, prompt=prompt, image_paths=images,
                              project_memory=memory_context + snippets +
                                  (ROBLOX_QUALITY_NOTES if
                                  (is_roblox_task(prompt) or roblox_context) else ''),
                              max_calls=route.max_calls,
                              context_chars=settings.context_chars,
                              checkpoint=lambda s: memory.put(memory_scope, s), on_event=audited_event,
                              workspace=workspace, workspace_edit=settings.workspace_edit and use_tools,
                              stream_tokens=stream_tokens, response_tokens=route.response_tokens,
                              subagent_model=route.subagent_model,
                              web_search_enabled=bool(research and mode == 'agent'),
                              subagents_enabled=(mode == 'agent'),
                              subagent_parallelism=(1 if settings.provider == 'local' else 2),
                              github_enabled=bool(mode == 'agent' and github_enabled),
                              intelligence=intelligence, mcp_gateway=mcp_gateway,
                              tool_workshop=workshop, specialists=specialists)
                audited_event({'event': 'model_started'})
                if allow_studio:
                    async with connect() as session:
                        return await execute(**kwargs, studio=session,
                            discovered=await list_tools(session), studio_id=settings.studio_id,
                            may_edit=settings.studio_edit)
                return await execute(**kwargs)
        # Bound an entire task, not just each of up to 12 individual model calls.
        task_timeout = route.task_timeout
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
        memory.event(memory_scope, {'run_id': stamp, 'answer': answer[:10000]})
        audited_event({'event': 'saved', 'run_id': stamp})
        metrics.record(settings.project, 'run_succeeded',elapsed_ms=int((time.monotonic()-started)*1000))
        return answer
    except Exception as exc:
        metrics.record(settings.project, 'run_failed', elapsed_ms=int((time.monotonic()-started)*1000),
                       detail=type(exc).__name__)
        raise
    finally:
        if workshop is not None:
            workshop.close()
        knowledge.close()
        memory.close()
        metrics.close()
