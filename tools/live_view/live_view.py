#!/usr/bin/env python3
"""
Start the live preview stream of a Yi 4k and keep it alive, so it can be
watched with VLC (or ffplay, OBS...) over RTSP.

Connect your computer to the camera's Wi-Fi first (the camera is at
192.168.42.1 by default), then:

    python3 live_view.py [camera_ip]

and open in VLC (Media -> Open Network Stream):

    rtsp://192.168.42.1/live

Keep this script running while you watch: the camera closes the session
if it does not receive anything for a while. Stop it with Ctrl+C.

This uses the JSON protocol on TCP port 7878 also used by the official
app and by camera_controller/controller.py:
    msg_id 257  start a session, the answer contains the token
    msg_id 259  start the viewfinder stream (param "none_force")
    msg_id 3    get settings, used here as a keepalive
    msg_id 258  end the session
"""

import json
import socket
import sys
import time

CAMERA_PORT = 7878
KEEPALIVE_SECONDS = 10
TIMEOUT_SECONDS = 10


class Camera:
    def __init__(self, ip):
        self.ip = ip
        self.sock = socket.create_connection((ip, CAMERA_PORT), timeout=TIMEOUT_SECONDS)
        self.buffer = ""
        self.decoder = json.JSONDecoder()
        self.token = 0

    def send(self, msg):
        self.sock.sendall(json.dumps(msg).encode())

    def messages(self):
        """Read from the socket and return every complete JSON message.

        The camera can send several messages in one packet, or one message
        split across packets, so they are parsed from a buffer."""
        data = self.sock.recv(8192)
        if not data:
            raise ConnectionError("the camera closed the connection")
        self.buffer += data.decode(errors="replace")
        out = []
        while True:
            self.buffer = self.buffer.lstrip()
            if not self.buffer:
                break
            try:
                msg, end = self.decoder.raw_decode(self.buffer)
            except ValueError:
                break  # incomplete message, wait for more data
            self.buffer = self.buffer[end:]
            out.append(msg)
        return out

    def request(self, msg):
        """Send a command and wait for the answer with the same msg_id.
        Notifications received in the meantime (msg_id 7) are printed."""
        self.send(msg)
        deadline = time.time() + TIMEOUT_SECONDS
        while time.time() < deadline:
            for reply in self.messages():
                if reply.get("msg_id") == msg["msg_id"]:
                    return reply
                if reply.get("msg_id") == 7:
                    print("camera:", reply.get("type"), reply.get("param", ""))
        raise TimeoutError("no answer to msg_id %d" % msg["msg_id"])

    def start_session(self):
        reply = self.request({"msg_id": 257, "token": 0})
        if reply.get("rval") != 0:
            raise RuntimeError("the camera refused the session: %s" % reply)
        self.token = reply["param"]

    def start_stream(self):
        reply = self.request({"msg_id": 259, "token": self.token, "param": "none_force"})
        if reply.get("rval") != 0:
            raise RuntimeError("the camera refused to start the stream: %s" % reply)

    def keepalive(self):
        self.request({"msg_id": 3, "token": self.token})

    def close(self):
        try:
            self.send({"msg_id": 258, "token": self.token})
        except OSError:
            pass
        self.sock.close()


def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.42.1"
    cam = Camera(ip)
    try:
        cam.start_session()
        print("session started (token %s)" % cam.token)
        cam.start_stream()
        print("stream started, open in VLC:  rtsp://%s/live" % ip)
        print("Ctrl+C to stop")
        while True:
            time.sleep(KEEPALIVE_SECONDS)
            cam.keepalive()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        cam.close()


if __name__ == "__main__":
    main()
