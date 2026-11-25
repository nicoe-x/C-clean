"""QA-only: capture this application's own client area, excluding desktop overlays."""
import ctypes
from ctypes import wintypes
from PIL import Image


def capture(root,path):
    u,g=ctypes.windll.user32,ctypes.windll.gdi32
    u.GetDC.restype=wintypes.HDC
    g.CreateCompatibleDC.restype=wintypes.HDC
    g.CreateCompatibleBitmap.restype=wintypes.HBITMAP
    g.SelectObject.restype=wintypes.HGDIOBJ
    g.SelectObject.argtypes=[wintypes.HDC,wintypes.HGDIOBJ]
    g.DeleteObject.argtypes=[wintypes.HGDIOBJ]
    g.DeleteDC.argtypes=[wintypes.HDC]
    g.CreateCompatibleBitmap.argtypes=[wintypes.HDC,ctypes.c_int,ctypes.c_int]
    g.CreateCompatibleDC.argtypes=[wintypes.HDC]
    u.PrintWindow.argtypes=[wintypes.HWND,wintypes.HDC,wintypes.UINT]
    g.GetDIBits.argtypes=[wintypes.HDC,wintypes.HBITMAP,wintypes.UINT,wintypes.UINT,ctypes.c_void_p,ctypes.c_void_p,wintypes.UINT]
    u.ReleaseDC.argtypes=[wintypes.HWND,wintypes.HDC]
    root.update()
    hwnd=root.winfo_id()
    w,h=root.winfo_width(),root.winfo_height()
    dc=u.GetDC(hwnd)
    memory=g.CreateCompatibleDC(dc)
    bitmap=g.CreateCompatibleBitmap(dc,w,h)
    old=g.SelectObject(memory,bitmap)
    class Header(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),('planes',wintypes.WORD),('bits',wintypes.WORD),('compression',wintypes.DWORD),('imageSize',wintypes.DWORD),('x',wintypes.LONG),('y',wintypes.LONG),('colors',wintypes.DWORD),('important',wintypes.DWORD)]
    try:
        if not u.PrintWindow(hwnd,memory,3):
            raise RuntimeError('PrintWindow failed')
        header=Header(ctypes.sizeof(Header),w,-h,1,32,0,0,0,0,0,0)
        pixels=ctypes.create_string_buffer(w*h*4)
        if g.GetDIBits(memory,bitmap,0,h,pixels,ctypes.byref(header),0)!=h:
            raise RuntimeError('GetDIBits failed')
        Image.frombuffer('RGB',(w,h),pixels,'raw','BGRX',0,1).save(path)
    finally:
        g.SelectObject(memory,old)
        g.DeleteObject(bitmap)
        g.DeleteDC(memory)
        u.ReleaseDC(hwnd,dc)
