"""STAR React Desktop shell and narrowly exposed Qt WebChannel service.

React is bundled locally under frontend/dist, never loaded from a remote site.
Every privileged action stays behind this explicit Python command registry.
The existing persistent SQLite files, model install paths, and Roblox MCP
adapters are reused without migration or credential exposure to JavaScript.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
import json
import os
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
from .intelligence import for_settings
from .providers import credential_status, save_api_key, clear_api_key
from .chat_images import chat_image, generate_chat_image
from .diagnostics import export_review_bundle
from .mcp_connections import MCPGateway
from .tool_workshop import ToolWorkshop

ALLOWED_ACTIONS = frozenset({
    'bootstrap','switchProject','pickFiles','sendMessage','saveSettings',
    'installBrain','startBrain','listModels','testModel','discoverStudio',
    'checkUpdates','installUpdate','transcribe','openDataFolder', 'copyText', 'openLegacy', 'selectFolder',
    'generateImage','saveProviderKey','clearProviderKey','cancelMessage','exportReviewBundle',
    'newChat','switchChat','testMcpConnection','runTeam','rememberDecision','listLearning',
    'listCustomTools','previewCustomTool','approveCustomTool','disableCustomTool',
    'startModelRouter','stopBrain','testModelTeam',
})


def react_index(root: Path | None = None) -> Path:
    """Resolve the static SPA from either source checkout or PyInstaller bundle."""
    base = root or Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return Path(base) / 'frontend' / 'dist' / 'index.html'


def sanitize_event(event: dict) -> dict:
    """Never forward raw tool results/secret tokens to an unrestricted webpage."""
    kind = str(event.get('event', 'working'))[:36]
    if kind in {'agent_started','agent_finished','agent_blocked'}:
        role=str(event.get('role','agent'))[:24]
        status=str(event.get('status','working'))[:18]
        return {'phase':f'STAR Teams: {role} — {status if kind != "agent_started" else "working"}'}
    if kind == 'assistant_delta':
        return {'phase':'Generating response', 'delta':str(event.get('text',''))[:2500]}
    if kind in {'subagent_started','subagent_finished'}:
        role=str(event.get('role','research'))[:30]
        if role not in {'planner','research','luau','ui','animation',
                        'environment','review','integration'}:
            role='research'
        status='working' if kind=='subagent_started' else str(event.get('status','done'))[:16]
        return {'phase':f'STAR {role} specialist · {status}'}
    if kind == 'route_selected':
        return {'phase': 'STAR · ' + str(event.get('description', 'Selecting model'))[:90]}
    if kind in {'saved','run_completed'}:
        return {'phase':'Saving verified task record'}
    if kind in {'tool_call','tool_result','tool_output'}:
        return {'phase':'Using an authorized local tool'}
    return {'phase':('STAR is working · '+kind)[:110]}


def file_allowed(path: Path, approved: set[Path]) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if resolved not in approved:
        raise PermissionError('Choose the file through STAR Attach before using it')
    if resolved.stat().st_size > 700_000_000:
        raise ValueError('Media file exceeds the supported size limit')
    return resolved


def _get_state(settings_file: Path, runtime: Runtime) -> dict:
    settings = Settings.load(settings_file)
    home = app_data()
    chats = Conversations(home / 'conversations.sqlite3')
    try:
        active_chat = chats.active_chat(settings.project)
        chat_threads = chats.list_chats(settings.project)
        recent = chats.recent(settings.project, limit=80, chat_id=active_chat)
        projects = sorted(set(chats.projects() + [settings.project]))
    finally:
        chats.close()
    messages = []
    for i, (role, body, created) in enumerate(recent):
        entry = {'id':f'saved-{i}', 'role':role,'text':body,'created':created}
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
        'version':__version__,'project':settings.project,'projects':projects,
        'messages':messages,'active_chat':active_chat,'chats':chat_threads,
        'settings':asdict(settings),
        'brain_installed':brain is not None,'brain_running':runtime.status()=='running',
        'model_router_running':runtime.router_running(),
        'tool_workshop':tool_workshop_status,
        'analytics':get_dashboard(home,settings.project),
        'credentials':credential_status(),
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
            self.active_update = False

        def _emit(self, request_id: str, kind: str, data):
            payload={'requestId':request_id,'kind':kind,'data':data}
            self.event.emit(json.dumps(payload,default=str))

        def _run(self, request_id: str, action: str, worker):
            def task():
                try:
                    data=worker()
                    self._emit(request_id, 'result', data)
                except Exception as exc:
                    if (action in {'sendMessage', 'startBrain', 'testModel'}
                        and (getattr(exc, 'status_code', None) is not None
                             or type(exc).__name__ in {'APIConnectionError', 'APITimeoutError'}
                             or 'System message must be at the beginning' in str(exc))):
                        from .model_health import explain_model_failure
                        detail = explain_model_failure(exc)
                    else:
                        detail = f'{type(exc).__name__}: {str(exc)[:350]}'
                    self._emit(request_id, 'error', detail)
                finally:
                    if action in {'sendMessage','generateImage','runTeam'}:self.active_task=False
                    if action=='installUpdate':self.active_update=False
            self.pool.submit(task)

        def _start_brain(self, info: BrainInstall):
            from .desktop_core import query_models
            settings_file=self.settings_file
            if self.runtime.router_running():
                raise RuntimeError('Stop the managed model router before starting the single-model Brain')
            if self.runtime.status()!='running':
                self.runtime.start(Path(info.executable),Path(info.model),
                    app_data()/'logs'/'star-brain-react.log',port=8080,context=4096,
                    gpu_layers=30,projector=Path(info.projector))
            probe=Settings(endpoint='http://127.0.0.1:8080/v1')
            for _ in range(70):
                if self.runtime.status()!='running':
                    raise RuntimeError('STAR Brain stopped. Check the STAR logs folder.')
                try:
                    models=query_models(probe)
                    if models:
                        settings=Settings.load(settings_file)
                        settings.endpoint=probe.endpoint
                        settings.provider='local'
                        settings.model=models[0]
                        settings.llama_server=info.executable
                        settings.gguf_model=info.model
                        settings.save(settings_file)
                        # A /models response is not proof the chat template actually works.
                        # Verify one real text completion before claiming the AI is ready.
                        from .model_health import probe_chat_endpoint, explain_model_failure
                        import asyncio
                        try:
                            probe = asyncio.run(probe_chat_endpoint(settings))
                        except Exception as exc:
                            raise RuntimeError('STAR Brain started but failed its chat test: '
                                               + explain_model_failure(exc)) from exc
                        return {'model':models[0], 'brain_running':True,
                                'chat_ready':True, 'sample':probe['sample']}
                except RuntimeError as exc:
                    if 'failed its chat test' in str(exc):
                        raise
                except Exception:
                    pass
                time.sleep(2)
            raise TimeoutError('Local model did not become ready. See STAR/logs/star-brain-react.log')

        def _start_model_router(self):
            if self.active_task:
                raise RuntimeError('Stop the active chat before switching STAR models')
            settings = Settings.load(self.settings_file)
            settings.validate()
            if settings.provider != 'local':
                raise ValueError('Select Local as the inference provider')
            if not settings.router_models_dir:
                raise ValueError('Choose a local GGUF model folder first')
            info = BrainInstall.load(app_data()/'brain.json')
            source = info.executable if info is not None else settings.llama_server
            if not source:
                raise RuntimeError('Install the verified STAR Brain llama.cpp engine first')
            engine = Path(source)
            self.runtime.start_router(engine, Path(settings.router_models_dir),
                app_data()/'logs'/'star-router-react.log',port=8080,
                context=settings.router_context,gpu_layers=settings.gpu_layers)
            probe = Settings(endpoint='http://127.0.0.1:8080/v1')
            try:
                for _ in range(35):
                    if self.runtime.status() != 'running':
                        raise RuntimeError('Router exited; inspect STAR/logs/star-router-react.log')
                    try:
                        models=query_models(probe)
                    except Exception:
                        models=[]
                    if models:
                        updated=Settings.load(self.settings_file)
                        updated.endpoint=probe.endpoint
                        updated.provider='local'
                        updated.llama_server=str(engine)
                        if updated.model not in models:
                            updated.model=(updated.fast_model if updated.fast_model in models
                                           else models[0])
                        updated.save(self.settings_file)
                        return {'brain_running':True,'model_router_running':True,
                                'model':updated.model,'models':models,'chat_ready':False,
                                'note':'Router ready; actual model completion is not yet verified'}
                    time.sleep(1)
                raise TimeoutError('Model router did not respond; check its log')
            except Exception:
                self.runtime.stop()
                raise

        def _run_chat(self, request_id, prompt, selected, mode='auto', research=False, github=False):
            home=app_data()
            settings=Settings.load(self.settings_file)
            if not settings.model.strip():
                raise ValueError('STAR Brain is offline. Go to STAR Brain and start your model.')
            chats=Conversations(home/'conversations.sqlite3')
            try:
                active_chat=chats.active_chat(settings.project)
                chats.add(settings.project,'user',prompt,chat_id=active_chat)
            finally:
                chats.close()
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
                answer=run_task(settings,full_prompt,pics,
                    on_event=lambda e:self._emit(request_id,'progress',sanitize_event(e)),
                    stream_tokens=True, mode=mode, research=research, cancel_event=self.cancel_chat, github_enabled=github, chat_id=active_chat)
            chats=Conversations(home/'conversations.sqlite3')
            try:
                chats.add(settings.project,'assistant',answer,chat_id=active_chat)
            finally:
                chats.close()
            return {'answer':answer}

        def _run_image(self, request_id, prompt):
            settings=Settings.load(self.settings_file)
            home=app_data()
            self._emit(request_id,'progress',{'phase':'Generating image using local ComfyUI…'})
            chats=Conversations(home/'conversations.sqlite3')
            try:
                active_chat=chats.active_chat(settings.project)
                chats.add(settings.project,'user',prompt,chat_id=active_chat)
            finally:
                chats.close()
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
                raise ValueError("Start STAR Brain before running a specialist team")
            if getattr(settings,'provider','local') != 'local':
                raise ValueError('STAR Teams currently requires the local STAR Brain model')
            chats = Conversations(home / "conversations.sqlite3")
            try:
                active_chat = chats.active_chat(settings.project)
                chats.add(settings.project, "user", prompt, chat_id=active_chat)
            finally:
                chats.close()
            answer, team = asyncio.run(run_research_team(
                endpoint=settings.endpoint, model=settings.model,
                project=settings.project, prompt=prompt, home=home,
                parallel=2,
                on_event=lambda event: self._emit(
                    request_id, 'progress', sanitize_event(event)),
            ))
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
                if action=='bootstrap':return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime)})
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
                    return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime)})
                if action=='newChat':
                    if self.active_task:raise RuntimeError('Wait for the current answer before starting a new chat')
                    settings=Settings.load(self.settings_file)
                    conversations=Conversations(app_data()/'conversations.sqlite3')
                    try: conversations.new_chat(settings.project)
                    finally: conversations.close()
                    return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime)})
                if action=='switchChat':
                    if self.active_task:raise RuntimeError('Wait for the current answer before switching chats')
                    chat_id=str(body.get('chatId',''))[:80]
                    settings=Settings.load(self.settings_file)
                    conversations=Conversations(app_data()/'conversations.sqlite3')
                    try: conversations.switch_chat(settings.project,chat_id)
                    finally: conversations.close()
                    return json.dumps({'ok':True,'data':_get_state(self.settings_file,self.runtime)})
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
                    changes=body.get('settings')
                    if not isinstance(changes,dict):raise ValueError('Invalid settings')
                    old=Settings.load(self.settings_file)
                    permitted={'endpoint','model','fast_model','reasoning_model','roblox_model','vision_model','router_models_dir','router_context','gpu_layers','roblox_research_enabled','tool_workshop_enabled','specialists_enabled','specialist_parallelism','provider','project','workspace','studio_id','studio_edit','workspace_edit','max_calls','context_chars','reduced_motion','comfy_workflow','comfy_prompt_node','comfy_port','obsidian_vault','obsidian_enabled','skills_enabled','graphify_enabled','mcp_graphify_docs','mcp_graphify_local','mcp_graphify_port','mcp_obsidian_live'}
                    for key,value in changes.items():
                        if key in permitted:setattr(old,key,value)
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
                    self.active_task=True
                    self._run(rid,action,lambda:self._run_team(rid,prompt))
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
                elif action=='listModels':
                    def worker():return {'models':query_models(Settings.load(self.settings_file))}
                    self._run(rid,action,worker)
                elif action=='testModel':
                    def worker():
                        import asyncio
                        from .model_health import probe_chat_endpoint
                        return asyncio.run(probe_chat_endpoint(Settings.load(self.settings_file)))
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
            self.cancel_chat.set()
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
