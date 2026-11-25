import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import cleaner


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cache = self.root / 'Cache'
        self.cache.mkdir()
        self.target = cleaner.Target('Test', 'cache', self.cache)
        self.stop = threading.Event()

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, old=True):
        path = self.cache / name
        path.write_bytes(b'cache data')
        if old:
            stamp = time.time() - 20 * 86400
            os.utime(path, (stamp, stamp))
        return path

    def test_age_and_only_selected_files_deleted(self):
        old = self.file('old')
        new = self.file('new', False)
        result = cleaner.scan(self.target, 7, self.stop)
        self.assertEqual(result.count, 2)
        self.assertEqual(len(result.eligible), 1)
        with patch.object(cleaner, 'discover', return_value=[self.target]):
            report = cleaner.clean([result], self.stop)
        self.assertEqual(report['deleted_files'], 1)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_modified_file_is_preserved(self):
        path = self.file('changed')
        result = cleaner.scan(self.target, 7, self.stop)
        path.write_bytes(b'new data from a running app')
        with patch.object(cleaner, 'discover', return_value=[self.target]):
            report = cleaner.clean([result], self.stop)
        self.assertEqual(report['deleted_files'], 0)
        self.assertTrue(path.exists())

    def test_unrecognized_root_is_never_deleted(self):
        path = self.file('old')
        result = cleaner.scan(self.target, 7, self.stop)
        with patch.object(cleaner, 'discover', return_value=[]):
            report = cleaner.clean([result], self.stop)
        self.assertEqual(report['deleted_files'], 0)
        self.assertTrue(path.exists())

    def test_model_is_read_only(self):
        path = self.file('model')
        self.target.cleanable = False
        result = cleaner.scan(self.target, 0, self.stop)
        self.assertEqual(result.size, 10)
        self.assertEqual(result.eligible, [])
        s = path.stat()
        result.eligible.append(cleaner.Entry(path, s.st_size, s.st_mtime_ns))
        with patch.object(cleaner, 'discover', return_value=[self.target]):
            report = cleaner.clean([result], self.stop)
        self.assertEqual(report['deleted_files'], 0)
        self.assertTrue(path.exists())

    def test_forged_outside_file_is_preserved(self):
        outside = self.root / 'credential'
        outside.write_bytes(b'secret')
        s = outside.stat()
        result = cleaner.Result(self.target, eligible=[cleaner.Entry(outside, s.st_size, s.st_mtime_ns)])
        with patch.object(cleaner, 'discover', return_value=[self.target]):
            report = cleaner.clean([result], self.stop)
        self.assertEqual(report['deleted_files'], 0)
        self.assertTrue(outside.exists())

    def test_junction_is_not_followed(self):
        import subprocess
        destination = self.root / 'private'
        destination.mkdir()
        secret = destination / 'token'
        secret.write_bytes(b'secret')
        junction = self.cache / 'junction'
        proc = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(destination)], capture_output=True)
        if proc.returncode:
            self.skipTest('Junction creation unavailable')
        try:
            result = cleaner.scan(self.target, 0, self.stop)
            self.assertEqual(result.count, 0)
            self.assertEqual(result.skipped, 1)
            self.assertFalse(cleaner.safe_chain(junction / 'token'))
            with patch.object(cleaner, 'discover', return_value=[self.target]):
                cleaner.clean([result], self.stop)
            self.assertTrue(secret.exists())
        finally:
            junction.rmdir()

    def test_cancel_does_not_delete(self):
        path = self.file('old')
        result = cleaner.scan(self.target, 0, self.stop)
        self.stop.set()
        with patch.object(cleaner, 'discover', return_value=[self.target]):
            report = cleaner.clean([result], self.stop)
        self.assertEqual(report['deleted_files'], 0)
        self.assertTrue(path.exists())

    def test_c_drive_boundary(self):
        self.assertTrue(cleaner.on_c(Path('C:/Users/example/Cache')))
        self.assertFalse(cleaner.on_c(Path('F:/Cache')))
        self.assertFalse(cleaner.on_c(Path('Cache')))

    def test_same_directory_is_counted_once(self):
        alias = cleaner.Target('Alias', 'cache', self.cache / '..' / 'Cache')
        targets = cleaner.deduplicate([self.target, alias])
        self.assertEqual(targets, [self.target])

    def test_frozen_reports_persist_beside_executable(self):
        with patch.object(cleaner.sys, 'frozen', True, create=True), patch.object(cleaner.sys, 'executable', str(self.root / 'cleaner.exe')):
            report = cleaner.save_report({'test': True})
        self.assertEqual(report.parent, self.root / 'reports')
        self.assertIn('true', report.read_text(encoding='utf-8'))

    def test_report_falls_back_if_executable_folder_is_unwritable(self):
        # A file at the reports path simulates an unavailable output directory.
        (self.root / 'reports').write_text('blocked')
        with patch.object(cleaner.sys, 'frozen', True, create=True), patch.object(cleaner.sys, 'executable', str(self.root / 'cleaner.exe')), patch.dict(os.environ, {'LOCALAPPDATA': str(self.root / 'local')}):
            report = cleaner.save_report({'test': True})
        self.assertEqual(report.parent, self.root / 'local/AI-Cache-Cleaner/reports')

    def advice_result(self, kind='渲染 / 下载缓存', amount=20 * 1024 * 1024, cleanable=True, skipped=0):
        target = cleaner.Target('Test', kind, self.cache, cleanable)
        return cleaner.Result(target, size=amount, count=1,
                              eligible=[cleaner.Entry(self.cache / 'old', amount, 0)] if cleanable else [], skipped=skipped)

    def test_recommendation_preserves_models_and_logs(self):
        self.assertEqual(cleaner.advice(self.advice_result(cleanable=False)).label, '建议保留')
        self.assertEqual(cleaner.advice(self.advice_result(kind='日志（手动选择）')).label, '按需清理')
        self.assertEqual(cleaner.advice(self.advice_result()).label, '推荐清理')

    def test_recommendation_avoids_recent_small_and_incomplete_caches(self):
        result = self.advice_result()
        self.assertEqual(cleaner.advice(result, 0).label, '按需清理')
        self.assertEqual(cleaner.advice(self.advice_result(amount=1024)).label, '按需清理')
        self.assertEqual(cleaner.advice(self.advice_result(skipped=1)).label, '先检查')
        result.eligible.clear()
        self.assertEqual(cleaner.advice(result).label, '无需清理')

    def test_report_recommendations_follow_chosen_age(self):
        result = self.advice_result()
        self.assertEqual(cleaner.summary([result], 7)[0]['recommendation'], '推荐清理')
        self.assertEqual(cleaner.summary([result], 0)[0]['recommendation'], '按需清理')


if __name__ == '__main__':
    unittest.main()
