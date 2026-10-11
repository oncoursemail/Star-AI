"""First-token metrics and export privacy are measurable, not fabricated."""
import json
from pathlib import Path
import zipfile

from star.analytics import AnalyticsStore
from star.diagnostics import _read_activity, export_review_bundle
from star.desktop_core import Settings
from star.react_shell import ALLOWED_ACTIONS

def test_first_visible_token_metrics_are_aggregate_and_private(tmp_path):
    metrics=AnalyticsStore(tmp_path/'analytics.sqlite3')
    for milliseconds in [110,330,680]:
        metrics.record('PRIVATE_PROJECT','first_token',elapsed_ms=milliseconds)
    metrics.record('PRIVATE_PROJECT','run_succeeded',elapsed_ms=2220)
    metrics.close()
    snapshot=_read_activity(tmp_path)
    assert snapshot['first_visible_token_ms']=={'count':3,'p50':330,'p95':680}
    assert snapshot['duration_ms']['p50']==2220
    assert 'PRIVATE_PROJECT' not in json.dumps(snapshot)

def test_review_action_is_explicit_only():
    assert 'exportReviewBundle' in ALLOWED_ACTIONS
    assert 'copyEntireDisk' not in ALLOWED_ACTIONS
    source=(Path(__file__).resolve().parents[1]/'star/react_shell.py').read_text()
    assert "include_screen=body.get('includeScreenshot',False)" in source
    assert "if include_screen:" in source
    assert 'QFileDialog.getSaveFileName' in source

def test_activity_without_database_is_honest(tmp_path):
    bundle=export_review_bundle(tmp_path,Settings(),tmp_path/'review.zip')
    with zipfile.ZipFile(bundle) as package:
        stats=json.loads(package.read('activity-summary.json'))
        assert stats['first_visible_token_ms']['count']==0
        assert stats['events']=={}
        assert 'current-screen.png' not in package.namelist()
