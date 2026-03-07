#core/camera_stream_worker

import subprocess
import numpy as np
import os
import re
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from utils.logging import log, Logger
from utils.subproc import kill_process_tree
from utils.paths import get_gstreamer_root

# Display resolution for each camera tile (scaled in GStreamer pipeline).
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 720
FRAME_SIZE = DISPLAY_WIDTH * DISPLAY_HEIGHT * 3


def redact(url: str) -> str:
    return re.sub(r'(rtsp://)([^:@]+):([^@]+)@', r'\1****:****@', url or '', flags=re.IGNORECASE)


def _get_gst_launch() -> str:
    """Resolve gst-launch-1.0.exe at runtime (supports bundled and installed GStreamer)."""
    gst_root = get_gstreamer_root()
    gst_bin = os.path.join(gst_root, 'bin')
    # Ensure GStreamer bin is in PATH so the subprocess can load its DLLs
    current_path = os.environ.get('PATH', '')
    if gst_bin not in current_path:
        os.environ['PATH'] = gst_bin + os.pathsep + current_path
    return os.path.join(gst_bin, 'gst-launch-1.0.exe')


def _build_gst_cmd(rtsp_url: str) -> str:

    gst_launch = _get_gst_launch()
    # decodebin auto-detects codec (H.264, H.265, MJPEG, etc.).
    # CPU-only decode is enforced in the caller by boosting software decoder
    # ranks to 512. Hardware decoders sit at GStreamer's default PRIMARY rank
    # (256), so software decoders always win the selection — no GPU involved.
    pipeline = (
        f'rtspsrc location="{rtsp_url}" latency=200 drop-on-latency=true ! '
        f'decodebin ! '
        f'queue max-size-buffers=1 leaky=downstream ! '
        f'videoconvert ! '
        f'videoscale ! '
        f'video/x-raw,format=RGB,width={DISPLAY_WIDTH},height={DISPLAY_HEIGHT} ! '
        f'fdsink sync=false'
    )
    return f'"{gst_launch}" -q {pipeline}'


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
        self.retry_delay = 3000
        self.max_retry_delay = 30000
        self.frame_consumed = True  # UI sets this True after painting
        self._proc = None
        self.logger = Logger.get_logger(
            name=f"Stream-{cam_id}",
            log_file=f"stream_{cam_id}.log"
        )

    def run(self):
        self.running = True

        while self.running:
            try:
                if not self.rtsp_url:
                    self.logger.error(f"Camera {self.cam_id} RTSP URL is empty.")
                    self.connectionStatus.emit(self.cam_id, False)
                    return

                cmd = _build_gst_cmd(self.rtsp_url)
                self.logger.info(f"Camera {self.cam_id}: Opening stream {redact(self.rtsp_url)}")

                # Boost software (CPU) decoders to rank 512.
                # GStreamer's hardware decoders default to rank 256 (PRIMARY).
                # decodebin always picks the highest rank → software wins,
                # GPU decoders are never selected. No GPU name is listed here.
                gst_env = os.environ.copy()
                gst_env['GST_PLUGIN_FEATURE_RANK'] = (
                    'avdec_h264:512,avdec_h265:512,'
                    'avdec_vp9:512,avdec_vp8:512,jpegdec:512'
                )

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    env=gst_env,
                )
                self._proc = proc

                # First successful read means connected
                first_frame = True

                while self.running:
                    raw = proc.stdout.read(FRAME_SIZE)
                    if len(raw) != FRAME_SIZE:
                        if self.running:
                            try:
                                err_output = proc.stderr.read(4096).decode("utf-8", errors="replace")
                                if err_output:
                                    self.logger.error(f"Camera {self.cam_id} GStreamer: {err_output.strip()}")
                            except Exception:
                                pass
                            self.logger.warning(f"Camera {self.cam_id}: pipe EOF; will reconnect.")
                            self.connectionStatus.emit(self.cam_id, False)
                        break

                    if first_frame:
                        self.logger.info(f"Camera {self.cam_id}: Connected.")
                        self.connectionStatus.emit(self.cam_id, True)
                        self.reconnect_attempts = 0
                        first_frame = False

                    # Only emit if UI consumed the previous frame — skip otherwise
                    # The pipe read above still drains GStreamer so it never blocks
                    if not self.frame_consumed:
                        continue

                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                        (DISPLAY_HEIGHT, DISPLAY_WIDTH, 3)
                    )
                    self.frame_consumed = False
                    self.frameReady.emit(self.cam_id, frame)

                self._cleanup_proc()

                # Delay before reconnect with backoff
                if self.running:
                    self.reconnect_attempts += 1
                    delay = min(self.retry_delay * self.reconnect_attempts, self.max_retry_delay)
                    self.logger.info(f"Camera {self.cam_id}: Reconnecting in {delay}ms (attempt {self.reconnect_attempts})...")
                    self.msleep(delay)

            except Exception as e:
                self.logger.error(f"Camera {self.cam_id} error: {e}")
                self.connectionStatus.emit(self.cam_id, False)
                self._cleanup_proc()
                self.reconnect_attempts += 1
                delay = min(self.retry_delay * self.reconnect_attempts, self.max_retry_delay)
                self.msleep(delay)

    def _cleanup_proc(self):
        if self._proc:
            try:
                kill_process_tree(self._proc.pid)
            except Exception:
                pass
            try:
                self._proc.wait(timeout=3)
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
