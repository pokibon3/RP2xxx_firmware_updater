"""書き込みモード (BOOTSEL) のドライブ RPI-RP2 / RP2350 の検出とコピー"""
from __future__ import annotations

import glob
import os
import string
import sys
import time
from dataclasses import dataclass

INFO_FILE = 'INFO_UF2.TXT'
OUT_FILE = 'firmware.uf2'


@dataclass(frozen=True)
class BootDrive:
    root: str
    chip: str      # 'RP2040' | 'RP2350'
    board: str

    @property
    def label(self) -> str:
        name = os.path.basename(self.root.rstrip('/\\')) or self.root
        return f'{name} ({self.chip})'


def _roots() -> list[str]:
    if sys.platform == 'win32':
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetErrorMode(0x0001 | 0x8000)  # 空のカードリーダー等でダイアログを出さない
        mask = k32.GetLogicalDrives()
        roots = []
        for i, c in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                r = f'{c}:\\'
                if k32.GetDriveTypeW(r) == 2:  # DRIVE_REMOVABLE
                    roots.append(r)
        return roots
    if sys.platform == 'darwin':
        return glob.glob('/Volumes/*/')
    user = os.environ.get('USER', '')
    return glob.glob(f'/media/{user}/*/') + glob.glob(f'/run/media/{user}/*/') + glob.glob('/media/*/')


def read_info(root: str) -> BootDrive | None:
    try:
        with open(os.path.join(root, INFO_FILE), encoding='ascii', errors='ignore') as f:
            text = f.read(4096)
    except OSError:
        return None
    board = ''
    for line in text.splitlines():
        if line.startswith('Board-ID:'):
            board = line.split(':', 1)[1].strip()
    if 'RP2350' in text:
        chip = 'RP2350'
    elif 'RP2' in text:          # RP2040: "Model: Raspberry Pi RP2" / "Board-ID: RPI-RP2"
        chip = 'RP2040'
    else:
        return None              # RP 以外の UF2 ブートローダー
    return BootDrive(root, chip, board or '?')


def find_drives() -> list[BootDrive]:
    return [d for d in map(read_info, _roots()) if d]


def wait_for_drive(timeout: float, cancel, exclude=()) -> BootDrive | None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if cancel.is_set():
            return None
        drives = [d for d in find_drives() if d.root not in exclude]
        if drives:
            time.sleep(0.5)   # マウント直後は書き込みが失敗することがある
            return drives[0]
        time.sleep(0.3)
    return None


def copy_uf2(drive: BootDrive, data: bytes, progress) -> None:
    """UF2 をドライブへ書き込む。progress(done, total) を呼ぶ。

    OS のキャッシュに溜めると進捗が実際の転送とずれるので、チャンクごとに fsync する。
    最後のブロックを受け取った時点でデバイスが再起動するため、その後のエラーは無視する。
    """
    path = os.path.join(drive.root, OUT_FILE)
    total, chunk = len(data), 64 * 1024
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_BINARY', 0))
    done = 0
    try:
        while done < total:
            n = os.write(fd, data[done:done + chunk])
            done += n
            if done < total:
                os.fsync(fd)
            progress(done, total)
        try:
            os.fsync(fd)
        except OSError:
            pass
    except OSError:
        if done < total:
            raise
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def wait_gone(drive: BootDrive, timeout: float) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if read_info(drive.root) is None:
            return True
        time.sleep(0.3)
    return False
