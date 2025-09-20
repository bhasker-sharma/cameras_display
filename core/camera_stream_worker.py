#core/camera_stream_worker

import numpy as np
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
from utils.subproc import win_no_window_kwargs
import os,sys,shutil
import re
from utils.logging import log, Logger   # ← add Logger


def tool(name: str) -> str:
    """Find ffmpeg/ffprobe whether running from source or frozen EXE."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        cand = os.path.join(base, f"{name}.exe")
        if os.path.exists(cand):
            return cand
    found = shutil.which(name)
    return found or name

def redact(url: str) -> str:
    # rtsp://user:pass@host:554/...
    return re.sub(r'(rtsp://)([^:@]+):([^@]+)@', r'\1****:****@', url or '', flags=re.IGNORECASE)

def _read_exact(pipe, n):
    """Read exactly n bytes from a pipe or return None on EOF/short read."""
    buf = bytearray(n)
    view = memoryview(buf)
    got = 0
    while got < n:
        chunk = pipe.read(n - got)
        if not chunk:  # EOF or broken pipe
            return None
        l = len(chunk)
        view[got:got + l] = chunk
        got += l
    return buf

class CameraStreamWorker(QThread):
    frameReady = pyqtSignal(int, object)
    connectionStatus = pyqtSignal(int, bool)

    def __init__(self, cam_id, rtsp_url):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.running = False
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.retry_delay = 3000
        self.proc = None
        os.makedirs("logs", exist_ok=True)
        self.logger = Logger.get_logger(
            name=f"Stream-{cam_id}",
            log_file=f"stream_{cam_id}.log"
        )

    def get_stream_resolution(self):
        ffprobe = tool("ffprobe")
        cmd = [
            ffprobe,
            "-hide_banner",
            "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-rw_timeout", "5000000",     # 5s I/O timeout (microseconds)
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            self.rtsp_url
        ] 
        self.logger.debug(f"ffprobe cmd: {cmd[0]} ... {redact(self.rtsp_url)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            stdin=subprocess.DEVNULL,
            **win_no_window_kwargs()
        )
        if result.returncode != 0:
            self.logger.error(f"ffprobe failed rc={result.returncode}; stderr={result.stderr.strip()}")
            raise RuntimeError(f"ffprobe error (code {result.returncode})")

        out = result.stdout.strip()
        self.logger.debug(f"ffprobe stdout: '{out}'")
        try:
            w_str, h_str = out.split(",")
            return int(w_str), int(h_str)
        except Exception:
            self.logger.error(f"Unexpected ffprobe output: '{out}'")
            raise RuntimeError("Cannot detect resolution")

    def run(self):
        import time
        self.running = True

        # ---- knobs you can tweak without touching the rest ----
        USE_UDP = True          # set True for lower latency (best on a clean LAN)
        DOWNSCALE_WIDTH = 720   # e.g. 640 for lighter frames; None = keep native
        # -------------------------------------------------------

        while self.running:
            try:
                if not self.rtsp_url:
                    self.logger.error(f"Camera {self.cam_id} RTSP URL is empty.")
                    self.connectionStatus.emit(self.cam_id, False)
                    return

                # Probe source resolution once per (re)connect
                width, height = self.get_stream_resolution()
                out_w, out_h = width, height

                # Optional mild downscale (off by default — no visible loss at 704→640)
                if DOWNSCALE_WIDTH:
                    out_w = int(DOWNSCALE_WIDTH)
                    out_h = max(1, (height * out_w) // width)
                    if out_h % 2:
                        out_h += 1  # keep even for safety
                frame_size = out_w * out_h * 3  # rgb24 bytes

                self.logger.info(f"Camera {self.cam_id}: {width}x{height} → output {out_w}x{out_h}")

                ffmpeg = tool("ffmpeg")

                # Choose transport profile
                if USE_UDP:
                    in_flags = ["-rtsp_transport", "udp", "-fflags", "nobuffer", "-flags", "low_delay", "-fflags", "flush_packets"]
                else:
                    in_flags = ["-rtsp_transport", "tcp", "-rtsp_flags", "prefer_tcp",
                                "-fflags", "nobuffer", "-flags", "low_delay"]

                # Build command
                cmd = [
                    ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "warning",
                    *in_flags,
                    "-probesize", "32k", "-analyzeduration", "0",
                    "-vsync", "0",
                    "-i", self.rtsp_url,
                ]
                # Optional scale in ffmpeg (only if we changed size)
                if (out_w, out_h) != (width, height):
                    cmd += ["-vf", f"scale={out_w}:{out_h}"]

                # Output raw frames to stdout
                cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-an", "pipe:1"]

                # per-camera ffmpeg stderr log
                os.makedirs("logs", exist_ok=True)
                fferr_path = os.path.join("logs", f"ffmpeg_stream_{self.cam_id}.log")
                fferr_fh = open(fferr_path, "w", encoding="utf-8")

                self.logger.info(f"Starting ffmpeg for cam {self.cam_id} ({'UDP' if USE_UDP else 'TCP'}) → {redact(self.rtsp_url)}")
                self.logger.debug(f"ffmpeg cmd: {cmd[0]} ... -i {redact(self.rtsp_url)} ...")

                ffmpeg_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=fferr_fh,
                    bufsize=0,  # unbuffered → lowest latency
                    **win_no_window_kwargs()
                )
                self.proc = ffmpeg_proc

                self.connectionStatus.emit(self.cam_id, True)
                self.reconnect_attempts = 0

                # Smooth UI pacing: PAL cams are usually 25fps; others 30fps
                max_emit_fps = 30.0 #25.0 if width in (704, 720) or height in (576, 480) else 30.0
                emit_interval = 1.0 / max_emit_fps
                last_emit = 0.0

                # Read frames exactly frame_size bytes at a time
                while self.running:
                    raw_frame = _read_exact(ffmpeg_proc.stdout, frame_size)
                    if raw_frame is None:
                        self.logger.warning("No data / EOF from ffmpeg; will reconnect.")
                        self.connectionStatus.emit(self.cam_id, False)
                        break

                    now = time.perf_counter()
                    if (now - last_emit) >= emit_interval:
                        rgb_frame = np.frombuffer(raw_frame, np.uint8).reshape((out_h, out_w, 3))
                        self.frameReady.emit(self.cam_id, rgb_frame)
                        last_emit = now

                    # tiny yield so Qt paints smoothly (without adding visible lag)
                    self.msleep(0.1)

                # Cleanup before potential reconnect
                try:
                    if ffmpeg_proc.poll() is None:
                        ffmpeg_proc.terminate()
                        ffmpeg_proc.wait(timeout=5)
                except Exception:
                    try:
                        ffmpeg_proc.kill()
                    except Exception:
                        pass
                finally:
                    try:
                        fferr_fh.flush()
                    except Exception:
                        pass
                    try:
                        fferr_fh.close()
                    except Exception:
                        pass
                    self.proc = None

            except Exception as e:
                self.logger.error(f"Camera {self.cam_id} error: {e}")
                self.connectionStatus.emit(self.cam_id, False)
                self.reconnect_attempts += 1
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    self.logger.error(f"Camera {self.cam_id}: Max reconnect attempts reached.")
                    break
                self.msleep(self.retry_delay)

    def stop(self):
        self.logger.info(f"Camera {self.cam_id}: Stop requested.")
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
        except Exception:
            pass
