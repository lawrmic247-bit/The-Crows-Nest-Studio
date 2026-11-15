#!/usr/bin/env python3
"""The Crow's Nest Studio — desktop documentary editor, v4.0."""
from __future__ import annotations
import json, os, queue, re, subprocess, sys, threading, webbrowser, tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from fact_checker import require_clearance, status_summary, sync_report
from narration import voice_slug, AudioPlayer, PlaybackError, find_ffplay, sample_preview_path, PRONUNCIATION_FILE, DEFAULT_PRONUNCIATIONS, load_pronunciations
from voice_profiles import list_profiles
from voice_studio_ui import VoiceStudio
import production_engine as production_engine
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

DISPLAY_MODE = update_engine.load_settings().get('appearance','slate')
SOFT_LIGHT = DISPLAY_MODE == 'soft_light'
GOLD = '#477669' if SOFT_LIGHT else '#9fc5bc'
INK = '#f2f5f2' if SOFT_LIGHT else '#202a33'
PANEL = '#dfe7e2' if SOFT_LIGHT else '#303d49'
CREAM = '#23382f' if SOFT_LIGHT else '#e0e6e8'
MUTED = '#50695f' if SOFT_LIGHT else '#bac7ce'
FIELD_BG = '#ffffff' if SOFT_LIGHT else '#374653'
TAB_BG = '#537566' if SOFT_LIGHT else '#48655e'
ACTIVE_BG = '#5d8877' if SOFT_LIGHT else '#bcd8cf'
ACTIVE_FG = '#ffffff' if SOFT_LIGHT else INK


