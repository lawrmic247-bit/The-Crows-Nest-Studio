"""Windows-friendly Voice Studio: non-destructive cleanup and optional local cloning."""
from __future__ import annotations
import os, subprocess, sys, tempfile, threading, tkinter as tk, wave
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk, scrolledtext
from narration import AudioPlayer, PlaybackError
from voice_profiles import (PROFILE_DIR, APPDATA, DEFAULT_ACTING, create_profile,
                            get_audio,get_profile,list_profiles,clean_recording,update_profile)

NAVY='#202a33';PANEL='#303d49';GOLD='#9fc5bc';CREAM='#e0e6e8';MUTED='#bac7ce'

class VoiceStudio(tk.Toplevel):
    def __init__(self, parent, on_use=None):
        super().__init__(parent)
        self.title("The Crow's Nest | Voice Studio")
        self.geometry('950x750')
        self.minsize(735,570)
        self.configure(bg=NAVY)
        self.on_use=on_use
        self.player=AudioPlayer()
        self.stream=None;self.captured=[];self.recording=False;self.sample_rate=48000
        self.selected_id=None;self.busy=False
        self.voice_var=tk.StringVar()
        self.name_var=tk.StringVar()
        self.level=tk.StringVar(value='light')
        self.choices={}
        self.clone_text=tk.StringVar(value="This is The Crow's Nest. We remember those who stood the watch.")
        self.status=tk.StringVar(value='Start by importing or recording a reference voice.')
        style=ttk.Style(self)
        style.configure('Voice.TNotebook',background=NAVY,borderwidth=0)
        style.configure('Voice.TNotebook.Tab',font=('Segoe UI',11),padding=(17,11),
                        background=PANEL,foreground=CREAM)
        style.map('Voice.TNotebook.Tab',background=[('selected','#446059')],
                  foreground=[('selected','#ffffff')])
        style.configure('Voice.TButton',font=('Segoe UI',10),padding=(12,9))
        style.configure('Voice.TEntry',font=('Segoe UI',11),padding=6)
        style.configure('Voice.TCombobox',font=('Segoe UI',11),padding=5)

        header=tk.Frame(self,bg=NAVY,padx=22,pady=16)
        header.pack(fill='x')
        tk.Label(header,text='Voice Studio',bg=NAVY,fg=CREAM,
                 font=('Segoe UI',23,'bold')).pack(anchor='w')
        tk.Label(header,text='Record  •  Listen  •  Refine  •  Use your own voice',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',11)).pack(anchor='w',pady=(3,0))

        picker=tk.Frame(self,bg=PANEL,padx=19,pady=13)
        picker.pack(fill='x',padx=18,pady=(0,10))
        tk.Label(picker,text='CURRENT VOICE PROFILE',bg=PANEL,fg=MUTED,
                 font=('Segoe UI',9,'bold')).pack(anchor='w',pady=(0,6))
        line=tk.Frame(picker,bg=PANEL);line.pack(fill='x')
        self.selector=ttk.Combobox(line,textvariable=self.voice_var,
                                   state='readonly',style='Voice.TCombobox')
        self.selector.pack(side='left',fill='x',expand=True)
        self.selector.bind('<<ComboboxSelected>>',lambda e:self.load())
        ttk.Button(line,text='Open library',style='Voice.TButton',
                   command=self.open_library).pack(side='left',padx=(10,0))

        tabs=ttk.Notebook(self,style='Voice.TNotebook')
        tabs.pack(fill='both',expand=True,padx=18,pady=(0,10))

        def page(title):
            outer=tk.Frame(tabs,bg=NAVY)
            tabs.add(outer,text=title)
            canvas=tk.Canvas(outer,bg=NAVY,highlightthickness=0)
            scroll=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right',fill='y')
            canvas.pack(side='left',fill='both',expand=True)
            content=tk.Frame(canvas,bg=NAVY,padx=14,pady=12)
            win=canvas.create_window((0,0),window=content,anchor='nw')
            content.bind('<Configure>',lambda e,c=canvas:c.configure(scrollregion=c.bbox('all')))
            canvas.bind('<Configure>',lambda e,c=canvas,w=win:c.itemconfigure(w,width=e.width))
            return content

        record_page=page('1. Record & import')
        self._label(record_page,'Start with an actual voice recording',14)
        tk.Label(record_page,text='Use a quiet 20–30 second recording. This is saved privately on your PC. '
                  'The source file is never overwritten.',bg=NAVY,fg=MUTED,
                  wraplength=760,justify='left',font=('Segoe UI',11)).pack(
                      anchor='w',padx=16,pady=(0,16))
        row=tk.Frame(record_page,bg=NAVY);row.pack(fill='x',padx=16,pady=(0,12))
        ttk.Button(row,text='Import audio file',style='Voice.TButton',
                   command=self.import_audio).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Start microphone',style='Voice.TButton',
                   command=self.record).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Stop & save recording',style='Voice.TButton',
                   command=self.stop_recording).pack(side='left')
        ttk.Button(record_page,text='Install microphone support',style='Voice.TButton',
                   command=self.install_mic).pack(anchor='w',padx=16,pady=(0,20))
        self._label(record_page,'Profile name')
        ttk.Entry(record_page,textvariable=self.name_var,
                  style='Voice.TEntry').pack(fill='x',padx=16,pady=(2,12))
        tk.Label(record_page,text='Your saved voice profiles appear in the selector above. '
                 'You can keep different voices and performances without changing your originals.',
                 bg=NAVY,fg=MUTED,wraplength=750,justify='left',
                 font=('Segoe UI',10)).pack(anchor='w',padx=16,pady=(2,12))

        clean_page=page('2. Listen & clean')
        self._label(clean_page,'Hear your actual voice before changing anything',14)
        tk.Label(clean_page,text='The cleanup makes a separate copy. Start with LIGHT; '
                 'a stronger setting can remove too much vocal texture.',
                 bg=NAVY,fg=MUTED,wraplength=760,justify='left',
                 font=('Segoe UI',11)).pack(anchor='w',padx=16,pady=(0,14))
        audio=tk.Frame(clean_page,bg=NAVY);audio.pack(fill='x',padx=16,pady=(0,13))
        ttk.Button(audio,text='▶ Play original',style='Voice.TButton',
                   command=lambda:self.play('original')).pack(side='left',padx=(0,10))
        ttk.Button(audio,text='▶ Play cleaned',style='Voice.TButton',
                   command=lambda:self.play('cleaned')).pack(side='left',padx=(0,10))
        ttk.Button(audio,text='■ Stop audio',style='Voice.TButton',
                   command=self.stop_audio).pack(side='left')
        self._label(clean_page,'Cleanup intensity')
        row=tk.Frame(clean_page,bg=NAVY);row.pack(fill='x',padx=16,pady=(2,12))
        ttk.Combobox(row,textvariable=self.level,state='readonly',
                     values=['off','light','balanced','strong'],
                     width=15,style='Voice.TCombobox').pack(side='left',padx=(0,12))
        ttk.Button(row,text='Make cleaned copy',style='Voice.TButton',
                   command=self.clean).pack(side='left')
        tk.Label(clean_page,text='Compare original vs. cleaned. Use what sounds most like you. '
                 'Playback uses an internal player with a Stop button, not Windows file associations.',
                 bg=NAVY,fg=MUTED,wraplength=760,justify='left',
                 font=('Segoe UI',11)).pack(anchor='w',padx=16,pady=(3,16))
        ttk.Button(clean_page,text='Export cleaned or original WAV',style='Voice.TButton',
                   command=self.export_wav).pack(anchor='w',padx=16)

        clone_page=page('3. Direct & clone')
        self._label(clone_page,'Words spoken in the reference clip')
        self.transcript=scrolledtext.ScrolledText(clone_page,height=3,wrap='word',
                    font=('Segoe UI',11),bg=PANEL,fg=CREAM,insertbackground=CREAM,
                    relief='flat',padx=10,pady=8)
        self.transcript.pack(fill='x',padx=16,pady=(2,11))
        self._label(clone_page,'Voice acting guide')
        self.direction=scrolledtext.ScrolledText(clone_page,height=4,wrap='word',
                    font=('Segoe UI',11),bg=PANEL,fg=CREAM,insertbackground=CREAM,
                    relief='flat',padx=10,pady=8)
        self.direction.pack(fill='x',padx=16,pady=(2,7))
        tk.Label(clone_page,text='Notes are saved with this voice. Qwen Base clones from the '
                 'reference clip and exact transcript; it does not directly follow acting notes.',
                 bg=NAVY,fg=MUTED,wraplength=760,justify='left',
                 font=('Segoe UI',10)).pack(anchor='w',padx=16,pady=(0,10))
        row=tk.Frame(clone_page,bg=NAVY);row.pack(fill='x',padx=16,pady=(0,13))
        ttk.Button(row,text='Save profile and notes',style='Voice.TButton',
                   command=self.save).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Use voice for narration',style='Voice.TButton',
                   command=self.use_voice).pack(side='left')
        self._label(clone_page,'Try an AI-generated line')
        ttk.Entry(clone_page,textvariable=self.clone_text,
                  style='Voice.TEntry').pack(fill='x',padx=16,pady=(2,11))
        row=tk.Frame(clone_page,bg=NAVY);row.pack(fill='x',padx=16,pady=(0,17))
        ttk.Button(row,text='Generate voice clone',style='Voice.TButton',
                   command=self.clone_preview).pack(side='left',padx=(0,10))
        ttk.Button(row,text='Design fictional voice',style='Voice.TButton',
                   command=self.design).pack(side='left')
        self.direction.insert('1.0',DEFAULT_ACTING)

        footer=tk.Frame(self,bg=PANEL,padx=17,pady=11)
        footer.pack(fill='x')
        tk.Label(footer,textvariable=self.status,bg=PANEL,fg=CREAM,anchor='w',
                 justify='left',wraplength=850,
                 font=('Segoe UI',10)).pack(fill='x')
        self.refresh()
        self.protocol('WM_DELETE_WINDOW',self.close)

    def _label(self,parent,text,size=11):
        tk.Label(parent,text=text,bg=NAVY,fg=CREAM,font=('Segoe UI',size,'bold')).pack(anchor='w',padx=16,pady=(8,5))

    def _open(self,path):
        if sys.platform=='win32':os.startfile(str(path))
        else:subprocess.Popen(['xdg-open',str(path)])

    def refresh(self,pick=None):
        profiles=list_profiles();self.choices={f"{p['name']}  ({p['profile_id']})":p['profile_id'] for p in profiles}
        self.selector['values']=list(self.choices)
        for label,pid in self.choices.items():
            if pid==pick or (not pick and pid==self.selected_id):
                self.voice_var.set(label);self.load();return
        if self.choices:self.voice_var.set(next(iter(self.choices)));self.load()

    def load(self):
        self.selected_id=self.choices.get(self.voice_var.get())
        if not self.selected_id:return
        p=get_profile(self.selected_id)
        self.name_var.set(p['name'])
        self.transcript.delete('1.0','end');self.transcript.insert('1.0',p.get('transcript',''))
        self.direction.delete('1.0','end');self.direction.insert('1.0',p.get('direction',DEFAULT_ACTING))
        self.level.set(p.get('cleanup_strength','light') if p.get('cleanup_strength')!='none' else 'light')
        self.status.set(f"Selected {p['name']}. Original reference is preserved.")

    def import_audio(self,path=None):
        if path is None:
            path=filedialog.askopenfilename(title='Choose your own or licensed reference audio',filetypes=[('Audio','*.wav *.mp3 *.flac *.m4a *.ogg *.aac *.wma *.mp4')])
        if not path:return
        name=simpledialog.askstring('Voice profile','Name this voice (e.g., My Natural Narrator):',parent=self)
        if not name:return
        allowed=messagebox.askyesno('Voice ownership and permission',
            'Is this your own voice, or do you have the speaker’s explicit permission to clone it?\n\nOnly proceed for your own or authorized voices.',parent=self)
        if not allowed:return
        self._background('Importing voice (the original will not be modified)...',
            lambda:create_profile(name,Path(path),transcript='',direction=DEFAULT_ACTING,consent=True),
            lambda p:self.refresh(p['profile_id']))

    def install_mic(self):
        self._background('Installing local microphone support...',
            lambda:subprocess.run([sys.executable.replace('pythonw.exe','python.exe'),'-m','pip','install','sounddevice','numpy'],
                                  check=True,capture_output=True,text=True,timeout=180),
            lambda _:self.status.set('Microphone support installed. Click Record microphone.'))

    def record(self):
        if self.recording:return
        try:
            import sounddevice as sd
            self.captured=[]
            def callback(indata,frames,time,status):
                if status:pass
                self.captured.append(indata.tobytes())
            self.stream=sd.InputStream(samplerate=self.sample_rate,channels=1,dtype='int16',callback=callback)
            self.stream.start();self.recording=True
            self.status.set('RECORDING — Speak naturally into your microphone. Click Stop and save when finished.')
        except Exception as e:
            messagebox.showerror('Microphone unavailable',f'{e}\n\nTry Install mic support or record in Windows Sound Recorder, then import the file.',parent=self)

    def stop_recording(self):
        if not self.recording:return
        try:
            self.stream.stop();self.stream.close();self.recording=False
            APPDATA.mkdir(parents=True,exist_ok=True)
            import uuid
            path=APPDATA/f'unsaved_recording_{uuid.uuid4().hex[:8]}.wav'
            with wave.open(str(path),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(self.sample_rate)
                w.writeframes(b''.join(self.captured))
            self.import_audio(path)
            self.status.set('Recording captured. Original WAV saved to local voice library.')
        except Exception as e:messagebox.showerror('Recording error',str(e),parent=self)

    def _background(self,status,fn,on_done):
        if self.busy:return
        self.busy=True;self.status.set(status)
        def run():
            try:
                result=fn()
                self.after(0,lambda:self._complete(result,on_done))
            except Exception as err:
                msg=str(err)
                self.after(0,lambda:self._fail(msg))
        threading.Thread(target=run,daemon=True).start()

    def _complete(self,result,on_done):
        self.busy=False
        try:on_done(result)
        except Exception as e:self._fail(str(e))

    def _fail(self,error):
        self.busy=False;self.status.set('ERROR: '+error)
        messagebox.showerror('Voice Studio',error,parent=self)

    def save(self):
        if not self.selected_id:return
        try:
            update_profile(self.selected_id,name=self.name_var.get(),
                           transcript=self.transcript.get('1.0','end').strip(),
                           direction=self.direction.get('1.0','end').strip())
            self.refresh(self.selected_id);self.status.set('Saved profile settings.')
        except Exception as e:self._fail(str(e))

    def clean(self):
        if not self.selected_id:return
        pid=self.selected_id
        self._background('Cleaning recording without changing pitch or identity...',
                         lambda:clean_recording(pid,self.level.get()),
                         lambda path:self.status.set('Cleaned copy saved. Press Play cleaned to compare it against your original.'))

    def _play_audio(self,path):
        try:
            backend=self.player.play(path)
            self.status.set(f'Playing {Path(path).name} using {backend}. Press Stop audio to end playback.')
        except (PlaybackError,OSError,ValueError) as e:
            self._fail(str(e))

    def play(self,kind):
        if not self.selected_id:
            self.status.set('Choose or import a voice profile before playing audio.')
            return
        try:
            path=get_audio(self.selected_id,kind)
        except Exception as e:
            self._fail(str(e))
            return
        self._play_audio(path)

    def stop_audio(self):
        self.player.stop()
        self.status.set('Audio stopped.')


    def export_wav(self):
        if not self.selected_id:return
        target=filedialog.asksaveasfilename(title='Export narration WAV',defaultextension='.wav',
                   filetypes=[('WAV audio','*.wav')],parent=self)
        if not target:return
        import shutil
        p=get_profile(self.selected_id)
        source=get_audio(self.selected_id,'cleaned' if p.get('cleaned_file') else 'reference')
        shutil.copyfile(source,target)
        self.status.set('Exported narration recording. To use it as scene 1, name the file 01.wav in your footage folder.')

    def use_voice(self):
        if not self.selected_id:return
        self.save()
        if self.on_use:self.on_use(self.selected_id,self.name_var.get())
        self.status.set('Selected. This voice is now the narration voice in the main editor.')

    def clone_preview(self):
        if not self.selected_id:return
        self.save()
        pid=self.selected_id;text=self.clone_text.get().strip()
        if not text:return
        out=APPDATA/'previews'/f'{pid}_clone_preview.wav'
        def fn():
            from qwen_voice import clone
            return clone(pid,text,out)
        self._background('Loading local Qwen model and creating voice clone (may be slow)...',fn,
                         lambda p:self._play_audio(p))

    def design(self):
        name=simpledialog.askstring('Fictional voice','New character voice name:',parent=self)
        if not name:return
        prompt=simpledialog.askstring('Character voice design','Describe the fictional voice: age, accent, timbre, pace, mannerisms:',parent=self)
        if not prompt:return
        out=APPDATA/'previews'/'voice_design_reference.wav'
        def fn():
            from qwen_voice import design
            return design(name,prompt,out)
        self._background('Creating original fictional voice (large optional model download)...',fn,
                         lambda p:self.refresh(p['profile_id']))

    def open_library(self):
        PROFILE_DIR.mkdir(parents=True,exist_ok=True)
        self._open(PROFILE_DIR)

    def close(self):
        self.player.stop()
        if self.recording:
            try:self.stream.stop();self.stream.close()
            except Exception:pass
        self.destroy()
