import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import cleaner
import disk_cleanup as dc


class GlobalCleanupUiTests(unittest.TestCase):
    def test_cancel_then_confirm_only_deletes_previewed_cache_and_invalidates_scans(self):
        with tempfile.TemporaryDirectory(prefix='ai-cleaner-ui-') as folder:
            cache=Path(folder)/'Cache'
            cache.mkdir()
            old=cache/'old.cache';old.write_bytes(b'old cache')
            document=cache/'personal.docx';document.write_bytes(b'private')
            timestamp=time.time()-40*86400
            for p in (old,document):os.utime(p,(timestamp,timestamp))
            target=cleaner.Target('Test','缓存',cache)
            with patch.object(dc,'targets',return_value=[target]):
                candidates=dc.scan_candidates(7,threading.Event())
                app=cleaner.App()
                app.root.withdraw()
                try:
                    app.mode.set('disk');app.switch_mode()
                    view=app.disk_panel.cleanup
                    view.apply(candidates,7,True)
                    view.selected={0};view.render()
                    with patch('global_cleanup_ui.confirm_plan',return_value=False) as confirm,patch('global_cleanup_ui.execute_plan') as execute:
                        view.start_clean()
                        self.assertEqual([f.path for f in confirm.call_args.args[1]],[old])
                        execute.assert_not_called()
                    self.assertTrue(old.exists())
                    app.valid_scan=True
                    with patch('global_cleanup_ui.confirm_plan',return_value=True),patch('global_cleanup_ui.save_report',return_value=Path(folder)/'report.json'):
                        view.start_clean()
                        deadline=time.time()+10
                        while app.disk_panel.busy and time.time()<deadline:
                            app.root.update();time.sleep(.02)
                    self.assertFalse(app.disk_panel.busy)
                    self.assertFalse(old.exists())
                    self.assertTrue(document.exists())
                    self.assertFalse(view.valid)
                    self.assertFalse(view.selected)
                    self.assertFalse(app.valid_scan)
                    self.assertEqual(str(view.clean_button['state']),'disabled')
                finally:
                    app.root.destroy()


if __name__=='__main__':
    unittest.main()
