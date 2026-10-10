"""Regressions for STAR's canonical public GitHub Releases channel."""
from pathlib import Path
import json

import pytest
from star import updates
from star.design_system import COLORS, contrast_ratio, MOTION_MS, stylesheet
from star.version import REPO, __version__
from scripts.publish_public_site import PUBLIC_FILES, PUBLIC_REPO, collect_public_files, publish

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


def test_official_release_metadata_requires_no_authentication():
    public={"tag_name":"v1.0.0","html_url":updates.RELEASES_URL,"assets":[]}
    client=FakeClient({updates.API:FakeResponse(body=public)})
    result=updates.get_latest(client)
    assert result.available and result.repository==REPO and result.anonymous_access
    assert client.called==[updates.API]


def test_missing_release_uses_official_browser_fallback():
    client=FakeClient({updates.API:FakeResponse(404)})
    result=updates.get_latest(client)
    assert result.requires_browser and not result.available
    assert result.repository==REPO and result.url==updates.RELEASES_URL
    assert client.called==[updates.API]


def test_unverified_or_other_repository_assets_cannot_be_auto_downloaded():
    missing_proof=updates.UpdateResult(True,'1.0.0',updates.RELEASES_URL,repository=REPO)
    with pytest.raises(PermissionError):
        updates._trusted_setup_asset(missing_proof)
    wrong_repo=updates.UpdateResult(True,'1.0.0',updates.RELEASES_URL,
        repository='other-owner/not-star',anonymous_access=True)
    with pytest.raises(PermissionError):
        updates._trusted_setup_asset(wrong_repo)


@pytest.mark.parametrize("flag",["draft","prerelease"])
def test_draft_and_prerelease_are_not_auto_updates(flag):
    client=FakeClient({updates.API:FakeResponse(body={
        'tag_name':'v1.0.0','assets':[],flag:True})})
    result=updates.get_latest(client)
    assert not result.available and result.requires_browser


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
    try:(extra/'index.html').symlink_to(ROOT/'site/index.html')
    except (OSError, NotImplementedError):pytest.skip('Symlinks unavailable on this test host')
    with pytest.raises(ValueError):collect_public_files(extra)


def test_public_web_version_and_download_location():
    site=json.loads((ROOT/'site/version.json').read_text())
    assert site['version']==__version__
    assert site['download']==f'https://github.com/{REPO}/releases/latest'
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
