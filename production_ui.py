#!/usr/bin/env python3
"""Prompt production and persistent queue window for The Crow's Nest Studio."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,scrolledtext,ttk

import production_engine as engine
import update_engine

SOFT_LIGHT=update_engine.load_settings().get('appearance')=='soft_light'
NAVY='#F1F4F4' if SOFT_LIGHT else '#0C121B'
PANEL='#FFFFFF' if SOFT_LIGHT else '#182330'
GOLD='#2F6758' if SOFT_LIGHT else '#D7B47B'
CREAM='#253640' if SOFT_LIGHT else '#EDF2F4'
MUTED='#60747C' if SOFT_LIGHT else '#A1B1BD'
HEADING_BG='#DAE5DF' if SOFT_LIGHT else '#223343'
ACTIVE_BG='#265247' if SOFT_LIGHT else '#EAC68D'
ACTIVE_FG='#FFFFFF' if SOFT_LIGHT else '#10202A'


def open_text_model_setup(parent,*,on_select=None):
    """One-click, user-approved model management; no terminal required."""
    window=tk.Toplevel(parent)
    window.title("Narration Script Model Setup")
    window.geometry("670x460")
    window.minsize(540,385)
    window.configure(bg=NAVY)
    window.transient(parent)
    selection=tk.StringVar(value="")
    state=tk.StringVar(value="Checking installed Ollama models...")
    busy={"value":False}
    tk.Label(window,text="Local script-writing model",bg=NAVY,fg=CREAM,
             font=("Segoe UI",18,"bold")).pack(anchor="w",padx=20,pady=(20,7))
    tk.Label(window,
             text="Studio's research works independently, but writing full scripts "
                  "needs an Ollama text model. Choose one already on your PC, or "
                  "install the recommended smaller model once. No paid credits.",
             bg=NAVY,fg=MUTED,font=("Segoe UI",10),wraplength=610,
             justify="left").pack(anchor="w",padx=20,pady=(0,17))
    tk.Label(window,text="Models installed on your computer",bg=NAVY,fg=CREAM,
             font=("Segoe UI",11,"bold")).pack(anchor="w",padx=20,pady=(0,6))
    combo=ttk.Combobox(window,textvariable=selection,state="readonly")
    combo.pack(fill="x",padx=20,pady=(0,16))
    tk.Label(window,textvariable=state,bg=NAVY,fg=CREAM,
             font=("Segoe UI",10),wraplength=610,justify="left").pack(
                 anchor="w",padx=20,pady=(0,17))
    buttons=tk.Frame(window,bg=NAVY)
    buttons.pack(fill="x",padx=20)
    def handle_models(models):
        combo["values"]=models
        configured=update_engine.load_settings().get("ollama_model","")
        if models:
            selection.set(engine.select_local_model(configured,installed=models))
            state.set(str(len(models))+" installed model(s). Select one and press Use model.")
        else:
            state.set("Ollama is running, but no text model is installed. "
                      "Click Install recommended model.")
    def refresh():
        if busy["value"]:return
        state.set("Checking Ollama...")
        def worker():
            try:
                models=engine.list_local_models()
                window.after(0,lambda:handle_models(models))
            except engine.OllamaSetupError as exc:
                window.after(0,lambda text=str(exc):state.set(text))
        threading.Thread(target=worker,daemon=True).start()
    def choose():
        if busy["value"]:return
        model=selection.get().strip()
        if not model:
            messagebox.showwarning("No installed model",
                "Install a local model first, or refresh the list.",parent=window)
            return
        settings=update_engine.load_settings()
        settings["ollama_model"]=model
        update_engine.save_settings(settings)
        window.destroy()
        if on_select:on_select(model)
    def install():
        if busy["value"]:return
        if not messagebox.askyesno("Download text model?",
                "Install qwen3:4b with Ollama? This is a one-time "
                "multi-gigabyte download to your computer. It is free, "
                "but uses your storage and internet connection.",parent=window):
            return
        busy["value"]=True
        download.configure(state="disabled")
        state.set("Starting model download. Studio will show progress here...")
        def worker():
            try:
                model=engine.pull_local_model(
                    engine.RECOMMENDED_TEXT_MODEL,
                    progress=lambda note:window.after(
                        0,lambda msg=note:state.set(msg)))
                def success():
                    busy["value"]=False
                    download.configure(state="normal")
                    handle_models(engine.list_local_models())
                    selection.set(model)
                    state.set(model+" installed. Click Use model to continue.")
                window.after(0,success)
            except (engine.OllamaSetupError,OSError,ValueError) as exc:
                def failure(msg=str(exc)):
                    busy["value"]=False
                    download.configure(state="normal")
                    state.set(msg)
                window.after(0,failure)
        threading.Thread(target=worker,daemon=True).start()
    ttk.Button(buttons,text="Use selected model",command=choose).pack(
        side="left",padx=(0,9),pady=(0,12))
    ttk.Button(buttons,text="Refresh list",command=refresh).pack(
        side="left",padx=(0,9))
    download=ttk.Button(window,text="Install recommended qwen3:4b",
                        command=install)
    download.pack(anchor="w",padx=20,pady=(0,12))
    ttk.Button(window,text="Get Ollama for Windows",
        command=lambda:webbrowser.open("https://ollama.com/download/windows")).pack(
            anchor="w",padx=20,pady=(0,12))
    refresh()
    return window


class ProductionStudio(tk.Toplevel):
    STYLE_CHOICES={
        'Archival photographs':'archival',
        'Cinematic photo motion':'motion',
        'Hybrid documentary':'hybrid',
        'Animated realism (local AI)':'ai_reenactment',
    }
    def __init__(self,parent,*,on_load=None,default_voice='kokoro:am_onyx'):
        super().__init__(parent)
        self.title("The Crow's Nest | Film Library")
        self.geometry('1060x800')
        self.minsize(710,500)
        self.configure(bg=NAVY)
        self.on_load=on_load
        self.busy=False
        self.notes=tk.StringVar(value='')
        self.minutes=tk.IntVar(value=10)
        self.fmt=tk.StringVar(value='wide')
        self.visual_style=tk.StringVar(value='Archival photographs')
        self.want_full=tk.BooleanVar(value=True)
        self.want_shorts=tk.BooleanVar(value=True)
        self.want_tiktok=tk.BooleanVar(value=True)
        self.output_choice=tk.StringVar(value='Full documentary')
        self.workflow_path=tk.StringVar(value=update_engine.load_settings().get('comfyui_workflow',''))
        self.inbox_dir=tk.StringVar(value=update_engine.load_settings().get('chatgpt_inbox',''))
        self.model=tk.StringVar(value=update_engine.load_settings().get('ollama_model','qwen3:4b'))
        self.voice=tk.StringVar(value=default_voice)
        self.media=tk.BooleanVar(value=True)
        self.start_immediately=tk.BooleanVar(value=True)
        self.state=tk.StringVar(value='Ready for review is the next step after research finishes.')
        style=ttk.Style(self)
        style.configure('Queue.Primary.TButton',font=('Segoe UI',10,'bold'),
                        padding=(17,11),background=GOLD,
                        foreground=ACTIVE_FG,borderwidth=0)
        style.map('Queue.Primary.TButton',
                  background=[('active',ACTIVE_BG)],
                  foreground=[('active',ACTIVE_FG)])
        style.configure('Queue.TNotebook',background=NAVY,borderwidth=0)
        style.configure('Queue.TNotebook.Tab',font=('Segoe UI',11),padding=(20,12),
                        background=PANEL,foreground=CREAM)
        style.map('Queue.TNotebook.Tab',background=[('selected','#48655e')],
                  foreground=[('selected','#ffffff')])
        style.configure('Queue.Treeview',background=PANEL,fieldbackground=PANEL,
                        foreground=CREAM,rowheight=31,font=('Segoe UI',10))
        style.configure('Queue.Treeview.Heading',background=HEADING_BG,
                        foreground=CREAM,font=('Segoe UI',10,'bold'))
        style.map('Queue.Treeview',background=[('selected','#48655e')],
                  foreground=[('selected','#ffffff')])

        header=tk.Frame(self,bg=NAVY,padx=25,pady=21)
        header.pack(fill='x')
        tk.Label(header,text="THE CROW'S NEST   /   PROJECTS",
                 bg=NAVY,fg=GOLD,font=('Segoe UI',9,'bold')).pack(anchor='w')
        tk.Label(header,text='Film library & production queue',bg=NAVY,fg=CREAM,
                 font=('Segoe UI',23,'bold')).pack(anchor='w',pady=(6,5))
        tk.Label(header,text='Return to your drafts, compare formats and review sources. '
                 'Advanced creation and integrations are available on separate pages.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',11),
                 wraplength=930,justify='left').pack(anchor='w')
        self.tabs=ttk.Notebook(self,style='Queue.TNotebook')
        self.tabs.pack(fill='both',expand=True,padx=18,pady=(0,10))

        self._page_scroll_canvases=[]
        self._page_scroll_containers=[]
        def page(title):
            outer=tk.Frame(self.tabs,bg=NAVY)
            self.tabs.add(outer,text=title)
            canvas=tk.Canvas(outer,bg=NAVY,highlightthickness=0,borderwidth=0)
            bar=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview)
            canvas.configure(yscrollcommand=bar.set)
            bar.pack(side='right',fill='y')
            canvas.pack(side='left',fill='both',expand=True)
            content=tk.Frame(canvas,bg=NAVY,padx=18,pady=17)
            win=canvas.create_window((0,0),window=content,anchor='nw')
            content.bind('<Configure>',lambda event,c=canvas:
                         c.configure(scrollregion=c.bbox('all')))
            canvas.bind('<Configure>',lambda event,c=canvas,w=win:
                        c.itemconfigure(w,width=event.width))
            content._scroll_outer=outer
            self._page_scroll_canvases.append(canvas)
            self._page_scroll_containers.append(outer)
            return content
        create=page('ADVANCED CREATE')
        queue=page('FILM LIBRARY')
        inbox=page('INTEGRATIONS')
        self.queue_page=queue._scroll_outer
        self._heading(create,'Advanced production brief',16)
        tk.Label(create,text='The main window is the easiest way to start. Use this page '
                 'when you need special narrator, source-note or model settings.',
                 bg=NAVY,fg=MUTED,wraplength=850,justify='left',
                 font=('Segoe UI',11)).pack(anchor='w',pady=(0,10))
        self.prompt=scrolledtext.ScrolledText(create,height=7,wrap='word',
                  bg=PANEL,fg=CREAM,insertbackground=CREAM,font=('Segoe UI',12),
                  relief='flat',padx=12,pady=11)
        self.prompt.pack(fill='both',expand=True,pady=(0,15))
        tk.Label(create,text='Describe a specific historical topic or military story angle.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w',pady=(0,10))
        basic=tk.Frame(create,bg=NAVY);basic.pack(fill='x',pady=(0,15))
        self._field(basic,'Length (minutes)',self.minutes,values=[1,2,3,5,8,10,12,15,20,30],width=9)
        self._field(basic,'Visual style',self.visual_style,
                    values=list(self.STYLE_CHOICES),width=25)

        deliver=tk.Frame(create,bg=PANEL,padx=14,pady=12)
        deliver.pack(fill='x',pady=(0,14))
        tk.Label(deliver,text='CREATE FROM THE SAME RESEARCH',bg=PANEL,fg=CREAM,
                 font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,7))
        outputs=tk.Frame(deliver,bg=PANEL);outputs.pack(fill='x')
        for label,var in (
            ('Full video • YouTube 16:9',self.want_full),
            ('YouTube Short • vertical 9:16',self.want_shorts),
            ('TikTok • punchy vertical 9:16',self.want_tiktok),
        ):
            tk.Checkbutton(outputs,text=label,variable=var,bg=PANEL,fg=CREAM,
                activeforeground=CREAM,activebackground=PANEL,selectcolor=NAVY,
                font=('Segoe UI',10)).pack(anchor='w',pady=(3,3))

        tk.Label(create,text='Archival uses photos. Motion animates those photos. Hybrid adds branded cards. '
                 'AI reenactment sends a few illustrative shots to YOUR local ComfyUI if configured. '
                 'It never represents generated scenes as archival evidence.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',10),wraplength=875,
                 justify='left').pack(anchor='w',pady=(0,13))
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
        self.add_btn=ttk.Button(controls,text='RESEARCH & BUILD',style='Queue.Primary.TButton',command=self.add_job)
        self.add_btn.pack(side='left',padx=(0,11))
        ttk.Button(controls,text='View production queue',
                   command=lambda:self.tabs.select(self.queue_page)).pack(side='left')
        tk.Label(create,text='New episodes are unverified drafts until you review their evidence.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',10)).pack(anchor='w',pady=(8,0))

        self._heading(queue,'Projects, not a pile of queue entries',16)
        tk.Label(queue,text='Drafts automatically move to Ready for review. '
                 'Open one to continue editing in the main studio; finished films '
                 'remain in your library.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',11),wraplength=880,
                 justify='left').pack(anchor='w',pady=(2,13))
        status_bar=tk.Frame(queue,bg=PANEL,padx=15,pady=13)
        status_bar.pack(fill='x',pady=(0,12))
        tk.Label(status_bar,text='SHOW',bg=PANEL,fg=MUTED,
                 font=('Segoe UI',9,'bold')).pack(side='left',padx=(0,12))
        self.stage_view=tk.StringVar(value='Ready for review')
        self.stage_selector=ttk.Combobox(status_bar,textvariable=self.stage_view,
                 state='readonly',width=24,
                 values=('Ready for review','Needs work','Completed / Library'))
        self.stage_selector.pack(side='left')
        self.stage_selector.bind('<<ComboboxSelected>>',lambda event:self.refresh())
        self.stage_summary=tk.StringVar(value='')
        tk.Label(status_bar,textvariable=self.stage_summary,
                 bg=PANEL,fg=MUTED,font=('Segoe UI',9),
                 anchor='e').pack(side='right',padx=(10,0))
        listing=tk.Frame(queue,bg=NAVY)
        listing.pack(fill='both',expand=True,pady=(0,11))
        self.list=ttk.Treeview(listing,style='Queue.Treeview',
                     columns=('state','duration'),show='tree headings',height=11)
        self.list.heading('#0',text='PRODUCTION')
        self.list.column('#0',width=490)
        self.list.heading('state',text='STAGE')
        self.list.column('state',width=155)
        self.list.heading('duration',text='RUN TIME')
        self.list.column('duration',width=90,anchor='center')
        scroll=ttk.Scrollbar(listing,command=self.list.yview)
        self.list.configure(yscrollcommand=scroll.set)
        self.list.pack(side='left',fill='both',expand=True)
        scroll.pack(side='left',fill='y')
        self.list.bind('<<TreeviewSelect>>',self._sync_primary)
        self.list.bind('<Double-1>',lambda event:self.primary_action())
        action_row=tk.Frame(queue,bg=NAVY)
        action_row.pack(fill='x',pady=(0,12))
        self.primary_btn=ttk.Button(action_row,text='CONTINUE TO REVIEW',
                                   style='Queue.Primary.TButton',
                                   command=self.primary_action)
        self.primary_btn.pack(side='left',padx=(0,12))
        self.run_btn=self.primary_btn
        self.selected_btn=self.primary_btn
        tk.Label(action_row,text='VERSION',bg=NAVY,fg=MUTED,
                 font=('Segoe UI',9,'bold')).pack(side='left',padx=(8,6))
        ttk.Combobox(action_row,textvariable=self.output_choice,
                state='readonly',width=18,
                values=('Full documentary','YouTube Short','TikTok')).pack(side='left')
        actions=tk.Menubutton(action_row,text='Manage  ▾',
                  bg=PANEL,fg=CREAM,activebackground=HEADING_BG,
                  activeforeground=CREAM,relief='flat',
                  font=('Segoe UI',10),padx=12,pady=9,cursor='hand2')
        actions.pack(side='right')
        self.manage_menu=tk.Menu(actions,tearoff=False)
        self.manage_menu.add_command(label='Delete selected queue entry',
                                    command=self.delete_selected)
        self.manage_menu.add_command(label='Clear waiting / failed queue',
                                    command=self.clear_waiting)
        self.manage_menu.add_command(label='Clear completed productions from list',
                                    command=self.clear_completed)
        self.manage_menu.add_separator()
        self.manage_menu.add_command(label='Move selected to library',
                                    command=self.archive_selected)
        self.manage_menu.add_command(label='Restore selected to review',
                                    command=self.restore_selected)
        self.manage_menu.add_separator()
        self.manage_menu.add_command(label='View research sources',
                                    command=self.open_leads)
        self.manage_menu.add_command(label='View image credits',
                                    command=self.open_credits)
        self.manage_menu.add_command(label='Open production files',
                                    command=self.open_job_folder)
        self.manage_menu.add_command(label='Refresh',
                                    command=self.refresh)
        self.manage_menu.add_command(label='Activity log',
                                    command=self.toggle_activity)
        actions.configure(menu=self.manage_menu)
        self.help_line=tk.StringVar(value='Select a production to see the next step.')
        tk.Label(queue,textvariable=self.help_line,bg=NAVY,fg=MUTED,
                 font=('Segoe UI',10),wraplength=870,
                 justify='left').pack(anchor='w',pady=(0,7))
        self.log=scrolledtext.ScrolledText(queue,height=6,wrap='word',
                   bg=PANEL,fg=CREAM,font=('Consolas',10),
                   relief='flat',padx=10,pady=9)
        # The log remains accessible under Manage, but no longer steals the
        # production library's limited visible area.
        self.activity_visible=False
        footer=tk.Frame(self,bg=PANEL,padx=17,pady=12)
        footer.pack(fill='x')
        tk.Label(footer,textvariable=self.state,anchor='w',wraplength=900,
                 justify='left',bg=PANEL,fg=CREAM,
                 font=('Segoe UI',10)).pack(fill='x')
        self._heading(inbox,'Local AI and connected services',16)
        tk.Label(inbox,text='The production screen only asks for models when one is missing. '
                 'All installations and integrations live here.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',11),
                 wraplength=850,justify='left').pack(anchor='w',pady=(0,12))
        ttk.Button(inbox,text='Find / install local writing model',
                   command=self.model_setup).pack(anchor='w',pady=(0,22))
        self._heading(inbox,'Private ChatGPT job inbox',14)
        tk.Label(inbox,text='ChatGPT can place private episode requests in your Drive job inbox. '
                 'Install Google Drive for desktop, then choose its locally synced folder here once. '
                 'Studio scans that folder while it is open and imports new jobs.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',11),wraplength=880,
                 justify='left').pack(anchor='w',pady=(0,17))
        row=tk.Frame(inbox,bg=NAVY);row.pack(fill='x',pady=(0,15))
        ttk.Entry(row,textvariable=self.inbox_dir).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='Choose folder',command=self.choose_inbox).pack(
                side='left',padx=(9,0))
        ttk.Button(inbox,text='Import new ChatGPT jobs now',command=self.scan_inbox).pack(
                anchor='w',pady=(0,15))
        tk.Label(inbox,text='A request can generate an unverified draft automatically. '
                 'You still listen, review claims and media rights, preview the video, '
                 'and explicitly approve publication.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',11),wraplength=880,
                 justify='left').pack(anchor='w',pady=(0,12))
        ttk.Button(inbox,text='View production queue',
                   command=lambda:self.tabs.select(self.queue_page)).pack(anchor='w')
        self._heading(inbox,'Optional: local AI video generation (ComfyUI / Wan 2.2)',13)
        tk.Label(inbox,text='Works with compatible AMD/ROCm or NVIDIA/CUDA hardware '
                 'and a local ComfyUI workflow with a __CROWS_PROMPT__ placeholder. '
                 'Generates illustrative shots, not authentic historical footage.',
                 bg=NAVY,fg=MUTED,font=('Segoe UI',10),wraplength=850,
                 justify='left').pack(anchor='w',pady=(0,7))
        setrow=tk.Frame(inbox,bg=NAVY);setrow.pack(fill='x',pady=(0,8))
        ttk.Entry(setrow,textvariable=self.workflow_path).pack(
            side='left',fill='x',expand=True)
        ttk.Button(setrow,text='Choose ComfyUI workflow',
                   command=self.choose_workflow).pack(side='left',padx=(8,0))
        ttk.Button(inbox,text='Check local AI engine',command=self.check_local_video).pack(
            anchor='w',pady=(0,10))
        self.refresh()
        self.after(30000,self._scan_inbox_timer)

    def _page_mouse_wheel(self,event):
        try:
            if event.widget.winfo_toplevel() is not self:
                return
            idx=self.tabs.index(self.tabs.select())
            canvas=self._page_scroll_canvases[idx]
            outer=self._page_scroll_containers[idx]
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

    def model_setup(self,on_select=None):
        def selected(name):
            self.model.set(name)
            self._log("Text-writing model selected: "+name)
            if on_select:on_select(name)
        return open_text_model_setup(self,on_select=selected)

    def choose_workflow(self):
        file=filedialog.askopenfilename(parent=self,
              title='Choose ComfyUI workflow in API JSON format',
              filetypes=[('API workflow JSON','*.json')])
        if not file:return
        from studio import load_workflow,LocalVideoError
        try:
            load_workflow(Path(file))
            self.workflow_path.set(file)
            settings=update_engine.load_settings()
            settings['comfyui_workflow']=file
            update_engine.save_settings(settings)
            self._log('AI video workflow saved. Generated scenes remain illustrative.')
        except (ValueError,OSError,LocalVideoError) as exc:
            messagebox.showerror('Unsupported workflow',str(exc),parent=self)

    def check_local_video(self):
        from studio import status,LocalVideoError
        try:
            self._log(status())
            messagebox.showinfo('Local video generator',status(),parent=self)
        except LocalVideoError as exc:
            messagebox.showwarning('ComfyUI unavailable',str(exc),parent=self)

    def choose_inbox(self):
        folder=filedialog.askdirectory(parent=self,title='Select locally synced Google Drive job inbox')
        if not folder:return
        self.inbox_dir.set(folder)
        settings=update_engine.load_settings()
        settings['chatgpt_inbox']=folder
        update_engine.save_settings(settings)
        self._log('Private inbox connected: '+folder)
        self.scan_inbox()

    def scan_inbox(self,silent=False):
        folder=Path(self.inbox_dir.get().strip())
        if not str(self.inbox_dir.get()).strip() or not folder.is_dir():
            if not silent:messagebox.showwarning('Inbox folder missing',
                'Choose your locally synced Google Drive job inbox folder first.',parent=self)
            return
        seen={j['id'] for j in engine.list_jobs()}
        ids=[]
        errors=[]
        for file in sorted(folder.glob('*.json'))[:60]:
            try:
                job=engine.import_chatgpt_job(file,source_folder=folder)
                if job.get('removed'):continue
                if job['id'] not in seen:
                    ids.append(job['id'])
                    seen.add(job['id'])
            except (OSError,ValueError,TypeError,KeyError) as exc:
                errors.append(file.name+': '+str(exc))
        if ids:
            self._log('Imported '+str(len(ids))+' new private ChatGPT job(s).')
            self.refresh(ids[-1])
            self.tabs.select(self.queue_page)
            if self.start_immediately.get() and not self.busy:
                self._run(ids)
        elif not silent:self._log('No new ChatGPT jobs in this folder.')
        if errors and not silent:
            messagebox.showwarning('Unrecognized inbox files',
                  '\n'.join(errors[:4]),parent=self)

    def _scan_inbox_timer(self):
        if self.winfo_exists():
            self.scan_inbox(silent=True)
            self.after(30000,self._scan_inbox_timer)

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
        view={'Needs work':'queue','Ready for review':'review',
              'Completed / Library':'archive'}[self.stage_view.get()]
        for item in self.list.get_children():
            self.list.delete(item)
        jobs=engine.list_stage_jobs(view)
        readable={'queued':'Waiting to start','failed':'Needs retry',
                  'needs_model':'Model needed','researching':'Researching',
                  'drafting':'Writing','gathering_media':'Finding imagery',
                  'rendering':'Rendering','awaiting_review':'Review script',
                  'ready':'Ready to render','finished':'Rendered'}
        for job in jobs:
            label='In library' if job.get('archived') else readable.get(job['status'],job['status'])
            self.list.insert('','end',iid=job['id'],text=job['title'][:88],
                    values=(label,str(job['minutes'])+' min'))
        ids=set(self.list.get_children())
        if chosen in ids:
            self.list.selection_set(chosen)
            self.list.focus(chosen)
        elif jobs:
            self.list.selection_set(jobs[0]['id'])
            self.list.focus(jobs[0]['id'])
        counts={key:len(engine.list_stage_jobs(key))
                for key in ('queue','review','archive')}
        self.stage_summary.set(
            f"{counts['queue']} waiting    •    {counts['review']} to review    •    {counts['archive']} in library")
        self._sync_primary()

    def _sync_primary(self,event=None):
        selected=self.list.selection()
        if not selected:
            self.primary_btn.configure(text='NO PROJECT SELECTED',state='disabled')
            self.help_line.set('This stage is empty. New drafts move here automatically.')
            return
        try:
            job=engine.get_job(selected[0])
        except (OSError,ValueError,KeyError):
            self.primary_btn.configure(state='disabled')
            return
        status=job.get('status')
        if self.busy or status in engine.RUNNING_JOB_STATES:
            self.primary_btn.configure(text='IN PROGRESS',state='disabled')
            self.help_line.set(job.get('progress','Working on this production.'))
        elif status=='needs_model':
            self.primary_btn.configure(text='SET UP WRITING MODEL',state='normal')
            self.help_line.set('One-time local Ollama model setup; your research request is preserved.')
        elif status in ('queued','failed'):
            self.primary_btn.configure(text='RUN / RETRY PRODUCTION',state='normal')
            self.help_line.set('Research and drafting run here. The finished draft moves to Ready for review.')
        elif job.get('manifest'):
            self.primary_btn.configure(text='CONTINUE IN MAIN STUDIO',state='normal')
            self.help_line.set('Opens the chosen version in the story editor; no additional pop-up is needed.')
        else:
            self.primary_btn.configure(text='NO DRAFT AVAILABLE',state='disabled')
            self.help_line.set('This production has no stored script.')

    def primary_action(self):
        if self.busy:
            return
        ident=self._selection()
        if not ident:
            return
        job=engine.get_job(ident)
        status=job.get('status')
        if status=='needs_model':
            self.model_setup(on_select=lambda model:self._run([ident]))
        elif status in ('queued','failed'):
            self._run([ident])
        elif status not in engine.RUNNING_JOB_STATES:
            self.open_draft()

    def toggle_activity(self):
        self.activity_visible=not self.activity_visible
        if self.activity_visible:
            self.log.pack(fill='x',pady=(8,0))
        else:
            self.log.pack_forget()

    def delete_selected(self):
        ident=self._selection()
        if not ident:return
        if self.busy:
            messagebox.showwarning('Production running',
                    'Finish active work before deleting a queue entry.',parent=self)
            return
        job=engine.get_job(ident)
        if not messagebox.askyesno(
            'Delete queue entry?',
            'Remove "'+job['title'][:110]+'" from the production lists?\n\n'
            'The saved scripts, research files, audio, imagery and rendered videos '
            'will NOT be deleted. This only removes the tracking entry.',
            parent=self):
            return
        try:
            engine.remove_queue_job(ident)
            self.refresh()
            self._log('Removed queue entry. Original production files were preserved.')
        except (ValueError,OSError) as exc:
            messagebox.showerror('Cannot remove project',str(exc),parent=self)

    def clear_waiting(self):
        if self.busy:
            messagebox.showinfo('Production running','Finish this operation before clearing the queue.',
                                parent=self)
            return
        count=sum(j.get('status') in ('queued','failed','needs_model')
                  for j in engine.list_jobs())
        if not count:
            self._log('Nothing waiting to clear.')
            return
        if not messagebox.askyesno('Clear waiting / failed queue?',
            f'Remove {count} waiting or failed job(s) from the lists?\n\n'
            'No active renders, scripts, sources, audio, or videos will be deleted.',
            parent=self):
            return
        done=engine.clear_pending_queue()
        self.refresh()
        self._log(f'Cleared {done} waiting/failed queue entries. Original files preserved.')

    def clear_completed(self):
        count=sum(j.get('status')=='finished' for j in engine.list_jobs())
        if not count:
            self._log('No completed productions to clear.')
            return
        if not messagebox.askyesno('Clear completed list?',
            f'Hide {count} rendered production(s) from the library list?\n\n'
            'The finished MP4 files, audio and scripts remain saved on your computer.',
            parent=self):
            return
        done=engine.clear_completed_from_queue()
        self.refresh()
        self._log(f'Cleared {done} completed entries. Exported videos remain on disk.')

    def archive_selected(self):
        ident=self._selection()
        if not ident:return
        try:
            engine.archive_job(ident)
            self.stage_view.set('Completed / Library')
            self.refresh(ident)
        except (ValueError,OSError) as exc:
            messagebox.showwarning('Cannot move this production',str(exc),parent=self)

    def restore_selected(self):
        ident=self._selection()
        if not ident:return
        job=engine.restore_job(ident)
        self.stage_view.set('Ready for review' if job['status'] in engine.REVIEW_JOB_STATES
                            else 'Completed / Library')
        self.refresh(ident)


    def choose_notes(self):
        p=filedialog.askopenfilename(parent=self,title='Source notes',filetypes=[('Plain text','*.txt'),('All files','*.*')])
        if p:self.notes.set(p)

    def add_job(self):
        if self.start_immediately.get():
            try:
                self.model.set(engine.select_local_model(self.model.get()))
            except engine.OllamaSetupError as exc:
                self._log(str(exc))
                self.model_setup(on_select=lambda name:self.add_job())
                return
        try:
            deliverables=[key for key,flag in (
                ('full',self.want_full),('shorts',self.want_shorts),('tiktok',self.want_tiktok))
                if flag.get()]
            video_format=('both' if len(deliverables)>1 else
                          'wide' if deliverables==['full'] else 'short')
            j=engine.create_job(self.prompt.get('1.0','end'),
                minutes=self.minutes.get(),fmt=video_format,
                model=self.model.get(),voice=self.voice.get(),notes_file=self.notes.get(),
                auto_media=self.media.get(),visual_style=self.STYLE_CHOICES[self.visual_style.get()],
                deliverables=deliverables)
        except Exception as exc:messagebox.showerror('Invalid production request',str(exc),parent=self);return
        self.refresh(j['id']);self.tabs.select(self.queue_page);self._log('Added '+j['id']+' to the production queue.')
        if self.start_immediately.get():self._run([j['id']])

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
        selections={'Full documentary':'full','YouTube Short':'shorts','TikTok':'tiktok'}
        requested=selections.get(self.output_choice.get(),'full')
        manifests=job.get('variants',{})
        chosen=manifests.get(requested)
        if not chosen:
            names=', '.join(manifests) if manifests else 'default'
            messagebox.showwarning('Version not generated',
                f'This episode has: {names}. Choose a generated output above.',parent=self)
            return
        if self.on_load:
            try:self.on_load(Path(chosen),jid)
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
