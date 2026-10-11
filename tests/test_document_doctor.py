"""Reader resources must actually work inside the executable's doctor path."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from star.document_doctor import check_document_bundle
from star.documents import DocumentStore


def test_bundle_doctor_extracts_all_readers_without_touching_application_profile(tmp_path, monkeypatch):
    profile = tmp_path / 'owner-profile'
    profile.mkdir()
    sentinel = profile / 'sentinel.txt'
    sentinel.write_text('preserve', encoding='utf-8')
    monkeypatch.setenv('APPDATA', str(profile))
    monkeypatch.setenv('XDG_DATA_HOME', str(profile))
    assert set(check_document_bundle()) == {'txt', 'pdf', 'docx', 'pptx', 'csv', 'tsv', 'xlsx', 'json'}
    assert list(profile.iterdir()) == [sentinel]
    assert sentinel.read_text() == 'preserve'


def test_bundle_doctor_refuses_silent_extraction_failure(monkeypatch):
    monkeypatch.setattr(DocumentStore, 'context', lambda *args, **kwargs: '')
    with pytest.raises(RuntimeError, match='evidence extraction failed'):
        check_document_bundle()


def test_document_doctor_launcher_needs_no_gui_or_profile(tmp_path):
    root = Path(__file__).resolve().parents[1]
    profile = tmp_path / 'isolated-profile'
    result = subprocess.run([sys.executable, str(root / 'star_desktop.py'), '--document-doctor'],
        cwd=root, env={**os.environ, 'APPDATA': str(profile), 'XDG_DATA_HOME': str(profile)},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'Packaged document readers OK' in result.stdout and 'xlsx' in result.stdout
    assert not profile.exists()
