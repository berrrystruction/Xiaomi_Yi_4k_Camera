## Bitrate mod for the Yi 4k on firmware 1.10.99

Put [autoexec.ash](autoexec.ash) in the root of your sd card. IMPORTANT: if you are on windows you must save page as (download) this file, if you copy paste its contents it will not work because it needs to have unix line endings (and an empty line at the end). If you want to edit this file, get an editor like Notepad++ that supports unix line endings.

For an explanation see: [Readme.md](../../Readme.md)

Same addresses as firmware 1.10.9, verified on a memory dump of a Yi 4k on 1.10.99 with [find_addresses.py](../../../tools/yi4k_port/).

### Tested limits (Yi 4k, firmware 1.10.99, 3840x2160 30P high quality)

- 120 Mbps: stable, 15 minutes of continuous recording (files are split at ~4 GB, this is normal).
- 150 Mbps: the camera crashes. The RTOS log (see [enable_logs](../../../enable_logs/)) shows the
  H.264 encoder failing with `henc_send_eng0_msg(1): ERROR! msg queue full` followed by
  `Assertion '0' at .../h264_enc/orccode/enc_thread/enc_th_main.c:5041 failed`: the stage that
  writes the final bitstream (ENG0) falls behind, its intermediate buffer keeps growing until the
  queue is full. The limit is the encoder, not the SD card (the card used writes at 33 MB/s).
