"""Application-only light/dark styling and read-only Windows theme detection."""
import tkinter as tk
from tkinter import ttk

LIGHT={'bg':'#f5f6f8','surface':'#ffffff','nav':'#f1f3f7','text':'#1c2935',
       'muted':'#78838f','accent':'#4657cc','border':'#e3e6ec','header':'#f8fafb',
       'selection':'#edf0ff','selection_text':'#3646b1','disabled':'#a6abb4',
       'green':'#168068','amber':'#a36613','red':'#b6414c','field':'#f5f7fb'}
DARK={'bg':'#1b1e24','surface':'#252931','nav':'#20242c','text':'#ecedf3',
      'muted':'#a2aab7','accent':'#a8b4ff','border':'#3d4451','header':'#2b3039',
      'selection':'#384365','selection_text':'#edf0ff','disabled':'#737d8e',
      'green':'#72d3ad','amber':'#e2ba70','red':'#ef919c','field':'#20242b'}
LABELS={'system':'跟随系统','light':'浅色','dark':'深色'}


def windows_theme():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            value,_=winreg.QueryValueEx(key,'AppsUseLightTheme')
        return 'dark' if value==0 else 'light'
    except (ImportError,OSError):return 'light'


def palette(widget):
    controller=getattr(widget._root(),'_theme_controller',None)
    return DARK if controller and controller.effective=='dark' else LIGHT


def current_theme(widget):
    controller=getattr(widget._root(),'_theme_controller',None)
    return controller.effective if controller else 'light'


