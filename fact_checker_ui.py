"""Source ledger and evidence review window for The Crow's Nest Studio."""
from __future__ import annotations
import tkinter as tk
import json
import webbrowser
import update_engine
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from fact_checker import (mark_claim, report_markdown, research_url, safe_url,
                          save_report, source_tier, status_summary, sync_report,
                          wiki_candidates)

SOFT_LIGHT=update_engine.load_settings().get('appearance')=='soft_light'
DARK='#F1F4F4' if SOFT_LIGHT else '#0C121B'
PANEL='#FFFFFF' if SOFT_LIGHT else '#182330'
GOLD='#2F6758' if SOFT_LIGHT else '#D7B47B'
LIGHT='#253640' if SOFT_LIGHT else '#EDF2F4'
GREY='#60747C' if SOFT_LIGHT else '#A1B1BD'
HEADING_BG='#DAE5DF' if SOFT_LIGHT else '#223343'

class FactCheckDialog(tk.Toplevel):
    def __init__(self,parent,slug:str,title:str,script:str,source_leads:Path|None=None):
        super().__init__(parent)
        self.title(f"The Crow's Nest | Editorial Clearance — {title}")
        self.geometry('1020x760')
        self.minsize(780,590)
        self.configure(bg=DARK)
        style=ttk.Style(self)
        style.configure('Evidence.Treeview',background=PANEL,fieldbackground=PANEL,
                        foreground=LIGHT,font=('Segoe UI',10),rowheight=31)
        style.configure('Evidence.Treeview.Heading',background=HEADING_BG,
                        foreground=LIGHT,font=('Segoe UI',11,'bold'))
        style.map('Evidence.Treeview',background=[('selected','#2E4C53')],
                  foreground=[('selected','#ffffff')])
        self.report=sync_report(slug,title,script)
        self.source_leads=Path(source_leads) if source_leads else None
        self.selected=None
        self.status_var=tk.StringVar(value='unreviewed')
        self.url_var=tk.StringVar()
        self.confirm=tk.BooleanVar(value=False)
        self.summary=tk.StringVar()
        head=tk.Frame(self,bg=DARK,padx=18,pady=14);head.pack(fill='x')
        tk.Label(head,text='Review facts & sources',bg=DARK,fg=LIGHT,
                 font=('Segoe UI',21,'bold')).pack(anchor='w')
        tk.Label(head,text='Research leads are NOT proof. Compare each claim with original sources; disputed claims block production.',
                 bg=DARK,fg=GREY,font=('Segoe UI',10),wraplength=925,justify='left').pack(anchor='w')
        tk.Label(head,textvariable=self.summary,bg=DARK,fg=LIGHT,
                 font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(8,0))

        pane=tk.PanedWindow(self,orient='vertical',sashrelief='flat',bg=DARK)
        pane.pack(fill='both',expand=True,padx=18,pady=(0,8))
        top=tk.Frame(pane,bg=PANEL)
        self.table=ttk.Treeview(top,columns=('risk','status','claim'),show='headings',height=8,style='Evidence.Treeview')
        for key,width in [('risk',90),('status',150),('claim',700)]:
            self.table.heading(key,text=key.upper())
            self.table.column(key,width=width,stretch=(key=='claim'))
        vs=ttk.Scrollbar(top,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=vs.set)
        vs.pack(side='right',fill='y');self.table.pack(side='left',fill='both',expand=True)
        self.table.bind('<<TreeviewSelect>>',self.select_claim)
        pane.add(top,minsize=135)

        bottom=tk.Frame(pane,bg=DARK)
        row=tk.Frame(bottom,bg=DARK);row.pack(fill='x',pady=(7,4))
        self.current=tk.StringVar(value='Select a statement above')
        tk.Label(row,textvariable=self.current,bg=DARK,fg=LIGHT,font=('Segoe UI',10,'bold'),
                 wraplength=900,justify='left').pack(anchor='w')
        form=tk.Frame(bottom,bg=DARK);form.pack(fill='both',expand=True)
        tk.Label(form,text='VERDICT',bg=DARK,fg=GOLD).grid(row=0,column=0,sticky='w',pady=4)
        self.status_box=ttk.Combobox(form,textvariable=self.status_var,state='readonly',
                                    values=['unreviewed','supported','disputed','needs_correction','nonfactual'],width=24)
        self.status_box.grid(row=0,column=1,sticky='w',pady=4)
        tk.Label(form,text='SOURCE HTTPS URL',bg=DARK,fg=GOLD).grid(row=1,column=0,sticky='w',pady=4)
        self.url_entry=ttk.Entry(form,textvariable=self.url_var)
        self.url_entry.grid(row=1,column=1,columnspan=4,sticky='ew',pady=4)
        self.source_type=tk.StringVar(value='')
        tk.Label(form,textvariable=self.source_type,bg=DARK,fg=GREY).grid(row=2,column=1,columnspan=4,sticky='w')
        self.url_var.trace_add('write',lambda *_: self.source_type.set(source_tier(self.url_var.get()) if self.url_var.get() else ''))
        tk.Label(form,text='EXACT SUPPORTING EXCERPT',bg=DARK,fg=GOLD).grid(row=3,column=0,sticky='nw',pady=4)
        self.quote=scrolledtext.ScrolledText(form,height=4,wrap='word',bg=PANEL,fg=LIGHT,insertbackground=LIGHT,font=('Segoe UI',11),padx=8,pady=7)
        self.quote.grid(row=3,column=1,columnspan=4,sticky='nsew',pady=4)
        tk.Label(form,text='NOTES / CONTEXT',bg=DARK,fg=GOLD).grid(row=4,column=0,sticky='nw',pady=4)
        self.notes=scrolledtext.ScrolledText(form,height=3,wrap='word',bg=PANEL,fg=LIGHT,insertbackground=LIGHT)
        self.notes.grid(row=4,column=1,columnspan=4,sticky='nsew',pady=4)
        ttk.Checkbutton(form,text='I checked the original evidence against this statement (not just its wording)',
                        variable=self.confirm).grid(row=5,column=1,columnspan=4,sticky='w',pady=(4,7))
        form.columnconfigure(1,weight=1);form.rowconfigure(3,weight=1);form.rowconfigure(4,weight=1)
        pane.add(bottom,minsize=280)

        foot=tk.Frame(self,bg=PANEL,padx=16,pady=9);foot.pack(fill='x')
        tk.Button(foot,text='Save claim review',command=self.save_claim,bg=GOLD,fg=DARK,padx=12,pady=7,
                  relief='flat',font=('Segoe UI',10,'bold')).pack(side='left',padx=(0,7))
        ttk.Button(foot,text='Discovered sources',command=self.open_research_sources).pack(side='left',padx=3)
        ttk.Button(foot,text='Find official sources',command=lambda:self.research('official')).pack(side='left',padx=3)
        ttk.Button(foot,text='Find other sources',command=lambda:self.research('other')).pack(side='left',padx=3)
        ttk.Button(foot,text='Export source report',command=self.export).pack(side='left',padx=3)
        ttk.Button(foot,text='Close',command=self.destroy).pack(side='right')
        self.refresh()
        if self.report['claims']:
            self.table.selection_set('0');self.table.focus('0');self.select_claim()
        self.transient(parent)

    def refresh(self):
        current=self.table.selection()
        self.table.delete(*self.table.get_children())
        for idx,row in enumerate(self.report['claims']):
            from fact_checker import row_ready
            status='CLEARED' if row_ready(row) else row['status'].replace('_',' ').upper()
            self.table.insert('', 'end',iid=str(idx),values=(row['priority'],status,row['text']))
        passed,total,remaining=status_summary(self.report)
        self.summary.set(f'Cleared {passed} / {total} statements  •  {remaining} require review before final render')
        if current and current[0] in self.table.get_children():self.table.selection_set(current[0])

    def select_claim(self,event=None):
        selection=self.table.selection()
        if not selection:return
        idx=int(selection[0]);self.selected=idx
        row=self.report['claims'][idx]
        self.current.set(f'{idx+1}. {row["text"]}\nReview priority: {row["priority"]}; flags: {", ".join(row["flags"]) or "general factual statement"}')
        self.status_var.set(row['status'])
        self.url_var.set(row.get('source_url',''))
        self.quote.delete('1.0','end');self.quote.insert('1.0',row.get('source_quote',''))
        self.notes.delete('1.0','end');self.notes.insert('1.0',row.get('review_notes',''))
        self.confirm.set(bool(row.get('reviewer_confirmed',False)))

    def save_claim(self):
        if self.selected is None:return
        row=self.report['claims'][self.selected]
        try:
            mark_claim(row,status=self.status_var.get(),source_url=self.url_var.get(),
                       source_quote=self.quote.get('1.0','end').strip(),
                       review_notes=self.notes.get('1.0','end').strip(),
                       reviewer_confirmed=self.confirm.get())
            save_report(self.report)
        except ValueError as error:
            messagebox.showwarning('Evidence incomplete',str(error),parent=self);return
        self.refresh()
        if self.selected+1<len(self.report['claims']):
            self.table.selection_set(str(self.selected+1))
            self.table.see(str(self.selected+1))
            self.select_claim()
        else:
            self.select_claim()
            ready,total,_=status_summary(self.report)
            if ready==total:
                messagebox.showinfo('Source review complete',
                    'Every claim has a source-led review or an explained editorial exemption. Recheck new edits before rendering.',
                    parent=self)

    def open_research_sources(self):
        """Show source-discovery results without implying they verify a claim."""
        if self.source_leads is None or not self.source_leads.is_file():
            messagebox.showinfo('Research leads not found',
                'No automatic source discovery exists for this script. '
                'Use Find official sources to research the selected claim.',parent=self)
            return
        try:
            data=json.loads(self.source_leads.read_text(encoding='utf-8'))
            rows=data.get('retrieved_sources',[])
            if not isinstance(rows,list):raise ValueError('Invalid source list')
            rows=[r for r in rows if isinstance(r,dict) and safe_url(str(r.get('url','')))]
        except (OSError,ValueError,TypeError) as exc:
            messagebox.showwarning('Cannot read source records',str(exc),parent=self)
            return
        if not rows:
            messagebox.showinfo('No retrieved sources',
                'Automatic research did not return source records. '
                'Use Find official sources and review the original pages.',parent=self)
            return
        viewer=tk.Toplevel(self)
        viewer.title('Research source leads — not verified')
        viewer.geometry('830x610')
        viewer.minsize(620,450)
        viewer.configure(bg=DARK)
        tk.Label(viewer,text='Research leads to inspect',bg=DARK,fg=LIGHT,
                 font=('Segoe UI',16,'bold')).pack(anchor='w',padx=16,pady=(14,4))
        tk.Label(viewer,text='These links came from public research catalogs. '
                 'None automatically verifies a claim; open the original document '
                 'and check the exact wording before approving it.',
                 bg=DARK,fg=GREY,font=('Segoe UI',10),wraplength=770,
                 justify='left').pack(anchor='w',padx=16,pady=(0,12))
        listing=tk.Frame(viewer,bg=DARK)
        listing.pack(fill='both',expand=True,padx=16,pady=(0,10))
        source_list=tk.Listbox(listing,exportselection=False,height=10,
                   bg=PANEL,fg=LIGHT,selectbackground=GOLD,
                   selectforeground=DARK,font=('Segoe UI',11))
        bar=ttk.Scrollbar(listing,orient='vertical',command=source_list.yview)
        source_list.configure(yscrollcommand=bar.set)
        bar.pack(side='right',fill='y')
        source_list.pack(side='left',fill='both',expand=True)
        for source in rows:
            source_list.insert('end',f"{source.get('publisher','Source')}: "
                               f"{str(source.get('title',''))[:130]}")
        current_url=tk.StringVar()
        detail=tk.Text(viewer,height=6,wrap='word',bg=PANEL,fg=LIGHT,
                       relief='flat',padx=10,pady=9,font=('Segoe UI',10))
        detail.pack(fill='x',padx=16,pady=(0,10))
        detail.configure(state='disabled')
        def selected():
            if not source_list.curselection():return None
            item=rows[int(source_list.curselection()[0])]
            current_url.set(str(item['url']))
            detail.configure(state='normal')
            detail.delete('1.0','end')
            detail.insert('1.0',str(item.get('excerpt') or
                          'No summary available. Inspect the original catalog page.'))
            detail.configure(state='disabled')
            return item
        def open_source(event=None):
            item=selected()
            if item:webbrowser.open(item['url'])
        def use_url():
            item=selected()
            if not item:return
            self.url_var.set(item['url'])
            self.confirm.set(False)
            viewer.destroy()
        source_list.bind('<<ListboxSelect>>',lambda e:selected())
        source_list.bind('<Double-Button-1>',open_source)
        buttons=tk.Frame(viewer,bg=DARK);buttons.pack(fill='x',padx=16,pady=(0,13))
        ttk.Button(buttons,text='Open source page',command=open_source).pack(side='left',padx=(0,9))
        ttk.Button(buttons,text='Use URL for selected claim',command=use_url).pack(side='left')
        ttk.Button(buttons,text='Close',command=viewer.destroy).pack(side='right')
        source_list.selection_set(0);selected()
        viewer.transient(self)

    def research(self,kind):
        if self.selected is None:return
        claim=self.report['claims'][self.selected]['text']
        webbrowser.open(research_url(claim,kind))
        # Results are not inserted as proof. User explicitly reviews linked evidence.

    def export(self):
        save_report(self.report)
        path=Path(__file__).resolve().parent/'exports'/f'{self.report["slug"]}_fact_check.md'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(report_markdown(self.report),encoding='utf-8')
        messagebox.showinfo('Source report exported',str(path),parent=self)


