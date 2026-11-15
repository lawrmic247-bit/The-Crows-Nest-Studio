#!/usr/bin/env python3
"""The Crow's Nest Studio — desktop documentary editor, v4.0."""
from __future__ import annotations
import json, os, queue, re, subprocess, sys, threading, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from fact_checker import require_clearance, status_summary, sync_report
from narration import voice_slug
from voice_profiles import list_profiles
from voice_studio_ui import VoiceStudio
from production_ui import ProductionStudio
from fact_checker_ui import FactCheckDialog
import update_engine

ROOT = Path(__file__).resolve().parent
FOOTAGE = ROOT / 'assets' / 'footage'
FOOTAGE.mkdir(parents=True, exist_ok=True)
VOICE_OPTIONS = {
    'Kokoro Onyx — deep American male (recommended)': 'kokoro:am_onyx',
    'Kokoro Adam — American male': 'kokoro:am_adam',
    'Kokoro Michael — American male': 'kokoro:am_michael',
    'Kokoro Fenrir — American male': 'kokoro:am_fenrir',
    'Piper Ryan — basic US male (legacy)': 'en_US-ryan-high',
    'Piper Lessac — basic (legacy)': 'en_US-lessac-medium',
}

GOLD = '#e8ba65'
INK = '#071523'
PANEL = '#10243b'
CREAM = '#f0e5ca'
MUTED = '#a6b7ca'


