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
from dataclasses import dataclass, asdict, replace, field
from typing import Callable

from .agent import execute, HistoryWindowPressure
from .media import image_part
from .memory import Memory
from . import conversation_memory
from .workspace import Workspace
from .intelligence import for_settings
from .mcp_connections import MCPGateway
from .tool_workshop import ToolWorkshop
from .specialist_agents import ResearchTeam
from .providers import (ALL_PROVIDERS, background_client, call_limits, connection_for, llama_request_fields,
                        model_unavailable, open_client,
                        provider_kind, server_context_tokens, validate_lan_endpoint)
from .brain_router import select_route, validate_alias, is_roblox_task, deep_request, ROBLOX_QUALITY_NOTES
from .instant_route import decide_instant_route, loaded_local_model, answer_on_pc
from . import server_roles, turn_memory
from .doc_knowledge import validate_knowledge_endpoint
from . import doc_grounding, skill_packs
from . import studio_loop
from .studio_connections import default_target, validate_target


def app_data() -> Path:
    # Don't store data beside the exe: installations under Program Files are read-only.
    if os.name == 'nt':
        base = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
        return base / 'STAR'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'star-ai'


@dataclass
class Settings:
    endpoint: str = 'http://127.0.0.1:8080/v1'
    provider: str = 'local'
    model: str = ''
    fast_model: str = ''
    reasoning_model: str = ''
    roblox_model: str = ''
    vision_model: str = ''
    project: str = 'STAR'
    workspace: str = ''
    studio_id: str = ''
    studio_target: str = field(default_factory=default_target)
    studio_edit: bool = False
    # The sandbox rule itself is code (star/studio_loop.py): edits only in a blank unsaved place.
    studio_own_places: bool = False       # ...and, when on, in places owned by STAR's own Roblox account
    studio_luau: bool = False             # let STAR run Luau in that sandbox (needed to create instances)
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
    # Where media runs (star/media_places.py): 'pc' = this PC's graphics card, 'servers' = the STAR Brains.
    media_images: str = 'pc'
    media_voice: str = 'pc'
    media_video: str = 'servers'
    media_use_references: bool = True     # give a project's pinned reference images to image and UI work
    comfy_home: str = ''                  # folder of the ComfyUI install STAR may start ('' = started by hand)
    ffmpeg_dir: str = ''                  # folder with ffmpeg and ffprobe ('' = look on PATH)
    # Longest side, in pixels, of a picture as the STAR Server or the on-device brain reads it
    # (0 = full size). The attached file itself is never changed. See star/media.py.
    picture_max_side: int = 1280
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
    # STAR Server (provider 'star_server'): an owner-entered private LAN address.
    # The server key is never stored here; it lives in the OS keyring.
    server_endpoint: str = ''
    server_timeout: int = 600        # seconds of silence allowed for one server request
    server_parallel: int = 1         # match the server's llama.cpp -np slot count
    server_context_tokens: int = 0   # per-request context; 0 = use what the server reports
    instant_route_enabled: bool | None = None   # None = on when a local model is already loaded
    # STAR Knowledge (official docs search, API lookup, Luau checks) on the same private
    # network: '' = the STAR Server's host on the knowledge port, 'off' = never ask it.
    knowledge_endpoint: str = ''
    # Learning (star/lessons.py). Lessons are local project notes, never weights.
    learning_auto_accept: bool = True     # False = "review everything": even my own words wait for approval
    learning_digest: bool = True          # let the fast model reword raw captures into candidates, in the background
    learning_digest_cloud: bool = False   # ...also when the selected provider is a hosted one

    @classmethod
    def load(cls, file: Path):
        if not file.exists():
            return cls()
        raw = json.loads(file.read_text(encoding='utf-8'))
        if 'studio_target' not in raw:
            # An old ID was selected on an unknown implicit route; never rebind its grants.
            raw = {**raw, 'studio_target': 'local_pc', 'studio_id': '', 'studio_edit': False, 'studio_luau': False}
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})

    def validate(self):
        validate_target(self.studio_target)
        for field in ('model', 'fast_model', 'reasoning_model', 'roblox_model', 'vision_model'):
            validate_alias(getattr(self, field), field=field)
        if not isinstance(self.provider, str) or self.provider not in ALL_PROVIDERS:
            raise ValueError('Unknown model provider')
        if not re.fullmatch(r'http://(?:127\.0\.0\.1|localhost):\d{2,5}/v1/?', self.endpoint):
            raise ValueError('Use a loopback local inference URL ending in /v1')
        port = int(self.endpoint.split(':')[-1].split('/')[0])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid local inference port')
        self._validate_server()
        if self.instant_route_enabled is not None and type(self.instant_route_enabled) is not bool:
            raise ValueError('Instant answers setting must be true, false or automatic')
        if not self.project.strip() or len(self.project) > 100:
            raise ValueError('Project name is invalid')
        if any(type(getattr(self, key)) is not bool
               for key in ('obsidian_enabled', 'skills_enabled', 'graphify_enabled',
                            'mcp_graphify_docs','mcp_graphify_local','mcp_obsidian_live',
                            'roblox_research_enabled', 'tool_workshop_enabled',
                            'specialists_enabled', 'learning_auto_accept', 'learning_digest',
                            'learning_digest_cloud', 'media_use_references', 'studio_own_places', 'studio_luau')):
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
        if any(getattr(self, key) not in ('pc', 'servers')
               for key in ('media_images', 'media_voice', 'media_video')):
            raise ValueError('Choose STAR Brains (servers) or This PC for each media capability')
        for key, label in (('comfy_home', 'ComfyUI folder'), ('ffmpeg_dir', 'FFmpeg folder')):
            value = getattr(self, key)
            if (not isinstance(value, str) or len(value) > 1024 or '\x00' in value
                    or value.lower().startswith(('http:', 'https:', 'file:', '\\\\'))):
                raise ValueError(f'Choose a local folder for the {label}')
        if type(self.picture_max_side) is not int or not (self.picture_max_side == 0
                                                           or 512 <= self.picture_max_side <= 4096):
            raise ValueError('Picture size for the brain must be 0 (full size) or 512 to 4096 pixels')
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

    def _validate_server(self):
        """STAR Server (LAN) settings. The loopback `endpoint` rule above is separate."""
        if not isinstance(self.server_endpoint, str):
            raise ValueError('STAR Server address must be text')
        if self.server_endpoint:
            validate_lan_endpoint(self.server_endpoint)
        elif provider_kind(self) == 'lan':
            validate_lan_endpoint('')  # raises the "enter your server address" message
        if not isinstance(self.knowledge_endpoint, str):
            raise ValueError('STAR Knowledge address must be text')
        if self.knowledge_endpoint and self.knowledge_endpoint != 'off':
            validate_knowledge_endpoint(self.knowledge_endpoint)
        if type(self.server_timeout) is not int or not 30 <= self.server_timeout <= 1800:
            raise ValueError('STAR Server timeout must be 30 to 1800 seconds')
        if type(self.server_parallel) is not int or not 1 <= self.server_parallel <= 4:
            raise ValueError('STAR Server parallel requests must be 1 to 4')
        if (type(self.server_context_tokens) is not int
                or not (self.server_context_tokens == 0 or 1024 <= self.server_context_tokens <= 1_048_576)):
            raise ValueError('STAR Server context must be 0 (automatic) or 1024 to 1048576 tokens')

    def save(self, file: Path):
        self.validate()
        file.parent.mkdir(parents=True, exist_ok=True)
        # configuration is nonsecret; never write bearer tokens here
        file.write_text(json.dumps(asdict(self), indent=2), encoding='utf-8')


