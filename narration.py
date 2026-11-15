#!/usr/bin/env python3
"""Local narrator for The Crow's Nest Studio.

Preferred voice: Kokoro ONNX; Piper retained for legacy projects.
The optional speech model is downloaded only after explicit user action.
"""
from __future__ import annotations

import argparse
import os
import time
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VOICE_DIR = ROOT / 'voices'
AUDIO_DIR = ROOT / 'assets' / 'narration'
KOKORO_DIR = VOICE_DIR / 'kokoro'
KOKORO_MODEL = KOKORO_DIR / 'kokoro-v1.0.onnx'
KOKORO_VOICES = KOKORO_DIR / 'voices-v1.0.bin'
MODEL_URL = ('https://github.com/thewh1teagle/kokoro-onnx/releases/'
             'download/model-files-v1.1/kokoro-v1.0.onnx')
VOICES_URL = ('https://github.com/thewh1teagle/kokoro-onnx/releases/'
              'download/model-files-v1.1/voices-v1.0.bin')
SAMPLE_TEXT = ("In 1967, a Navy corpsman served with the Marine Corps in Vietnam. "
               "On May 16, 1968, Donald Ballard treated wounded Marines in Quảng Trị. "
               "This is The Crow's Nest.")


# Only TTS input is normalized; scripts and subtitles keep the original text.
PRONUNCIATION_FILE = (Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local'/'share')
                      / 'TheCrowsNestStudioData' / 'pronunciations.json')
DEFAULT_PRONUNCIATIONS = {
    'corpsman': 'core-man',
    'corpsmen': 'core-men',
    'Marine Corps': 'Marine Core',
    'Quảng Trị': 'Kwang Tree',
    'Đà Nẵng': 'Dah Nang',
}
_ONES = ('zero','one','two','three','four','five','six','seven','eight','nine',
         'ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen',
         'seventeen','eighteen','nineteen')
_TENS = ('','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety')
_DECADES = {20:'twenties',30:'thirties',40:'forties',50:'fifties',
            60:'sixties',70:'seventies',80:'eighties',90:'nineties'}
_YEAR_PATTERN = re.compile(r'(?<![\w/])((?:1[0-9]{3}|20[0-9]{2}))(s?)(?![\w/])')

_MONTHS = ('January','February','March','April','May','June','July','August',
           'September','October','November','December')
_MONTH_EXPR = '|'.join(_MONTHS)
_DATE_PATTERN = re.compile(
    r'\b('+_MONTH_EXPR+r')\s+([1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?'
    r',?\s+((?:1[0-9]{3}|20[0-9]{2}))\b', re.IGNORECASE)
_DMY_PATTERN = re.compile(
    r'\b([1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?\s+'
    r'('+_MONTH_EXPR+r')\s+((?:1[0-9]{3}|20[0-9]{2}))\b', re.IGNORECASE)
_ORDINALS = {
    1:'first',2:'second',3:'third',4:'fourth',5:'fifth',6:'sixth',7:'seventh',
    8:'eighth',9:'ninth',10:'tenth',11:'eleventh',12:'twelfth',13:'thirteenth',
    14:'fourteenth',15:'fifteenth',16:'sixteenth',17:'seventeenth',18:'eighteenth',
    19:'nineteenth',20:'twentieth',30:'thirtieth'
}


