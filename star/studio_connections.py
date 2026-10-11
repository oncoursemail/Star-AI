"""Host-selected Studio connections shared by the desktop and STAR's local MCP.

Only opaque route/instance choices cross the UI boundary, never launcher commands.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

TARGETS = {'local_pc': 'Roblox Studio on this PC',
           'host_launcher': 'Practice Studio (configured host)'}
PROBE_SECONDS = 15


def default_target() -> str:
    # A downloaded app starts with the user's PC regardless of an operator environment.
    return 'local_pc'


def validate_target(target: str) -> str:
    if type(target) is not str or target not in TARGETS:
        raise ValueError('Select this PC or the configured STAR Studio server')
    return target


def connection_status(settings, cached: dict | None = None) -> dict:
    target = validate_target(settings.studio_target)
    if (cached and cached.get('target') == target
            and cached.get('selected_id', '') == settings.studio_id):
        return dict(cached)
    configured = True
    if target == 'host_launcher':
        from .studio import custom_launcher
        try:
            configured = custom_launcher() is not None
        except Exception:
            configured = False
    return {'target': target, 'label': TARGETS[target],
            'state': 'not_checked' if configured else 'unconfigured',
            'checked_at': '', 'tool_count': 0, 'instances': [],
            'selected_id': settings.studio_id, 'selected_valid': False,
            'reason_code': '' if configured else 'host_launcher_unavailable',
            'local_mcp': 'not_checked', 'server_name': 'STAR local MCP'}


def _text(value, bound=200):
    return (type(value) is str and 0 < len(value) <= bound
            and value == value.strip() and not any(ord(c) < 32 for c in value))


def normalize_probe(settings, value) -> dict:
    result = connection_status(settings)
    if (type(value) is not dict or value.get('status') not in {'tools_and_instances_discovered', 'tools_discovered_no_instances'}
            or value.get('target') != settings.studio_target
            or value.get('local_mcp') != 'memory' or value.get('server_name') != 'STAR local MCP'
            or type(value.get('tool_count')) is not int or not 1 <= value['tool_count'] <= 1000
            or type(value.get('studios')) is not list or len(value['studios']) > 32):
        raise ValueError('Invalid Studio discovery evidence')
    if bool(value['studios']) != (value['status'] == 'tools_and_instances_discovered'):
        raise ValueError('Studio discovery status does not match its instance evidence')
    instances, seen = [], set()
    for entry in value['studios']:
        if (type(entry) is not dict or not _text(entry.get('id')) or not _text(entry.get('name'))
                or entry['id'] in seen):
            raise ValueError('Invalid Studio instance evidence')
        seen.add(entry['id'])
        instances.append({'id': entry['id'], 'name': entry['name']})
    result.update(state='connected' if instances else 'no_instances', instances=instances,
                  checked_at=datetime.now(timezone.utc).isoformat(), tool_count=value['tool_count'],
                  selected_valid=settings.studio_id in seen, reason_code='', local_mcp='memory')
    return result


async def discover(settings) -> dict:
    result = connection_status(settings)
    if result['state'] == 'unconfigured':
        return result
    from . import local_mcp
    try:
        value = await asyncio.wait_for(local_mcp.discover(target=settings.studio_target), PROBE_SECONDS)
        return normalize_probe(settings, value)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        result.update(state='unavailable', instances=[], selected_valid=False,
                      checked_at=datetime.now(timezone.utc).isoformat(),
                      reason_code='timeout' if isinstance(exc, TimeoutError) else 'connection_failed')
        return result


async def select_instance(settings, identifier: str) -> dict:
    if not _text(identifier):
        raise ValueError('Choose a discovered Studio instance')
    report = await discover(settings)
    if report['state'] != 'connected' or identifier not in {item['id'] for item in report['instances']}:
        raise ValueError('The selected Studio is not available on this connection; test it again')
    settings.studio_id = identifier
    settings.studio_edit = False
    settings.studio_luau = False
    return {**report, 'selected_id': identifier, 'selected_valid': True}
