"""Minimal local ComfyUI workflow runner. No hosted image API is required.

ComfyUI workflows can contain third-party nodes. STAR only runs a conservative
set of known local core nodes by default. Operators can extend this list in a
reviewed code change rather than asking an LLM to silently execute unknown nodes.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
import httpx

LOCAL_CLASSES = frozenset({
    'CheckpointLoaderSimple', 'CLIPTextEncode', 'EmptyLatentImage', 'KSampler',
    'KSamplerAdvanced', 'VAEDecode', 'VAEEncode', 'SaveImage', 'LoadImage',
    'LoraLoader', 'LoraLoaderModelOnly', 'CLIPSetLastLayer', 'LatentUpscale',
    'ImageScale', 'ImageScaleBy', 'VAELoader', 'CLIPLoader', 'UNETLoader',
    'ConditioningCombine', 'ConditioningSetArea', 'ConditioningAverage',
})


def load_workflow(path: Path, *, prompt_text: str, prompt_node: str):
    path=path.expanduser().resolve(strict=True)
    if path.suffix.lower() != '.json' or path.stat().st_size > 2_000_000:
        raise ValueError('Use a small ComfyUI API-format JSON workflow')
    raw=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw,dict) or not raw:
        raise ValueError('Invalid API workflow. Export using ComfyUI Save (API format).')
    for node_id,node in raw.items():
        if not isinstance(node,dict) or node.get('class_type') not in LOCAL_CLASSES:
            raise PermissionError(f'Unreviewed or external workflow node {node_id}: {node.get("class_type") if isinstance(node,dict) else "invalid"}')
    if prompt_node not in raw or raw[prompt_node].get('class_type')!='CLIPTextEncode':
        raise ValueError('Prompt node must be the ID of a CLIPTextEncode node')
    if not 1 <= len(prompt_text) <= 1500:
        raise ValueError('Prompt must be 1-1500 characters')
    result=copy.deepcopy(raw)
    result[prompt_node]['inputs']['text']=prompt_text
    return result


def generate(workflow_file: Path, *, prompt: str, node_id: str, output: Path, port: int = 8188,
             timeout_seconds: int = 360):
    if not 1<=port<=65535:
        raise ValueError('Invalid local ComfyUI port')
    flow=load_workflow(workflow_file, prompt_text=prompt, prompt_node=node_id)
    url=f'http://127.0.0.1:{port}'
    output.mkdir(parents=True,exist_ok=True)
    with httpx.Client(timeout=30, trust_env=False) as client:
        reply=client.post(url+'/prompt',json={'prompt':flow,'client_id':'star-local-desktop'})
        reply.raise_for_status()
        payload=reply.json()
        job=payload.get('prompt_id')
        if not isinstance(job,str) or not re.fullmatch(r'[A-Za-z0-9-]{8,80}',job):
            raise RuntimeError('ComfyUI did not return a valid prompt ID: '+str(payload)[:400])
        finish=time.monotonic()+timeout_seconds
        images=[]
        while time.monotonic()<finish:
            history=client.get(url+'/history/'+job)
            history.raise_for_status()
            detail=history.json().get(job)
            if detail:
                status=detail.get('status',{})
                if status.get('status_str')=='error':
                    raise RuntimeError('ComfyUI generation failed: '+str(status)[:500])
                for node in detail.get('outputs',{}).values():
                    for result in node.get('images',[]):
                        name=result.get('filename','')
                        if not name or '/' in name or '\\' in name or name in ('.','..'):
                            continue
                        params={'filename':name,'type':result.get('type','output'),'subfolder':result.get('subfolder','')}
                        if params['type'] not in {'output','temp'}:
                            continue
                        if params['subfolder'] and ('..' in params['subfolder'] or params['subfolder'].startswith(('/','\\'))):
                            continue
                        img=client.get(url+'/view',params=params)
                        img.raise_for_status()
                        if len(img.content)>25_000_000:
                            raise ValueError('Generated image exceeds 25 MB limit')
                        new_path=output/(f'{job[:8]}_{len(images)}_'+name)
                        new_path.write_bytes(img.content)
                        images.append(new_path)
                if images:
                    return images
                if status.get('completed'):
                    raise RuntimeError('ComfyUI finished but no SaveImage output was found')
            time.sleep(2)
        raise TimeoutError('ComfyUI job did not finish within allotted time')
