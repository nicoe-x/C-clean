"""Local preferences and portable, read-only scan exports."""
import csv
import html
import json
import os
from pathlib import Path
from datetime import datetime

from cleaner import summary, size


def preferences_path():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'AI-Cache-Cleaner/preferences.json'


def load_preferences():
    default = {'days': '7', 'favorites': [], 'theme':'system'}
    try:
        path = preferences_path()
        if path.stat().st_size > 1024 * 1024:
            return default
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return default
        days = str(data.get('days', '7'))
        favorites = data.get('favorites', [])
        theme=data.get('theme','system')
        return {'days': days if days in ('0', '1', '7', '30', '90') else '7',
                'favorites': [p for p in favorites if isinstance(p, str)][:2000] if isinstance(favorites, list) else [],
                'theme':theme if theme in ('system','light','dark') else 'system'}
    except (OSError, ValueError, TypeError):
        return default


def save_preferences(days, favorites, theme=None):
    if theme is None:theme=load_preferences()['theme']
    if theme not in ('system','light','dark'):theme='system'
    path = preferences_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'days': str(days), 'favorites': sorted(favorites),'theme':theme}, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def path_key(path):
    return os.path.normcase(os.path.normpath(str(path)))


def csv_cell(value):
    # CSV may be opened in Excel; paths and application names must remain text.
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def export_results(path, results, days, selected=(), complete=True):
    path = Path(path)
    rows = summary(results, days)
    selected = set(selected)
    if path.suffix.lower() == '.csv':
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('应用', '目录', '类型', '清理建议', '建议原因', '清理影响', '总字节', '可清理字节', '文件数', '符合范围文件数', '跳过项', '已选择', '时间范围（天）', '扫描完整'))
            for i, row in enumerate(rows):
                writer.writerow([csv_cell(row[k]) for k in ('app', 'path', 'category', 'recommendation', 'reason', 'impact', 'bytes', 'eligible_bytes', 'files', 'eligible_files', 'skipped')] + ['是' if i in selected else '否', days, '是' if complete else '否'])
    elif path.suffix.lower() == '.html':
        esc = lambda x: html.escape(str(x), quote=True)
        body = []
        for i, row in enumerate(rows):
            body.append(f'<tr><td>{esc(row["app"])}<small>{esc(row["path"])}</small></td><td>{esc(row["recommendation"])}</td><td>{esc(size(row["bytes"]))}</td><td>{esc(size(row["eligible_bytes"]))}</td><td>{esc(row["reason"])}<small>{esc(row["impact"])}</small></td><td>{"已选" if i in selected else "—"}</td></tr>')
        path.write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI 缓存扫描报告</title>
<style>body{{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#f3f6fb;color:#17263c;margin:0;padding:40px}}main{{max-width:1400px;margin:auto}}h1{{margin-bottom:8px}}p,small{{color:#64748b}}.cards{{display:flex;gap:16px;margin:24px 0}}.card{{background:white;padding:20px;flex:1;border-radius:12px}}b{{display:block;font-size:28px;margin-top:8px}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:16px;text-align:left;border-bottom:1px solid #e3eaf4;vertical-align:top}}th{{background:#e8eef8}}small{{display:block;margin-top:8px;overflow-wrap:anywhere;font-size:12px}}@media print{{body{{padding:0}}.card{{border:1px solid #ddd}}}}</style>
<main><h1>AI 缓存扫描报告</h1><p>{datetime.now():%Y-%m-%d %H:%M} · C 盘 / 当前用户 · {days} 天前最后修改 · {"扫描完整" if complete else "扫描不完整 / 时间范围已更改，请重新扫描"}</p>
<div class="cards"><div class="card">已发现占用<b>{esc(size(sum(r.size for r in results)))}</b></div><div class="card">符合范围可清理<b>{esc(size(sum(r.reclaimable for r in results)))}</b></div><div class="card">已选择<b>{esc(size(sum(r.reclaimable for i,r in enumerate(results) if i in selected)))}</b></div></div>
<p>建议来自目录类型、文件年龄和大小，不检测应用运行状态。报告只供查看；模型不参与清理。共 {len(rows)} 个目录，跳过 {sum(r.skipped for r in results)} 项。</p>
<table><thead><tr><th>应用 / 目录</th><th>建议</th><th>占用</th><th>可清理</th><th>原因 / 影响</th><th>选择</th></tr></thead><tbody>{''.join(body)}</tbody></table></main></html>''', encoding='utf-8')
    else:
        raise ValueError('请选择 .html 或 .csv 格式')
    return path
