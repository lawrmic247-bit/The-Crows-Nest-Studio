#!/usr/bin/env python3
"""Prompt production and persistent queue window for The Crow's Nest Studio."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,scrolledtext,ttk

import production_engine as engine

NAVY='#071523'; PANEL='#10243b'; GOLD='#e8ba65'; CREAM='#f0e5ca'; MUTED='#a6b7ca'


class ProductionStudio(tk.Toplevel):
    def __init__(self,parent,*,on_load=None,default_voice='kokoro:am_onyx'):
        super().__init__(parent)
        self.title("THE CROW'S NEST — PROMPT PRODUCTION QUEUE")
        self.geometry('990x790');self.minsize(760,610)
        self.configure(bg=NAVY)
        self.on_load=on_load
        self.busy=False
        self.notes=tk.StringVar(value='')
        self.minutes=tk.IntVar(value=8)
        self.fmt=tk.StringVar(value='wide')
        self.model=tk.StringVar(value='qwen3:8b')
        self.voice=tk.StringVar(value=default_voice)
        self.media=tk.BooleanVar(value=True)
        self.start_immediately=tk.BooleanVar(value=True)
        self.state=tk.StringVar(value='Add a prompt, then run it. New scripts remain UNVERIFIED until fact checked.')
        tk.Label(self,text='PROMPT-TO-DOCUMENTARY PRODUCTION',bg=NAVY,fg=GOLD,
                 font=('Georgia',18,'bold')).pack(fill='x',padx=17,pady=(12,3))
        tk.Label(self,text='LOCAL OLLAMA  /  ARCHIVAL MEDIA LEADS  /  FACT-CHECK GATE  /  VOICE PROFILES',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',padx=17)
        box=tk.Frame(self,bg=NAVY);box.pack(fill='x',padx=17,pady=(12,5))
        tk.Label(box,text='EPISODE PROMPT',bg=NAVY,fg=GOLD,font=('Segoe UI',10,'bold')).pack(anchor='w')
        self.prompt=scrolledtext.ScrolledText(box,height=4,wrap='word',bg=PANEL,fg=CREAM,
            insertbackground=CREAM,font=('Segoe UI',11),relief='flat',padx=8,pady=6)
        self.prompt.pack(fill='x',pady=(5,9))
        self.prompt.insert('1.0',"Explore the history of the crow's nest lookout, from sailing ships to modern naval operations. Show how the lookout's responsibilities and equipment changed, without inventing specific events or quotations.")
        opts=tk.Frame(box,bg=NAVY);opts.pack(fill='x')
        self._field(opts,'MINUTES',self.minutes,values=[1,2,3,5,8,10,12,15,20,30],width=6)
        self._field(opts,'FORMAT',self.fmt,values=['short','wide','both'],width=10)
        self._field(opts,'LOCAL OLLAMA MODEL',self.model,width=14)
        self._field(opts,'NARRATOR MODEL / PROFILE',self.voice,width=23)
        tk.Checkbutton(box,text='Find appropriately credited archival still images (Wikimedia Commons)',
             variable=self.media,bg=NAVY,fg=CREAM,selectcolor=PANEL,activebackground=NAVY,activeforeground=CREAM).pack(anchor='w',pady=(8,2))
        tk.Checkbutton(box,text='Start generating immediately when I add a prompt',
            variable=self.start_immediately,bg=NAVY,fg=CREAM,selectcolor=PANEL,activebackground=NAVY,activeforeground=CREAM).pack(anchor='w')
        source=tk.Frame(box,bg=NAVY);source.pack(fill='x',pady=(2,9))
        tk.Label(source,text='RESEARCH NOTES (OPTIONAL)',bg=NAVY,fg=GOLD).pack(side='left')
        ttk.Entry(source,textvariable=self.notes).pack(side='left',fill='x',expand=True,padx=(10,6))
        ttk.Button(source,text='Browse',command=self.choose_notes).pack(side='left')
        controls=tk.Frame(box,bg=NAVY);controls.pack(fill='x')
        self.add_btn=ttk.Button(controls,text='ADD PROMPT TO QUEUE',command=self.add_job)
        self.add_btn.pack(side='left',padx=(0,8))
        self.run_btn=ttk.Button(controls,text='RUN QUEUED EPISODES',command=self.run_queue)
        self.run_btn.pack(side='left',padx=(0,8))
        self.selected_btn=ttk.Button(controls,text='RUN SELECTED',command=self.run_selected)
        self.selected_btn.pack(side='left')
        tk.Label(self,text='PRODUCTION QUEUE — select an episode to review',bg=NAVY,fg=GOLD,
                 font=('Segoe UI',10,'bold')).pack(anchor='w',padx=17,pady=(8,3))
        listing=tk.Frame(self,bg=NAVY);listing.pack(fill='both',expand=True,padx=17)
        self.list=ttk.Treeview(listing,columns=('state','duration','created'),show='tree headings',height=7)
        self.list.heading('#0',text='Prompt / episode');self.list.column('#0',width=450)
        self.list.heading('state',text='Status');self.list.column('state',width=155,anchor='w')
        self.list.heading('duration',text='Target');self.list.column('duration',width=85,anchor='center')
        self.list.heading('created',text='Created (UTC)');self.list.column('created',width=145)
        scrollbar=ttk.Scrollbar(listing,command=self.list.yview);self.list.configure(yscrollcommand=scrollbar.set)
        self.list.pack(side='left',fill='both',expand=True);scrollbar.pack(side='left',fill='y')
        actions=tk.Frame(self,bg=NAVY);actions.pack(fill='x',padx=17,pady=(9,3))
        ttk.Button(actions,text='OPEN DRAFT IN EDITOR',command=self.open_draft).pack(side='left',padx=(0,8))
        ttk.Button(actions,text='VIEW MEDIA CREDITS',command=self.open_credits).pack(side='left',padx=(0,8))
        ttk.Button(actions,text='SOURCE SEARCH LEADS',command=self.open_leads).pack(side='left',padx=(0,8))
        ttk.Button(actions,text='OPEN JOB FOLDER',command=self.open_job_folder).pack(side='left',padx=(0,8))
        ttk.Button(actions,text='REFRESH',command=self.refresh).pack(side='left')
        tk.Label(self,text='ACTIVITY / ERRORS',bg=NAVY,fg=GOLD,font=('Segoe UI',10,'bold')).pack(anchor='w',padx=17)
        self.log=scrolledtext.ScrolledText(self,height=5,wrap='word',bg='#030d18',fg=CREAM,
                       font=('Consolas',9),relief='flat')
        self.log.pack(fill='x',padx=17,pady=(4,8))
        tk.Label(self,textvariable=self.state,anchor='w',wraplength=880,justify='left',
                 bg=PANEL,fg=CREAM,font=('Segoe UI',9),padx=12,pady=10).pack(fill='x')
        self.refresh()

    def _field(self,parent,label,variable,values=None,width=10):
        f=tk.Frame(parent,bg=NAVY);f.pack(side='left',padx=(0,15))
        tk.Label(f,text=label,bg=NAVY,fg=GOLD,font=('Segoe UI',8,'bold')).pack(anchor='w')
        if values:
            widget=ttk.Combobox(f,textvariable=variable,values=values,width=width,state='readonly')
        else:widget=ttk.Entry(f,textvariable=variable,width=width)
        widget.pack(anchor='w',pady=(4,0))

    def _log(self,message):
        self.log.insert('end',str(message)+'\n');self.log.see('end')
        self.state.set(str(message)[:350])

    def refresh(self,select=None):
        chosen=select or self.list.focus()
        for item in self.list.get_children():self.list.delete(item)
        for j in engine.list_jobs():
            self.list.insert('', 'end',iid=j['id'],text=j['title'][:110],values=(j['status'],str(j['minutes'])+' min',j['created_at'][:16].replace('T',' ')))
        if chosen in self.list.get_children():self.list.selection_set(chosen);self.list.focus(chosen)

    def choose_notes(self):
        p=filedialog.askopenfilename(parent=self,title='Source notes',filetypes=[('Plain text','*.txt'),('All files','*.*')])
        if p:self.notes.set(p)

    def add_job(self):
        try:
            j=engine.create_job(self.prompt.get('1.0','end'),minutes=self.minutes.get(),fmt=self.fmt.get(),
                model=self.model.get(),voice=self.voice.get(),notes_file=self.notes.get(),auto_media=self.media.get())
        except Exception as exc:messagebox.showerror('Invalid production request',str(exc),parent=self);return
        self.refresh(j['id']);self._log('Added '+j['id']+' to the production queue.')
        if self.start_immediately:self._run([j['id']])

    def _selection(self):
        ids=self.list.selection()
        if not ids:messagebox.showwarning('Select a job','Select one production job first.',parent=self);return None
        return ids[0]

    def _run(self,ids):
        if self.busy:
            messagebox.showinfo('Busy','A production job is already running.',parent=self);return
        if not ids:return
        self.busy=True
        self.run_btn.configure(state='disabled');self.selected_btn.configure(state='disabled')
        def worker():
            for job_id in ids:
                try:
                    self.after(0,lambda ident=job_id:self._log('Starting '+ident))
                    engine.run_job(job_id,progress=lambda s:self.after(0,lambda m=s:self._log(m)))
                except Exception as exc:
                    msg=str(exc)
                    self.after(0,lambda m=msg:self._log('ERROR: '+m))
                self.after(0,lambda ident=job_id:self.refresh(ident))
            self.after(0,self._idle)
        threading.Thread(target=worker,daemon=True).start()

    def _idle(self):
        self.busy=False;self.run_btn.configure(state='normal');self.selected_btn.configure(state='normal')
        self.refresh();self._log('Queue processing stopped. Open drafts in the editor for source review.')

    def run_selected(self):
        jid=self._selection()
        if jid:self._run([jid])

    def run_queue(self):
        ids=[j['id'] for j in reversed(engine.list_jobs()) if j['status'] in ('queued','needs_model','failed')]
        if not ids:messagebox.showinfo('Queue','No new/retryable jobs are queued.',parent=self);return
        self._run(ids)

    def open_draft(self):
        jid=self._selection()
        if not jid:return
        job=engine.get_job(jid)
        if not job.get('manifest'):
            messagebox.showinfo('Not yet drafted','Run this job to generate a script first.',parent=self);return
        if self.on_load:
            try:self.on_load(Path(job['manifest']),jid)
            except Exception as exc:messagebox.showerror('Unable to load script',str(exc),parent=self);return
            self._log('Loaded draft into the editor. Review source evidence in FACT CHECK before final rendering.')
        else:self._open(Path(job['manifest']))

    def open_credits(self):
        jid=self._selection()
        if not jid:return
        job=engine.get_job(jid)
        path=job.get('media_credits','')
        if path and Path(path).exists():self._open(Path(path))
        else:messagebox.showinfo('Media credits','No downloaded Commons media for this job. Original footage can be supplied manually.',parent=self)

    def open_leads(self):
        jid=self._selection()
        if not jid:return
        path=engine.get_job(jid).get('research_leads','')
        if path and Path(path).exists():self._open(Path(path))
        else:messagebox.showinfo('Search leads','Run this job to generate research search links.',parent=self)

    def open_job_folder(self):
        jid=self._selection()
        if jid:self._open(engine.MEDIA_DIR/jid if (engine.MEDIA_DIR/jid).is_dir() else engine.QUEUE)

    def _open(self,path):
        try:
            if sys.platform=='win32':os.startfile(str(path))
            elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
            else:subprocess.Popen(['xdg-open',str(path)])
        except Exception as exc:messagebox.showerror('Unable to open',str(exc),parent=self)