def python_bin() -> str:
    p = Path(sys.executable)
    if p.name.lower() == 'pythonw.exe' and p.with_name('python.exe').exists():
        return str(p.with_name('python.exe'))
    return str(p)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("The Crow's Nest | Studio " + update_engine.VERSION)
        self.geometry('1160x830')
        self.minsize(740,520)
        self.configure(bg=INK)
        try:
            scale=float(update_engine.load_settings().get('ui_scale',1.0))
            if 0.9<=scale<=1.4:
                self.tk.call('tk','scaling',scale*1.33333333)
        except (OSError,ValueError,TypeError,tk.TclError):
            pass
        if sys.platform == 'win32':
            try:
                self.iconbitmap(default=str(ROOT/'assets'/'branding'/'CrowsNestStudio.ico'))
            except (tk.TclError, OSError):
                pass
        self.pipe: queue.Queue = queue.Queue()
        self.player=AudioPlayer()
        self.video_preview_process=None
        self.last_render=None
        self.busy=False
        self.production_window=None
        self.inbox_busy=False
        self.pending_chat_job=None
        self.last_preview: Path | None = None
        self.loaded_manifest_path: Path | None = None
        self.loaded_production_job: str | None = None

        style=ttk.Style(self)
        style.theme_use('clam')
        style.configure('TButton',font=('Segoe UI',10),padding=(12,9),
                        foreground=CREAM,background=PANEL,borderwidth=0)
        style.map('TButton',background=[('active','#45616a'),('disabled',PANEL)],
                  foreground=[('disabled','#8c9ba4')])
        style.configure('TEntry',font=('Segoe UI',11),fieldbackground=FIELD_BG,
                        foreground=CREAM,insertcolor=CREAM,padding=(9,8),borderwidth=1)
        style.configure('TCombobox',font=('Segoe UI',11),fieldbackground=FIELD_BG,
                        foreground=CREAM,background=PANEL,padding=6)
        style.map('TCombobox',fieldbackground=[('readonly',FIELD_BG)],
                  foreground=[('readonly',CREAM)])
        style.configure('TCheckbutton',font=('Segoe UI',11),background=INK,foreground=CREAM)
        style.map('TCheckbutton',background=[('active',INK)],
                  foreground=[('active',CREAM)])
        style.configure('Studio.TNotebook',background=INK,borderwidth=0)
        style.configure('Studio.TNotebook.Tab',font=('Segoe UI',11),padding=(22,13),
                        background=PANEL,foreground=CREAM)
        style.map('Studio.TNotebook.Tab',background=[('selected',TAB_BG)],
                  foreground=[('selected','#ffffff')])

        header=tk.Frame(self,bg=INK,padx=24,pady=16)
        header.pack(fill='x')
        tk.Label(header,text="The Crow's Nest",bg=INK,fg=CREAM,
                 font=('Segoe UI',23,'bold')).pack(anchor='w')
        tk.Label(header,text='One topic → Full documentary + YouTube Short + TikTok. Human-reviewed before publishing.',
                 bg=INK,fg=MUTED,font=('Segoe UI',11)).pack(anchor='w',pady=(3,0))

        self.tabs=ttk.Notebook(self,style='Studio.TNotebook')
        self.tabs.pack(fill='both',expand=True,padx=20,pady=(0,7))
        self.step_hint=tk.StringVar(value='Start by creating all three formats from one researched topic.')
        tk.Label(self,textvariable=self.step_hint,bg=INK,fg=MUTED,
                 font=('Segoe UI',10),anchor='w',justify='left',
                 wraplength=1060).pack(fill='x',padx=24,pady=(0,10))

        self._page_scroll_canvases=[]
        self._page_scroll_containers=[]
        def page(label):
            outer=tk.Frame(self.tabs,bg=INK)
            self.tabs.add(outer,text=label)
            canvas=tk.Canvas(outer,bg=INK,highlightthickness=0,borderwidth=0)
            bar=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
            canvas.configure(yscrollcommand=bar.set)
            bar.pack(side='right',fill='y')
            canvas.pack(side='left',fill='both',expand=True)
            inner=tk.Frame(canvas,bg=INK,padx=20,pady=19)
            win=canvas.create_window((0,0),window=inner,anchor='nw')
            inner.bind('<Configure>',lambda event,c=canvas:
                       c.configure(scrollregion=c.bbox('all')))
            canvas.bind('<Configure>',lambda event,c=canvas,w=win:
                        c.itemconfigure(w,width=event.width))
            self._page_scroll_canvases.append(canvas)
            self._page_scroll_containers.append(outer)
            return inner

        create=page('1 · STORY')
        voice=page('2 · VOICE')
        export=page('3 · VERIFY & RENDER')
        publish=page('4 · WATCH & PUBLISH')
        activity=page('5 · SETTINGS')
        self.write_page=create
        self.voice_page=voice
        self.export_page=export
        self.publish_page=publish
        self.activity_page=activity

        self._label(create,'Start with a topic, or polish a prepared script')
        tk.Label(create,text='Create a documentary draft with Ollama, or type your narration below. '
                 'Choose Create from one topic for three formats at once. Separate existing script scenes with blank lines.',
                 bg=INK,fg=MUTED,font=('Segoe UI',11),wraplength=900,justify='left').pack(
                     anchor='w',pady=(3,17))
        prompt_bar=tk.Frame(create,bg=INK);prompt_bar.pack(fill='x',pady=(0,15))
        ttk.Button(prompt_bar,text='Create from one topic',
                   command=self.open_production_studio).pack(side='left',padx=(0,10))
        ttk.Button(prompt_bar,text='Quick AI: research & draft',
                   command=self.prompt_draft).pack(side='left')
        self.chat_ready_button=ttk.Button(prompt_bar,text='Review ChatGPT draft',
                   state='disabled',command=self.open_chat_ready)
        self.chat_ready_button.pack(side='left',padx=(10,0))
        ttk.Button(create,text='View discovered research sources',
                   command=self.open_research_sources).pack(anchor='w',pady=(0,11))
        self._label(create,'Episode title')
        self.title_var=tk.StringVar(value="The History of the Crow's Nest")
        ttk.Entry(create,textvariable=self.title_var,font=('Segoe UI',12)).pack(
            fill='x',pady=(5,18))
        self._label(create,'Narration script')
        self.script=scrolledtext.ScrolledText(create,height=13,wrap='word',
                    fg=CREAM,bg=PANEL,insertbackground=CREAM,
                    selectbackground='#48655e',font=('Segoe UI',12),
                    relief='flat',borderwidth=0,padx=14,pady=12,undo=True)
        self.script.pack(fill='both',expand=True,pady=(6,12))
        self.script.insert('1.0',
            "Long before radar, a lookout could be the first to recognize trouble on the horizon.\n\n"
            "From the upper deck, sailors scanned for ships, land, weather, and danger. Their duty was vigilance.\n\n"
            "This is The Crow's Nest. Military history, traditions, news, and the people behind the stories.")
        self.script.bind('<KeyRelease>',lambda event:setattr(self,'last_preview',None))
        tk.Label(create,text='Next: open Narrate to select a voice and generate playback.',
                 bg=INK,fg=GOLD,font=('Segoe UI',10)).pack(anchor='w')

        self._label(voice,'Choose how the story sounds')
        tk.Label(voice,text='Listen to a short sample before generating the full narration. '
                 'Your own recordings and clones are managed in Voice Studio.',
                 bg=INK,fg=MUTED,font=('Segoe UI',11),wraplength=920,justify='left').pack(
                     anchor='w',pady=(3,20))
        self.refresh_voices()
        self.voice_var=tk.StringVar(value=next(iter(VOICE_OPTIONS)))
        self._label(voice,'Narrator')
        self.voice_combo=ttk.Combobox(voice,textvariable=self.voice_var,state='readonly',
                      values=list(VOICE_OPTIONS),width=65)
        self.voice_combo.pack(fill='x',pady=(6,18))
        self.voice_var.trace_add('write',lambda *_:setattr(self,'last_preview',None))
        pace=tk.Frame(voice,bg=INK);pace.pack(fill='x',pady=(0,22))
        tk.Label(pace,text='Speaking pace',bg=INK,fg=CREAM,
                 font=('Segoe UI',11,'bold')).pack(side='left',padx=(0,13))
        self.speed_var=tk.StringVar(value='0.97')
        ttk.Combobox(pace,textvariable=self.speed_var,
                 values=['0.85','0.90','0.94','0.97','1.00','1.05','1.10'],
                 state='readonly',width=9).pack(side='left')
        self.speed_var.trace_add('write',lambda *_:setattr(self,'last_preview',None))
        tk.Label(pace,text='0.97 gives a measured documentary pace',bg=INK,fg=MUTED,
                 font=('Segoe UI',10)).pack(side='left',padx=(14,0))
        actions=tk.Frame(voice,bg=INK);actions.pack(fill='x',pady=(0,12))
        self.sample_button=ttk.Button(actions,text='▶ Hear voice sample',
                         command=self.preview_selected_voice)
        self.sample_button.pack(side='left',padx=(0,10))
        self.voice_install_button=ttk.Button(actions,text='Install selected voice',
                         command=self.install_voice)
        self.voice_install_button.pack(side='left',padx=(0,10))
        ttk.Button(actions,text='My voices: record / clean / clone',
                   command=self.open_voice_studio).pack(side='left')
        ttk.Button(voice,text='Edit pronunciation guide',
                   command=self.edit_pronunciations).pack(anchor='w',pady=(0,3))
        self.generate_button=tk.Button(voice,text='Generate full narration',
                         command=self.generate_narration,bg=GOLD,fg=INK,
                         activebackground=ACTIVE_BG,activeforeground=ACTIVE_FG,relief='flat',
                         font=('Segoe UI',12,'bold'),padx=18,pady=11,cursor='hand2')
        self.generate_button.pack(anchor='w',pady=(14,13))
        listen=tk.Frame(voice,bg=INK);listen.pack(fill='x')
        self.preview_button=ttk.Button(listen,text='▶ Play generated narration',
                         command=self.play_narration)
        self.preview_button.pack(side='left',padx=(0,10))
        ttk.Button(listen,text='■ Stop audio',command=self.stop_audio).pack(side='left')
        tk.Label(voice,text='Playback happens inside Studio. No default media app is required. '
                 'If the voice model is missing, install it once and try the sample again.',
                 bg=INK,fg=MUTED,font=('Segoe UI',10),wraplength=850,
                 justify='left').pack(anchor='w',pady=(20,0))

        self._label(export,'Check your evidence, then make the video')
        tk.Label(export,text='Fact-check claims and confirm media rights before rendering. '
                 'No unpublished draft is automatically treated as verified.',
                 bg=INK,fg=MUTED,font=('Segoe UI',11),wraplength=920,
                 justify='left').pack(anchor='w',pady=(4,21))
        self._label(export,'Output format')
        fmt=tk.Frame(export,bg=INK);fmt.pack(fill='x',pady=(5,19))
        self.short=tk.BooleanVar(value=True)
        self.wide=tk.BooleanVar(value=False)
        ttk.Checkbutton(fmt,text='YouTube Short / TikTok • 9:16',variable=self.short).pack(side='left',padx=(0,20))
        ttk.Checkbutton(fmt,text='Full YouTube documentary • 16:9',variable=self.wide).pack(side='left')
        self._label(export,'Optional footage folder')
        pathrow=tk.Frame(export,bg=INK);pathrow.pack(fill='x',pady=(6,7))
        self.folder=tk.StringVar(value=str(FOOTAGE))
        ttk.Entry(pathrow,textvariable=self.folder).pack(side='left',fill='x',expand=True)
        ttk.Button(pathrow,text='Browse',command=self.browse).pack(side='left',padx=(10,0))
        tk.Label(export,text='Use 01.mp4 or 01.jpg for scene one, 02.mp4 for scene two, and so on. '
                 'If footage is missing, Studio makes a branded scene card.',
                 bg=INK,fg=MUTED,font=('Segoe UI',10),
                 wraplength=900,justify='left').pack(anchor='w',pady=(0,18))
        ttk.Button(export,text='Review factual claims and sources',
                   command=self.fact_check).pack(anchor='w',pady=(0,16))
        self.review=tk.BooleanVar(value=False)
        ttk.Checkbutton(export,text='I reviewed the cited claims and rights to the footage',
                        variable=self.review).pack(anchor='w',pady=(0,8))
        self.demo=tk.BooleanVar(value=False)
        ttk.Checkbutton(export,text='Advanced: silent test render (no narration)',
                        variable=self.demo).pack(anchor='w',pady=(0,20))
        row=tk.Frame(export,bg=INK);row.pack(fill='x')
        self.render_button=tk.Button(row,text='Render video',
                         command=self.render,bg=GOLD,fg=INK,
                         activebackground=ACTIVE_BG,activeforeground=ACTIVE_FG,relief='flat',
                         font=('Segoe UI',12,'bold'),padx=21,pady=12,cursor='hand2')
        self.render_button.pack(side='left',padx=(0,14))
        ttk.Button(row,text='Open exports folder',
                   command=self.open_exports).pack(side='left')

        self._label(publish,'Review the complete video before publishing')
        tk.Label(publish,text='Preview the complete MP4 with sound. Nothing is uploaded automatically. '
                 'When you approve it, Studio will open Buffer and your export folder '
                 'so you can attach the file and choose your channels.',
                 bg=INK,fg=MUTED,font=('Segoe UI',11),wraplength=900,
                 justify='left').pack(anchor='w',pady=(3,20))
        self.rendered_label=tk.StringVar(value='No finished video selected. Render a documentary or choose an MP4.')
        tk.Label(publish,textvariable=self.rendered_label,bg=PANEL,fg=CREAM,
                 font=('Segoe UI',11),justify='left',wraplength=880,
                 padx=12,pady=13).pack(fill='x',pady=(0,16))
        actions=tk.Frame(publish,bg=INK);actions.pack(fill='x',pady=(0,19))
        ttk.Button(actions,text='▶ Preview finished video',command=self.preview_video).pack(
                side='left',padx=(0,11))
        ttk.Button(actions,text='Select an existing MP4',command=self.select_rendered_video).pack(
                side='left',padx=(0,11))
        ttk.Button(actions,text='Open export folder',command=self.open_exports).pack(side='left')
        self.publish_reviewed=tk.BooleanVar(value=False)
        ttk.Checkbutton(publish,text='I watched this complete video and approve the final upload',
                        variable=self.publish_reviewed).pack(anchor='w',pady=(0,22))
        self.buffer_button=tk.Button(publish,text='Continue to Buffer upload',
                         command=self.open_buffer_upload,bg=GOLD,fg=INK,
                         activebackground=ACTIVE_BG,activeforeground=ACTIVE_FG,relief='flat',
                         font=('Segoe UI',12,'bold'),padx=22,pady=13,cursor='hand2')
        self.buffer_button.pack(anchor='w')
        tk.Label(publish,text='Buffer currently requires a publicly hosted video URL for its API. '
                 'This handoff opens its browser composer and your MP4 folder; '
                 'you attach the file and select TikTok or YouTube there.',
                 bg=INK,fg=MUTED,font=('Segoe UI',10),wraplength=900,
                 justify='left').pack(anchor='w',pady=(18,0))

        self._label(activity,'Activity log and system maintenance')
        tk.Label(activity,text='Progress, model-installation output, and error messages appear here. '
                 'Use Check setup if narration or rendering fails.',
                 bg=INK,fg=MUTED,font=('Segoe UI',11),wraplength=900,
                 justify='left').pack(anchor='w',pady=(4,16))
        row=tk.Frame(activity,bg=INK);row.pack(fill='x',pady=(0,15))
        ttk.Button(row,text='Check setup',command=self.check_setup).pack(side='left',padx=(0,10))
        ttk.Button(row,text='System / Updates',command=self.system_updates).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Display comfort',command=self.display_comfort).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Open exports',command=self.open_exports).pack(side='left')
        self.log=scrolledtext.ScrolledText(activity,height=16,wrap='word',
                          fg=CREAM,bg=PANEL,insertbackground=CREAM,
                          font=('Consolas',10),relief='flat',borderwidth=0,
                          padx=13,pady=12)
        self.log.pack(fill='both',expand=True,pady=(0,10))

        footer=tk.Frame(self,bg=PANEL,padx=20,pady=13)
        footer.pack(fill='x')
        self.status=tk.StringVar(value='Ready. Start at Write, then Narrate, then Review & render.')
        tk.Label(footer,textvariable=self.status,fg=CREAM,bg=PANEL,
                 font=('Segoe UI',10),anchor='w',justify='left',
                 wraplength=960).pack(fill='x')
        self._set_log('Studio '+update_engine.VERSION+' ready. Choose a step above.\n')
        hints=[
            'Create one topic and generate a documentary plus vertical social versions.',
            'Choose your narrator, hear the audio, then correct any difficult pronunciations.',
            'Check EVERY factual claim and footage license before the final render.',
            'Watch the entire video and approve it before opening Buffer.',
            'Adjust the display, update Studio, or inspect its activity log.'
        ]
        self.tabs.bind('<<NotebookTabChanged>>',
            lambda event:self.step_hint.set(hints[self.tabs.index(self.tabs.select())]))
        for number in range(1,6):
            self.bind_all(f'<Control-Key-{number}>',
                lambda event,idx=number-1:self.tabs.select(idx))
        self.bind_all('<Control-n>',lambda event:self.open_production_studio())
        self.bind_all('<Escape>',lambda event:self.stop_audio())
        self.bind_all('<MouseWheel>',self._page_mouse_wheel,add='+')
        self.bind_all('<Button-4>',self._page_mouse_wheel,add='+')
        self.bind_all('<Button-5>',self._page_mouse_wheel,add='+')
        self.after(1800,self.auto_update_check)
        self.after(150,self.poll)
        self.after(10000,self.poll_chat_inbox)
        self.protocol('WM_DELETE_WINDOW',self.close)

    def _page_mouse_wheel(self,event):
        # Scroll the currently visible page without stealing wheel events from
        # text editors, lists, or other windows.
        try:
            if event.widget.winfo_toplevel() is not self:
                other=self.production_window
                if other is not None and other.winfo_exists():
                    return other._page_mouse_wheel(event)
                return
            tab_index=self.tabs.index(self.tabs.select())
            canvas=self._page_scroll_canvases[tab_index]
            outer=self._page_scroll_containers[tab_index]
            widget=event.widget
            while widget is not None and widget is not self:
                if isinstance(widget,(tk.Text,tk.Listbox,ttk.Treeview,ttk.Combobox)):
                    return
                if widget is outer:
                    break
                widget=widget.master
            if widget is not outer:
                return
            if event.num==4:
                units=-2
            elif event.num==5:
                units=2
            elif getattr(event,'delta',0):
                delta=event.delta
                units=-int(delta/120) if abs(delta)>=120 else (-1 if delta>0 else 1)
            else:
                return
            canvas.yview_scroll(units,'units')
            return 'break'
        except (tk.TclError,IndexError):
            return

    def mouse_scroll(self,event):
        return self._page_mouse_wheel(event)

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
                    if 'visual_provenance' in previous:
                        current['visual_provenance']=previous['visual_provenance']
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

    def edit_pronunciations(self):
        """Edit local pronunciation rules without altering historical script text."""
        top=tk.Toplevel(self)
        top.title("Narrator pronunciation guide")
        top.geometry('710x570')
        top.minsize(530,450)
        top.configure(bg=INK)
        tk.Label(top,text='How should the narrator say these words?',
                 bg=INK,fg=CREAM,font=('Segoe UI',16,'bold')).pack(
                    anchor='w',padx=19,pady=(18,7))
        tk.Label(top,text='Edit the JSON pairs below. The left side matches written text; '
                 'the right side is how the narrator should speak it. '
                 'Dates and 4-digit years are corrected automatically. '
                 'The original script and captions do not change.',
                 bg=INK,fg=MUTED,font=('Segoe UI',10),wraplength=650,
                 justify='left').pack(fill='x',padx=19,pady=(0,15))
        try:
            data=load_pronunciations()
            raw_text=json.dumps(data,indent=2,ensure_ascii=False)
        except (ValueError,OSError):
            raw_text=(PRONUNCIATION_FILE.read_text(encoding='utf-8',errors='replace')
                      if PRONUNCIATION_FILE.is_file()
                      else json.dumps(DEFAULT_PRONUNCIATIONS,indent=2,ensure_ascii=False))
            messagebox.showwarning('Repair pronunciation guide',
                'The saved pronunciation guide is invalid. Correct its JSON contents and save.',
                parent=top)
        editor=scrolledtext.ScrolledText(top,font=('Consolas',11),bg=PANEL,fg=CREAM,
                       insertbackground=CREAM,wrap='none',padx=13,pady=12)
        editor.pack(fill='both',expand=True,padx=19,pady=(0,13))
        editor.insert('1.0',raw_text)
        def save():
            try:
                rules=json.loads(editor.get('1.0','end'))
                if not isinstance(rules,dict) or len(rules)>120:
                    raise ValueError('Use a JSON object with no more than 120 entries.')
                for key,value in rules.items():
                    if not isinstance(key,str) or not isinstance(value,str):
                        raise ValueError('All rules must be written text.')
                    if not (1<=len(key.strip())<=100 and 1<=len(value.strip())<=150):
                        raise ValueError('Rules cannot be blank or excessively long.')
                PRONUNCIATION_FILE.parent.mkdir(parents=True,exist_ok=True)
                tmp=PRONUNCIATION_FILE.with_suffix('.tmp')
                tmp.write_text(json.dumps(rules,ensure_ascii=False,indent=2),
                               encoding='utf-8')
                tmp.replace(PRONUNCIATION_FILE)
                self.last_preview=None
                self.status.set('Saved pronunciation guide. Regenerate narration to hear changes.')
                top.destroy()
            except (ValueError,OSError) as exc:
                messagebox.showerror('Invalid pronunciation guide',str(exc),parent=top)
        row=tk.Frame(top,bg=INK);row.pack(fill='x',padx=19,pady=(0,14))
        ttk.Button(row,text='Save pronunciation guide',command=save).pack(side='left')
        ttk.Button(row,text='Cancel',command=top.destroy).pack(side='left',padx=(10,0))
        top.transient(self)

    def _video_file(self):
        path=self.last_render
        if path is None or not Path(path).is_file():
            messagebox.showwarning('No rendered MP4',
                'Render your video first or choose an existing export.',parent=self)
            return None
        return Path(path)

    def _set_rendered(self,path):
        path=Path(path)
        self.last_render=path
        self.publish_reviewed.set(False)
        self.rendered_label.set('Ready to preview: '+str(path))
        self.tabs.select(self.publish_page)

    def select_rendered_video(self):
        path=filedialog.askopenfilename(parent=self,
              initialdir=str(ROOT/'exports'),title='Select your completed Crow Nest MP4',
              filetypes=[('MP4 video','*.mp4')])
        if path:self._set_rendered(path)

    def preview_video(self):
        path=self._video_file()
        if not path:return
        if self.video_preview_process is not None:
            try:
                if self.video_preview_process.poll() is None:self.video_preview_process.terminate()
            except OSError:pass
        executable=find_ffplay()
        if executable:
            try:
                self.video_preview_process=subprocess.Popen(
                    [executable,'-autoexit','-hide_banner','-loglevel','error',
                     '-window_title',"The Crow's Nest - video preview",str(path)],
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                self.status.set('Video preview open. Watch the whole MP4 before approval.')
                return
            except OSError as exc:
                self._set_log('FFplay video preview unavailable: '+str(exc)+'\n')
        self._open(path)

    def open_buffer_upload(self):
        path=self._video_file()
        if not path:return
        if not self.publish_reviewed.get():
            messagebox.showwarning('Watch first',
                'Preview the complete MP4 and check the approval box before continuing.',parent=self)
            return
        yes=messagebox.askyesno('Hand off to Buffer',
              'Open Buffer and this MP4 folder for manual attachment and final channel selection? '
              'This does NOT publish anything yet.',parent=self)
        if not yes:return
        try:
            self.clipboard_clear()
            self.clipboard_append(self.title_var.get().strip())
            self._open(path.parent)
            webbrowser.open('https://publish.buffer.com/')
            self.status.set('Buffer opened. Attach your MP4, choose the channels, then publish in Buffer.')
        except (OSError,tk.TclError) as exc:
            messagebox.showerror('Buffer handoff error',str(exc),parent=self)

    def open_production_studio(self):
        if self.production_window is not None and self.production_window.winfo_exists():
            self.production_window.lift()
            self.production_window.focus_set()
            return
        self.production_window=ProductionStudio(
            self,on_load=self.load_production_draft,default_voice=self._voice())

    def open_chat_ready(self):
        if not self.pending_chat_job:
            self.status.set('No imported ChatGPT draft is ready.')
            return
        try:
            job=production_engine.get_job(self.pending_chat_job)
            if job['status']!='awaiting_review' or not job.get('manifest'):
                raise ValueError('The imported draft is not ready for review.')
            self.load_production_draft(Path(job['manifest']),job['id'])
            self.reviewed_chat_ids.add(job['id'])
            self.chat_ready_button.configure(state='disabled')
            self.pending_chat_job=None
        except (OSError,ValueError,KeyError) as exc:
            messagebox.showerror('Cannot open imported draft',str(exc),parent=self)

    def poll_chat_inbox(self):
        """Import when the main app is open, without auto-clearing a user's edits."""
        try:
            self._poll_chat_inbox_once()
        except (OSError,ValueError,TypeError) as exc:
            self._set_log('ChatGPT inbox check: '+str(exc)+'\n')
        if self.winfo_exists():
            self.after(45000,self.poll_chat_inbox)

    def _poll_chat_inbox_once(self):
        if self.inbox_busy:
            return
        if self.production_window is not None and self.production_window.winfo_exists():
            # The dedicated production window owns inbox polling while open.
            return
        folder_name=update_engine.load_settings().get('chatgpt_inbox','')
        if not folder_name or not Path(folder_name).is_dir():
            return
        folder=Path(folder_name).resolve()
        existing={job['id'] for job in production_engine.list_jobs()}
        new=[]
        for file in sorted(folder.glob('*.json'))[:60]:
            try:
                job=production_engine.import_chatgpt_job(file,source_folder=folder)
                if job['id'] not in existing:
                    existing.add(job['id'])
                    new.append(job['id'])
            except (OSError,ValueError,TypeError,KeyError):
                # An incomplete sync or invalid request is not trusted or executed.
                continue
        if not new:
            awaiting=[j for j in production_engine.list_jobs()
                      if j.get('source_file') and j['status']=='awaiting_review'
                      and j['id'] not in self.reviewed_chat_ids]
            if awaiting and not self.pending_chat_job:
                self.pipe.put(('chat_ready',awaiting[0]['id']))
            return
        self.inbox_busy=True
        self.status.set('New ChatGPT episode request received. Preparing an unverified draft...')
        def worker():
            for job_id in new:
                try:
                    job=production_engine.run_job(job_id)
                    if job['status']=='awaiting_review':
                        self.pipe.put(('chat_ready',job_id))
                except Exception as exc:
                    self.pipe.put(('update_log','ChatGPT draft could not run: '+str(exc)))
            self.pipe.put(('chat_inbox_idle',True))
        threading.Thread(target=worker,daemon=True).start()

    def load_production_draft(self, path:Path, job_id:str):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data.get('scenes'),list) or not data['scenes']:
            raise ValueError('Production job does not have a valid storyboard.')
        self.loaded_manifest_path=Path(path)
        self.loaded_production_job=job_id
        self.title_var.set(data['title'])
        self.script.delete('1.0','end')
        self.script.insert('1.0','\n\n'.join(x.get('narration','') for x in data['scenes']))
        delivery=data.get('deliverable','full')
        self.short.set(delivery in ('shorts','tiktok'))
        self.wide.set(delivery=='full')
        self.review.set(False);self.demo.set(False);self.last_preview=None
        for label,ident in VOICE_OPTIONS.items():
            if ident==__import__('production_engine').get_job(job_id)['voice']:
                self.voice_var.set(label);break
        self._set_log(f'Loaded production job {job_id}. Review claims in FACT CHECK, check footage rights, then narrate and render.\n')
        self.tabs.select(self.write_page)
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
                self.tabs.select(self.voice_page)
                break

    def prompt_draft(self):
        topic=simpledialog.askstring(
            'Research and draft a documentary',
            'What topic should Studio research and turn into a video?',
            parent=self,initialvalue=self.title_var.get())
        if not topic:return
        duration=simpledialog.askinteger(
            'Full documentary length','Target length in minutes (1–30):',
            minvalue=1,maxvalue=30,initialvalue=10,parent=self)
        if duration is None:return
        try:
            job=production_engine.create_job(
                topic,minutes=duration,fmt='both',voice=self._voice(),
                auto_media=True,visual_style='hybrid',
                deliverables=['full','shorts','tiktok'])
        except (ValueError,OSError) as exc:
            messagebox.showerror('Cannot create documentary',str(exc),parent=self)
            return
        def work():
            result=production_engine.run_job(
                job['id'],progress=lambda message:self.pipe.put(('update_log',message)))
            self.pipe.put(('quick_draft_ready',(result['id'],result['manifest'],
                        result.get('research_source_count',0))))
            self.pipe.put(('done','Research and draft prepared. Review facts and sources before rendering.'))
        self._run_task('Researching your topic and writing a source-led draft...',work)

    def open_research_sources(self):
        if not self.loaded_production_job:
            messagebox.showinfo('No research yet','Run Quick AI: research & draft first, '
                                'or load a research-backed job from the queue.',parent=self)
            return
        try:
            job=production_engine.get_job(self.loaded_production_job)
            path=Path(job.get('research_leads',''))
            if not path.is_file():
                raise ValueError('No research source file was found for this job.')
            self._open(path)
        except (OSError,ValueError,KeyError) as error:
            messagebox.showwarning('Research unavailable',str(error),parent=self)

    def _voice(self):
        return VOICE_OPTIONS[self.voice_var.get()]

    def _speed(self):
        return float(self.speed_var.get())

    def preview_selected_voice(self):
        voice = self._voice()
        speed = self._speed()
        preview = sample_preview_path(voice,speed)
        if preview.is_file() and preview.stat().st_size > 44:
            self._play_audio(preview)
            return
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

    def _play_audio(self,path):
        try:
            backend=self.player.play(path)
            self.status.set(f'Playing {Path(path).name} with {backend}. Click Stop audio to finish.')
            self._set_log('Audio playback started: '+str(path)+'\n')
        except (PlaybackError, OSError, ValueError) as exc:
            self.status.set('Playback error. Check your sound output.')
            self._set_log('PLAYBACK ERROR: '+str(exc)+'\n')
            self.tabs.select(self.activity_page)
            messagebox.showerror('Voice playback failed',
                    str(exc)+'\n\nCheck the Windows sound output and run Check setup in Activity & settings.',
                    parent=self)

    def stop_audio(self):
        self.player.stop()
        self.status.set('Playback stopped.')

    def play_narration(self):
        if self.last_preview and self.last_preview.is_file():
            self._play_audio(self.last_preview)
            return
        self.tabs.select(self.voice_page)
        messagebox.showinfo('Generate narration first',
            'Click Generate full narration, then Play generated narration. '
            'To hear a short sample first, click Hear voice sample.',
            parent=self)

    def close(self):
        self.player.stop()
        if self.video_preview_process is not None:
            try:
                if self.video_preview_process.poll() is None:self.video_preview_process.terminate()
            except OSError:pass
        self.destroy()

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
        doc_slug=json.loads(manifest.read_text(encoding='utf-8'))['slug']
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
            outputs=[str(ROOT/'exports'/f"{doc_slug}_{fmt}.mp4") for fmt in formats]
            self.pipe.put(('rendered',outputs[-1]))
            self.pipe.put(('done',f'Rendered {len(formats)} MP4 format(s). Open Preview & publish to inspect.'))
        self._run_task('Rendering MP4 video...',work)

    def fact_check(self):
        try:
            manifest=self._manifest()
            data=json.loads(manifest.read_text(encoding='utf-8'))
            script='\n\n'.join(scene.get('narration','') for scene in data['scenes'])
        except (ValueError,OSError) as error:
            messagebox.showwarning('Script needed',str(error));return
        leads=None
        if self.loaded_production_job:
            try:
                record=production_engine.get_job(self.loaded_production_job)
                candidate=record.get('research_leads','')
                if candidate and Path(candidate).is_file():leads=Path(candidate)
            except (OSError,ValueError,KeyError):
                pass
        FactCheckDialog(self,data['slug'],data['title'],script,source_leads=leads)

    def display_comfort(self):
        """Light/dark and text scaling are preferences, applied on next launch."""
        dialog=tk.Toplevel(self)
        dialog.title("Display comfort")
        dialog.geometry('470x340')
        dialog.configure(bg=INK)
        dialog.transient(self)
        settings=update_engine.load_settings()
        appearance=tk.StringVar(value=('Soft light' if settings.get('appearance')=='soft_light' else 'Low-glare dark'))
        size=tk.StringVar(value=str(int(float(settings.get('ui_scale',1.0))*100)))
        tk.Label(dialog,text='Customize the workspace',bg=INK,fg=CREAM,
                 font=('Segoe UI',16,'bold')).pack(anchor='w',padx=22,pady=(22,7))
        tk.Label(dialog,text='Choose a low-glare dark or soft light theme. '
                 'Increase text size if the interface feels crowded.',
                 bg=INK,fg=MUTED,font=('Segoe UI',10),wraplength=420,
                 justify='left').pack(anchor='w',padx=22,pady=(0,17))
        tk.Label(dialog,text='Appearance',bg=INK,fg=CREAM,
                 font=('Segoe UI',10,'bold')).pack(anchor='w',padx=22)
        ttk.Combobox(dialog,textvariable=appearance,values=['Low-glare dark','Soft light'],
                     state='readonly').pack(fill='x',padx=22,pady=(4,13))
        tk.Label(dialog,text='UI text size (%)',bg=INK,fg=CREAM,
                 font=('Segoe UI',10,'bold')).pack(anchor='w',padx=22)
        ttk.Combobox(dialog,textvariable=size,values=['90','100','115','125','140'],
                     state='readonly').pack(fill='x',padx=22,pady=(4,15))
        def save():
            settings['appearance']=('soft_light' if appearance.get()=='Soft light' else 'slate')
            settings['ui_scale']=int(size.get())/100
            update_engine.save_settings(settings)
            dialog.destroy()
            messagebox.showinfo('Display saved','Close and reopen Studio to apply your comfort settings.',
                                parent=self)
        ttk.Button(dialog,text='Save display settings',command=save).pack(anchor='w',padx=22)

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
                    if kind=='quick_draft_ready':
                        job_id,manifest,found=value
                        self.load_production_draft(Path(manifest),job_id)
                        self.status.set(f'{found} research source lead(s) found. Review the written '
                                        'script, then review each claim in Fact Checker.')
                    elif kind=='draft_loaded':
                        self.loaded_manifest_path=None;self.loaded_production_job=None
                        self.title_var.set(value[0]);self.script.delete('1.0','end');self.script.insert('1.0',value[1])
                        self.review.set(False);self.demo.set(False);self.last_preview=None
                        self.tabs.select(self.write_page)
                    elif kind=='preview':
                        self.last_preview=Path(value)
                    elif kind=='rendered':
                        self._set_rendered(Path(value))
                    elif kind=='chat_ready':
                        if value not in self.reviewed_chat_ids:
                            self.pending_chat_job=value
                            self.chat_ready_button.configure(state='normal')
                            self.status.set('ChatGPT draft prepared. Click Review ChatGPT draft in Write.')
                    elif kind=='chat_inbox_idle':
                        self.inbox_busy=False
                    elif kind=='play':
                        self._play_audio(Path(value))
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