class InlineFactReview(tk.Frame):
    """The evidence desk inside Step 2; never opens a second application window.

    Source-discovery items are leads, not proof. The original clearance
    requirements in fact_checker.py remain authoritative.
    """
    def __init__(self,parent,*,on_saved=None):
        super().__init__(parent,bg=DARK)
        self.on_saved=on_saved
        self.report=None
        self.slug=None
        self.source_leads=None
        self.selection=None
        self.verdict=tk.StringVar(value='unreviewed')
        self.source=tk.StringVar()
        self.confirm=tk.BooleanVar(value=False)
        self.summary=tk.StringVar(value='Load a researched documentary to begin.')
        title=tk.Frame(self,bg=DARK)
        title.pack(fill='x',pady=(12,8))
        tk.Label(title,text='EVIDENCE DESK',bg=DARK,fg=GOLD,
                 font=('Segoe UI',10,'bold')).pack(anchor='w')
        tk.Label(title,text='Verify every claim before narration',
                 bg=DARK,fg=LIGHT,font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(4,3))
        tk.Label(title,textvariable=self.summary,bg=DARK,fg=GREY,
                 font=('Segoe UI',10),wraplength=720,justify='left').pack(anchor='w')
        listbox=tk.Frame(self,bg=DARK)
        listbox.pack(fill='x',pady=(0,8))
        self.claims=ttk.Treeview(listbox,columns=('status','claim'),
                      show='headings',height=6,style='Evidence.Treeview')
        self.claims.heading('status',text='REVIEW')
        self.claims.heading('claim',text='CLAIM')
        self.claims.column('status',width=145,stretch=False)
        self.claims.column('claim',width=600,stretch=True)
        scroll=ttk.Scrollbar(listbox,orient='vertical',command=self.claims.yview)
        self.claims.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.claims.pack(fill='x',expand=True)
        self.claims.bind('<<TreeviewSelect>>',self._select)
        form=tk.Frame(self,bg=DARK)
        form.pack(fill='x')
        form.columnconfigure(1,weight=1)
        tk.Label(form,text='VERDICT',fg=GOLD,bg=DARK,
                 font=('Segoe UI',9,'bold')).grid(row=0,column=0,sticky='w',padx=(0,12),pady=5)
        ttk.Combobox(form,textvariable=self.verdict,
             values=('unreviewed','supported','disputed','needs_correction','nonfactual'),
             state='readonly',width=20).grid(row=0,column=1,sticky='w',pady=5)
        tk.Label(form,text='SOURCE URL',fg=GOLD,bg=DARK,
                 font=('Segoe UI',9,'bold')).grid(row=1,column=0,sticky='w',padx=(0,12),pady=5)
        ttk.Entry(form,textvariable=self.source).grid(row=1,column=1,sticky='ew',pady=5)
        tk.Label(form,text='EXACT SUPPORTING EXCERPT',fg=GOLD,bg=DARK,
                 font=('Segoe UI',9,'bold')).grid(row=2,column=0,sticky='nw',padx=(0,12),pady=5)
        self.quote=scrolledtext.ScrolledText(form,height=3,wrap='word',bg=PANEL,fg=LIGHT,
                    insertbackground=LIGHT,font=('Segoe UI',10),padx=8,pady=7)
        self.quote.grid(row=2,column=1,sticky='ew',pady=5)
        tk.Label(form,text='NOTES',fg=GOLD,bg=DARK,
                 font=('Segoe UI',9,'bold')).grid(row=3,column=0,sticky='nw',padx=(0,12),pady=5)
        self.notes=scrolledtext.ScrolledText(form,height=2,wrap='word',bg=PANEL,fg=LIGHT,
                    insertbackground=LIGHT,font=('Segoe UI',10),padx=8,pady=7)
        self.notes.grid(row=3,column=1,sticky='ew',pady=5)
        ttk.Checkbutton(form,
             text='I checked the underlying source against this exact statement',
             variable=self.confirm).grid(row=4,column=1,sticky='w',pady=(4,9))
        actions=tk.Frame(self,bg=DARK)
        actions.pack(fill='x',pady=(4,12))
        ttk.Button(actions,text='Save evidence & next',
                   command=self.save_selected).pack(side='left',padx=(0,9))
        ttk.Button(actions,text='Find primary source',
                   command=self.search_official).pack(side='left',padx=(0,9))
        self.source_picker=tk.StringVar()
        self.leads=ttk.Combobox(self,textvariable=self.source_picker,
                    state='readonly',values=[],height=12)
        tk.Label(self,text='RESEARCH LEADS — OPEN THE ORIGINAL SOURCE, THEN VERIFY ITS CLAIMS',
                 bg=DARK,fg=GREY,font=('Segoe UI',9,'bold')).pack(anchor='w',pady=(5,3))
        self.leads.pack(fill='x',pady=(0,7))
        ttk.Button(self,text='Open selected source in browser',
                   command=self.open_source).pack(anchor='w',pady=(0,14))
        self._lead_urls=[]

    def load(self,slug:str,title:str,script:str,source_leads:Path|None=None):
        self.slug=slug
        self.report=sync_report(slug,title,script)
        self.source_leads=Path(source_leads) if source_leads else None
        self.claims.delete(*self.claims.get_children())
        from fact_checker import row_ready
        for index,row in enumerate(self.report['claims']):
            label='CLEARED' if row_ready(row) else row['status'].replace('_',' ').upper()
            self.claims.insert('','end',iid=str(index),
                               values=(label,row['text'][:420]))
        cleared,total,missing=status_summary(self.report)
        self.summary.set(f'{cleared} of {total} claims cleared • {missing} need supporting review')
        self._lead_urls=[]
        names=[]
        if self.source_leads and self.source_leads.is_file():
            try:
                records=json.loads(self.source_leads.read_text(encoding='utf-8'))
                for row in records.get('retrieved_sources',[])[:60]:
                    if isinstance(row,dict) and safe_url(str(row.get('url',''))):
                        self._lead_urls.append(str(row['url']))
                        names.append((str(row.get('publisher','Source'))+' — '+
                                     str(row.get('title',''))[:115]))
            except (OSError,ValueError,TypeError):
                pass
        self.leads.configure(values=names)
        self.source_picker.set(names[0] if names else 'No automatic leads; search official sources')
        if self.report['claims']:
            self.claims.selection_set('0')
            self._select()

    def _select(self,event=None):
        selection=self.claims.selection()
        if not selection or not self.report:return
        self.selection=int(selection[0])
        row=self.report['claims'][self.selection]
        self.verdict.set(row.get('status','unreviewed'))
        self.source.set(row.get('source_url',''))
        self.quote.delete('1.0','end')
        self.quote.insert('1.0',row.get('source_quote',''))
        self.notes.delete('1.0','end')
        self.notes.insert('1.0',row.get('review_notes',''))
        self.confirm.set(bool(row.get('reviewer_confirmed',False)))

    def save_selected(self):
        if self.report is None or self.selection is None:
            return
        row=self.report['claims'][self.selection]
        try:
            mark_claim(row,status=self.verdict.get(),source_url=self.source.get(),
                       source_quote=self.quote.get('1.0','end').strip(),
                       review_notes=self.notes.get('1.0','end').strip(),
                       reviewer_confirmed=self.confirm.get())
            save_report(self.report)
        except ValueError as exc:
            messagebox.showwarning('Evidence incomplete',str(exc),parent=self)
            return
        index=self.selection
        self.load(self.report['slug'],self.report['title'],
                  '\n\n'.join(x['text'] for x in self.report['claims']),
                  source_leads=self.source_leads)
        if index+1<len(self.report['claims']):
            self.claims.selection_set(str(index+1))
            self.claims.see(str(index+1))
            self._select()
        if self.on_saved:self.on_saved()

    def search_official(self):
        if self.report is None or self.selection is None:return
        webbrowser.open(research_url(self.report['claims'][self.selection]['text'],'official'))

    def open_source(self):
        index=self.leads.current()
        if 0<=index<len(self._lead_urls):
            webbrowser.open(self._lead_urls[index])
            self.source.set(self._lead_urls[index])
            self.confirm.set(False)
