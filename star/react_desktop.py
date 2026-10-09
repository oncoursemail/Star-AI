"""STAR's React desktop host: Qt WebEngine + a deliberately narrow Python bridge.

React is presentation only. Model tokens, file paths, GitHub credentials and
Roblox capabilities live in Python. Never expose shell or arbitrary file APIs
through the WebChannel. Projects and checkpoints stay under APPDATA/STAR.
"""
from __future__ import annotations

from dataclasses import asdict, fields
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

from .desktop_core import Settings, Conversations, app_data, run_task, query_models, check_studio
from .analytics import get_dashboard
from .version import __version__


def frontend_path() -> Path | None:
    roots = [Path(getattr(sys, '_MEIPASS', '')),
             Path(__file__).resolve().parents[1],
             Path(sys.executable).resolve().parent]
    for root in roots:
        if not str(root) or str(root) == '.':
            continue
        candidate = root / 'frontend' / 'dist' / 'index.html'
        if candidate.is_file():
            return candidate
    return None


def state_snapshot(config: Settings) -> dict:
    """Stable read-only view for React; never includes secret credentials."""
    from .brain_setup import BrainInstall
    home = app_data()
    home.mkdir(parents=True, exist_ok=True)
    db = Conversations(home / 'conversations.sqlite3')
    try:
        recent = db.recent(config.project, limit=90)
        history = [{'id': f'msg-{i}', 'role': role, 'body': body, 'created': created}
                   for i, (role, body, created) in enumerate(recent)]
        projects = db.projects()
    finally:
        db.close()
    brain = BrainInstall.load(home / 'brain.json')
    return {
        'version': __version__, 'mode': 'desktop', 'settings': asdict(config),
        'messages': history, 'projects': sorted(set(projects + [config.project])),
        'analytics': get_dashboard(home, config.project),
        'brain': {'ready': brain is not None, 'state': 'Installed' if brain else 'Not installed',
                  'model': config.model if brain else '', 'version': brain.engine_version if brain else ''},
    }


def sanitize_new_settings(original: Settings, proposed: dict) -> Settings:
    allowed = set(f.name for f in fields(Settings))
    if not isinstance(proposed, dict) or any(k not in allowed for k in proposed):
        raise ValueError('Settings contain an unsupported field')
    raw = asdict(original)
    raw.update(proposed)
    result = Settings(**raw)
    result.validate()
    return result


