import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from cleaner import Target
import disk_cleanup as dc


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ai-cleaner-safety-')
        self.root = Path(self.temp.name)
        self.cache = self.root / 'Cache'
        self.cache.mkdir()
        self.target = Target('Test', '渲染缓存', self.cache)
        self.allowed = patch.object(dc,'targets',return_value=[self.target])
        self.allowed.start()
        self.stop = threading.Event()

    def tearDown(self):
        self.allowed.stop()
        self.temp.cleanup()

    def file(self,name,old=True):
        path=self.cache/name
        path.write_bytes(b'cache data')
        if old:
            timestamp=time.time()-40*86400
            os.utime(path,(timestamp,timestamp))
        return path

    def plan(self):
        return dc.make_plan(dc.scan_candidates(7,self.stop))

    def test_only_old_safe_cache_is_deleted_through_handle(self):
        old=self.file('old.cache')
        new=self.file('new.cache',False)
        personal=self.file('report.docx')
        secret=self.file('auth.json')
        plan=self.plan()
        self.assertEqual([f.path for f in plan],[old])
        report=dc.execute_plan(plan,self.stop)
        self.assertEqual(report['deleted_files'],1,report)
        self.assertFalse(old.exists())
        self.assertTrue(all(p.exists() for p in (new,personal,secret)))

    def test_file_changed_after_preview_is_preserved(self):
        path=self.file('old.cache')
        plan=self.plan()
        path.write_bytes(b'updated by app')
        report=dc.execute_plan(plan,self.stop)
        self.assertEqual(report['deleted_files'],0)
        self.assertTrue(path.exists())

    def test_same_size_and_time_replacement_is_preserved(self):
        path=self.file('old.cache')
        plan=self.plan()
        original=path.with_name('moved.cache')
        path.rename(original)
        path.write_bytes(b'cache data')
        os.utime(path,ns=(plan[0].modified,plan[0].modified))
        report=dc.execute_plan(plan,self.stop)
        self.assertEqual(report['deleted_files'],0)
        self.assertTrue(path.exists())
        self.assertTrue(original.exists())

    def test_new_hardlink_after_preview_is_preserved(self):
        path=self.file('old.cache')
        plan=self.plan()
        alias=self.root/'alias'
        os.link(path,alias)
        report=dc.execute_plan(plan,self.stop)
        self.assertEqual(report['deleted_files'],0)
        self.assertTrue(path.exists())

    def test_removed_allowlist_and_cancel_preserve_all_files(self):
        path=self.file('old.cache')
        plan=self.plan()
        with patch.object(dc,'targets',return_value=[]):
            report=dc.execute_plan(plan,self.stop)
        self.assertEqual(report['deleted_files'],0)
        self.stop.set()
        report=dc.execute_plan(plan,self.stop)
        self.assertTrue(report['cancelled'])
        self.assertEqual(report['unprocessed_files'],1)
        self.assertTrue(path.exists())

    def test_external_path_forged_into_plan_is_rejected(self):
        path=self.root/'private.cache'
        path.write_bytes(b'secret')
        s=path.stat()
        f=dc.PlannedFile(path,self.cache,s.st_size,s.st_mtime_ns,s.st_dev,s.st_ino,time.time_ns()+1)
        c=dc.Candidate(self.target,files=[f])
        self.assertEqual(dc.make_plan([c]),())
        report=dc.execute_plan([f],self.stop)
        self.assertEqual(report['deleted_files'],0)
        self.assertTrue(path.exists())

    def test_system_and_personal_roots_protected(self):
        for path in (Path(os.environ['WINDIR'])/'Temp/a.cache',Path.home()/'Documents/a.cache',Path.home()/'.ssh/id_rsa'):
            self.assertTrue(dc.protected_path(path),str(path))

    def test_unknown_formats_and_private_names_are_excluded(self):
        for name in ('personal.vhdx','notes.custom','id_ed25519','wallet','keys.pem'):
            self.file(name)
        self.assertEqual(self.plan(),())

    def test_open_writer_is_skipped(self):
        path=self.file('old.cache')
        plan=self.plan()
        with path.open('r+b'):
            report=dc.execute_plan(plan,self.stop)
        self.assertEqual(report['deleted_files'],0)
        self.assertTrue(path.exists())

    def test_junction_replacement_after_preview_is_skipped(self):
        import subprocess
        path=self.file('old.cache')
        plan=self.plan()
        moved=self.root/'moved'
        self.cache.rename(moved)
        other=self.root/'other'
        other.mkdir()
        private=other/'old.cache'
        private.write_bytes(b'cache data')
        os.utime(private,ns=(plan[0].modified,plan[0].modified))
        proc=subprocess.run(['cmd','/c','mklink','/J',str(self.cache),str(other)],capture_output=True)
        if proc.returncode:
            self.skipTest('Junction creation unavailable')
        try:
            report=dc.execute_plan(plan,self.stop)
            self.assertEqual(report['deleted_files'],0)
            self.assertTrue(private.exists())
            self.assertTrue((moved/'old.cache').exists())
        finally:
            self.cache.rmdir()

    def test_new_files_after_preview_never_join_deletion_plan(self):
        old=self.file('old.cache')
        plan=self.plan()
        new=self.file('new-but-backdated.cache')
        report=dc.execute_plan(plan,self.stop)
        self.assertEqual(report['deleted_files'],1)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())

    def test_parent_traversal_cannot_escape_allowlist(self):
        outside=self.root/'outside.cache'
        outside.write_bytes(b'private')
        timestamp=time.time()-40*86400
        os.utime(outside,(timestamp,timestamp))
        s=outside.stat()
        forged=self.cache/'..'/'outside.cache'
        f=dc.PlannedFile(forged,self.cache,s.st_size,s.st_mtime_ns,s.st_dev,s.st_ino,time.time_ns())
        self.assertEqual(dc.make_plan([dc.Candidate(self.target,files=[f])]),())
        self.assertEqual(dc.execute_plan([f],self.stop)['deleted_files'],0)
        self.assertTrue(outside.exists())


if __name__=='__main__':
    unittest.main()
