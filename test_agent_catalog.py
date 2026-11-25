import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import agent_catalog as catalog
import agent_discovery as discovery
import cleaner
import disk_cleanup


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='clearspace-catalog-')
        self.root = Path(self.temp.name)
        self.bases = {key:self.root/key for key in ('home', 'local', 'roaming')}
        for path in self.bases.values(): path.mkdir()
        self.paths_patch = patch.object(discovery, 'locations', return_value=self.bases)
        self.paths_patch.start()
        env = {key:'' for product in catalog.STATES for key in product.environments}
        self.env_patch = patch.dict(os.environ, env)
        self.env_patch.start()
        self.stop = threading.Event()

    def tearDown(self):
        self.env_patch.stop(); self.paths_patch.stop(); self.temp.cleanup()

    def file(self, path, content=b'cache data'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        old = time.time()-40*86400
        os.utime(path, (old, old))
        return path

    def test_catalog_has_sources_and_required_products(self):
        rows = catalog.products()
        names = {row['name'] for row in rows}
        self.assertEqual(len(names), len(rows))
        self.assertGreaterEqual(len(rows), 65)
        self.assertTrue({'OpenClaw', 'Hermes Agent', 'ZCode', 'WorkBuddy', '豆包', 'Kimi Code', 'Qwen Code', 'Gemini CLI', 'Cline'} <= names)
        for row in rows:
            self.assertTrue(row['paths'], row)
            self.assertTrue(all(s.startswith('https://') for s in row['sources']))

    def test_desktop_name_or_cache_name_alone_never_grants_cleanup(self):
        root = self.bases['roaming']/'WorkBuddy'
        self.file(root/'Cache/personal.dat')
        self.file(root/'sessions/chat.jsonl')
        targets = discovery.discover_agents()
        self.assertTrue(targets)
        self.assertTrue(all(not target.cleanable for target in targets))

    def test_all_desktop_catalog_rules_find_structured_renderer_cache(self):
        for app in catalog.DESKTOPS:
            root = self.bases['roaming']/app.aliases[0]
            self.file(root/'GPUCache/index')
            self.file(root/'Cache/Cache_Data/old.cache')
        targets = discovery.discover_agents()
        found = {target.app for target in targets if target.cleanable}
        self.assertTrue({app.name for app in catalog.DESKTOPS} <= found)

    def test_doubao_profiles_keep_chats_and_credentials(self):
        root = self.bases['local']/'Doubao/User Data'
        cache = self.file(root/'Default/Cache/Cache_Data/index')
        chat = self.file(root/'Default/IndexedDB/chat.log')
        cookie = self.file(root/'Default/Network/Cookies')
        token = self.file(root/'Default/Local Storage/token')
        targets = discovery.discover_agents()
        allowed = [t for t in targets if t.cleanable]
        self.assertEqual({t.path for t in allowed}, {cache.parent.parent})
        with patch.object(cleaner, 'discover', return_value=targets):
            cleaner.clean(cleaner.scan_many(allowed, 7, self.stop), self.stop)
        self.assertFalse(cache.exists())
        self.assertTrue(all(p.exists() for p in (chat, cookie, token)))

    def test_zcode_session_container_is_detected_without_deleting_state(self):
        root = self.bases['roaming']/'ZCode'
        self.file(root/'session/Code Cache/js/index')
        state = self.file(root/'session/Session Storage/state.log')
        targets = discovery.discover_agents()
        self.assertTrue(any(t.cleanable and t.path == root/'session/Code Cache' for t in targets))
        self.assertFalse(any(t.cleanable and state.is_relative_to(t.path) for t in targets))

    def test_mixed_agent_cache_tmp_and_workspaces_are_read_only(self):
        paths = (
            '.hermes/cache/documents/report.dat', '.hermes/cache/scratch/work.cache',
            '.hermes/sessions/chat.jsonl', '.openclaw/workspace/notes.md',
            '.openclaw/agents/main/sessions/chat.jsonl', '.gemini/tmp/project/chats/chat.json',
            '.qwen/tmp/project/work.cache', '.workbuddy/cache/runtime.dat',
            '.workbuddy/plugins/runtime.dat', '.kimi/sessions/chat.jsonl',
            '.nanobot/workspace/memory/notes.md', '.zeroclaw/workspace/tasks.dat',
            '.openfang/data/memory.db',
        )
        files = [self.file(self.bases['home']/p) for p in paths]
        targets = discovery.discover_agents()
        self.assertTrue(targets)
        for target in targets:
            result = cleaner.scan(target, 0, self.stop)
            self.assertFalse(target.cleanable)
            self.assertEqual(result.eligible, [])
            self.assertEqual(cleaner.advice(result).label, '建议保留')
        with patch.object(cleaner, 'discover', return_value=targets):
            self.assertEqual(cleaner.clean(cleaner.scan_many(targets, 0, self.stop), self.stop)['deleted_files'], 0)
        self.assertTrue(all(p.exists() for p in files))

    def test_diagnostic_logs_are_manual_and_profiles_are_separate(self):
        files = [self.file(self.bases['home']/p) for p in (
            '.hermes/logs/agent.log', '.hermes/profiles/work/logs/agent.log',
            '.openclaw-dev/logs/gateway.log', '.workbuddy/logs/app.log')]
        targets = discovery.discover_agents()
        logs = [t for t in targets if t.cleanable]
        self.assertEqual({t.path for t in logs}, {p.parent for p in files})
        for target in logs:
            result = cleaner.scan(target, 7, self.stop)
            self.assertEqual(cleaner.advice(result).label, '按需清理')

    def test_environment_override_is_statistics_only_even_with_logs(self):
        root = self.root/'custom'
        self.file(root/'logs/important.log')
        self.file(root/'cache/report.dat')
        with patch.dict(os.environ, {'HERMES_HOME':str(root), 'OPENCLAW_STATE_DIR':str(root)}):
            targets = discovery.discover_agents()
        self.assertEqual(len(targets), 1)
        self.assertFalse(targets[0].cleanable)

    def test_inaccessible_or_broken_mount_is_skipped(self):
        with patch.object(Path, 'is_dir', side_effect=OSError(649, 'Broken mount')):
            self.assertFalse(discovery.existing(Path('C:/Broken/Hermes')))
            self.assertEqual(discovery.discover_agents(), [])

    def test_nested_roots_do_not_double_count(self):
        root = self.bases['roaming']/'WorkBuddy'
        self.file(root/'GPUCache/index', b'12345')
        self.file(root/'User/globalStorage/saoudrizwan.claude-dev/tasks/chat.json', b'1234567')
        self.file(root/'settings.json', b'abc')
        results = cleaner.scan_many(discovery.discover_agents(), 7, self.stop)
        self.assertEqual(sum(r.size for r in results), 15)
        self.assertEqual(sum(r.count for r in results), 3)
        cline = next(r for r in results if r.target.app == 'Cline')
        self.assertFalse(cline.target.cleanable)

    def test_personal_documents_in_renderer_cache_stay_protected(self):
        root = self.bases['roaming']/'ZCode'
        self.file(root/'GPUCache/index')
        files = [self.file(root/'GPUCache'/name) for name in ('report.pdf', 'memory.md', 'settings.json', 'auth.dat', 'model.gguf')]
        targets = discovery.discover_agents()
        cache = next(t for t in targets if t.cleanable)
        result = cleaner.scan(cache, 7, self.stop)
        self.assertEqual({f.path.name for f in result.eligible}, {'index'})
        # Even a forged eligible file cannot bypass the execution-time guard.
        for path in files:
            info = path.stat(); result.eligible.append(cleaner.Entry(path, info.st_size, info.st_mtime_ns))
        with patch.object(cleaner, 'discover', return_value=targets): cleaner.clean([result], self.stop)
        self.assertTrue(all(p.exists() for p in files))

    def test_analysis_only_custom_parent_cannot_grant_cleanup(self):
        root = self.root/'unknown-agent'
        self.file(root/'cache/old.cache')
        target = cleaner.Target('自选目录', '应用数据（仅统计）', root, False)
        results = cleaner.scan_many(discovery.partition_targets([target]), 0, self.stop)
        self.assertEqual(results[0].eligible, [])
        self.assertNotIn(root, {t.path for t in discovery.discover_agents() if t.cleanable})

    def test_global_cleanup_does_not_accept_state_roots(self):
        root = self.bases['home']/'.hermes'
        self.file(root/'cache/scratch/work.cache')
        self.file(root/'logs/agent.log')
        with patch.object(disk_cleanup, 'discover', side_effect=discovery.discover_agents):
            targets = disk_cleanup.targets()
        self.assertNotIn(root, {t.path for t in targets})
        self.assertNotIn(root/'cache', {t.path for t in targets})
        self.assertIn(root/'logs', {t.path for t in targets})


if __name__ == '__main__': unittest.main()
