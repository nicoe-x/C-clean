import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from disk_scan import analyze, serialize
from disk_ui import export_disk


class DiskScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.stop = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, amount):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x' * amount)
        return p

    def test_rollup_largest_and_types(self):
        self.file('a.txt', 10)
        self.file('folder/b.bin', 30)
        self.file('folder/sub/c.TXT', 20)
        result = analyze(self.root, self.stop, top_n=2)
        self.assertEqual(result.total, 60)
        self.assertEqual(result.files, 3)
        self.assertEqual(result.folders[str(self.root / 'folder')].size, 50)
        self.assertEqual([f['size'] for f in result.largest], [30, 20])
        self.assertEqual(result.extensions['.txt'], {'size': 30, 'files': 2})
        self.assertFalse(result.cancelled)
        self.assertTrue(all(p.exists() for p in (self.root / 'a.txt', self.root / 'folder/b.bin')))

    def test_hard_links_count_once(self):
        original = self.file('file', 20)
        os.link(original, self.root / 'alias')
        result = analyze(self.root, self.stop)
        self.assertEqual(result.total, 20)
        self.assertEqual(result.files, 1)
        self.assertEqual(result.skip_counts['硬链接（已统计）'], 1)

    def test_junction_does_not_escape_scan(self):
        import subprocess
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'private').write_bytes(b'secret')
        scan_root = self.root / 'scan'
        scan_root.mkdir()
        link = scan_root / 'link'
        proc = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True)
        if proc.returncode:
            self.skipTest('No junction support')
        try:
            result = analyze(scan_root, self.stop)
            self.assertEqual(result.total, 0)
            self.assertEqual(result.skip_counts['链接 / 重解析点'], 1)
        finally:
            link.rmdir()

    def test_permission_failures_are_visible(self):
        (self.root / 'blocked').mkdir()
        from fast_fs import Directory
        original = Directory.__enter__
        def denied(directory):
            if str(directory.path).endswith('blocked'):
                raise PermissionError('test denial')
            return original(directory)
        with patch.object(Directory,'__enter__',denied):
            result = analyze(self.root, self.stop)
        self.assertEqual(result.skip_counts['无法读取'], 1)
        self.assertIn('test denial', result.issues[0]['detail'])

    def test_cancel_keeps_consistent_partial_results(self):
        self.file('file.bin', 10)
        self.file('folder/nested.bin', 20)
        def cancel(_):
            self.stop.set()
        result = analyze(self.root, self.stop, progress=cancel)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.total, sum(d['size'] for d in result.extensions.values()))
        self.assertEqual(result.files, sum(d['files'] for d in result.extensions.values()))
        self.assertTrue(serialize(result)['cancelled'])

    def test_no_delete_api_and_export_marks_partial(self):
        self.file('file.bin', 10)
        result = analyze(self.root, self.stop)
        result.cancelled = True
        for ext in ('csv', 'html'):
            path = self.root / ('export.' + ext)
            export_disk(path, result)
            text = path.read_text(encoding='utf-8-sig')
            self.assertIn('不完整' if ext == 'html' else 'False', text)
        self.assertNotIn('eligible', serialize(result))
        self.assertTrue((self.root / 'file.bin').exists())


if __name__ == '__main__':
    unittest.main()