def python_bin() -> str:
    p = Path(sys.executable)
    if p.name.lower() == 'pythonw.exe' and p.with_name('python.exe').exists():
        return str(p.with_name('python.exe'))
    return str(p)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("THE CROW'S NEST — STUDIO v4.0")
        self.geometry('1160x850')
        self.minsize(760,570)
        self.configure(bg=INK)
        if sys.platform == 'win32':
            try:
                self.iconbitmap(default=str(ROOT/'assets'/'branding'/'CrowsNestStudio.ico'))
            except (tk.TclError, OSError):
                pass
        self.pipe: queue.Queue = queue.Queue()
        self.busy = False
        self.last_preview: Path | None = None
        self.loaded_manifest_path: Path | None = None
        self.loaded_production_job: str | None = None
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('N.TFrame', background=INK)
        style.configure('N.TLabel', background=INK, foreground=CREAM, font=('Segoe UI', 10))
        style.configure('N.TCheckbutton', background=INK, foreground=CREAM, font=('Segoe UI', 10))
        style.configure('N.TButton', font=('Segoe UI', 10), padding=(12, 7))
        style.configure('N.TCombobox', font=('Segoe UI', 10))

        # Header remains visible while editing.
        heading = tk.Frame(self, bg=INK, padx=20, pady=13)
        heading.pack(fill='x')
        tk.Label(heading, text="THE CROW'S NEST", fg=GOLD, bg=INK,
                 font=('Georgia', 24, 'bold')).pack(anchor='w')
        tk.Label(heading, text='DOCUMENTARY STUDIO  /  PRODUCTION QUEUE  /  VOICE STUDIO  /  NO RENDER CREDITS',
                 fg=MUTED, bg=INK, font=('Segoe UI', 9)).pack(anchor='w')

        # Main pane scrolls on small laptop screens; bottom actions do not disappear.
        self.canvas = tk.Canvas(self, bg=INK, highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        inside = tk.Frame(self.canvas, bg=INK, padx=20)
        self.inner = inside
        self.canvas_window = self.canvas.create_window((0,0), window=inside, anchor='nw')
        inside.bind('<Configure>', lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e:self.canvas.itemconfigure(self.canvas_window, width=e.width))
        self.canvas.bind_all('<MouseWheel>', self.mouse_scroll)

        self._label(inside, 'VIDEO TITLE')
        self.title_var = tk.StringVar(value="The History of the Crow's Nest")
        ttk.Entry(inside, textvariable=self.title_var, font=('Segoe UI', 12)).pack(fill='x', pady=(3,12))

        controls = tk.Frame(inside, bg=INK)
        controls.pack(fill='x', pady=(0,12))
        fmt = tk.Frame(controls, bg=INK)
        fmt.pack(side='left', padx=(0,28))
        self._label(fmt, 'OUTPUT FORMAT')
        self.short = tk.BooleanVar(value=True)
        self.wide = tk.BooleanVar(value=False)
        ttk.Checkbutton(fmt, text='Shorts  9:16', variable=self.short, style='N.TCheckbutton').pack(side='left')
        ttk.Checkbutton(fmt, text='YouTube  16:9', variable=self.wide, style='N.TCheckbutton').pack(side='left', padx=(14,0))

        voice_frame = tk.Frame(controls, bg=INK)
        voice_frame.pack(side='left', fill='x', expand=True)
        self._label(voice_frame, 'NARRATOR  •  TRY THE VOICES BEFORE RENDERING')
        self.refresh_voices()
        self.voice_var = tk.StringVar(value=next(iter(VOICE_OPTIONS)))
        self.voice_combo=ttk.Combobox(voice_frame, textvariable=self.voice_var, state='readonly',
                     values=list(VOICE_OPTIONS), width=51)
        self.voice_combo.pack(anchor='w', fill='x')

        prompt_bar=tk.Frame(inside,bg=INK)
        prompt_bar.pack(fill='x',pady=(4,8))
        ttk.Button(prompt_bar,text='PROMPT → VIDEO QUEUE',command=self.open_production_studio).pack(side='left')
        ttk.Button(prompt_bar,text='Quick draft (Ollama)',command=self.prompt_draft).pack(side='left',padx=(8,0))
        ttk.Button(prompt_bar,text='VOICE STUDIO — RECORD / CLEAN / CLONE',command=self.open_voice_studio).pack(side='left',padx=8)
        tk.Label(prompt_bar,text='Drafts are UNVERIFIED until the fact-check gate clears them.',fg=MUTED,bg=INK).pack(side='left')
        self._label(inside, 'NARRATION SCRIPT   •   blank line = new scene')
        self.script = scrolledtext.ScrolledText(inside, height=9, wrap='word',
                                                fg=CREAM, bg=PANEL, insertbackground=CREAM,
                                                font=('Segoe UI', 11), undo=True,
                                                relief='flat', borderwidth=9)
        self.script.pack(fill='x', pady=(4,11))
        self.script.insert('1.0',
            "Long before radar, a lookout could be the first to recognize trouble on the horizon.\n\n"
            "From the upper deck, sailors scanned for ships, land, weather, and danger. Their duty was vigilance.\n\n"
            "This is The Crow's Nest. Military history, traditions, news, and the people behind the stories.")

        self.script.bind('<KeyRelease>', lambda event: setattr(self, 'last_preview', None))
        self.voice_var.trace_add('write', lambda *_: setattr(self, 'last_preview', None))
        pace = tk.Frame(inside, bg=INK)
        pace.pack(fill='x', pady=(0,9))
        tk.Label(pace, text='NARRATION PACE', fg=GOLD, bg=INK,
                 font=('Segoe UI', 9, 'bold')).pack(side='left', padx=(0,12))
        self.speed_var = tk.StringVar(value='0.97')
        ttk.Combobox(pace, textvariable=self.speed_var, values=['0.85','0.90','0.94','0.97','1.00','1.05','1.10'],
                     state='readonly', width=7).pack(side='left')
        tk.Label(pace, text='0.97 = natural measured documentary pace', fg=MUTED,
                 bg=INK, font=('Segoe UI',9)).pack(side='left', padx=(12,0))
        self.speed_var.trace_add('write', lambda *_: setattr(self, 'last_preview', None))

        # Voice actions are prominent and independent from video rendering.
        voice_actions = tk.Frame(inside, bg=INK)
        voice_actions.pack(fill='x', pady=(0,6))
        self.generate_button = tk.Button(voice_actions, text='1  GENERATE NARRATION',
                                         command=self.generate_narration, bg=GOLD, fg=INK,
                                         activebackground='#ffd98d', relief='flat',
                                         font=('Segoe UI', 10, 'bold'), padx=18, pady=10,
                                         cursor='hand2')
        self.generate_button.pack(side='left', padx=(0,8))
        self.sample_button = ttk.Button(voice_actions, text='HEAR THIS VOICE', command=self.preview_selected_voice)
        self.sample_button.pack(side='left', padx=(0,8))
        self.preview_button = ttk.Button(voice_actions, text='Play full narration', command=self.play_narration)
        self.preview_button.pack(side='left', padx=(0,8))
        self.voice_install_button = ttk.Button(voice_actions, text='Install selected voice',
                                               command=self.install_voice)
        self.voice_install_button.pack(side='left')
        tk.Label(inside, text='Kokoro sounds more natural than Piper. One-time model download ~350 MB; later previews and production run offline.',
                 fg=MUTED, bg=INK, font=('Segoe UI', 9), anchor='w').pack(fill='x', pady=(0,15))

        self._label(inside, 'OPTIONAL FOOTAGE FOLDER   •   01.mp4 / 01.jpg / 02.mp4 ...')
        pathrow = tk.Frame(inside, bg=INK)
        pathrow.pack(fill='x', pady=(3,9))
        self.folder = tk.StringVar(value=str(FOOTAGE))
        ttk.Entry(pathrow, textvariable=self.folder).pack(side='left', fill='x', expand=True)
        ttk.Button(pathrow, text='Browse footage', command=self.browse).pack(side='left', padx=(8,0))
        tk.Label(inside, text='No footage? The editor will make branded scene cards. Actual military footage makes a stronger documentary.',
                 fg=MUTED, bg=INK, font=('Segoe UI', 9), anchor='w').pack(fill='x', pady=(0,10))

        self.review = tk.BooleanVar(value=False)
        ttk.Checkbutton(inside, text='I reviewed footage rights and personally reviewed all cited factual claims',
                        variable=self.review, style='N.TCheckbutton').pack(anchor='w', pady=(0,5))
        self.demo = tk.BooleanVar(value=False)
        ttk.Checkbutton(inside, text='Advanced: silent test render only (no narration)',
                        variable=self.demo, style='N.TCheckbutton').pack(anchor='w', pady=(0,12))

        self._label(inside, 'ACTIVITY LOG')
        self.log = scrolledtext.ScrolledText(inside, height=8, wrap='word',
                                             fg='#e0e8f2', bg='#030d18', insertbackground=CREAM,
                                             font=('Consolas', 9), relief='flat', borderwidth=8)
        self.log.pack(fill='x', pady=(3,10))

        # Always-visible bottom toolbar with the main deliverable action.
        bottom = tk.Frame(self, bg=PANEL, padx=20, pady=10)
        bottom.pack(side='bottom', fill='x')
        self.render_button = tk.Button(bottom, text='2  RENDER VIDEO',
                                       command=self.render, bg=GOLD, fg=INK,
                                       activebackground='#ffd98d', relief='flat',
                                       font=('Segoe UI', 12, 'bold'), padx=16, pady=9,
                                       cursor='hand2')
        self.render_button.pack(side='left', padx=(0,14))
        ttk.Button(bottom, text='Open exports', command=self.open_exports).pack(side='left', padx=(0,7))
        ttk.Button(bottom, text='FACT CHECK', command=self.fact_check).pack(side='left', padx=(0,7))
        ttk.Button(bottom, text='System / Updates', command=self.system_updates).pack(side='left', padx=(0,7))
        ttk.Button(bottom, text='Check setup', command=self.check_setup).pack(side='left')
        self.status = tk.StringVar(value='Ready • Generate narration, listen, then render your MP4.')
        tk.Label(bottom, textvariable=self.status, fg=CREAM, bg=PANEL,
                 font=('Segoe UI', 9), anchor='w', wraplength=480).pack(side='right', padx=(10,0))
        self._set_log('Studio v4.0: Prompt production queue, source suggestions, narration, voice profiles, factual review, and verified updater.\n')
        self.after(1800, self.auto_update_check)
        self.after(150, self.poll)

    def mouse_scroll(self, event):
        # Let the text editor scroll naturally while it has keyboard focus.
        if isinstance(self.focus_get(), tk.Text):
            return
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta/120)), 'units')

    def _label(self, parent, label):
        tk.Label(parent, text=label, fg=GOLD, bg=INK,
                 font=('Segoe UI', 9, 'bold'), anchor='w').pack(anchor='w')

    def _set_log(self, msg):
        self.log.insert('end', msg)
        self.log.see('end')

    def _busy(self, value: bool):
        self.busy = value
        state = 'disabled' if value else 'normal'
        for btn in (self.generate_button, self.preview_button,
                    self.voice_install_button, self.sample_button, self.render_button):
            btn.configure(state=state)

    def _run_task(self, name, runner):
        if self.busy:
            return
        self._busy(True)
        self.status.set(name)
        self._set_log('\n' + name + '\n')
        def thread_fn():
            try:
                runner()
            except Exception as exc:
                self.pipe.put(('error', str(exc)))
        threading.Thread(target=thread_fn, daemon=True).start()

    def _command(self, args, timeout=None):
        command = [str(x) for x in args]
        kwargs = dict(cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                      text=True, encoding='utf-8', errors='replace', bufsize=1)
        if sys.platform == 'win32':
            kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        self.pipe.put('$ ' + ' '.join(command[:3]) + ' ...')
        p = subprocess.Popen(command, **kwargs)
        for line in p.stdout:
            self.pipe.put(line.rstrip())
        rc = p.wait(timeout=timeout)
        if rc:
            raise RuntimeError(f'Command failed (exit code {rc}). Read the activity log above.')

    def _manifest(self):
        raw = self.script.get('1.0', 'end').strip()
        title = self.title_var.get().strip()
        parts = [s.strip() for s in re.split(r'\n\s*\n+', raw) if s.strip()]
        if not title or not parts:
            raise ValueError('Enter a title and narration script first.')
        if len(parts) > 80:
            raise ValueError('Too many scenes. Use fewer than 81.')
        slug = re.sub(r'[^a-z0-9]+','_',title.lower()).strip('_')[:48]
        footage = Path(self.folder.get())
        scenes=[]
        for i, text in enumerate(parts, 1):
            item={'heading': f'Part {i} — {title[:48]}', 'narration': text}
            for ext in ('.mp4','.mov','.mkv','.webm','.jpg','.jpeg','.png','.webp'):
                path=footage/f'{i:02}{ext}'
                if path.is_file():
                    item['visual'] = str(path)
                    break
            audio = footage / f'{i:02}.wav'
            if audio.is_file():
                item['audio']=str(audio)
            scenes.append(item)
        if self.loaded_manifest_path and self.loaded_manifest_path.is_file():
            path=self.loaded_manifest_path
            old=json.loads(path.read_text(encoding='utf-8'))
            old_scenes=old.get('scenes',[])
            if len(old_scenes)==len(scenes):
                # Preserve storyboard visuals/attribution from the queued production job.
                for previous,current in zip(old_scenes,scenes):
                    current['heading']=previous.get('heading',current['heading'])
                    if 'visual' in previous and 'visual' not in current:current['visual']=previous['visual']
                    if (previous.get('narration')==current['narration'] and
                            old.get('narrator',{}).get('voice')==self._voice() and
                            float(old.get('narrator',{}).get('speed',0.97))==self._speed() and
                            'audio' in previous and 'audio' not in current):
                        current['audio']=previous['audio']
            obj=old
            obj.update(title=title,approved=self.review.get(),scenes=scenes,
                       narrator={'voice':self._voice(),'speed':self._speed()})
        else:
            path = ROOT/'episodes'/f'{slug}.json'
            obj={'slug':slug,'title':title,'approved':self.review.get(), 'narrator':{'voice':self._voice(), 'speed':self._speed()},
                 'sources':['User supplied; review before publication'], 'scenes':scenes}
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
        return path

    def open_production_studio(self):
        ProductionStudio(self,on_load=self.load_production_draft,default_voice=self._voice())

    def load_production_draft(self, path:Path, job_id:str):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data.get('scenes'),list) or not data['scenes']:
            raise ValueError('Production job does not have a valid storyboard.')
        self.loaded_manifest_path=Path(path)
        self.loaded_production_job=job_id
        self.title_var.set(data['title'])
        self.script.delete('1.0','end')
        self.script.insert('1.0','\n\n'.join(x.get('narration','') for x in data['scenes']))
        fmt=__import__('production_engine').get_job(job_id)['format']
        self.short.set(fmt in ('short','both'));self.wide.set(fmt in ('wide','both'))
        self.review.set(False);self.demo.set(False);self.last_preview=None
        for label,ident in VOICE_OPTIONS.items():
            if ident==__import__('production_engine').get_job(job_id)['voice']:
                self.voice_var.set(label);break
        self._set_log(f'Loaded production job {job_id}. Review claims in FACT CHECK, check footage rights, then narrate and render.\n')
        self.lift()

    def refresh_voices(self):
        for prof in list_profiles():
            VOICE_OPTIONS[f"CUSTOM • {prof['name']} • {prof['profile_id']}"] = 'profile:' + prof['profile_id']
        if getattr(self, 'voice_combo', None):
            self.voice_combo.configure(values=list(VOICE_OPTIONS))

    def open_voice_studio(self):
        VoiceStudio(self,on_use=self.select_custom_voice)

    def select_custom_voice(self,profile_id,name):
        self.refresh_voices()
        desired='profile:'+profile_id
        for label,value in VOICE_OPTIONS.items():
            if value == desired:
                self.voice_var.set(label)
                self._set_log(f'Selected custom voice {name}. Install its Qwen model before generating narration.\n')
                break

    def prompt_draft(self):
        topic=simpledialog.askstring('Prompt to script',
            'What is the episode about? Enter a full topic or production prompt:',parent=self,initialvalue=self.title_var.get())
        if not topic:return
        minutes=simpledialog.askinteger('Approximate duration','Target duration in minutes (1–20):',minvalue=1,maxvalue=20,initialvalue=5,parent=self)
        if minutes is None:return
        notes=filedialog.askopenfilename(title='OPTIONAL: researched source notes TXT (Cancel = unverified draft)',
                            filetypes=[('Text notes','*.txt'),('All files','*.*')],parent=self)
        def work():
            cmd=[python_bin(),str(ROOT/'draft_with_ollama.py'),'--topic',topic,'--minutes',str(minutes)]
            if notes:cmd+=['--notes',notes]
            self._command(cmd,timeout=600)
            import re
            slug=re.sub('[^a-z0-9]+','_',topic.lower()).strip('_')[:50]
            path=ROOT/'episodes'/f'{slug}_UNREVIEWED.json'
            data=json.loads(path.read_text(encoding='utf-8'))
            self.pipe.put(('draft_loaded',(topic,'\n\n'.join(x['narration'] for x in data['scenes']))))
            self.pipe.put(('done','Unverified draft loaded. Review and fact-check before generating a publishable video.'))
        self._run_task('Writing an UNVERIFIED documentary draft with your local Ollama model...',work)

    def _voice(self):
        return VOICE_OPTIONS[self.voice_var.get()]

    def _speed(self):
        return float(self.speed_var.get())

    def preview_selected_voice(self):
        voice = self._voice()
        speed = self._speed()
        suffix = f'{int(speed * 100):03d}'
        preview = ROOT / 'assets' / 'narration' / 'voice_previews' / f'{voice_slug(voice)}_{suffix}.wav'
        def work():
            self._command([python_bin(), str(ROOT/'narration.py'), '--voice', voice,
                           '--speed', str(speed), '--sample'])
            self.pipe.put(('play', str(preview)))
            self.pipe.put(('done', 'Voice sample ready. Try other narrators until one sounds right.'))
        self._run_task('Generating a short narrator sample...', work)

    def _narrate(self, manifest, voice, speed):
        self._command([python_bin(), str(ROOT/'narration.py'), str(manifest), '--voice', voice, '--speed', str(speed)])
        data = json.loads(manifest.read_text(encoding='utf-8'))
        return ROOT/'assets'/'narration'/data['slug']/voice_slug(voice)/'Narration_Preview.wav'

    def browse(self):
        path=filedialog.askdirectory(initialdir=self.folder.get())
        if path:
            self.folder.set(path)

    def generate_narration(self):
        try:
            manifest=self._manifest()
            voice=self._voice();speed=self._speed()
        except Exception as e:
            messagebox.showwarning('Missing input',str(e));return
        def work():
            preview=self._narrate(manifest,voice,speed)
            self.pipe.put(('preview',str(preview)))
            self.pipe.put(('done','Narration ready! Click Play narration to listen.'))
        self._run_task('Generating WAV narration locally...',work)

    def install_voice(self):
        voice=self._voice()
        def work():
            self._command([python_bin(), str(ROOT/'narration.py'), '--voice', voice, '--install'])
            self.pipe.put(('done',f'{voice} installed. Click HEAR THIS VOICE for a sample.'))
        self._run_task('Installing voice engine/model (internet required once)...',work)

    def play_narration(self):
        if self.last_preview and self.last_preview.exists():
            self._open(self.last_preview)
            return
        try:
            manifest=self._manifest();voice=self._voice();speed=self._speed()
        except Exception as e:
            messagebox.showwarning('Missing input',str(e));return
        def work():
            preview=self._narrate(manifest,voice,speed)
            self.pipe.put(('preview',str(preview)))
            self.pipe.put(('play',str(preview)))
            self.pipe.put(('done','Narration preview opened.'))
        self._run_task('Preparing narration playback...',work)

    def render(self):
        formats=[fmt for fmt,value in [('short',self.short),('wide',self.wide)] if value.get()]
        if not formats:
            messagebox.showwarning('Choose format','Select Shorts or YouTube widescreen.');return
        if not self.review.get() and not self.demo.get():
            messagebox.showwarning('Review required','Confirm footage rights and source-led fact checking.');return
        try:
            manifest=self._manifest();voice=self._voice();speed=self._speed()
        except Exception as e:
            messagebox.showwarning('Missing input',str(e));return
        demo=self.demo.get()
        if not demo:
            doc=json.loads(manifest.read_text(encoding='utf-8'))
            script='\n\n'.join(scene.get('narration','') for scene in doc['scenes'])
            try:require_clearance(doc['slug'],script)
            except (ValueError, OSError) as error:
                messagebox.showwarning('FACT CHECK REQUIRED',str(error));return
        def work():
            if not demo:
                doc=json.loads(manifest.read_text(encoding='utf-8'))
                if any('audio' not in s for s in doc['scenes']):
                    self._narrate(manifest,voice,speed)
            for fmt in formats:
                cmd=[python_bin(), str(ROOT/'studio.py'),'render',str(manifest),'--format',fmt,'--voice',voice]
                if demo:
                    cmd+=['--silent-demo']
                self._command(cmd)
            self.pipe.put(('done',f'Rendered {len(formats)} MP4 format(s). Click Open exports.'))
        self._run_task('Rendering MP4 video...',work)

    def fact_check(self):
        try:
            manifest=self._manifest()
            data=json.loads(manifest.read_text(encoding='utf-8'))
            script='\n\n'.join(scene.get('narration','') for scene in data['scenes'])
        except (ValueError,OSError) as error:
            messagebox.showwarning('Script needed',str(error));return
        FactCheckDialog(self,data['slug'],data['title'],script)

    def _configured_repo(self):
        return update_engine.load_settings().get('release_repo','')

    def system_updates(self):
        repo=self._configured_repo()
        message='Trusted GitHub Releases repository (owner/repository).\n\nUpdates require a Crow\'s Nest release repo. Leave blank to keep updates disabled.'
        answer=simpledialog.askstring('System & Updates',message,initialvalue=repo,parent=self)
        if answer is None:return
        answer=answer.strip()
        if answer:
            try:update_engine.validate_repo(answer)
            except ValueError as error:
                messagebox.showerror('Invalid repository',str(error));return
        settings=update_engine.load_settings()
        settings['release_repo']=answer
        update_engine.save_settings(settings)
        if answer:self.check_for_updates()
        else:messagebox.showinfo('Updates disabled','The studio can still check dependencies and fact-check scripts. No update source is configured.')

    def auto_update_check(self):
        if self._configured_repo():self.check_for_updates(silent=True)

    def check_for_updates(self,silent=False):
        repo=self._configured_repo()
        if not repo:return
        def work():
            try:
                release=update_engine.get_release(repo)
                if release:self.pipe.put(('update_available',release))
                elif not silent:self.pipe.put(('update_info','You have the latest version.'))
            except Exception as error:
                self.pipe.put(('update_log','Update check unavailable: '+str(error)))
        threading.Thread(target=work,daemon=True).start()
        if not silent:self._set_log(f'Checking verified releases for {repo}...\n')

    def download_update(self,release):
        def work():
            stage=update_engine.stage_release(release,install=ROOT)
            self.pipe.put(('update_staged',str(stage)))
        self._run_task(f'Verifying and staging v{release.version} update...',work)

    def install_staged_update(self,stage):
        args=[python_bin(),str(ROOT/'update_engine.py'),'apply',
              '--stage',str(stage),'--install',str(ROOT),'--wait-pid',str(os.getpid())]
        try:
            subprocess.Popen(args,cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self._set_log('App will close; verified update will install, then reopen automatically.\n')
            self.destroy()
        except Exception as error:
            messagebox.showerror('Unable to start installer',str(error))

    def check_setup(self):
        def work():
            self._command([python_bin(),str(ROOT/'studio.py'),'doctor'])
            self.pipe.put(('done','Setup check complete.'))
        self._run_task('Checking FFmpeg and narrator...',work)

    def _open(self,path:Path):
        try:
            if sys.platform=='win32':
                os.startfile(str(path))
            elif sys.platform=='darwin':
                subprocess.Popen(['open',str(path)])
            else:
                subprocess.Popen(['xdg-open',str(path)])
        except Exception as exc:
            messagebox.showerror('Could not open file',str(exc))

    def open_exports(self):
        path=ROOT/'exports'
        path.mkdir(parents=True, exist_ok=True)
        self._open(path)

    def poll(self):
        try:
            while True:
                msg=self.pipe.get_nowait()
                if isinstance(msg,tuple):
                    kind,value=msg
                    if kind=='draft_loaded':
                        self.loaded_manifest_path=None;self.loaded_production_job=None
                        self.title_var.set(value[0]);self.script.delete('1.0','end');self.script.insert('1.0',value[1])
                        self.review.set(False);self.demo.set(False);self.last_preview=None
                    elif kind=='preview':
                        self.last_preview=Path(value)
                    elif kind=='play':
                        self._open(Path(value))
                    elif kind=='done':
                        self.status.set(value)
                        self._busy(False)
                    elif kind=='update_available':
                        if messagebox.askyesno('New Crow\'s Nest version',
                                f'Version {value.version} is available from your trusted repository.\n\nDownload a verified update and restart?'):
                            self.download_update(value)
                    elif kind=='update_info':
                        messagebox.showinfo('System & Updates',value)
                    elif kind=='update_log':
                        self._set_log(value+'\n')
                    elif kind=='update_staged':
                        self.install_staged_update(Path(value))
                    elif kind=='error':
                        self.status.set('ERROR: '+value)
                        self._set_log('ERROR: '+value+'\n')
                        self._busy(False)
                else:
                    self._set_log(str(msg)+'\n')
        except queue.Empty:
            pass
        self.after(150,self.poll)

if __name__=='__main__':
    App().mainloop()
