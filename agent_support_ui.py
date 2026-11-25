"""On-demand product list; the main scan view stays compact."""
import tkinter as tk
from tkinter import ttk

from agent_catalog import products, DESKTOPS, STATES
from win11_ui import Button, Panel, round_window


def show_support(app):
    window = tk.Toplevel(app.root)
    window.title('支持列表')
    window.geometry('820x540')
    window.minsize(640, 420)
    window.transient(app.root)
    body = ttk.Frame(window, padding=20)
    body.pack(fill='both', expand=True)
    bar = ttk.Frame(body)
    bar.pack(fill='x', pady=(0, 12))
    search = tk.StringVar()
    ttk.Entry(bar, textvariable=search).pack(side='left', fill='x', expand=True)
    Button(bar, text='添加目录', state='disabled' if app.busy or app.disk_panel.busy else 'normal',
           command=lambda:app.add_analysis_directory(window)).pack(side='left', padx=(12, 0))
    panel = Panel(body, padding=8)
    panel.pack(fill='both', expand=True)
    tree = ttk.Treeview(panel.content, columns=('app', 'mode'), show='headings', selectmode='browse')
    tree.heading('app', text='应用'); tree.heading('mode', text='支持范围')
    tree.column('app', width=320); tree.column('mode', width=230)
    sy = ttk.Scrollbar(panel.content, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=sy.set)
    sy.pack(side='right', fill='y'); tree.pack(fill='both', expand=True)
    sources = tk.StringVar()
    ttk.Label(body, textvariable=sources, style='Hint.TLabel').pack(fill='x', pady=(12, 0))
    rows = products()
    desktop_names = {p.name for p in DESKTOPS}
    log_names = {p.name for p in STATES if p.logs}
    def render(*_):
        tree.delete(*tree.get_children())
        query = search.get().strip().casefold()
        for i, row in enumerate(rows):
            if query and query not in (row['name']+' '+' '.join(row['paths'])).casefold(): continue
            mode = '缓存识别 / 数据统计' if row['name'] in desktop_names else '日志手选 / 数据统计' if row['name'] in log_names else '仅统计'
            tree.insert('', 'end', iid=str(i), values=(row['name'], mode))
    def select(_):
        chosen = tree.selection()
        sources.set(rows[int(chosen[0])]['sources'][0] if chosen else '')
    search.trace_add('write', render)
    tree.bind('<<TreeviewSelect>>', select)
    window.bind('<Escape>', lambda _:window.destroy())
    render()
    window.after_idle(lambda:round_window(window))
    window.grab_set()
