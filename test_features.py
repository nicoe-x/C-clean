import csv
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cleaner import Target, Result, Entry
from features import load_preferences, save_preferences, preferences_path, path_key, export_results


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'LOCALAPPDATA': str(self.folder)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def result(self, app='Test'):
        target = Target(app, '渲染 / 下载缓存', self.folder / 'Cache')
        return Result(target, size=20 * 1024 * 1024, count=1,
                      eligible=[Entry(target.path / 'old', 20 * 1024 * 1024, 0)])

    def test_preferences_round_trip_without_selections(self):
        favorite = path_key(self.folder / 'Cache')
        save_preferences('30', {favorite})
        self.assertEqual(load_preferences(), {'days': '30', 'favorites': [favorite],'theme':'system'})
        self.assertNotIn('selected', preferences_path().read_text())

    def test_bad_preferences_are_ignored(self):
        path = preferences_path()
        path.parent.mkdir(parents=True)
        for data in ('not-json', '[]', '{"days": "-999", "favorites": "bad"}'):
            path.write_text(data)
            self.assertEqual(load_preferences(), {'days': '7', 'favorites': [],'theme':'system'})

    def test_csv_has_bom_and_neutralizes_formulas(self):
        path = self.folder / 'report.csv'
        export_results(path, [self.result('=WEBSERVICE("example")')], 7, {0})
        self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.reader(stream))
        self.assertTrue(rows[1][0].startswith("'="))
        self.assertEqual(rows[1][-3:], ['是', '7', '是'])

    def test_html_escapes_data_and_labels_incomplete_scan(self):
        path = self.folder / 'report.html'
        export_results(path, [self.result('<script>alert(1)</script>')], 30, complete=False)
        text = path.read_text(encoding='utf-8')
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)
        self.assertIn('扫描不完整', text)
        self.assertIn('30 天前', text)
        self.assertIn('推荐清理', text)

    def test_export_rejects_unknown_format(self):
        path = self.folder / 'report.exe'
        with self.assertRaises(ValueError):
            export_results(path, [self.result()], 7)
        self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
