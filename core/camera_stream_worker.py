#core/camera_stream_worker

import cv2
import os
import re
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from utils.logging import log, Logger


def redact(url: str) -> str:
    return re.sub(r'(rtsp://)([^:@]+):([^@]+)@', r'\1****:****@', url or '', flags=re.IGNORECASE)


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
        self._cap = None
        os.makedirs("logs", exist_ok=True)
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

                self.logger.info(f"Camera {self.cam_id}: Opening stream {redact(self.rtsp_url)}")

                cap = cv2.VideoCapture(self.rtsp_url)
                self._cap = cap

                if not cap.isOpened():
                    raise RuntimeError("Cannot open RTSP stream")

                self.logger.info(f"Camera {self.cam_id}: Connected.")
                self.connectionStatus.emit(self.cam_id, True)
                self.reconnect_attempts = 0

                # Simple read loop — emit every frame, let UI drop old ones.
                # This matches the proven lag-free approach.
                while self.running:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        self.logger.warning(f"Camera {self.cam_id}: read() failed / EOF; will reconnect.")
                        self.connectionStatus.emit(self.cam_id, False)
                        break

                    self.frameReady.emit(self.cam_id, frame)

                # Cleanup before potential reconnect
                cap.release()
                self._cap = None

            except Exception as e:
                self.logger.error(f"Camera {self.cam_id} error: {e}")
                self.connectionStatus.emit(self.cam_id, False)
                if self._cap:
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                    self._cap = None
                self.reconnect_attempts += 1
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    self.logger.error(f"Camera {self.cam_id}: Max reconnect attempts reached.")
                    break
                self.msleep(self.retry_delay)

    def stop(self, blocking=True):
        self.logger.info(f"Camera {self.cam_id}: Stop requested (blocking={blocking}).")
        self.mutex.lock()
        self.running = False
        self.mutex.unlock()
        # Do NOT release cap here — let run() handle it cleanly
        # to avoid the "async_lock assertion" crash.
        if blocking:
            self.wait(5000)  # wait up to 5s for run() to exit
