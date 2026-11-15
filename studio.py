#!/usr/bin/env python3
"""The Crow's Nest Studio: locally rendered documentary assembly.

Open toolchain: local Piper TTS (or supplied WAV), ffmpeg, Pillow.
Never posts to social networks on its own. Does not invent or fetch source footage.
"""
from __future__ import annotations
import argparse, copy, json, math, os, re, shutil, subprocess, sys, tempfile, textwrap, time, urllib.error, urllib.parse, urllib.request, uuid, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

BASE = "http://127.0.0.1:8188"
MAX_BYTES = 90 * 1024 * 1024
ACCEPTED_EXTS = {".mp4",".webm",".mov",".gif"}


class LocalVideoError(RuntimeError):
    pass


def _request(path:str,payload:dict|None=None,*,urlopen=None,limit=2_000_000,
             timeout=12)->bytes:
    if urlopen is None:urlopen=urllib.request.urlopen
    if not path.startswith("/") or path.startswith("//"):
        raise LocalVideoError("Only local ComfyUI routes can be queried.")
    url=BASE+path
    if payload is None:
        req=urllib.request.Request(url,headers={"User-Agent":"CrowsNestStudio/4.3"})
    else:
        req=urllib.request.Request(
            url,data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type":"application/json","User-Agent":"CrowsNestStudio/4.3"},
            method="POST")
    with urlopen(req,timeout=timeout) as response:
        raw=response.read(limit+1)
    if len(raw)>limit:
        raise LocalVideoError("Video engine response exceeds the safety limit.")
    return raw


def status(*,urlopen=None)->str:
    try:
        raw=json.loads(_request("/system_stats",urlopen=urlopen))
        system=raw.get("system",{})
        devices=raw.get("devices",[])
        display=str(devices[0].get("name","unknown accelerator")) if devices else "accelerator unknown"
        return "Connected to local ComfyUI: "+display
    except (urllib.error.URLError,TimeoutError,OSError,ValueError,KeyError,TypeError) as exc:
        raise LocalVideoError("ComfyUI is not running locally at 127.0.0.1:8188. "
                              "Open ComfyUI first. No cloud fallback is used.") from exc


def load_workflow(path:Path)->dict:
    path=Path(path)
    if path.suffix.lower()!=".json" or not path.is_file() or path.stat().st_size>1_500_000:
        raise LocalVideoError("Choose a ComfyUI API-format workflow JSON under 1.5 MB.")
    raw=json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw,dict) or not 1<=len(raw)<=200:
        raise LocalVideoError("Expected an API-format object keyed by node IDs.")
    found=0
    for node_id,node in raw.items():
        if not isinstance(node_id,str) or not isinstance(node,dict):
            raise LocalVideoError("Workflow node structure is invalid.")
        inputs=node.get("inputs")
        if not isinstance(node.get("class_type"),str) or not isinstance(inputs,dict):
            raise LocalVideoError("Export workflow in API format, not UI graph format.")
        for key,value in inputs.items():
            if isinstance(value,str) and "__CROWS_PROMPT__" in value:
                found+=1
    if found!=1:
        raise LocalVideoError("Place __CROWS_PROMPT__ exactly once in the positive prompt text node.")
    return raw


def prepare_workflow(template:dict,prompt:str)->dict:
    if not isinstance(prompt,str) or not 12<=len(prompt)<=1800:
        raise LocalVideoError("Prompt must be 12–1800 characters.")
    graph=copy.deepcopy(template)
    for node in graph.values():
        for name,value in node["inputs"].items():
            if isinstance(value,str) and "__CROWS_PROMPT__" in value:
                node["inputs"][name]=value.replace("__CROWS_PROMPT__",prompt)
    return graph


def _outputs(history:dict,prompt_id:str)->list[dict]:
    item=history.get(prompt_id,history)
    if not isinstance(item,dict):
        return []
    outputs=item.get("outputs",{})
    rows=[]
    for node in outputs.values():
        if not isinstance(node,dict):continue
        for field in ("videos","gifs","images"):
            for data in node.get(field,[]):
                name=str(data.get("filename",""))
                if Path(name).suffix.lower() in ACCEPTED_EXTS:
                    rows.append(data)
    return rows