def spoken_day(day:int)->str:
    if not 1<=day<=31:
        raise ValueError('Day must be 1–31.')
    if day in _ORDINALS:
        return _ORDINALS[day]
    return _TENS[day//10] + '-' + _ORDINALS[day%10]




def _spoken_number(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n >= 100:
        raise ValueError('Expected a number under 100.')
    return _TENS[n//10] + (('-' + _ONES[n%10]) if n%10 else '')


def spoken_year(year: int, decade: bool=False) -> str:
    """Expand calendar years: 1967 => nineteen sixty-seven; 1960s => nineteen sixties."""
    if not 1000 <= year <= 2099:
        raise ValueError('Year outside supported narration range.')
    if year < 2000:
        century = _spoken_number(year//100)
        suffix = year % 100
        if decade and suffix in _DECADES:
            return century + ' ' + _DECADES[suffix]
        if suffix == 0:
            return century + ' hundreds' if decade else century + ' hundred'
        if suffix < 10:
            return century + ' oh ' + _spoken_number(suffix)
        return century + ' ' + _spoken_number(suffix)
    suffix = year % 100
    if decade and suffix == 0:
        return 'two thousands'
    if decade and suffix in _DECADES:
        return 'twenty ' + _DECADES[suffix]
    if year < 2010:
        return 'two thousand' + (' ' + _spoken_number(suffix) if suffix else '')
    if suffix == 0:
        return 'twenty-one hundred'
    return 'twenty ' + _spoken_number(suffix)


def load_pronunciations() -> dict[str,str]:
    result = dict(DEFAULT_PRONUNCIATIONS)
    if PRONUNCIATION_FILE.is_file():
        try:
            data=json.loads(PRONUNCIATION_FILE.read_text(encoding='utf-8'))
            if not isinstance(data,dict):
                raise ValueError('Pronunciation guide must contain a JSON object.')
            if len(data)>120:
                raise ValueError('Pronunciation guide exceeds 120 entries.')
            for key,value in data.items():
                if not isinstance(key,str) or not isinstance(value,str):
                    raise ValueError('Pronunciation entries must have text keys and values.')
                if not 1 <= len(key.strip()) <= 100 or not 1 <= len(value.strip()) <= 150:
                    raise ValueError('Pronunciation entries cannot be blank or excessively long.')
                result[key.strip()]=value.strip()
        except (OSError,ValueError) as exc:
            raise ValueError('Invalid pronunciation guide. Open Narrate > Pronunciation guide: '+str(exc)) from exc
    return result


def normalize_for_speech(text: str) -> str:
    """Speech-only year and pronunciation adjustments without touching on-screen captions."""
    if not isinstance(text,str):
        raise TypeError('Narration must be text.')
    # Month-name dates are unambiguous; leave numeric 05/06/1968 untouched.
    text=_DATE_PATTERN.sub(
        lambda m: f'{m.group(1)} {spoken_day(int(m.group(2)))}, {spoken_year(int(m.group(3)))}',
        text)
    text=_DMY_PATTERN.sub(
        lambda m: f'the {spoken_day(int(m.group(1)))} of {m.group(2)}, {spoken_year(int(m.group(3)))}',
        text)
    text=_YEAR_PATTERN.sub(lambda m: spoken_year(int(m.group(1)),bool(m.group(2))),text)
    pronunciations=load_pronunciations()
    for spelling,spoken in sorted(pronunciations.items(),key=lambda kv:-len(kv[0])):
        text=re.sub(r'(?<!\w)'+re.escape(spelling)+r'(?!\w)',
                    lambda m,word=spoken: word,text,flags=re.IGNORECASE)
    return text


class PlaybackError(RuntimeError):
    pass


def find_ffplay() -> str | None:
    candidate = shutil.which("ffplay") or shutil.which("ffplay.exe")
    if candidate:
        return candidate
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if ffmpeg:
        sibling = Path(ffmpeg).with_name("ffplay.exe" if sys.platform == "win32" else "ffplay")
        if sibling.is_file():
            return str(sibling)
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        packages = local / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            # Only scan the packaged FFmpeg distributions, not the whole disk.
            for folder in packages.glob("*FFmpeg*"):
                for candidate_path in folder.glob("**/bin/ffplay.exe"):
                    if candidate_path.is_file():
                        return str(candidate_path)
    return None


class AudioPlayer:
    """One player per window. Playback never opens an external media app."""

    def __init__(self):
        self.process = None
        self.backend = None
        self.current_file = None

    def stop(self) -> None:
        process = self.process
        self.process = None
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
            finally:
                if process.stderr:
                    process.stderr.close()
        if self.backend == "Windows WAV":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except (ImportError, RuntimeError):
                pass
        self.backend = None
        self.current_file = None

    def play(self, path: str | Path) -> str:
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise PlaybackError(f"Audio file not found: {path}")
        if path.stat().st_size < 44:
            raise PlaybackError(f"The recording is empty or incomplete: {path.name}")

        self.stop()
        ffplay = find_ffplay()
        detail = ""
        if ffplay:
            command = [ffplay, "-nodisp", "-autoexit", "-hide_banner",
                       "-loglevel", "error", "-nostats", str(path)]
            options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
                       "stderr": subprocess.PIPE}
            if sys.platform == "win32":
                options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                process = subprocess.Popen(command, **options)
                time.sleep(0.12)
                rc = process.poll()
                if rc is None or rc == 0:
                    self.process = process
                    self.backend = "FFplay"
                    self.current_file = path
                    return self.backend
                detail = (process.stderr.read(4096) or b"").decode("utf-8", "replace").strip()
                process.stderr.close()
            except OSError as exc:
                detail = str(exc)

        if sys.platform == "win32" and path.suffix.lower() == ".wav":
            try:
                import winsound
                winsound.PlaySound(str(path),
                                   winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                self.backend = "Windows WAV"
                self.current_file = path
                return self.backend
            except (OSError, RuntimeError) as exc:
                detail = str(exc)

        raise PlaybackError(
            "Could not play this audio through the Windows output device. "
            "Check the default speaker, volume mixer, and that FFplay is installed "
            "alongside FFmpeg." + (f"\n\nDetails: {detail}" if detail else "")
        )


def python_bin() -> str:
    p = Path(sys.executable)
    if p.name.lower() == 'pythonw.exe':
        other = p.with_name('python.exe')
        if other.exists():
            return str(other)
    return str(p)


def call(cmd: list[str]) -> str:
    p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, encoding='utf-8', errors='replace', check=False)
    if p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}):\n{p.stdout[-2600:]}")
    return p.stdout


def parse_voice(voice: str) -> tuple[str, str]:
    if voice.startswith('profile:'):
        name=voice.partition(':')[2]
        if not re.fullmatch(r'[a-z0-9-]{1,75}',name):
            raise ValueError('Invalid saved voice profile ID')
        return 'qwen',name
    if voice.startswith('kokoro:'):
        name = voice.partition(':')[2]
        # These voice IDs are shipped by the official Kokoro v1 voices bundle.
        if name not in {'am_onyx', 'am_adam', 'am_michael', 'am_eric', 'am_fenrir',
                        'am_liam', 'am_echo', 'am_puck'}:
            raise ValueError('Unsupported Kokoro voice preset: ' + name)
        return 'kokoro', name
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,90}', voice):
        raise ValueError('Invalid voice name')
    return 'piper', voice


