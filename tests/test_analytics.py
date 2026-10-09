"""STAR analytics is real data, local-only, and project isolated."""
from datetime import datetime, timezone, timedelta
import pytest
from star.analytics import AnalyticsStore, get_dashboard
from star.desktop_core import Conversations


def test_empty_analytics_does_not_fabricate_activity(tmp_path):
    result = get_dashboard(tmp_path, 'VALEN')
    assert result['started'] == result['succeeded'] == result['failed'] == 0
    assert result['tools'] == result['messages'] == 0
    assert len(result['trend']) == 14 and all(x['runs'] == 0 for x in result['trend'])
    assert result['recent'] == [] and result['median_ms'] is None


def test_project_isolation_trend_and_median(tmp_path):
    clock = datetime(2026, 10, 9, tzinfo=timezone.utc)
    store = AnalyticsStore(tmp_path / 'analytics.sqlite3')
    store.record('VALEN','run_started',at=clock-timedelta(days=1))
    store.record('VALEN','run_succeeded',elapsed_ms=2100,at=clock-timedelta(days=1))
    store.record('VALEN','run_started',at=clock)
    store.record('VALEN','run_failed',detail='Tool error',at=clock)
    store.record('VALEN','tool_completed',at=clock)
    store.record('OTHER','run_started',at=clock)
    result=store.summary('VALEN',14,now=clock)
    assert result['started'] == 2
    assert result['succeeded'] == 1 and result['failed'] == 1
    assert result['tools'] == 1 and result['median_ms'] == 2100
    assert [x['runs'] for x in result['trend']][-2:] == [1,1]
    assert store.summary('OTHER',14,now=clock)['started'] == 1
    store.close()


def test_user_messages_are_counted_from_real_conversation_db(tmp_path):
    db=Conversations(tmp_path/'conversations.sqlite3')
    db.add('VALEN','user','hello')
    db.add('VALEN','assistant','world')
    db.add('OTHER','user','other')
    db.close()
    assert get_dashboard(tmp_path,'VALEN')['messages'] == 1


def test_invalid_or_sensitive_values_are_refused_and_details_truncated(tmp_path):
    store=AnalyticsStore(tmp_path/'a.db')
    with pytest.raises(ValueError):store.record('A','arbitrary_event')
    with pytest.raises(ValueError):store.record('A','run_succeeded',elapsed_ms=-5)
    store.record('A','run_failed',detail='e'*300)
    row=store.connection.execute('SELECT detail FROM events').fetchone()[0]
    assert len(row) == 180
    store.close()
