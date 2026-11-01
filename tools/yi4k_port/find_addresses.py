#!/usr/bin/env python3
"""
Port the Yi 4k bitrate and ultra resolution mods to a firmware version that
is not in this repository (e.g. 1.10.99), using a RAM dump of the camera.

How to get the dump: put an autoexec.ash containing only this line (plus an
empty line at the end, unix line endings) on the SD card and boot the camera:

    savebin c:\\dump.bin 0xA0600000 l 2097152

(2 MB starting at 0xA0600000: it contains the tables on every known firmware.
A full 16 MB dump at 0xA0000000 froze a camera on firmware 1.10.99. If you use
another start address, pass it with --base.)

Then remove autoexec.ash from the SD card and copy dump.bin to your computer.
The dump must be taken WITHOUT any mod active, so that the tables contain the
stock values.

Usage:
    python3 find_addresses.py dump.bin 1.10.99 [--out DIR]

The script searches the dump for the stock bitrate table of the reference
firmware (1.10.9), whose layout and default values have been identical on
every 4k firmware from 1.8.9 to 1.10.9, and computes how much it moved.
It then checks the audio bitrate and the ultra resolution tables (always
0x86F0 bytes after the bitrate table on every known firmware) and writes the
autoexec.ash files for the new version. Nothing is written if a check fails.
"""

import argparse
import os
import re
import struct
import sys

DUMP_BASE = 0xA0600000  # start address of the dump, set with --base
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF_VERSION = "1.10.9"
REF_BITRATE = os.path.join(REPO, "bitrate", "4k", REF_VERSION, "autoexec.ash")
REF_ADDRESSES = os.path.join(REPO, "bitrate", "4k", REF_VERSION, "bitrate_addresses.txt")
REF_RESOLUTION = os.path.join(REPO, "4k", "ultra_increased_resolution", REF_VERSION, "autoexec.ash")

WRITE_RE = re.compile(r"^(write[lwb]) (0x[0-9A-Fa-f]+) (0x[0-9A-Fa-f]+)(.*)$")
AUDIO_STOCK = 0x1F400  # 128 kb/s
# Audio offset below the bitrate table seen so far: 0x384, 0x38C, 0x394.
AUDIO_WINDOW = (0x300, 0x400)
# Stock sizes of the modes changed by the resolution mod (width, height).
RES_STOCK = {(3840, 2160), (1920, 1080)}


def parse_script(path):
    """Return the lines of a script; write commands become tuples."""
    out = []
    with open(path, newline="") as f:
        for line in f.read().split("\n"):
            m = WRITE_RE.match(line)
            if m:
                out.append((m[1], int(m[2], 16), m[3], m[4]))
            else:
                out.append(line)
    return out


def read_u32(dump, addr):
    off = addr - DUMP_BASE
    if off < 0 or off + 4 > len(dump):
        return None
    return struct.unpack_from("<I", dump, off)[0]


def read_u16(dump, addr):
    off = addr - DUMP_BASE
    if off < 0 or off + 2 > len(dump):
        return None
    return struct.unpack_from("<H", dump, off)[0]


def find_bitrate_table(dump, table):
    """table: list of (addr, value). Returns list of matching deltas."""
    a0 = table[0][0]
    first = b"".join(struct.pack("<I", v) for _, v in table[:3])
    if [a for a, _ in table[:3]] != [a0, a0 + 4, a0 + 8]:
        sys.exit("unexpected reference table layout")
    deltas = []
    pos = dump.find(first)
    while pos != -1:
        delta = DUMP_BASE + pos - a0
        if all(read_u32(dump, a + delta) == v for a, v in table):
            deltas.append(delta)
        pos = dump.find(first, pos + 1)
    return deltas


def fmt_addr(a):
    return "0x%08X" % a