def voice_slug(voice: str) -> str:
    engine, name = parse_voice(voice)
    return f'{engine}_{name}' if engine in {'kokoro','qwen'} else name


def check_voice(voice: str) -> None:
    engine, name = parse_voice(voice)
    if engine == 'qwen':
        from voice_profiles import get_audio,get_profile
        profile=get_profile(name)
        if not profile.get('consent_confirmed'):
            raise PermissionError('Voice owner authorization is required.')
        get_audio(name,'reference')
        return
    if engine == 'kokoro':
        if not KOKORO_MODEL.is_file() or not KOKORO_VOICES.is_file():
            raise RuntimeError('Kokoro voice model is missing. Click INSTALL SELECTED VOICE first. '
                               'The first download is approximately 350 MB.')
    else:
        model, config = VOICE_DIR / (name + '.onnx'), VOICE_DIR / (name + '.onnx.json')
        if not model.is_file() or not config.is_file():
            raise RuntimeError(f'Piper voice {name} is missing. Click INSTALL SELECTED VOICE first.')


def _download(url: str, output: Path, min_bytes: int) -> None:
    if output.is_file() and output.stat().st_size > min_bytes:
        print(f'Reusing installed model: {output.name}', flush=True)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + '.partial')
    print(f'Downloading {output.name} (first use only)...', flush=True)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={
                'User-Agent': 'CrowsNestStudio/2.1'}), timeout=60) as response:
            with partial.open('wb') as out:
                total = 0
                last_report = 0
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
                    total += len(block)
                    if total - last_report >= 25 * 1024 * 1024:
                        print(f'{output.name}: {total // (1024 * 1024)} MB downloaded', flush=True)
                        last_report = total
        if partial.stat().st_size <= min_bytes:
            raise RuntimeError(f'Incomplete model file received: {output.name}')
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)


