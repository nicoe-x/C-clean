"""Narrow global cleanup allowlist, immutable preview plans and verified deletion.

No arbitrary path supplied by a report or the UI can grant deletion permission.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import stat
import time

from fast_fs import Directory
from cleaner import discover, deduplicate, Target, REPARSE, on_c, safe_chain, size

PERSONAL_SUFFIXES = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.pdf', '.txt',
    '.jpg', '.jpeg', '.png', '.gif', '.heic', '.mp4', '.mov', '.mp3', '.wav', '.zip',
    '.7z', '.rar', '.db', '.sqlite', '.sqlite3', '.pem', '.key', '.pfx', '.kdbx',
    '.gguf', '.safetensors', '.onnx', '.pt', '.pth', '.bin', '.env', '.json', '.jsonl',
    '.md', '.csv', '.tsv', '.ini', '.yaml', '.yml', '.toml', '.xml', '.py', '.js',
    '.ts', '.tsx', '.jsx', '.ipynb', '.sql', '.r', '.c', '.cpp', '.h', '.cs', '.go',
    '.rs', '.sh', '.ps1', '.bat', '.exe', '.dll', '.pyd', '.node', '.wasm'}
PRIVATE_PARTS = {'credentials', 'auth', 'sessions', 'session storage', 'local storage',
                 'network', 'history', '.ssh', '.aws', '.azure', '.gnupg'}
CACHE_SUFFIXES = {'', '.cache', '.dat', '.data', '.body', '.vsix', '.whl', '.tmp',
                  '.temp', '.log', '.idx', '.index', '.block', '.ldb', '.sst'}
PRIVATE_NAMES = {'id_rsa', 'id_ed25519', 'id_ecdsa', 'authorized_keys', 'known_hosts',
                 'passwd', 'passwords', 'wallet', 'cookies', 'login data', 'web data'}


def protected_path(path: Path) -> bool:
    text = str(path).casefold()
    for variable, fallback in (('WINDIR', 'C:/Windows'), ('ProgramFiles', 'C:/Program Files'),
                               ('ProgramFiles(x86)', 'C:/Program Files (x86)'), ('ProgramData', 'C:/ProgramData')):
        root = Path(os.environ.get(variable, fallback))
        if path == root or path.is_relative_to(root):
            return True
    if '$recycle.bin' in {p.casefold() for p in path.parts} or 'system volume information' in text:
        return True
    home = Path.home()
    for name in ('Desktop', 'Documents', 'Downloads', 'Pictures', 'Music', 'Videos', 'OneDrive', '.ssh', '.aws', '.azure', '.gnupg'):
        if path == home / name or path.is_relative_to(home / name):
            return True
    return False


def targets() -> list[Target]:
    local = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    candidates = [t for t in discover() if t.cleanable]
    for app, base in (('Chrome', local / 'Google/Chrome/User Data'), ('Edge', local / 'Microsoft/Edge/User Data')):
        try:
            if not safe_chain(base):
                continue
            for profile in base.iterdir():
                if profile.name == 'Default' or (profile.name.startswith('Profile ') and profile.name[8:].isdigit()):
                    for name in ('Cache', 'Code Cache', 'GPUCache'):
                        candidates.append(Target(app, '浏览器渲染缓存', profile / name))
        except OSError:
            pass
    candidates.extend((Target('pip', '下载缓存', local / 'pip/Cache'),
                       Target('npm', '下载缓存', local / 'npm-cache/_cacache')))
    # Never allow arbitrary TEMP, Windows Update, Recycle Bin, downloads,
    # package runtimes, plugin runtimes or model directories.
    return deduplicate([t for t in candidates if on_c(t.path) and not protected_path(t.path)
                        and t.path.is_dir() and safe_chain(t.path)])


def protected_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    name = path.name.casefold()
    return (path.suffix.casefold() in PERSONAL_SUFFIXES or path.suffix.casefold() not in CACHE_SUFFIXES or
            name in PRIVATE_NAMES or
            any(p.casefold() in PRIVATE_PARTS for p in relative.parts) or
            name.startswith(('auth', 'credential', '.env')) or 'token' in name)


def beneath(path,root):
    return (path.is_absolute() and root.is_absolute() and '..' not in path.parts
            and '..' not in root.parts and path != root and path.is_relative_to(root))


@dataclass(frozen=True)
class PlannedFile:
    path: Path
    root: Path
    size: int
    modified: int
    device: int
    inode: int
    cutoff: int


@dataclass
class Candidate:
    target: Target
    files: list[PlannedFile] = field(default_factory=list)
    excluded: int = 0
    issues: int = 0

    @property
    def size(self):
        return sum(f.size for f in self.files)

    @property
    def recommended(self):
        return bool(self.files) and not self.issues and '日志' not in self.target.kind and self.size >= 10 * 1024 * 1024

    @property
    def label(self):
        if not self.files:
            return '无需清理'
        if self.issues:
            return '先检查'
        return '推荐清理' if self.recommended else '按需清理'

    @property
    def reason(self):
        if not self.files:
            return '没有符合时间范围且通过保护检查的文件。'
        if self.issues:
            return '目录中存在无法读取或链接条目，请先检查；只允许预览中通过检查的文件。'
        if '日志' in self.target.kind:
            return '旧日志可能用于排查问题，需手动选择；正在排查故障时建议保留。'
        return '已知可再生成缓存；清理后可能重新下载或生成，首次打开可能稍慢。'


def scan_candidates(days, stop, progress=None):
    from concurrent.futures import ThreadPoolExecutor,as_completed
    days=max(7,int(days))
    cutoff=time.time_ns()-days*86400*1_000_000_000
    def work(target):
        last_progress=time.monotonic()
        candidate = Candidate(target)
        examined = eligible_bytes = 0
        if progress:
            progress(f'{target.app} / {target.path.name}')
        pending = [target.path]
        anchor=None
        while pending and not stop.is_set():
            folder=pending.pop()
            try:
                with Directory(folder,anchor) as entries:
                    if anchor is None:
                        anchor=entries.canonical
                    for item in entries:
                        if stop.is_set():
                            break
                        examined+=1
                        try:
                            if item.attrs & REPARSE:
                                candidate.issues+=1
                            elif item.is_dir:
                                if item.name.casefold() in PRIVATE_PARTS:
                                    candidate.excluded+=1
                                else:
                                    pending.append(Path(item.path))
                            elif item.modified>=cutoff or item.attrs & (1|2|4):
                                candidate.excluded+=1
                            else:
                                path=Path(item.path)
                                if protected_file(path,target.path):
                                    candidate.excluded+=1
                                else:
                                    # Only prospective preview files need a separate
                                    # link-count/identity check; not every entry.
                                    check=os.stat(path,follow_symlinks=False)
                                    if (check.st_nlink!=1 or check.st_ino!=item.inode
                                            or check.st_dev!=item.volume or check.st_size!=item.size
                                            or check.st_mtime_ns!=item.modified
                                            or getattr(check,'st_file_attributes',0)&(REPARSE|1|2|4)):
                                        candidate.excluded+=1
                                    else:
                                        candidate.files.append(PlannedFile(path,target.path,item.size,
                                            item.modified,item.volume,item.inode,cutoff))
                                        eligible_bytes+=item.size
                        except (OSError,ValueError):
                            candidate.issues+=1
                        if progress and time.monotonic()-last_progress>=.4:
                            last_progress=time.monotonic()
                            progress(f'{target.app} · {examined:,} 项 · {size(eligible_bytes)}')
            except OSError:
                candidate.issues+=1
        return candidate
    result=[]
    with ThreadPoolExecutor(max_workers=4,thread_name_prefix='cleanup-advice') as pool:
        futures=[pool.submit(work,target) for target in targets()]
        for future in as_completed(futures):
            if not future.cancelled():result.append(future.result())
            if stop.is_set():
                for pending in futures:pending.cancel()
    return sorted(result,key=lambda c:c.size,reverse=True)


def make_plan(candidates):
    allowed = {str(t.path).casefold() for t in targets()}
    plan, seen = [], set()
    for c in candidates:
        if str(c.target.path).casefold() not in allowed:
            continue
        for f in c.files:
            identity = (f.device, f.inode)
            if (f.root != c.target.path or not beneath(f.path,f.root)
                    or protected_path(f.path) or protected_file(f.path, f.root)
                    or f.modified >= min(f.cutoff, time.time_ns() - 7*86400*1_000_000_000) or identity in seen):
                continue
            seen.add(identity)
            plan.append(f)
    return tuple(plan)


def _delete_windows(f: PlannedFile):
    """Open once, validate the opened object, delete through that same handle.

    Final-path and identity checks prevent a directory swap from redirecting a
    previewed deletion to a different file. No pathname unlink follows checks.
    """
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE,ctypes.c_void_p]
    kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    class Info(ctypes.Structure):
        _fields_ = [('attrs',wintypes.DWORD),('created',wintypes.FILETIME),('accessed',wintypes.FILETIME),
                    ('modified',wintypes.FILETIME),('volume',wintypes.DWORD),('highSize',wintypes.DWORD),
                    ('lowSize',wintypes.DWORD),('links',wintypes.DWORD),('highId',wintypes.DWORD),('lowId',wintypes.DWORD)]
    # Deny concurrent writers while validating and deleting the opened object.
    handle = kernel.CreateFileW('\\\\?\\' + str(f.path),0x10000 | 0x80,1,None,3,0x00200000,None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = Info()
        if not kernel.GetFileInformationByHandle(handle,ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attrs & (REPARSE | 1 | 2 | 4 | 16) or info.links != 1:
            raise ValueError('文件属性或硬链接状态变化')
        actual_size = (info.highSize << 32) | info.lowSize
        actual_inode = (info.highId << 32) | info.lowId
        ns = (((info.modified.dwHighDateTime << 32) | info.modified.dwLowDateTime) - 116444736000000000) * 100
        if actual_size != f.size or actual_inode != f.inode or ns != f.modified or ns >= f.cutoff:
            raise ValueError('文件已变化，未删除')
        name = ctypes.create_unicode_buffer(32768)
        length = kernel.GetFinalPathNameByHandleW(handle,name,len(name),0)
        if not length or length >= len(name):
            raise ValueError('无法验证最终文件路径')
        final = name.value
        if final.startswith('\\\\?\\'):
            final = final[4:]
        if os.path.normcase(os.path.normpath(final)) != os.path.normcase(os.path.normpath(str(f.path))):
            raise ValueError('最终文件路径与预览不一致')
        # Confirm volume too through an independent path stat; if a concurrent
        # replacement changes the pathname we conservatively skip this item.
        current = os.stat(f.path, follow_symlinks=False)
        if current.st_dev != f.device or current.st_ino != f.inode or not safe_chain(f.path):
            raise ValueError('路径或文件身份变化')
        delete = wintypes.BOOLEAN(1)
        if not kernel.SetFileInformationByHandle(handle,4,ctypes.byref(delete),ctypes.sizeof(delete)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)


def execute_plan(plan, stop, progress=None):
    allowed = {str(t.path).casefold() for t in targets()}
    report = {'deleted_files':0,'deleted_bytes':0,'skipped_files':0,'items':[], 'cancelled':False}
    for index,f in enumerate(plan):
        if stop.is_set():
            report['cancelled'] = True
            break
        row = {'path':str(f.path),'size':f.size}
        try:
            if (str(f.root).casefold() not in allowed or not beneath(f.path,f.root)
                    or protected_path(f.path) or protected_file(f.path,f.root) or not safe_chain(f.path)
                    or f.modified >= min(f.cutoff, time.time_ns() - 7*86400*1_000_000_000)):
                raise ValueError('不满足白名单或保护条件')
            s = os.stat(f.path,follow_symlinks=False)
            if (s.st_size,s.st_mtime_ns,s.st_dev,s.st_ino,s.st_nlink) != (f.size,f.modified,f.device,f.inode,1):
                raise ValueError('扫描后文件已变化')
            if os.name != 'nt':
                raise ValueError('仅 Windows 支持经过句柄验证的清理')
            _delete_windows(f)
            report['deleted_files'] += 1
            report['deleted_bytes'] += f.size
            row['status'] = 'deleted'
        except (OSError,ValueError) as exc:
            report['skipped_files'] += 1
            row.update(status='skipped', reason=str(exc))
        report['items'].append(row)
        if progress and (index % 100 == 0 or index + 1 == len(plan)):
            progress(index + 1,len(plan))
    report['unprocessed_files'] = len(plan)-len(report['items'])
    return report


def path_advice(path, candidates):
    path = Path(path)
    if protected_path(path):
        return '受保护'
    if any(path == c.target.path or path.is_relative_to(c.target.path) for c in candidates):
        return '缓存'
    if any(c.target.path.is_relative_to(path) for c in candidates):
        return '含缓存'
    return '保留'


def candidate_summary(candidates):
    return [{'app':c.target.app,'path':str(c.target.path),'category':c.target.kind,
             'recommendation':c.label,'reason':c.reason,'eligible_bytes':c.size,
             'eligible_files':len(c.files),'excluded':c.excluded,'issues':c.issues} for c in candidates]
