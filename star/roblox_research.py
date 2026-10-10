"""Bounded, evidence-first Roblox research for STAR's existing chat.

Public web endpoints can change without notice. This module only performs GET
requests against fixed Roblox/Discourse/YouTube hosts; it is not a web browser,
an authenticated Roblox client, a video downloader, or a Studio editor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import json
import os
import re
import sqlite3
import time
import uuid

import httpx

_MAX_BYTES = 240_000
_MAX_QUERY = 140
_HOSTS = {
    "games": "https://games.roblox.com",
    "thumbnails": "https://thumbnails.roblox.com",
    "apis": "https://apis.roblox.com",
    "forum": "https://devforum.roblox.com",
    "youtube": "https://www.googleapis.com",
    "oembed": "https://www.youtube.com",
}
_DOCUMENTS = (
    ("Luau language and types", "luau", "https://create.roblox.com/docs/luau", "luau code syntax type checking script"),
    ("Engine API reference", "reference/engine", "https://create.roblox.com/docs/reference/engine", "class api services properties methods engine"),
    ("Roblox scripting", "scripting", "https://create.roblox.com/docs/scripting", "script localscript modulescript gameplay"),
    ("Remote events and callbacks", "scripting/events/remote", "https://create.roblox.com/docs/scripting/events/remote", "remoteevent remotefunction server client network security"),
    ("Luau type checking", "luau/type-checking", "https://create.roblox.com/docs/luau/type-checking", "strict type annotations lint"),
    ("Performance optimization", "performance-optimization/improve", "https://create.roblox.com/docs/performance-optimization/improve", "performance lag optimization fps profiling"),
    ("Parallel Luau", "scripting/multithreading", "https://create.roblox.com/docs/scripting/multithreading", "parallel actors multithreading"),
    ("UI design", "ui", "https://create.roblox.com/docs/ui", "gui hud ui ux layout scale animation"),
    ("Animation", "animation", "https://create.roblox.com/docs/animation", "animation animator rig motion"),
    ("Data stores", "cloud-services/data-stores", "https://create.roblox.com/docs/cloud-services/data-stores", "datastore player data saving persistence"),
    ("Physics", "physics", "https://create.roblox.com/docs/physics", "physics collision constraints vehicle"),
    ("Lighting and effects", "environment/lighting", "https://create.roblox.com/docs/environment/lighting", "lighting atmosphere rendering shadows"),
    ("Assets", "projects/assets", "https://create.roblox.com/docs/projects/assets", "assets mesh texture models materials"),
    ("Experience discovery", "discovery", "https://create.roblox.com/docs/discovery", "game genre discover recommendations retention engagement"),
    ("Analytics", "production/analytics", "https://create.roblox.com/docs/production/analytics", "game stats dau retention monetization analytics"),
    ("Open Cloud REST APIs", "cloud", "https://create.roblox.com/docs/cloud", "api open cloud tokens oauth scopes"),
    ("Open Cloud API reference", "cloud/reference", "https://create.roblox.com/docs/cloud/reference", "rest universe openapi"),
    ("Creator Store queries", "projects/assets/api", "https://create.roblox.com/docs/projects/assets/api", "creator store models meshes search marketplace"),
    ("Luau source repository", "luau", "https://github.com/luau-lang/luau", "compiler analyzer lint code"),
    ("Creator documentation source", "creator-docs", "https://github.com/Roblox/creator-docs", "docs source markdown github"),
)
_GENRES = {
    "obby / platformer": ("obby", "obstacle course", "parkour", "platforming", "jump across"),
    "simulator / incremental": ("simulator", "clicker", "rebirth", "hatch eggs", "upgrade your"),
    "tycoon / management": ("tycoon", "factory", "business empire", "build your empire", "manage your"),
    "roleplay / social": ("roleplay", "role play", "rp ", "hangout", "socialize", "adopt a"),
    "survival / horror": ("survival", "killer", "horror", "escape the monster", "scary", "nightmare"),
    "shooter / FPS": ("fps", "first person shooter", "gunfight", "shooter", "shoot enemies"),
    "racing / driving": ("race", "racing", "drift", "driving", "cars", "vehicles"),
    "combat / battlegrounds": ("battleground", "fighting game", "fight other", "arena combat", "pvp"),
    "tower defense / strategy": ("tower defense", "strategy", "defend waves", "place towers"),
    "puzzle / escape": ("puzzle", "escape room", "solve clues", "riddles"),
    "collecting / trading": ("collect pets", "trade pets", "collect characters", "collect items"),
}


def _positive_id(value, *, name="universe_id") -> int:
    if type(value) not in (int, str) or not re.fullmatch(r"[1-9][0-9]{0,17}", str(value)):
        raise ValueError(f"{name} must be a positive Roblox numeric ID")
    return int(value)


def _query(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= _MAX_QUERY:
        raise ValueError("Research query must contain 1 to 140 characters")
    return value.strip()


def _safe_image(value) -> str | None:
    if not isinstance(value, str) or len(value) > 1500:
        return None
    url = urlsplit(value)
    host = (url.hostname or "").lower()
    if url.scheme == "https" and not url.username and not url.password and (
        host.endswith(".rbxcdn.com") or host in {"i.ytimg.com", "img.youtube.com"}
    ):
        return value
    return None


def _safe_int(value):
    return value if type(value) is int and value >= 0 else None


def _short(value, maximum=250):
    return str(value or "")[:maximum]


def infer_game_type(name: str, description: str, platform_genre: str = "") -> dict:
    """Transparent label hypotheses, never an assertion about actual gameplay."""
    text = (name + " " + description).lower()
    matches = []
    for label, keywords in _GENRES.items():
        clues = [phrase for phrase in keywords if phrase in text]
        if clues:
            matches.append({"type": label, "clues": clues[:3], "score": len(clues)})
    matches.sort(key=lambda x: (-x["score"], x["type"]))
    return {
        "platform_label": _short(platform_genre, 80) or None,
        "inferred_types": matches[:3],
        "confidence": ("medium" if matches and matches[0]["score"] >= 2 else
                       "low" if matches else "insufficient evidence"),
        "method": "Title/description keyword clues only; requires screenshots, gameplay footage or Studio inspection to verify mechanics.",
    }


class RobloxResearch:
    """Read-only adapter with bounded responses and per-task TTL caching.

    All request origins and paths are developer-defined. A model never supplies
    a host, arbitrary URL, HTTP method, cookie, proxy, or authorization header.
    """

    def __init__(self, *, home: Path, client: httpx.Client | None = None, now=None):
        self.home = Path(home)
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(6.0, connect=3.0),
            follow_redirects=False, trust_env=False,
            headers={"User-Agent": "STAR-Intelligence-Research/1.0", "Accept": "application/json"},
        )
        self._owns_client = client is None
        self.now = now or time.time
        self._cache: dict[tuple, tuple[float, dict]] = {}

    def close(self):
        if self._owns_client:
            self.client.close()

    def status(self) -> dict:
        return {
            "enabled": True, "read_only": True, "public_game_data": True,
            "forum": "best effort; rate limits / challenge pages possible",
            "youtube_data_api_configured": bool(os.environ.get("STAR_YOUTUBE_API_KEY")),
            "open_cloud_read_configured": bool(os.environ.get("STAR_ROBLOX_READ_API_KEY")),
            "note": "No API keys, cookies, uploads or game publishing exposed to the model.",
        }

    def _get(self, host: str, path: str, params=None, *, ttl=90, api_key=None) -> dict:
        # All callers construct literal paths, except validated numeric IDs.
        if host not in _HOSTS or not path.startswith("/") or "//" in path or ".." in path:
            raise ValueError("Unapproved research endpoint")
        params = params or {}
        cache_key = (host, path, tuple(sorted((k, str(v)) for k, v in params.items())))
        cached = self._cache.get(cache_key)
        if cached and self.now() < cached[0]:
            return cached[1]
        headers = {"x-api-key": api_key} if api_key else None
        try:
            with self.client.stream("GET", _HOSTS[host] + path, params=params, headers=headers,
                                    follow_redirects=False) as response:
                if response.status_code == 429:
                    raise ValueError(f"{host} is rate limiting requests; retry later")
                if response.status_code != 200:
                    raise ValueError(f"{host} returned HTTP {response.status_code}; data unavailable")
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise ValueError(f"{host} returned non-JSON content (possibly a challenge page)")
                chunks, length = [], 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > _MAX_BYTES:
                        raise ValueError(f"{host} response exceeded the safety limit")
                    chunks.append(chunk)
            result = json.loads(b"".join(chunks))
            if not isinstance(result, dict):
                raise ValueError(f"{host} returned an unsupported response format")
        except (httpx.RequestError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{host} is unreachable or returned invalid JSON ({type(exc).__name__})") from None
        self._cache[cache_key] = (self.now() + ttl, result)
        if len(self._cache) > 100:
            self._cache = {k: v for k, v in self._cache.items() if self.now() < v[0]}
        return result

    def _game_raw(self, universe_id: int) -> dict:
        result = self._get("games", "/v1/games", {"universeIds": universe_id}, ttl=100)
        for item in result.get("data", []):
            if isinstance(item, dict) and _safe_int(item.get("id")) == universe_id:
                return item
        raise ValueError("Roblox returned no public game for that Universe ID")

    def _history(self, universe_id: int, playing, visits, favorites) -> dict:
        """Historical comparisons only against samples STAR really observed."""
        if all(v is None for v in (playing, visits, favorites)):
            return {"samples": 0, "trend": "not measured"}
        self.home.mkdir(parents=True, exist_ok=True)
        db = self.home / "roblox_public_snapshots.sqlite3"
        with sqlite3.connect(db, timeout=8) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS game_snapshots ("
                               "universe_id INTEGER NOT NULL, observed_at INTEGER NOT NULL, "
                               "playing INTEGER, visits INTEGER, favorites INTEGER, "
                               "PRIMARY KEY(universe_id, observed_at))")
            current = int(self.now())
            previous = connection.execute(
                "SELECT observed_at, playing, visits, favorites FROM game_snapshots "
                "WHERE universe_id=? AND observed_at<? ORDER BY observed_at DESC LIMIT 1",
                (universe_id, current),
            ).fetchone()
            connection.execute(
                "INSERT OR REPLACE INTO game_snapshots VALUES (?,?,?,?,?)",
                (universe_id, current, playing, visits, favorites),
            )
            connection.execute("DELETE FROM game_snapshots WHERE observed_at<?",
                               (current - 90 * 86400,))
            count = connection.execute(
                "SELECT COUNT(*) FROM game_snapshots WHERE universe_id=?",
                (universe_id,),
            ).fetchone()[0]
        return {
            "samples": count,
            "previous_observed_at": datetime.fromtimestamp(previous[0], timezone.utc).isoformat() if previous else None,
            "playing_change": playing - previous[1] if previous and playing is not None and previous[1] is not None else None,
            "visits_change": visits - previous[2] if previous and visits is not None and previous[2] is not None else None,
            "favorites_change": favorites - previous[3] if previous and favorites is not None and previous[3] is not None else None,
            "note": "Changes compare observations, not a complete Roblox analytics history; no revenue, retention or DAU inferred.",
        }

    def game_report(self, universe_id) -> dict:
        universe_id = _positive_id(universe_id)
        game = self._game_raw(universe_id)
        votes, pictures, warnings = None, [], []
        try:
            payload = self._get("games", "/v1/games/votes", {"universeIds": universe_id}, ttl=120)
            votes = next((x for x in payload.get("data", [])
                          if isinstance(x, dict) and x.get("id") == universe_id), None)
        except ValueError as exc:
            warnings.append(str(exc))
        try:
            payload = self._get("thumbnails", "/v1/games/icons", {
                "universeIds": universe_id, "returnPolicy": "PlaceHolder",
                "size": "512x512", "format": "Png", "isCircular": "false",
            }, ttl=300)
            pictures.extend({"kind": "icon", "url": url} for x in payload.get("data", []) if isinstance(x, dict)
                            if (url := _safe_image(x.get("imageUrl"))))
        except ValueError as exc:
            warnings.append(str(exc))
        try:
            payload = self._get("thumbnails", "/v1/games/multiget/thumbnails", {
                "universeIds": universe_id, "countPerUniverse": 4, "size": "768x432",
                "format": "Png", "isCircular": "false",
            }, ttl=300)
            for item in payload.get("data", [])[:5]:
                if isinstance(item, dict):
                    for x in item.get("thumbnails", [])[:4]:
                        if isinstance(x, dict) and (url := _safe_image(x.get("imageUrl"))):
                            pictures.append({"kind": "thumbnail", "url": url})
        except (ValueError, TypeError) as exc:
            warnings.append(_short(exc, 150))
        player_count = _safe_int(game.get("playing"))
        visits = _safe_int(game.get("visits"))
        favorites = _safe_int(game.get("favoritedCount"))
        creator = game.get("creator") if isinstance(game.get("creator"), dict) else {}
        root_place = _safe_int(game.get("rootPlaceId"))
        name = _short(game.get("name"), 160)
        description = _short(game.get("description"), 1400)
        return {
            "universe_id": universe_id, "root_place_id": root_place,
            "url": f"https://www.roblox.com/games/{root_place}" if root_place else None,
            "name": name, "description": description,
            "creator": {"name": _short(creator.get("name"), 100), "id": _safe_int(creator.get("id")), "type": _short(creator.get("type"), 40)},
            "metrics": {
                "playing_now_snapshot": player_count, "cumulative_visits": visits,
                "favorites": favorites, "max_players_per_server": _safe_int(game.get("maxPlayers")),
                "votes_up": _safe_int(votes.get("upVotes")) if votes else None,
                "votes_down": _safe_int(votes.get("downVotes")) if votes else None,
            },
            "created": _short(game.get("created"), 50), "updated": _short(game.get("updated"), 50),
            "genre": infer_game_type(name, description, _short(game.get("genre_l1") or game.get("genre"), 80)),
            "images": pictures[:5], "history": self._history(universe_id, player_count, visits, favorites),
            "observed_at": datetime.fromtimestamp(self.now(), timezone.utc).isoformat(),
            "data_source": "https://games.roblox.com/v1/games",
            "image_source": "https://thumbnails.roblox.com",
            "caveats": [
                "Live playing is a point-in-time snapshot; visits are cumulative, not unique players.",
                "Descriptions and Roblox-provided media cannot verify all actual in-game mechanics.",
                "Public endpoints may be changed, restricted or rate limited by Roblox.",
            ],
            "warnings": warnings[:3],
        }

    def compare_games(self, universe_ids: list) -> dict:
        if not isinstance(universe_ids, list) or not 2 <= len(universe_ids) <= 4:
            raise ValueError("Compare 2 to 4 Universe IDs")
        ids = [_positive_id(x) for x in universe_ids]
        if len(set(ids)) != len(ids):
            raise ValueError("Universe IDs must be distinct")
        result = []
        errors = []
        for game_id in ids:
            try:
                row = self.game_report(game_id)
                result.append({"universe_id": game_id, "name": row["name"], "url": row["url"],
                               "metrics": row["metrics"], "genre": row["genre"],
                               "observed_at": row["observed_at"]})
            except (ValueError, OSError, sqlite3.Error) as exc:
                errors.append({"universe_id": game_id, "error": _short(exc, 180)})
        return {"games": result, "errors": errors,
                "warning": "Only comparable public snapshot metrics; do not infer game quality, earnings, retention or lifetime popularity rankings."}

    def search_games(self, query: str, limit=8) -> dict:
        query = _query(query)
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError("limit must be 1 to 12")
        payload = self._get("apis", "/search-api/omni-search", {
            "searchQuery": query, "sessionId": str(uuid.uuid4()), "pageType": "all",
        }, ttl=0)
        identifiers = []
        def visit(node, depth=0):
            if depth > 6 or len(identifiers) >= limit * 3:
                return
            if isinstance(node, dict):
                for key in ("universeId", "universe_id"):
                    value = node.get(key)
                    if type(value) in (int, str) and re.fullmatch(r"[1-9][0-9]{0,17}", str(value)):
                        identifier = int(value)
                        if identifier not in identifiers:
                            identifiers.append(identifier)
                for key, value in list(node.items())[:32]:
                    if isinstance(value, (list, dict)):
                        visit(value, depth + 1)
            elif isinstance(node, list):
                for child in node[:50]:
                    visit(child, depth + 1)
        visit(payload.get("searchResults", []))
        results, errors = [], []
        for universe_id in identifiers[:limit]:
            try:
                game = self._game_raw(universe_id)
                results.append({
                    "universe_id": universe_id, "name": _short(game.get("name"), 160),
                    "root_place_id": _safe_int(game.get("rootPlaceId")),
                    "playing_snapshot": _safe_int(game.get("playing")),
                    "visits": _safe_int(game.get("visits")),
                    "url": f"https://www.roblox.com/games/{game['rootPlaceId']}" if _safe_int(game.get("rootPlaceId")) else None,
                })
            except ValueError as exc:
                errors.append(_short(exc, 140))
        return {
            "query": query, "results": results, "errors": errors[:3],
            "search_source": "https://apis.roblox.com/search-api/omni-search",
            "note": "Undocumented and changeable public search endpoint. Search results are not a complete Roblox catalog; no exact title match guaranteed.",
        }

    def search_forum(self, query: str, limit=7) -> dict:
        query = _query(query)
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError("limit must be 1 to 12")
        payload = self._get("forum", "/search.json", {"q": query}, ttl=180)
        results = []
        for topic in payload.get("topics", [])[:limit * 2]:
            if not isinstance(topic, dict) or not _safe_int(topic.get("id")):
                continue
            results.append({
                "title": _short(topic.get("title"), 180), "url": f"https://devforum.roblox.com/t/{topic['id']}",
                "topic_id": topic["id"], "created_at": _short(topic.get("created_at"), 50),
                "posts_count": _safe_int(topic.get("posts_count")),
            })
            if len(results) >= limit:
                break
        return {"query": query, "topics": results, "source": "https://devforum.roblox.com/search",
                "note": "Community posts are not official Roblox policy or verified engine behavior."}

    def forum_latest(self, limit=7) -> dict:
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError("limit must be 1 to 12")
        payload = self._get("forum", "/latest.json", ttl=180)
        results = []
        for topic in payload.get("topic_list", {}).get("topics", [])[:limit]:
            if isinstance(topic, dict) and _safe_int(topic.get("id")):
                results.append({"title": _short(topic.get("title"), 160),
                                "url": f"https://devforum.roblox.com/t/{topic['id']}",
                                "created_at": _short(topic.get("created_at"), 50),
                                "last_posted_at": _short(topic.get("last_posted_at"), 50)})
        return {"topics": results, "source": "https://devforum.roblox.com/latest",
                "note": "Latest forum discussions; not all are official Roblox news. Check authors and announcement category."}

    def docs(self, query: str, limit=7) -> dict:
        query = _query(query)
        if type(limit) is not int or not 1 <= limit <= 12:
            raise ValueError("limit must be 1 to 12")
        tokens = re.findall(r"[a-z0-9]+", query.lower())
        ranks = []
        for title, slug, url, terms in _DOCUMENTS:
            haystack = (title + " " + slug.replace("/", " ") + " " + terms).lower()
            score = sum(2 if word in title.lower() else 1 for word in tokens if word in haystack)
            ranks.append((score, title, url))
        ranked = sorted(ranks, key=lambda x: (-x[0], x[1]))
        return {"query": query, "results": [{"title": title, "url": url, "match_score": score}
                for score, title, url in ranked if score > 0][:limit],
                "source": "Curated official Creator Hub and Luau source links",
                "note": "A curated link index, not full-text search or a claim the pages were downloaded."}

    def youtube_search(self, query: str, limit=6) -> dict:
        query = _query(query)
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("limit must be 1 to 10")
        key = os.environ.get("STAR_YOUTUBE_API_KEY", "").strip()
        search_url = "https://www.youtube.com/results?" + urlencode({"search_query": query})
        if not key:
            return {"configured": False, "search_url": search_url, "results": [],
                    "note": "Set STAR_YOUTUBE_API_KEY locally to enable actual YouTube Data API search; no results were fetched."}
        payload = self._get("youtube", "/youtube/v3/search", {
            "part": "snippet", "type": "video", "maxResults": limit,
            "q": query, "key": key,
        }, ttl=180)
        videos = []
        for item in payload.get("items", [])[:limit]:
            if not isinstance(item, dict):
                continue
            video_id = item.get("id", {}).get("videoId") if isinstance(item.get("id"), dict) else None
            if not isinstance(video_id, str) or not re.fullmatch(r"[\w-]{11}", video_id, re.ASCII):
                continue
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            thumb = snippet.get("thumbnails", {}).get("medium", {}) if isinstance(snippet.get("thumbnails"), dict) else {}
            videos.append({"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}",
                           "title": _short(snippet.get("title"), 200),
                           "description_excerpt": _short(snippet.get("description"), 380),
                           "channel": _short(snippet.get("channelTitle"), 120),
                           "published_at": _short(snippet.get("publishedAt"), 60),
                           "thumbnail_url": _safe_image(thumb.get("url")) if isinstance(thumb, dict) else None})
        return {"configured": True, "query": query, "results": videos, "search_url": search_url,
                "note": "Video titles/descriptions are metadata, not watched footage or verified gameplay."}

    def youtube_video(self, video_id: str) -> dict:
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError("Invalid YouTube video ID")
        url = f"https://www.youtube.com/watch?v={video_id}"
        key = os.environ.get("STAR_YOUTUBE_API_KEY", "").strip()
        if not key:
            payload = self._get("oembed", "/oembed", {"url": url, "format": "json"}, ttl=600)
            return {"url": url, "video_id": video_id, "title": _short(payload.get("title"), 180),
                    "channel": _short(payload.get("author_name"), 120),
                    "thumbnail_url": _safe_image(payload.get("thumbnail_url")),
                    "source": "YouTube public oEmbed", "video_watched": False,
                    "transcript_available": False,
                    "note": "Metadata preview only. Upload an authorized video file or supply permitted captions for actual content analysis."}
        payload = self._get("youtube", "/youtube/v3/videos", {
            "part": "snippet,statistics,contentDetails", "id": video_id, "key": key,
        }, ttl=180)
        item = next((x for x in payload.get("items", []) if isinstance(x, dict)
                     and x.get("id") == video_id), None)
        if item is None:
            raise ValueError("YouTube did not return a public video with that ID")
        snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
        stats = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
        details = item.get("contentDetails") if isinstance(item.get("contentDetails"), dict) else {}
        return {"video_id": video_id, "url": url, "title": _short(snippet.get("title"), 200),
                "channel": _short(snippet.get("channelTitle"), 100),
                "description_excerpt": _short(snippet.get("description"), 1600),
                "published_at": _short(snippet.get("publishedAt"), 50),
                "view_count": _safe_int(int(stats["viewCount"])) if str(stats.get("viewCount", "")).isdigit() else None,
                "like_count": _safe_int(int(stats["likeCount"])) if str(stats.get("likeCount", "")).isdigit() else None,
                "duration_iso8601": _short(details.get("duration"), 45),
                "captions_flag": details.get("caption") == "true",
                "video_watched": False, "transcript_available": False,
                "source": "YouTube Data API videos.list",
                "note": "Caption flag does not grant caption-download permission. No frames/audio/transcript were analyzed."}

    def open_cloud_universe(self, universe_id) -> dict:
        universe_id = _positive_id(universe_id)
        key = os.environ.get("STAR_ROBLOX_READ_API_KEY", "").strip()
        if not key:
            return {"configured": False, "universe_id": universe_id,
                    "note": "Configure a least-privilege Roblox Open Cloud universe:read key in the local process environment."}
        payload = self._get("apis", f"/cloud/v2/universes/{universe_id}",
                            api_key=key, ttl=180)
        return {"configured": True, "universe_id": universe_id,
                "source": f"https://apis.roblox.com/cloud/v2/universes/{universe_id}",
                "metadata": {k: payload.get(k) for k in ("name", "displayName", "description", "visibility", "createTime", "updateTime") if k in payload},
                "note": "Read-only owner-authorized metadata; never disclose the API key."}
