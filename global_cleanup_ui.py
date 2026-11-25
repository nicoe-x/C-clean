"""Selectable global cleanup suggestions and paged exact-file confirmation."""
import csv
from datetime import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from win11_ui import Button, Panel, round_window

from cleaner import size, save_report
from disk_cleanup import scan_candidates, make_plan, execute_plan, candidate_summary


def format_time(ns):
    try:
        return datetime.fromtimestamp(ns / 1_000_000_000).strftime('%Y-%m-%d %H:%M')
    except (OSError,ValueError,OverflowError):
        return '时间不可用'


def export_plan(path,plan):
    from features import csv_cell
    with open(path,'w',encoding='utf-8-sig',newline='') as stream:
        w=csv.writer(stream)
        w.writerow(('拟删除文件（仅预览，尚未执行）','字节','修改时间','允许的缓存根目录'))
        for f in plan:
            w.writerow((csv_cell(f.path),f.size,format_time(f.modified),csv_cell(f.root)))


def confirm_plan(parent,plan,days):
    dialog=tk.Toplevel(parent)
    dialog.title('清理确认')
    width=min(980, max(760,parent.winfo_screenwidth()-60))
    height=min(650,max(500,parent.winfo_screenheight()-100))
    dialog.geometry(f'{width}x{height}+{max(0,(parent.winfo_screenwidth()-width)//2)}+40')
    dialog.minsize(min(820,width),min(540,height))
    dialog.transient(parent)
    dialog.after_idle(lambda:round_window(dialog))
    answer=[False]
    frame=ttk.Frame(dialog,padding=20)
    frame.pack(fill='both',expand=True)
    ttk.Label(frame,text=f'{len(plan):,} 个文件 · {size(sum(f.size for f in plan))}',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text=f'{days} 天前',style='Hint.TLabel').pack(anchor='w',pady=(5,12))
    footer=ttk.Frame(frame)
    footer.pack(side='bottom',fill='x')
    ttk.Label(footer,text='永久删除，不进入回收站。请先退出相关应用。',style='Hint.TLabel',wraplength=900).pack(anchor='w',pady=(12,8))
    buttons=ttk.Frame(footer)
    buttons.pack(fill='x')
    Button(buttons,text='取消',command=dialog.destroy).pack(side='left')
    def export():
        name=filedialog.asksaveasfilename(parent=dialog,title='导出拟删除文件清单',defaultextension='.csv',initialfile='拟删除缓存清单.csv',filetypes=(('CSV','*.csv'),))
        if name:
            try:
                export_plan(name,plan)
            except OSError as exc:
                messagebox.showerror('导出失败',str(exc),parent=dialog)
    Button(buttons,text='导出清单',command=export).pack(side='left',padx=8)
    def accept():
        answer[0]=True
        dialog.destroy()
    Button(buttons,text='删除',style='Danger.TButton',command=accept).pack(side='right')
    paging=ttk.Frame(frame)
    paging.pack(fill='x',pady=(0,8))
    page=[0]
    pages=max(1,(len(plan)+199)//200)
    note=tk.StringVar()
    prev=Button(paging,text='上一页',command=lambda:render(-1))
    prev.pack(side='left')
    next_button=Button(paging,text='下一页',command=lambda:render(1))
    next_button.pack(side='left',padx=6)
    ttk.Label(paging,textvariable=note).pack(side='left',padx=10)
    panel=Panel(frame,padding=8)
    panel.pack(fill='both',expand=True)
    box=panel.content
    tree=ttk.Treeview(box,columns=('path','size','modified'),show='headings',height=5)
    for key,title,width in (('path','完整文件路径',610),('size','大小',100),('modified','最后修改',150)):
        tree.heading(key,text=title)
        tree.column(key,width=width,minwidth=80,stretch=key=='path')
    sy=ttk.Scrollbar(box,orient='vertical',command=tree.yview)
    sx=ttk.Scrollbar(box,orient='horizontal',command=tree.xview)
    tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
    tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
    box.rowconfigure(0,weight=1);box.columnconfigure(0,weight=1)
    def render(delta=0):
        page[0]=max(0,min(pages-1,page[0]+delta))
        tree.delete(*tree.get_children())
        first=page[0]*200
        for f in plan[first:first+200]:
            tree.insert('','end',values=(str(f.path),size(f.size),format_time(f.modified)))
        note.set(f'{page[0]+1} / {pages}  ·  {first+1}–{min(first+200,len(plan))}')
        prev.configure(state='normal' if page[0] else 'disabled')
        next_button.configure(state='normal' if page[0]+1<pages else 'disabled')
    render()
    tree.bind('<Control-c>',lambda _:copy())
    def copy():
        rows=tree.selection()
        if rows:
            dialog.clipboard_clear();dialog.clipboard_append(tree.item(rows[0],'values')[0])
    dialog.bind('<Escape>',lambda _:dialog.destroy())
    dialog.grab_set()
    parent.wait_window(dialog)
    return answer[0]


class CleanupView(ttk.Frame):
    def __init__(self,parent,owner):
        super().__init__(parent,padding=10)
        self.owner=owner
        self.candidates=[]
        self.selected=set()
        self.valid=False
        self.days=tk.StringVar(value='7')
        self.scanned_days=7
        self.note=tk.StringVar(value='')
        bar=ttk.Frame(self)
        bar.pack(fill='x',pady=(0,8))
        ttk.Label(bar,text='早于').pack(side='left')
        self.age=ttk.Combobox(bar,textvariable=self.days,values=('7','30','90'),state='readonly',width=4)
        self.age.pack(side='left',padx=6)
        self.age.bind('<<ComboboxSelected>>',lambda _:self.invalidate('请刷新'))
        ttk.Label(bar,text='天').pack(side='left')
        self.refresh_button=Button(bar,text='刷新',command=self.refresh_candidates)
        self.refresh_button.pack(side='left',padx=12)
        self.select_button=Button(bar,text='全选推荐项',command=self.select_recommended,state='disabled')
        self.select_button.pack(side='left')
        self.clear_button=Button(bar,text='取消选择',command=self.clear,state='disabled')
        self.clear_button.pack(side='left',padx=6)
        self.clean_button=Button(bar,text='预览清理',command=self.start_clean,style='Accent.TButton',state='disabled')
        self.clean_button.pack(side='right')
        bottom=ttk.Frame(self)
        bottom.pack(side='bottom',fill='x')
        ttk.Label(bottom,textvariable=self.note,style='Hint.TLabel',wraplength=1000).pack(anchor='w',pady=(8,4))
        self.detail=tk.StringVar(value='')
        # Per-item reasons are available through Details only.
        panel=Panel(self,padding=8)
        panel.pack(fill='both',expand=True)
        box=panel.content
        self.tree=ttk.Treeview(box,columns=('check','app','advice','size','files','path'),show='headings',height=5)
        for key,title,width in (('check','',42),('app','应用',140),('advice','建议',100),('size','可清理',110),('files','文件数',80),('path','路径',500)):
            self.tree.heading(key,text=title)
            self.tree.column(key,width=width,minwidth=45,stretch=key=='path')
        sy=ttk.Scrollbar(box,orient='vertical',command=self.tree.yview)
        sx=ttk.Scrollbar(box,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        self.tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        box.columnconfigure(0,weight=1);box.rowconfigure(0,weight=1)
        self.tree.bind('<Button-1>',self.click)
        self.tree.bind('<space>',lambda _:self.choose(self.tree.focus()))
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.show_detail())
        self.tree.bind('<Double-1>',self.details)

    def invalidate(self,message):
        self.valid=False
        self.selected.clear()
        self.note.set(message if len(message)<=18 else '需刷新')
        self.render()

    def apply(self,candidates,days,complete):
        self.candidates=candidates
        self.scanned_days=days
        self.selected.clear()
        self.valid=complete and int(self.days.get())==days
        self.render()
        if not self.valid:
            self.note.set('请刷新')

    def set_busy(self):
        busy=self.owner.busy
        self.age.configure(state='disabled' if busy else 'readonly')
        self.refresh_button.configure(state='disabled' if busy else 'normal')
        enabled=self.valid and not busy
        self.select_button.configure(state='normal' if enabled and any(c.recommended for c in self.candidates) else 'disabled')
        self.clear_button.configure(state='normal' if enabled and self.selected else 'disabled')
        amount=sum(self.candidates[i].size for i in self.selected)
        self.clean_button.configure(state='normal' if enabled and self.selected else 'disabled',text=f'预览清理 · {size(amount)}' if self.selected else '预览清理')

    def render(self):
        focus=self.tree.focus()
        self.tree.delete(*self.tree.get_children())
        for i,c in enumerate(self.candidates):
            marker='☑' if i in self.selected else ('☐' if c.files else '—')
            self.tree.insert('','end',iid=str(i),values=(marker,c.target.app,c.label,size(c.size),len(c.files),str(c.target.path)))
        if focus and self.tree.exists(focus):
            self.tree.focus(focus);self.tree.selection_set(focus)
        if self.valid:
            self.note.set(f'{len(self.candidates)} 个目录 · {size(sum(c.size for c in self.candidates))} · 已选 {len(self.selected)} 项')
        self.set_busy()

    def show_detail(self):
        rows=self.tree.selection()
        if rows and int(rows[0])<len(self.candidates):
            c=self.candidates[int(rows[0])]
            self.detail.set(f'{c.reason}  排除 {c.excluded} 项，读取 / 链接异常 {c.issues} 项。目录：{c.target.path}')

    def details(self,event=None):
        if event is not None and self.tree.identify_column(event.x)=='#1':return 'break'
        rows=self.tree.selection()
        if rows:
            c=self.candidates[int(rows[0])]
            messagebox.showinfo('详情',f'{c.target.app} · {c.label}\n\n{c.reason}\n\n{c.target.path}',parent=self.winfo_toplevel())
        return 'break'

    def choose(self,row):
        if self.owner.busy or not self.valid or not row:
            return 'break'
        i=int(row)
        if self.candidates[i].files:
            self.selected.symmetric_difference_update({i})
            self.tree.focus(row)
            self.render()
        return 'break'

    def click(self,event):
        if self.tree.identify_region(event.x,event.y)=='cell' and self.tree.identify_column(event.x)=='#1':
            return self.choose(self.tree.identify_row(event.y))

    def select_recommended(self):
        if self.valid and not self.owner.busy:
            self.selected={i for i,c in enumerate(self.candidates) if c.recommended}
            self.render()

    def clear(self):
        if not self.owner.busy:
            self.selected.clear();self.render()

    def refresh_candidates(self):
        if self.owner.busy:
            return
        self.owner.cleanup_auto_checked=True
        self.invalidate('检查中')
        self.owner.begin_cleanup_operation('advice')
        days=int(self.days.get())
        def worker():
            try:
                candidates=scan_candidates(days,self.owner.stop,lambda text:self.owner.events.put(('cleanup_status',text)))
                complete=not self.owner.stop.is_set()
                path=save_report({'days':days,'complete':complete,'targets':candidate_summary(candidates)},'disk-cleanup-advice')
                self.owner.events.put(('advice_done',(candidates,days,complete,path)))
            except Exception as exc:
                self.owner.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def start_clean(self):
        if self.owner.busy or not self.valid or not self.selected:
            return
        plan=make_plan([self.candidates[i] for i in sorted(self.selected)])
        if not plan:
            self.invalidate('需刷新')
            return
        if not confirm_plan(self.winfo_toplevel(),plan,self.scanned_days):
            return
        # The tuple contains exactly the files that were shown in the dialog.
        self.owner.begin_cleanup_operation('clean')
        def worker():
            try:
                manifest=save_report({'created_at':datetime.now().isoformat(),'days':self.scanned_days,
                    'confirmed':True,'files':[{'path':str(f.path),'bytes':f.size,'modified_ns':f.modified,
                        'root':str(f.root),'device':f.device,'inode':f.inode} for f in plan]},'disk-cleanup-plan')
                report=execute_plan(plan,self.owner.stop,lambda done,total:self.owner.events.put(('cleanup_status',f'清理已处理 {done:,} / {total:,} 个文件')))
                report['days']=self.scanned_days
                report['preview_files']=len(plan)
                report['manifest']=str(manifest)
                report['created_at']=datetime.now().isoformat()
                path=save_report(report,'disk-cleanup')
                self.owner.events.put(('cleanup_done',(report,path)))
            except Exception as exc:
                self.owner.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
