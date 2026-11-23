"""RP2040 / RP2350 ファームウェア書き込みツール (tkinter)

動作中のデバイスを USB リセット / 1200bps で書き込みモードに切り替え、
現れたドライブ (RPI-RP2 / RP2350) へ UF2 をコピーする。
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import device
import drive
import uf2
from version import __version__

APP_TITLE = 'RP2040 / RP2350 ファームウェア書き込み'
CONFIG_PATH = Path.home() / '.rp2xxx_updater.json'
FW_EXTS = ('.uf2', '.bin')
MAX_SCAN_FILES = 300

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # ドラッグ＆ドロップは無くても動く
    TkinterDnD = None


class Cancelled(Exception):
    pass


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f'{n} B'
    if n < 1024 * 1024:
        return f'{n / 1024:.1f} KB'
    return f'{n / 1048576:.2f} MB'


def scan_folder(folder: str) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('node_modules', 'CMakeFiles')]
        for fn in filenames:
            if fn.lower().endswith(FW_EXTS) and not fn.startswith('.'):
                found.append(os.path.join(dirpath, fn))
                if len(found) >= MAX_SCAN_FILES:
                    return found
    return found


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.devices: list[device.Device] = []
        self.drives: list[drive.BootDrive] = []
        self.files: list[str] = []
        self.base_dir: str | None = None
        self.fw: uf2.Firmware | None = None
        self.config = self._load_config()
        self.want_device_key: str | None = self.config.get('device')

        root.title(f'{APP_TITLE}  v{__version__}')
        root.minsize(640, 600)
        self._build()
        self._restore()
        self.root.after(50, self._pump)
        self._poll()
        root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------
    def _build(self):
        st = ttk.Style()
        st.configure('Title.TLabel', font=('', 16, 'bold'))
        st.configure('Head.TLabel', font=('', 13, 'bold'))
        st.configure('Sub.TLabel', foreground='gray50')
        st.configure('Big.TButton', font=('', 14, 'bold'), padding=(16, 8))

        main = ttk.Frame(self.root, padding=16)
        main.pack(fill='both', expand=True)
        main.columnconfigure(0, weight=1)

        head = ttk.Frame(main)
        head.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(head, text=APP_TITLE, style='Title.TLabel').pack(side='left')
        ttk.Label(head, text=f'v{__version__}', style='Sub.TLabel').pack(side='left', padx=(8, 0), pady=(4, 0))

        # ① デバイス
        f1 = ttk.Frame(main)
        f1.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        f1.columnconfigure(0, weight=1)
        ttk.Label(f1, text='① デバイス', style='Head.TLabel').grid(row=0, column=0, sticky='w')
        self.cb_dev = ttk.Combobox(f1, state='readonly')
        self.cb_dev.grid(row=1, column=0, sticky='ew', pady=(4, 2))
        self.cb_dev.bind('<<ComboboxSelected>>', self._on_device_selected)
        self.lbl_dev = ttk.Label(f1, text='', style='Sub.TLabel')
        self.lbl_dev.grid(row=2, column=0, sticky='w')

        # ② ファームウェア
        f2 = ttk.Frame(main)
        f2.grid(row=2, column=0, sticky='ew', pady=(0, 12))
        f2.columnconfigure(0, weight=1)
        ttk.Label(f2, text='② ファームウェア', style='Head.TLabel').grid(row=0, column=0, sticky='w')
        bar = ttk.Frame(f2)
        bar.grid(row=1, column=0, sticky='ew', pady=(4, 4))
        self.btn_fw = ttk.Button(bar, text='ファームウェアを選択…', command=self._choose_files)
        self.btn_fw.pack(side='left')
        self.btn_dir = ttk.Button(bar, text='フォルダから…', command=self._choose_folder)
        self.btn_dir.pack(side='left', padx=(8, 0))
        hint = '（ここへドラッグ＆ドロップも可）' if TkinterDnD else ''
        ttk.Label(bar, text=hint, style='Sub.TLabel').pack(side='left', padx=(8, 0))

        lf = ttk.Frame(f2)
        lf.grid(row=2, column=0, sticky='ew')
        lf.columnconfigure(0, weight=1)
        self.lst = tk.Listbox(lf, height=5, activestyle='none', exportselection=False)
        self.lst.grid(row=0, column=0, sticky='ew')
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.lst.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.lst.configure(yscrollcommand=sb.set)
        self.lst.bind('<<ListboxSelect>>', self._on_list_select)
        self.lbl_fw = ttk.Label(f2, text='ファームウェアが選択されていません', style='Sub.TLabel', justify='left')
        self.lbl_fw.grid(row=3, column=0, sticky='w', pady=(4, 0))

        # ③ 書き込み
        f3 = ttk.Frame(main)
        f3.grid(row=3, column=0, sticky='nsew')
        main.rowconfigure(3, weight=1)
        f3.columnconfigure(0, weight=1)
        f3.rowconfigure(4, weight=1)
        ttk.Label(f3, text='③ 書き込み', style='Head.TLabel').grid(row=0, column=0, sticky='w')
        bb = ttk.Frame(f3)
        bb.grid(row=1, column=0, sticky='w', pady=(4, 6))
        self.btn_write = ttk.Button(bb, text='書き込み開始', style='Big.TButton', command=self._start_write)
        self.btn_write.pack(side='left')
        self.btn_cancel = ttk.Button(bb, text='中止', command=self._on_cancel)
        self.btn_cancel.pack(side='left', padx=(8, 0))
        self.pb = ttk.Progressbar(f3, maximum=1000, mode='determinate')
        self.pb.grid(row=2, column=0, sticky='ew')
        pf = ttk.Frame(f3)
        pf.grid(row=3, column=0, sticky='ew', pady=(2, 6))
        pf.columnconfigure(0, weight=1)
        self.lbl_phase = ttk.Label(pf, text='待機中')
        self.lbl_phase.grid(row=0, column=0, sticky='w')
        self.lbl_nums = ttk.Label(pf, text='', style='Sub.TLabel')
        self.lbl_nums.grid(row=0, column=1, sticky='e')

        self.txt = ScrolledText(f3, height=10, wrap='word', state='disabled', relief='flat',
                                font=('Menlo' if sys.platform == 'darwin' else 'Consolas', 11))
        self.txt.grid(row=4, column=0, sticky='nsew')
        for tag, color in (('info', '#2f6fd0'), ('ok', '#1f9d55'), ('warn', '#c77700'), ('err', '#d03030'),
                           ('time', 'gray55')):
            self.txt.tag_configure(tag, foreground=color)

        if TkinterDnD:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)

        self._update_buttons()

    def _update_buttons(self):
        idle = not self.busy
        self.btn_write.configure(state='normal' if idle and self.fw else 'disabled')
        self.btn_cancel.configure(state='normal' if self.busy else 'disabled')
        for w in (self.btn_fw, self.btn_dir):
            w.configure(state='normal' if idle else 'disabled')
        self.cb_dev.configure(state='readonly' if idle else 'disabled')
        self.lst.configure(state='normal' if idle else 'disabled')

    def log(self, msg: str, level: str = ''):
        """どのスレッドからでも呼べる"""
        self.ui(self._log, msg, level)

    def _log(self, msg, level):
        self.txt.configure(state='normal')
        self.txt.insert('end', datetime.now().strftime('%H:%M:%S '), 'time')
        self.txt.insert('end', msg + '\n', level)
        self.txt.see('end')
        self.txt.configure(state='disabled')

    def progress(self, ratio: float, phase: str | None = None, nums: str | None = None):
        self.ui(self._progress, ratio, phase, nums)

    def _progress(self, ratio, phase, nums):
        self.pb['value'] = max(0, min(1, ratio)) * 1000
        if phase is not None:
            self.lbl_phase.configure(text=phase)
        if nums is not None:
            self.lbl_nums.configure(text=nums)

    def ui(self, fn, *args):
        self.q.put((fn, args))

    def _pump(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.root.after(50, self._pump)

    # ------------------------------------------------------------
    #  デバイス / ドライブの監視
    # ------------------------------------------------------------
    def _poll(self):
        try:
            self.devices = device.list_devices()
            self.drives = drive.find_drives()
        except Exception as e:  # 監視は止めない
            self.devices, self.drives = [], []
            print('poll error:', e, file=sys.stderr)
        self._refresh_device_ui()
        self.root.after(1000, self._poll)

    def _refresh_device_ui(self):
        labels = [d.label for d in self.devices]
        if list(self.cb_dev['values']) != labels:
            self.cb_dev['values'] = labels
        sel = self._selected_device()
        if sel is None and self.devices:
            # 前回選んだデバイスがあればそれ、無ければ先頭
            sel = next((d for d in self.devices if d.key == self.want_device_key), self.devices[0])
        if sel is not None:
            idx = self.devices.index(sel)
            if self.cb_dev.current() != idx:
                self.cb_dev.current(idx)
        elif self.cb_dev.get():
            self.cb_dev.set('')

        if self.drives:
            text = '書き込みモードのドライブ: ' + ', '.join(f'{d.label}  {d.root}' for d in self.drives)
        elif self.devices:
            text = '書き込み開始で自動的に書き込みモードへ切り替えます'
        else:
            text = 'デバイスが見つかりません（BOOTSEL ボタンを押しながら USB を挿しても書き込めます）'
        if self.lbl_dev.cget('text') != text:
            self.lbl_dev.configure(text=text)

    def _selected_device(self) -> device.Device | None:
        name = self.cb_dev.get()
        return next((d for d in self.devices if d.label == name), None)

    def _on_device_selected(self, _e=None):
        d = self._selected_device()
        if d:
            self.want_device_key = d.key
            self.config['device'] = d.key
            self._save_config()

    # ------------------------------------------------------------
    #  ファームウェア選択
    # ------------------------------------------------------------
    def _choose_files(self):
        init = self.config.get('dir') or str(Path.home())
        paths = filedialog.askopenfilenames(
            title='ファームウェアを選択', initialdir=init,
            filetypes=[('ファームウェア', '*.uf2 *.bin'), ('UF2', '*.uf2'), ('BIN', '*.bin'), ('すべて', '*')])
        if paths:
            self._set_files(list(paths), os.path.dirname(paths[0]) if len(paths) > 1 else None)
            self.config['dir'] = os.path.dirname(paths[0])
            self._save_config()

    def _choose_folder(self):
        init = self.config.get('dir') or str(Path.home())
        folder = filedialog.askdirectory(title='ファームウェアのフォルダを選択', initialdir=init, mustexist=True)
        if folder:
            self._open_folder(folder)

    def _open_folder(self, folder: str):
        files = scan_folder(folder)
        if not files:
            self.log(f'{folder} に .uf2 / .bin ファイルがありません', 'warn')
            return
        self.config['dir'] = folder
        self._save_config()
        self._set_files(files, folder)

    def _on_drop(self, e):
        if self.busy:
            return
        paths = list(self.root.tk.splitlist(e.data))
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self._open_folder(paths[0])
            return
        files = []
        for p in paths:
            if os.path.isdir(p):
                files += scan_folder(p)
            elif p.lower().endswith(FW_EXTS):
                files.append(p)
        if not files:
            self.log('.uf2 / .bin ファイルをドロップしてください', 'warn')
            return
        self._set_files(files, os.path.dirname(files[0]) if len(files) > 1 else None)

    def _set_files(self, files: list[str], base_dir: str | None, select: str | None = None):
        def mtime(p):
            try:
                return os.path.getmtime(p)
            except OSError:
                return 0
        self.files = sorted(set(files), key=mtime, reverse=True)  # 新しい順
        self.base_dir = base_dir
        self.lst.delete(0, 'end')
        for p in self.files:
            rel = os.path.relpath(p, base_dir) if base_dir else os.path.basename(p)
            when = datetime.fromtimestamp(mtime(p)).strftime('%m/%d %H:%M')
            self.lst.insert('end', f'{rel}    ({fmt_bytes(os.path.getsize(p)) if os.path.exists(p) else "?"}, {when})')
        target = select if select in self.files else (self.files[0] if self.files else None)
        if target:
            i = self.files.index(target)
            self.lst.selection_clear(0, 'end')
            self.lst.selection_set(i)
            self.lst.see(i)
            self._select_file(target)
        self.config['files'] = self.files[:MAX_SCAN_FILES]
        self.config['base_dir'] = base_dir
        self._save_config()

    def _on_list_select(self, _e=None):
        sel = self.lst.curselection()
        if sel and not self.busy:
            self._select_file(self.files[sel[0]])

    def _select_file(self, path: str):
        try:
            self.fw = uf2.load(path)
        except (OSError, uf2.FirmwareError) as e:
            self.fw = None
            self.lbl_fw.configure(text=f'読み込みエラー: {e}')
            self._update_buttons()
            return
        fw = self.fw
        chips = fw.target_chips()
        lo = min(b.addr for b in fw.blocks) if fw.blocks else 0
        hi = max(b.addr + len(b.data) for b in fw.blocks) if fw.blocks else 0
        when = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y/%m/%d %H:%M')
        target = '/'.join(chips) if fw.kind == 'UF2' else 'RP2040 / RP2350（書き込み時に変換）'
        self.lbl_fw.configure(text=(
            f'{fw.name}   {fw.kind} {fmt_bytes(len(fw.raw))}   更新 {when}\n'
            f'対象: {target}   ファミリー: {fw.family_names()}   範囲: 0x{lo:08x}–0x{hi:08x}'))
        self.config['file'] = path
        self._save_config()
        self._update_buttons()

    # ------------------------------------------------------------
    #  書き込み
    # ------------------------------------------------------------
    def _start_write(self):
        if self.busy or not self.fw:
            return
        self.busy = True
        self.cancel.clear()
        self._update_buttons()
        dev = self._selected_device()
        path = self.fw.path
        threading.Thread(target=self._write_thread, args=(path, dev), daemon=True).start()

    def _on_cancel(self):
        self.cancel.set()
        self.log('中止しています…', 'warn')

    def _write_thread(self, path: str, dev: device.Device | None):
        t0 = time.monotonic()
        try:
            self._write(path, dev, t0)
        except Cancelled:
            self.progress(0, '中止しました', '')
            self.log('中止しました', 'warn')
        except Exception as e:
            self.progress(1, 'エラー', '')
            self.log(f'エラー: {e}', 'err')
        finally:
            self.ui(self._write_done)

    def _write_done(self):
        self.busy = False
        self._update_buttons()

    def _check_cancel(self):
        if self.cancel.is_set():
            raise Cancelled()

    def _write(self, path: str, dev: device.Device | None, t0: float):
        fw = uf2.load(path)  # 書き込み直前に読み直す（ビルドし直した場合に備えて）
        self.log(f'ファームウェア: {path}', 'info')
        self.progress(0.01, '準備中…', '')

        bd = self._pick_drive(drive.find_drives(), fw)
        if bd is None:
            dev = self._wait_device_back(dev)
            if dev is not None:
                self.progress(0.02, '書き込みモードへ切り替え中…')
                device.enter_bootloader(dev, self.log)
                self.progress(0.03, 'ドライブを待っています…')
                bd = drive.wait_for_drive(30, self.cancel)
                self._check_cancel()
                if bd is None:
                    raise RuntimeError('書き込みモードのドライブ (RPI-RP2 / RP2350) が見つかりません')
            else:
                self.log('BOOTSEL ボタンを押しながら USB を挿してください。ドライブが現れるのを待っています…', 'warn')
                self.progress(0.03, 'BOOTSEL ボタンを押しながら USB を挿してください')
                bd = drive.wait_for_drive(180, self.cancel)
                self._check_cancel()
                if bd is None:
                    raise RuntimeError('書き込みモードのドライブが見つかりませんでした')

        self.log(f'ドライブ: {bd.root} ({bd.chip}, Board-ID: {bd.board})', 'info')
        lo, hi, nbytes = uf2.check(fw, bd.chip)
        data = uf2.to_uf2(fw, bd.chip)
        self.log(f'書き込み開始: {fw.name} → {bd.chip} (0x{lo:08x}–0x{hi:08x}, {fmt_bytes(nbytes)})', 'info')

        tc = time.monotonic()

        def on_progress(done, total):
            speed = done / max(1e-3, time.monotonic() - tc)
            self.progress(0.05 + 0.85 * done / total, 'コピー中…',
                          f'{fmt_bytes(done)} / {fmt_bytes(total)}   {speed / 1024:.0f} KB/s')

        drive.copy_uf2(bd, data, on_progress)
        self.progress(0.92, 'デバイスの再起動を待っています…', '')
        if not drive.wait_gone(bd, 30):
            raise RuntimeError('デバイスが再起動しませんでした（UF2 の内容が書き込まれていない可能性があります）')
        secs = time.monotonic() - t0
        self.progress(1, '完了', f'{fmt_bytes(len(data))} / {secs:.1f}s')
        self.log(f'完了しました。新しいファームウェアで起動しています ({secs:.1f}s)', 'ok')

    def _pick_drive(self, drives: list[drive.BootDrive], fw: uf2.Firmware) -> drive.BootDrive | None:
        if not drives:
            return None
        chips = fw.target_chips()
        for d in drives:
            if d.chip in chips:
                return d
        return drives[0]  # 合わなければ check() でエラーになる

    def _wait_device_back(self, dev: device.Device | None) -> device.Device | None:
        """前回の書き込み直後などでデバイスが再起動中なら、戻ってくるまで待つ"""
        if dev is None:
            return None
        t = time.monotonic()
        shown = False
        while time.monotonic() - t < 10:
            self._check_cancel()
            cur = next((d for d in device.list_devices() if d.key == dev.key), None)
            if cur is not None:
                if shown:
                    time.sleep(1.0)  # 列挙直後はシリアルが準備中のことがある
                return cur
            if drive.find_drives():
                return None
            if not shown:
                self.progress(0.01, 'デバイスの再接続を待っています…')
                shown = True
            time.sleep(0.3)
        self.log(f'{dev.port} が見つかりません', 'warn')
        return None

    # ------------------------------------------------------------
    #  設定
    # ------------------------------------------------------------
    def _load_config(self) -> dict:
        try:
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _save_config(self):
        try:
            CONFIG_PATH.write_text(json.dumps(self.config, ensure_ascii=False, indent=1), encoding='utf-8')
        except OSError:
            pass

    def _restore(self):
        files = [p for p in self.config.get('files', []) if os.path.isfile(p)]
        if files:
            self._set_files(files, self.config.get('base_dir'), self.config.get('file'))
        self.log(f'RP2xxx Updater v{__version__}')
        self.log('ファームウェアを選んで「書き込み開始」を押してください')

    def _on_close(self):
        if self.busy and not messagebox.askokcancel(APP_TITLE, '書き込み中です。終了しますか？'):
            return
        self.root.destroy()


def main():
    if TkinterDnD:
        try:
            root = TkinterDnD.Tk()
        except Exception:
            globals()['TkinterDnD'] = None
            root = tk.Tk()
    else:
        root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == '__main__':
    main()