def install_voice(voice: str) -> None:
    engine, name = parse_voice(voice)
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    if engine == 'qwen':
        print('Installing optional local Qwen3-TTS. The weights download on first use and need significant hardware.',flush=True)
        print(call([python_bin(),'-m','pip','install','qwen-tts','soundfile','torch']),flush=True)
        check_voice(voice)
        return
    if engine == 'kokoro':
        print('Installing the offline Kokoro speech engine...', flush=True)
        print(call([python_bin(), '-m', 'pip', 'install', 'kokoro-onnx==0.6.1',
                    'soundfile>=0.13,<1']), flush=True)
        _download(MODEL_URL, KOKORO_MODEL, 80_000_000)
        _download(VOICES_URL, KOKORO_VOICES, 10_000_000)
        # Fail early if a corrupted or incompatible file was downloaded.
        from kokoro_onnx import Kokoro
        tts = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
        if name not in tts.get_voices():
            raise RuntimeError(f'Voice {name} not present in Kokoro voice pack.')
        print('Kokoro installed and model loaded successfully.', flush=True)
    else:
        print(call([python_bin(), '-m', 'pip', 'install', 'piper-tts==1.8.0']), flush=True)
        print(call([python_bin(), '-m', 'piper.download_voices',
                    '--data-dir', str(VOICE_DIR), name]), flush=True)
    check_voice(voice)


def _sentence_chunks(text: str, limit: int = 220) -> list[str]:
    text = ' '.join(text.split())
    if not text:
        raise ValueError('Narration text is empty')
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: list[str] = []
    current = ''
    for sentence in sentences:
        words = sentence.split()
        for word in words:
            if len(word) > limit:
                raise ValueError('A word exceeds the narrator model input limit')
            proposed = (current + ' ' + word).strip()
            if len(proposed) > limit and current:
                chunks.append(current)
                current = word
            else:
                current = proposed
        if current and len(current) >= 115:
            chunks.append(current)
            current = ''
    if current:
        chunks.append(current)
    return chunks


def _speak_kokoro(text: str, out: Path, voice: str, speed: float, tts=None) -> None:
    import numpy as np
    import soundfile as sf
    if tts is None:
        from kokoro_onnx import Kokoro
        tts = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    output = []
    sample_rate = None
    parts = _sentence_chunks(text)
    for i, part in enumerate(parts):
        samples, rate = tts.create(part, voice=voice, speed=speed, lang='en-us')
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        if not len(audio):
            raise RuntimeError('Kokoro generated empty audio')
        if sample_rate is not None and rate != sample_rate:
            raise RuntimeError('Inconsistent Kokoro output sample rate')
        sample_rate = rate
        output.append(audio)
        if i != len(parts) - 1:
            output.append(np.zeros(int(rate * 0.14), dtype=np.float32))
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), np.concatenate(output), sample_rate, subtype='PCM_16')


def _speak_piper(text: str, out: Path, name: str) -> None:
    call([python_bin(), '-m', 'piper', '--data-dir', str(VOICE_DIR),
          '-m', name, '-f', str(out), '--', text])


def speak(text: str, out: Path, voice: str, speed: float = 0.97, tts=None) -> Path:
    if not 0.75 <= speed <= 1.25:
        raise ValueError('Narration speed must be between 0.75 and 1.25')
    check_voice(voice)
    engine, name = parse_voice(voice)
    spoken_text = normalize_for_speech(text)
    if engine == 'qwen':
        from qwen_voice import clone
        clone(name,spoken_text,out,model=tts)
    elif engine == 'kokoro':
        _speak_kokoro(spoken_text, out, name, speed, tts=tts)
    else:
        _speak_piper(spoken_text, out, name)
    with wave.open(str(out), 'rb') as generated:
        if generated.getnframes() <= 0:
            raise RuntimeError('Narration audio is empty')
    return out


