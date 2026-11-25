"""Metadata-only discovery; session, model and runtime roots stay read-only."""
from pathlib import Path
import re

from agent_catalog import DESKTOPS, STATES, EXTENSIONS, RENDER_CACHES, CHROMIUM_MARKERS, locations, state_roots, profile_name
from cleaner import Target, on_c, safe_chain, deduplicate


def path_key(path):
    return str(path).casefold()


def existing(path):
    try:
        return on_c(path) and '..' not in path.parts and path.is_dir() and safe_chain(path)
    except OSError:
        return False


def children(path):
    if not existing(path): return ()
    try: return tuple(p for p in path.iterdir() if existing(p))
    except OSError: return ()


def chromium_profile(path):
    for marker in CHROMIUM_MARKERS:
        file = path/marker
        try:
            if file.is_file() and safe_chain(file): return True
        except OSError: pass
    return False


def discover_agents():
    bases = locations()
    targets = []
    desktop_roots = []

    def data(app, root, model=False):
        if existing(root):
            targets.append(Target(app, '模型（仅统计）' if model else '应用数据（仅统计）', root, False))

    for app in DESKTOPS:
        for base in (bases['roaming'], bases['local']):
            for alias in app.aliases:
                root = base/alias
                if existing(root): desktop_roots.append((app.name, root))

    # Preserve Store-build support without searching unrelated package data.
    for package in children(bases['local']/'Packages'):
        if package.name.casefold().startswith(('openai.', 'anthropic.', 'claude')):
            for prefix in ('LocalCache/Roaming', 'LocalCache/Local', 'RoamingState'):
                for app in ('Codex', 'ChatGPT', 'Claude'):
                    root = package/prefix/app
                    if existing(root): desktop_roots.append((app, root))

    for app, root in desktop_roots:
        data(app, root)
        profiles = [root, root/'User Data', root/'EBWebView', root/'web/Codex', root/'web/ChatGPT']
        if app == 'ZCode': profiles.append(root/'session')
        profiles.extend(children(root/'Partitions'))
        for parent in tuple(profiles):
            if existing(parent):
                profiles.extend(p for p in children(parent) if profile_name(p.name))
        seen = set()
        recognized = False
        for profile in profiles:
            key = path_key(profile)
            if key in seen or not existing(profile): continue
            seen.add(key)
            if not chromium_profile(profile): continue
            recognized = True
            names = RENDER_CACHES
            if app in ('VS Code', 'Cursor', 'Windsurf', 'Trae', 'CodeBuddy', 'Qoder', 'Kiro', 'Antigravity', 'Void', 'VSCodium', 'PearAI'):
                names += ('CachedData', 'CachedExtensionVSIXs')
            for name in names:
                cache = profile/name
                if existing(cache): targets.append(Target(app, '渲染缓存', cache))
        if recognized and existing(root/'logs'):
            targets.append(Target(app, '日志（手动选择）', root/'logs'))

        # VS Code plugin data is not a cache. Give it its own read-only row.
        for name, extension, _ in EXTENSIONS:
            data(name, root/'User/globalStorage'/extension)

    for app in STATES:
        roots = state_roots(app, bases)
        if app.name == 'OpenClaw':
            roots.extend((p, False) for p in children(bases['home'])
                         if re.fullmatch(r'\.openclaw-[A-Za-z0-9_-]+', p.name))
        for root, redirected in tuple(roots):
            if not existing(root): continue
            if app.profiles and not redirected:
                roots.extend((p, False) for p in children(root/'profiles'))
        for root, redirected in roots:
            if not existing(root): continue
            data(app.name, root)
            if not redirected:
                for name in app.logs:
                    log = root/name
                    if existing(log): targets.append(Target(app.name, '日志（手动选择）', log))

    for app, relative in (('Ollama', '.ollama/models'), ('Hugging Face', '.cache/huggingface/hub'),
                          ('Whisper', '.cache/whisper'), ('LM Studio', '.lmstudio/models'),
                          ('ModelScope', '.cache/modelscope/hub'), ('Jan', '.jan')):
        data(app, bases['home']/relative, model=app != 'Jan')

    # Physical aliases are deduplicated before assigning exclusions. Read-only
    # parent rows omit child targets so each byte is counted once.
    return partition_targets(targets)


def partition_targets(targets):
    """Remove overlaps without allowing an analysis-only parent to grant deletion."""
    unique = {}
    for target in targets:
        key = path_key(target.path)
        if key not in unique or not target.cleanable: unique[key] = target
    result = deduplicate(list(unique.values()))
    for target in result:
        excluded = list(target.excluded)
        excluded.extend(other.path for other in result if other.path != target.path and other.path.is_relative_to(target.path))
        if not target.cleanable:
            excluded.extend(target.path/name for name in ('Application', 'Programs'))
        target.excluded = tuple(excluded)
    return result
