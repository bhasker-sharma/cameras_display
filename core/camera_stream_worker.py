#core/camera_stream_worker

import subprocess
import cv2
import numpy as np
import os
import re
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from utils.logging import log, Logger

# Mild sharpen kernel — boosts edges without introducing noise
_SHARPEN_KERNEL = np.array([[0, -0.5, 0],
                            [-0.5,  3, -0.5],
                            [0, -0.5, 0]], dtype=np.float32)

# Display resolution for each camera tile (scaled in GStreamer pipeline).
# 1280x720 balances quality vs pipe bandwidth for 48 cameras (~69 MB/s each).
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 720

_GST_ROOT = os.environ.get(
    "GSTREAMER_1_0_ROOT_MSVC_X86_64",
    r"C:\Program Files\gstreamer\1.0\msvc_x86_64"
)
_GST_BIN = os.path.join(_GST_ROOT, "bin")
GST_LAUNCH = os.path.join(_GST_BIN, "gst-launch-1.0.exe")

# Ensure GStreamer DLLs are findable by subprocesses
if _GST_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _GST_BIN + os.pathsep + os.environ.get("PATH", "")


def redact(url: str) -> str:
    return re.sub(r'(rtsp://)([^:@]+):([^@]+)@', r'\1****:****@', url or '', flags=re.IGNORECASE)


def _build_gst_cmd(rtsp_url: str) -> str:
    """Build gst-launch-1.0 command for low-latency RTSP display.

    Pipeline order matters:
      1. decodebin   — decode H264/H265 (outputs NV12/I420)
      2. videoconvert — convert to RGB first (videoscale can't scale NV12 reliably)
      3. videoscale   — scale to display size
      4. caps filter  — lock output to exact RGB + WxH (no stride padding)
      5. fdsink       — raw RGB frames to stdout
    """
    pipeline = (
        f'rtspsrc location="{rtsp_url}" latency=0 protocols=udp ! '
        f'decodebin ! '
        f'videoconvert ! '
        f'video/x-raw,format=RGB ! '
        f'videobalance brightness=0.05 contrast=1.15 saturation=1.1 ! ' #brightness (-1 to 1), contrast(0.0 to 2.0), saturation(0.0 to 2.0)
        f'videoscale ! '
        f'video/x-raw,format=RGB,width={DISPLAY_WIDTH},height={DISPLAY_HEIGHT} ! '
        f'fdsink'
    )
    return f'"{GST_LAUNCH}" -q {pipeline}'


class CameraStreamWorker(QThread):
    frameReady = pyqtSignal(int, object)
    connectionStatus = pyqtSignal(int, bool)

    def __init__(self, cam_id, rtsp_url):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.running = False
        self.mutex = QMutex()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3
        self.retry_delay = 3000
        self._proc = None
        os.makedirs("logs", exist_ok=True)
        self.logger = Logger.get_logger(
            name=f"Stream-{cam_id}",
            log_file=f"stream_{cam_id}.log"
        )

    def run(self):
        self.running = True
        frame_size = DISPLAY_WIDTH * DISPLAY_HEIGHT * 3  # BGR

        while self.running:
            try:
                if not self.rtsp_url:
                    self.logger.error(f"Camera {self.cam_id} RTSP URL is empty.")
                    self.connectionStatus.emit(self.cam_id, False)
                    return

                cmd = _build_gst_cmd(self.rtsp_url)
                self.logger.info(f"Camera {self.cam_id}: Opening stream {redact(self.rtsp_url)}")

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                self._proc = proc

                # First successful read means connected
                first_frame = True

                while self.running:
                    raw = proc.stdout.read(frame_size)
                    if len(raw) != frame_size:
                        if self.running:
                            self.logger.warning(f"Camera {self.cam_id}: pipe EOF; will reconnect.")
                            self.connectionStatus.emit(self.cam_id, False)
                        break

                    if first_frame:
                        self.logger.info(f"Camera {self.cam_id}: Connected.")
                        self.connectionStatus.emit(self.cam_id, True)
                        self.reconnect_attempts = 0
                        first_frame = False

                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                        (DISPLAY_HEIGHT, DISPLAY_WIDTH, 3)
                    )
                    frame = cv2.filter2D(frame, -1, _SHARPEN_KERNEL)
                    self.frameReady.emit(self.cam_id, frame)

                self._cleanup_proc()

            except Exception as e:
                self.logger.error(f"Camera {self.cam_id} error: {e}")
                self.connectionStatus.emit(self.cam_id, False)
                self._cleanup_proc()
                self.reconnect_attempts += 1
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    self.logger.error(f"Camera {self.cam_id}: Max reconnect attempts reached.")
                    break
                self.msleep(self.retry_delay)

    def _cleanup_proc(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def stop(self, blocking=True):
        self.logger.info(f"Camera {self.cam_id}: Stop requested (blocking={blocking}).")
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()
        self._cleanup_proc()
        if blocking:
            self.wait(5000)
