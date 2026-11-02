# Watch the Yi 4k live on a computer (VLC)

There are two ways to get the camera's video on a computer.

## A. Live preview over the camera's Wi-Fi (RTSP)

The camera streams the same low resolution preview that the Yi app shows.

1. Turn on Wi-Fi on the camera and connect the computer to the camera's
   network (`YDXJ_...`). The camera is at `192.168.42.1`.
2. Run:
   ```
   python3 live_view.py
   ```
3. In VLC: *Media -> Open Network Stream* -> `rtsp://192.168.42.1/live`

Keep the script running while watching; Ctrl+C closes the session.

The stream has some latency (VLC buffers about 1 s by default; lower it in
*Show more options -> Caching*). While the computer is connected to the
camera it is not connected to your home network.

Tested only against a simulated camera: the protocol (msg_id 257/259 and the
`/live` RTSP path) is the one used by the Yi app, but it was not verified on
a real Yi 4k with firmware 1.10.99 yet.

## B. Live mode to your home network (RTMP)

The camera's *Live* mode connects to your Wi-Fi router and pushes 1080p video
to an RTMP server. With a server on your computer, any device on the home
network can watch it.

1. Download [MediaMTX](https://github.com/bluenviron/mediamtx/releases) on the
   computer and start it (no configuration needed, it listens for RTMP on port
   1935 and RTSP on port 8554).
2. Find the computer's IP address (e.g. `192.168.1.10`).
3. Create the QR code as explained in [live](../../live/), with
   `"url":"rtmp://192.168.1.10/yi"` and your Wi-Fi name and password.
4. Put the camera in Live mode, scan the QR code.
5. In VLC: `rtsp://192.168.1.10:8554/yi` (or `rtmp://192.168.1.10/yi`).

The live mode bitrate is low (about 1.4 Mbps at 1080p), it is meant for
internet streaming. The QR code contains your Wi-Fi password in plain text:
do not share pictures of it.
