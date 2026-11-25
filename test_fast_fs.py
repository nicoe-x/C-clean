import os
from pathlib import Path
import tempfile
import unittest

from fast_fs import Directory,REPARSE


class NativeMetadataTests(unittest.TestCase):
    def test_multi_batch_names_identity_and_time_match_os_stat(self):
        with tempfile.TemporaryDirectory(prefix='cache-native-test-') as folder:
            root=Path(folder)
            for i in range(900):
                (root/f'{i:04}-long-filename-for-batch.cache').touch()
            special=root/'中文 🧹 文件.cache'
            special.write_bytes(b'cache')
            os.link(special,root/'hardlink.cache')
            with Directory(root) as stream:
                rows=list(stream)
                self.assertEqual(stream.identity,(root.stat().st_dev,root.stat().st_ino))
            self.assertEqual(len(rows),902)
            self.assertEqual(len({e.name for e in rows}),902)
            for e in rows:
                s=os.stat(e.path,follow_symlinks=False)
                self.assertEqual((e.size,e.modified,e.inode,e.volume),(s.st_size,s.st_mtime_ns,s.st_ino,s.st_dev))
            by_name={e.name:e for e in rows}
            self.assertEqual(by_name[special.name].inode,by_name['hardlink.cache'].inode)

    def test_directory_anchor_rejects_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            left=root/'allowed';right=root/'outside'
            left.mkdir();right.mkdir()
            with Directory(left) as stream:anchor=stream.canonical
            with self.assertRaises(OSError):
                with Directory(right,anchor):pass

    def test_fallback_returns_same_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'file.cache';path.write_bytes(b'cache')
            stream=Directory(folder)
            stream.native=False
            with stream:rows=list(stream)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0].inode,path.stat().st_ino)
            self.assertEqual(rows[0].size,5)


if __name__=='__main__':unittest.main()
