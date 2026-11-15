"""Verified GitHub Releases updater for The Crow's Nest Studio.

Checks and downloads run as ordinary user. No installation happens without user action.
Uses GitHub's SHA-256 asset digest over HTTPS; never trusts an unsigned URL.
Preserves episodes, footage, narration, voices and exports. Reverts code on failed update.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
SETTINGS_DIR = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / 'TheCrowsNestStudio'
SETTINGS_FILE = SETTINGS_DIR / 'settings.json'
OWNER_REPO_RE = re.compile(r'^[A-Za-z0-9-]{1,39}/[A-Za-z0-9_.-]{1,100}$')
TAG_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
MAX_DOWNLOAD = 100 * 1024 * 1024
ALLOWED_CODE = {
    'VERSION', 'gui.py', 'studio.py', 'narration.py', 'desktop_launcher.py',
    'draft_with_ollama.py', 'production_engine.py', 'production_ui.py', 'voice_profiles.py', 'voice_studio_ui.py', 'qwen_voice.py', 'update_engine.py', 'diagnostics.py',
    'fact_checker.py', 'fact_checker_ui.py',
    'requirements.txt', 'README.md', 'README_DESKTOP.md', 'STUDIO_3_0_GUIDE.md', 'STUDIO_4_0_GUIDE.md',
    'Install_Desktop_App.ps1', 'Install_Desktop_App.bat', 'Connect_GitHub_Once.ps1', 'Connect_GitHub_Once.bat',
    'Launch_Studio_Windows.bat', 'Launch_Studio_Linux.sh',
}
REQUIRED_CODE = {'production_engine.py','production_ui.py','voice_profiles.py','voice_studio_ui.py','qwen_voice.py','VERSION','gui.py','studio.py','narration.py','update_engine.py','diagnostics.py','fact_checker.py','fact_checker_ui.py'}


@dataclass(frozen=True)
class Release:
    version: str
    asset_url: str
    digest: str
    size: int
    notes: str


def version_tuple(v: str) -> tuple[int, int, int]:
    match = TAG_RE.fullmatch(v.strip())
    if not match:
        raise ValueError(f'Unsupported version: {v!r}. Expected vX.Y.Z')
    return tuple(int(k) for k in match.groups())


def load_settings() -> dict:
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        return raw if isinstance(raw,dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(tmp, SETTINGS_FILE)


def validate_repo(repo: str) -> str:
    if not OWNER_REPO_RE.fullmatch(repo):
        raise ValueError('Enter your trusted release repository in owner/repository form.')
    return repo


def _load_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        'User-Agent': 'CrowsNestStudio-Updater/2',
        'Accept': 'application/vnd.github+json',
    })
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Update metadata is unexpectedly large.')
    return json.loads(raw.decode('utf-8'))


def get_release(repo: str, current_version: str = VERSION, *, fetch=_load_json) -> Release | None:
    repo = validate_repo(repo)
    api = f'https://api.github.com/repos/{repo}/releases/latest'
    payload = fetch(api)
    tag = payload.get('tag_name','')
    new = tag.lstrip('v')
    if version_tuple(new) <= version_tuple(current_version):
        return None
    name = f'Crows_Nest_Studio_Update_v{new}.zip'
    assets = [a for a in payload.get('assets',[]) if a.get('name')==name]
    if len(assets) != 1:
        raise ValueError(f'Release {tag} has no uniquely named {name} update archive.')
    asset = assets[0]
    digest = str(asset.get('digest','')).lower()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',digest):
        raise ValueError('Release is missing an authoritative GitHub SHA-256 digest; refusing update.')
    url = asset.get('browser_download_url','')
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='github.com':
        raise ValueError('Update must be downloaded from github.com over HTTPS.')
    expected_prefix = f'/{repo}/releases/download/'
    if not parsed.path.startswith(expected_prefix) or not parsed.path.endswith('/'+name):
        raise ValueError('Release download path does not match your trusted repository.')
    size = int(asset.get('size',0))
    if not 0<size<=MAX_DOWNLOAD:
        raise ValueError('Update is empty or too large for the verified updater.')
    return Release(new,url,digest.partition(':')[2],size,str(payload.get('body',''))[:1000])


def is_allowed(name: str) -> bool:
    if name in ALLOWED_CODE:
        return True
    if name.startswith('assets/branding/') and name.count('/')==2:
        return Path(name).suffix.lower() in {'.ico','.png','.jpg','.jpeg'}
    return False


def validate_archive(archive: Path, version: str) -> list[str]:
    names=[];uncompressed=0
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            name = member.filename
            if member.is_dir(): continue
            # Do not follow symlinks or accept absolute/traversal paths.
            if name.startswith('/') or '\\' in name or not is_allowed(name):
                raise ValueError(f'Unexpected update path: {name}')
            if member.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError(f'Symlink not allowed: {name}')
            if name in names:
                raise ValueError(f'Duplicate update file: {name}')
            uncompressed+=member.file_size
            if uncompressed>120_000_000:raise ValueError('Expanded update exceeds safe size limit.')
            if member.file_size > 35_000_000:
                raise ValueError(f'Oversized update file: {name}')
            names.append(name)
        if not REQUIRED_CODE.issubset(names):
            raise ValueError('Update is missing required program files.')
        if z.read('VERSION').decode('utf-8').strip()!=version:
            raise ValueError('Version inside ZIP does not match release tag.')
    return names


def stage_release(release: Release, *, install: Path = ROOT,
                  opener=urllib.request.urlopen) -> Path:
    cache = install/'.updates'
    cache.mkdir(parents=True, exist_ok=True)
    temp_file = cache/f'download-{uuid.uuid4().hex}.zip'
    digest=hashlib.sha256();written=0
    try:
        request = urllib.request.Request(release.asset_url, headers={'User-Agent':'CrowsNestStudio-Updater/2'})
        with opener(request,timeout=45) as response, temp_file.open('wb') as dest:
            # urllib automatically checks HTTPS certificates; reject unexpected final URL host.
            final = urllib.parse.urlparse(response.geturl())
            if final.scheme!='https' or final.hostname not in {
                'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}:
                raise ValueError('Unexpected download redirect host.')
            while True:
                block=response.read(1024*1024)
                if not block: break
                written += len(block)
                if written>MAX_DOWNLOAD: raise ValueError('Download exceeds size limit.')
                digest.update(block);dest.write(block)
        if written!=release.size or digest.hexdigest()!=release.digest:
            raise ValueError('Release archive failed SHA-256 or size verification.')
        names=validate_archive(temp_file,release.version)
        stage = cache/f'staged-v{release.version}'
        if stage.exists(): shutil.rmtree(stage)
        stage.mkdir()
        with zipfile.ZipFile(temp_file) as z:
            for name in names:
                dest=stage/name
                dest.parent.mkdir(parents=True,exist_ok=True)
                with z.open(name) as src, dest.open('wb') as out:
                    shutil.copyfileobj(src,out)
        return stage
    finally:
        temp_file.unlink(missing_ok=True)


def apply_stage(stage: Path, *, install: Path=ROOT, restart: bool=False) -> None:
    """Apply only validated staged code, roll back changed files if any check fails."""
    stage=stage.resolve();install=install.resolve()
    if stage.parent!=install/'.updates' or not stage.name.startswith('staged-v'):
        raise ValueError('Stage must be inside the installation update cache.')
    version=(stage/'VERSION').read_text(encoding='utf-8').strip()
    version_tuple(version)
    if version_tuple(version)<=version_tuple((install/'VERSION').read_text().strip()):
        raise ValueError('Refusing downgrade or duplicate update.')
    files=[p for p in stage.rglob('*') if p.is_file()]
    paths=[p.relative_to(stage).as_posix() for p in files]
    if not REQUIRED_CODE.issubset(paths) or any(not is_allowed(name) for name in paths):
        raise ValueError('Staged package failed file allowlist.')
    backup=install/'.updates'/f'backup-{int(time.time())}'
    backup.mkdir(parents=True,exist_ok=False)
    changed=[]
    try:
        for source,rel in zip(files,paths):
            target=install/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            existed=target.exists()
            if existed:
                old=backup/rel
                old.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,old)
            next_file=target.with_name(target.name+'.update-new')
            shutil.copy2(source,next_file)
            os.replace(next_file,target)
            changed.append((rel,existed))
        for name in ('gui.py','studio.py','production_engine.py','production_ui.py','narration.py','update_engine.py','diagnostics.py','fact_checker.py','fact_checker_ui.py'):
            source=(install/name).read_text(encoding='utf-8')
            compile(source,name,'exec')
        if not (install/'assets'/'branding'/'The_Crows_Nest_Watermark_512.png').exists():
            raise ValueError('Updated app is missing its watermark.')
        (backup/'UPDATE_SUCCEEDED.txt').write_text(f'Applied {version}',encoding='utf-8')
    except Exception:
        for rel,existed in reversed(changed):
            target=install/rel
            if existed: shutil.copy2(backup/rel,target)
            else: target.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(stage,ignore_errors=True)
    if restart and sys.platform=='win32':
        pythonw=install/'.venv'/'Scripts'/'pythonw.exe'
        if pythonw.exists():
            subprocess.Popen([str(pythonw),str(install/'gui.py')],cwd=install,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def wait_for_pid(pid: int, max_wait: int=50) -> None:
    if sys.platform!='win32' or pid<=0:return
    import ctypes
    SYNCHRONIZE=0x00100000
    WAIT_OBJECT_0=0x0
    handle=ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE,False,pid)
    if handle:
        try:
            ret=ctypes.windll.kernel32.WaitForSingleObject(handle,max_wait*1000)
            if ret!=WAIT_OBJECT_0:raise TimeoutError('Editor has not closed. Update postponed.')
        finally:ctypes.windll.kernel32.CloseHandle(handle)


def log_applier_error(install: Path, message: str) -> None:
    try:
        p=install/'.updates'/'last-update-error.txt'
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(message,encoding='utf-8')
    except OSError:pass


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('apply');a.add_argument('--stage',type=Path,required=True)
    a.add_argument('--install',type=Path,required=True);a.add_argument('--wait-pid',type=int,default=0)
    opts=ap.parse_args()
    if opts.cmd=='apply':
        try:
            wait_for_pid(opts.wait_pid)
            apply_stage(opts.stage,install=opts.install,restart=True)
        except Exception as e:
            log_applier_error(opts.install,repr(e));raise

if __name__=='__main__':main()