def generate_clip(prompt:str,workflow:Path,out:Path,*,urlopen=None,
                  poll_interval=4,deadline_seconds=900)->Path:
    """Queue one trusted local ComfyUI workflow and retrieve an output video."""
    if not 5<=deadline_seconds<=3600:
        raise LocalVideoError("Generation deadline must be between 5 and 3600 seconds.")
    template=load_workflow(workflow)
    data={"prompt":prepare_workflow(template,prompt),"client_id":uuid.uuid4().hex}
    submission=json.loads(_request("/prompt",data,urlopen=urlopen))
    prompt_id=submission.get("prompt_id")
    if not isinstance(prompt_id,str) or not re.fullmatch(r"[a-z0-9-]{8,80}",prompt_id,re.I):
        raise LocalVideoError("ComfyUI rejected the queued workflow: "+str(submission.get("error","unknown")))
    stop=time.monotonic()+deadline_seconds
    while time.monotonic()<stop:
        history=json.loads(_request("/history/"+prompt_id,urlopen=urlopen))
        if prompt_id in history:
            record=history[prompt_id]
            if record.get("status",{}).get("status_str")=="error":
                raise LocalVideoError("ComfyUI reported a generation error; inspect its local queue.")
            files=_outputs(history,prompt_id)
            if files:
                candidate=files[0]
                name=str(candidate.get("filename",""))
                suffix=Path(name).suffix.lower()
                if suffix==".gif":
                    raise LocalVideoError("Workflow returned a GIF. Configure an MP4/WebM SaveVideo output.")
                route="/view?"+urllib.parse.urlencode({
                    "filename":name,
                    "subfolder":str(candidate.get("subfolder","")),
                    "type":str(candidate.get("type","output")),
                })
                raw=_request(route,urlopen=urlopen,limit=MAX_BYTES,timeout=120)
                if len(raw)<1000:
                    raise LocalVideoError("ComfyUI exported an empty video.")
                out=Path(out).with_suffix(suffix)
                out.parent.mkdir(parents=True,exist_ok=True)
                tmp=out.with_suffix(out.suffix+".partial")
                tmp.write_bytes(raw)
                os.replace(tmp,out)
                return out
            if record.get("status",{}).get("completed"):
                raise LocalVideoError("The workflow finished without an MP4/WebM clip.")
        time.sleep(poll_interval)
    raise LocalVideoError("ComfyUI timed out; check its queue. This does not mean it stopped rendering.")


def build_reenactment_prompt(heading:str,subject:str)->str:
    """Avoid synthetic imagery being mistaken for actual historical footage."""
    return (
        "Historical illustration only, NOT authentic archival footage. "
        "Cinematic realistic reconstruction of a military history documentary "
        "with restrained camera movement, no captions or insignia forgery. "
        "Research subject: "+subject[:200]+". Scene: "+heading[:220]+". "
        "Do not depict a known individual's identifiable face without a verified reference. "
        "Avoid invented exact casualty numbers, medals, or documentary evidence."
    )


ROOT = Path(__file__).resolve().parent
BRAND = ROOT / 'assets' / 'branding'
SAMPLE_BG = ROOT / 'assets' / 'sample' / 'background.jpg'
DEFAULT_VOICE = 'kokoro:am_onyx'
RESOLUTIONS = {'short':(1080,1920),'wide':(1920,1080)}


def shell(args:list[str], *, silent=False):
    if not silent: print('>', ' '.join(map(str,args)))
    r=subprocess.run([str(x) for x in args], check=False, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"Command failed ({r.returncode}): {' '.join(map(str,args))}\n{r.stderr[-3500:]}")
    return r.stdout


def require(binary):
    try:
        from diagnostics import fix_process_path
        fix_process_path()
    except ImportError:
        pass
    if not shutil.which(binary): raise RuntimeError(f'Missing {binary}. Install it and rerun.')


def probe_duration(f):
    return float(shell(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(f)],silent=True).strip())


