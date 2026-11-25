from pathlib import Path
import tempfile
import tkinter as tk
import time
import types
import unittest

import cleaner
from disk_cleanup import Candidate,PlannedFile
from win11_ui import Button


class RoundedControlTests(unittest.TestCase):
    def test_disabled_click_and_keyboard_do_not_invoke(self):
        root=tk.Tk();root.withdraw()
        try:
            calls=[]
            button=Button(root,text='全选推荐项',command=lambda:calls.append(1),state='disabled')
            button.pack();root.update_idletasks()
            button.invoke();button._key();button._press(None);button._release(types.SimpleNamespace(x=0,y=0))
            self.assertEqual(calls,[])
            button.configure(state='normal')
            button._press(None);button._release(types.SimpleNamespace(x=0,y=0))
            self.assertEqual(calls,[1])
            button._key()
            self.assertEqual(calls,[1,1])
            self.assertEqual(button['state'],'normal')
        finally:root.destroy()

    def test_global_select_all_ignores_filters_and_preserves_protection(self):
        app=cleaner.App();app.root.withdraw()
        try:
            amount=20*1024*1024
            def row(app_name,kind='缓存',cleanable=True,skipped=0):
                t=cleaner.Target(app_name,kind,Path(f'C:/Test/{app_name}'),cleanable)
                return cleaner.Result(t,size=amount,count=1,eligible=[cleaner.Entry(t.path/'old.cache',amount,0)] if cleanable else [],skipped=skipped)
            app.results=[row('A'),row('B'),row('Logs','日志'),row('Model',cleanable=False),row('Check',skipped=1)]
            app.days.set('7');app.valid_scan=True;app.search.set('A');app.refresh()
            app.select_button.invoke()
            self.assertEqual(app.selected,{0,1})
            self.assertEqual(app.select_button['text'],'全选推荐项')
            app.valid_scan=False;app.refresh();app.selected.clear();app.select_button.invoke()
            self.assertEqual(app.selected,set())
            view=app.disk_panel.cleanup
            now=time.time_ns()
            candidates=[]
            for name,kind,issues in (('A','缓存',0),('B','缓存',0),('Logs','日志',0),('Check','缓存',1)):
                t=cleaner.Target(name,kind,Path(f'C:/Test/{name}'))
                f=PlannedFile(t.path/'old.cache',t.path,amount,0,1,len(candidates)+1,now)
                candidates.append(Candidate(t,files=[f],issues=issues))
            view.apply(candidates,7,True);view.select_button.invoke()
            self.assertEqual(view.selected,{0,1})
            self.assertEqual(view.select_button['text'],'全选推荐项')
            self.assertFalse(app.disk_panel.busy)
            view.invalidate('需刷新');view.select_button.invoke()
            self.assertFalse(view.selected)
        finally:app.root.destroy()


if __name__=='__main__':unittest.main()
