"""Read-only directory metadata scanner. Never opens file contents or deletes data."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
import heapq
import os
from pathlib import Path
import stat
import threading
import time

from cleaner import REPARSE, safe_chain
from fast_fs import Directory


@dataclass
class Folder:
    path: Path
    parent: str | None
    size: int = 0
    files: int = 0
    skipped: int = 0
    scanned: bool = False


@dataclass
class DiskResult:
    root: Path
    folders: dict[str, Folder] = field(default_factory=dict)
    largest: list[dict] = field(default_factory=list)
    extensions: dict[str, dict] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    skip_counts: dict[str, int] = field(default_factory=dict)
    cancelled: bool = False
    seconds: float = 0
    stale: bool = False

    @property
    def total(self):
        return self.folders.get(str(self.root), Folder(self.root, None)).size

    @property
    def files(self):
        return self.folders.get(str(self.root), Folder(self.root, None)).files


def analyze(root: Path, stop: threading.Event, progress=None, top_n=200) -> DiskResult:
    root = Path(os.path.abspath(root))
    result = DiskResult(root)
    if not root.is_dir() or not safe_chain(root):
        raise ValueError('扫描根目录不可访问或涉及链接重定向')
    started = time.monotonic()
    result.folders[str(root)] = Folder(root, None)
    pending = [str(root)]
    seen_dirs, seen_files = set(), set()
    anchor = None
    reasons = Counter()
    largest = []
    total = files = serial = 0
    updated = 0.0

    def issue(node, path, reason, detail=''):
        node.skipped += 1
        reasons[reason] += 1
        if len(result.issues) < 500:
            result.issues.append({'path': str(path), 'reason': reason, 'detail': detail})

    while pending and not stop.is_set():
        key = pending.pop()
        node = result.folders[key]
        node.scanned = True
        try:
            with Directory(node.path,anchor) as entries:
                if anchor is None:
                    anchor=entries.canonical
                identity=entries.identity
                if identity[1] and identity in seen_dirs:
                    issue(node,node.path,'目录别名（已统计）')
                    continue
                seen_dirs.add(identity)
                for entry in entries:
                    if stop.is_set():
                        break
                    try:
                        if entry.attrs & REPARSE:
                            issue(node,entry.path,'链接 / 重解析点')
                            continue
                        if entry.is_dir:
                            result.folders[entry.path]=Folder(Path(entry.path),key)
                            pending.append(entry.path)
                        else:
                            identity=(entry.volume,entry.inode)
                            if entry.inode and identity in seen_files:
                                issue(node,entry.path,'硬链接（已统计）')
                                continue
                            if entry.inode:
                                seen_files.add(identity)
                            node.size += entry.size
                            node.files += 1
                            total += entry.size
                            files += 1
                            ext = os.path.splitext(entry.name)[1].casefold() or '（无扩展名）'
                            group = result.extensions.setdefault(ext, {'size': 0, 'files': 0})
                            group['size'] += entry.size
                            group['files'] += 1
                            serial += 1
                            record = (entry.size, serial, entry.path, entry.modified/1_000_000_000)
                            if len(largest) < top_n:
                                heapq.heappush(largest, record)
                            elif top_n and record[0] > largest[0][0]:
                                heapq.heapreplace(largest, record)
                    except OSError as exc:
                        issue(node, entry.path, '无法读取', str(exc))
                    now = time.monotonic()
                    if progress and now - updated >= .25:
                        updated = now
                        progress({'files': files, 'folders': len(result.folders), 'bytes': total, 'path': str(node.path), 'skipped': sum(reasons.values()),'seconds':now-started})
        except OSError as exc:
            issue(node, node.path, '无法读取', str(exc))
    # Parents are inserted before descendants. Reverse insertion order rolls up
    # all visited data correctly, including when the walk was cancelled.
    for node in reversed(list(result.folders.values())):
        if node.parent is not None:
            parent = result.folders[node.parent]
            parent.size += node.size
            parent.files += node.files
            parent.skipped += node.skipped
    result.largest = [{'path': path, 'size': amount, 'modified': modified}
                      for amount, _, path, modified in sorted(largest, reverse=True)]
    result.skip_counts = dict(reasons)
    result.cancelled = stop.is_set()
    result.seconds = time.monotonic() - started
    return result


def serialize(result):
    return {'mode': 'disk-analysis', 'root': str(result.root), 'cancelled': result.cancelled, 'stale':result.stale,
            'seconds': result.seconds, 'bytes': result.total, 'files': result.files,
            'folders': [{'path': str(n.path), 'parent': n.parent, 'bytes': n.size,
                         'files': n.files, 'skipped': n.skipped, 'scanned': n.scanned} for n in result.folders.values()],
            'largest_files': result.largest, 'extensions': result.extensions,
            'skip_counts': result.skip_counts, 'issues_sample': result.issues,
            'notes': '只读分析。逻辑大小；硬链接按首次遇到路径计入；别名及重解析点跳过；不可读项不提权。'}
