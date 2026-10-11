"""Host-selected Studio connections shared by the desktop and STAR's local MCP.

Only opaque route/instance choices cross the UI boundary, never launcher commands.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from . import studio

TARGETS = {'local_pc': 'Roblox Studio on this PC',
           'host_launcher': 'Practice Studio (configured host)'}
# Include each bounded connector stage and the private local MCP status exchange.
PROBE_SECONDS = studio.INITIALIZE_SECONDS + studio.DISCOVERY_SECONDS + studio.INSTANCE_SECONDS + 5


def default_target() -> str:
    # A downloaded app starts with the user's PC regardless of an operator environment.
    return 'local_pc'


def validate_target(target: str) -> str:
    if type(target) is not str or target not in TARGETS:
        raise ValueError('Select this PC or the configured STAR Studio server')
    return target


def connection_status(settings, cached: dict | None = None, *, home=None) -> dict:
    target = validate_target(settings.studio_target)
    if (cached and cached.get('target') == target
            and cached.get('selected_id', '') == settings.studio_id):
        return dict(cached)
    configured = True
    diagnostic = None
    if target == 'host_launcher':
        try:
            configured = studio.configured_command(home) is not None
            if not configured:
                diagnostic = {'stage': 'configuration', 'reason': 'not_configured'}
        except Exception as exc:
            configured = False
            diagnostic = studio.connection_diagnostic(exc)
    return {'target': target, 'label': TARGETS[target],
            'state': 'not_checked' if configured else 'unconfigured',
            'checked_at': '', 'tool_count': 0, 'instances': [],
            'selected_id': settings.studio_id, 'selected_valid': False,
            'reason_code': '' if configured else 'host_launcher_unavailable',
            'diagnostic': diagnostic,
            'local_mcp': 'not_checked', 'server_name': 'STAR local MCP'}


def _text(value, bound=200):
    return (type(value) is str and 0 < len(value) <= bound
            and value == value.strip() and not any(ord(c) < 32 for c in value))


def normalize_probe(settings, value, *, home=None) -> dict:
    result = connection_status(settings, home=home)
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
                  selected_valid=settings.studio_id in seen, reason_code='', local_mcp='memory',
                  # Connector-supplied diagnostic fields are never copied or trusted.
                  diagnostic=None if instances else {'stage': 'instance_discovery', 'reason': 'no_instances'})
    return result


async def discover(settings, *, home=None) -> dict:
    result = connection_status(settings, home=home)
    if result['state'] == 'unconfigured':
        return result
    from . import local_mcp
    try:
        value = await asyncio.wait_for(local_mcp.discover(target=settings.studio_target, home=home), PROBE_SECONDS)
        try:
            return normalize_probe(settings, value, home=home)
        except ValueError:
            raise studio.StudioTransportError('Invalid Studio discovery evidence',
                                               stage='probe', reason='invalid_evidence') from None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        result.update(state='unavailable', instances=[], selected_valid=False,
                      checked_at=datetime.now(timezone.utc).isoformat(),
                      reason_code='timeout' if isinstance(exc, TimeoutError) else 'connection_failed',
                      diagnostic={'stage': 'probe', 'reason': 'timeout'} if isinstance(exc, TimeoutError)
                      else studio.connection_diagnostic(exc))
        return result


async def select_instance(settings, identifier: str, *, home=None) -> dict:
    if not _text(identifier):
        raise ValueError('Choose a discovered Studio instance')
    report = await discover(settings, home=home)
    if report['state'] != 'connected' or identifier not in {item['id'] for item in report['instances']}:
        raise ValueError('The selected Studio is not available on this connection; test it again')
    settings.studio_id = identifier
    settings.studio_edit = False
    settings.studio_luau = False
    return {**report, 'selected_id': identifier, 'selected_valid': True}