TERMINAL_STATUSES = ('failed', 'cancelled')


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
        # Turn outcome (additive; old rows and older STAR versions stay valid).
        # status is 'complete' except on the terminal 'event' record of a turn that
        # failed or was cancelled; reply_to is the user message row that record answers.
        if 'status' not in columns:
            self.connection.execute(
                "ALTER TABLE messages ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'"
            )
        if 'reply_to' not in columns:
            self.connection.execute('ALTER TABLE messages ADD COLUMN reply_to INTEGER')
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
        # The owner's thumb on an answer (additive: a new table, nothing existing changes).
        self.connection.execute(
            'CREATE TABLE IF NOT EXISTS message_feedback '
            '(message_id INTEGER PRIMARY KEY, project TEXT NOT NULL, chat_id TEXT NOT NULL, '
            'value TEXT NOT NULL, updated TEXT NOT NULL)'
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

    def add(self, project: str, role: str, body: str, chat_id: str | None = None, *,
            status: str = 'complete', reply_to: int | None = None) -> int:
        """Store one message and return its row id."""
        if role not in {'user', 'assistant', 'event'}:
            raise ValueError('Invalid message role')
        if status != 'complete' and (status not in TERMINAL_STATUSES or role != 'event'
                                     or type(reply_to) is not int):
            raise ValueError('Only an event record that answers a user message can be failed or cancelled')
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
            row = self.connection.execute(
                'INSERT INTO messages(project,role,body,created,chat_id,status,reply_to) '
                'VALUES (?,?,?,?,?,?,?)',
                (project, role, body, stamp, target, status, reply_to)
            ).lastrowid
            # Name new chats from their first prompt, without altering legacy titles.
            if role == 'user' and target != 'legacy':
                text = ' '.join(body.split())
                # A long first message is shortened for the title; the ellipsis says so
                # (the top bar used to show a title that simply stopped mid-word).
                first_line = (text if len(text) <= 64 else text[:63].rstrip() + '…') or 'New chat'
                self.connection.execute(
                    'UPDATE chats SET title=? WHERE project=? AND id=? AND title=?',
                    (first_line, project, target, 'New chat')
                )
            self.connection.execute(
                'UPDATE chats SET updated=? WHERE project=? AND id=?',
                (stamp, project, target)
            )
        return int(row)

    def add_terminal(self, project: str, chat_id: str, user_id: int, status: str, detail: str) -> int | None:
        """Record that the turn started by user message ``user_id`` ended without an answer.

        Idempotent: a turn gets at most one terminal record. Returns the new row id,
        or None when the turn was already closed.
        """
        if status not in TERMINAL_STATUSES:
            raise ValueError('Terminal status must be failed or cancelled')
        owner = self.connection.execute(
            "SELECT 1 FROM messages WHERE id=? AND project=? AND chat_id=? AND role='user'",
            (user_id, project, chat_id)
        ).fetchone()
        if not owner:
            raise ValueError('Terminal record must answer a user message in the same conversation')
        if self.connection.execute(
            "SELECT 1 FROM messages WHERE reply_to=? AND status!='complete'", (user_id,)
        ).fetchone():
            return None
        return self.add(project, 'event', detail[:2000], chat_id=chat_id,
                        status=status, reply_to=user_id)

    def recent(self, project: str, limit: int = 70, chat_id: str | None = None,
               include_events: bool = True):
        """Newest ``limit`` messages, oldest first. Model context passes include_events=False."""
        scope, args = ('project=?', [project]) if chat_id is None else ('project=? AND chat_id=?', [project, chat_id])
        if not include_events:
            scope += " AND role IN ('user','assistant')"
        rows = self.connection.execute(
            f'SELECT role,body,created FROM messages WHERE {scope} ORDER BY id DESC LIMIT ?',
            (*args, limit)
        ).fetchall()
        return list(reversed(rows))

    def history_rows(self, project: str, chat_id: str | None = None, clip: int = 4000):
        """Every user/assistant row of the chat as (role, text), oldest first, without events.

        All rows, not the newest few: the model's history window is measured from the
        first message of the chat so that it stays put from turn to turn (see
        context_layout.conversation_window). Each text is cut to ``clip`` characters.
        """
        scope, args = ('project=?', [project]) if chat_id is None else ('project=? AND chat_id=?', [project, chat_id])
        return self.connection.execute(
            f"SELECT role,SUBSTR(body,1,?) FROM messages WHERE {scope} AND role IN ('user','assistant') ORDER BY id",
            (clip, *args)
        ).fetchall()

    def raw_history_records(self, project: str, chat_id: str | None = None) -> list[dict]:
        """Full ID-bearing records of exactly one chat, including terminal outcomes."""
        return conversation_memory.raw_records(self.connection, project, chat_id)

    def recent_records(self, project: str, limit: int = 70, chat_id: str | None = None) -> list[dict]:
        """Like recent(), with row ids and turn outcome, for the UI state payload."""
        scope, args = ('project=?', [project]) if chat_id is None else ('project=? AND chat_id=?', [project, chat_id])
        rows = self.connection.execute(
            'SELECT id,role,body,created,status,reply_to,'
            '(SELECT value FROM message_feedback f WHERE f.message_id=messages.id) FROM messages '
            f'WHERE {scope} ORDER BY id DESC LIMIT ?', (*args, limit)
        ).fetchall()
        return [{'id': i, 'role': role, 'body': body, 'created': created,
                 'status': status, 'reply_to': reply_to, 'feedback': feedback or ''}
                for i, role, body, created, status, reply_to, feedback in reversed(rows)]

    def set_feedback(self, project: str, message_id: int, value: str) -> dict:
        """Store, change or clear ('') the owner's thumb on one answer of this project.

        Returns the chat, the answer and the question it answered, for the lesson record.
        """
        if value not in ('up', 'down', ''):
            raise ValueError('Feedback must be up, down or empty')
        row = self.connection.execute(
            "SELECT chat_id,body FROM messages WHERE id=? AND project=? AND role='assistant'",
            (message_id, project)
        ).fetchone()
        if not row:
            raise ValueError("Feedback must be about one of STAR's answers in this project")
        chat_id, answer = row
        asked = self.connection.execute(
            "SELECT body FROM messages WHERE project=? AND chat_id=? AND role='user' AND id<? "
            'ORDER BY id DESC LIMIT 1', (project, chat_id, message_id)
        ).fetchone()
        with self.connection:
            if value:
                self.connection.execute(
                    'INSERT INTO message_feedback(message_id,project,chat_id,value,updated) VALUES (?,?,?,?,?) '
                    'ON CONFLICT(message_id) DO UPDATE SET value=excluded.value,updated=excluded.updated',
                    (message_id, project, chat_id, value, datetime.now(timezone.utc).isoformat())
                )
            else:
                self.connection.execute('DELETE FROM message_feedback WHERE message_id=?', (message_id,))
        return {'chat_id': chat_id, 'answer': answer, 'question': asked[0] if asked else ''}

    def turn_context(self, project: str, chat_id: str | None, prompt: str = '') -> dict:
        """The message being answered now and what happened to the turn before it.

        For after-turn learning (star/lessons.py): a correction is linked to the answer it
        follows, and a repeat of a failed message is a retry. Read-only. `message_id` is None
        when the newest stored user message is not the one in `prompt` (a direct call that
        saved nothing).
        """
        target = chat_id if chat_id is not None else 'legacy'
        rows = self.connection.execute(
            'SELECT id,role,body,status,reply_to FROM messages WHERE project=? AND chat_id=? '
            'ORDER BY id DESC LIMIT 16', (project, target)
        ).fetchall()
        found = {'message_id': None, 'previous': None}
        users = [index for index, row in enumerate(rows) if row[1] == 'user']
        if not users:
            return found
        current = users[0]
        earlier = rows[current + 1:]
        if rows[current][2] and prompt.startswith(rows[current][2]) and not any(
                row[1] == 'assistant' for row in rows[:current]):
            found['message_id'] = rows[current][0]
        else:
            # The newest stored turn is already finished: it is the turn before this prompt.
            earlier = rows
        before = next((index for index, row in enumerate(earlier) if row[1] == 'user'), None)
        if before is None:
            return found
        asked = earlier[before]
        previous = {'message_id': asked[0], 'text': asked[2], 'outcome': 'none',
                    'answer_id': None, 'answer': '', 'detail': ''}
        for row in reversed(earlier[:before]):       # rows after that question, oldest first
            if row[1] == 'assistant':
                previous.update(outcome='answered', answer_id=row[0], answer=row[2])
                break
            if row[1] == 'event' and row[3] in TERMINAL_STATUSES and row[4] == asked[0]:
                previous.update(outcome=row[3], detail=row[2])
        found['previous'] = previous
        return found

    def retry_state(self, project: str, chat_id: str, busy: bool = False) -> dict | None:
        """What happened to the newest user message in a chat, if it got no answer.

        Returns None when the newest turn was answered (or there is no turn, or a
        task is still running). Otherwise: status failed/cancelled from the stored
        terminal record, or 'interrupted' when nothing at all was recorded after the
        message (for example STAR was closed mid-reply). Derived on read, never written.
        """
        last = self.connection.execute(
            "SELECT id,body,created FROM messages WHERE project=? AND chat_id=? AND role='user' "
            'ORDER BY id DESC LIMIT 1', (project, chat_id)
        ).fetchone()
        if not last:
            return None
        user_id, prompt, created = last
        after = self.connection.execute(
            'SELECT role,body,created,status,reply_to FROM messages '
            'WHERE project=? AND chat_id=? AND id>? ORDER BY id', (project, chat_id, user_id)
        ).fetchall()
        if any(role == 'assistant' for role, *_ in after):
            return None
        for role, body, stamp, status, reply_to in reversed(after):
            if role == 'event' and status in TERMINAL_STATUSES and reply_to == user_id:
                return {'status': status, 'detail': body, 'prompt': prompt,
                        'message_id': user_id, 'created': stamp}
        if busy:
            return None
        return {'status': 'interrupted',
                'detail': 'No reply was recorded for this message. STAR may have been closed before it finished.',
                'prompt': prompt, 'message_id': user_id, 'created': created}

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


def check_studio(settings: Settings | None = None, home: Path | None = None):
    from .studio_connections import discover
    return asyncio.run(discover(settings or Settings(), home=home if home is not None else app_data()))


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

def needs_studio_connection(prompt: str, prior_user_turns: list[str] | None = None) -> bool:
    """Only connect to Roblox Studio for an actual selected-place operation.

    A configured studio_id is NOT a request to connect for every agent call.
    Public Roblox game stats, forum research, generic coding discussions,
    image generation and tool catalogues must remain independent of Studio.
    """
    if not isinstance(prompt,str) or not prompt.strip():
        return False
    text=prompt.lower()
    actions=('inspect','edit','modify','build','create','fix','test ','run ','playtest',
             'open ','change ','update ','delete ','remove ','add ','insert ','scan ')
    requests_action=any(a in text for a in actions)
    if not requests_action:
        return False
    studio_scopes=('studio','current place','selected place','my game',
                   'my project','my roblox game','the place','game hierarchy',
                   'explorer tree','datamodel')
    if any(term in text for term in studio_scopes):
        return True
    if 'roblox' in text and not any(term in text for term in (
        'statistics','stats','visits','favorites','playing','concurrent',
        'universe id','place id','news','devforum','forum','public api',
        'game search','game research','popular games')):
        return True
    return bool(len(text)<=160 and prior_user_turns
                and re.search(r'\b(?:it|this|that|same|continue|again)\b',text)
                and any(any(term in turn.lower() for term in studio_scopes)
                        for turn in prior_user_turns[-3:] if isinstance(turn,str)))


def model_context_char_budget(settings: Settings, model: str | None = None) -> int:
    """Conservative CHAR proxy, not an exact tokenizer, for managed local router.

    The router's ctx-size is in tokens; complex Luau/MCP schemas can have many
    tokens per character. Keep a reserve for the active user prompt, tools and
    response. Other inference endpoints retain their existing settings.
    """
    kind = provider_kind(settings)
    if kind == 'local' and settings.router_models_dir:
        # Even 8-GB GPUs can page heavily when the KV cache is oversized.
        return min(settings.context_chars, max(3000, 2 * (settings.router_context - 512)))
    if kind == 'lan':
        # Each llama-server slot has its own context. Use the owner's value or
        # the size the server itself reported; unknown keeps the saved budget.
        # `model` is the model the request is routed to (the quick model has a
        # smaller context than the main one).
        tokens = server_context_tokens(settings, model) or server_context_tokens(settings)
        if tokens:
            return min(settings.context_chars, max(3000, 2 * (tokens - 1024)))
    return settings.context_chars


# Characters of earlier turns replayed on STAR Server (see `history_char_budget`).
SERVER_HISTORY_CHARS = 12000


def history_char_budget(settings: Settings) -> int:
    """Characters of earlier turns to replay.

    Cached history costs nothing per turn; what costs is the first message
    after a start and each time the window moves, when the server reads what is
    in the window again (see conversation_memory.select_window: the window
    moves by half of this budget at a time, and one replayed message is at most
    a quarter of it).

      cloud        12000: a hosted provider reads fast.
      STAR Server  12000: measured on the owner's server (docs/agents/model-routing.md).
                   The old 6000 cut every replayed message at 1500 characters, less than
                   one Fast-mode answer, and kept one to three exchanges. 12000 keeps a
                   whole Fast-mode answer (3000 characters) and three to seven exchanges.
                   A window move re-reads about 6000 characters; the post-answer warm-up
                   does that while the owner reads the answer.
      on this PC   6000: small GPU models with small contexts; unchanged.

    One budget for every model of a server: the window is then the same request
    start whichever model answers.
    """
    allowed = model_context_char_budget(settings)
    kind = provider_kind(settings)
    if kind == 'cloud':
        return min(12000, allowed // 2)
    if kind == 'lan':
        return min(SERVER_HISTORY_CHARS, max(1500, allowed // 2))
    return min(6000, max(1500, allowed // 4))


def stable_memory(settings: Settings, checkpoint: str) -> str:
    """The part of the compacted checkpoint that goes into the system message."""
    # Request budgeting must see all of it. Silently taking the suffix can drop
    # earlier requirements before the agent has a chance to detect overflow.
    return checkpoint


def memory_scope_for(settings: Settings, chat_id: str | None) -> str:
    return settings.project if chat_id in (None, 'legacy') else settings.project + '::chat::' + chat_id


def chat_history(settings: Settings, home: Path, chat_id: str | None):
    """Earlier turns of a chat exactly as the next request will replay them.

    Returns (history messages, newest stored rows). The same function feeds a
    real turn and the cache warm-up, so both start with identical bytes. A
    trailing user row is the message being answered now (already saved by the
    UI) and is not history; an earlier message that never got a reply is kept,
    marked as unanswered (see context_layout.exchanges).
    """
    window, rows = chat_history_snapshot(settings, home, chat_id)
    return window.messages, [(row['role'], row['body']) for row in rows
                             if row['role'] in {'user', 'assistant'}][-12:]


def chat_history_snapshot(settings: Settings, home: Path, chat_id: str | None, *, current_text=None):
    """Full scoped originals and a pure bounded window, shared with warm-up."""
    budget = history_char_budget(settings)
    dialogue = Conversations(home / 'conversations.sqlite3')
    try:
        rows = dialogue.raw_history_records(settings.project, chat_id)
    finally:
        dialogue.close()
    window = conversation_memory.select_window(rows, budget, current_text=current_text)
    checkpoint = conversation_memory.read_checkpoint(home / 'conversations.sqlite3', settings.project,
                                                      chat_id, records=rows)
    return conversation_memory.respect_checkpoint(window, checkpoint), rows


def picture_limit(settings) -> int | None:
    """Longest side of a picture as the model reads it: capped on our own hardware, untouched for hosted models."""
    if provider_kind(settings) not in ('lan', 'local'):
        return None
    return int(getattr(settings, 'picture_max_side', 1280) or 0) or None


def run_task(settings: Settings, prompt: str, images: list[Path] | None = None,
             on_event: Callable[[dict], None] | None = None,
             stream_tokens: bool = False, mode: str = 'auto', research: bool = False,
             cancel_event=None, github_enabled: bool = False, chat_id: str | None = None,
             owner_text: str | None = None, documents: list[Path] | None = None,
             studio_configuration_home: Path | None = None) -> str:
    """User-controlled fast/automatic/agent routing; all hosted calls are opt-in.

    `owner_text` is what the owner typed, when `prompt` also carries text STAR added (an
    audio transcript, a note about video frames). Only the owner's own words can become an
    automatically accepted lesson.
    """
    from openai import AsyncOpenAI
    from .knowledge import KnowledgeStore
    from . import lessons as learning
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
    token_timing = {'requested': None, 'first': None, 'last': None}
    metrics.record(settings.project, 'run_started')
    def audited_event(event):
        nonlocal first_visible_token
        now = time.monotonic()
        if event.get('event') == 'model_turn' and token_timing['requested'] is None:
            token_timing['requested'] = now
        if event.get('event') == 'assistant_delta' and str(event.get('text','')).strip():
            if token_timing['first'] is None:
                token_timing['first'] = now
            token_timing['last'] = now
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
    memory_scope = memory_scope_for(settings, chat_id)
    knowledge = KnowledgeStore(home / 'knowledge')
    workshop = None
    document_store = None
    document_tools = None
    lesson_store = learning.LessonStore(knowledge=knowledge, record=metrics.record)
    recalled = []
    learned = {'grounding': None, 'messages': None, 'done': False}

    def learn_from_turn():
        """After the turn (answered, failed or stopped): record what it taught. Regular
        expressions and a few SQLite rows, no model call; a problem here never changes
        the outcome of the turn."""
        if learned['done']:
            return
        learned['done'] = True
        try:
            said = prompt if owner_text is None else owner_text
            chats = Conversations(home / 'conversations.sqlite3')
            try:
                turn = chats.turn_context(settings.project, chat_id, said)
            finally:
                chats.close()
            summary = learning.capture_turn(
                lesson_store, project=settings.project, chat_id=chat_id, owner_text=said, turn=turn,
                grounding=learned['grounding'], messages=learned['messages'],
                auto_accept=settings.learning_auto_accept is True)
            if on_event and (summary['accepted'] or summary['candidates'] or summary.get('not_kept')):
                on_event({'event': 'lessons_captured', 'accepted': summary['accepted'],
                          'candidates': summary['candidates'],
                          **({'replaced': summary['replaced']} if summary['replaced'] else {}),
                          **({'not_kept': summary['not_kept']} if summary.get('not_kept') else {})})
        except Exception:
            pass
    try:
        # Evidence is attached only to this project and conversation. Later turns
        # can retrieve it without reopening files elsewhere on the computer.
        document_block = ''
        if documents or (home / 'documents.sqlite3').is_file():
            from .documents import DocumentStore
            from .document_tools import DocumentTools
            document_store = DocumentStore(home, settings.project, chat_id)
            if documents:
                audited_event({'event': 'documents_started'})
                attached = document_store.ingest([Path(path) for path in documents], cancel_event)
                audited_event({'event': 'documents_ready', 'documents': len(attached)})
            document_block = document_store.context(prompt, budget_chars=min(6000, settings.context_chars // 3))
            if document_block:
                document_tools = DocumentTools(document_store)
        # Earlier turns are sent as real user/assistant messages, oldest first, and the
        # window over them only moves in whole blocks: the request starts with the same
        # bytes turn after turn, which is what lets the model server reuse its cache.
        history_window, conversation_records = chat_history_snapshot(
            settings, home, chat_id, current_text=owner_text if owner_text is not None else prompt)
        history = history_window.messages
        recent_all = [(row['role'], row['body']) for row in conversation_records
                      if row['role'] in {'user', 'assistant'}][-12:]
        # The UI saved the message being answered before calling this; it is not a prior turn.
        route_history = (
            recent_all[:-1] if recent_all and recent_all[-1][0] == 'user'
            and recent_all[-1][1] and prompt.startswith(recent_all[-1][1]) else recent_all
        )
        recent_users = [body for role,body in route_history if role=='user']
        project_tools = needs_project_tools(prompt, recent_users)
        referential = len(prompt) <= 160 and bool(re.search(
            r'\b(?:it|this|that|same|continue|again|those|these)\b', prompt, re.I))
        roblox_context = bool(project_tools and referential
                              and any(is_roblox_task(turn) for turn in recent_users[-3:]))
        # STAR Server may offer several models: blank role fields are filled from what the
        # server listed (never saved, never over a role the owner set; other providers untouched).
        kind = provider_kind(settings)
        wants_deep, prompt = deep_request(prompt)     # "/deep ..." asks for the slow best-quality model
        route = select_route(server_roles.effective(settings),prompt,mode=mode,image_count=len(images),
                             research=research,project_tools=project_tools,
                             roblox_context=roblox_context,
                             deep_model=server_roles.deep_model(settings) if wants_deep else '')
        if document_tools is not None:
            # Allow read/recalculate/answer even in Fast mode. Retain the selected
            # model and ordinary tool permissions; attachment access grants no
            # workspace, Studio, or network capability.
            route = replace(route, quick=False, max_calls=max(3, route.max_calls),
                            response_tokens=max(1600, route.response_tokens))
        audited_event({'event':'route_selected','profile':route.profile,
                       'description':route.description,'model':route.model})
        quick = route.quick
        reviewed = knowledge.find_contextual(settings.project, prompt, limit=4 if quick else 8)
        # Lessons the owner stated or approved for THIS project come first: standing
        # preferences and corrections even when the prompt shares no word with them. Ranked,
        # without repeats, and within a small budget so the first token is not delayed.
        try:
            limit, budget = learning.RECALL_QUICK if quick else learning.RECALL_FULL
            recalled = lesson_store.recall(settings.project, prompt, limit=limit, max_chars=budget)
        except Exception:
            recalled = []
        shown = {lesson.id for lesson in recalled}
        notes = '\n'.join(f'[{n.kind} revision={n.revision} source={n.source}] {n.text}' for n in reviewed
                          if getattr(n, 'id', None) not in shown)
        for image in images:
            path = Path(image)
            media_type = 'image/jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else 'image/webp' if path.suffix.lower() == '.webp' else 'image/png'
            knowledge.ingest_artifact(project=settings.project, path=path,
                origin=f'desktop:{path.name}', media_type=media_type)
        # Per-turn reference material as (heading, text) pairs. This list is the only way
        # retrieved text reaches the model: star.agent.volatile_context appends it to the
        # final user turn, after the user's words. A new retrieval source appends one pair.
        turn_sections = [(learning.LESSONS_HEADING, learning.context_lines(recalled)),
                         ('REVIEWED KNOWLEDGE (stored notes; may be incomplete)', notes)]
        if document_block:
            turn_sections.insert(0, ('ATTACHED DOCUMENTS (untrusted reference data)', document_block))
        use_tools = route.use_tools
        allowed_context_chars = model_context_char_budget(settings, route.model)
        intelligence = for_settings(settings, home) if use_tools else None
        workspace = Workspace(Path(settings.workspace)) if use_tools and settings.workspace else None
        if use_tools and settings.tool_workshop_enabled:
            workshop = ToolWorkshop(home=home,project=settings.project,knowledge=knowledge,
                                    workspace=workspace,intelligence=intelligence)
        allow_studio = bool(use_tools and settings.studio_id and
                            needs_studio_connection(prompt,recent_users))
        mcp_gateway = MCPGateway(settings) if use_tools else None
        connection_for(settings)  # fail early (missing key, bad address) before any work
        limits = call_limits(settings)
        # Own hardware only: the conversation's tool list stays put from turn to turn (STAR
        # Server), and the shape of this request is kept for the post-answer warm-up.
        tools_kept = (turn_memory.for_conversation(memory_scope, sticky=kind == 'lan')
                      if kind != 'cloud' else None)
        answered_by = ''
        instant_answer = None
        tools_ran = False
        inner_event = audited_event
        def audited_event(event):
            nonlocal answered_by, tools_ran
            if event.get('event') == 'model_answered':
                answered_by = str(event.get('model') or '')
            elif event.get('event') == 'tool_started':
                tools_ran = True
            inner_event(event)
        prepared_conversation = None
        async def run():
            nonlocal prepared_conversation, instant_answer, first_visible_token
            # Do not touch the PC's model unless this standalone text turn is eligible.
            # The loopback /models probe reads only residency; a router's unloaded model
            # is never selected and no llama.cpp process is started or downloaded.
            eligible = dict(prompt=prompt, mode=mode, provider=kind,
                            enabled=settings.instant_route_enabled is not False,
                            attachments=len(images) + len(documents or ()),
                            tools=use_tools or document_tools is not None or bool(github_enabled),
                            research=research, documentation=route.grounding.retrieve != 'none',
                            deep=wants_deep, followup=referential or roblox_context
                            or bool(owner_text is not None and owner_text != prompt))
            if decide_instant_route(**eligible, loaded_model='resident').use_local:
                local_model = await loaded_local_model(settings.endpoint)
                if decide_instant_route(**eligible, loaded_model=local_model).use_local:
                    try:
                        instant_answer = await answer_on_pc(settings.endpoint, local_model, prompt)
                    except Exception:
                        # Local text was buffered, not streamed to the chat. The original
                        # server request can now run unchanged, exactly once.
                        audited_event({'event': 'instant_fallback', 'model': route.model})
                    else:
                        first_visible_token = True
                        metrics.record(settings.project, 'first_token',
                                       elapsed_ms=instant_answer.first_token_ms)
                        audited_event({'event': 'instant_selected', 'model': instant_answer.model})
                        audited_event({'event': 'model_answered', 'model': instant_answer.model})
                        audited_event({'event': 'assistant_delta', 'text': instant_answer.text})
                        audited_event({'event': 'finished', 'model_calls': 1, 'tool_calls': 0})
                        return (instant_answer.text,
                                [{'role': 'user', 'content': prompt},
                                 {'role': 'assistant', 'content': instant_answer.text}], [])
            from .web_search import search_web, source_context
            if research:
                audited_event({'event': 'search_started'})
                found = await search_web(prompt[:600], limit=5)
                turn_sections.append(('WEB SEARCH', source_context(found)))
                audited_event({'event': 'search_finished'})
            # One client per task, with the selected provider's own time limits.
            async with open_client(settings) as client:
                # Summaries, sub-agents, specialists and code repair are not the conversation:
                # on STAR Server they use the slot next to it (providers.llama_request_fields).
                helper = background_client(client, settings, conversation=memory_scope)
                specialists = (ResearchTeam(
                    client=helper,model=route.subagent_model,project=settings.project,
                    knowledge=knowledge,workspace=workspace,intelligence=intelligence,
                    parallelism=settings.specialist_parallelism,on_event=audited_event
                ) if use_tools and settings.specialists_enabled else None)
                # Stable part: the compacted checkpoint only changes when one is written.
                # Reserve room for the system instructions, user text and
                # discovered tool schemas before adding this turn's context.
                memory_limit = max(700, allowed_context_chars - 3200)
                # >>> STAR Knowledge (star/doc_grounding.py): official-docs passages for Roblox/Luau
                # questions, added as delimited UNTRUSTED reference data. Never raises; '' when unused.
                docs = await doc_grounding.prepare_async(settings, route, prompt, recent_users,
                                                         audited_event, mode=mode)
                def slot_fields(model):
                    # llama.cpp cache fields; {} for cloud providers.
                    return lambda tools: llama_request_fields(
                        settings, conversation=memory_scope, tools=tools, model=model)
                learned['grounding'] = docs
                if docs.block:
                    # First in the list: when room runs out earlier sections win, and these passages
                    # are the ones chosen for this exact question. The block carries its own markers.
                    turn_sections.insert(0, ('OFFICIAL DOCUMENTATION (untrusted reference data)', docs.block))
                # <<< STAR Knowledge
                # >>> Skill packs (star/skill_packs): short Roblox guidance, only for prompts that match, and
                # never in quick chat mode. It rides in the per-turn sections, after the documentation.
                packs = [] if quick else skill_packs.select(prompt)
                pack_block = skill_packs.render(packs)
                if pack_block:
                    turn_sections.insert(1 if docs.block else 0, (skill_packs.BLOCK_HEADING, pack_block))
                    audited_event({'event': 'skill_packs', 'names': [pack.name for pack in packs], 'chars': len(pack_block)})
                # <<< Skill packs
                kwargs = dict(client=client, model=route.model, prompt=prompt, image_paths=images,
                              project_memory=stable_memory(settings, memory.get(memory_scope)),
                              history=history,
                              preserve_history=True,
                              # Only the lessons section may look like lessons (guard_sections).
                              turn_sections=learning.guard_sections(turn_sections), mode=mode,
                              # The documentation block has its own budget (brain_router.GROUNDING_BUDGET);
                              # it is added on top so stored notes keep the room they had before.
                              turn_context_chars=min(3000 if quick else 10000, memory_limit) + len(docs.block) + len(document_block) + len(pack_block),
                              # Standing guidance for every tool-using turn (the short
                              # plain-chat rules carry their own Roblox line).
                              guidance=ROBLOX_QUALITY_NOTES,
                              request_extras=slot_fields(route.model),
                              tool_memory=tools_kept, helper_client=helper,
                              image_max_side=picture_limit(settings),
                              max_calls=route.max_calls,
                              context_chars=allowed_context_chars,
                              checkpoint=lambda s: memory.put(memory_scope, s), on_event=audited_event,
                              workspace=workspace, workspace_edit=settings.workspace_edit and use_tools,
                              stream_tokens=stream_tokens, response_tokens=route.response_tokens,
                              subagent_model=route.subagent_model,
                              web_search_enabled=bool(research and mode == 'agent'),
                              subagents_enabled=(mode == 'agent'),
                              subagent_parallelism=limits.parallel,
                              github_enabled=bool(mode == 'agent' and github_enabled),
                              intelligence=intelligence, mcp_gateway=mcp_gateway,
                              tool_workshop=workshop, specialists=specialists)
                if document_tools is not None:
                    kwargs['document_tools'] = document_tools
                audited_event({'event': 'model_started'})
                async def answer_with(model):
                    nonlocal prepared_conversation
                    window, candidate = history_window, None
                    for attempt in range(5):
                        candidate = await conversation_memory.prepare(
                            helper, model, home / 'conversations.sqlite3', settings.project, chat_id,
                            conversation_records, window,
                            summary_chars=min(6000, max(700, allowed_context_chars // 4)),
                            cancel_event=cancel_event, on_event=audited_event, candidate=candidate)
                        kwargs.update(model=model, request_extras=slot_fields(model), history=window.messages,
                            project_memory=conversation_memory.compose_memory(
                                stable_memory(settings, memory.get(memory_scope)), candidate.checkpoint))
                        try:
                            if allow_studio:
                                from .local_mcp import connect_studio
                                # One guarded connection per attempt: a retry below happens only when
                                # nothing was sent to the model or to Studio, so nothing is replayed.
                                async with connect_studio(settings, home,
                                        studio_configuration_home=studio_configuration_home) as guarded:
                                    # The tool list is the connector's own, read now. What STAR may do in
                                    # the open place is decided in code from what that place is.
                                    discovered = guarded.discovered
                                    sections = list(kwargs.get('turn_sections') or ())
                                    # The verdict's text can quote the place; like every other section
                                    # it may not look like lessons (guard_sections).
                                    sections.extend(learning.guard_sections(
                                        [('ROBLOX STUDIO PLACE', guarded.verdict.reason)]))
                                    outcome = await execute(**{**kwargs, 'turn_sections': sections}, studio=guarded,
                                        discovered=discovered, studio_id=settings.studio_id,
                                        may_edit=guarded.verdict.editable,
                                        allow_luau=guarded.verdict.editable and settings.studio_luau)
                                    result = studio_loop.with_report(outcome, guarded)
                            else:
                                result = await execute(**kwargs)
                        except HistoryWindowPressure as pressure:
                            if pressure.dispatched or pressure.tool_actions_started:
                                raise conversation_memory.ConversationRetentionError(
                                    'Conversation context needs another recap after model/tool work; task stopped '
                                    'without replaying actions. Original dialogue and prefix checkpoint are unchanged.')
                            if pressure.dropped != window.messages[:len(pressure.dropped)]:
                                raise conversation_memory.ConversationRetentionError(
                                    'Request pressure does not match complete original exchanges; task stopped.')
                            if attempt == 4:
                                raise conversation_memory.ConversationRetentionError(
                                    'Conversation preparation exceeded four budget retries; task stopped '
                                    'with originals and the previous prefix checkpoint unchanged.')
                            window = conversation_memory.omit_messages(window, len(pressure.dropped))
                            continue
                        prepared_conversation = candidate
                        return result
                used = route
                try:
                    result = await answer_with(route.model)
                except Exception as exc:
                    # A role's model that is missing or will not load: answer with the single
                    # configured model instead, once, and only if nothing was shown or run yet.
                    if (kind != 'lan' or route.model == settings.model or first_visible_token
                            or tools_ran or not model_unavailable(exc)):
                        raise
                    server_roles.mark_failed(settings, route.model)
                    used = replace(route, model=settings.model, subagent_model=(
                        settings.model if route.subagent_model == route.model else route.subagent_model))
                    if specialists is not None:
                        specialists.model = used.subagent_model
                    kwargs.update(subagent_model=used.subagent_model)
                    audited_event({'event': 'route_fallback', 'model': settings.model})
                    result = await answer_with(settings.model)
                # STAR Knowledge: static Luau check of the answer's code, then the sources list.
                return await doc_grounding.finalize(docs, used, result, model_client=helper, prompt=prompt,
                                                    started=started, on_event=audited_event)
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
            advice = ('Try Fast mode or a smaller prompt, or raise the STAR Server timeout in Settings.'
                      if provider_kind(settings) == 'lan' else
                      'Try Fast mode, a smaller prompt, or a hosted provider.')
            raise TimeoutError(f'STAR exceeded its {task_timeout}s task budget. {advice}') from exc
        first = token_timing['first']
        last = token_timing['last']
        requested = token_timing['requested']
        # Stream chunks do not always map 1:1 to tokens. Without usage metadata
        # throughput is explicitly marked approximate rather than claiming exact tokens.
        measured_first = (instant_answer.first_token_ms if instant_answer is not None else
                          max(0, int((first - requested) * 1000)) if first is not None and requested is not None else None)
        throughput = (instant_answer.tokens_per_second if instant_answer is not None else
                      round(max(0, len(re.findall(r"\w+|[^\w\s]", answer)) - 1)
                            / max(0.001, last - first), 1)
                      if first is not None and last is not None else None)
        brain = ('pc' if instant_answer is not None or kind == 'local'
                 else 'server' if kind == 'lan' else 'cloud')
        stats = {'brain': brain, 'model': answered_by or route.model,
                 'first_token_ms': measured_first, 'tokens_per_second': throughput,
                 'estimated_tokens': instant_answer.estimated_tokens if instant_answer is not None else True}
        audited_event({'event': 'answer_stats', **stats})
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        runs = home / 'runs' / stamp
        runs.mkdir(parents=True, exist_ok=True)
        (runs / 'transcript.json').write_text(json.dumps(redact_for_logs({
            'messages': msgs, 'archive': archive,
            # Which model was asked and which one the server said answered.
            'route': {'profile': route.profile, 'requested_model': route.model,
                      'answered_model': answered_by or route.model},
            'answer_stats': stats}), ensure_ascii=False, default=str), encoding='utf-8')
        (runs / 'answer.md').write_text(answer, encoding='utf-8')
        memory.event(memory_scope, {'run_id': stamp, 'answer': answer[:10000]})
        # Failed/cancelled answers, budget refusals and required archive/log
        # failures never advance retention. Validate source/CAS after persistence.
        if prepared_conversation is not None:
            conversation_memory.commit(home / 'conversations.sqlite3', prepared_conversation,
                                       cancel_event=cancel_event)
        audited_event({'event': 'saved', 'run_id': stamp})
        metrics.record(settings.project, 'run_succeeded',elapsed_ms=int((time.monotonic()-started)*1000))
        # The answer exists: count the lessons that were in its context, then learn from the turn.
        try:
            lesson_store.mark_used(settings.project, recalled)
        except Exception:
            pass
        learned['messages'] = msgs
        learn_from_turn()
        return answer
    except Exception as exc:
        metrics.record(settings.project, 'run_failed', elapsed_ms=int((time.monotonic()-started)*1000),
                       detail=type(exc).__name__)
        # A stated preference is still the owner's even when this turn failed or was stopped.
        learn_from_turn()
        raise
    finally:
        if document_store is not None:
            document_store.close()
        if workshop is not None:
            workshop.close()
        knowledge.close()
        memory.close()
        metrics.close()