def digest(text: str, voice: str, speed: float) -> str:
    return hashlib.sha256(f'4.2\0{voice}\0{speed:.3f}\0{normalize_for_speech(text.strip())}'.encode('utf-8')).hexdigest()


def generate_sample(voice: str, speed: float = 0.97) -> Path:
    suffix = f'{int(speed * 100):03d}'
    path = AUDIO_DIR / 'voice_previews' / f'{voice_slug(voice)}_{suffix}_pron2.wav'
    if not path.is_file():
        speak(SAMPLE_TEXT, path, voice, speed)
    print('VOICE PREVIEW READY: ' + str(path), flush=True)
    return path


def synthesize(manifest: Path, voice: str, speed: float = 0.97) -> Path:
    check_voice(voice)
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    scenes = doc.get('scenes', [])
    if not scenes:
        raise ValueError('Add narration text before generating audio')
    slug = str(doc.get('slug') or 'episode').strip()
    if slug != Path(slug).name or not slug.replace('-', '').replace('_', '').isalnum():
        raise ValueError('Invalid episode name')
    target = AUDIO_DIR / slug / voice_slug(voice)
    target.mkdir(parents=True, exist_ok=True)
    cache = target / 'cache.json'
    old = json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {}
    new: dict[str, str] = {}
    rendered: list[Path] = []
    engine, _name = parse_voice(voice)
    tts = None
    if engine == 'kokoro':
        from kokoro_onnx import Kokoro
        tts = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    elif engine == 'qwen':
        from qwen_voice import load_model,CLONE_MODEL
        tts = load_model(CLONE_MODEL)
    for idx, scene in enumerate(scenes, 1):
        text = scene.get('narration', '').strip()
        if not text:
            raise ValueError(f'Scene {idx} has no narration')
        filename = f'{idx:02}.wav'
        out = target / filename
        h = digest(text, voice, speed)
        if engine == 'qwen':
            from voice_profiles import get_audio,get_profile
            ref=get_audio(_name,'reference')
            profile=get_profile(_name)
            h=hashlib.sha256((h + hashlib.sha256(ref.read_bytes()).hexdigest() + profile.get('transcript','')).encode()).hexdigest()
        if old.get(filename) != h or not out.exists() or out.stat().st_size < 1000:
            print(f'Generating scene {idx}/{len(scenes)} with {voice}...', flush=True)
            speak(text, out, voice, speed=speed, tts=tts)
        else:
            print(f'Reusing narrator audio for scene {idx}/{len(scenes)}.', flush=True)
        new[filename] = h
        rendered.append(out)
        scene['audio'] = str(out)
    cache.write_text(json.dumps(new, indent=2), encoding='utf-8')
    doc['narrator'] = {'voice': voice, 'speed': speed}
    manifest.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding='utf-8')
    preview = target / 'Narration_Preview.wav'
    if len(rendered) == 1:
        shutil.copyfile(rendered[0], preview)
    else:
        cmd = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y']
        for audio in rendered:
            cmd.extend(['-i', str(audio)])
        streams = ''.join(f'[{i}:a]' for i in range(len(rendered)))
        cmd.extend(['-filter_complex', f'{streams}concat=n={len(rendered)}:v=0:a=1[out]',
                    '-map', '[out]', '-c:a', 'pcm_s16le', str(preview)])
        call(cmd)
    print('NARRATION READY: ' + str(preview), flush=True)
    return preview


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('episode', nargs='?', type=Path)
    parser.add_argument('--voice', default='kokoro:am_onyx')
    parser.add_argument('--speed', type=float, default=0.97)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--sample', action='store_true')
    args = parser.parse_args()
    if args.install:
        install_voice(args.voice)
    elif args.sample:
        generate_sample(args.voice, args.speed)
    else:
        if args.episode is None or not args.episode.is_file():
            raise ValueError('Provide an existing episode manifest JSON file')
        synthesize(args.episode, args.voice, args.speed)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(1)
