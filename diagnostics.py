"""Human-readable diagnostics and opt-in repair for the local desktop studio."""
from __future__ import annotations
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VOICE_DIR=ROOT/'voices'


def find_winget_ffmpeg() -> Path | None:
    local=Path(os.environ.get('LOCALAPPDATA') or '')
    if not local.is_dir():return None
    base=local/'Microsoft'/'WinGet'/'Packages'
    if not base.exists():return None
    for p in base.glob('Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe'):
        if (p.parent/'ffprobe.exe').is_file():return p.parent
    return None


def fix_process_path() -> bool:
    if shutil.which('ffmpeg') and shutil.which('ffprobe'):return True
    found=find_winget_ffmpeg()
    if found:
        os.environ['PATH']=str(found)+os.pathsep+os.environ.get('PATH','')
    return bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))


def health(voice: str='kokoro:am_onyx', test_render: bool=False) -> list[tuple[str,str,str]]:
    results=[]
    def add(name,ok,description):results.append((name,'OK' if ok else 'ACTION NEEDED',description))
    add('FFmpeg',fix_process_path(),shutil.which('ffmpeg') or 'Install Gyan.FFmpeg')
    add('FFprobe',bool(shutil.which('ffprobe')),shutil.which('ffprobe') or 'Install FFprobe')
    add('Python runtime',sys.version_info >= (3,10),sys.version.split()[0])
    add('Pillow',importlib.util.find_spec('PIL') is not None,'Image/branding processor')
    add('Piper (legacy)',importlib.util.find_spec('piper') is not None,'Optional original speech engine')
    add('Kokoro narrator',importlib.util.find_spec('kokoro_onnx') is not None,'Natural local speech engine')
    if voice.startswith('kokoro:'):
        files=(VOICE_DIR/'kokoro'/'kokoro-v1.0.onnx',VOICE_DIR/'kokoro'/'voices-v1.0.bin')
    else:
        files=(VOICE_DIR/(voice+'.onnx'),VOICE_DIR/(voice+'.onnx.json'))
    add('Selected voice model',all(f.is_file() for f in files),voice)
    watermark=ROOT/'assets'/'branding'/'The_Crows_Nest_Watermark_512.png'
    add('Watermark',watermark.is_file(),str(watermark))
    add('Fact-check engine',(ROOT/'fact_checker.py').is_file() and (ROOT/'fact_checker_ui.py').is_file(),
        'Source-led claims review; publication blocked until cleared')
    add('Prompt production queue',(ROOT/'production_engine.py').is_file() and (ROOT/'production_ui.py').is_file(),
        'Ollama optional; queue stores drafts until reviewed')
    add('Ollama local model',shutil.which('ollama') is not None,
        'Install Ollama and pull model qwen3:8b for prompt drafting')
    add('Updater engine',(ROOT/'update_engine.py').is_file(),'Trusted GitHub Releases required for online updates')
    try:
        (ROOT/'exports').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryFile(dir=ROOT/'exports') as _f: pass
        add('Export folder',True,'Writable')
    except OSError as exc: add('Export folder',False,str(exc))
    if test_render and shutil.which('ffmpeg'):
        with tempfile.TemporaryDirectory(prefix='crows_test_') as tmp:
            sample=Path(tmp)/'check.mp4'
            cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',
                 'color=c=0x10243b:s=320x180:r=12:d=0.3','-c:v','libx264','-pix_fmt','yuv420p',str(sample)]
            try:
                cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
                add('Test video render',cp.returncode==0 and sample.stat().st_size>0,'320x180 MP4 output')
            except (Exception, OSError) as exc:add('Test video render',False,str(exc))
    return results


def repair(selected_voice='kokoro:am_onyx'):
    """User-triggered only: install known packages and download an official Piper voice."""
    fix_process_path()
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg not found. Install Gyan.FFmpeg; then click Repair again.')
    cmds=[[sys.executable,'-m','pip','install','Pillow>=10.2'],
          [sys.executable,str(ROOT/'narration.py'),'--voice',selected_voice,'--install']]
    for cmd in cmds:
        print('Running: '+ ' '.join(cmd[:4]),flush=True)
        completed=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 text=True,encoding='utf-8',errors='replace')
        print(completed.stdout[-3000:],flush=True)
        if completed.returncode:
            raise RuntimeError(f'Repair command failed ({completed.returncode}). See log.')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repair',action='store_true')
    ap.add_argument('--test-render',action='store_true')
    ap.add_argument('--voice',default='kokoro:am_onyx')
    args=ap.parse_args()
    if args.repair:repair(args.voice)
    for name,status,info in health(args.voice,args.test_render):
        print(f'{status:13} {name:22} {info}',flush=True)

if __name__=='__main__':main()
