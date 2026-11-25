from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import cleaner


class DiskUiTests(unittest.TestCase):
    def test_mode_switch_worker_drilldown_and_window_shutdown(self):
        app = cleaner.App()
        app.root.withdraw()
        try:
            self.assertEqual(app.active_mode, 'agent')
            app.mode.set('disk')
            app.switch_mode()
            self.assertEqual(app.active_mode, 'disk')
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / 'nested').mkdir()
                (root / 'nested/file.bin').write_bytes(b'x' * 64)
                app.disk_panel.root_path = root
                with patch('disk_ui.save_report', return_value=root / 'report.json'):
                    app.start_scan()
                    app.mode.set('agent')
                    app.switch_mode()
                    self.assertEqual(app.mode.get(), 'disk')
                    deadline = time.time() + 10
                    while app.disk_panel.busy and time.time() < deadline:
                        app.root.update()
                        time.sleep(.02)
                self.assertFalse(app.disk_panel.busy)
                self.assertEqual(app.disk_panel.result.total, 64)
                app.disk_panel.show_folder(str(root / 'nested'))
                self.assertEqual(app.disk_panel.current, str(root / 'nested'))
                app.disk_panel.up()
                self.assertEqual(app.disk_panel.current, str(root))
                # ttk.Frame.children must remain Tk's widget mapping, not the
                # analysis directory index (a past shutdown regression).
                self.assertTrue(all(hasattr(widget, 'destroy') for widget in app.disk_panel.children.values()))
                self.assertTrue((root / 'nested/file.bin').exists())
            app.switch_agent()
            self.assertEqual(app.active_mode, 'agent')
        finally:
            app.root.destroy()


if __name__ == '__main__':
    unittest.main()
