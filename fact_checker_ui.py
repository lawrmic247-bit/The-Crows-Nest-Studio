"""Source ledger and evidence review window for The Crow's Nest Studio."""
from __future__ import annotations
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from fact_checker import (mark_claim, report_markdown, research_url, safe_url,
                          save_report, source_tier, status_summary, sync_report,
                          wiki_candidates)

DARK='#202a33';PANEL='#303d49';GOLD='#9fc5bc';LIGHT='#e0e6e8';GREY='#bac7ce'

class FactCheckDialog(tk.Toplevel):
    def __init__(self,parent,slug:str,title:str,script:str):
        super().__init__(parent)
        self.title(f'Fact Check — {title}')
        self.geometry('1020x760')
        self.minsize(780,590)
        self.configure(bg=DARK)
        style=ttk.Style(self)
        style.configure('Evidence.Treeview',background=PANEL,fieldbackground=PANEL,
                        foreground=LIGHT,font=('Segoe UI',10),rowheight=31)
        style.configure('Evidence.Treeview.Heading',background='#425260',
                        foreground=LIGHT,font=('Segoe UI',11,'bold'))
        style.map('Evidence.Treeview',background=[('selected','#48655e')],
                  foreground=[('selected','#ffffff')])
        self.report=sync_report(slug,title,script)
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
