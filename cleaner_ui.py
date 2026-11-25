"""Desktop presentation layer; deletion policy lives in cleaner.py."""
import os
import queue
import shutil
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from win11_ui import Button, Panel, install_fields, round_window
from datetime import datetime

from cleaner import advice, discover, scan, scan_many, clean, size, summary, save_report
from features import load_preferences, save_preferences, path_key, export_results
from disk_ui import DiskPanel
from app_theme import ThemeController,LABELS

BG = '#f5f6f8'
INK = '#1c2935'
MUTED = '#78838f'
BLUE = '#4657cc'
COLORS = {'推荐清理': '#168068', '按需清理': '#a36613', '建议保留': '#64748b',
          '无需清理': '#64748b', '先检查': '#b45309'}


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Clearspace')
        width = min(1280, max(1040, self.root.winfo_screenwidth() - 80))
        height = min(820, max(640, self.root.winfo_screenheight() - 100))
        self.root.geometry(f'{width}x{height}+{max(0, (self.root.winfo_screenwidth() - width)//2)}+20')
        self.root.minsize(min(1040, width), min(680, height))
        self.root.configure(bg=BG)
        self.assets = Path(__file__).resolve().parent / 'assets'
        self.images = {}
        for name in ('logo-24', 'logo-32', 'logo-48'):
            try:
                self.images[name] = tk.PhotoImage(file=str(self.assets / f'{name}.png'))
            except tk.TclError:
                pass
        if (self.assets / 'app.ico').exists():
            self.root.iconbitmap(default=str(self.assets / 'app.ico'))
        preferences = load_preferences()
        self.theme_preference=preferences['theme']
        self.favorites = set(preferences['favorites'])
        self.results, self.selected = [], set()
        self.analysis_paths = []
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = self.valid_scan = False
        self.report_path = None
        self.scanned_days = int(preferences['days'])
        self.sort_key, self.sort_reverse = 'advice', False
        self.days = tk.StringVar(value=preferences['days'])
        self.search = tk.StringVar()
        self.filter = tk.StringVar(value='全部目录')
        self.app_filter = tk.StringVar(value='所有应用')
        self.disk_text = tk.StringVar()
        self.mode = tk.StringVar(value='agent')
        self.active_mode = 'agent'
        self.status = tk.StringVar(value='就绪')
        self._style()
        self._layout()
        self.update_disk()
        self.theme_controller=ThemeController(self.root,self.theme_preference)
        self.root.after_idle(lambda:round_window(self.root))
        self.search.trace_add('write', lambda *_: self.refresh())
        self.root.bind('<F5>', lambda _: self.start_scan() if not self.busy else None)
        self.root.bind('<Control-f>', lambda _: self.search_entry.focus_set())
        self.tree.bind('<Control-a>', self.select_visible)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.bind('<Destroy>', self.cancel_callbacks, add='+')
        self.root.after(100, self.poll)

    def cancel_callbacks(self,event):
        if event.widget is self.root:
            for callback in self.root.tk.call('after','info'):
                try:
                    self.root.after_cancel(callback)
                except tk.TclError:
                    pass

    def _style(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('.', font=('Microsoft YaHei UI', 9), foreground=INK)
        s.configure('TFrame', background=BG)
        s.configure('TLabel', background=BG, foreground=INK)
        s.configure('White.TFrame', background='white')
        s.configure('White.TLabel', background='white', foreground=INK)
        s.configure('Hint.TLabel', background=BG, foreground=MUTED, font=('Microsoft YaHei UI', 9))
        s.configure('TButton', padding=(11, 7), background='white', borderwidth=1, bordercolor='#e4e8eb', relief='flat')
        s.map('TButton', background=[('active', '#edf2f1'), ('disabled', '#f2f4f5')], foreground=[('disabled', '#aeb6bd')])
        s.configure('Accent.TButton', background=BLUE, foreground='white', padding=(16, 8))
        s.map('Accent.TButton', background=[('disabled', '#e6e8f4'), ('active', '#3949b8')], foreground=[('disabled', '#9ba1b9')])
        s.configure('Danger.TButton',background='#b6414c',foreground='white',padding=(16,8))
        s.map('Danger.TButton',background=[('active','#9b3440')])
        s.configure('TCombobox', padding=6, fieldbackground='white', bordercolor='#dce4f0')
        s.map('TCombobox', fieldbackground=[('readonly', 'white')])
        s.configure('TEntry', padding=7, bordercolor='#dce4f0')
        s.configure('Treeview', rowheight=38, background='white', fieldbackground='white', borderwidth=0)
        s.configure('Treeview.Heading', background='#f8fafb', foreground=MUTED,
                    padding=(8, 9), font=('Microsoft YaHei UI', 9, 'bold'), borderwidth=0)
        s.map('Treeview', background=[('selected', '#edf0ff')], foreground=[('selected', '#3646b1')])
        s.layout('Treeview',[('Treeview.treearea',{'sticky':'nswe'})])
        for orientation in ('Vertical','Horizontal'):
            s.configure(f'{orientation}.TScrollbar',background='#d8dfdf',troughcolor=BG,
                        bordercolor=BG,lightcolor=BG,darkcolor=BG,arrowcolor='#82938e',
                        arrowsize=10,gripcount=0,borderwidth=0)
        s.configure('Horizontal.TProgressbar', background=BLUE, troughcolor='#edf1f3', borderwidth=0, thickness=3)
        s.configure('TNotebook', background=BG, borderwidth=0)
        s.configure('TNotebook.Tab', background='#edf1f3', foreground=MUTED, padding=(14, 10))
        s.map('TNotebook.Tab', background=[('selected', 'white')], foreground=[('selected', BLUE)],
              padding=[('selected',(14,10))])
        s.layout('TNotebook.Tab',[('Notebook.padding',{'sticky':'nswe','children':[('Notebook.label',{'sticky':'nswe'})]})])

        install_fields(s,self.root)

    def _layout(self):
        header=tk.Frame(self.root,bg='white',padx=20,pady=12)
        header.pack(fill='x')
        if 'logo-32' in self.images:
            tk.Label(header,image=self.images['logo-32'],bg='white').pack(side='left',padx=(0,10))
        tk.Label(header,text='Clearspace',bg='white',fg=INK,font=('Segoe UI',15,'bold')).pack(side='left')
        nav=Panel(header,height=40,width=260,padding=3,skin='nav')
        nav.pack(side='left',padx=28)
        navigation=[]
        for label,value in (('Agent 缓存','agent'),('C 盘分析','disk')):
            button=Button(nav.content,text=label,variable=self.mode,value=value,command=self.switch_mode,style='Segment.TButton')
            button.pack(side='left',padx=2)
            navigation.append(button)
        nav.configure(width=sum(b.winfo_reqwidth()+4 for b in navigation)+6)
        tk.Label(header,textvariable=self.disk_text,bg='white',fg=MUTED,font=('Microsoft YaHei UI',9)).pack(side='right')
        self.theme_label=tk.StringVar(value=LABELS[self.theme_preference])
        self.theme_box=ttk.Combobox(header,textvariable=self.theme_label,values=tuple(LABELS.values()),state='readonly',width=8)
        self.theme_box.pack(side='right',padx=(0,14))
        self.theme_box.bind('<<ComboboxSelected>>',self.change_theme)
        self.page_title=tk.StringVar(value='Agent 缓存')
        self.surface=ttk.Frame(self.root)
        self.surface.pack(fill='both',expand=True)
        main=ttk.Frame(self.surface,padding=(20,16,20,12))
        main.pack(fill='both',expand=True)
        cards = ttk.Frame(main)
        cards.pack(fill='x')
        self.metric_values, self.metric_notes = [], []
        for i, (title, note, color) in enumerate((('占用', '', INK),
                                                 ('建议清理', '', INK),
                                                 ('已选', '', BLUE))):
            card = Panel(cards,height=90,padding=14)
            card.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 12, 0))
            cards.columnconfigure(i, weight=1, uniform='card')
            tk.Label(card.content, text=title, bg='white', fg=MUTED, font=('Microsoft YaHei UI', 10)).pack(anchor='w')
            value = tk.Label(card.content, text='—', bg='white', fg=color, font=('Segoe UI',23,'bold'))
            value.pack(anchor='w', pady=(2, 0))
            detail = tk.Label(card.content, text=note, bg='white', fg=MUTED, font=('Microsoft YaHei UI', 9))
            # Detail counters are retained for compatibility, not displayed.
            self.metric_values.append(value)
            self.metric_notes.append(detail)
        toolbar = ttk.Frame(main)
        toolbar.pack(fill='x', pady=(16, 10))
        self.scan_button = Button(toolbar, text='扫描', style='Accent.TButton', command=self.start_scan)
        self.scan_button.pack(side='left')
        ttk.Label(toolbar, text='   早于 ').pack(side='left')
        self.age = ttk.Combobox(toolbar, textvariable=self.days, values=('0', '1', '7', '30', '90'), state='readonly', width=4)
        self.age.pack(side='left')
        self.age.bind('<<ComboboxSelected>>', self.age_changed)
        ttk.Label(toolbar, text=' 天').pack(side='left')
        self.cancel_button = Button(toolbar, text='停止', command=lambda: self.stop.set(), state='disabled')
        self.cancel_button.pack(side='left', padx=10)
        self.report_button = Button(toolbar, text='记录', command=self.open_report, state='disabled')
        self.report_button.pack(side='right')
        self.export_button = Button(toolbar, text='导出', command=self.export_report, state='disabled')
        self.export_button.pack(side='right', padx=8)
        self.details_button=Button(toolbar,text='详情',command=self.open_detail,state='disabled')
        self.details_button.pack(side='right',padx=8)
        Button(toolbar,text='支持列表',command=self.show_support).pack(side='right',padx=8)
        filters = ttk.Frame(main)
        filters.pack(fill='x', pady=(0, 10))
        ttk.Label(filters, text='搜索 ', style='Hint.TLabel').pack(side='left')
        self.search_entry = ttk.Entry(filters, textvariable=self.search, width=18)
        self.search_entry.pack(side='left', padx=(0, 12))
        self.search_entry.bind('<Escape>', lambda _: self.search.set(''))
        self.filter_box = ttk.Combobox(filters, textvariable=self.filter, state='readonly', width=13,
                                      values=('全部目录', '推荐清理', '按需清理', '建议保留', '无需清理', '先检查', '已选择', '收藏目录'))
        self.filter_box.pack(side='left')
        self.filter_box.bind('<<ComboboxSelected>>', lambda _: self.refresh())
        self.app_box = ttk.Combobox(filters, textvariable=self.app_filter, state='readonly', width=15, values=('所有应用',))
        self.app_box.pack(side='left', padx=10)
        self.app_box.bind('<<ComboboxSelected>>', lambda _: self.refresh())
        self.visible_note = ttk.Label(filters, text='等待扫描', style='Hint.TLabel')
        self.visible_note.pack(side='right')
        content = ttk.Frame(main)
        content.pack(fill='both', expand=True)
        table_panel=Panel(content,padding=8)
        table_panel.pack(side='left',fill='both',expand=True)
        box=table_panel.content
        columns = ('selected', 'app', 'advice', 'eligible', 'size', 'path')
        self.tree = ttk.Treeview(box, columns=columns, show='headings', selectmode='browse', height=5)
        for name, title, width in zip(columns, ('', '应用 / 缓存', '建议', '可清理', '占用', '路径'), (42, 220, 100, 100, 100, 380)):
            self.tree.heading(name, text=title, command=lambda key=name: self.sort_by(key))
            self.tree.column(name, width=width, minwidth=45, stretch=name == 'path', anchor='w' if name == 'app' else 'center')
        scroll = ttk.Scrollbar(box, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.empty_state=tk.Frame(box,bg='white',padx=20,pady=20)
        self.empty_title=tk.Label(self.empty_state,text='暂无数据',bg='white',fg=INK,font=('Microsoft YaHei UI',15,'bold'))
        self.empty_title.pack()
        self.empty_subtitle=tk.Label(self.empty_state,text='查看 Agent 的旧缓存与空间占用',bg='white',fg=MUTED,font=('Microsoft YaHei UI',10))
        # No empty-state description.
        self.empty_button=Button(self.empty_state,text='扫描 Agent 缓存',style='Accent.TButton',command=self.start_scan)
        # The main toolbar already contains the scan action.
        self.empty_state.place(relx=.5,rely=.5,anchor='center')
        for label, color in COLORS.items():
            self.tree.tag_configure(label, foreground=INK)
        self.tree.bind('<Button-1>', self.toggle)
        self.tree.bind('<space>', self.toggle_keyboard)
        self.tree.bind('<<TreeviewSelect>>', self.show_detail)
        self.tree.bind('<Double-1>', self.double_click)
        self.tree.bind('<Button-3>', self.context_menu)
        holders=tk.Frame(main)
        self.detail_title=tk.Label(holders)
        self.detail_badge=tk.Label(holders)
        self.reason=tk.Label(holders)
        self.impact=tk.Label(holders)
        self.detail_stats=tk.Label(holders)
        self.path_text=tk.Text(holders,state='disabled')
        self.folder_button=Button(holders)
        self.copy_button=Button(holders)
        self.favorite_button=Button(holders)
        footer = ttk.Frame(main)
        footer.pack(side='bottom', fill='x', before=content)
        bottom = ttk.Frame(footer)
        bottom.pack(fill='x',pady=(10,8))
        self.select_button = Button(bottom, text='全选推荐项', command=self.select_caches, state='disabled')
        self.select_button.pack(side='left')
        self.clear_button = Button(bottom, text='取消选择', command=self.clear_selection, state='disabled')
        self.clear_button.pack(side='left', padx=8)
        self.app_select_button = Button(bottom, text='选当前应用', command=self.select_app, state='disabled')
        # Only displayed while an application filter is active.
        self.clean_button = Button(bottom, text='预览清理', command=self.start_clean, style='Accent.TButton', state='disabled')
        self.clean_button.pack(side='right')
        progress_wrap=ttk.Frame(footer,height=4)
        progress_wrap.pack(fill='x')
        progress_wrap.pack_propagate(False)
        self.progress = ttk.Progressbar(progress_wrap, mode='determinate', maximum=100)
        self.progress.pack(fill='both',expand=True)
        ttk.Label(footer, textvariable=self.status, style='Hint.TLabel').pack(anchor='w', pady=(6, 0))
        self.agent_frame = main
        self.disk_panel = DiskPanel(self.surface, self.switch_agent, self.disk_cleanup_finished)

    def disk_cleanup_finished(self):
        self.valid_scan=False
        self.selected.clear()
        self.refresh()
        self.update_disk()
        self.status.set('数据已更新，请重新扫描')

    def change_theme(self,_=None):
        mode=next((key for key,value in LABELS.items() if value==self.theme_label.get()),'system')
        self.theme_preference=mode
        self.theme_controller.set_mode(mode)
        self.persist_preferences()

    def switch_agent(self):
        self.mode.set('agent')
        self.switch_mode()

    def switch_mode(self):
        if self.busy or self.disk_panel.busy:
            self.mode.set(self.active_mode)
            message = '请先停止当前操作'
            (self.disk_panel.status if self.disk_panel.busy else self.status).set(message)
            return
        self.active_mode = self.mode.get()
        if self.active_mode == 'disk':
            self.agent_frame.pack_forget()
            self.disk_panel.pack(fill='both', expand=True)
            self.root.title('Clearspace')
            self.page_title.set('C 盘空间分析')
        else:
            self.disk_panel.pack_forget()
            self.agent_frame.pack(fill='both', expand=True)
            self.root.title('Clearspace')
            self.page_title.set('Agent 缓存清理')
        self.update_disk()

    def age_changed(self, _=None):
        self.valid_scan = False
        self.selected.clear()
        self.refresh()
        self.status.set('请重新扫描')
        self.persist_preferences()

    def set_busy(self, busy):
        self.busy = busy
        self.scan_button.configure(state='disabled' if busy else 'normal')
        self.age.configure(state='disabled' if busy else 'readonly')
        self.cancel_button.configure(state='normal' if busy else 'disabled')
        self.update_metrics()
        if busy and not self.results:
            self.empty_title.configure(text='扫描中')
            self.empty_subtitle.configure(text='可随时停止，扫描不会修改文件')
            self.empty_button.configure(state='disabled')

    def update_metrics(self):
        total = sum(r.size for r in self.results)
        recommended = sum(r.reclaimable for r in self.results if advice(r, int(self.days.get())).label == '推荐清理')
        chosen = sum(self.results[i].reclaimable for i in self.selected)
        for widget, value in zip(self.metric_values, (total, recommended, chosen)):
            widget.configure(text=size(value) if self.results else '—')
        if self.results:
            self.metric_notes[0].configure(text=f'{len(self.results)} 个目录 · 可清理共 {size(sum(r.reclaimable for r in self.results))}')
        else:
            self.metric_notes[0].configure(text='包含缓存、日志和受保护模型')
        self.metric_notes[2].configure(text=f'已选 {len(self.selected)} 个目录 · 包含筛选后隐藏的选择' if self.selected else '尚未选择目录')
        available = not self.busy and self.valid_scan
        self.select_button.configure(state='normal' if available and recommended else 'disabled')
        self.clear_button.configure(state='normal' if available and self.selected else 'disabled')
        self.clean_button.configure(state='normal' if available and self.selected else 'disabled', text=f'预览清理 · {size(chosen)}' if self.selected else '预览清理')
        self.export_button.configure(state='normal' if self.results and not self.busy else 'disabled')
        self.details_button.configure(state='normal' if self.results and not self.busy else 'disabled')
        self.app_select_button.configure(state='normal' if available and self.app_filter.get() != '所有应用' else 'disabled')
        if self.app_filter.get()!='所有应用':self.app_select_button.pack(side='left',padx=6)
        else:self.app_select_button.pack_forget()

    def start_scan(self):
        if self.active_mode == 'disk':
            self.disk_panel.start_scan()
            return
        if self.busy:
            return
        self.stop.clear()
        self.results.clear()
        self.selected.clear()
        self.valid_scan = False
        self.scanned_days = int(self.days.get())
        self.reset_detail()
        self.refresh()
        self.set_busy(True)
        self.progress.configure(mode='determinate', value=0)
        self.cancel_button.configure(text='停止')
        self.status.set('扫描中')
        days = int(self.days.get())
        analysis_paths = tuple(self.analysis_paths)
        def worker():
            try:
                targets=discover()
                if analysis_paths:
                    from cleaner import Target
                    from agent_discovery import partition_targets, existing
                    targets = partition_targets(targets + [Target('自选目录', '应用数据（仅统计）', p, False) for p in analysis_paths if existing(p)])
                results=scan_many(targets,days,self.stop,
                    lambda done,total,target:self.events.put(('progress',(done,total,target.app))))
                cancelled = self.stop.is_set()
                path = save_report({'created_at': datetime.now().isoformat(), 'days': days, 'cancelled': cancelled, 'targets': summary(results, days)})
                self.events.put(('scanned', (results, cancelled, path)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def show_support(self):
        from agent_support_ui import show_support
        show_support(self)

    def add_analysis_directory(self, parent):
        if self.busy or self.disk_panel.busy: return
        name = filedialog.askdirectory(parent=parent, title='添加分析目录（仅统计）', mustexist=True)
        if not name: return
        from agent_discovery import existing
        path = Path(name)
        if not existing(path):
            messagebox.showinfo('无法添加', '请选择 C 盘中的普通目录。', parent=parent)
            return
        if path not in self.analysis_paths:
            self.analysis_paths.append(path)
            self.valid_scan = False
            self.selected.clear()
            self.status.set('已添加，重新扫描')
            self.update_metrics()

    def sort_by(self, key):
        if key == 'selected':
            return
        self.sort_reverse = not self.sort_reverse if self.sort_key == key else key in ('eligible', 'size')
        self.sort_key = key
        self.refresh()

    def visible_indices(self):
        query, mode = self.search.get().strip().casefold(), self.filter.get()
        indices = []
        for i, r in enumerate(self.results):
            label = advice(r, int(self.days.get())).label
            if self.app_filter.get() != '所有应用' and r.target.app != self.app_filter.get():
                continue
            if query and query not in f'{r.target.app} {r.target.path} {r.target.kind}'.casefold():
                continue
            if mode == '已选择' and i not in self.selected:
                continue
            if mode == '收藏目录' and path_key(r.target.path) not in self.favorites:
                continue
            if mode not in ('全部目录', '已选择', '收藏目录') and label != mode:
                continue
            indices.append(i)
        def key(i):
            r = self.results[i]
            return {'app': r.target.app.casefold(), 'advice': (advice(r, int(self.days.get())).rank, -r.reclaimable),
                    'eligible': r.reclaimable, 'size': r.size,'path':str(r.target.path).casefold()}[self.sort_key]
        return sorted(indices, key=key, reverse=self.sort_reverse)

    def refresh(self):
        focus = self.tree.focus()
        scroll = self.tree.yview()[0]
        self.tree.delete(*self.tree.get_children())
        indices = self.visible_indices()
        if indices:
            self.empty_state.place_forget()
        else:
            self.empty_state.place(relx=.5,rely=.5,anchor='center')
            self.empty_title.configure(text='无匹配项' if self.results else '暂无数据')
            self.empty_subtitle.configure(text='试试其他应用、关键词或建议类型' if self.results else '查看 Agent 的旧缓存与空间占用')
            self.empty_button.configure(text='清除筛选' if self.results else '扫描 Agent 缓存',
                command=self.reset_filters if self.results else self.start_scan,state='disabled' if self.busy else 'normal')
        for key, title in (('app','应用 / 缓存'),('advice','建议'),('eligible','可清理'),('size','占用')):
            self.tree.heading(key, text=title + ((' ↓' if self.sort_reverse else ' ↑') if self.sort_key == key else ''))
        for i in indices:
            r = self.results[i]
            label = advice(r, int(self.days.get())).label
            marker = '☑' if i in self.selected else ('☐' if r.target.cleanable and r.eligible else '—')
            star = '★ ' if path_key(r.target.path) in self.favorites else ''
            self.tree.insert('', 'end', iid=str(i), values=(marker, f'{star}{r.target.app}  /  {r.target.path.name}', label, size(r.reclaimable), size(r.size),str(r.target.path)), tags=(label,))
        if focus and self.tree.exists(focus):
            self.tree.focus(focus)
            self.tree.selection_set(focus)
        elif indices:
            self.tree.focus(str(indices[0]))
            self.tree.selection_set(str(indices[0]))
        else:
            self.reset_detail()
        self.tree.yview_moveto(scroll)
        self.show_detail()
        self.visible_note.configure(text=f'{len(indices)} / {len(self.results)}' if self.results else ('没有扫描结果' if self.valid_scan else '等待扫描'))
        self.update_metrics()

    def reset_filters(self):
        self.search.set('')
        self.filter.set('全部目录')
        self.app_filter.set('所有应用')
        self.refresh()

    def select_caches(self):
        if self.busy or not self.valid_scan:
            return
        self.selected = {i for i, r in enumerate(self.results) if advice(r, int(self.days.get())).label == '推荐清理'}
        self.refresh()
        self.status.set('已选择推荐项')

    def clear_selection(self):
        if not self.busy:
            self.selected.clear()
            self.refresh()

    def choose(self, row):
        if self.busy or not self.valid_scan or not row:
            return
        i = int(row)
        r = self.results[i]
        if not r.target.cleanable or not r.eligible:
            self.status.set('不可清理')
            return
        self.selected.symmetric_difference_update({i})
        self.tree.focus(row)
        self.refresh()

    def toggle(self, event):
        if self.tree.identify_region(event.x, event.y) == 'cell' and self.tree.identify_column(event.x) == '#1':
            self.choose(self.tree.identify_row(event.y))
            return 'break'

    def toggle_keyboard(self, _):
        self.choose(self.tree.focus())
        return 'break'

    def double_click(self,event):
        if self.tree.identify_column(event.x)!='#1':self.open_detail()
        return 'break'

    def reset_detail(self):
        self.detail_title.configure(text='查看清理建议')
        self.detail_badge.configure(text='单击左侧任意一行', fg=MUTED, bg='#edf2f9')
        self.reason.configure(text='这里会说明是否建议清理，以及清理后可能发生的变化。')
        self.impact.configure(text='扫描不会更改任何文件。')
        self.detail_stats.configure(text='')
        self.set_path('')
        self.folder_button.configure(state='disabled')
        self.copy_button.configure(state='disabled')
        self.favorite_button.configure(state='disabled', text='☆ 收藏目录')

    def set_path(self, path):
        self.path_text.configure(state='normal')
        self.path_text.delete('1.0', 'end')
        self.path_text.insert('1.0', path)
        self.path_text.configure(state='disabled')

    def current_result(self):
        rows = self.tree.selection()
        return self.results[int(rows[0])] if rows and int(rows[0]) < len(self.results) else None

    def show_detail(self, _=None):
        r = self.current_result()
        if r is None:
            return
        a = advice(r, int(self.days.get()))
        self.detail_title.configure(text=f'{r.target.app} / {r.target.path.name}')
        self.detail_badge.configure(text=a.label, fg=COLORS[a.label], bg='#edf5f2' if a.label == '推荐清理' else '#f1f4f8')
        self.reason.configure(text=a.reason)
        self.impact.configure(text=a.effect)
        self.detail_stats.configure(text=f'{r.count:,} 个文件 · 符合范围 {len(r.eligible):,} 个\n总占用 {size(r.size)} · 可释放 {size(r.reclaimable)}')
        self.set_path(str(r.target.path))
        self.folder_button.configure(state='normal')
        self.copy_button.configure(state='normal')
        self.favorite_button.configure(state='normal', text='★ 已收藏 · 取消' if path_key(r.target.path) in self.favorites else '☆ 收藏目录')

    def open_detail(self):
        r=self.current_result()
        if r is None:return
        a=advice(r,int(self.days.get()))
        dialog=tk.Toplevel(self.root)
        dialog.title('详情')
        dialog.geometry('560x340+160+100')
        dialog.transient(self.root)
        dialog.after_idle(lambda:round_window(dialog))
        frame=ttk.Frame(dialog,padding=20)
        frame.pack(fill='both',expand=True)
        ttk.Label(frame,text=f'{r.target.app} / {r.target.path.name}',font=('Microsoft YaHei UI',13,'bold')).pack(anchor='w')
        ttk.Label(frame,text=a.label,foreground=BLUE).pack(anchor='w',pady=(8,12))
        ttk.Label(frame,text=a.reason,wraplength=510).pack(anchor='w')
        ttk.Label(frame,text=a.effect,wraplength=510,style='Hint.TLabel').pack(anchor='w',pady=(8,12))
        path=tk.StringVar(value=str(r.target.path))
        ttk.Entry(frame,textvariable=path,state='readonly').pack(fill='x')
        buttons=ttk.Frame(frame)
        buttons.pack(fill='x',pady=16)
        Button(buttons,text='打开',command=self.open_folder).pack(side='left')
        Button(buttons,text='复制',command=self.copy_path).pack(side='left',padx=8)
        Button(buttons,text='收藏',command=self.toggle_favorite).pack(side='left')
        Button(buttons,text='关闭',command=dialog.destroy).pack(side='right')
        dialog.bind('<Escape>',lambda _:dialog.destroy())
        dialog.grab_set()

    def update_disk(self):
        try:
            usage = shutil.disk_usage('C:\\')
            self.disk_text.set(f'C: 可用 {size(usage.free)} / {size(usage.total)}')
        except OSError:
            self.disk_text.set('C: —')

    def persist_preferences(self):
        try:
            save_preferences(self.days.get(), self.favorites,self.theme_controller.mode)
        except OSError:
            self.status.set('本次设置已生效，但无法保存偏好；下次启动可能无法恢复。')

    def toggle_favorite(self):
        r = self.current_result()
        if r:
            self.favorites.symmetric_difference_update({path_key(r.target.path)})
            self.persist_preferences()
            self.refresh()

    def select_visible(self, _=None):
        if self.valid_scan and not self.busy:
            self.selected.update(i for i in self.visible_indices() if advice(self.results[i], int(self.days.get())).label == '推荐清理')
            self.refresh()
            self.status.set('已选择可见推荐项')
        return 'break'

    def select_app(self):
        if not self.valid_scan or self.busy or self.app_filter.get() == '所有应用':
            return
        self.selected.update(i for i,r in enumerate(self.results) if r.target.app == self.app_filter.get() and advice(r, int(self.days.get())).label == '推荐清理')
        self.refresh()
        self.status.set(f'已选 {self.app_filter.get()}')

    def context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        self.tree.focus(row)
        self.tree.selection_set(row)
        self.show_detail()
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label='打开目录', command=self.open_folder)
        menu.add_command(label='复制路径', command=self.copy_path)
        menu.add_command(label='收藏 / 取消收藏', command=self.toggle_favorite)
        menu.add_separator()
        menu.add_command(label='选择当前可见推荐项', command=self.select_visible, state='disabled' if self.busy or not self.valid_scan else 'normal')
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def export_report(self):
        if self.busy or not self.results:
            return
        name = filedialog.asksaveasfilename(parent=self.root, title='导出全部扫描结果（包含筛选隐藏的目录）',
            initialfile=f'AI缓存报告-{datetime.now():%Y%m%d-%H%M}.html', defaultextension='.html',
            filetypes=(('可读网页报告', '*.html'), ('Excel 可打开的 CSV', '*.csv')))
        if name:
            try:
                path = export_results(name, self.results, self.scanned_days, self.selected, self.valid_scan)
                self.status.set(f'已导出 {path.name}')
            except (OSError, ValueError) as exc:
                messagebox.showerror('导出失败', str(exc), parent=self.root)

    def open_folder(self):
        r = self.current_result()
        if r:
            try:
                os.startfile(str(r.target.path))
            except OSError as exc:
                messagebox.showerror('无法打开目录', str(exc), parent=self.root)

    def copy_path(self):
        r = self.current_result()
        if r:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(r.target.path))
            self.status.set('已复制')

    def open_report(self):
        if self.report_path:
            try:
                os.startfile(str(self.report_path))
            except OSError as exc:
                messagebox.showerror('无法打开报告', str(exc), parent=self.root)

    def confirm(self, chosen):
        dialog = tk.Toplevel(self.root)
        dialog.title('核对清理清单')
        dialog.geometry('700x520')
        dialog.minsize(620, 480)
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.after_idle(lambda:round_window(dialog))
        frame = ttk.Frame(dialog, padding=24)
        frame.pack(fill='both', expand=True)
        amount = sum(r.reclaimable for r in chosen)
        count = sum(len(r.eligible) for r in chosen)
        ttk.Label(frame, text=f'预计释放 {size(amount)}', font=('Microsoft YaHei UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(frame, text=f'{len(chosen)} 个目录 · {count:,} 个文件 · {self.days.get()} 天前', style='Hint.TLabel').pack(anchor='w', pady=(4, 14))
        box = ttk.Frame(frame)
        box.pack(fill='both', expand=True)
        text = tk.Text(box, wrap='word', relief='flat', bg='white', fg=INK, font=('Microsoft YaHei UI', 10), padx=12, pady=10)
        sb = ttk.Scrollbar(box, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        text.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        for r in chosen:
            a = advice(r, int(self.days.get()))
            text.insert('end', f'{r.target.app} · {a.label} · {size(r.reclaimable)}\n{r.target.path}\n\n')
        text.configure(state='disabled')
        ttk.Label(frame, text='永久删除，不进入回收站。请先退出相关应用。', style='Hint.TLabel').pack(anchor='w', pady=14)
        row = ttk.Frame(frame)
        row.pack(fill='x')
        answer = [False]
        def accept():
            answer[0] = True
            dialog.destroy()
        Button(row, text='取消', command=dialog.destroy).pack(side='left')
        Button(row, text='删除', style='Danger.TButton', command=accept).pack(side='right')
        dialog.bind('<Escape>', lambda _: dialog.destroy())
        dialog.grab_set()
        self.root.wait_window(dialog)
        return answer[0]

    def start_clean(self):
        if self.busy or not self.valid_scan or not self.selected:
            return
        chosen = [self.results[i] for i in sorted(self.selected)]
        if not self.confirm(chosen):
            return
        self.stop.clear()
        self.set_busy(True)
        self.cancel_button.configure(text='停止清理')
        self.progress.configure(mode='indeterminate')
        self.progress.start(12)
        self.status.set('清理中')
        days = int(self.days.get())
        def worker():
            try:
                report = clean(chosen, self.stop)
                report['cancelled'] = self.stop.is_set()
                report['targets'] = summary(chosen, days)
                path = save_report(report, 'cleanup')
                self.events.put(('cleaned', (report, path)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event, data = self.events.get_nowait()
                if event == 'progress':
                    index, total, app = data
                    self.progress.configure(value=index * 100 / max(total, 1))
                    self.status.set(f'{app} · {min(index,total)} / {total}')
                elif event == 'scanned':
                    self.results, cancelled, path = data
                    self.report_path = path
                    apps = ('所有应用', *sorted({r.target.app for r in self.results}, key=str.casefold))
                    self.app_box.configure(values=apps)
                    if self.app_filter.get() not in apps:
                        self.app_filter.set('所有应用')
                    self.valid_scan = not cancelled
                    self.set_busy(False)
                    self.refresh()
                    self.progress.configure(value=0 if cancelled else 100)
                    self.scan_button.configure(text='扫描')
                    self.report_button.configure(state='normal')
                    self.update_disk()
                    self.status.set('已停止 · 结果不完整' if cancelled else f'{len(self.results)} 个目录 · 跳过 {sum(r.skipped for r in self.results)} 项')
                elif event == 'cleaned':
                    report, path = data
                    self.report_path = path
                    self.valid_scan = False
                    self.selected.clear()
                    self.results.clear()
                    self.progress.stop()
                    self.progress.configure(mode='determinate', value=0 if report['cancelled'] else 100)
                    self.set_busy(False)
                    self.refresh()
                    self.report_button.configure(state='normal')
                    self.update_disk()
                    self.disk_panel.invalidate_cleanup('Agent 缓存已执行清理，请刷新全盘模式的清理建议。')
                    self.status.set(f'{"清理已停止" if report["cancelled"] else "清理完成"} · 已释放 {size(report["deleted_bytes"])} · 删除 {report["deleted_files"]} 个文件 · 跳过 {report["skipped_files"]} 个')
                elif event == 'error':
                    self.valid_scan = False
                    self.progress.stop()
                    self.set_busy(False)
                    self.status.set('操作失败')
                    messagebox.showerror('操作失败', data, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.disk_panel.busy:
            self.disk_panel.stop.set()
            self.disk_panel.status.set('正在停止')
        elif self.busy:
            self.stop.set()
            self.status.set('正在停止')
        else:
            self.root.destroy()
