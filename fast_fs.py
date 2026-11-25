"""Batch Windows directory metadata, with a portable conservative fallback.

FILE_ID_EXTD_DIR_INFO supplies size, timestamps and 128-bit identity in one
directory query. No file contents are opened. Deletion uses its own full checks.
"""
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import stat
import struct

REPARSE=0x400
DIRECTORY=0x10


@dataclass(slots=True)
class Metadata:
    name: str
    path: str
    attrs: int
    size: int
    modified: int
    inode: int
    volume: int

    @property
    def is_dir(self):
        return bool(self.attrs & DIRECTORY)


if os.name=='nt':
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.GetFileInformationByHandleEx.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]


class Directory:
    def __init__(self,path,anchor=None):
        self.path=Path(path)
        self.anchor=Path(anchor) if anchor else None
        self.handle=None
        self.native=os.name=='nt'

    def __enter__(self):
        if self.anchor is None:
            from cleaner import safe_chain
            if not safe_chain(self.path):
                raise OSError('链接或路径变化')
        if not self.native:
            from cleaner import safe_chain
            if not safe_chain(self.path):
                raise OSError('链接或路径变化')
            s=self.path.stat()
            self.identity=(s.st_dev,s.st_ino)
            self.canonical=self.path.resolve()
            if self.anchor and not self.canonical.is_relative_to(self.anchor):
                raise OSError('目录路径已越过扫描根目录')
            return self
        name=str(self.path.absolute())
        if not name.startswith('\\\\?\\'):
            name='\\\\?\\'+name
        self.handle=kernel.CreateFileW(name,1|0x80,1|2|4,None,3,0x02000000|0x00200000,None)
        if self.handle==ctypes.c_void_p(-1).value:
            self.handle=None
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            attrs=(ctypes.c_uint32*2)()
            if not kernel.GetFileInformationByHandleEx(self.handle,9,attrs,ctypes.sizeof(attrs)):
                raise ctypes.WinError(ctypes.get_last_error())
            if attrs[0]&REPARSE or not attrs[0]&DIRECTORY:
                raise OSError('链接或路径变化')
            info=ctypes.create_string_buffer(24)
            if not kernel.GetFileInformationByHandleEx(self.handle,18,info,24):
                raise ctypes.WinError(ctypes.get_last_error())
            self.identity=(struct.unpack_from('<Q',info,0)[0],int.from_bytes(info.raw[8:24],'little'))
            final=ctypes.create_unicode_buffer(32768)
            n=kernel.GetFinalPathNameByHandleW(self.handle,final,len(final),0)
            if not n or n>=len(final):
                raise OSError('无法验证目录最终路径')
            self.canonical=Path(final.value[4:] if final.value.startswith('\\\\?\\') else final.value)
            if self.anchor and not self.canonical.is_relative_to(self.anchor):
                raise OSError('目录路径已越过扫描根目录')
            return self
        except BaseException:
            self.__exit__(None,None,None)
            raise

    def __exit__(self,*_):
        if self.handle is not None:
            kernel.CloseHandle(self.handle)
            self.handle=None

    def __iter__(self):
        if not self.native:
            yield from self.fallback()
            return
        buffer=ctypes.create_string_buffer(65536)
        first=True
        while True:
            if not kernel.GetFileInformationByHandleEx(self.handle,20 if first else 19,buffer,len(buffer)):
                error=ctypes.get_last_error()
                if error in (18,2):
                    return
                if first and error in (1,50,87):
                    yield from self.fallback()
                    return
                raise ctypes.WinError(error)
            first=False
            raw=buffer.raw
            offset=0
            while True:
                next_offset=struct.unpack_from('<I',raw,offset)[0]
                modified=struct.unpack_from('<q',raw,offset+24)[0]
                amount=struct.unpack_from('<q',raw,offset+40)[0]
                attrs,length=struct.unpack_from('<II',raw,offset+56)
                if length>len(raw)-offset-88 or length%2:
                    raise OSError('无效目录枚举记录')
                name=raw[offset+88:offset+88+length].decode('utf-16-le',errors='surrogatepass')
                if name not in ('.','..'):
                    inode=int.from_bytes(raw[offset+72:offset+88],'little')
                    yield Metadata(name,os.path.join(str(self.path),name),attrs,amount,
                                   (modified-116444736000000000)*100,inode,self.identity[0])
                if not next_offset:
                    break
                if next_offset<88 or offset+next_offset>=len(raw):
                    raise OSError('无效目录枚举偏移')
                offset+=next_offset

    def fallback(self):
        with os.scandir(self.path) as entries:
            for entry in entries:
                s=os.stat(entry.path,follow_symlinks=False)
                attrs=getattr(s,'st_file_attributes',0)
                if stat.S_ISDIR(s.st_mode):attrs|=DIRECTORY
                if stat.S_ISLNK(s.st_mode):attrs|=REPARSE
                yield Metadata(entry.name,entry.path,attrs,s.st_size,s.st_mtime_ns,s.st_ino,s.st_dev)
