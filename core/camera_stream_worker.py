# camera_app/core/camera_stream_worker.py

import cv2
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition,QTimer
from utils.logging import log


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
        self.max_reconnect_attempts = 3  # Allow unlimited retries
        self.retry_delay = 3000  # Start with 3 seconds
        self.timeout_seconds = 3  # OpenCV/FFmpeg timeout duration

    def run(self):
        self.running = True

        while self.running:
            try:
                if not self.rtsp_url:
                    log.warning(f"Camera {self.cam_id}: No RTSP URL, skipping.")
                    self.connectionStatus.emit(self.cam_id, False)
                    self.msleep(self.retry_delay)
                    continue

                log.debug(f"Camera {self.cam_id}: Attempting to open RTSP")

                cap = cv2.VideoCapture(
                    self.rtsp_url,
                    cv2.CAP_FFMPEG
                )

                # Wait up to N ms for stream to open
                success = cap.isOpened()
                if not success:
                    raise Exception("RTSP open timeout/failure")

                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))

                self.connectionStatus.emit(self.cam_id, True)
                self.reconnect_attempts = 0

                while self.running:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        log.warning(f"Camera {self.cam_id}: Failed to read frame.")
                        raise Exception("Frame read failed")

                    self.frameReady.emit(self.cam_id, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    self.msleep(15)

                cap.release()

            except Exception as e:
                log.error(f"Camera {self.cam_id} exception: {e}")
                self.connectionStatus.emit(self.cam_id, False)
                self.reconnect_attempts += 1

                if self.reconnect_attempts > self.max_reconnect_attempts:
                    log.error(f"Camera {self.cam_id}: Max reconnect attempts reached, stopping worker.")
                    self.connectionStatus.emit(self.cam_id, False)
                    break

                self.msleep(self.retry_delay)

    def stop(self):
        log.info(f"Camera {self.cam_id}: Stop requested.")
        self.mutex.lock()
        self.running = False
        self.condition.wakeAll()
        self.mutex.unlock()