class ThemeController:
    def __init__(self,root,mode='system',reader=None,interval=1000):
        self.root=root
        self.reader=reader or windows_theme
        self.mode=mode if mode in LABELS else 'system'
        self.effective=self.reader() if self.mode=='system' else self.mode
        if self.effective not in ('light','dark'):self.effective='light'
        self.interval=interval
        self._pending=None
        root._theme_controller=self
        self.apply()
        root.bind_all('<Map>',self._mapped,add='+')
        self._timer=root.after(interval,self._poll)

    def set_mode(self,mode):
        self.mode=mode if mode in LABELS else 'system'
        effective=self.reader() if self.mode=='system' else self.mode
        effective=effective if effective in ('light','dark') else 'light'
        if effective!=self.effective:
            self.effective=effective
            self.apply()

    def check_system(self):
        if self.mode=='system':self.set_mode('system')

    def _poll(self):
        if not self.root.winfo_exists():return
        self.check_system()
        self._timer=self.root.after(self.interval,self._poll)

    def _mapped(self,_):
        if self._pending is None:self._pending=self.root.after_idle(self._new_widgets)

    def _new_widgets(self):
        self._pending=None
        if self.root.winfo_exists():self.apply_widgets(self.root)

    def apply(self):
        p=palette(self.root)
        s=ttk.Style(self.root)
        s.configure('.',background=p['bg'],foreground=p['text'])
        for name in ('TFrame','TLabel','Hint.TLabel','TNotebook'):
            s.configure(name,background=p['bg'],foreground=p['muted'] if name=='Hint.TLabel' else p['text'])
        s.configure('White.TFrame',background=p['surface'])
        s.configure('White.TLabel',background=p['surface'],foreground=p['text'])
        s.configure('TNotebook',borderwidth=0,bordercolor=p['bg'],lightcolor=p['bg'],darkcolor=p['bg'])
        s.configure('TEntry',fieldbackground=p['surface'],foreground=p['text'],insertcolor=p['text'],selectbackground=p['selection'],selectforeground=p['selection_text'])
        s.map('TEntry',fieldbackground=[('readonly',p['surface']),('disabled',p['field'])],
              foreground=[('disabled',p['disabled']),('readonly',p['text'])])
        s.configure('TCombobox',fieldbackground=p['surface'],foreground=p['text'],selectbackground=p['selection'],selectforeground=p['text'])
        s.map('TCombobox',foreground=[('disabled',p['disabled']),('readonly',p['text'])],fieldbackground=[('readonly',p['surface'])])
        s.configure('Treeview',background=p['surface'],fieldbackground=p['surface'],foreground=p['text'])
        s.configure('Treeview.Heading',background=p['header'],foreground=p['muted'])
        s.map('Treeview.Heading',background=[('active',p['nav']),('pressed',p['nav'])],foreground=[('active',p['text'])])
        s.map('Treeview',background=[('selected',p['selection'])],foreground=[('selected',p['selection_text'])])
        s.configure('TNotebook.Tab',background=p['bg'],foreground=p['muted'])
        s.map('TNotebook.Tab',background=[('selected',p['surface'])],foreground=[('selected',p['accent'])],padding=[('selected',(14,10))])
        for orientation in ('Vertical','Horizontal'):
            s.configure(f'{orientation}.TScrollbar',background=p['border'],troughcolor=p['bg'],
                        bordercolor=p['bg'],lightcolor=p['bg'],darkcolor=p['bg'],arrowcolor=p['muted'])
            s.map(f'{orientation}.TScrollbar',background=[('disabled',p['nav']),('active',p['border']),('!active',p['border'])],
                  arrowcolor=[('disabled',p['muted']),('active',p['text'])])
        s.configure('Horizontal.TProgressbar',background=p['accent'],troughcolor=p['nav'],bordercolor=p['bg'],lightcolor=p['bg'],darkcolor=p['bg'])
        self.root.option_add('*TCombobox*Listbox.background',p['surface'])
        self.root.option_add('*TCombobox*Listbox.foreground',p['text'])
        self.root.option_add('*TCombobox*Listbox.selectBackground',p['selection'])
        self.root.option_add('*TCombobox*Listbox.selectForeground',p['selection_text'])
        from win11_ui import install_fields
        install_fields(s,self.root)
        self.apply_widgets(self.root)

    def _color(self,widget,value,option):
        p=palette(widget)
        try:
            rgb=widget.winfo_rgb(value)
            value='#'+''.join(f'{c//257:02x}' for c in rgb)
        except (tk.TclError,TypeError):return value
        foreground='foreground' in option or option=='insertbackground'
        if option=='selectbackground':return p['selection']
        if option=='selectforeground':return p['selection_text']
        if option=='activebackground':return p['selection']
        if option=='activeforeground':return p['selection_text']
        if option=='disabledforeground':return p['disabled']
        if option in ('highlightbackground','highlightcolor'):return p['border']
        if foreground:
            roles={
                'text':{'#000000','#ffffff','#17263c','#243b3b','#293245','#273c3b','#344052','#1c2935','#ecedf3'},
                'muted':{'#78838f','#64748b','#89938f','#7a8892','#98a1aa','#97a3ab','#98a1aa','#a2aab7'},
                'accent':{'#4657cc','#2563eb','#2463d4','#a8b4ff'},
                'green':{'#168068','#168068','#72d3ad'},'amber':{'#a36613','#b45309','#e2ba70'},'red':{'#b6414c','#ef919c'}}
        else:
            roles={'bg':{LIGHT['bg'],DARK['bg'],'#d9d9d9','#f0f0f0'},
                   'surface':{'#ffffff',DARK['surface']},'nav':{LIGHT['nav'],DARK['nav'],'#f4f5f9'},
                   'field':{LIGHT['field'],DARK['field']},'border':{LIGHT['border'],DARK['border'],'#e8ecef','#e8ecee'},
                   'header':{'#edf2f9','#edf5f2','#f1f4f8',DARK['header']}}
        for role,values in roles.items():
            if value in values:return p[role]
        return p['text'] if foreground else p['surface']

    def apply_widgets(self,widget):
        from win11_ui import Button,Panel,round_window
        p=palette(widget)
        if isinstance(widget,ttk.Treeview):
            saved=getattr(widget,'_theme_tags',{})
            for tag in widget.tk.splitlist(widget.tk.call(str(widget),'tag','names')):
                color=widget.tag_configure(tag,'foreground')
                if color:
                    if tag not in saved:saved[tag]=color
                    widget.tag_configure(tag,foreground=self._color(widget,saved[tag],'foreground'))
            widget._theme_tags=saved
        elif isinstance(widget,ttk.Label):
            value=widget.cget('foreground')
            if value:
                original=getattr(widget,'_theme_foreground',value)
                widget._theme_foreground=original
                widget.configure(foreground=self._color(widget,original,'foreground'))
        elif isinstance(widget,(tk.Tk,tk.Toplevel,tk.Frame,tk.Canvas,tk.Label,tk.Text,tk.Menu,tk.Listbox)):
            originals=getattr(widget,'_theme_original',{})
            for option in ('background','foreground','insertbackground','selectbackground','selectforeground','highlightbackground','highlightcolor','activebackground','activeforeground','disabledforeground'):
                try:
                    if option not in originals:originals[option]=widget.cget(option)
                    value=self._color(widget,originals[option],option)
                    if isinstance(widget,(tk.Tk,tk.Toplevel)) and option=='background':value=p['bg']
                    widget.configure(**{option:value})
                except tk.TclError:pass
            widget._theme_original=originals
        if isinstance(widget,ttk.Combobox):
            popdown=f'{widget}.popdown.f.l'
            if widget.tk.call('winfo','exists',popdown):
                widget.tk.call(popdown,'configure','-background',p['surface'],'-foreground',p['text'],
                               '-selectbackground',p['selection'],'-selectforeground',p['selection_text'])
        for child in widget.winfo_children():self.apply_widgets(child)
        if isinstance(widget,Button):widget._draw()
        if isinstance(widget,Panel):
            widget.content.configure(bg=p['nav'] if widget._skin=='nav' else p['surface'])
            widget._redraw(type('Size',(),{'width':widget.winfo_width(),'height':widget.winfo_height()})())
        if isinstance(widget,(tk.Tk,tk.Toplevel)):
            round_window(widget,refresh_theme=False)
