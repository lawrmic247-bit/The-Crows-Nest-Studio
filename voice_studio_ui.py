"""Windows-friendly Voice Studio: non-destructive cleanup and optional local cloning."""
from __future__ import annotations
import os, subprocess, sys, tempfile, threading, tkinter as tk, wave
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk, scrolledtext
from voice_profiles import (PROFILE_DIR, APPDATA, DEFAULT_ACTING, create_profile,
                            get_audio,get_profile,list_profiles,clean_recording,update_profile)

NAVY='#071523';PANEL='#10243b';GOLD='#e8ba65';CREAM='#f0e5ca';MUTED='#a6b7ca'

class VoiceStudio(tk.Toplevel):
    def __init__(self, parent, on_use=None):
        super().__init__(parent)
        self.title("THE CROW'S NEST — VOICE STUDIO")
        self.geometry('850x760');self.minsize(700,550)
        self.configure(bg=NAVY)
        self.status=tk.StringVar(value='Import or record your voice to begin.')
        tk.Label(self,textvariable=self.status,bg=PANEL,fg=CREAM,wraplength=790,anchor='w',pady=9).pack(side='bottom',fill='x')
        canvas=tk.Canvas(self,bg=NAVY,highlightthickness=0)
        bar=ttk.Scrollbar(self,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        body=tk.Frame(canvas,bg=NAVY)
        pane=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(pane,width=e.width))
        self.on_use=on_use
        self.stream=None;self.captured=[];self.recording=False;self.sample_rate=48000
        self.selected_id=None
        self.busy=False
        self._label(body,'VOICE STUDIO  /  RECORD • CLEAN • CLONE',20)
        tk.Label(body,text='Original recordings stay untouched. Cleanup never shifts pitch or alters vocal formants.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w',padx=16)
        row=tk.Frame(body,bg=NAVY);row.pack(fill='x',padx=15,pady=8)
        self.voice_var=tk.StringVar()
        self.choices={}
        self.selector=ttk.Combobox(row,textvariable=self.voice_var,state='readonly',width=48)
        self.selector.pack(side='left',fill='x',expand=True)
        self.selector.bind('<<ComboboxSelected>>',lambda e:self.load())
        ttk.Button(row,text='Import reference audio',command=self.import_audio).pack(side='left',padx=(8,0))
        ttk.Button(row,text='Refresh',command=self.refresh).pack(side='left',padx=(8,0))
        mic=tk.Frame(body,bg=NAVY);mic.pack(fill='x',padx=15,pady=(0,8))
        ttk.Button(mic,text='Record microphone',command=self.record).pack(side='left')
        ttk.Button(mic,text='Stop and save recording',command=self.stop_recording).pack(side='left',padx=8)
        ttk.Button(mic,text='Install mic support',command=self.install_mic).pack(side='left',padx=8)
        self._label(body,'VOICE PROFILE')
        self.name_var=tk.StringVar();ttk.Entry(body,textvariable=self.name_var).pack(fill='x',padx=16,pady=(0,8))
        self._label(body,'REFERENCE TRANSCRIPT — EXACT WORDS SPOKEN IN YOUR CLIP')
        self.transcript=scrolledtext.ScrolledText(body,height=3,wrap='word',font=('Segoe UI',10))
        self.transcript.pack(fill='x',padx=16,pady=(0,9))
        self._label(body,'ACTING GUIDE — HOW THE CHARACTER SHOULD SOUND')
        self.direction=scrolledtext.ScrolledText(body,height=4,wrap='word',font=('Segoe UI',10))
        self.direction.pack(fill='x',padx=16,pady=(0,9))
        hint=('Acting notes describe the desired delivery. Qwen Base cloning uses the real reference audio and transcript; '
              'it does NOT accept an independent acting prompt. A separate VoiceDesign engine can create fictional voices from text.')
        tk.Label(body,text=hint,wraplength=790,justify='left',bg=NAVY,fg=MUTED).pack(fill='x',padx=16,pady=(0,6))
        ttk.Button(body,text='Save name / transcript / acting notes',command=self.save).pack(anchor='w',padx=16,pady=(0,8))
        self._label(body,'GENTLE CLEANUP — A/B BEFORE YOU USE IT')
        cleanup=tk.Frame(body,bg=NAVY);cleanup.pack(fill='x',padx=16,pady=(0,10))
        self.level=tk.StringVar(value='light')
        ttk.Combobox(cleanup,textvariable=self.level,state='readonly',values=['off','light','balanced','strong'],width=12).pack(side='left')
        ttk.Button(cleanup,text='Clean recording',command=self.clean).pack(side='left',padx=7)
        ttk.Button(cleanup,text='Play ORIGINAL',command=lambda:self.play('original')).pack(side='left',padx=7)
        ttk.Button(cleanup,text='Play CLEANED',command=lambda:self.play('cleaned')).pack(side='left',padx=7)
        ttk.Button(cleanup,text='Use as AI narrator',command=self.use_voice).pack(side='left',padx=7)
        ttk.Button(cleanup,text='Export WAV',command=self.export_wav).pack(side='left',padx=7)
        self._label(body,'AI VOICE CLONING — OPTIONAL LOCAL MODEL')
        tk.Label(body,text='Uses Qwen3-TTS Base. Requires an installed model; best with a capable GPU. Your voice reference stays on your computer.',
                 wraplength=790,justify='left',bg=NAVY,fg=MUTED).pack(fill='x',padx=16)
        self.clone_text=tk.StringVar(value="This is The Crow's Nest. From the first watch to the final bell, the stories remain.")
        ttk.Entry(body,textvariable=self.clone_text).pack(fill='x',padx=16,pady=(5,6))
        bottom=tk.Frame(body,bg=NAVY);bottom.pack(fill='x',padx=16)
        ttk.Button(bottom,text='Generate CLONE preview',command=self.clone_preview).pack(side='left')
        ttk.Button(bottom,text='Design a new FICTIONAL voice from prompt',command=self.design).pack(side='left',padx=10)
        ttk.Button(bottom,text='Open voice library',command=self.open_library).pack(side='left')
        def wheel(e):
            if e.delta and not isinstance(self.focus_get(),tk.Text):
                canvas.yview_scroll(int(-e.delta/120),'units')
        canvas.bind('<MouseWheel>',wheel)
        body.bind('<MouseWheel>',wheel)
        self.direction.insert('1.0',DEFAULT_ACTING)
        self.refresh()
        self.protocol('WM_DELETE_WINDOW',self.close)

    def _label(self,parent,text,size=10):
        tk.Label(parent,text=text,bg=NAVY,fg=GOLD,font=('Segoe UI',size,'bold')).pack(anchor='w',padx=16,pady=(8,3))

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
                         lambda path:(self.status.set('Cleaned copy created; A/B against ORIGINAL before selecting.'),self._open(path)))

    def play(self,kind):
        if not self.selected_id:return
        try:self._open(get_audio(self.selected_id,kind))
        except Exception as e:self._fail(str(e))

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
                         lambda p:(self.status.set('Clone preview created. Listen before using.'),self._open(p)))

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
        if self.recording:
            try:self.stream.stop();self.stream.close()
            except Exception:pass
        self.destroy()
