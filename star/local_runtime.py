"""Manage a user-supplied llama.cpp executable from STAR Desktop.

STAR's .exe does not bundle third-party model weights or llama.cpp CUDA libraries.
Only an explicitly selected llama-server.exe is started, with fixed arguments,
loopback networking, and no shell expansion. This is a local inference adapter.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import threading
from .model_fleet import inspect_models_dir


class Runtime:
    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.log_file = None
        self.log_path: Path | None = None
        self.lock = threading.Lock()
        self.mode: str | None = None

    @staticmethod
    def arguments(executable: Path, model: Path, *, port=8080, context=4096, gpu_layers=25, projector: Path | None = None) -> list[str]:
        executable=executable.expanduser().resolve(strict=True)
        model=model.expanduser().resolve(strict=True)
        if executable.name.lower()!='llama-server.exe' or executable.suffix.lower()!='.exe':
            raise ValueError('Choose the llama-server.exe supplied with llama.cpp')
        if model.suffix.lower()!='.gguf' or model.stat().st_size<100000:
            raise ValueError('Choose a downloaded GGUF model file (at least 100 KB)')
        if not 1024<=port<=65535 or not 512<=context<=32768 or not 0<=gpu_layers<=1000:
            raise ValueError('Invalid port, context length or GPU layers')
        args = [str(executable), '-m', str(model), '--host', '127.0.0.1',
                '--port', str(port), '--ctx-size', str(context), '-ngl', str(gpu_layers), '--jinja']
        if projector is not None:
            proj = projector.expanduser().resolve(strict=True)
            if proj.suffix.lower() != '.gguf':
                raise ValueError('Vision projector must be a GGUF file')
            args += ['--mmproj', str(proj)]
        return args

    @staticmethod
    def router_arguments(executable: Path, models_dir: Path, *, port=8080,
                         context=4096, gpu_layers=25, max_loaded=1) -> list[str]:
        """Dynamic llama.cpp model router, bound strictly to loopback.

        One resident model prevents multiple heavy GGUFs from exhausting RAM.
        """
        executable = Path(executable).expanduser()
        if executable.is_symlink():
            raise ValueError('Server executable must not be a symlink')
        exe = executable.resolve(strict=True)
        if exe.name.lower() != 'llama-server.exe' or not exe.is_file():
            raise ValueError('Choose an installed llama-server.exe')
        inventory = inspect_models_dir(Path(models_dir))
        if (type(port) is not int or not 1024 <= port <= 65535
                or type(context) is not int or not 512 <= context <= 32768
                or type(gpu_layers) is not int or not 0 <= gpu_layers <= 1000
                or max_loaded != 1):
            raise ValueError('Invalid local model router limits')
        return [str(exe), '--models-dir', str(inventory.directory),
                '--models-max', '1', '--host', '127.0.0.1',
                '--port', str(port), '--ctx-size', str(context),
                '-ngl', str(gpu_layers), '-np', '1', '--jinja']

    def start_router(self, executable: Path, models_dir: Path, log_path: Path,
                     *, port=8080, context=4096, gpu_layers=25):
        """Start only an explicitly requested, locally installed model router."""
        with self.lock:
            if self.process and self.process.poll() is None:
                raise RuntimeError('Stop the current managed STAR Brain before starting model router')
            argv = self.router_arguments(executable, models_dir, port=port,
                                         context=context, gpu_layers=gpu_layers)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file = log_path.open('ab')
            self.log_path = log_path
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            try:
                self.process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                    stdout=self.log_file, stderr=subprocess.STDOUT, creationflags=flags)
                self.mode = 'router'
            except Exception:
                self.log_file.close()
                self.log_file = None
                self.mode = None
                raise
            return self.process.pid

    def router_running(self) -> bool:
        with self.lock:
            return bool(self.mode == 'router' and self.process and self.process.poll() is None)

    def start(self, executable: Path, model: Path, log_path: Path, *, port=8080, context=4096, gpu_layers=25, projector: Path | None = None):
        with self.lock:
            if self.process and self.process.poll() is None:
                raise RuntimeError('llama.cpp is already running')
            argv=self.arguments(executable,model,port=port,context=context,gpu_layers=gpu_layers,projector=projector)
            log_path.parent.mkdir(parents=True,exist_ok=True)
            self.log_file=log_path.open('ab')
            self.log_path=log_path
            flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            try:
                self.process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=self.log_file,
                    stderr=subprocess.STDOUT,creationflags=flags)
            except Exception:
                self.log_file.close();self.log_file=None
                raise
            self.mode = 'single'
            return self.process.pid

    def stop(self):
        with self.lock:
            process=self.process
            if not process:
                self.mode = None
                return
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
            self.process=None
            self.mode=None
            if self.log_file:self.log_file.close();self.log_file=None

    def status(self):
        with self.lock:
            if not self.process:return 'not started'
            return 'running' if self.process.poll() is None else f'exited ({self.process.returncode})'
