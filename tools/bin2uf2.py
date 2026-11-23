#!/usr/bin/env python3
"""Raw flash image (.bin) -> UF2 converter for RP2040 / RP2350.

usage: bin2uf2.py input.bin output.uf2 [--family rp2040|rp2350-arm-s|rp2350-riscv] [--base 0x10000000]
"""
import argparse
import struct

FAMILIES = {
    "rp2040": 0xE48BFF56,
    "rp2350-arm-s": 0xE48BFF59,
    "rp2350-riscv": 0xE48BFF5A,
}
MAGIC0, MAGIC1, MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
FLAG_FAMILY_ID = 0x00002000
PAYLOAD = 256


def convert(data: bytes, base: int, family: int) -> bytes:
    if len(data) % PAYLOAD:
        data += b"\x00" * (PAYLOAD - len(data) % PAYLOAD)
    n = len(data) // PAYLOAD
    out = bytearray()
    for i in range(n):
        chunk = data[i * PAYLOAD:(i + 1) * PAYLOAD]
        hdr = struct.pack("<IIIIIIII", MAGIC0, MAGIC1, FLAG_FAMILY_ID,
                          base + i * PAYLOAD, PAYLOAD, i, n, family)
        out += hdr + chunk + b"\x00" * (476 - PAYLOAD) + struct.pack("<I", MAGIC_END)
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--family", default="rp2040", choices=FAMILIES)
    ap.add_argument("--base", default="0x10000000", type=lambda s: int(s, 0))
    a = ap.parse_args()
    with open(a.input, "rb") as f:
        data = f.read()
    uf2 = convert(data, a.base, FAMILIES[a.family])
    with open(a.output, "wb") as f:
        f.write(uf2)
    print(f"{a.output}: {len(uf2) // 512} blocks ({len(data)} bytes @ {a.base:#x}, family {a.family})")


if __name__ == "__main__":
    main()
