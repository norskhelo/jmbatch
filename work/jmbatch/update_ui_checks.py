"""Offline update-dialog checks using the real Tk controls and worker queue."""
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch


def check_manual(application, directory):
    from core import VERSION
    from updates import select_release
    ui, root = application.updates, application.root
    checks = []
    def check(value, label):
        assert value, label
        checks.append(label)
    def pump(seconds=.15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            root.update()
            time.sleep(.01)
    def until(predicate):
        end = time.monotonic() + 5
        while not predicate() and time.monotonic() < end:
            pump(.02)
        assert predicate(), 'worker did not settle'
    def shot(name):
        from PIL import ImageGrab
        pump()
        ImageGrab.grab(window=ui.dialog.winfo_id()).save(directory / (name + '.png'))
    name = 'JMBatch-9.0.0-Windows-x64.zip'
    answer = select_release([dict(body='Offline update fixture', assets=[dict(name=name, size=100,
        state='uploaded', browser_download_url='https://github.com/norskhelo/jmbatch/releases/download/test/'+name)])],ui.repo,VERSION,True)
    gate, finish = threading.Event(), threading.Event()
    attempts = []
    def prepare(home, release, current, cancel, status, progress):
        attempts.append(1)
        gate.wait(5)
        status('下载更新 · GitHub · 45% · 4.5/10.0 MB')
        progress(45,100)
        finish.wait(5)
        if cancel.is_set():
            raise InterruptedError('cancelled')
        if len(attempts) == 2:
            raise OSError('模拟网络失败，请检查网络后重试')
        status('下载更新 · GHFast · 0% · 0.0/10.0 MB')
        progress(0,100)
        status('正在校验更新包…')
        return {'fixture':True}
    ui.latest = None
    ui.automatic = False
    ui.seen_path.write_text(VERSION, encoding='utf-8')
    try:
        with patch('updates.fetch_bulletin',return_value=answer) as fetch:
            ui.show_and_check()
            ui.show_and_check()
            until(lambda:not ui.checking)
            pump()
            check(fetch.call_count==1, 'repeated check shares one request')
            popup=ui.dialog
            check(popup.winfo_exists() and not ui.progress_area.winfo_ismapped(), 'confirmation starts without a progress bar')
            shot('windows-confirm')
            ui.dismiss_button.invoke();pump()
            check(not popup.winfo_exists() and ui.latest is not None, 'cancel before confirmation keeps the discovered version')
            ui.show_and_check();pump();popup=ui.dialog
            with patch('update_install.prepare',side_effect=prepare):
                ui.download_button.invoke();pump()
                check(ui.dialog is popup and popup.winfo_exists(), 'confirmation stays open when download starts')
                check(ui.progress_area.winfo_ismapped() and str(ui.progress_bar['mode'])=='indeterminate', 'preparation shows an indeterminate progress bar')
                ui.download_button.invoke();ui.show_and_check();pump()
                check(len(attempts)==1 and ui.dialog is popup, 'repeat actions do not start another download or popup')
                gate.set();until(lambda:ui.download_fraction==45)
                check(float(ui.progress_bar['value'])==45, 'worker byte counts drive the visible progress bar')
                shot('windows-downloading')
                ui.dismiss_button.invoke();pump()
                check(ui.cancel.is_set() and popup.winfo_exists() and str(ui.dismiss_button['state'])=='disabled', 'cancel waits for the worker in the same popup')
                finish.set();until(lambda:not ui.downloading)
                check(ui.download_button['text']=='重试' and '已取消' in ui.status, 'cancelled download can retry')
                ui.download_button.invoke();until(lambda:not ui.downloading)
                check('模拟网络失败' in ui.status and ui.dialog is popup and ui.download_button['text']=='重试', 'failure remains visible and retryable in the same popup')
                shot('windows-failure')
                ui.download_button.invoke();until(lambda:not ui.downloading)
                check(ui.ready is not None and float(ui.progress_bar['value'])==100 and ui.download_button['text']=='安装并重启', 'verified download exposes installation in the same popup')
                shot('windows-ready')
                with patch('tkinter.messagebox.askyesno',return_value=False),patch('update_install.launch_helper') as install:
                    ui.download_button.invoke()
                    check(not install.called and popup.winfo_exists(), 'declining installation retains the verified package')
                ui.dismiss_button.invoke();pump();ui.show_and_check();pump()
                check(ui.download_button['text']=='安装并重启', 'reopening retains the verified install action')
        ui.close_update();ui.show_notes();pump()
        check('Offline update fixture' in ui.notes_area.get('1.0','end'), 'independent update notes remain available')
        ui.notes_window.destroy()
    finally:
        gate.set();finish.set()
        ui.downloading=False;ui.ready=None
        if ui.dialog is not None and ui.dialog.winfo_exists():ui.close_update()
    return checks


def run(directory):
    import tkinter as tk
    from app import App
    from updates import UpdateUI
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    root=tk.Tk();errors=[]
    root.report_callback_exception=lambda *args:errors.append(str(args))
    with patch.object(UpdateUI,'startup',lambda self:None):
        app=App(root,directory/'profile')
        root.geometry('700x900');root.update();app.settings_button.invoke();root.update()
        try:
            checks=check_manual(app,directory)
            assert not errors,errors
            (directory/'result.json').write_text(json.dumps({'passed':True,'checks':checks},ensure_ascii=False,indent=2),'utf-8')
        finally:
            app.engine.pause();app.download_covers.worker.close();root.destroy()


if __name__=='__main__':
    import sys
    run(Path(sys.argv[1]))
