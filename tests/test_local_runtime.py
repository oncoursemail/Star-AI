from pathlib import Path
import pytest
from star.local_runtime import Runtime


def test_local_runtime_args(tmp_path):
    exe=tmp_path/'llama-server.exe';exe.write_bytes(b'binary placeholder')
    gguf=tmp_path/'vision.gguf';gguf.write_bytes(b'a'*100100)
    args=Runtime.arguments(exe,gguf,port=8080,context=4096,gpu_layers=20)
    assert '--host' in args and '127.0.0.1' in args
    assert args[args.index('-ngl')+1]=='20'
    assert args.count('--jinja')==1


def test_local_runtime_refuses_nonserver_exe(tmp_path):
    exe=tmp_path/'somefile.exe';exe.write_bytes(b'binary')
    gguf=tmp_path/'vision.gguf';gguf.write_bytes(b'a'*100100)
    with pytest.raises(ValueError):Runtime.arguments(exe,gguf)


def test_local_runtime_refuses_bad_model(tmp_path):
    exe=tmp_path/'llama-server.exe';exe.write_bytes(b'x')
    model=tmp_path/'model.gguf';model.write_bytes(b'bad')
    with pytest.raises(ValueError):Runtime.arguments(exe,model)
