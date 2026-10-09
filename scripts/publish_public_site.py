"""Safely copy only selected public website files to STAR's distribution repo.

Runs *only* on a trusted GitHub Actions runner with a fine-grained token that
has Contents: write access to the dedicated public repository. It cannot read
other source files or send local transcripts, memory, keys, or model weights.
"""
from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import sys

import httpx

PUBLIC_REPO = 'oncoursemail/Star-Intelligence-Downloads'
PUBLIC_FILES = frozenset({
    'index.html', 'styles.css', 'site.js', 'star-icon.svg',
    'version.json', 'robots.txt', '.nojekyll',
})
MAX_SITE_FILE = 1_000_000


def collect_public_files(site: Path) -> dict[str, bytes]:
    if not site.is_dir() or site.is_symlink():
        raise ValueError('Expected a genuine site/ directory')
    files = {}
    for name in sorted(PUBLIC_FILES):
        path = site / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or symlinked website file: ' + name)
        if path.stat().st_size > MAX_SITE_FILE:
            raise ValueError('Website file exceeds publish limit: ' + name)
        files[name] = path.read_bytes()
    return files


def publish(repo: str, token: str, site: Path, *, dry_run: bool = False) -> list[str]:
    if repo != PUBLIC_REPO:
        raise PermissionError('Public upload destination is not the approved STAR releases repository')
    files = collect_public_files(site)
    if dry_run:
        return sorted(files)
    if not token:
        raise PermissionError('Set STAR_PUBLIC_RELEASE_TOKEN with Contents: write on public repository only')
    headers={'Authorization':f'Bearer {token}', 'Accept':'application/vnd.github+json',
             'X-GitHub-Api-Version':'2022-11-28'}
    # No credentials are ever printed, persisted, or embedded in the website.
    with httpx.Client(base_url='https://api.github.com',timeout=40.0,trust_env=False) as client:
        for filename,data in files.items():
            endpoint=f'/repos/{repo}/contents/{filename}'
            old=client.get(endpoint,headers=headers)
            if old.status_code == 404:
                sha=None
            else:
                old.raise_for_status()
                payload=old.json()
                sha=payload.get('sha')
                if payload.get('type')!='file' or not sha:
                    raise ValueError('Public path is not a normal file: '+filename)
                if payload.get('encoding')=='base64':
                    previous=base64.b64decode(payload.get('content',''))
                    if previous == data:
                        continue
            request={'message':f'website: update STAR {filename}',
                     'content':base64.b64encode(data).decode('ascii'), 'branch':'main'}
            if sha:
                request['sha']=sha
            response=client.put(endpoint,headers=headers,json=request)
            response.raise_for_status()
    return sorted(files)


def main():
    parser=argparse.ArgumentParser(description='Publish only STAR public website files')
    parser.add_argument('--repo',required=True)
    parser.add_argument('--site',default='site')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    files=publish(args.repo,os.environ.get('GH_TOKEN',''),Path(args.site),dry_run=args.dry_run)
    print('Public website files prepared:',', '.join(files))


if __name__=='__main__':
    main()
