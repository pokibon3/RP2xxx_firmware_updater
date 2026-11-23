# PyInstaller spec — macOS: dist/RP2xxx Updater.app / Windows: dist/RP2xxx Updater.exe
#   pyinstaller --noconfirm rp2updater.spec
import sys
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

APP_NAME = 'RP2xxx Updater'

datas, binaries, hiddenimports = [], [], []
d, b, h = collect_all('tkinterdnd2')            # tkdnd の Tcl 拡張
datas += d; binaries += b; hiddenimports += h
binaries += collect_dynamic_libs('libusb_package')  # libusb-1.0 (USB リセット用)
hiddenimports += ['usb.backend.libusb1', 'serial.tools.list_ports']

a = Analysis(
    ['rp2updater.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=['numpy', 'PIL', 'unittest', 'pydoc'],
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP_NAME,
              console=False, argv_emulation=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)
    app = BUNDLE(
        coll,
        name=f'{APP_NAME}.app',
        bundle_identifier='io.github.pokibon3.rp2xxx-updater',
        info_plist={
            'CFBundleDisplayName': APP_NAME,
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            'NSRemovableVolumesUsageDescription':
                '書き込みモードの基板 (RPI-RP2 / RP2350 ドライブ) にファームウェアを書き込むために使用します。',
        },
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=APP_NAME,
              console=False, upx=False)
