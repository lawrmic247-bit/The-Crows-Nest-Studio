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

NAVY='#202a33'; PANEL='#303d49'; GOLD='#9fc5bc'; CREAM='#e0e6e8'; MUTED='#bac7ce'


class ProductionStudio(tk.Toplevel):
    def __init__(self,parent,*,on_load=None,default_voice='kokoro:am_onyx'):
        super().__init__(parent)
        self.title("The Crow's Nest | Episode Queue")
        self.geometry('1010x775')
        self.minsize(770,600)
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
        self.state=tk.StringVar(value='Enter an idea, create an episode, then review it in the editor.')
        style=ttk.Style(self)
        style.configure('Queue.TNotebook',background=NAVY,borderwidth=0)
        style.configure('Queue.TNotebook.Tab',font=('Segoe UI',11),padding=(20,12),
                        background=PANEL,foreground=CREAM)
        style.map('Queue.TNotebook.Tab',background=[('selected','#48655e')],
                  foreground=[('selected','#ffffff')])
        style.configure('Queue.Treeview',background=PANEL,fieldbackground=PANEL,
                        foreground=CREAM,rowheight=31,font=('Segoe UI',10))
        style.configure('Queue.Treeview.Heading',background='#425260',
                        foreground=CREAM,font=('Segoe UI',10,'bold'))
        style.map('Queue.Treeview',background=[('selected','#48655e')],
                  foreground=[('selected','#ffffff')])

        header=tk.Frame(self,bg=NAVY,padx=22,pady=16)
        header.pack(fill='x')
        tk.Label(header,text='Episode production',bg=NAVY,fg=CREAM,
                 font=('Segoe UI',22,'bold')).pack(anchor='w')
        tk.Label(header,text='Create from a prompt  •  Review in the editor  •  Render after fact-check',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',11)).pack(anchor='w',pady=(3,0))
        self.tabs=ttk.Notebook(self,style='Queue.TNotebook')
        self.tabs.pack(fill='both',expand=True,padx=18,pady=(0,10))

        create=tk.Frame(self.tabs,bg=NAVY,padx=18,pady=17)
        queue=tk.Frame(self.tabs,bg=NAVY,padx=18,pady=17)
        self.tabs.add(create,text='1. Create episode')
        self.tabs.add(queue,text='2. Production queue')
        self.queue_page=queue
        self._heading(create,'Describe the episode you want',13)
        tk.Label(create,text='Include the topic, angle, key events, and style. '
                 'The generated script will still require source review.',
                 bg=NAVY,fg=MUTED,wraplength=850,justify='left',
                 font=('Segoe UI',11)).pack(anchor='w',pady=(0,10))
        self.prompt=scrolledtext.ScrolledText(create,height=7,wrap='word',
                  bg=PANEL,fg=CREAM,insertbackground=CREAM,font=('Segoe UI',12),
                  relief='flat',padx=12,pady=11)
        self.prompt.pack(fill='both',expand=True,pady=(0,15))
        self.prompt.insert('1.0',"Explore the history of the crow's nest lookout, from sailing ships to modern naval operations. Explain how responsibilities and equipment changed without inventing events or quotations.")
        basic=tk.Frame(create,bg=NAVY);basic.pack(fill='x',pady=(0,15))
        self._field(basic,'Length (minutes)',self.minutes,values=[1,2,3,5,8,10,12,15,20,30],width=9)
        self._field(basic,'Video shape',self.fmt,values=['short','wide','both'],width=12)

        self.advanced=tk.Frame(create,bg=NAVY)
        self.show_advanced=tk.BooleanVar(value=False)
        ttk.Checkbutton(create,text='Show advanced production settings',
                        variable=self.show_advanced,command=self.toggle_advanced).pack(
                            anchor='w',pady=(0,10))
        self._field(self.advanced,'Ollama model',self.model,width=16)
        self._field(self.advanced,'Narrator / saved profile',self.voice,width=24)
        source=tk.Frame(self.advanced,bg=NAVY)
        source.pack(fill='x',pady=(12,4))
        tk.Label(source,text='Source notes (optional)',bg=NAVY,fg=CREAM,
                 font=('Segoe UI',10)).pack(side='left',padx=(0,12))
        ttk.Entry(source,textvariable=self.notes).pack(side='left',fill='x',expand=True)
        ttk.Button(source,text='Browse',command=self.choose_notes).pack(side='left',padx=(8,0))
        tk.Checkbutton(self.advanced,text='Search for credited archival still images',
             variable=self.media,bg=NAVY,fg=CREAM,selectcolor=PANEL,
             activebackground=NAVY,activeforeground=CREAM).pack(anchor='w',pady=(8,4))
        tk.Checkbutton(self.advanced,text='Run immediately after adding a prompt',
             variable=self.start_immediately,bg=NAVY,fg=CREAM,selectcolor=PANEL,
             activebackground=NAVY,activeforeground=CREAM).pack(anchor='w',pady=(0,8))
        controls=tk.Frame(create,bg=NAVY);controls.pack(fill='x',pady=(8,3))
        self.add_btn=ttk.Button(controls,text='Create episode',command=self.add_job)
        self.add_btn.pack(side='left',padx=(0,11))
        ttk.Button(controls,text='View production queue',
                   command=lambda:self.tabs.select(self.queue_page)).pack(side='left')
        tk.Label(create,text='New episodes are unverified drafts until you review their evidence.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w',pady=(8,0))

        self._heading(queue,'Your episodes',13)
        tk.Label(queue,text='Select an episode to open its draft, view research leads, '
                 'or inspect media credits.',bg=NAVY,fg=MUTED,
                 font=('Segoe UI',11),wraplength=900,justify='left').pack(
                     anchor='w',pady=(0,13))
        listing=tk.Frame(queue,bg=NAVY);listing.pack(fill='both',expand=True)
        self.list=ttk.Treeview(listing,style='Queue.Treeview',
                    columns=('state','duration','created'),show='tree headings',height=9)
        self.list.heading('#0',text='Episode')
        self.list.column('#0',width=375)
        self.list.heading('state',text='Status');self.list.column('state',width=140)
        self.list.heading('duration',text='Target');self.list.column('duration',width=80,anchor='center')
        self.list.heading('created',text='Created (UTC)');self.list.column('created',width=140)
        scroll=ttk.Scrollbar(listing,command=self.list.yview)
        self.list.configure(yscrollcommand=scroll.set)
        self.list.pack(side='left',fill='both',expand=True)
        scroll.pack(side='left',fill='y')
        row=tk.Frame(queue,bg=NAVY);row.pack(fill='x',pady=(12,8))
        ttk.Button(row,text='Open selected draft in editor',
                   command=self.open_draft).pack(side='left',padx=(0,8))
        self.run_btn=ttk.Button(row,text='Run pending',command=self.run_queue)
        self.run_btn.pack(side='left',padx=(0,8))
        self.selected_btn=ttk.Button(row,text='Retry selected',command=self.run_selected)
        self.selected_btn.pack(side='left',padx=(0,8))
        ttk.Button(row,text='Refresh',command=self.refresh).pack(side='left')
        row=tk.Frame(queue,bg=NAVY);row.pack(fill='x',pady=(0,12))
        ttk.Button(row,text='Media credits',command=self.open_credits).pack(side='left',padx=(0,8))
        ttk.Button(row,text='Research leads',command=self.open_leads).pack(side='left',padx=(0,8))
        ttk.Button(row,text='Job folder',command=self.open_job_folder).pack(side='left')
        self.log=scrolledtext.ScrolledText(queue,height=5,wrap='word',
                  bg=PANEL,fg=CREAM,font=('Consolas',10),relief='flat',padx=10,pady=9)
        self.log.pack(fill='x')
        footer=tk.Frame(self,bg=PANEL,padx=17,pady=12)
        footer.pack(fill='x')
        tk.Label(footer,textvariable=self.state,anchor='w',wraplength=900,
                 justify='left',bg=PANEL,fg=CREAM,
                 font=('Segoe UI',10)).pack(fill='x')
        self.refresh()

    def _heading(self,parent,text,size=12):
        tk.Label(parent,text=text,bg=NAVY,fg=CREAM,
                 font=('Segoe UI',size,'bold')).pack(anchor='w',pady=(0,8))

    def toggle_advanced(self):
        if self.show_advanced.get():
            self.advanced.pack(fill='x',pady=(0,12),before=self.add_btn.master)
        else:
            self.advanced.pack_forget()

    def _field(self,parent,label,variable,values=None,width=10):
        f=tk.Frame(parent,bg=NAVY);f.pack(side='left',padx=(0,15))
        tk.Label(f,text=label,bg=NAVY,fg=CREAM,font=('Segoe UI',10,'bold')).pack(anchor='w')
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
        self.refresh(j['id']);self.tabs.select(self.queue_page);self._log('Added '+j['id']+' to the production queue.')
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
