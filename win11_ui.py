"""Rounded Tk controls with build-time antialiased assets; no runtime Pillow."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, font
import weakref

BG='#f5f6f8'
ACCENT='#4657cc'
_resources=weakref.WeakKeyDictionary()


class Resources:
    def __init__(self,root):
        self.root=weakref.proxy(root)
        self.images={}
        self.folder=Path(__file__).resolve().parent/'assets/fluent'

    def image(self,name,theme=None):
        from app_theme import current_theme
        theme=theme or current_theme(self.root)
        key=f'{theme}/{name}'
        if key not in self.images:
            path=self.folder/('dark' if theme=='dark' else '')/f'{name}.png'
            self.images[key]=tk.PhotoImage(master=self.root,file=str(path))
        return self.images[key]

    def surface(self,name,width,height,master):
        source=self.image(name)
        target=tk.PhotoImage(master=master,width=width,height=height)
        def copy(sx,sy,ex,ey,dx,dy,tx,ty):
            if tx>dx and ty>dy:
                target.tk.call(str(target),'copy',str(source),'-from',sx,sy,ex,ey,'-to',dx,dy,tx,ty)
        r=10
        copy(10,10,11,11,r,r,width-r,height-r)
        copy(10,0,11,r,r,0,width-r,r)
        copy(10,32-r,11,32,r,height-r,width-r,height)
        copy(0,10,r,11,0,r,r,height-r)
        copy(32-r,10,32,11,width-r,r,width,height-r)
        copy(0,0,r,r,0,0,r,r)
        copy(32-r,0,32,r,width-r,0,width,r)
        copy(0,32-r,r,32,0,height-r,r,height)
        copy(32-r,32-r,32,32,width-r,height-r,width,height-r+r)
        return target


def resources(widget):
    root=widget._root()
    if root not in _resources:_resources[root]=Resources(root)
    return _resources[root]


def background(master):
    try:return master.cget('background')
    except tk.TclError:
        return ttk.Style(master).lookup(master.cget('style') or master.winfo_class(),'background') or BG


def icon_for(text):
    for prefix,name in (('全选','select'),('推荐项','select'),('扫描','scan'),('停止','stop'),
        ('取消选择','clear'),('预览','preview'),('刷新','refresh'),('详情','info'),
        ('支持列表','info'),('添加目录','folder'),
        ('导出','export'),('记录','report'),('存储','settings'),('复制','copy'),
        ('收藏','bookmark'),('☆','bookmark'),('★','bookmark'),('选当前','select'),
        ('上一','left'),('下一','right'),('删除','trash'),('取消','close'),
        ('关闭','close'),('打开','folder'),('↑','up'),('Agent','cache'),('C 盘','disk')):
        if text.startswith(prefix):return name
    return None


class Button(tk.Canvas):
    def __init__(self,master,text='',command=None,state='normal',style='TButton',
                 icon=None,variable=None,value=None,**kwargs):
        self._button_options={'text':text,'command':command,'state':state,'style':style}
        self.variable,self.value=variable,value
        self.explicit_icon=icon
        self._hover=False
        self._pressed=False
        self._trace=None
        self._font=font.Font(master,family='Microsoft YaHei UI',size=9)
        super().__init__(master,bg=background(master),highlightthickness=0,borderwidth=0,
                         height=34,takefocus=1,cursor='hand2',**kwargs)
        self.bind('<Enter>',lambda _:self._set_hover(True))
        self.bind('<Leave>',lambda _:self._set_hover(False))
        self.bind('<Button-1>',self._press)
        self.bind('<ButtonRelease-1>',self._release)
        self.bind('<space>',lambda _:self._key())
        self.bind('<Return>',lambda _:self._key())
        self.bind('<FocusIn>',lambda _:self._draw())
        self.bind('<FocusOut>',lambda _:self._draw())
        self.bind('<Destroy>',self._destroyed)
        if variable:self._trace=variable.trace_add('write',lambda *_:self._draw())
        self._draw()

    def _destroyed(self,event):
        if event.widget is self and self.variable and self._trace:
            try:self.variable.trace_remove('write',self._trace)
            except tk.TclError:pass

    def _set_hover(self,hover):
        if self._hover!=hover:
            self._hover=hover
            if not hover:self._pressed=False
            self._draw()

    def _press(self,_):
        if self._button_options['state']!='disabled':
            self.focus_set();self._pressed=True;self._draw()

    def _release(self,event):
        pressed=self._pressed
        self._pressed=False;self._draw()
        if pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height():self.invoke()

    def _key(self):
        self.invoke()
        return 'break'

    def invoke(self):
        if self._button_options['state']=='disabled':return None
        if self.variable:self.variable.set(self.value)
        command=self._button_options['command']
        if command:return command()

    def configure(self,cnf=None,**kwargs):
        if isinstance(cnf,dict):kwargs={**cnf,**kwargs}
        changed=False
        for key in tuple(kwargs):
            if key in self._button_options:
                value=kwargs.pop(key)
                if self._button_options[key]!=value:self._button_options[key]=value;changed=True
        result=super().configure(**kwargs) if kwargs else None
        if changed:self._draw()
        return result

    config=configure

    def cget(self,key):
        return self._button_options[key] if key in self._button_options else super().cget(key)

    __getitem__=cget

    def _draw(self):
        from app_theme import palette
        if not self.winfo_exists():return
        p=palette(self)
        text=str(self._button_options['text'])
        name=self.explicit_icon if self.explicit_icon is not None else icon_for(text)
        if text=='↑':text=''
        disabled=self._button_options['state']=='disabled'
        style=self._button_options['style']
        selected=bool(self.variable and self.variable.get()==self.value)
        mode='disabled' if disabled else ('pressed' if self._pressed else ('hover' if self._hover else 'normal'))
        kind='primary' if style=='Accent.TButton' else ('danger' if style=='Danger.TButton' else 'button')
        if style=='Segment.TButton':kind='segment-selected' if selected else 'segment'
        if self.focus_get() is self and not disabled and not self._pressed and not self.variable:mode='focus'
        white=kind in ('primary','danger') and not disabled
        foreground=p['disabled'] if disabled else ('white' if white else (p['accent'] if selected else p['text']))
        icon_color='disabled' if disabled else ('white' if white else ('accent' if selected else 'dark'))
        width=max(34 if not text else 76,self._font.measure(text)+(24 if name and text else (16 if name else 0))+24)
        height=34
        super().configure(width=width,height=height,cursor='arrow' if disabled else 'hand2',takefocus=0 if disabled else 1,bg=background(self.master))
        self.delete('all')
        try:
            self._surface=resources(self).surface(f'{kind}-{mode}',width,height,self)
            self.create_image(0,0,image=self._surface,anchor='nw')
        except (OSError,tk.TclError):
            self.create_polygon(8,0,width-8,0,width,8,width,height-8,width-8,height,8,height,0,height-8,0,8,
                                fill=ACCENT if white else 'white',outline='#e2e5eb',smooth=True)
        text_width=self._font.measure(text)
        left=(width-text_width-(24 if name and text else (16 if name else 0)))/2
        if name:
            try:
                self._icon=resources(self).image(f'{name}-{icon_color}')
                self.create_image(left,9,image=self._icon,anchor='nw')
                left+=24 if text else 16
            except (OSError,tk.TclError):pass
        if text:self.create_text(left,17,text=text,anchor='w',font=self._font,fill=foreground)


class Panel(tk.Frame):
    def __init__(self,master,height=1,padding=8,width=None,skin='panel',**kwargs):
        super().__init__(master,bg=background(master),height=height,**({'width':width} if width else {}),**kwargs)
        self._skin=skin
        self._canvas=tk.Canvas(self,bg=background(master),highlightthickness=0,borderwidth=0)
        self._canvas.place(x=0,y=0,relwidth=1,relheight=1)
        self.content=tk.Frame(self,bg='#f1f3f7' if skin=='nav' else 'white')
        self.content.place(x=padding,y=padding,relwidth=1,relheight=1,width=-2*padding,height=-2*padding)
        self.bind('<Configure>',self._redraw)

    def _redraw(self,event):
        if event.width<22 or event.height<22:return
        self._canvas.configure(bg=background(self.master))
        try:
            self._image=resources(self).surface(self._skin,event.width,event.height,self)
            self._canvas.delete('all');self._canvas.create_image(0,0,image=self._image,anchor='nw')
        except (OSError,tk.TclError):pass


def install_fields(style,master):
    from app_theme import current_theme
    r=resources(master)
    try:
        for theme in ('light','dark'):
            name=f'Fluent.{theme}.field'
            if name not in style.element_names():
                normal=r.image('field-normal',theme);focused=r.image('field-focus',theme);disabled=r.image('field-disabled',theme)
                style.element_create(name,'image',normal,('disabled',disabled),('focus',focused),border=8,sticky='nswe')
                style.element_create(f'Fluent.{theme}.down','image',r.image('down-dark',theme),sticky='')
        theme=current_theme(master)
        field=f'Fluent.{theme}.field';arrow=f'Fluent.{theme}.down'
        style.layout('TEntry',[(field,{'sticky':'nswe','children':[('Entry.padding',{'sticky':'nswe','children':[('Entry.textarea',{'sticky':'nswe'})]})]})])
        style.layout('TCombobox',[(field,{'sticky':'nswe','children':[
            (arrow,{'side':'right','sticky':''}),('Combobox.padding',{'sticky':'nswe','children':[('Combobox.textarea',{'sticky':'nswe'})]})]})])
        style.configure('TEntry',padding=(5,0))
        style.configure('TCombobox',padding=(5,0),arrowsize=16)
    except tk.TclError:pass


def round_window(window,refresh_theme=True):
    try:
        from app_theme import current_theme
        controller=getattr(window._root(),'_theme_controller',None)
        if refresh_theme:
            if controller:controller.apply_widgets(window)
            window.update_idletasks()
        user=ctypes.windll.user32
        user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]
        user.GetAncestor.restype=wintypes.HWND
        hwnd=user.GetAncestor(window.winfo_id(),2)
        dwm=ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        preference=ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(hwnd,33,ctypes.byref(preference),ctypes.sizeof(preference))
        dark=ctypes.c_int(current_theme(window)=='dark')
        dwm.DwmSetWindowAttribute(hwnd,20,ctypes.byref(dark),ctypes.sizeof(dark))
    except (OSError,AttributeError,tk.TclError):pass
