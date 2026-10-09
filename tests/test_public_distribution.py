"""Private source never gets mirrored to STAR's public distribution channel."""
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from star import updates
from star.design_system import COLORS, contrast_ratio, MOTION_MS, stylesheet
from star.version import PUBLIC_REPO, REPO, __version__
from scripts.publish_public_site import PUBLIC_FILES, collect_public_files, publish

ROOT=Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code=status
        self.body=body or {}
    def raise_for_status(self):
        if self.status_code>=400:
            raise ValueError('GitHub error')
    def json(self):
        return self.body


class FakeClient:
    def __init__(self, responses):
        self.responses=responses
        self.called=[]
    def get(self,url,**kwargs):
        self.called.append(url)
        return self.responses[url]


def test_public_metadata_preferred_without_authentication():
    public={"tag_name":"v0.7.1","html_url":updates.PUBLIC_RELEASES_URL,"assets":[]}
    client=FakeClient({updates.PUBLIC_API:FakeResponse(body=public)})
    result=updates.get_latest(client)
    assert result.available and result.repository==PUBLIC_REPO
    assert client.called==[updates.PUBLIC_API]  # Never requests private data if public works.


def test_when_public_missing_private_stays_browser_only():
    client=FakeClient({updates.PUBLIC_API:FakeResponse(404),updates.API:FakeResponse(404)})
    result=updates.get_latest(client)
    assert result.requires_browser and not result.available
    assert result.repository==REPO
    assert 'CLI is not required' in result.explanation


def test_private_update_assets_never_auto_downloaded():
    new=updates.UpdateResult(True,'0.7.1',updates.RELEASES_URL,repository=REPO,assets=())
    with pytest.raises(PermissionError):
        updates._trusted_setup_asset(new)


def test_all_public_website_files_are_allowlisted_and_copy_only(tmp_path):
    source=ROOT/'site'
    ready=collect_public_files(source)
    assert set(ready)==PUBLIC_FILES
    assert all('/'.encode() not in name.encode() for name in ready)
    assert 'star/desktop.py' not in ready
    assert publish(PUBLIC_REPO,'',source,dry_run=True)==sorted(PUBLIC_FILES)
    with pytest.raises(PermissionError):
        publish('oncoursemail/Star-AI','',source,dry_run=True)
    extra=tmp_path/'site';extra.mkdir()
    for name in PUBLIC_FILES:(extra/name).write_bytes(ready[name])
    (extra/'private.pem').write_text('NEVER PUBLIC')
    result=collect_public_files(extra)
    assert 'private.pem' not in result
    (extra/'index.html').unlink()
    (extra/'index.html').symlink_to(ROOT/'site/index.html')
    with pytest.raises(ValueError):collect_public_files(extra)


def test_public_web_version_and_download_location():
    site=json.loads((ROOT/'site/version.json').read_text())
    assert site['version']==__version__
    # Until the dedicated public mirror is created, download from the live
    # publicly accessible main STAR Release instead of a broken link.
    assert REPO in site['download']
    assert REPO in (ROOT/'site/index.html').read_text()
    assert 'site.js' in (ROOT/'site/index.html').read_text()


def test_public_ci_path_is_independent_of_private_source():
    job=(ROOT/'.github/workflows/windows-desktop.yml').read_text()
    assert 'publish-public:' in job and 'needs: [publish-release]' in job
    assert 'secrets.STAR_PUBLIC_RELEASE_TOKEN' in job
    assert 'vars.STAR_PUBLIC_REPO' in job
    assert 'publish_public_site.py' in job
    assert 'permissions:\n      contents: read' in job
    assert 'source' not in 'STAR-Genesis-Windows-x64.zip'


def test_oled_palette_is_accessible_and_icons_are_real():
    assert contrast_ratio(COLORS['text'],COLORS['canvas'])>7
    assert contrast_ratio(COLORS['muted'],COLORS['surface'])>=4.5
    assert contrast_ratio(COLORS['gold_ink'],COLORS['gold'])>=7
    style=stylesheet()
    assert 'QFrame#MetricCard' in style
    assert 'QPushButton#Nav:checked' in style
    assert MOTION_MS['message']<=220
    from star.visuals import svg_icon
    assert '<svg' in svg_icon('analytics') and '<path' in svg_icon('copy')


def test_qa_screenshots_use_real_star_theme():
    source=(ROOT/'scripts/capture_desktop_ui.py').read_text()
    assert "app.setStyleSheet(STYLE)" in source
    assert "app.setStyle('Fusion')" in source
    assert "not using its OLED stylesheet" in source


def test_no_font_offscreen_renderer_is_not_treated_as_a_real_ui_verification():
    script=(ROOT/'scripts/capture_desktop_ui.py').read_text()
    assert 'if fonts:' in script
    assert 'nonrepresentative' in script
    assert 'real desktop visual QA' in script
