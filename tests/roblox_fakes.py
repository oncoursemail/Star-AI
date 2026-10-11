"""A stand-in for apis.roblox.com, shaped after the documented Open Cloud answers.

Statuses for the failure cases are the ones the real service gave on 2026-10-11 (reads only): 403
without a key, 401 for a key Roblox does not accept, 400 from introspect for text that is not a key,
200 for the metadata of a universe the key's account does not own.
"""
from __future__ import annotations

import json
import re

import httpx

KEY = "FakeRobloxKey0123456789+/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=="
ACCOUNT = 4242
UNIVERSE, PLACE = 7001, 9001
ALL = {"universeIds": ["*"]}
FULL_SCOPES = [
    {"name": "universe-places", "operations": ["write"], **ALL},
    {"name": "universe.place.luau-execution-session", "operations": ["read", "write"], **ALL},
    {"name": "universe-datastores.control", "operations": ["list"], **ALL},
    {"name": "universe", "operations": ["read", "write"], **ALL},
]


class FakeRoblox:
    def __init__(self, *, scopes=None, account=ACCOUNT):
        self.key = KEY
        self.account = account
        self.scopes = FULL_SCOPES if scopes is None else scopes
        self.enabled, self.expired, self.revoked = True, False, False
        self.universes = {UNIVERSE: {"path": f"universes/{UNIVERSE}", "displayName": "STAR Test Place",
                                     "user": f"users/{account}", "visibility": "PRIVATE",
                                     "rootPlace": f"universes/{UNIVERSE}/places/{PLACE}"}}
        self.places = {(UNIVERSE, PLACE): {"path": f"universes/{UNIVERSE}/places/{PLACE}",
                                           "displayName": "STAR Test Place", "serverSize": 10}}
        self.calls: list[tuple[str, str]] = []
        self.published: list[dict] = []
        self.tasks: dict[str, dict] = {}
        self.version = 3
        self.polls_before_done = 2
        self.task_result = {"state": "COMPLETE", "output": {"results": [{"passed": 2, "failed": 0, "cases": [
            {"name": "Shop.spec: buys", "ok": True}, {"name": "Shop.spec: refuses", "ok": True}]}]}}
        self.logs = ['STAR_TEST_RESULT {"passed":2,"failed":0,"cases":[]}']
        self.fail: dict[str, int] = {}          # endpoint label -> status to answer once
        self.seen_keys: set[str] = set()        # every credential value the fake was sent
        self.task_path_override: str | None = None

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))

    def writes(self) -> list[tuple[str, str]]:
        return [call for call in self.calls if call[0] != "GET" and not call[1].endswith("/introspect")]

    # ------------------------------------------------------------------ dispatch
    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url.scheme == "https" and request.url.host == "apis.roblox.com"
        path, method = request.url.path, request.method
        self.calls.append((method, path))
        if path == "/api-keys/v1/introspect" and method == "POST":
            return self._introspect(json.loads(request.content))
        key = request.headers.get("x-api-key")
        if key is None:
            return self._json(403, {"errors": [{"code": 0, "message": "Invalid authentication data provided"}]})
        self.seen_keys.add(key)
        if key != self.key or self.revoked:
            return self._json(401, {"errors": [{"code": 0, "message": "Invalid API Key"}]})
        for pattern, label, handler in self._routes:
            found = re.fullmatch(pattern, path)
            if found and handler.__name__.startswith("_" + method.lower()):
                if label in self.fail:
                    return self._json(self.fail.pop(label), {"message": "simulated"})
                return handler(self, request, *found.groups())
        return self._json(404, {"message": "not an endpoint of the fake"})

    @staticmethod
    def _json(status, body) -> httpx.Response:
        return httpx.Response(status, json=body)

    def _introspect(self, body) -> httpx.Response:
        key = body.get("apiKey")
        self.seen_keys.add(str(key))
        if not isinstance(key, str) or len(key) < 40:
            return self._json(400, {"code": 3, "message": "API Key is not provided in a valid format."})
        if key != self.key or self.revoked:
            return self._json(401, {"errors": [{"code": 0, "message": "Invalid API Key"}]})
        return self._json(200, {"name": "star", "authorizedUserId": self.account, "scopes": self.scopes,
                                "enabled": self.enabled, "expired": self.expired})

    # ------------------------------------------------------------------ reads
    def _get_user(self, request, user):
        return self._json(200, {"path": f"users/{user}", "id": user, "name": "StarOwnAccount"})

    def _get_universe(self, request, universe):
        found = self.universes.get(int(universe))
        return self._json(200, found) if found else self._json(404, {"message": "not found"})

    def _get_place(self, request, universe, place):
        found = self.places.get((int(universe), int(place)))
        return self._json(200, found) if found else self._json(
            400, {"code": "INVALID_ARGUMENT", "message": "No universe exists for place"})

    def _get_stores(self, request, universe):
        owned = self.universes.get(int(universe), {}).get("user") == f"users/{self.account}"
        return self._json(200, {"dataStores": [{"path": f"universes/{universe}/data-stores/Coins", "id": "Coins"}]}) \
            if owned else self._json(401, {"code": 16, "message": "Not authorized."})

    # ------------------------------------------------------------------ writes
    def _post_publish(self, request, universe, place):
        self.version += 1
        self.published.append({"universe": int(universe), "place": int(place), "bytes": request.content,
                               "content_type": request.headers.get("content-type"),
                               "version_type": request.url.params.get("versionType")})
        return self._json(200, {"versionNumber": self.version})

    def _post_task(self, request, universe, place, version=None):
        script = json.loads(request.content)["script"]
        number = len(self.tasks) + 1
        path = (f"universes/{universe}/places/{place}/versions/{version or self.version}"
                f"/luau-execution-sessions/session-{number}/tasks/task-{number}")
        self.tasks[path] = {"script": script, "polls": 0}
        return self._json(200, {"path": self.task_path_override or path, "state": "QUEUED", "user": str(self.account)})

    def _get_task(self, request, universe, place, version, session, task):
        path = f"universes/{universe}/places/{place}/versions/{version}/luau-execution-sessions/{session}/tasks/{task}"
        record = self.tasks.get(path)
        if record is None:
            return self._json(404, {"message": "no such task"})
        record["polls"] += 1
        if record["polls"] <= self.polls_before_done:
            return self._json(200, {"path": path, "state": "PROCESSING"})
        return self._json(200, {"path": path, **self.task_result})

    def _get_logs(self, request, universe, place, version, session, task):
        return self._json(200, {"luauExecutionSessionTaskLogs": [{"path": "logs/1", "messages": self.logs}]})

    _TASK = (r"/cloud/v2/universes/(\d+)/places/(\d+)/versions/(\d+)"
             r"/luau-execution-sessions/([\w-]+)/tasks/([\w-]+)")
    _routes = (
        (r"/cloud/v2/users/(\d+)", "user", _get_user),
        (r"/cloud/v2/universes/(\d+)", "universe", _get_universe),
        (r"/cloud/v2/universes/(\d+)/places/(\d+)", "place", _get_place),
        (r"/cloud/v2/universes/(\d+)/data-stores", "data_stores", _get_stores),
        (r"/universes/v1/(\d+)/places/(\d+)/versions", "publish", _post_publish),
        (r"/cloud/v2/universes/(\d+)/places/(\d+)/versions/(\d+)/luau-execution-session-tasks", "create", _post_task),
        (r"/cloud/v2/universes/(\d+)/places/(\d+)/luau-execution-session-tasks", "create", _post_task),
        (_TASK, "task", _get_task),
        (_TASK + "/logs", "logs", _get_logs),
    )