def launch() -> None:
    """Start React when its compiled bundle exists; caller selects legacy fallback."""
    path = frontend_path()
    if not path:
        raise FileNotFoundError('STAR React frontend is not built; run npm install && npm run build in frontend/')

    from PySide6.QtCore import QObject, QUrl, QRunnable, QThreadPool, Signal, Slot, QTimer
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import QWebEngineSettings

    class WorkerEvents(QObject):
        succeeded = Signal(object)
        failed = Signal(str)

    class Worker(QRunnable):
        def __init__(self, fn):
            super().__init__()
            self.fn = fn
            self.events = WorkerEvents()

        @Slot()
        def run(self):
            try:
                self.events.succeeded.emit(self.fn())
            except Exception as exc:
                self.events.failed.emit(f'{type(exc).__name__}: {str(exc)[:320]}')

    class Bridge(QObject):
        event = Signal(str)

        def __init__(self, window):
            super().__init__(window)
            self.window = window
            self.settings_path = app_data() / 'settings.json'
            self.config = Settings.load(self.settings_path)
            self.selected: dict[str, Path] = {}
            self.workers: set[Worker] = set()
            self.busy_actions: set[str] = set()
            from .local_runtime import Runtime
            self.runtime = Runtime()

        def emit(self, kind: str, **kwargs):
            self.event.emit(json.dumps({'type': kind, **kwargs}, ensure_ascii=False, default=str))

        def schedule(self, label: str, fn, success=None, failure=None) -> bool:
            if label in self.busy_actions:
                return False
            self.busy_actions.add(label)
            job = Worker(fn)
            self.workers.add(job)

            def succeeded(value):
                self.busy_actions.discard(label)
                self.workers.discard(job)
                if success:
                    success(value)
            def failed(message):
                self.busy_actions.discard(label)
                self.workers.discard(job)
                if failure:
                    failure(message)
                else:
                    self.emit('error', error=message)
            job.events.succeeded.connect(succeeded)
            job.events.failed.connect(failed)
            QThreadPool.globalInstance().start(job)
            return True

        def running_model(self):
            from .brain_setup import install_brain
            from .local_runtime import Runtime
            from .brain_setup import BrainInstall
            brain = BrainInstall.load(app_data() / 'brain.json')
            if brain is None:
                brain = install_brain(app_data(), progress=lambda evt: self.emit('brain_progress', data=evt))
            if self.runtime.status() != 'running':
                self.runtime.start(Path(brain.executable), Path(brain.model),
                                   app_data() / 'logs' / 'react-star-brain.log',
                                   port=8080, context=4096, gpu_layers=30,
                                   projector=Path(brain.projector))
            probe = Settings(endpoint='http://127.0.0.1:8080/v1')
            for _ in range(65):
                if self.runtime.status() != 'running':
                    raise RuntimeError('STAR Brain exited while starting. Open your local STAR logs folder.')
                try:
                    models = query_models(probe)
                    if models:
                        return models[0]
                except Exception:
                    pass
                time.sleep(2)
            raise TimeoutError('STAR Brain did not become available in time')

        def model_ready(self, model):
            self.config.endpoint = 'http://127.0.0.1:8080/v1'
            self.config.model = str(model)
            self.config.save(self.settings_path)
            self.emit('brain_ready', model=model)

        def model_failed(self, message):
            self.emit('brain_failed', error=message)

        @Slot(str, result=str)
        def dispatch(self, raw: str) -> str:
            try:
                if len(raw) > 65000:
                    raise ValueError('Request too large')
                req = json.loads(raw)
                action, data = req.get('action'), req.get('data', {})
                if not isinstance(data, dict):
                    raise ValueError('Invalid request data')
                if action == 'bootstrap':
                    return json.dumps({'ok': True, 'data': state_snapshot(self.config)})
                if action == 'select_attachments':
                    filters = 'References (*.png *.jpg *.jpeg *.webp *.wav *.mp3 *.m4a *.mp4 *.mov *.webm);;All files (*)'
                    paths, _ = QFileDialog.getOpenFileNames(self.window, 'Attach references', str(Path.home()), filters)
                    entries = []
                    for p in paths[:8]:
                        file = Path(p).resolve()
                        if not file.is_file() or file.stat().st_size > 150_000_000:
                            continue
                        token = uuid.uuid4().hex
                        self.selected[token] = file
                        entries.append({'token': token, 'name': file.name, 'kind': file.suffix.lower()})
                    return json.dumps({'ok': True, 'data': entries})
                if action == 'choose_workspace':
                    choice = QFileDialog.getExistingDirectory(self.window, 'Choose a STAR project folder', self.config.workspace or str(Path.home()))
                    if choice:
                        next_settings = sanitize_new_settings(self.config, {'workspace': choice})
                        next_settings.save(self.settings_path)
                        self.config = next_settings
                    return json.dumps({'ok': True, 'data': self.config.workspace})
                if action == 'save_settings':
                    candidate = sanitize_new_settings(self.config, data.get('settings', {}))
                    candidate.save(self.settings_path)
                    self.config = candidate
                    return json.dumps({'ok': True})
                if action == 'chat_send':
                    message = str(data.get('message') or '').strip()
                    if not message or len(message) > 20000:
                        raise ValueError('A message is required (up to 20,000 characters)')
                    requested = data.get('attachment_tokens') or []
                    if not isinstance(requested, list) or len(requested) > 8:
                        raise ValueError('Too many attachments')
                    if not self.config.model:
                        raise ValueError('Install or select a local model first in STAR Brain')
                    if 'chat' in self.busy_actions:
                        raise RuntimeError('Wait for the current response')
                    paths = [self.selected.pop(str(token)) for token in requested]
                    db = Conversations(app_data() / 'conversations.sqlite3')
                    try:
                        db.add(self.config.project, 'user', message)
                    finally:
                        db.close()
                    frozen_settings = Settings(**asdict(self.config))
                    def answer():
                        from .media_features import VIDEO_EXTENSIONS, AUDIO_EXTENSIONS, video_frames, transcribe_audio
                        with tempfile.TemporaryDirectory(prefix='star-react-media-') as d:
                            pictures = []
                            notes = []
                            for file in paths:
                                if file.suffix.lower() in VIDEO_EXTENSIONS:
                                    pictures.extend(video_frames(file, Path(d) / f'video-{uuid.uuid4().hex}', max_frames=4))
                                    notes.append(f'Video {file.name}: representative frames only, not continuous video understanding.')
                                elif file.suffix.lower() in AUDIO_EXTENSIONS:
                                    notes.append(f'Audio {file.name}: {transcribe_audio(file)}')
                                else:
                                    pictures.append(file)
                            prompt = message + ('\n\n' + '\n'.join(notes) if notes else '')
                            return run_task(frozen_settings, prompt, pictures[:4], on_event=lambda evt: self.emit('task_progress', data=evt))
                    def complete(result):
                        db2 = Conversations(app_data() / 'conversations.sqlite3')
                        try:
                            db2.add(frozen_settings.project, 'assistant', str(result))
                        finally:
                            db2.close()
                        self.emit('task_done', answer=str(result))
                    def failed(exc):
                        self.emit('task_failed', error=exc)
                    if not self.schedule('chat', answer, complete, failed):
                        raise RuntimeError('STAR is still working')
                    return json.dumps({'ok': True, 'started': True})
                if action == 'brain_install':
                    if not self.schedule('brain', self.running_model, self.model_ready, self.model_failed):
                        raise RuntimeError('Brain setup is already running')
                    return json.dumps({'ok': True, 'started': True})
                if action == 'models_list':
                    if not self.schedule('models', lambda: query_models(self.config),
                                         lambda models: self.emit('models_ready', models=models)):
                        raise RuntimeError('Model check is already running')
                    return json.dumps({'ok': True, 'started': True})
                if action == 'studio_discover':
                    if not self.schedule('studio', check_studio,
                                         lambda value: self.emit('studio_ready', data=value)):
                        raise RuntimeError('Studio discovery is already running')
                    return json.dumps({'ok': True, 'started': True})
                if action == 'check_updates':
                    from .updates import get_latest
                    if not self.schedule('updates', get_latest,
                                         lambda value: self.emit('update_ready', data=asdict(value))):
                        raise RuntimeError('Already checking updates')
                    return json.dumps({'ok': True, 'started': True})
                if action == 'update_install':
                    from .updates import get_latest, stage_installer, launch_installer
                    def upgrade():
                        result = get_latest()
                        if not result.available:
                            raise RuntimeError('No newer verified version is available')
                        path = stage_installer(result, app_data())
                        launch_installer(path)
                        return path.version
                    if not self.schedule('upgrade', upgrade,
                                         lambda version: (self.emit('update_started', version=version), QTimer.singleShot(600, self.window.close))):
                        raise RuntimeError('Update is already running')
                    return json.dumps({'ok': True, 'started': True})
                if action == 'open_url':
                    url = str(data.get('url') or '')
                    if not (url.startswith('https://github.com/oncoursemail/Star-AI/') or url.startswith('https://create.roblox.com/')):
                        raise PermissionError('Website is outside STAR documentation links')
                    QDesktopServices.openUrl(QUrl(url))
                    return json.dumps({'ok': True})
                return json.dumps({'ok': False, 'error': 'Unknown STAR action'})
            except Exception as exc:
                return json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {str(exc)[:280]}'})

        def close(self):
            self.runtime.stop()

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f'STAR Intelligence · Genesis v{__version__}')
            self.resize(1440, 900)
            self.setMinimumSize(850, 600)
            self.web = QWebEngineView(self)
            self.setCentralWidget(self.web)
            self.channel = QWebChannel(self.web.page())
            self.bridge = Bridge(self)
            self.channel.registerObject('starBridge', self.bridge)
            self.web.page().setWebChannel(self.channel)
            # Local HTML accesses bundled JS/CSS only; model requests remain Python-only.
            settings = self.web.settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
            address = QUrl.fromLocalFile(str(path.resolve()))
            address.setQuery('desktop=1')
            self.web.setUrl(address)

        def closeEvent(self, event):
            self.bridge.close()
            super().closeEvent(event)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('STAR Intelligence')
    window = MainWindow()
    window.show()
    # Resumes a previously installed, verified local brain without re-downloading.
    from .brain_setup import BrainInstall
    if BrainInstall.load(app_data() / 'brain.json'):
        QTimer.singleShot(2000, lambda: window.bridge.schedule('brain', window.bridge.running_model,
                            window.bridge.model_ready, window.bridge.model_failed))
    raise SystemExit(app.exec())
