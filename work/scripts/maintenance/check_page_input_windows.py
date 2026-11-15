"""Check native Tk hit testing and input guards on an isolated Windows desktop."""
from pathlib import Path
import ctypes
from ctypes import wintypes
import json
import faulthandler
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / 'outputs/reports/page-input-windows'
HOME = ROOT / 'work/tests/page-input-windows/profile'
REPORT.mkdir(parents=True, exist_ok=True)
HOME.mkdir(parents=True, exist_ok=True)
user = ctypes.WinDLL('user32', use_last_error=True)
user.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
user.CreateDesktopW.restype = wintypes.HANDLE
user.SetThreadDesktop.argtypes = [wintypes.HANDLE]
desktop = user.CreateDesktopW('JMBatchPageInput', None, None, 0, 0x10000000, None)
assert desktop and user.SetThreadDesktop(desktop), ctypes.get_last_error()
sys.path.insert(0, str(ROOT / 'work/jmbatch'))
import tkinter as tk
from app import App
from ui_main import set_front_page

def pump(seconds=.15):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(.005)

def belongs(widget, parent):
    while widget is not None:
        if widget == parent:
            return True
        widget = widget.master
    return False

checks, errors = [], []
root = tk.Tk()
root.report_callback_exception = lambda *args: errors.append(str(args))
faulthandler.enable()
faulthandler.dump_traceback_later(45, exit=True)
with patch('updates.UpdateUI.startup'), patch('tkinter.messagebox.showinfo', side_effect=lambda *a, **k: errors.append(str(a))), patch('tkinter.messagebox.showwarning', side_effect=lambda *a, **k: errors.append(str(a))):
    app = App(root, HOME)
    try:
        for width, height in ((700, 900), (480, 700)):
            print('Checking', width, height, flush=True)
            root.geometry(f'{width}x{height}')
            pump()
            for library in (False, True, False):
                set_front_page(app, library, animate=False)
                pump()
                front = app.library_window.window if library else app.download_panel
                for x, y in ((2, 40), (front.winfo_width()-3, 80)):
                    target = root.winfo_containing(front.winfo_rootx()+x, front.winfo_rooty()+y)
                    assert belongs(target, front), (width, library, target)
                    target.event_generate('<ButtonPress-1>', x=1, y=1)
                    pump(.65)
                    target.event_generate('<ButtonRelease-1>', x=1, y=1)
                    target.event_generate('<MouseWheel>', delta=-120)
                    assert app.library_visible == library
                    assert not app.selecting and not app.library_window.batch_mode
                checks.append(f'{width}: front={library}, blank tap/hold/wheel stay on front')
            # A stale keyboard/mouse target on the hidden library is blocked by its bindtag.
            received = []
            app.library_window.tree.bind('<space>', lambda e: received.append('space'), add='+')
            app.library_window.tree.event_generate('<space>')
            assert not received
            set_front_page(app, True, animate=True)
            app.add_button.event_generate('<ButtonPress-1>', x=5, y=5)
            assert not any(isinstance(w, tk.Toplevel) for w in root.winfo_children())
            pump(1.2)
            assert app.library_visible and app.page_exchange is None
            set_front_page(app, False, animate=True)
            pump(1.2)
            app.add_button.event_generate('<ButtonPress-1>', x=5, y=5)
            pump()
            dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            assert len(dialogs) == 1
            dialogs[0].destroy()
            checks.append(f'{width}: transition blocks input; add button works afterward')
        assert not errors, errors
        (REPORT / 'result.json').write_text(json.dumps({'passed': True, 'checks': checks}, ensure_ascii=False, indent=2), encoding='utf-8')
        print('PASS', len(checks), 'Windows input checks')
    finally:
        app.close()
        faulthandler.cancel_dump_traceback_later()
