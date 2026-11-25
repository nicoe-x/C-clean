"""Windows AI cache inspector. Standard library only; scan is always read-only."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import queue
import stat
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

CACHE_NAMES = ('Cache', 'Code Cache', 'GPUCache', 'DawnCache', 'DawnGraphiteCache',
               'DawnWebGPUCache', 'GPUPersistentCache', 'GrShaderCache', 'ShaderCache',
               'CachedData', 'CachedExtensionVSIXs')
REPARSE = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)


def linked(path: Path) -> bool:
    s = path.lstat()
    return stat.S_ISLNK(s.st_mode) or bool(getattr(s, 'st_file_attributes', 0) & REPARSE)


def safe_chain(path: Path) -> bool:
    """Reject symlinks/junctions anywhere, including ancestors outside the cache."""
    try:
        return all(not linked(p) for p in (path, *path.parents))
    except OSError:
        return False


def on_c(path: Path) -> bool:
    return path.is_absolute() and path.drive.casefold() == 'c:'


@dataclass
class Target:
    app: str
    kind: str
    path: Path
    cleanable: bool = True
    excluded: tuple[Path, ...] = ()


@dataclass
class Entry:
    path: Path
    size: int
    modified: int


@dataclass
class Result:
    target: Target
    size: int = 0
    count: int = 0
    eligible: list[Entry] = field(default_factory=list)
    skipped: int = 0

    @property
    def reclaimable(self):
        return sum(e.size for e in self.eligible)


@dataclass(frozen=True)
class Advice:
    label: str
    reason: str
    effect: str
    rank: int


def advice(result: Result, days: int = 7) -> Advice:
    if not result.target.cleanable:
        if '模型' not in result.target.kind:
            return Advice('建议保留', '可能包含会话、配置、技能、工作文件或运行时，仅统计占用。',
                          '只清理独立列出的缓存和日志，保留此目录中的应用数据。', 4)
        return Advice('建议保留', '这是模型数据，不是普通临时缓存；工具仅统计，不提供删除。',
                      '删除模型会影响离线使用，并可能需要重新下载。', 4)
    if not result.eligible:
        return Advice('无需清理', f'没有符合当前「{days} 天前」条件的文件，或目录为空。',
                      '可以保留当前文件，无需为了清理而缩短时间范围。', 3)
    if result.skipped:
        return Advice('先检查', f'扫描中有 {result.skipped} 项无法读取或涉及链接，统计可能不完整。',
                      '先打开目录检查；清理时仍会跳过链接、变更和无权限文件。', 2)
    if '日志' in result.target.kind:
        return Advice('按需清理', '旧日志可释放空间，但可能仍用于排查崩溃、连接或调用问题。',
                      '删除后无法查看这些历史日志；正在排查问题时请保留。', 1)
    if days < 7:
        return Advice('按需清理', '当前时间范围包含较新的缓存，可能很快被应用再次使用。',
                      '应用可能重新生成或下载缓存；建议优先使用 7 天或更长范围。', 1)
    if result.reclaimable < 10 * 1024 * 1024:
        return Advice('按需清理', '可释放空间不足 10 MB，清理收益较小。',
                      '保留也不会占用太多空间；清理后缓存可能再次生成。', 1)
    effect = ('扩展安装包缓存会被删除，后续安装或更新扩展时可能重新下载。'
              if result.target.path.name == 'CachedExtensionVSIXs' else
              '应用会按需重建缓存；首次打开页面或界面可能稍慢。')
    return Advice('推荐清理', f'有 {size(result.reclaimable)} 缓存符合时间范围，可由应用重新生成。', effect, 0)


def deduplicate(targets: list[Target]) -> list[Target]:
    # Windows Store virtualization can expose one directory under two paths.
    # Path-string deduplication alone would double both sizes and deletion plans.
    seen = set()
    result = []
    for target in targets:
        try:
            s = target.path.stat()
            key = (s.st_dev, s.st_ino) if s.st_ino else str(target.path).casefold()
            if key not in seen:
                seen.add(key)
                result.append(target)
        except OSError:
            pass
    return result


def discover() -> list[Target]:
    from agent_discovery import discover_agents
    return discover_agents()


def scan(target: Target, days: int, stop: threading.Event) -> Result:
    from fast_fs import Directory
    from disk_cleanup import protected_file
    result=Result(target)
    cutoff=time.time_ns()-days*86400*1_000_000_000
    pending=[target.path]
    excluded={str(p).casefold() for p in target.excluded}
    anchor=None
    while pending and not stop.is_set():
        folder=pending.pop()
        try:
            with Directory(folder,anchor) as entries:
                if anchor is None:
                    anchor=entries.canonical
                for entry in entries:
                    if stop.is_set():break
                    if entry.attrs & REPARSE:
                        result.skipped+=1
                    elif entry.is_dir:
                        if str(entry.path).casefold() not in excluded:
                            pending.append(Path(entry.path))
                    else:
                        result.size+=entry.size
                        result.count+=1
                        if (target.cleanable and entry.modified<cutoff
                                and not entry.attrs & (1|2|4)
                                and not protected_file(Path(entry.path), target.path)):
                            result.eligible.append(Entry(Path(entry.path),entry.size,entry.modified))
        except OSError:
            result.skipped+=1
    return result


def scan_many(targets,days,stop,progress=None):
    from concurrent.futures import ThreadPoolExecutor,as_completed
    results=[]
    with ThreadPoolExecutor(max_workers=4,thread_name_prefix='cache-scan') as pool:
        futures={pool.submit(scan,t,days,stop):t for t in targets}
        for future in as_completed(futures):
            if future.cancelled():continue
            results.append(future.result())
            if progress:progress(len(results),len(targets),futures[future])
            if stop.is_set():
                for pending in futures:pending.cancel()
    return results


def clean(results: list[Result], stop: threading.Event) -> dict:
    from disk_cleanup import protected_file
    # Re-discover so callers cannot turn an arbitrary path into a deletion target.
    allowed = {str(t.path).casefold() for t in discover() if t.cleanable}
    report = {'deleted_files': 0, 'deleted_bytes': 0, 'skipped_files': 0, 'errors': []}
    for result in results:
        root = result.target.path
        if not result.target.cleanable or str(root).casefold() not in allowed or not safe_chain(root):
            report['skipped_files'] += len(result.eligible)
            continue
        for entry in result.eligible:
            if stop.is_set():
                return report
            try:
                if (not entry.path.is_relative_to(root) or not safe_chain(entry.path)
                        or protected_file(entry.path, root)):
                    report['skipped_files'] += 1
                    continue
                current = entry.path.stat()
                # A running app may have updated the file since the scan.
                if (not stat.S_ISREG(current.st_mode) or current.st_size != entry.size
                        or current.st_mtime_ns != entry.modified or current.st_nlink != 1
                        or getattr(current, 'st_file_attributes', 0) & (1|2|4|REPARSE)):
                    report['skipped_files'] += 1
                    continue
                entry.path.unlink()
                report['deleted_files'] += 1
                report['deleted_bytes'] += entry.size
            except OSError as exc:
                report['skipped_files'] += 1
                report['errors'].append({'path': str(entry.path), 'error': str(exc)})
    return report


def size(n: int) -> str:
    value = float(n)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024 or unit == 'TB':
            return f'{value:,.1f} {unit}'
        value /= 1024


def summary(results, days=7):
    return [dict(app=r.target.app, category=r.target.kind, path=str(r.target.path),
                 cleanable=r.target.cleanable, bytes=r.size, files=r.count,
                 eligible_bytes=r.reclaimable, eligible_files=len(r.eligible), skipped=r.skipped,
                 recommendation=advice(r, days).label, reason=advice(r, days).reason,
                 impact=advice(r, days).effect)
            for r in results]


def save_report(data, prefix='scan') -> Path:
    # A one-file executable unpacks __file__ into a temporary runtime folder.
    # Persist reports beside the actual executable, with a per-user fallback.
    base = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
    fallback = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'AI-Cache-Cleaner/reports'
    for folder in (base / 'reports', fallback):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f'{prefix}-{datetime.now():%Y%m%d-%H%M%S-%f}.json'
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return path
        except OSError:
            if folder == fallback:
                raise


def App():
    from cleaner_ui import App as Window
    return Window()


def main():
    parser = argparse.ArgumentParser(description='C 盘 AI 缓存管家')
    parser.add_argument('--scan', action='store_true', help='只读命令行扫描，输出 JSON')
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--self-test', action='store_true', help='打开窗口并执行只读扫描自检，完成后自动退出')
    args = parser.parse_args()
    if args.days < 0:
        parser.error('--days 必须 >= 0')
    if args.scan:
        results = [scan(t, args.days, threading.Event()) for t in discover()]
        if sys.stdout is not None:
            print(json.dumps(summary(results, args.days), ensure_ascii=False, indent=2))
        else:
            save_report({'days': args.days, 'targets': summary(results, args.days)})
    else:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('LocalTools.Clearspace.6')
        except (AttributeError, OSError):
            pass
        app = App()
        if args.self_test:
            import tempfile
            fixture = tempfile.TemporaryDirectory(prefix='ai-cache-selftest-')
            fixture_root = Path(fixture.name)
            (fixture_root / 'nested').mkdir()
            (fixture_root / 'nested/sample.bin').write_bytes(b'x' * 64)
            state = {'stage': 'agent'}
            app.days.set(str(args.days))
            app.start_scan()
            def finish_test():
                if app.busy or app.disk_panel.busy:
                    app.root.after(100, finish_test)
                    return
                if state['stage'] == 'agent':
                    state['stage'] = 'disk'
                    app.mode.set('disk')
                    app.switch_mode()
                    app.disk_panel.root_path = fixture_root
                    app.start_scan()
                    app.root.after(100, finish_test)
                    return
                disk_result = app.disk_panel.result
                disk_ok = bool(disk_result and disk_result.total == 64 and disk_result.files == 1)
                original_mode = app.theme_controller.mode
                app.theme_controller.set_mode('dark')
                app.root.update_idletasks()
                theme_ok = app.theme_controller.effective == 'dark'
                app.theme_controller.set_mode('light')
                theme_ok = theme_ok and app.theme_controller.effective == 'light'
                app.theme_controller.set_mode(original_mode)
                from agent_catalog import products
                save_report({'ok': app.valid_scan and disk_ok and theme_ok, 'frozen': bool(getattr(sys, 'frozen', False)),
                             'gui': True, 'icon_loaded': 'logo-48' in app.images,
                             'disk_analysis_self_test': disk_ok,
                             'theme_switch_self_test': theme_ok,
                             'catalog_products': len(products()),
                             'support_list_ui': hasattr(app, 'show_support'),
                             'global_cleanup_ui': hasattr(app.disk_panel,'cleanup'),
                             'global_cleanup_starts_unselected': not app.disk_panel.cleanup.selected,
                             'disk': app.disk_text.get(), 'apps': list(app.app_box['values']),
                             'targets': len(app.results), 'status': app.status.get()}, 'self-test')
                app.root.destroy()
                fixture.cleanup()
            app.root.after(100, finish_test)
        app.root.mainloop()


if __name__ == '__main__':
    sys.modules.setdefault('cleaner', sys.modules[__name__])
    main()
