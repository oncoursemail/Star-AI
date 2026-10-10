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


def app_data() -> Path:
    # Don't store data beside the exe: installations under Program Files are read-only.
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
        return base / 'STAR'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'star-ai'


@dataclass
class Settings:
    endpoint: str = 'http://127.0.0.1:1234/v1'
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
    obsidian_vault: str = ''
    obsidian_enabled: bool = False
    skills_enabled: bool = True
    graphify_enabled: bool = True
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
        if not re.fullmatch(r'http://(?:127\.0\.0\.1|localhost):\d{2,5}/v1/?', self.endpoint):
            raise ValueError('Use a loopback local inference URL ending in /v1')
        port = int(self.endpoint.split(':')[-1].split('/')[0])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid local inference port')
        if not self.project.strip() or len(self.project) > 100:
            raise ValueError('Project name is invalid')
        if self.workspace and (not Path(self.workspace).expanduser().is_dir()):
            raise ValueError('Choose an existing workspace directory')
        if any(type(getattr(self, key)) is not bool
               for key in ('obsidian_enabled', 'skills_enabled', 'graphify_enabled')):
            raise ValueError('Tool access settings must be true or false')
        if self.obsidian_vault and not Path(self.obsidian_vault).expanduser().is_dir():
            raise ValueError('Obsidian vault must be an existing folder')
        if self.obsidian_enabled and not self.obsidian_vault:
            raise ValueError('Select an Obsidian vault before enabling read access')
        if type(self.comfy_port) is not int or not 1 <= self.comfy_port <= 65535:
            raise ValueError('Invalid local ComfyUI port')
        if not isinstance(self.comfy_prompt_node, str) or not re.fullmatch(r'[0-9]{1,12}', self.comfy_prompt_node):
            raise ValueError('ComfyUI prompt node ID must be numeric')
        if not isinstance(self.comfy_workflow, str) or len(self.comfy_workflow) > 1024:
            raise ValueError('Invalid ComfyUI workflow path')
        if self.studio_edit and not self.studio_id.strip():
            raise ValueError('Choose a disposable Studio instance before editing')
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
    with httpx.Client(timeout=8, trust_env=False) as client:
        response = client.get(settings.endpoint.rstrip('/') + '/models')
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


def run_task(settings: Settings, prompt: str, images: list[Path] | None = None,
             on_event: Callable[[dict], None] | None = None,
             stream_tokens: bool = False, chat_id: str | None = None) -> str:
    """Called from a Qt worker thread. No API key needed for localhost engines."""
    from openai import AsyncOpenAI
    from .knowledge import KnowledgeStore
    from .studio import connect, list_tools
    settings.validate()
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
        reviewed = knowledge.find(settings.project, prompt, reviewed_only=True, limit=8)
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
            recent = dialogue.recent(settings.project, limit=12, chat_id=chat_id)
            prior_turns = recent_context(recent, prompt)
        finally:
            dialogue.close()
        workspace = Workspace(Path(settings.workspace)) if settings.workspace else None
        intelligence = for_settings(settings, home)
        allow_studio = bool(settings.studio_id)
        async def run():
            async with AsyncOpenAI(base_url=settings.endpoint, api_key='local-only', timeout=180.0, max_retries=0) as client:
                kwargs = dict(client=client, model=settings.model, prompt=prompt, image_paths=images,
                              project_memory=(memory.get(settings.project) + '\nREVIEWED KNOWLEDGE:\n' + notes + '\nRECENT CONVERSATION (stored, may be incomplete):\n' + prior_turns)[-14000:],
                              max_calls=settings.max_calls, context_chars=settings.context_chars,
                              checkpoint=lambda s: memory.put(settings.project, s), on_event=audited_event,
                              workspace=workspace, workspace_edit=settings.workspace_edit,
                              intelligence=intelligence,
                              stream_tokens=stream_tokens)
                if allow_studio:
                    async with connect() as session:
                        answer, msgs, archive = await execute(**kwargs, studio=session,
                            discovered=await list_tools(session), studio_id=settings.studio_id,
                            may_edit=settings.studio_edit)
                else:
                    answer, msgs, archive = await execute(**kwargs)
                return answer, msgs, archive
        answer, msgs, archive = asyncio.run(run())
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
