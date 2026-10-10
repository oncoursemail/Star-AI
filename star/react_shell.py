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
import time
import uuid

from .desktop_core import Settings, Conversations, app_data, run_task, query_models, check_studio
from .analytics import get_dashboard
from .brain_setup import BrainInstall, install_brain
from .local_runtime import Runtime
from .version import __version__
from .intelligence import for_settings

ALLOWED_ACTIONS = frozenset({
    'bootstrap','switchProject','pickFiles','sendMessage','saveSettings',
    'installBrain','startBrain','listModels','testModel','discoverStudio',
    'checkUpdates','installUpdate','transcribe','openDataFolder', 'copyText', 'openLegacy', 'selectFolder',
})


def react_index(root: Path | None = None) -> Path:
    """Resolve the static SPA from either source checkout or PyInstaller bundle."""
    base = root or Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    return Path(base) / 'frontend' / 'dist' / 'index.html'


def sanitize_event(event: dict) -> dict:
    """Never forward raw tool results/secret tokens to an unrestricted webpage."""
    kind = str(event.get('event', 'working'))[:36]
    if kind == 'assistant_delta':
        return {'phase':'Generating response', 'delta':str(event.get('text',''))[:2500]}
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
        recent = chats.recent(settings.project, limit=80)
        projects = sorted(set(chats.projects() + [settings.project]))
    finally:
        chats.close()
    messages = [{'id':f'saved-{i}', 'role':role, 'text':text, 'created':created}
                for i,(role,text,created) in enumerate(recent)]
    brain = BrainInstall.load(home / 'brain.json')
    return {
        'version':__version__, 'project':settings.project, 'projects':projects,
        'messages':messages, 'settings':asdict(settings),
        'brain_installed':brain is not None, 'brain_running':runtime.status()=='running',
        'analytics':get_dashboard(home, settings.project),
        'intelligence':for_settings(settings,home).status(),
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
                    if action=='sendMessage':self.active_task=False
                    if action=='installUpdate':self.active_update=False
            self.pool.submit(task)

        def _start_brain(self, info: BrainInstall):
            from .desktop_core import query_models
            settings_file=self.settings_file
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
                except Exception:
                    pass
                time.sleep(2)
            raise TimeoutError('Local model did not become ready. See STAR/logs/star-brain-react.log')

        def _run_chat(self, request_id, prompt, selected):
            home=app_data()
            settings=Settings.load(self.settings_file)
            if not settings.model.strip():
                raise ValueError('STAR Brain is offline. Go to STAR Brain and start your model.')
            chats=Conversations(home/'conversations.sqlite3')
            try:
                chats.add(settings.project,'user',prompt)
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
                    stream_tokens=True)
            chats=Conversations(home/'conversations.sqlite3')
            try:
                chats.add(settings.project,'assistant',answer)
            finally:
                chats.close()
            return {'answer':answer}

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
                if action=='selectFolder':
                    selected=QFileDialog.getExistingDirectory(self.host, 'Choose a local notes or project folder')
                    return json.dumps({'ok':True,'data':{'path':str(selected) if selected else ''}})
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
                if action=='saveSettings':
                    changes=body.get('settings')
                    if not isinstance(changes,dict):raise ValueError('Invalid settings')
                    old=Settings.load(self.settings_file)
                    permitted={'endpoint','model','project','workspace','studio_id','studio_edit','workspace_edit','max_calls','context_chars','reduced_motion','obsidian_vault','obsidian_enabled','skills_enabled','graphify_enabled'}
                    for key,value in changes.items():
                        if key in permitted:setattr(old,key,value)
                    old.save(self.settings_file)
                    return json.dumps({'ok':True,'data':asdict(old)})
                if action=='openLegacy':
                    if getattr(sys, 'frozen', False):
                        command=[sys.executable, '--legacy-ui']
                    else:
                        command=[sys.executable, str(Path(__file__).resolve().parents[1]/'star_desktop.py'), '--legacy-ui']
                    import subprocess
                    subprocess.Popen(command, close_fds=True, stdin=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW',0))
                    return json.dumps({'ok':True,'data':True})
                if action=='copyText':
                    content=str(body.get('text',''))
                    if len(content)>300000:raise ValueError('Too much text')
                    QApplication.clipboard().setText(content)
                    return json.dumps({'ok':True,'data':True})
                if action=='openDataFolder':
                    path=app_data();path.mkdir(parents=True,exist_ok=True)
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
                    return json.dumps({'ok':True,'data':True})
                if action=='sendMessage':
                    if self.active_task:raise RuntimeError('STAR is already handling a task')
                    prompt=str(body.get('prompt','')).strip()
                    if not prompt or len(prompt)>30000:raise ValueError('Message must be 1–30,000 characters')
                    files=body.get('files') or []
                    if not isinstance(files,list) or len(files)>8:raise ValueError('Too many attachments')
                    selected=[file_allowed(Path(str(f)),self.allowed_files) for f in files]
                    self.active_task=True
                    self._run(rid,action,lambda:self._run_chat(rid,prompt,selected))
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
                elif action=='listModels':
                    def worker():return {'models':query_models(Settings.load(self.settings_file))}
                    self._run(rid,action,worker)
                elif action=='testModel':
                    def worker():
                        import asyncio
                        from .model_health import probe_chat_endpoint
                        return asyncio.run(probe_chat_endpoint(Settings.load(self.settings_file)))
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
