"""Where each media capability runs: the STAR Brains (servers) or this PC (its graphics card).

One setting per capability (`media_images`, `media_voice`, `media_video`), one function every code
path asks (`require`), and one description the Settings page shows (`describe`). An option that
does not exist is listed as unavailable with the reason; choosing it never falls back silently
to the other place. `fixable` tells the page whether a setting could make an option available
(connect STAR Server, install the on-device brain) or whether this install can never offer it
(no image or voice model on servers without a graphics card); the page explains the second kind
instead of drawing it as a choice.

The speed notes come from `media_measurements.py`: numbers measured on the owner's hardware,
each with its date. Where a number is an estimate from published measurements it says so.
"""
from __future__ import annotations

from pathlib import Path

CAPABILITIES = ('images', 'voice', 'video')
PLACES = ('servers', 'pc')
LABELS = {'servers': 'STAR Brains (servers)', 'pc': 'This PC (your GPU)'}
TITLES = {'images': 'Images', 'voice': 'Voice', 'video': 'Video understanding'}
FIELDS = {'images': 'media_images', 'voice': 'media_voice', 'video': 'media_video'}
DEFAULTS = {'images': 'pc', 'voice': 'pc', 'video': 'servers'}


class PlaceUnavailable(RuntimeError):
    """The place chosen in Settings cannot do this. The message says why and what to change."""


def measurements() -> dict:
    from .media_measurements import MEASUREMENTS
    return MEASUREMENTS


def chosen(settings, capability: str) -> str:
    if capability not in CAPABILITIES:
        raise ValueError('Unknown media capability')
    value = getattr(settings, FIELDS[capability], DEFAULTS[capability])
    return value if value in PLACES else DEFAULTS[capability]


def _seconds(value) -> str:
    return f'{value:.0f}' if isinstance(value, (int, float)) and value >= 10 else f'{value:.1f}'


def _images(settings, home: Path | None) -> dict:
    data = measurements().get('images', {})
    pc, servers = data.get('pc', {}), data.get('servers', {})
    sizes = pc.get('seconds_per_image', {})
    if sizes:
        timing = ', '.join(f'{size} in {_seconds(seconds)} s' for size, seconds in sizes.items())
        note = (f"Measured on this PC ({pc.get('gpu', 'graphics card')}, {pc.get('date', '')}): {timing}. "
                f"Starting ComfyUI takes about {_seconds(pc.get('start_seconds', 0))} s and the first image after "
                f"that took {_seconds(pc.get('first_image_seconds', 0))} s. "
                f"Changing an attached picture takes about {_seconds(pc.get('edit_seconds_1024', 0))} s. "
                f"The card's memory peaked at {pc.get('vram_peak_mb', 0)} MB of {pc.get('vram_total_mb', 0)} MB "
                f"(the desktop itself was using {pc.get('vram_idle_mb', 0)} MB); a voice call needs about "
                "1 GB of the same card, and the two were not measured together.")
    else:
        note = 'Not measured on this PC yet.'
    low, high = (servers.get('estimate_seconds_1024') or [0, 0])[:2]
    reason = ('Not available: no image model is installed on the servers, and they have no graphics card. '
              + (f'On their processors one 1024 image with this model is estimated at {low // 60} to '
                 f'{high // 60} minutes ({low} to {high} s), an estimate from published processor '
                 'measurements, not measured on the servers. ' if high else '')
              + (f"This PC makes the same image in about {_seconds(sizes.get('1024x1024'))} s."
                 if sizes.get('1024x1024') else ''))
    return {'pc': {'available': True, 'note': note, 'reason': '', 'fixable': True},
            'servers': {'available': False, 'note': '', 'reason': reason.strip(), 'fixable': False}}