def font(bold=False):
    candidates=(['C:/Windows/Fonts/georgiab.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'] if bold else
                ['C:/Windows/Fonts/georgia.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for f in candidates:
        if Path(f).exists(): return f
    return None


def fitted_font(text, max_width, first_size, bold=True):
    for size in range(max(16, int(first_size)), 14,-2):
        ff=ImageFont.truetype(font(bold),size) if font(bold) else ImageFont.load_default()
        if ImageDraw.Draw(Image.new('RGB',(10,10))).textbbox((0,0),text,font=ff)[2] <= max_width:return ff
    return ff


def make_card(out:Path, width:int,height:int,title:str,subtitle:str):
    im=Image.open(SAMPLE_BG).convert('RGB') if SAMPLE_BG.exists() else Image.new('RGB',(width,height),(5,16,29))
    im=ImageOps.fit(im,(width,height),method=Image.Resampling.LANCZOS,centering=(0.5,0.5))
    im=ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(radius=max(8,int(width*.015))))).enhance(0.40)
    # edge-to-edge dark veil, subtle modern-documentary style
    veil=Image.new('RGBA',(width,height),(0,0,0,0)); d=ImageDraw.Draw(veil)
    d.rounded_rectangle((int(width*.045),int(height*.30),int(width*.955),int(height*.71)),radius=18,fill=(2,14,28,206))
    im=Image.alpha_composite(im.convert('RGBA'),veil)
    d=ImageDraw.Draw(im)
    lines=textwrap.wrap(title.upper(),width=19 if height>width else 34,break_long_words=False)
    lines=lines[:4]
    fs=int(width*.067 if width>height else width*.084)
    top=int(height*.44)-len(lines)*fs*.57
    for line in lines:
        f=fitted_font(line,width*.82,fs,True)
        bbox=d.textbbox((0,0),line,font=f,stroke_width=1);tw=bbox[2]-bbox[0]
        d.text(((width-tw)/2,int(top)),line,font=f,fill=(246,230,197),stroke_fill=(0,0,0),stroke_width=2)
        top+=int(fs*1.23)
    d.rectangle((int(width*.22),int(top)+15,int(width*.78),int(top)+19),fill=(200,148,65))
    subf=fitted_font(subtitle,width*.78,int(width*.030),False)
    bbox=d.textbbox((0,0),subtitle,font=subf); tw=bbox[2]-bbox[0]
    d.text(((width-tw)/2,int(top)+38),subtitle,font=subf,fill=(215,196,166))
    out.parent.mkdir(parents=True,exist_ok=True);im.convert('RGB').save(out,quality=92)


