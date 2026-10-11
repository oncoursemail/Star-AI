"""STAR React Desktop shell and narrowly exposed Qt WebChannel service.

React is bundled locally under frontend/dist, never loaded from a remote site.
Every privileged action stays behind this explicit Python command registry.
The existing persistent SQLite files, model install paths, and Roblox MCP
adapters are reused without migration or credential exposure to JavaScript.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid

from .desktop_core import Settings, Conversations, app_data, run_task, query_models, check_studio
from .analytics import get_dashboard
from .brain_setup import BrainInstall, install_brain
from .local_runtime import Runtime
from .version import __version__
from .build_info import read_build_info
from .intelligence import for_settings
from .providers import credential_status, save_api_key, clear_api_key, provider_kind
from .model_health import (explain_model_failure, missing_model_message, note_server_result,
                           probe_server, server_status)
from .chat_images import chat_image, generate_chat_image
from .warmup import Warmer
from .diagnostics import export_review_bundle
from .mcp_connections import MCPGateway
from .tool_workshop import ToolWorkshop
from .voice.bridge import VOICE_ACTIONS, VoiceBridge
from .lessons import LESSON_ACTIONS, handle_action as handle_lesson_action, learning_status, write_export
from .lesson_digest import Digester, may_start_automatic

ALLOWED_ACTIONS = frozenset({
    'bootstrap','switchProject','pickFiles','sendMessage','saveSettings',
    'installBrain','startBrain','listModels','testModel','discoverStudio',
    'checkUpdates','installUpdate','transcribe','openDataFolder', 'copyText', 'openLegacy', 'selectFolder',
    'generateImage','saveProviderKey','clearProviderKey','cancelMessage','exportReviewBundle',
    'newChat','switchChat','testMcpConnection','runTeam','rememberDecision','listLearning',
    'listCustomTools','previewCustomTool','approveCustomTool','disableCustomTool',
    'startModelRouter','stopBrain','testModelTeam','testServer','warmUp',
})
# Voice calls keep their own action list (star/voice/bridge.py, docs/STAR_VOICE_CALLS.md).
ALLOWED_ACTIONS = ALLOWED_ACTIONS | VOICE_ACTIONS
# Learning: review of lessons and thumbs on answers (star/lessons.py), plus the optional
# background rewording of raw captures (star/lesson_digest.py).
ALLOWED_ACTIONS = ALLOWED_ACTIONS | LESSON_ACTIONS | {'digestLessons'}

# A background warm-up (server check + prompt-cache priming) gives way at once to
# anything that talks to the model server or changes what it would talk to.
WARM_UP_STOPPERS = frozenset({
    'sendMessage','runTeam','generateImage','testServer','testModel','testModelTeam','listModels',
    'startModelRouter','stopBrain','startBrain','installBrain','saveSettings','switchProject',
    'saveProviderKey','clearProviderKey','newChat','switchChat',
})

# Settings the React interface may change. Never a credential: provider and
# server keys go straight to the OS keyring through saveProviderKey.
PERMITTED_SETTINGS = frozenset({
    'endpoint','model','fast_model','reasoning_model','roblox_model','vision_model',
    'router_models_dir','router_context','gpu_layers','roblox_research_enabled',
    'tool_workshop_enabled','specialists_enabled','specialist_parallelism','provider',
    'project','workspace','studio_id','studio_edit','workspace_edit','max_calls',
    'context_chars','reduced_motion','comfy_workflow','comfy_prompt_node','comfy_port',
    'obsidian_vault','obsidian_enabled','skills_enabled','graphify_enabled',
    'mcp_graphify_docs','mcp_graphify_local','mcp_graphify_port','mcp_obsidian_live',
    'server_endpoint','server_timeout','server_parallel','server_context_tokens',
    'knowledge_endpoint',
    'learning_auto_accept','learning_digest','learning_digest_cloud',
})


def apply_setting_changes(settings: Settings, changes: dict) -> Settings:
    """Copy only allowlisted fields from the interface onto saved settings."""
    if not isinstance(changes, dict):
        raise ValueError('Invalid settings')
    for key, value in changes.items():
        if key in PERMITTED_SETTINGS:
            setattr(settings, key, value)
    return settings


def server_settings_for(action: str, settings_file: Path) -> Settings | None:
    """Saved settings when `action` talks to the selected STAR Server, else None."""
    if action not in {'sendMessage','testModel','listModels','runTeam','testModelTeam'}:
        return None
    try:
        current = Settings.load(settings_file)
        return current if provider_kind(current) == 'lan' else None
    except Exception:
        return None


def describe_failure(action: str, exc: Exception, settings_file: Path) -> str:
    """One short, secret-free line for the interface when a worker fails."""
    model_error = (getattr(exc, 'status_code', None) is not None
                   or type(exc).__name__ in {'APIConnectionError', 'APITimeoutError'}
                   or 'System message must be at the beginning' in str(exc))
    server = server_settings_for(action, settings_file)
    if server is not None:
        import httpx
        if model_error or isinstance(exc, httpx.HTTPError):
            status = getattr(exc, 'status_code', None)
            if status is None or status in (401, 403, 503):
                # Unreachable, timed out, wrong key or still loading: the status
                # light should stop claiming the server is ready.
                note_server_result(server, False, 'request_failed')
            return explain_model_failure(exc, provider_kind='lan')
    elif action in {'sendMessage', 'startBrain', 'testModel'} and model_error:
        return explain_model_failure(exc)
    return f'{type(exc).__name__}: {str(exc)[:350]}'


def react_index(root: Path | None = None) -> Path:
    """Resolve the static SPA from either source checkout or PyInstaller bundle."""
    base = root or Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return Path(base) / 'frontend' / 'dist' / 'index.html'


_SPECIALIST_ROLES = frozenset({'planner','research','luau','ui','animation',
                               'environment','review','integration'})
_TEAM_STAGES = frozenset({'evidence','design','critic','synthesis'})
_ROUTE_PROFILES = frozenset({'fast','reasoning','roblox','vision','research','agent'})
_STEP_STATES = {'completed':'done','done':'done','failed':'failed','blocked':'blocked',
                'cancelled':'cancelled'}
_TOOL_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,47}')
# A model id as a server or provider names it ("star-voice", "openai/gpt-oss-20b"). Shown as
# plain text in the status popover and the activity record; anything else is not forwarded.
_MODEL_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/+-]{0,79}')


def _model_name(value):
    return value if isinstance(value, str) and _MODEL_NAME.fullmatch(value) else None


def _opaque_id(value) -> str:
    """Stable row key for the activity view that never reveals a model-authored id."""
    return 't' + hashlib.sha256(str(value).encode('utf-8', 'replace')).hexdigest()[:10]


def _bounded_int(value, top: int):
    return value if type(value) is int and 0 <= value <= top else None


def sanitize_event(event: dict) -> dict:
    """Never forward raw tool results/secret tokens to an unrestricted webpage.

    `phase` stays a short human sentence. `activity` is the structured form the
    chat's activity timeline renders: only enumerated kinds, states and roles,
    bounded integers, an opaque step key, and the name of a tool that already
    passed authorization. Goals, arguments, outputs and model-authored task ids
    are never included.
    """
    kind = str(event.get('event', 'working'))[:36]
    if kind == 'team_planned':
        steps = []
        tasks = event.get('tasks')
        for item in (tasks if isinstance(tasks, list) else [])[:8]:
            if not isinstance(item, dict) or item.get('id') not in _TEAM_STAGES:
                continue
            needs = item.get('dependencies')
            steps.append({
                'id': item['id'],
                'role': item.get('role') if item.get('role') in _SPECIALIST_ROLES else 'research',
                'needs': [d for d in (needs if isinstance(needs, (list, tuple)) else ())[:8]
                          if d in _TEAM_STAGES],
            })
        return {'phase': 'STAR Teams: plan ready',
                'activity': {'type': 'plan', 'group': 'team', 'steps': steps}}
    if kind in {'agent_started','agent_finished','agent_blocked'}:
        role=str(event.get('role','agent'))[:24]
        if role not in _SPECIALIST_ROLES:
            role='agent'
        status=str(event.get('status','working'))[:18]
        task=event.get('task')
        state=('running' if kind == 'agent_started' else 'blocked' if kind == 'agent_blocked'
               else _STEP_STATES.get(status, 'failed'))
        activity={'type':'agent','group':'team',
                  'id':task if task in _TEAM_STAGES else _opaque_id(task),
                  'role':role if role != 'agent' else 'specialist','state':state}
        elapsed=_bounded_int(event.get('elapsed_ms'), 3_600_000)
        if kind == 'agent_finished' and elapsed is not None:
            activity['elapsed_ms']=elapsed
        return {'phase':f'STAR Teams: {role} — {state if kind != "agent_started" else "working"}',
                'activity':activity}
    if kind == 'assistant_delta':
        return {'phase':'Generating response', 'delta':str(event.get('text',''))[:2500]}
    if kind in {'subagent_started','subagent_finished'}:
        role=str(event.get('role','research'))[:30]
        if role not in _SPECIALIST_ROLES:
            role='research'
        status='working' if kind=='subagent_started' else str(event.get('status','done'))[:16]
        if kind == 'subagent_finished' and status not in _STEP_STATES:
            status='failed'
        state='running' if kind == 'subagent_started' else _STEP_STATES[status]
        return {'phase':f'STAR {role} specialist · {status}',
                'activity':{'type':'agent','group':'specialist',
                            'id':_opaque_id(event.get('task_id')),'role':role,'state':state}}
    if kind == 'route_selected':
        activity={'type':'route'}
        if event.get('profile') in _ROUTE_PROFILES:
            activity['profile']=event['profile']
        if _model_name(event.get('model')):
            activity['model']=event['model']       # the model this message is sent to
        return {'phase': 'STAR · ' + str(event.get('description', 'Selecting model'))[:90],
                'activity':activity}
    if kind == 'route_fallback':
        # The model chosen for this job is missing or did not load; the configured one answers.
        activity={'type':'route','fallback':True}
        if _model_name(event.get('model')):
            activity['model']=event['model']
        return {'phase':'That model is not available. Using your main model','activity':activity}
    if kind == 'model_answered':
        # The model name the server itself reported on the answer.
        activity={'type':'model'}
        if _model_name(event.get('model')):
            activity['model']=event['model']
        return {'phase':'Finishing the answer','activity':activity}
    if kind in {'search_started','search_finished'}:
        started = kind == 'search_started'
        return {'phase':'Searching the web' if started else 'Web search finished',
                'activity':{'type':'search','state':'running' if started else 'done'}}
    if kind in {'knowledge_started','knowledge_finished'}:
        # Official documentation lookup on STAR Server. Only a state and two bounded numbers
        # leave the host; the query and the passages never do.
        state=str(event.get('state',''))
        activity={'type':'docs','state':'running' if kind == 'knowledge_started'
                  else 'done' if state in {'ok','empty'} else 'failed'}
        for key,top in (('passages',10),('elapsed_ms',600_000)):
            count=_bounded_int(event.get(key), top)
            if kind == 'knowledge_finished' and count is not None:
                activity[key]=count
        return {'phase':'Reading the official documentation' if kind == 'knowledge_started'
                else 'Documentation ready' if activity['state'] == 'done' else 'Documentation unavailable',
                'activity':activity}
    if kind in {'luau_check_started','luau_repair_started','luau_check_finished'}:
        state=str(event.get('state',''))
        result=state if state in {'passed','failed','repaired','unavailable'} else ''
        activity={'type':'luau_check','state':'running' if kind != 'luau_check_finished'
                  else 'failed' if result in {'failed','unavailable'} else 'done'}
        if kind == 'luau_check_finished' and result:
            activity['result']=result
        if kind == 'luau_repair_started':
            activity['repair']=True
        return {'phase':'Fixing the Luau code' if kind == 'luau_repair_started' else 'Checking the Luau code'
                if kind == 'luau_check_started' else 'Luau check finished','activity':activity}
    if kind == 'model_turn':
        activity={'type':'turn'}
        for key in ('step','max_steps'):
            count=_bounded_int(event.get(key), 64)
            if count:
                activity[key]=count
        return {'phase':'Thinking','activity':activity}
    if kind == 'finished':
        activity={'type':'finished'}
        for key in ('model_calls','tool_calls'):
            count=_bounded_int(event.get(key), 999)
            if count is not None:
                activity[key]=count
        return {'phase':'Finishing the answer','activity':activity}
    if kind in {'saved','run_completed'}:
        return {'phase':'Saving verified task record','activity':{'type':'saved'}}
    if kind in {'tool_started','tool_finished','tool_rejected'}:
        state=('running' if kind == 'tool_started' else 'blocked' if kind == 'tool_rejected'
               else 'failed' if event.get('is_error') else 'done')
        activity={'type':'tool','state':state}
        name=event.get('tool')
        # A rejected name never passed authorization and may be invented by the model.
        if kind != 'tool_rejected' and isinstance(name, str) and _TOOL_NAME.fullmatch(name):
            activity['tool']=name
        return {'phase':'A tool request was not permitted' if kind == 'tool_rejected'
                else 'Using an authorized local tool','activity':activity}
    if kind in {'tool_call','tool_result','tool_output'}:
        return {'phase':'Using an authorized local tool'}
    if kind == 'model_responding':
        # First streamed chunk: the server has read the prompt and started to write.
        return {'phase':'The model is writing'}
    if kind == 'tool_requested':
        # The model began to write a tool call. Nothing is authorized or run yet, so no name.
        return {'phase':'Preparing a tool request'}
    if kind == 'model_started':
        # Routing and context are ready; the request goes out next (after Studio connects, if it is used).
        return {'phase':'Contacting the model'}
    # An event without wording of its own still reads as a sentence, never as an internal name.
    return {'phase':'STAR is working'}


# Bridge actions that save a user message first and then try to answer it.
TURN_ACTIONS = frozenset({'sendMessage', 'generateImage', 'runTeam'})


@dataclass(frozen=True)
class TurnRef:
    """The saved user message a running turn answers (set once that message is stored)."""
    project: str
    chat_id: str
    user_id: int


def failure_outcome(action: str, exc: Exception, *, cancelled: bool = False,
                    settings_file: Path | None = None) -> tuple[str, str]:
    """Return ``(status, user_message)`` for a worker that raised.

    status is 'cancelled' when the user pressed Stop (or the error says so) and
    'failed' otherwise. The message is what the UI shows and what is stored.
    """
    from .model_health import explain_model_failure
    if cancelled or 'cancelled by user' in str(exc).lower():
        return 'cancelled', explain_model_failure(RuntimeError('cancelled by user'))
    if settings_file is not None:
        # Provider-aware wording (STAR Server vs local brain) and the server status light.
        return 'failed', describe_failure(action, exc, settings_file)
    if (action in {'sendMessage', 'startBrain', 'testModel'}
            and (getattr(exc, 'status_code', None) is not None
                 or type(exc).__name__ in {'APIConnectionError', 'APITimeoutError'}
                 or 'System message must be at the beginning' in str(exc))):
        return 'failed', explain_model_failure(exc)
    return 'failed', f'{type(exc).__name__}: {str(exc)[:350]}'


def record_turn_failure(home: Path, turn: TurnRef, status: str, detail: str) -> bool:
    """Persist the terminal record of a turn that ended without an answer.

    Never raises: a storage problem must not hide the original error from the UI.
    """
    try:
        chats = Conversations(home / 'conversations.sqlite3')
        try:
            chats.add_terminal(turn.project, turn.chat_id, turn.user_id, status, detail)
        finally:
            chats.close()
        return True
    except Exception:
        return False


def run_worker(request_id: str, action: str, worker, *, emit, home: Path,
               current_turn, cancelled, settings_file: Path | None = None) -> None:
    """Run one bridge worker and emit exactly one result or error event.

    A failed or cancelled chat/image/team turn is stored BEFORE its error event is
    emitted, so a reload or restart shows the same history the UI just displayed.
    """
    try:
        data = worker()
    except Exception as exc:
        status, detail = failure_outcome(action, exc, cancelled=bool(cancelled()),
                                         settings_file=settings_file)
        turn = current_turn() if action in TURN_ACTIONS else None
        if turn is not None:
            record_turn_failure(home, turn, status, detail)
        emit(request_id, 'error', detail)
        return
    try:
        emit(request_id, 'result', data)
    except Exception as exc:
        emit(request_id, 'error', f'{type(exc).__name__}: {str(exc)[:350]}')


def file_allowed(path: Path, approved: set[Path]) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if resolved not in approved:
        raise PermissionError('Choose the file through STAR Attach before using it')
    if resolved.stat().st_size > 700_000_000:
        raise ValueError('Media file exceeds the supported size limit')
    return resolved


def _get_state(settings_file: Path, runtime: Runtime, busy: bool = False) -> dict:
    settings = Settings.load(settings_file)
    home = app_data()
    chats = Conversations(home / 'conversations.sqlite3')
    try:
        active_chat = chats.active_chat(settings.project)
        chat_threads = chats.list_chats(settings.project)
        recent = chats.recent_records(settings.project, limit=80, chat_id=active_chat)
        retry = chats.retry_state(settings.project, active_chat, busy=busy)
        projects = sorted(set(chats.projects() + [settings.project]))
    finally:
        chats.close()
    messages = []
    for i, record in enumerate(recent):
        role, body, created = record['role'], record['body'], record['created']
        entry = {'id':f'saved-{i}', 'role':role,'text':body,'created':created}
        if role == 'assistant':
            # The stored row id lets the owner rate this answer; `feedback` is their current thumb.
            entry['mid'] = record['id']
            if record['feedback']:
                entry['feedback'] = record['feedback']
        if record['status'] != 'complete':
            entry['status'] = record['status']  # 'failed' | 'cancelled' terminal record
        preview = chat_image(home, body) if role == 'assistant' else None
        if preview:
            entry.update(preview)
        messages.append(entry)
    brain = BrainInstall.load(home / 'brain.json')
    workshop = ToolWorkshop(home=home,project=settings.project)
    try:
        tool_workshop_status=workshop.status()
    finally:
        workshop.close()
    return {
        'version':__version__,'build':read_build_info(),'project':settings.project,'projects':projects,
        'messages':messages,'active_chat':active_chat,'chats':chat_threads,
        'retry':retry,
        'settings':asdict(settings),
        'brain_installed':brain is not None,'brain_running':runtime.status()=='running',
        'model_router_running':runtime.router_running(),
        'tool_workshop':tool_workshop_status,
        'analytics':get_dashboard(home,settings.project),
        'learning':learning_status(home,settings.project),
        'credentials':credential_status(),
        'server':server_status(settings),
        'intelligence':for_settings(settings,home).status(),
        'mcp':MCPGateway(settings).status(),
        'release_url':'https://github.com/oncoursemail/Star-AI/releases/latest',
    }


def launch():
    try:
        from PySide6.QtCore import QObject, QUrl, Slot, Signal, Qt, QTimer
        from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWebEngineCore import QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebChannel import QWebChannel
    except ImportError as exc:
        raise RuntimeError('Install STAR desktop requirements including PySide6 WebEngine') from exc

    index = react_index()
    if not index.is_file():
        raise FileNotFoundError(
            f'STAR React UI not built at {index}. Run `cd frontend && npm install && npm run build` first. '
            'The Windows release workflow builds the interface automatically.'
        )

    class RestrictedPage(QWebEnginePage):
        def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
            if not is_main_frame:
                return True
            if url.isLocalFile():
                try:
                    urlpath = Path(url.toLocalFile()).resolve(strict=True)
                    if urlpath == index.resolve():
                        return True
                except OSError:
                    return False
            if url.scheme() == 'https' and url.host() in {'github.com','docs.github.com','create.roblox.com','huggingface.co'}:
                QDesktopServices.openUrl(url)
            return False

    class Bridge(QObject):
        event = Signal(str)
        shutdownRequested = Signal()
        def __init__(self, host):
            super().__init__()
            self.host = host
            self.settings_file = app_data() / 'settings.json'
            self.runtime = Runtime()
            self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='star-react')
            self.shutdownRequested.connect(QApplication.instance().quit)
            self.allowed_files: set[Path] = set()
            self.active_task = False
            self.cancel_chat = threading.Event()
            self.turn: TurnRef | None = None
            self.active_update = False
            self.warmer = Warmer()
            self.digester = Digester()
            self.voice = VoiceBridge(lambda call_id, data: self._emit(call_id, 'voice', data),
                                     settings_path=app_data() / 'voice.json', save_turn=self._save_voice_turn)

        def _warm_target(self):
            """What a message sent now would talk to. Runs on the warm-up thread."""
            settings=Settings.load(self.settings_file)
            home=app_data()
            chat_id=None
            if (home/'conversations.sqlite3').is_file():
                chats=Conversations(home/'conversations.sqlite3')
                try: chat_id=chats.active_chat(settings.project)
                finally: chats.close()
            return settings,home,chat_id

        def _warm(self, request_id: str = '', check: bool = True, then=None):
            """Check the selected model server and prime its prompt cache, off the UI thread.

            It is not a turn: nothing is saved, `active_task` stays False, and any
            real request cancels it (see WARM_UP_STOPPERS). Cloud providers are skipped.
            `then(report)` runs on the warm-up thread once it has finished.
            """
            def finished(report):
                if request_id:self._emit(request_id,'result',report)
                if then is not None:then(report)
            self.warmer.start(
                self._warm_target, check=check,
                on_checked=(lambda report:self._emit(request_id,'progress',{'phase':'Server checked'})) if request_id else None,
                on_done=finished if (request_id or then is not None) else None)

        def _digest_target(self):
            settings=Settings.load(self.settings_file)
            return settings,app_data(),settings.project

        def _digest_when_idle(self, report=None):
            """After a turn and its cache warm-up: let the fast model reword raw captures into
            candidate lessons. Not a turn, never trusted output, and any real request stops it."""
            if not may_start_automatic(report,turn_running=self.active_task,voice_call=self._in_voice_call()):
                return
            self.digester.start(self._digest_target)

        def _in_voice_call(self):
            try:return bool(self.voice.handle('voiceStatus',{}).get('inCall'))
            except Exception:return False

        def _save_voice_turn(self, user_text: str, reply_text: str):
            # A call shows up in the active chat like typed messages do.
            settings = Settings.load(self.settings_file)
            chats = Conversations(app_data() / 'conversations.sqlite3')
            try:
                active_chat = chats.active_chat(settings.project)
                chats.add(settings.project, 'user', user_text, chat_id=active_chat)
                if reply_text:
                    chats.add(settings.project, 'assistant', reply_text, chat_id=active_chat)
            finally:
                chats.close()

        def _emit(self, request_id: str, kind: str, data):
            payload={'requestId':request_id,'kind':kind,'data':data}
            self.event.emit(json.dumps(payload,default=str))

        def _run(self, request_id: str, action: str, worker):
            def task():
                try:
                    run_worker(request_id, action, worker, emit=self._emit, home=app_data(),
                               current_turn=lambda: self.turn, cancelled=self.cancel_chat.is_set,
                               settings_file=self.settings_file)
                finally:
                    if action in TURN_ACTIONS:
                        self.turn=None
                        self.active_task=False
                    if action=='installUpdate':self.active_update=False
            self.pool.submit(task)

        def _start_brain(self, info: BrainInstall):
            # This helper performs an actual completion before changing settings
            # and stops a newly launched engine if validation fails.
            from .brain_runtime_health import start_verified_brain
            return start_verified_brain(
                self.runtime, info, self.settings_file, app_data())

        def _start_model_router(self):
            if self.active_task:
                raise RuntimeError('Stop the active chat before switching STAR models')
            # The helper refuses non-local providers and never switches the
            # owner away from STAR Server while the router is loading.
            from .brain_runtime_health import start_model_router
            info = BrainInstall.load(app_data()/'brain.json')
            source = info.executable if info is not None else Settings.load(self.settings_file).llama_server
            return start_model_router(self.runtime, self.settings_file, app_data(), source)

        def _run_chat(self, request_id, prompt, selected, mode='auto', research=False, github=False):
            home=app_data()
            settings=Settings.load(self.settings_file)
            if not settings.model.strip():
                raise ValueError(missing_model_message(settings))
            chats=Conversations(home/'conversations.sqlite3')
            try:
                active_chat=chats.active_chat(settings.project)
                user_id=chats.add(settings.project,'user',prompt,chat_id=active_chat)
            finally:
                chats.close()
            self.turn=TurnRef(settings.project,active_chat,user_id)
            from .media_features import VIDEO_EXTENSIONS,AUDIO_EXTENSIONS,video_frames,transcribe_audio
            pics=[];extras=[]
            with tempfile.TemporaryDirectory(prefix='star-media-') as directory:
                for path in selected:
                    if path.suffix.lower() in VIDEO_EXTENSIONS:
                        frames=video_frames(path,Path(directory)/('v_'+uuid.uuid4().hex),max_frames=4)
                        pics.extend(frames)
                        extras.append(f'Video source: {path.name}; {len(frames)} sampled frames (not full continuous understanding).')
                    elif path.suffix.lower() in AUDIO_EXTENSIONS:
                        extras.append(f'Audio transcript from {path.name}: {transcribe_audio(path)}')
                    else:
                        pics.append(path)
                if len(pics)>4:
                    pics=pics[:4]
                    extras.append('Only the first 4 visual attachments were sent to respect context limits.')
                full_prompt=prompt+('\n\n'+'\n'.join(extras) if extras else '')
                learned={}
                def relay(e):
                    # What the turn taught is reported with the result, not as a progress step.
                    if e.get('event')=='lessons_captured':
                        learned.update(accepted=int(e.get('accepted',0)),candidates=int(e.get('candidates',0)),
                                       replaced=int(e.get('replaced',0)),not_kept=int(e.get('not_kept',0)))
                        return
                    self._emit(request_id,'progress',sanitize_event(e))
                answer=run_task(settings,full_prompt,pics,on_event=relay,
                    stream_tokens=True, mode=mode, research=research, cancel_event=self.cancel_chat, github_enabled=github, chat_id=active_chat,
                    owner_text=prompt)
            if provider_kind(settings)=='lan':
                note_server_result(settings,True,'ok')
            chats=Conversations(home/'conversations.sqlite3')
            try:
                chats.add(settings.project,'assistant',answer,chat_id=active_chat)
            finally:
                chats.close()
            # While the owner reads the answer, let the server read it too: the next
            # message then starts from a fully cached conversation. Cancelled by any request.
            # Once that is done the server is idle, which is when raw captures get reworded.
            self._warm(check=False,then=self._digest_when_idle)
            return {'answer':answer,'learned':learned} if learned else {'answer':answer}

        def _run_image(self, request_id, prompt):
            settings=Settings.load(self.settings_file)
            home=app_data()
            self._emit(request_id,'progress',{'phase':'Generating image using local ComfyUI…'})
            chats=Conversations(home/'conversations.sqlite3')
            try:
                active_chat=chats.active_chat(settings.project)
                user_id=chats.add(settings.project,'user',prompt,chat_id=active_chat)
            finally:
                chats.close()
            self.turn=TurnRef(settings.project,active_chat,user_id)
            chat_id = active_chat
            result=generate_chat_image(settings,prompt,home,cancel_event=self.cancel_chat)
            chats=Conversations(home/'conversations.sqlite3')
            try:
                chats.add(settings.project,'assistant',result['message'],chat_id=chat_id)
            finally:
                chats.close()
            return {'answer':result['answer'],'image':result['image']}

        def _run_team(self, request_id: str, prompt: str):
            """One user request, four bounded read-only specialists, one stored answer."""
            from .team_service import run_research_team
            import asyncio
            home = app_data()
            settings = Settings.load(self.settings_file)
            if not settings.model.strip():
                raise ValueError(missing_model_message(settings, teams=True))
            if provider_kind(settings) == 'cloud':
                raise ValueError('STAR Teams runs on your own hardware. Select On-device or STAR Server as the provider.')
            chats = Conversations(home / "conversations.sqlite3")
            try:
                active_chat = chats.active_chat(settings.project)
                user_id = chats.add(settings.project, "user", prompt, chat_id=active_chat)
            finally:
                chats.close()
            self.turn = TurnRef(settings.project, active_chat, user_id)
            from .team_cancellation import run_until_cancelled
            async def run():
                return await run_until_cancelled(
                    run_research_team(
                        settings=settings, prompt=prompt, home=home,
                        on_event=lambda event: self._emit(
                            request_id, 'progress', sanitize_event(event)),
                    ),
                    is_cancelled=self.cancel_chat.is_set,
                )
            answer, team = asyncio.run(run())
            chats = Conversations(home / "conversations.sqlite3")
            try:
                chats.add(settings.project, "assistant", answer, chat_id=active_chat)
            finally:
                chats.close()
            return {
                "answer": answer,
                "agents": len(team.results),
                "peak_concurrency": team.peak_concurrency,
                "elapsed_ms": team.elapsed_ms,
            }

        @Slot(str,result=str)
        def invoke(self, raw: str) -> str:
            try:
                if len(raw)>100000:
                    raise ValueError('Request is too large')
                body=json.loads(raw)
                if not isinstance(body,dict):raise ValueError('Invalid request')
                action=body.get('action')
                if action not in ALLOWED_ACTIONS:raise PermissionError('Action not permitted')
                rid=str(body.get('requestId',''))[:80]
                if action in WARM_UP_STOPPERS:self.warmer.cancel()
                if action in WARM_UP_STOPPERS or action in VOICE_ACTIONS:self.digester.cancel()
                if action=='warmUp':
                    if self.active_task:
                        return json.dumps({'ok':True,'data':{'primed':False,'skipped':'busy'}})
                    self._warm(rid)
                    return json.dumps({'ok':True,'pending':True,'requestId':rid})
                if action in VOICE_ACTIONS:
                    return json.dumps({'ok':True,'data':self.voice.handle(action, body, rid)})
                if action=='bootstrap':return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime,busy=self.active_task)})
                if action=='pickFiles':
                    from .media_features import AUDIO_EXTENSIONS
                    kind=body.get('kind')
                    if kind=='audio':
                        names, _=QFileDialog.getOpenFileNames(self.host,'Select audio references','','Audio files (*.wav *.mp3 *.m4a *.flac *.ogg *.aac)')
                    else:
                        names, _=QFileDialog.getOpenFileNames(self.host,'Attach references','','Media (*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.mkv *.webm *.avi *.wav *.mp3 *.m4a *.flac *.ogg *.aac)')
                    picked=[]
                    for name in names[:8]:
                        path=Path(name).resolve(strict=True)
                        if path.is_file() and path.stat().st_size<=700_000_000:
                            self.allowed_files.add(path)
                            picked.append(str(path))
                    return json.dumps({'ok':True,'data':picked})
                if action=='switchProject':
                    project=str(body.get('project','')).strip()
                    if not project or len(project)>60 or any(ch in project for ch in '\\/:*?"<>|\x00'):
                        raise ValueError('Project name must be 1–60 characters without path separators')
                    settings=Settings.load(self.settings_file)
                    settings.project=project;settings.save(self.settings_file)
                    return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime,busy=self.active_task)})
                if action=='newChat':
                    if self.active_task:raise RuntimeError('Wait for the current answer before starting a new chat')
                    settings=Settings.load(self.settings_file)
                    conversations=Conversations(app_data()/'conversations.sqlite3')
                    try: conversations.new_chat(settings.project)
                    finally: conversations.close()
                    self._warm(check=False)
                    return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime)})
                if action=='switchChat':
                    if self.active_task:raise RuntimeError('Wait for the current answer before switching chats')
                    chat_id=str(body.get('chatId',''))[:80]
                    settings=Settings.load(self.settings_file)
                    conversations=Conversations(app_data()/'conversations.sqlite3')
                    try: conversations.switch_chat(settings.project,chat_id)
                    finally: conversations.close()
                    self._warm(check=False)
                    return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime)})
                if action in LESSON_ACTIONS:
                    # Review, export and feedback are explicit owner actions in the interface.
                    settings=Settings.load(self.settings_file)
                    data=handle_lesson_action(app_data(),settings.project,action,body)
                    if action=='exportLessons':
                        # The file goes where the owner chooses, like the review bundle.
                        name=re.sub(r'[^A-Za-z0-9._-]+','-',settings.project).strip('-') or 'project'
                        suggested=str(Path.home()/f"STAR-lessons-{name}-{time.strftime('%Y%m%d',time.gmtime())}.json")
                        filename,_=QFileDialog.getSaveFileName(self.host,'Export lessons',suggested,'JSON (*.json)')
                        if not filename:
                            return json.dumps({'ok':True,'data':{'cancelled':True}})
                        data=write_export(Path(filename),data)
                    return json.dumps({'ok':True,'data':data},default=str)
                if action=='digestLessons':
                    # "Summarise now": the same background step, started by the owner for even one capture.
                    if self.active_task:raise RuntimeError('Wait for the current answer before summarising captures')
                    def digested(report):
                        self._emit(rid,'result',report)
                        # The chat's own model answered: prime its conversation cache again.
                        if report.get('shared_model') and not self.active_task:self._warm(check=False)
                    started=self.digester.start(self._digest_target,minimum=1,on_done=digested)
                    if started is None:raise RuntimeError('STAR is already summarising captures')
                    return json.dumps({'ok':True,'pending':True,'requestId':rid})
                if action=='rememberDecision':
                    from .learning import approve_learning
                    settings=Settings.load(self.settings_file)
                    receipt=approve_learning(
                        app_data(), project=settings.project,
                        text=body.get('text'),
                        kind=str(body.get('kind','decision')),
                        replaces_note_id=body.get('replaces_note_id'),
                        human_approved=body.get('approved') is True,
                    )
                    return json.dumps({'ok':True,'data':asdict(receipt)})
                if action=='listLearning':
                    from .knowledge import KnowledgeStore
                    settings=Settings.load(self.settings_file)
                    store=KnowledgeStore(app_data()/'knowledge')
                    try:
                        notes=[{'id':n.id,'kind':n.kind,'text':n.text[:1200],
                                'created':n.created,'source':n.source}
                               for n in store.find(settings.project,'',reviewed_only=True,limit=30)
                               if n.source=='user:explicit-approved-decision'][:12]
                    finally:
                        store.close()
                    return json.dumps({'ok':True,'data':{'notes':notes}})
                if action=='saveSettings':
                    old=apply_setting_changes(Settings.load(self.settings_file),body.get('settings'))
                    old.save(self.settings_file)
                    return json.dumps({'ok':True,'data':asdict(old)})
                if action=='saveProviderKey':
                    name=str(body.get('provider',''))
                    token=body.get('key','')
                    save_api_key(name,token)
                    return json.dumps({'ok':True,'data':{'connected':True}})
                if action=='clearProviderKey':
                    name=str(body.get('provider',''))
                    clear_api_key(name)
                    return json.dumps({'ok':True,'data':{'connected':False}})
                if action=='selectFolder':
                    selected=QFileDialog.getExistingDirectory(self.host, 'Choose a local notes or project folder')
                    return json.dumps({'ok':True,'data':{'path':str(selected) if selected else ''}})
                if action=='exportReviewBundle':
                    include_screen=body.get('includeScreenshot',False)
                    if type(include_screen) is not bool:
                        raise ValueError('Invalid screenshot selection')
                    stamp=time.strftime('%Y%m%d',time.gmtime())
                    suggested=str(Path.home()/f'STAR-review-v{__version__}-{stamp}.zip')
                    filename,_=QFileDialog.getSaveFileName(
                        self.host, 'Export STAR review bundle', suggested, 'ZIP archive (*.zip)')
                    if not filename:
                        return json.dumps({'ok':True,'data':{'cancelled':True}})
                    destination=Path(filename).expanduser()
                    if not destination.suffix:
                        destination=destination.with_suffix('.zip')
                    screenshot=None
                    if include_screen:
                        # Optional explicit screenshot may expose the currently visible
                        # chat, so the React option defaults to unchecked.
                        from PySide6.QtCore import QBuffer, QIODevice
                        buffer=QBuffer()
                        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                        if not self.host.view.grab().save(buffer,'PNG'):
                            buffer.close()
                            raise RuntimeError('Could not capture current screen')
                        screenshot=bytes(buffer.data())
                        buffer.close()
                    def worker():
                        result=export_review_bundle(
                            app_data(),Settings.load(self.settings_file),destination,
                            runtime_status=self.runtime.status(),screenshot_png=screenshot)
                        return {'filename':result.name,'screenshot_included':bool(screenshot),
                                'saved_to_user_selected_location':True}
                    self._run(rid,action,worker)
                    return json.dumps({'ok':True,'pending':True,'requestId':rid})
                if action=='openLegacy':
                    raise PermissionError('The legacy UI is diagnostic-only; start STAR.exe --legacy-ui explicitly if necessary.')
                if action=='copyText':
                    content=str(body.get('text',''))
                    if len(content)>300000:raise ValueError('Too much text')
                    QApplication.clipboard().setText(content)
                    return json.dumps({'ok':True,'data':True})
                if action=='openDataFolder':
                    path=app_data();path.mkdir(parents=True,exist_ok=True)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                    return json.dumps({'ok':True,'data':True})
                if action=='cancelMessage':
                    if self.active_task:
                        self.cancel_chat.set()
                    return json.dumps({'ok':True,'data':{'cancel_requested':self.active_task}})
                if action=='runTeam':
                    if self.active_task:raise RuntimeError('STAR is already handling a task')
                    prompt=str(body.get('prompt','')).strip()
                    if not 2 <= len(prompt) <= 12000:
                        raise ValueError('Team prompt must be 2–12,000 characters')
                    if body.get('files'):
                        raise ValueError('STAR Teams currently supports text only. Turn off Team mode to attach files.')
                    self.cancel_chat = threading.Event()
                    self.active_task=True
                    try:
                        self._run(rid,action,lambda:self._run_team(rid,prompt))
                    except Exception:
                        self.active_task=False
                        raise
                if action=='sendMessage':
                    if self.active_task:raise RuntimeError('STAR is already handling a task')
                    prompt=str(body.get('prompt','')).strip()
                    if not prompt or len(prompt)>30000:raise ValueError('Message must be 1–30,000 characters')
                    files=body.get('files') or []
                    if not isinstance(files,list) or len(files)>8:raise ValueError('Too many attachments')
                    selected=[file_allowed(Path(str(f)),self.allowed_files) for f in files]
                    mode=body.get('mode','auto')
                    if mode not in ('fast','auto','agent'):
                        raise ValueError('Choose Fast, Auto, or Agent mode')
                    research=body.get('research',False)
                    if not isinstance(research,bool):
                        raise ValueError('Invalid research flag')
                    github=body.get('github',False)
                    if not isinstance(github,bool) or (github and mode != 'agent'):
                        raise ValueError('GitHub inspection requires Agent mode')
                    self.cancel_chat = threading.Event()
                    self.active_task=True
                    try:
                        self._run(rid,action,lambda:self._run_chat(rid,prompt,selected,mode=mode,research=research,github=github))
                    except Exception:
                        self.active_task=False
                        raise
                elif action=='generateImage':
                    if self.active_task:raise RuntimeError('STAR is already handling a task')
                    prompt=str(body.get('prompt','')).strip()
                    if not 1<=len(prompt)<=1500:raise ValueError('Image prompt must be 1–1500 characters')
                    self.active_task=True
                    self.cancel_chat = threading.Event()
                    try:
                        self._run(rid,action,lambda:self._run_image(rid,prompt))
                    except Exception:
                        self.active_task=False
                        raise
                elif action=='installBrain':
                    def worker():
                        info=install_brain(app_data(),progress=lambda e:self._emit(rid,'progress',e))
                        return self._start_brain(info)
                    self._run(rid,action,worker)
                elif action=='startBrain':
                    def worker():
                        info=BrainInstall.load(app_data()/'brain.json')
                        if info is None:raise RuntimeError('Download STAR Brain first')
                        return self._start_brain(info)
                    self._run(rid,action,worker)
                elif action=='startModelRouter':
                    if self.active_task:
                        raise RuntimeError('Stop the current chat before switching models')
                    self._run(rid,action,self._start_model_router)
                elif action=='stopBrain':
                    if self.active_task:
                        raise RuntimeError('Stop the current task before stopping the model server')
                    if self.runtime.status() != 'running':
                        return json.dumps({'ok':True,'data':{'stopped':False}})
                    self._run(rid,action,lambda:(self.runtime.stop() or {'stopped':True}))
                elif action=='testModelTeam':
                    if self.active_task:
                        raise RuntimeError('Finish the current chat before testing other models')
                    def worker():
                        import asyncio
                        from .model_fleet import check_configured_team
                        return asyncio.run(check_configured_team(
                            Settings.load(self.settings_file),
                            on_progress=lambda e:self._emit(rid,'progress',e)))
                    self._run(rid,action,worker)
                elif action=='testServer':
                    # Timed health -> key -> limits -> tiny chat check of the saved
                    # STAR Server. The key stays in the keyring; only step names,
                    # timings and model IDs go back to the interface.
                    self._run(rid,action,lambda:probe_server(Settings.load(self.settings_file)))
                elif action=='listModels':
                    def worker():return {'models':query_models(Settings.load(self.settings_file))}
                    self._run(rid,action,worker)
                elif action=='testModel':
                    def worker():
                        import asyncio
                        from .model_health import probe_chat_endpoint
                        current=Settings.load(self.settings_file)
                        result=asyncio.run(probe_chat_endpoint(current))
                        if provider_kind(current)=='lan':
                            note_server_result(current,True,'ok')
                        return result
                    self._run(rid,action,worker)
                elif action in {'listCustomTools','previewCustomTool',
                                  'approveCustomTool','disableCustomTool'}:
                    identifier=body.get('id')
                    query=body.get('query')
                    if action!='listCustomTools' and (type(identifier) is not int or identifier<1):
                        raise ValueError('A valid custom tool ID is required')
                    def worker():
                        from .knowledge import KnowledgeStore
                        from .workspace import Workspace
                        current=Settings.load(self.settings_file)
                        if not current.tool_workshop_enabled:
                            raise PermissionError('Tool Workshop is disabled')
                        home=app_data()
                        knowledge=KnowledgeStore(home/'knowledge')
                        workshop=ToolWorkshop(home=home,project=current.project,
                            knowledge=knowledge,
                            workspace=Workspace(Path(current.workspace)) if current.workspace else None,
                            intelligence=for_settings(current,home))
                        try:
                            if action=='listCustomTools':
                                return workshop.catalog()
                            if action=='previewCustomTool':
                                return workshop.run(identifier,query,preview=True)
                            if action=='approveCustomTool':
                                return workshop.approve(identifier)
                            return workshop.disable(identifier)
                        finally:
                            workshop.close()
                            knowledge.close()
                    self._run(rid,action,worker)
                elif action=='testMcpConnection':
                    server=str(body.get('server',''))
                    if server not in {'graphify_docs','graphify_local','obsidian_live'}:
                        raise ValueError('Unknown MCP connector')
                    def worker():
                        import asyncio
                        gateway=MCPGateway(Settings.load(self.settings_file))
                        # Probe does not call any server tool or perform writes.
                        return asyncio.run(gateway.probe(server))
                    self._run(rid,action,worker)
                elif action=='discoverStudio':
                    self._run(rid,action,lambda:{'studios':check_studio()})
                elif action=='checkUpdates':
                    from .updates import get_latest
                    self._run(rid,action,lambda:asdict(get_latest()))
                elif action=='installUpdate':
                    from .updates import stage_installer, launch_installer, get_latest
                    if self.active_update:
                        raise RuntimeError('STAR is already installing an update')
                    self.active_update = True
                    def worker():
                        result=get_latest()
                        if not result.available:raise RuntimeError('No newer update is available')
                        self._emit(rid,'progress',{'phase':'Downloading and verifying STAR Setup','downloaded':0,'total':0})
                        candidate=stage_installer(result,app_data(),progress=lambda done,total:
                            self._emit(rid,'progress',{'phase':'Downloading verified update',
                                                      'downloaded':done,'total':total}))
                        self._emit(rid,'progress',{'phase':'SHA-256 verified — starting Windows Setup',
                                                  'downloaded':1,'total':1})
                        # Only checksum-verified GitHub assets may run unattended.
                        # Setup replaces the application and relaunches STAR; user data is outside {app}.
                        launch_installer(candidate,unattended=True)
                        self.shutdownRequested.emit()
                        return {'status':'launched_installer','version':candidate.version}
                    self._run(rid,action,worker)
                elif action=='transcribe':
                    path=file_allowed(Path(str(body.get('file',''))),self.allowed_files)
                    from .media_features import transcribe_audio
                    self._run(rid,action,lambda:{'text':transcribe_audio(path)})
                return json.dumps({'ok':True,'pending':True,'requestId':rid})
            except Exception as exc:
                return json.dumps({'ok':False,'error':f'{type(exc).__name__}: {str(exc)[:380]}'})

        def close(self):
            self.voice.close()
            self.cancel_chat.set()
            self.warmer.cancel()
            self.runtime.stop()
            self.pool.shutdown(wait=False,cancel_futures=True)

    class Shell(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f'STAR Intelligence — v{__version__}')
            self.resize(1440,900)
            self.setMinimumSize(920,650)
            self.view=QWebEngineView(self)
            self.page=RestrictedPage(self.view)
            self.view.setPage(self.page)
            self.setCentralWidget(self.view)
            self.channel=QWebChannel(self.view.page())
            self.bridge=Bridge(self)
            self.channel.registerObject('starBridge',self.bridge)
            self.view.page().setWebChannel(self.channel)
            url=QUrl.fromLocalFile(str(index.resolve()))
            url.setQuery('desktop=1')
            self.view.load(url)
        def closeEvent(self,event):
            self.bridge.close()
            return super().closeEvent(event)

    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('STAR Intelligence')
    app.setStyle('Fusion')
    shell=Shell()
    shell.show()
    return app.exec()
