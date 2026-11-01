# Port the Yi 4k mods to a new firmware version

The bitrate and ultra resolution mods use RAM addresses that change with every
firmware version. This tool finds the addresses for a version that is not in
this repository (for example **1.10.99**) from a memory dump of your camera,
and generates the `autoexec.ash` files for it.

It works because on every known Yi 4k firmware (1.8.9 to 1.10.9):

- the bitrate table has exactly the same layout and stock values, it only moves
  in memory;
- the ultra resolution table is always `0x86F0` bytes after the bitrate table;
- the audio bitrate is `0x384`-`0x394` bytes before the bitrate table.

It was tested by simulating the dumps of firmwares 1.9.0, 1.9.4, 1.10.4 and
1.10.7 (and 1.8.9): the generated addresses are identical to the ones in this
repository.

## 1. Dump the camera memory

Make sure there is no other `autoexec.ash` mod on the SD card. Create an
`autoexec.ash` in the root of the SD card containing only this line, followed
by an empty line, with unix line endings:

```
savebin c:\dump.bin 0xA0600000 l 2097152
```

Boot the camera, wait a few seconds, turn it off. You will find `dump.bin`
(2 MB) on the SD card. **Remove `autoexec.ash` from the SD card.**

Dumping is read-only and does not change anything on the camera.

The 2 MB starting at `0xA0600000` contain the tables on every known firmware.
Do not use the full 16 MB dump at `0xA0000000` from the
[autoexec.ash notes](../../autoexec.ash/): on firmware 1.10.99 it froze the
camera at boot.

### If the camera freezes at boot

The screen stays black and the camera does not turn off: take the battery out,
put the SD card in a computer and delete `autoexec.ash`. The camera will boot
normally again. Then try a smaller dump, e.g. 64 KB around the 1.10.9 table:

```
savebin c:\dump.bin 0xA06D0000 l 65536
```

and run the tool with `--base 0xA06D0000`.

## 2. Find the addresses

```
python3 find_addresses.py dump.bin 1.10.99
```

If you dumped from another start address, add `--base <address>`.

If every check passes, the folder `out_1.10.99` contains:

- `bitrate_autoexec.ash` - the bitrate mod with the stock values (edit them as
  explained in [bitrate](../../bitrate/));
- `bitrate_addresses.txt` - which address corresponds to which video mode;
- `ultra_increased_resolution_autoexec.ash` - the 4000x2700 / 2000x1500 mod.

If a check fails, nothing is generated: the firmware changed too much and the
addresses must be found by hand.

## 3. Test

Use only one mod at a time at first. If anything goes wrong, remove
`autoexec.ash` from the SD card and reboot: the mods live in RAM only.