def _voice(settings, home: Path | None) -> dict:
    data = measurements().get('voice', {})
    pc = data.get('pc', {})
    note = ('Speech recognition and Star\'s voice run on this PC. '
            + (f"Measured ({pc.get('date', '')}): recognising a sentence {pc['asr_gpu_seconds']} s and speaking "
               f"one {pc['tts_gpu_seconds']} s on the graphics card; {pc['asr_cpu_seconds']} s and "
               f"{pc['tts_cpu_seconds']} s on this PC's processor alone. " if pc else '')
            + 'The words of the reply are still written by the STAR Brain.')
    reason = ('Not available: no speech recogniser or voice is installed on the servers; today they only write '
              'the reply text. They have no graphics card, so speech there would run on processors. '
              + (f"Measured on this PC's processor as a guide, that is {pc['asr_cpu_seconds']} s to recognise and "
                 f"{pc['tts_cpu_seconds']} s to speak each sentence (against {pc['asr_gpu_seconds']} s and "
                 f"{pc['tts_gpu_seconds']} s on the graphics card), plus sending the audio over the network. "
                 'Not measured on the servers.' if pc else ''))
    return {'pc': {'available': True, 'note': note, 'reason': '', 'fixable': True},
            'servers': {'available': False, 'note': '', 'reason': reason.strip(), 'fixable': False}}


def _video(settings, home: Path | None) -> dict:
    from .providers import STAR_SERVER, get_api_key
    data = measurements().get('video', {})
    servers, pc = data.get('servers', {}), data.get('pc', {})
    server_set = bool(str(getattr(settings, 'server_endpoint', '') or '').strip()) and bool(get_api_key(STAR_SERVER))
    if servers:
        note = (f"Frames and transcript are prepared on this PC, then read by the server's vision model. "
                f"Measured ({servers.get('date', '')}): a {servers.get('clip_seconds', 0)} s clip, "
                f"{servers.get('frames', 0)} frames plus its transcript, answered in "
                f"{_seconds(servers.get('answer_seconds', 0))} s "
                f"(preparing frames and transcript {_seconds(servers.get('prepare_seconds', 0))} s). "
                'The servers have no graphics card, so each frame costs seconds to read.')
    else:
        note = 'Frames and transcript are prepared on this PC, then read by the server\'s vision model. Not measured yet.'
    brain = bool(home and (Path(home) / 'brain.json').is_file())
    pc_note = ('The on-device brain on your graphics card reads the frames; nothing leaves this PC. '
               + (pc.get('note') or 'Not measured yet on this PC.'))
    return {'servers': {'available': server_set, 'note': note, 'fixable': True,
                        'reason': '' if server_set else
                        'Not available: no STAR Server is connected. Add its address and key in Settings → STAR Server.'},
            'pc': {'available': brain, 'note': pc_note, 'fixable': True,
                   'reason': '' if brain else
                   'Not available: the on-device brain is not installed (Settings → On-device brain). '
                   'It shares the graphics card with image generation.'}}


_RULES = {'images': _images, 'voice': _voice, 'video': _video}


def describe(settings, home: Path | None = None) -> list[dict]:
    """Everything the Settings page shows: per capability, the choice and both options."""
    shown = []
    for capability in CAPABILITIES:
        facts = _RULES[capability](settings, home)
        shown.append({'id': capability, 'title': TITLES[capability], 'field': FIELDS[capability],
                      'chosen': chosen(settings, capability),
                      'options': [{'id': place, 'label': LABELS[place], **facts[place]} for place in PLACES]})
    return shown


def require(settings, capability: str, home: Path | None = None) -> str:
    """The chosen place, or PlaceUnavailable with the reason. Never the other place instead."""
    place = chosen(settings, capability)
    option = _RULES[capability](settings, home)[place]
    if not option['available']:
        raise PlaceUnavailable(f"{TITLES[capability]} is set to {LABELS[place]} in Settings → Where STAR generates. "
                               + option['reason'])
    return place


def require_video_provider(settings, home: Path | None = None) -> str:
    """A video's frames go only to the place chosen for video understanding.

    The chat sends pictures to whichever provider is selected, so the selected provider has to
    be the chosen place: the STAR Server for 'servers', the on-device brain for 'pc'. A hosted
    provider never receives frames of the owner's local video through this path.
    """
    from .providers import provider_kind
    place = require(settings, 'video', home)
    kind = provider_kind(settings)
    wanted = 'lan' if place == 'servers' else 'local'
    if kind != wanted:
        using = {'lan': 'STAR Server', 'local': 'On-device', 'cloud': 'a hosted provider'}.get(kind, kind)
        raise PlaceUnavailable(
            f'Video understanding is set to {LABELS[place]}, but the chat is using {using}. '
            f"Select {'STAR Server' if wanted == 'lan' else 'On-device'} as the provider, or change the choice in "
            'Settings → Where STAR generates. STAR does not send frames of your video anywhere else.')
    return place
