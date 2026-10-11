"""Real runs of image understanding, video understanding and "compare with reference" against a
STAR Server, through the same code the chat uses.

    python scripts/media/measure_vision.py image   --file shot.png --question "What is on this screen?"
    python scripts/media/measure_vision.py video   --file clip.mp4 --question "What happens in this video?"
    python scripts/media/measure_vision.py compare --reference a.png --candidate b.png

Common options: --endpoint http://<server>:8080/v1 (or STAR_SERVER_URL), --key-file <file> (or
STAR_SERVER_API_KEY), --ffmpeg-dir <folder>, --out result.json. Run with APPDATA pointing at an
empty folder. The key is read into this process only and is never printed or written.

`image` and `video` go through `star.chat_media.prepare_turn` and `star.desktop_core.run_task`,
exactly as the desktop sends an attachment; the model client is wrapped only to read the timing
block llama.cpp returns (tokens read and written). On a shared server, hold its measuring lock.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class Watch:
    def __init__(self, client, log: list):
        self._client, self._log = client, log
        self.chat = self.completions = self

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *error):
        return await self._client.__aexit__(*error)

    async def create(self, **kwargs):
        row = {'model': kwargs.get('model'), 'sent_at': time.perf_counter(),
               'images': sum(1 for message in kwargs.get('messages') or [] if isinstance(message.get('content'), list)
                             for part in message['content'] if part.get('type') == 'image_url')}
        self._log.append(row)
        result = await self._client.chat.completions.create(**kwargs)
        if not kwargs.get('stream') or not hasattr(result, '__aiter__'):
            row['answered_model'] = getattr(result, 'model', None)
            _timings(row, getattr(result, 'timings', None))
            return result

        async def chunks():
            async for chunk in result:
                row.setdefault('first_chunk_s', round(time.perf_counter() - row['sent_at'], 2))
                if getattr(chunk, 'model', None):
                    row['answered_model'] = chunk.model
                _timings(row, getattr(chunk, 'timings', None))
                yield chunk
        return chunks()


def _timings(row: dict, timings) -> None:
    if isinstance(timings, dict):
        for key, name in (('prompt_n', 'read'), ('cache_n', 'cached'), ('predicted_n', 'written'),
                          ('prompt_ms', 'read_ms'), ('prompt_per_second', 'read_tok_s'),
                          ('predicted_per_second', 'write_tok_s')):
            if isinstance(timings.get(key), (int, float)):
                row[name] = round(timings[key], 2) if isinstance(timings[key], float) else timings[key]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('what', choices=('image', 'video', 'compare'))
    parser.add_argument('--endpoint', default=os.environ.get('STAR_SERVER_URL', ''))
    parser.add_argument('--key-file', default='')
    parser.add_argument('--file')
    parser.add_argument('--question', default='Describe what you see in two sentences.')
    parser.add_argument('--reference')
    parser.add_argument('--candidate')
    parser.add_argument('--ffmpeg-dir', default='')
    parser.add_argument('--mode', default='fast')
    parser.add_argument('--out', default='')
    args = parser.parse_args()
    key = os.environ.get('STAR_SERVER_API_KEY', '').strip()
    if not key and args.key_file:
        key = Path(args.key_file).expanduser().read_text(encoding='utf-8').strip()
    if not key or not args.endpoint:
        print('Set --endpoint and STAR_SERVER_API_KEY or --key-file', file=sys.stderr)
        return 2
    os.environ['STAR_SERVER_API_KEY'] = key

    import star.desktop_core as core
    import star.vision as vision_module
    from star import chat_media, providers, references
    from star.model_health import probe_server

    log: list[dict] = []
    real_open = providers.open_client
    watched = lambda settings, **kw: Watch(real_open(settings, **kw), log)      # noqa: E731
    core.open_client = watched
    providers.open_client = watched
    home = core.app_data()
    home.mkdir(parents=True, exist_ok=True)
    settings = core.Settings(provider='star_server', server_endpoint=args.endpoint.rstrip('/'), model='star-fast',
                             project='media-test', knowledge_endpoint='off', ffmpeg_dir=args.ffmpeg_dir)
    check = probe_server(settings, chat=False)       # what the app does at start: reads the model list
    report: dict = {'what': args.what, 'date': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'server_ok': check.get('ok'),
                    'roles': {entry['role']: entry['model'] for entry in check.get('roles') or []},
                    'vision_model': vision_module.vision_model(settings)}
    began = time.perf_counter()
    if args.what == 'compare':
        project = settings.project
        entry = references.pin(home, project, Path(args.reference), label='reference')
        result = references.compare(settings, home, project, entry['id'], Path(args.candidate))
        report.update(differences=result['differences'], measured=result['measured']['lines'],
                      model=result['model'], model_seconds=result['seconds'], model_error=result['model_error'],
                      side_by_side=str(result['side_by_side']))
    else:
        chats = core.Conversations(home / 'conversations.sqlite3')
        chat = chats.new_chat(settings.project)
        chats.add(settings.project, 'user', args.question, chat_id=chat)
        seen: dict = {}

        def on_event(event: dict) -> None:
            kind, now = event.get('event'), round(time.perf_counter() - began, 2)
            if kind == 'assistant_delta' and str(event.get('text', '')).strip():
                seen.setdefault('first_token_s', now)
            elif kind == 'route_selected':
                seen['profile'], seen['route_model'] = event.get('profile'), event.get('model')
            elif kind == 'model_answered':
                seen['answered_model'] = event.get('model')

        with tempfile.TemporaryDirectory(prefix='star-media-') as directory:
            prepared = time.perf_counter()
            media = chat_media.prepare_turn(settings, home, args.question, [Path(args.file).resolve()],
                                            Path(directory) / 'm')
            report['prepare_s'] = round(time.perf_counter() - prepared, 2)
            if media.video is not None:
                video = media.video
                report['video'] = {'duration_s': round(video.duration, 1), 'frames': len(video.frames),
                                   'frame_times': video.times, 'has_audio': video.has_audio, 'asr': video.asr,
                                   'transcript_chars': len(video.transcript_text()), 'audio_note': video.audio_note,
                                   'timings': video.timings, 'transcript_start': video.transcript_text()[:300]}
            answer = core.run_task(settings, media.prompt(args.question), media.pictures, on_event=on_event,
                                   stream_tokens=True, mode=args.mode, chat_id=chat, owner_text=args.question)
            answer += media.footer
        chats.add(settings.project, 'assistant', answer, chat_id=chat)
        chats.close()
        report.update(seen, pictures_sent=len(media.pictures), answer=answer)
    report['total_s'] = round(time.perf_counter() - began, 2)
    report['requests'] = [{k: v for k, v in row.items() if k != 'sent_at'} for row in log]
    text = json.dumps(report, indent=1, ensure_ascii=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
