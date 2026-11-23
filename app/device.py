"""動作中のデバイスを書き込みモード (BOOTSEL) へ切り替える

- pico-sdk の Reset インターフェース (class 0xff / subclass 0 / protocol 1) があれば USB リセット
- なければ USB シリアルを 1200bps で開閉（pico-sdk stdio_usb / Arduino-Pico 共通）
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import serial
from serial.tools import list_ports

# RP2040 / RP2350 搭載ボードでよく使われる USB ベンダー ID
RP_VIDS = {
    0x2E8A,  # Raspberry Pi
    0x239A,  # Adafruit
    0x1B4F,  # SparkFun
    0x2886,  # Seeed
    0x16D0,  # MCS (Pimoroni 等)
}
RPI_VID = 0x2E8A
DEBUGPROBE_PID = 0x000C

RESET_CLASS, RESET_SUBCLASS, RESET_PROTOCOL = 0xFF, 0x00, 0x01
RESET_REQUEST_BOOTSEL = 0x01


@dataclass(frozen=True)
class Device:
    port: str
    vid: int
    pid: int
    serial_number: str | None
    product: str

    @property
    def key(self) -> str:
        """再接続しても同じデバイスを選び直すための識別子"""
        return f'{self.vid:04x}:{self.pid:04x}:{self.serial_number or self.port}'

    @property
    def label(self) -> str:
        sn = f'  [{self.serial_number}]' if self.serial_number else ''
        return f'{self.product}  —  {self.port}{sn}'


def list_devices() -> list[Device]:
    devs = []
    for p in list_ports.comports():
        if p.vid is None or p.vid not in RP_VIDS:
            continue
        product = p.product or p.description or 'USB シリアル'
        if product in ('n/a', p.device):
            product = 'USB シリアル'
        devs.append(Device(p.device, p.vid, p.pid, p.serial_number, product))
    devs.sort(key=lambda d: d.port)
    return devs


# ------------------------------------------------------------
#  USB リセット (pyusb + libusb)
# ------------------------------------------------------------
def _usb_backend():
    try:
        import usb.backend.libusb1
        try:
            import libusb_package
            return libusb_package.get_libusb1_backend()
        except ImportError:
            return usb.backend.libusb1.get_backend()
    except Exception:
        return None


def _reset_interface(dev) -> int | None:
    try:
        cfg = dev.get_active_configuration()
    except Exception:
        try:
            cfg = dev[0]
        except Exception:
            return None
    for intf in cfg:
        if (intf.bInterfaceClass, intf.bInterfaceSubClass, intf.bInterfaceProtocol) == \
                (RESET_CLASS, RESET_SUBCLASS, RESET_PROTOCOL) and intf.bAlternateSetting == 0:
            return intf.bInterfaceNumber
    return None


def _find_usb_with_reset(target: Device):
    """シリアルポートと同じ USB デバイスで、Reset インターフェースを持つものを探す"""
    be = _usb_backend()
    if be is None:
        return None, None
    import usb.core
    import usb.util
    cands = []
    for dev in usb.core.find(find_all=True, idVendor=target.vid, idProduct=target.pid, backend=be) or []:
        itf = _reset_interface(dev)
        if itf is None:
            continue
        sn = None
        try:
            sn = usb.util.get_string(dev, dev.iSerialNumber) if dev.iSerialNumber else None
        except Exception:
            pass
        cands.append((dev, itf, sn))
    if target.serial_number:
        for dev, itf, sn in cands:
            if sn == target.serial_number:
                return dev, itf
    if len(cands) == 1 and not (target.serial_number and cands[0][2]):
        return cands[0][0], cands[0][1]  # シリアル番号で照合できないが 1 台だけ
    return None, None


def _usb_reset(dev, itf: int) -> None:
    import usb.util
    try:
        try:
            usb.util.claim_interface(dev, itf)
        except Exception:
            pass
        try:
            # 'vendor' 型だと TinyUSB が STALL する。picotool と同じ class 型 (0x21) で送る
            dev.ctrl_transfer(0x21, RESET_REQUEST_BOOTSEL, 0, itf, None, timeout=1000)
        except Exception:
            pass  # 即座に再起動するので転送がエラーになるのは正常
    finally:
        try:
            usb.util.dispose_resources(dev)
        except Exception:
            pass


# ------------------------------------------------------------
#  1200bps タッチ
# ------------------------------------------------------------
def _touch_1200(port: str) -> None:
    try:
        s = serial.Serial()
        s.port = port
        s.baudrate = 1200
        s.dtr = True
        s.rts = True
        s.open()
        time.sleep(0.05)
        s.dtr = False
        s.rts = False
        time.sleep(0.05)
        s.close()
    except serial.SerialException as e:
        raise RuntimeError(f'シリアルポート {port} を開けません（他のアプリが使用中？）: {e}') from e


def port_present(dev: Device) -> bool:
    return any(p.device == dev.port for p in list_ports.comports())


def enter_bootloader(dev: Device, log) -> None:
    if dev.vid == RPI_VID and dev.pid == DEBUGPROBE_PID:
        raise RuntimeError('Debugprobe は自動で書き込みモードに切り替えられません。'
                           'BOOTSEL ボタンを押しながら USB を挿し直してください。')
    usb_dev, itf = None, None
    try:
        usb_dev, itf = _find_usb_with_reset(dev)
    except Exception as e:
        log(f'USB の確認に失敗しました ({e})。1200bps で切り替えます', 'warn')
    if usb_dev is not None:
        log(f'USB リセットで書き込みモードへ切り替えます (interface {itf})', 'info')
        _usb_reset(usb_dev, itf)
        if _wait_port_gone(dev, 3.0):
            return
        log('USB リセットに応答がないため 1200bps を試します', 'warn')
    else:
        log(f'1200bps で書き込みモードへ切り替えます ({dev.port})', 'info')
    _touch_1200(dev.port)
    if not _wait_port_gone(dev, 3.0):
        raise RuntimeError('デバイスが書き込みモードに切り替わりませんでした。'
                           'このファームウェアは自動切り替えに対応していない可能性があります。'
                           'BOOTSEL ボタンを押しながら USB を挿し直してください。')


def _wait_port_gone(dev: Device, timeout: float) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if not port_present(dev):
            return True
        time.sleep(0.1)
    return False
