"""C: analysis view, with a separate allowlisted cleanup workflow."""
from collections import defaultdict
from datetime import datetime
import csv
import html
import os
from pathlib import Path
import queue
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from win11_ui import Button, Panel, round_window

from cleaner import size, save_report
from disk_scan import analyze, serialize
from disk_cleanup import scan_candidates, path_advice, candidate_summary
from global_cleanup_ui import CleanupView


def display_time(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
    except (OSError, ValueError, OverflowError):
        return '时间不可用'


def export_disk(path, result, candidates=(), days=7, selected=(), cleanup_valid=False):
    path = Path(path)
    if path.suffix.lower() == '.csv':
        from features import csv_cell
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            w = csv.writer(stream)
            w.writerow(('类型', '路径 / 扩展名', '逻辑字节', '文件数', '跳过项', '完整扫描', '此目录已尝试扫描', '建议'))
            for n in result.folders.values():
                w.writerow(('目录（含子目录，勿相加）', csv_cell(n.path), n.size, n.files, n.skipped, not result.cancelled and not result.stale, n.scanned, path_advice(n.path,candidates)))
            for f in result.largest:
                w.writerow(('大文件', csv_cell(f['path']), f['size'], 1, 0, not result.cancelled and not result.stale, '',path_advice(f['path'],candidates)))
            for ext, data in result.extensions.items():
                w.writerow(('文件类型', csv_cell(ext), data['size'], data['files'], 0, not result.cancelled and not result.stale, '', '仅统计，不能按扩展名批量删除'))
            for row in result.issues:
                w.writerow(('跳过项样本：' + row['reason'], csv_cell(row['path']), '', '', '', not result.cancelled and not result.stale, '', '不参与清理'))
            for i,c in enumerate(candidates):
                w.writerow(('白名单缓存建议（非已删除）',csv_cell(c.target.path),c.size,len(c.files),c.issues,cleanup_valid,'',f'{c.label} · {days} 天前 · {"已选" if i in selected else "未选"} · {c.reason}'))
    elif path.suffix.lower() == '.html':
        esc = lambda x: html.escape(str(x), quote=True)
        def table(headers, rows):
            return '<table><thead><tr>' + ''.join(f'<th>{esc(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table>'
        root_children = sorted((n for n in result.folders.values() if n.parent == str(result.root)), key=lambda n:n.size, reverse=True)
        folders = table(('目录', '逻辑大小（含子目录）', '文件数', '跳过项','建议'), ((n.path,size(n.size) if n.scanned else '未扫描',n.files,n.skipped,path_advice(n.path,candidates)) for n in root_children))
        large = table(('大文件路径', '大小', '修改时间','建议'), ((f['path'],size(f['size']),display_time(f['modified']),path_advice(f['path'],candidates)) for f in result.largest))
        extensions = table(('扩展名', '逻辑大小', '文件数'), ((ext,size(d['size']),d['files']) for ext,d in sorted(result.extensions.items(),key=lambda x:x[1]['size'],reverse=True)))
        issues = table(('路径', '原因', '详情'), ((r['path'],r['reason'],r['detail']) for r in result.issues))
        suggestions = table(('允许的缓存目录','建议','原因 / 影响','符合范围','选择'),((c.target.path,c.label,c.reason,size(c.size),'已选' if i in selected else '未选') for i,c in enumerate(candidates)))
        path.write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>C 盘空间分析</title><style>body{{font:14px system-ui,"Microsoft YaHei",sans-serif;background:#f3f6fb;color:#17263c;padding:32px}}main{{max-width:1400px;margin:auto}}table{{width:100%;border-collapse:collapse;background:white;margin-bottom:32px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #e3eaf4;overflow-wrap:anywhere}}th{{background:#e7eef8}}p{{line-height:1.8;color:#64748b}}.total{{font-size:28px;font-weight:bold}}</style><main><h1>C 盘全局空间分析</h1><p>{datetime.now():%Y-%m-%d %H:%M} · {"清理前旧结果，请重新扫描" if result.stale else ("扫描已停止，结果不完整" if result.cancelled else "扫描完成")} · 只读分析</p><div class="total">{esc(size(result.total))} · {result.files:,} 个文件 · {len(result.folders):,} 个目录</div><p>文件逻辑大小与磁盘实际已用空间不同。硬链接仅计入首次遇到的路径；目录别名和重解析点跳过。无法读取的目录未提权访问，跳过共 {sum(result.skip_counts.values()):,} 项。目录大小包含子目录，不能逐行相加。目录和大文件保留，仅独立白名单缓存可在预览确认后清理。</p><h2>白名单缓存清理建议（非删除记录）</h2><p>{days} 天前 · {"建议检查完整" if cleanup_valid else "建议未检查完成或已失效，不能据此执行清理"}</p>{suggestions}<h2>根目录下的目录分布</h2>{folders}<h2>大文件 Top {len(result.largest)}</h2>{large}<h2>文件类型</h2>{extensions}<h2>跳过项（最多 500 条样本）</h2>{issues}</main></html>''', encoding='utf-8')
    else:
        raise ValueError('请选择 .html 或 .csv 格式')


class DiskPanel(ttk.Frame):
    def __init__(self, parent, switch_agent, on_cleaned=None):
        super().__init__(parent, padding=(20,14,20,12))
        self.result = None
        self.on_cleaned=on_cleaned
        self.busy = False
        self.operation='idle'
        self.cleanup_auto_checked=False
        self.stop = threading.Event()
        self.events = queue.Queue()
        self.current = ''
        self.folder_children = defaultdict(list)
        self.report_path = None
        self.row_paths = {}
        self.status = tk.StringVar(value='就绪')
        self.root_path = Path('C:/')
        cards = ttk.Frame(self)
        cards.pack(fill='x')
        self.metrics = []
        for i,title in enumerate(('占用','文件','目录','跳过')):
            card = Panel(cards,height=88,padding=14)
            card.grid(row=0,column=i,sticky='nsew',padx=(0 if i==0 else 12,0))
            cards.columnconfigure(i,weight=1,uniform='disk')
            tk.Label(card.content,text=title,bg='white',fg='#64748b',font=('Microsoft YaHei UI',9)).pack(anchor='w')
            value = tk.Label(card.content,text='—',bg='white',fg='#293245',font=('Segoe UI',22,'bold'))
            value.pack(anchor='w')
            self.metrics.append(value)
        bar = ttk.Frame(self)
        bar.pack(fill='x',pady=12)
        self.scan_button = Button(bar,text='扫描',style='Accent.TButton',command=self.start_scan)
        self.scan_button.pack(side='left')
        self.stop_button = Button(bar,text='停止',command=self.stop.set,state='disabled')
        self.stop_button.pack(side='left',padx=8)
        self.export_button = Button(bar,text='导出',command=self.export,state='disabled')
        self.export_button.pack(side='right')
        self.log_button=Button(bar,text='记录',command=self.open_log,state='disabled')
        self.log_button.pack(side='right',padx=6)
        Button(bar,text='存储设置',command=self.storage_settings).pack(side='right',padx=8)
        footer=ttk.Frame(self)
        footer.pack(side='bottom',fill='x')
        progress_wrap=ttk.Frame(footer,height=4)
        progress_wrap.pack(fill='x')
        progress_wrap.pack_propagate(False)
        self.progress=ttk.Progressbar(progress_wrap,mode='indeterminate')
        self.progress.pack(fill='both',expand=True)
        self.status_label=ttk.Label(footer,textvariable=self.status,style='Hint.TLabel',wraplength=980)
        self.status_label.pack(anchor='w',pady=(6,0))
        self.notebook=ttk.Notebook(self)
        self.notebook.pack(fill='both',expand=True)
        self.directory_page=ttk.Frame(self.notebook,padding=10)
        self.notebook.add(self.directory_page,text='  目录  ')
        location=ttk.Frame(self.directory_page)
        location.pack(fill='x',pady=(0,8))
        self.up_button=Button(location,text='↑',command=self.up)
        self.up_button.pack(side='left')
        self.breadcrumb=tk.StringVar(value='C:\\')
        ttk.Label(location,textvariable=self.breadcrumb).pack(side='left',padx=12)
        self.folder_tree=self.make_tree(self.directory_page,('name','size','share','files','skip','advice'),('名称','大小','占比','文件','跳过','建议'),(300,120,130,90,80,210))
        self.folder_tree.bind('<Double-1>',self.drill)
        self.file_tree=self.tab('  大文件  ',('size','modified','advice','path'),('大小','修改时间','建议','路径'),(120,140,210,600))
        self.type_tree=self.tab('  类型  ',('ext','size','files'),('类型','大小','文件'),(450,200,200))
        self.issue_tree=self.tab('  跳过  ',('reason','path','detail'),('原因','路径','详情'),(200,520,300))
        self.issue_summary=ttk.Label(self.issue_tree.page,text='',style='Hint.TLabel',wraplength=1000)
        self.issue_summary.pack(fill='x',before=self.issue_tree.container,pady=(0,8))
        self.cleanup=CleanupView(self.notebook,self)
        self.notebook.add(self.cleanup,text='  清理  ')
        for tree in (self.folder_tree,self.file_tree,self.issue_tree):
            tree.bind('<Button-3>',lambda event,t=tree:self.menu(event,t))
        self.file_tree.bind('<Double-1>',lambda _:self.reveal_selected(self.file_tree))
        self.notebook.bind('<<NotebookTabChanged>>',self.on_tab)
        self.after(100,self.poll)

    def on_tab(self,_=None):
        if (self.notebook.select()==str(self.cleanup) and not self.busy
                and not self.cleanup.valid and not self.cleanup_auto_checked):
            self.cleanup.refresh_candidates()

    def make_tree(self,parent,columns,titles,widths):
        panel=Panel(parent,padding=8)
        panel.pack(fill='both',expand=True)
        box=panel.content
        tree=ttk.Treeview(box,columns=columns,show='headings',height=5)
        for col,title,width in zip(columns,titles,widths):
            tree.heading(col,text=title)
            tree.column(col,width=width,minwidth=70,stretch=col in ('name','path','detail','ext'))
        vertical=ttk.Scrollbar(box,orient='vertical',command=tree.yview)
        horizontal=ttk.Scrollbar(box,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        tree.grid(row=0,column=0,sticky='nsew')
        vertical.grid(row=0,column=1,sticky='ns')
        horizontal.grid(row=1,column=0,sticky='ew')
        box.columnconfigure(0,weight=1)
        box.rowconfigure(0,weight=1)
        tree.empty_frame=tk.Frame(box,bg='white',padx=18,pady=18)
        tk.Label(tree.empty_frame,text='暂无数据',bg='white',fg='#273c3b',font=('Microsoft YaHei UI',15,'bold')).pack()
        tree.empty_frame.place(relx=.5,rely=.5,anchor='center')
        tree.container=panel
        tree.page=parent
        return tree

    def tab(self,title,columns,titles,widths):
        page=ttk.Frame(self.notebook,padding=10)
        self.notebook.add(page,text=title)
        return self.make_tree(page,columns,titles,widths)

    def start_scan(self):
        if self.busy:
            return
        self.busy=True
        self.operation='scan'
        self.cleanup_auto_checked=False
        self.stop.clear()
        self.result=None
        self.cleanup.candidates=[]
        self.cleanup.invalidate('正在扫描，清理选择已重置。')
        self.cleanup.set_busy()
        self.row_paths.clear()
        for label in self.metrics:
            label.configure(text='—')
        for tree in (self.folder_tree,self.file_tree,self.type_tree,self.issue_tree):
            tree.delete(*tree.get_children())
            tree.empty_frame.place_forget()
        self.scan_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        self.export_button.configure(state='disabled')
        self.stop_button.configure(text='停止')
        self.progress.start(12)
        self.status.set('扫描中')
        days=int(self.cleanup.days.get())
        def worker():
            try:
                candidates=[]
                result=analyze(self.root_path,self.stop,lambda data:self.events.put(('progress',data)))
                payload=serialize(result)
                payload['cleanup_advice']=candidate_summary(candidates)
                payload['cleanup_days']=days
                self.events.put(('cleanup_status','整理中'))
                path=save_report(payload,'disk-analysis')
                self.events.put(('done',(result,path)))
            except Exception as exc:
                self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def show_folder(self,key):
        if not self.result or key not in self.result.folders:
            return
        self.current=key
        node=self.result.folders[key]
        self.folder_tree.delete(*self.folder_tree.get_children())
        children=sorted(self.folder_children[key],key=lambda n:n.size,reverse=True)
        for i,child in enumerate(children):
            row=f'dir:{i}'
            share=child.size/node.size if node.size else 0
            self.folder_tree.insert('', 'end',iid=row,values=(child.path.name,size(child.size) if child.scanned else '未扫描',f'{"▰"*round(share*10)} {share:.1%}' if child.scanned else '—',f'{child.files:,}' if child.scanned else '—',child.skipped,path_advice(child.path,self.cleanup.candidates)))
            self.row_paths[(id(self.folder_tree),row)]=str(child.path)
        direct=node.size-sum(n.size for n in children)
        if direct:
            self.folder_tree.insert('','end',iid='direct',values=('直属文件',size(direct),f'{direct/node.size:.1%}','—','—','保留'))
        shown = key if len(key) < 95 else '…' + key[-94:]
        self.breadcrumb.set(f'{shown}  ·  {size(node.size)}  ·  文件 {size(direct)}')
        self.up_button.configure(state='normal' if node.parent else 'disabled')
        self.folder_tree.empty_frame.place_forget()

    def drill(self,event):
        row=self.folder_tree.identify_row(event.y)
        key=self.row_paths.get((id(self.folder_tree),row))
        if key:
            self.show_folder(key)

    def up(self):
        if self.result and self.current in self.result.folders:
            parent=self.result.folders[self.current].parent
            if parent:
                self.show_folder(parent)

    def selected_path(self,tree):
        rows=tree.selection()
        return self.row_paths.get((id(tree),rows[0])) if rows else None

    def reveal_selected(self,tree):
        path=self.selected_path(tree)
        if path:
            try:
                # Explorer selects the file rather than executing it.
                subprocess.Popen(['explorer.exe','/select,',path])
            except OSError as exc:
                messagebox.showerror('无法定位路径',str(exc),parent=self.winfo_toplevel())

    def copy_selected(self,tree):
        path=self.selected_path(tree)
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)

    def menu(self,event,tree):
        row=tree.identify_row(event.y)
        if not row:
            return
        tree.selection_set(row)
        menu=tk.Menu(self,tearoff=False)
        menu.add_command(label='在资源管理器中定位',command=lambda:self.reveal_selected(tree))
        menu.add_command(label='复制路径',command=lambda:self.copy_selected(tree))
        try:
            menu.tk_popup(event.x_root,event.y_root)
        finally:
            menu.grab_release()

    def storage_settings(self):
        try:
            os.startfile('ms-settings:storagesense')
        except OSError as exc:
            messagebox.showerror('无法打开存储设置',str(exc),parent=self.winfo_toplevel())

    def open_log(self):
        if self.report_path:
            try:
                os.startfile(str(self.report_path))
            except OSError as exc:
                messagebox.showerror('无法打开记录',str(exc),parent=self.winfo_toplevel())

    def begin_cleanup_operation(self,operation):
        self.busy=True
        self.operation=operation
        self.stop.clear()
        self.scan_button.configure(state='disabled')
        self.stop_button.configure(state='normal',text='停止' if operation=='clean' else '停止')
        self.export_button.configure(state='disabled')
        self.progress.start(12)
        self.cleanup.set_busy()
        self.status.set('清理中' if operation=='clean' else '检查中')

    def finish_cleanup_operation(self):
        self.busy=False
        self.progress.stop()
        self.scan_button.configure(state='normal')
        self.stop_button.configure(state='disabled',text='停止')
        self.export_button.configure(state='normal' if self.result else 'disabled')
        self.cleanup.set_busy()

    def invalidate_cleanup(self,message):
        self.cleanup.invalidate(message)
        if self.result:
            self.result.stale=True
        self.status.set('需重新扫描')

    def export(self):
        if not self.result or self.busy:
            return
        name=filedialog.asksaveasfilename(parent=self.winfo_toplevel(),title='导出全盘分析',initialfile=f'C盘分析-{datetime.now():%Y%m%d-%H%M}.html',defaultextension='.html',filetypes=(('网页报告','*.html'),('CSV（目录含子目录，不可相加）','*.csv')))
        if name:
            try:
                export_disk(name,self.result,self.cleanup.candidates,self.cleanup.scanned_days,self.cleanup.selected,self.cleanup.valid)
                self.status.set(f'已导出 {Path(name).name}')
            except (OSError,ValueError) as exc:
                messagebox.showerror('导出失败',str(exc),parent=self.winfo_toplevel())

    def poll(self):
        try:
            while True:
                event,data=self.events.get_nowait()
                if event=='progress':
                    for label,value in zip(self.metrics,(size(data['bytes']),f'{data["files"]:,}',f'{data["folders"]:,}',f'{data["skipped"]:,}')):
                        label.configure(text=value)
                    self.status.set(f'已读取 {data["files"]:,} 个文件 · {data.get("seconds",0):.1f} 秒 · 当前 {data["path"][-85:]}')
                elif event=='cleanup_status':
                    self.status.set(data)
                elif event=='candidates':
                    self.cleanup.apply(*data)
                elif event=='advice_done':
                    candidates,days,complete,self.report_path=data
                    self.finish_cleanup_operation()
                    self.log_button.configure(state='normal')
                    self.cleanup.apply(candidates,days,complete)
                    if not complete:
                        self.cleanup.note.set('已停止 · 需刷新')
                    if self.result:
                        self.show_folder(self.current)
                        for i,f in enumerate(self.result.largest):
                            if self.file_tree.exists(str(i)):
                                self.file_tree.set(str(i),'advice',path_advice(f['path'],self.cleanup.candidates))
                    self.status.set('检查完成' if complete else '已停止 · 结果不完整')
                elif event=='cleanup_done':
                    report,self.report_path=data
                    self.finish_cleanup_operation()
                    self.log_button.configure(state='normal')
                    self.invalidate_cleanup('清理已结束，建议和勾选已失效；需要再次清理时请刷新清理建议。')
                    self.status.set(f'{"清理已停止" if report["cancelled"] else "清理完成"} · 删除 {report["deleted_files"]} 个文件 / {size(report["deleted_bytes"])} · 跳过 {report["skipped_files"]} 个 · 未处理 {report["unprocessed_files"]} 个 · 请重新扫描')
                    if self.on_cleaned:
                        self.on_cleaned()
                elif event=='done':
                    self.result,self.report_path=data
                    self.busy=False
                    self.progress.stop()
                    self.scan_button.configure(state='normal',text='扫描')
                    self.stop_button.configure(state='disabled')
                    self.export_button.configure(state='normal')
                    self.log_button.configure(state='normal')
                    self.cleanup.set_busy()
                    if self.result.cancelled and self.cleanup.valid:
                        self.cleanup.note.set('部分扫描 · 缓存检查完成')
                    self.folder_children=defaultdict(list)
                    for node in self.result.folders.values():
                        if node.parent:
                            self.folder_children[node.parent].append(node)
                    self.show_folder(str(self.result.root))
                    for i,f in enumerate(self.result.largest):
                        row=str(i)
                        self.file_tree.insert('','end',iid=row,values=(size(f['size']),display_time(f['modified']),path_advice(f['path'],self.cleanup.candidates),f['path']))
                        self.row_paths[(id(self.file_tree),row)]=f['path']
                    for ext,d in sorted(self.result.extensions.items(),key=lambda x:x[1]['size'],reverse=True):
                        self.type_tree.insert('','end',values=(ext,size(d['size']),f'{d["files"]:,}'))
                    for i,issue in enumerate(self.result.issues):
                        self.issue_tree.insert('','end',iid=str(i),values=(issue['reason'],issue['path'],issue['detail']))
                        self.row_paths[(id(self.issue_tree),str(i))]=issue['path']
                    self.issue_summary.configure(text=' · '.join(f'{reason} {amount:,} 项' for reason,amount in self.result.skip_counts.items()) or '没有跳过项')
                    for tree in (self.file_tree,self.type_tree,self.issue_tree):
                        tree.empty_frame.place_forget()
                    for label,value in zip(self.metrics,(size(self.result.total),f'{self.result.files:,}',f'{len(self.result.folders):,}',f'{sum(self.result.skip_counts.values()):,}')):
                        label.configure(text=value)
                    self.status.set(f'{"已停止 · 部分结果" if self.result.cancelled else "扫描完成"} · {self.result.seconds:.1f} 秒 · 跳过 {sum(self.result.skip_counts.values()):,} 项')
                    if not self.result.cancelled and self.notebook.select()==str(self.cleanup) and not self.cleanup_auto_checked:
                        self.after_idle(self.cleanup.refresh_candidates)
                elif event=='error':
                    self.busy=False
                    self.progress.stop()
                    self.scan_button.configure(state='normal')
                    self.stop_button.configure(state='disabled')
                    self.cleanup.invalidate('操作失败 · 需刷新')
                    if self.operation=='clean':
                        if self.result:
                            self.result.stale=True
                        if self.on_cleaned:
                            self.on_cleaned()
                    self.export_button.configure(state='normal' if self.result else 'disabled')
                    self.status.set('操作失败，请查看记录')
                    messagebox.showerror('操作失败',data,parent=self.winfo_toplevel())
        except queue.Empty:
            pass
        self.after(100,self.poll)
