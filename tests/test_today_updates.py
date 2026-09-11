"""Besuchsgrenzen und Neuigkeiten brauchen weder Themen-Abos noch Lesemarken."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

from council.store import CouncilStore
from kern.store import Store
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from app.deps import get_store, get_council_store  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402


@pytest.fixture
def stores(tmp_path, monkeypatch):
    users = Store(tmp_path / 'users.sqlite')
    council = CouncilStore(tmp_path / 'council.sqlite')
    uid = users.create_web_user('besuch@example.org', 'unused', status='active', email_verified=True)
    original = council.updates_since
    def fixed_today(*args, **kwargs):
        kwargs.setdefault('today', '2026-09-11')
        return original(*args, **kwargs)
    monkeypatch.setattr(council, 'updates_since', fixed_today)
    yield users, council, uid
    users.close()
    council.close()


def test_visit_window_stays_stable_and_catches_changes_during_previous_visit(stores):
    users, _, uid = stores
    start = datetime(2026, 9, 1, 8, tzinfo=timezone.utc)
    users.record_visit(uid, start)
    first = users.visit_window(uid)
    assert first['first_visit']
    assert datetime.fromisoformat(first['since']) == start - timedelta(days=7)
    for minute in [0, 5, 15, 40]:
        users.record_visit(uid, start + timedelta(minutes=minute))
        assert users.visit_window(uid) == first
    assert users.visit_window(uid, start + timedelta(days=2)) == first
    users.record_visit(uid, start + timedelta(days=2))
    second = users.visit_window(uid)
    assert not second['first_visit']
    assert second['since'] == first['until']
    users.record_visit(uid, start + timedelta(days=2, seconds=1))
    assert users.visit_window(uid) == second
    other = users.create_web_user('anders@example.org', 'unused')
    assert users.visit_window(other, start)['first_visit']


def test_visit_migration_preserves_existing_accounts(tmp_path):
    path = tmp_path / 'old.sqlite'
    users = Store(path)
    uid = users.create_web_user('alt@example.org', 'unused')
    for col in ['visit_started_at', 'visit_previous_at', 'visit_active_at']:
        users._conn.execute(f'ALTER TABLE web_users DROP COLUMN {col}')
    users.close()
    users = Store(path)
    users.record_visit(uid)
    assert users.visit_window(uid)['first_visit']
    users.close()


def seed_updates(council):
    with council._conn:
        council._conn.executemany(
            "INSERT INTO council_sessions VALUES (?, ?, ?, '', '', ?)",
            [(1, 'Jugendhilfeausschuss', '2026-05-01', '2026-09-05'),
             (2, 'Sozialausschuss', '2026-09-15', '2026-09-05'),
             (3, 'Finanzausschuss', '2026-09-16', '2026-09-05')])
        council._conn.executemany(
            'INSERT INTO agenda_snapshots VALUES (?, ?, ?, ?)',
            [(2, 'a', '[]', '2026-09-02T10:00:00'), (2, 'b', '[]', '2026-09-03T10:00:00'),
             (3, 'a', '[]', '2026-08-20T10:00:00')])
        council._conn.executemany(
            'INSERT INTO agenda_changes (ksinr, changed_at, diff_json) VALUES (?, ?, ?)',
            [(2, '2026-09-03T10:00:00', '{}'), (3, '2026-09-03T11:00:00', '{}'),
             (3, '2026-09-03T12:00:00', '{}'), (3, '2026-10-01T12:00:00', '{}')])
        council._conn.execute(
            "INSERT INTO council_protocols (ksinr, extracted_at, available_at) VALUES (1, ?, ?)",
            ('2026-09-04T09:00:00', '2026-09-04T09:00:00'))


def test_arrivals_count_old_sessions_but_not_refreshes_or_duplicate_agenda_changes(stores):
    _, council, _ = stores
    seed_updates(council)
    result = council.updates_since('2026-09-01T00:00:00Z', '2026-09-05T00:00:00Z', limit=2)
    assert result['counts'] == {'protocol': 1, 'agenda': 1, 'agenda_change': 1}
    assert result['items'][0]['session_date'] == '2026-05-01'
    assert result['items'][1]['id'] == 'agenda:2'
    remaining = council.updates_since('2026-09-01T00:00:00Z', '2026-09-05T00:00:00Z', offset=2)
    assert [i['id'] for i in remaining['items']] == ['agenda_change:3']
    assert council.updates_since('2026-09-04T11:00:00+02:00', '2026-09-05T00:00:00Z')['total'] == 0
    council.save_protocol(1, {}, {}, '', 0, 'test', [], [])
    assert council.updates_since('2026-09-05T00:00:00Z', '2099-01-01')['total'] == 1
    council.mark_protocol_failed(1, {})
    council.save_protocol(1, {}, {}, '', 0, 'test', [], [])
    assert council._conn.execute('SELECT available_at FROM council_protocols WHERE ksinr=1').fetchone()[0] == '2026-09-04T09:00:00'


def test_protocol_migration_does_not_change_known_import_time(tmp_path):
    path = tmp_path / 'council.sqlite'
    council = CouncilStore(path)
    seed_updates(council)
    council._conn.execute('ALTER TABLE council_protocols DROP COLUMN available_at')
    council.close()
    for _ in range(2):
        council = CouncilStore(path)
        assert council._conn.execute('SELECT available_at FROM council_protocols WHERE ksinr=1').fetchone()[0] == '2026-09-04T09:00:00'
        council.close()


def test_api_requires_account_no_topics_and_keeps_pagination_window(stores):
    users, council, uid = stores
    seed_updates(council)
    users.record_visit(uid, datetime(2026, 9, 1, tzinfo=timezone.utc))
    users.record_visit(uid, datetime(2026, 9, 5, tzinfo=timezone.utc))
    app.dependency_overrides[get_store] = lambda: users
    app.dependency_overrides[get_council_store] = lambda: council
    try:
        client = TestClient(app)
        assert client.get('/api/today/updates').status_code == 401
        assert client.post('/api/today/visit').status_code == 401
        client.headers['Authorization'] = 'Bearer ' + create_access_token(uid)
        previous = users.visit_window(uid)
        result = client.get('/api/today/updates').json()
        assert result['total'] == 3
        assert result['first_visit'] is False
        assert users.visit_window(uid) == previous
        client.post('/api/today/visit')
        page = client.get('/api/today/updates', params={
            'since': result['since'], 'until': result['until'], 'offset': 2, 'limit': 1,
        }).json()
        assert page['total'] == 3 and page['items'][0]['id'] == 'agenda_change:3'
        group = client.get('/api/today/updates', params={
            'since': result['since'], 'until': result['until'], 'kind': 'agenda_change', 'committee': 'Finanzausschuss',
        }).json()
        assert group['total'] == 1 and group['items'][0]['id'] == 'agenda_change:3'
        assert client.get('/api/today/updates?kind=invalid').status_code == 422
        assert client.get('/api/today/updates?since=2026-09-01').status_code == 422
        with users._conn:
            users._conn.execute("UPDATE web_users SET status='disabled' WHERE id=?", (uid,))
        assert client.get('/api/today/updates').status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_chronicle_is_recorded_even_without_any_subscribers(tmp_path, monkeypatch):
    import importlib.util
    from unittest.mock import Mock
    from council.scraper import CouncilSession, AgendaItem
    from datetime import date

    spec = importlib.util.spec_from_file_location('committees_today', Path(__file__).resolve().parents[1] / 'scripts' / 'check_committees.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    users_path, council_path = tmp_path / 'u.sqlite', tmp_path / 'c.sqlite'
    monkeypatch.setattr(module, 'RATSLOTSE_DB', str(users_path))
    monkeypatch.setattr(module, 'COUNCIL_DB', str(council_path))
    session = CouncilSession(77, 'Rat', (date.today() + timedelta(days=3)).isoformat(), '17:00', 'Rathaus',
                             [AgendaItem('Ö 1', 'Neue Radwege')])
    scraper = Mock()
    scraper.fetch_committee_list.return_value = []
    scraper.upcoming_calendar.return_value = ([77], [])
    scraper.fetch_session.return_value = session
    monkeypatch.setattr(module, 'CouncilScraper', lambda: scraper)
    monkeypatch.setattr('council.impact.rate_agenda_batch', lambda items: [(i['id'], 50, 'Test') for i in items])
    monkeypatch.setattr(module.notify, 'zustellen', lambda *args, **kwargs: 0)
    module.main()
    session.agenda_items.append(AgendaItem('Ö 2', 'Neue Schulwege'))
    module.main()
    council = CouncilStore(council_path)
    assert council.get_latest_agenda_snapshot(77)[1]['title'] == 'Neue Schulwege'
    assert len(council.agenda_changes(77)) == 1
    council.close()


def test_agendas_expire_after_meeting_day_but_protocols_remain(stores):
    _, council, _ = stores
    seed_updates(council)
    window = ('2026-09-01T00:00:00Z', '2026-09-05T00:00:00Z')
    # Dasselbe Besuchsfenster: der Kalendertag bestimmt die Relevanz.
    assert council.updates_since(*window, today='2026-09-15')['total'] == 3
    tomorrow = council.updates_since(*window, today='2026-09-16')
    assert tomorrow['counts'] == {'protocol': 1, 'agenda_change': 1}
    later = council.updates_since(*window, today='2026-09-17')
    assert later['counts'] == {'protocol': 1}
    assert later['items'][0]['session_date'] == '2026-05-01'


def test_four_months_bundle_protocols_by_committee_and_page_only_selected_group(stores):
    _, council, _ = stores
    with council._conn:
        for i in range(849):
            day = (datetime(2026, 1, 1) + timedelta(days=i % 240)).date().isoformat()
            council._conn.execute(
                "INSERT INTO council_sessions VALUES (?, ?, ?, '', '', ?)",
                (i + 1, f'Gremium {i % 17}', day, '2026-09-05'))
            council._conn.execute(
                "INSERT INTO council_protocols (ksinr, extracted_at, available_at) VALUES (?, ?, ?)",
                (i + 1, '2026-06-24T10:00:00', '2026-06-24T10:00:00'))
    window = ('2026-05-11T00:00:00Z', '2026-09-11T00:00:00Z')
    result = council.updates_since(*window)
    assert result['total'] == 849 and len(result['items']) == 3
    assert len(result['groups']) == 17
    assert sum(g['count'] for g in result['groups']) == 849
    group = next(g for g in result['groups'] if g['committee'] == 'Gremium 0')
    assert group['count'] == 50
    assert group['latest']['session_date'] == group['last_session_date']
    page = council.updates_since(*window, kind='protocol', committee='Gremium 0', offset=3)
    assert page['total'] == 50 and len(page['items']) == 3
    assert all(i['committee'] == 'Gremium 0' for i in page['items'])
    assert len(page['groups']) == 1
    first = council.updates_since(*window, kind='protocol', committee='Gremium 0')
    assert not {i['id'] for i in first['items']} & {i['id'] for i in page['items']}
    assert [i['session_date'] for i in first['items'] + page['items']] == sorted(
        [i['session_date'] for i in first['items'] + page['items']], reverse=True)
    end = council.updates_since(*window, kind='protocol', committee='Gremium 0', offset=50)
    assert end['items'] == [] and end['groups'] == first['groups']