def render(lines, addr_map, title_from, title_to):
    text = []
    for line in lines:
        if isinstance(line, tuple):
            cmd, addr, val, rest = line
            text.append("%s %s %s%s" % (cmd, fmt_addr(addr_map(cmd, addr)), val, rest))
        else:
            text.append(line.replace(title_from, title_to))
    return "\n".join(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump", help="dump.bin taken from the camera")
    ap.add_argument("--base", default="0xA0600000",
                    help="memory address the dump starts at (default 0xA0600000)")
    ap.add_argument("version", help="firmware version of the camera, e.g. 1.10.99")
    ap.add_argument("--out", default=None, help="output directory (default: ./out_<version>)")
    args = ap.parse_args()
    global DUMP_BASE
    DUMP_BASE = int(args.base, 0)

    with open(args.dump, "rb") as f:
        dump = f.read()
    print("dump: %d bytes (0x%08X - 0x%08X)" % (len(dump), DUMP_BASE, DUMP_BASE + len(dump)))

    bitrate_lines = parse_script(REF_BITRATE)
    writes = [l for l in bitrate_lines if isinstance(l, tuple)]
    audio = [w for w in writes if "bs" in w[3] and int(w[2], 16) == AUDIO_STOCK]
    if len(audio) != 1:
        sys.exit("could not identify the audio line in the reference script")
    audio = audio[0]
    table = [(a, int(v, 16)) for c, a, v, r in writes if (c, a, v, r) != audio]

    # 1. bitrate table
    deltas = find_bitrate_table(dump, table)
    if len(deltas) != 1:
        sys.exit("FAILED: found the stock bitrate table %d times (expected exactly 1). "
                 "Is the dump taken without mods and from a Yi 4k (not 4k+)?" % len(deltas))
    delta = deltas[0]
    new_table_start = table[0][0] + delta
    print("bitrate table: %s (1.10.9: %s, shift %+#x)" % (fmt_addr(new_table_start), fmt_addr(table[0][0]), delta))

    # 2. audio bitrate (its distance from the table changes a bit between versions)
    lo = new_table_start - AUDIO_WINDOW[1]
    hi = new_table_start - AUDIO_WINDOW[0]
    audio_hits = [a for a in range(lo, hi, 4) if read_u32(dump, a) == AUDIO_STOCK]
    if len(audio_hits) != 1:
        sys.exit("FAILED: audio bitrate not found unambiguously (%d candidates)" % len(audio_hits))
    new_audio = audio_hits[0]
    print("audio bitrate: %s (offset -%#x from the table)" % (fmt_addr(new_audio), new_table_start - new_audio))

    # 3. ultra resolution table, always 0x86F0 bytes after the bitrate table
    res_lines = parse_script(REF_RESOLUTION)
    # (so it moves by the same amount as the bitrate table)
    res_delta = delta
    res_ok = True
    for c, a, v, _ in [l for l in res_lines if isinstance(l, tuple)]:
        na = a + res_delta
        if c == "writel":
            cur = read_u32(dump, na)
            w, h = cur & 0xFFFF, cur >> 16
            good = (w, h) in RES_STOCK
            print("resolution %s: stock %dx%d %s" % (fmt_addr(na), w, h, "OK" if good else "UNEXPECTED"))
            res_ok &= good
    if not res_ok:
        print("WARNING: the ultra resolution table does not contain the expected stock values, "
              "its script will NOT be generated.")

    # 4. write the scripts
    out = args.out or "out_%s" % args.version
    os.makedirs(out, exist_ok=True)

    def bitrate_map(cmd, addr):
        return new_audio if addr == audio[1] else addr + delta

    path = os.path.join(out, "bitrate_autoexec.ash")
    with open(path, "w", newline="\n") as f:
        f.write(render(bitrate_lines, bitrate_map, REF_VERSION, args.version))
    print("written", path)

    with open(REF_ADDRESSES, newline="") as f:
        addr_text = f.read()
    addr_text = re.sub(r"^(0x[0-9A-Fa-f]+)",
                       lambda m: fmt_addr(bitrate_map("writel", int(m[1], 16))), addr_text, flags=re.M)
    path = os.path.join(out, "bitrate_addresses.txt")
    with open(path, "w", newline="\n") as f:
        f.write(addr_text.replace(REF_VERSION, args.version))
    print("written", path)

    if res_ok:
        path = os.path.join(out, "ultra_increased_resolution_autoexec.ash")
        with open(path, "w", newline="\n") as f:
            f.write(render(res_lines, lambda c, a: a + res_delta, REF_VERSION, args.version))
        print("written", path)


if __name__ == "__main__":
    main()
