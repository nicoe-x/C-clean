from pathlib import Path
import tempfile
import os
import features
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

import cleaner
from app_theme import DARK,LIGHT,LABELS
from features import load_preferences,save_preferences
from win11_ui import Button,round_window


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='clearspace-theme-')
        self.environment=patch.dict(os.environ,{'LOCALAPPDATA':str(Path(self.temp.name)/'local')})
        self.environment.start()
        self.path=patch('features.preferences_path',return_value=Path(self.temp.name)/'preferences.json')
        self.path.start()
        self.system=['light']
        self.reader=patch('app_theme.windows_theme',side_effect=lambda:self.system[0])
        self.reader.start()
        self.app=cleaner.App()
        self.app.root.withdraw()

    def tearDown(self):
        self.app.root.destroy()
        self.reader.stop();self.path.stop();self.environment.stop();self.temp.cleanup()

    def test_manual_override_live_follow_and_preserved_selection(self):
        app=self.app
        target=cleaner.Target('Test','缓存',Path('C:/Test/Cache'))
        app.results=[cleaner.Result(target,size=20*1024*1024,eligible=[cleaner.Entry(target.path/'old.cache',20*1024*1024,0)])]
        app.valid_scan=True;app.days.set('7');app.refresh();app.select_caches()
        selected=set(app.selected);rows=app.tree.get_children();results=app.results
        app.theme_label.set('深色');app.change_theme()
        self.assertEqual(app.theme_controller.effective,'dark')
        self.assertEqual(load_preferences()['theme'],'dark')
        self.assertEqual(ttk.Style(app.root).lookup('Treeview','foreground'),DARK['text'])
        self.assertEqual(str(app.tree.tag_configure('推荐清理','foreground')),DARK['text'])
        self.system[0]='light';app.theme_controller.check_system()
        self.assertEqual(app.theme_controller.effective,'dark')
        app.theme_label.set('跟随系统');app.change_theme()
        self.assertEqual(app.theme_controller.effective,'light')
        controller=app.theme_controller
        app.root.after_cancel(controller._timer)
        controller.interval=20;controller._poll()
        self.system[0]='dark'
        deadline=time.monotonic()+1
        while controller.effective!='dark' and time.monotonic()<deadline:
            app.root.update();time.sleep(.01)
        self.assertEqual(controller.effective,'dark')
        self.assertEqual(load_preferences()['theme'],'system')
        self.assertEqual(app.selected,selected)
        self.assertEqual(app.tree.get_children(),rows)
        self.assertIs(app.results,results)
        self.assertTrue(app.valid_scan)
        app.theme_label.set('浅色');app.change_theme()
        self.assertEqual(app.root.cget('background'),LIGHT['bg'])
        self.assertEqual(str(app.tree.tag_configure('推荐清理','foreground')),LIGHT['text'])
        self.assertEqual(tuple(app.theme_box['values']),tuple(LABELS.values()))

    def test_new_dialog_and_controls_inherit_dark_palette(self):
        app=self.app
        app.theme_label.set('深色');app.change_theme()
        dialog=tk.Toplevel(app.root)
        label=tk.Label(dialog,text='Test',bg='white',fg='#1c2935');label.pack()
        button=Button(dialog,text='取消');button.pack()
        round_window(dialog)
        app.root.update()
        self.assertEqual(label.cget('background'),DARK['surface'])
        self.assertEqual(label.cget('foreground'),DARK['text'])
        self.assertEqual(button._surface.get(20,16),(45,50,60))
        dialog.destroy()

    def test_preferences_migration_validation_and_preservation(self):
        self.assertEqual(load_preferences()['theme'],'system')
        save_preferences('30',set(),'dark')
        save_preferences('90',{'C:/Test/Cache'})
        self.assertEqual(load_preferences()['theme'],'dark')
        data='{"days":"7","favorites":[],"theme":"invalid"}'
        features.preferences_path().write_text(data)
        self.assertEqual(load_preferences()['theme'],'system')
        features.preferences_path().write_text('{"days":"30","favorites":[]}')
        self.assertEqual(load_preferences()['theme'],'system')


if __name__=='__main__':unittest.main()