def voice(scene:dict, idx:int, directory:Path, *, silent_demo=False,voice_model:str=DEFAULT_VOICE):
    src=scene.get('audio')
    if src:
        p=ROOT/src if not Path(src).is_absolute() else Path(src)
        if not p.exists():raise FileNotFoundError(f'Audio file for scene {idx}: {p}')
        return p
    wav=directory/f'narration_{idx:02}.wav'
    if silent_demo:
        secs=float(scene.get('demoSeconds',5.0))
        with wave.open(str(wav),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
            w.writeframes(b'\x00\x00'*int(secs*24000))
        return wav
    try:
        from narration import speak
        speak(scene['narration'], wav, voice_model)
    except Exception as e:
        raise RuntimeError('Local narrator failed. Install the voice from the desktop app or supply a WAV.\n'+str(e))
    return wav


def mk_subtitles(scenes, times, dest:Path):
    def stamp(t):
        v=max(0,round(t*1000));h,v=divmod(v,3600000);m,v=divmod(v,60000);s,ms=divmod(v,1000)
        return f'{h:02}:{m:02}:{s:02},{ms:03}'
    lines=[];n=1;offset=0.0
    for scene,dur in zip(scenes,times):
        # Approximate captions. For word-accurate timing, substitute aligned SRT.
        words=scene['narration'].replace('\n',' ').split();groups=[]
        for i in range(0,len(words),6):groups.append(' '.join(words[i:i+6]))
        if groups:
            weights=[max(1,len(g.split())) for g in groups]; total=sum(weights); start=offset
            for g,wt in zip(groups,weights):
                stop=min(offset+dur,start+dur*wt/total)
                lines.append(f'{n}\n{stamp(start)} --> {stamp(stop)}\n{g}\n');n+=1;start=stop
        offset+=dur
    dest.write_text('\n'.join(lines),encoding='utf-8')


def video_asset(scene, idx, directory, wh):
    path=scene.get('visual')
    if path:
        p=Path(path);p=(ROOT/p if not p.is_absolute() else p)
        if not p.exists(): raise FileNotFoundError(f'Scene {idx} visual missing: {p}')
        if p.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.mp4','.mov','.mkv','.webm'}:
            raise ValueError(f'Unsupported scene visual format: {p}')
        return p
    p=directory/f'card_{idx:02}.jpg'
    make_card(p,*wh, scene.get('heading',f'Scene {idx}'),'THE CROW’S NEST • INDEPENDENT')
    return p


def mk_scene(scene,idx,wav,duration,visual,out,wh,fps,visual_style='archival'):
    w,h=wh
    vf=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},format=yuv420p'
    ext=visual.suffix.lower()
    if ext in {'.png','.jpg','.jpeg','.webp'}:
        if visual_style in ('motion','hybrid'):
            # Restrained Ken Burns movement on authentic photos; no invented footage.
            vf=(f'scale={w}:{h}:force_original_aspect_ratio=increase,'
                f'crop={w}:{h},'
                f"zoompan=z='min(zoom+0.0005,1.12)':d=1:s={w}x{h}:fps={fps},"
                f'format=yuv420p')
        a=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(fps),'-i',str(visual)]
    else:
        a=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-stream_loop','-1','-i',str(visual)]
    if 'AI-generated' in str(scene.get('visual_provenance','')):
        vf+=(",drawtext=text='AI REENACTMENT - ILLUSTRATION':"
             "x=22:y=22:fontsize=24:fontcolor=white:"
             "box=1:boxcolor=black@0.76:boxborderw=12")
    a+=['-i',str(wav),'-vf',vf,'-af','apad','-t',f'{duration:.3f}','-r',str(fps),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-ac','2','-movflags','+faststart',str(out)]
    shell(a,silent=True)


def subtitle_filter(path):
    # FFmpeg's filter parser requires extra escaping for Windows paths and colons.
    p=path.resolve().as_posix().replace('\\','/').replace(':','\\:').replace("'","\\'")
    return f"subtitles='{p}':force_style='FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,Outline=2,Shadow=1,MarginV=70,Alignment=2'"


def render(manifest:Path,fmt:str,*,silent_demo=False,voice_model=DEFAULT_VOICE,captions=True,music=None):
    require('ffmpeg');require('ffprobe')
    data=json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(data.get('scenes'),list) or not data['scenes']:raise ValueError('Manifest must include scenes')
    if not silent_demo and data.get('approved') is not True:
        raise ValueError('Confirm footage rights and source-led factual review before rendering.')
    fact_path = None
    if not silent_demo:
        from fact_checker import require_clearance
        factual_script='\n\n'.join(scene.get('narration','') for scene in data['scenes'])
        fact_path=require_clearance(data['slug'],factual_script)
        # Rendering must NEVER generate new media after media-rights approval.
        # Studio Stage 4 prepares illustrations first, then the user reviews them.
        if data.get('visual_style')=='ai_reenactment' and data.get('production_job'):
            if data.get('ai_visuals_prepared') is not True:
                raise ValueError('Prepare AI illustrations in Step 4, inspect the results, then approve footage rights before rendering.')
    wh=RESOLUTIONS[fmt];fps=30
    out=ROOT/'exports'/f"{data.get('slug','episode')}_{fmt}.mp4"
    out.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='crowsnest_') as tmp:
        work=Path(tmp);clips=[];durs=[]
        for i,scene in enumerate(data['scenes'],1):
            if not scene.get('narration','').strip():raise ValueError(f'Scene {i} missing narration')
            audio=voice(scene,i,work,silent_demo=silent_demo,voice_model=voice_model)
            duration=max(1.0,probe_duration(audio)+0.20)
            visual=video_asset(scene,i,work,wh)
            clip=work/f'clip_{i:02}.mp4'
            print(f'Rendering scene {i}/{len(data["scenes"])} ({duration:.1f}s): {scene.get("heading", "")}',flush=True)
            mk_scene(scene,i,audio,duration,visual,clip,wh,fps,
                     visual_style=data.get('visual_style','archival'))
            durs.append(duration);clips.append(clip)
        concat=work/'list.txt';concat.write_text(''.join(f"file '{str(p).replace(chr(39),chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in clips),encoding='utf-8')
        joined=work/'joined.mp4'
        shell(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(joined)],silent=True)
        subtitles=out.with_suffix('.srt');mk_subtitles(data['scenes'],durs,subtitles)
        wmpath=BRAND/'The_Crows_Nest_Watermark_512.png'
        if not wmpath.exists():raise FileNotFoundError(f'Missing watermark: {wmpath}')
        ww=190 if fmt=='short' else 190
        if captions:
            first=subtitle_filter(subtitles)+','
        else:first=''
        sx='W-w-30' if fmt=='short' else 'W-w-40'
        sy='85' if fmt=='short' else '40'
        vf=f"[0:v]{first}format=yuv420p[base];[1:v]format=rgba,scale={ww}:-1,colorchannelmixer=aa=0.73[watermark];[base][watermark]overlay={sx}:{sy}[v]"
        cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',str(joined),'-i',str(wmpath)]
        if music:
            m=Path(music);m=(ROOT/m if not m.is_absolute() else m)
            if not m.exists():raise FileNotFoundError(m)
            cmd+=['-stream_loop','-1','-i',str(m)]
            vf+=';[0:a]volume=1.0[a0];[2:a]volume=0.09[a1];[a0][a1]amix=inputs=2:duration=first[a]'
            aout=['-map','[a]']
        else:aout=['-map','0:a']
        cmd+=['-filter_complex',vf,'-map','[v]']+aout+['-c:v','libx264','-preset','medium','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)]
        try:shell(cmd,silent=True)
        except RuntimeError as e:
            if captions and 'subtitles' in str(e).lower():
                raise RuntimeError('Your FFmpeg build needs libass to burn subtitles. Re-run with --no-burn-captions; an SRT will still be produced.\n'+str(e))
            raise
    publication={'title':data.get('title'),'summary':data.get('description'),'aiDisclosure':True,'officialAffiliation':False,'sources':data.get('sources',[]),'format':fmt,'visual_style':data.get('visual_style','archival'),'video':out.name,'subtitle':subtitles.name,'illustrativeAiScenes':[i+1 for i,scene in enumerate(data['scenes']) if 'AI-generated' in str(scene.get('visual_provenance',''))],'copyrightChecklist':'Human review of all source footage required','factCheckReport':str(fact_path) if fact_path else 'silent-demo; not fact-checked'}
    out.with_suffix('.publish.json').write_text(json.dumps(publication,indent=2),encoding='utf-8')
    print(f'FINISHED: {out} ({probe_duration(out):.1f}s). Captions: {subtitles}')
    return out


def doctor():
    from diagnostics import health
    for name,status,description in health(test_render=False):
        print(f'{status:13} {name:22} {description}')
    print('The Crow\'s Nest Studio — health check')
    for binary in ['ffmpeg','ffprobe']:
        print(f'{binary}: {shutil.which(binary) or "MISSING"}')
    try: import piper;print('Piper: available')
    except ImportError:print('Piper: not installed — pip install piper-tts')
    voices=list((ROOT/'voices').glob('*.onnx'))
    print('Downloaded voice models:',len(voices))
    print('Watermark:',(BRAND/'The_Crows_Nest_Watermark_512.png').exists())
    print('Exports:',ROOT/'exports')
    print('Formats:',', '.join(RESOLUTIONS))


def main():
    ap=argparse.ArgumentParser(description="The Crow's Nest unlimited local editor")
    sub=ap.add_subparsers(dest='cmd',required=True)
    sub.add_parser('doctor')
    r=sub.add_parser('render')
    r.add_argument('episode',type=Path)
    r.add_argument('--format',choices=RESOLUTIONS,default='short')
    r.add_argument('--voice',default=DEFAULT_VOICE)
    r.add_argument('--silent-demo',action='store_true',help='Testing only: creates silent placeholder audio rather than narration')
    r.add_argument('--no-burn-captions',action='store_true')
    r.add_argument('--music',default=None,help='Optional locally licensed audio file')
    args=ap.parse_args()
    if args.cmd=='doctor':doctor()
    elif args.cmd=='render':
        p=args.episode if args.episode.exists() else ROOT/args.episode
        if not p.exists():raise FileNotFoundError(p)
        render(p,args.format,silent_demo=args.silent_demo,voice_model=args.voice,captions=not args.no_burn_captions,music=args.music)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)
