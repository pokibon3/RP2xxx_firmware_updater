"""UF2 / BIN ファームウェアの読み込み・チップ適合チェック・BIN→UF2 変換"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field

UF2_MAGIC0, UF2_MAGIC1, UF2_MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
FLAG_NOT_MAIN_FLASH = 0x00000001
FLAG_FAMILY_ID = 0x00002000

FAMILY = {
    'RP2040':        0xE48BFF56,
    'ABSOLUTE':      0xE48BFF57,
    'DATA':          0xE48BFF58,
    'RP2350_ARM_S':  0xE48BFF59,
    'RP2350_RISCV':  0xE48BFF5A,
    'RP2350_ARM_NS': 0xE48BFF5B,
}
FAMILY_NAME = {v: k for k, v in FAMILY.items()}
RP2350_FAMILIES = {FAMILY['RP2350_ARM_S'], FAMILY['RP2350_RISCV'], FAMILY['RP2350_ARM_NS']}

FLASH_START, FLASH_END = 0x10000000, 0x11000000
E10_DUMMY_ADDR = 0x10FFFF00  # RP2350-E10 回避用のダミーブロック


class FirmwareError(Exception):
    pass


@dataclass
class Block:
    addr: int
    family: int | None
    data: bytes


@dataclass
class Firmware:
    path: str
    kind: str                      # 'UF2' | 'BIN'
    raw: bytes
    blocks: list[Block]
    families: set[int] = field(default_factory=set)

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def family_names(self) -> str:
        if not self.families:
            return '指定なし'
        return ', '.join(FAMILY_NAME.get(f, f'0x{f:08x}') for f in sorted(self.families))

    def target_chips(self) -> list[str]:
        chips = [c for c in ('RP2040', 'RP2350') if any(family_matches(b.family, c) for b in self.blocks)]
        return chips


def family_matches(family: int | None, chip: str) -> bool:
    if family is None or family in (FAMILY['ABSOLUTE'], FAMILY['DATA']):
        return True
    if chip == 'RP2040':
        return family == FAMILY['RP2040']
    return family in RP2350_FAMILIES


def load(path: str) -> Firmware:
    with open(path, 'rb') as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lower()
    if ext == '.uf2':
        return _parse_uf2(path, raw)
    if ext == '.bin':
        if len(raw) == 0:
            raise FirmwareError('BIN ファイルが空です')
        if len(raw) > FLASH_END - FLASH_START:
            raise FirmwareError('BIN がフラッシュ容量 (16MB) を超えています')
        return Firmware(path, 'BIN', raw, [Block(FLASH_START, None, raw)])
    raise FirmwareError('対応していない拡張子です (.uf2 / .bin)')


def _parse_uf2(path: str, raw: bytes) -> Firmware:
    if len(raw) == 0 or len(raw) % 512:
        raise FirmwareError('UF2 のサイズが 512 の倍数ではありません')
    blocks, families = [], set()
    for off in range(0, len(raw), 512):
        m0, m1, flags, addr, size, _no, _num, fam = struct.unpack_from('<8I', raw, off)
        (m_end,) = struct.unpack_from('<I', raw, off + 508)
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or m_end != UF2_MAGIC_END:
            raise FirmwareError(f'UF2 ブロック #{off // 512} のマジックが不正です')
        if flags & FLAG_NOT_MAIN_FLASH:
            continue
        if size > 476:
            raise FirmwareError(f'UF2 ブロック #{off // 512} のペイロード長が不正です')
        family = fam if flags & FLAG_FAMILY_ID else None
        if family is not None:
            families.add(family)
        blocks.append(Block(addr, family, raw[off + 32: off + 32 + size]))
    return Firmware(path, 'UF2', raw, blocks, families)


def check(fw: Firmware, chip: str) -> tuple[int, int, int]:
    """チップ向けのブロックを検査し (先頭, 末尾, バイト数) を返す。不適合なら FirmwareError"""
    blocks = [b for b in fw.blocks
              if family_matches(b.family, chip)
              and not (b.family == FAMILY['ABSOLUTE'] and b.addr == E10_DUMMY_ADDR)]
    if not blocks:
        raise FirmwareError(f'このファームウェア ({fw.family_names()}) は {chip} 向けではありません')
    lo, hi, n = min(b.addr for b in blocks), 0, 0
    for b in blocks:
        if b.addr < FLASH_START or b.addr + len(b.data) > FLASH_END:
            raise FirmwareError(f'フラッシュ範囲外のアドレス 0x{b.addr:08x} を含みます（RAM 実行用 UF2 は非対応）')
        hi = max(hi, b.addr + len(b.data))
        n += len(b.data)
    return lo, hi, n


def to_uf2(fw: Firmware, chip: str) -> bytes:
    """ドライブへコピーする UF2 データ（UF2 はそのまま、BIN は変換）"""
    if fw.kind == 'UF2':
        return fw.raw
    family = FAMILY['RP2040'] if chip == 'RP2040' else FAMILY['RP2350_ARM_S']
    data, base = fw.blocks[0].data, fw.blocks[0].addr
    n = (len(data) + 255) // 256
    out = bytearray()
    for i in range(n):
        chunk = data[i * 256:(i + 1) * 256].ljust(256, b'\0')
        hdr = struct.pack('<8I', UF2_MAGIC0, UF2_MAGIC1, FLAG_FAMILY_ID, base + i * 256, 256, i, n, family)
        out += hdr + chunk + b'\0' * (476 - 256) + struct.pack('<I', UF2_MAGIC_END)
    return bytes(out)
