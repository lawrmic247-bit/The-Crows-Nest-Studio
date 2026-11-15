"""Non-destructive recordings and consent-bound voice profiles for The Crow's Nest.

No speech is transmitted to a remote service by this module. The originals and
profiles persist independently of the replaceable Windows program directory.
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, uuid, wave
from datetime import datetime, timezone
from pathlib import Path

APPDATA = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share') / 'TheCrowsNestStudioData'
PROFILE_DIR = APPDATA / 'voice_profiles'
SUPPORTED = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac', '.wma', '.mp4'}
DEFAULT_ACTING = ('Natural American narrator. Keep my original pitch, accent, cadence, '\
                  'and vocal texture. Clear enunciation, understated authority, '\
                  'warm and slightly weathered; never exaggerated trailer delivery.')


def slugify(name: str) -> str:
    label = re.sub(r'[^a-z0-9]+', '-', name.strip().lower()).strip('-')[:36]
    if not label: raise ValueError('Enter a profile name.')
    return label


def _profile_path(profile_id: str) -> Path:
    if not re.fullmatch(r'[a-z0-9-]{1,75}', profile_id):
        raise ValueError('Invalid profile identifier')
    return PROFILE_DIR / profile_id


def _read_profile(directory: Path) -> dict:
    p = directory / 'profile.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    data['profile_id'] = directory.name
    return data


def list_profiles() -> list[dict]:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    profiles=[]
    for folder in PROFILE_DIR.iterdir():
        if folder.is_dir() and (folder/'profile.json').is_file():
            try: profiles.append(_read_profile(folder))
            except (ValueError, OSError): pass
    return sorted(profiles,key=lambda p:p.get('name','').lower())


def get_profile(profile_id: str) -> dict:
    return _read_profile(_profile_path(profile_id))


def write_profile(data: dict) -> dict:
    directory=_profile_path(data['profile_id'])
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/'profile.json'
    tmp=directory/'profile.json.tmp'
    tmp.write_text(json.dumps({k:v for k,v in data.items() if k!='profile_id'},indent=2,ensure_ascii=False),encoding='utf-8')
    tmp.replace(path)
    return get_profile(data['profile_id'])


def create_profile(name: str, source_path: Path, *, transcript: str,
                   direction: str=DEFAULT_ACTING, consent: bool=False,
                   own_voice: bool=True) -> dict:
    if not consent:
        raise PermissionError('You must confirm that you own this voice or have the speaker’s express permission to clone it.')
    source_path=Path(source_path).expanduser().resolve()
    if not source_path.is_file(): raise FileNotFoundError(source_path)
    if source_path.suffix.lower() not in SUPPORTED: raise ValueError('Unsupported audio format.')
    if source_path.stat().st_size > 250_000_000: raise ValueError('Import a recording smaller than 250 MB.')
    name = name.strip()[:90]
    if not name: raise ValueError('Enter a profile name.')
    profile_id=f'{slugify(name)}-{uuid.uuid4().hex[:8]}'
    directory=_profile_path(profile_id)
    directory.mkdir(parents=True,exist_ok=False)
    original=directory/('original'+source_path.suffix.lower())
    try:
        shutil.copy2(source_path,original)
        # Use a stable WAV reference for Qwen's speech feature extractor. Never
        # treat the cleaned file as a replacement for the voice identity reference.
        wav=directory/'reference.wav'
        _run_ffmpeg(['-i',str(original),'-vn','-ac','1','-ar','24000','-c:a','pcm_s16le',str(wav)])
        with wave.open(str(wav),'rb') as w:
            duration=w.getnframes()/w.getframerate()
        if not 2 <= duration <= 3600:
            raise ValueError('Reference audio must be at least 2 seconds long.')
        data={'profile_id':profile_id,'name':name,'transcript':transcript.strip(),
              'direction':direction.strip() or DEFAULT_ACTING,
              'speaker_is_owner':bool(own_voice),'consent_confirmed':True,
              'created_at':datetime.now(timezone.utc).isoformat(),
              'original_file':original.name,'reference_file':'reference.wav',
              'cleaned_file':None,'cleanup_strength':'none',
              'voice_model':'Qwen3-TTS-12Hz-0.6B-Base'}
        write_profile(data)
        return get_profile(profile_id)
    except Exception:
        shutil.rmtree(directory,ignore_errors=True)
        raise


def _run_ffmpeg(args: list[str]):
    p=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y']+args,
                     capture_output=True,text=True,timeout=600)
    if p.returncode:
        raise RuntimeError('FFmpeg failed: '+p.stderr[-1000:])


def clean_recording(profile_id: str, strength: str='light') -> Path:
    """Non-destructive EQ-free cleanup: pitch and voice timbre preserved.

    The output is an alternate media file; original and reference remain intact.
    No equalization, pitch shifting, formant changes, or time-stretching.
    """
    settings={
      'off':'anull',
      'light':'highpass=f=65,afftdn=nr=5,acompressor=threshold=-22dB:ratio=1.45:attack=20:release=260,loudnorm=I=-18:TP=-2:LRA=11',
      'balanced':'highpass=f=70,afftdn=nr=9,acompressor=threshold=-24dB:ratio=1.7:attack=20:release=220,loudnorm=I=-18:TP=-2:LRA=10',
      'strong':'highpass=f=75,afftdn=nr=13,acompressor=threshold=-26dB:ratio=2:attack=15:release=220,loudnorm=I=-18:TP=-2:LRA=9',
    }
    if strength not in settings: raise ValueError('Unknown cleanup strength')
    data=get_profile(profile_id)
    directory=_profile_path(profile_id)
    dest=directory/f'cleaned_{strength}.wav'
    original=directory/data['original_file']
    _run_ffmpeg(['-i',str(original),'-vn','-af',settings[strength],'-ac','1','-ar','48000','-c:a','pcm_s16le',str(dest)])
    data['cleaned_file']=dest.name;data['cleanup_strength']=strength
    write_profile(data)
    return dest


def get_audio(profile_id: str, kind: str='reference') -> Path:
    p=get_profile(profile_id)
    if kind=='original': filename=p['original_file']
    elif kind=='cleaned': filename=p.get('cleaned_file') or p['original_file']
    elif kind=='reference': filename=p['reference_file']
    else: raise ValueError('Unknown audio selection')
    result=_profile_path(profile_id)/filename
    if not result.is_file(): raise FileNotFoundError(result)
    return result


def update_profile(profile_id: str, *, name: str, transcript: str, direction: str) -> dict:
    profile=get_profile(profile_id)
    profile['name']=name.strip()[:90]
    profile['transcript']=transcript.strip()[:4000]
    profile['direction']=direction.strip()[:4000] or DEFAULT_ACTING
    if not profile['name']: raise ValueError('Profile name is required.')
    return write_profile(profile)
