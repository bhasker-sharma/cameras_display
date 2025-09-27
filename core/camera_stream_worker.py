import numpy as np
import subprocess
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
import cv2
from utils.logging import log
from utils.helper import win_no_window_kwargs
import os, sys



def get_ffmpeg_path(tool="ffmpeg.exe"):
    """Return path to bundled ffmpeg/ffprobe"""
    if getattr(sys, 'frozen', False):  # running as exe
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, "ffmpeg_binary", tool)



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

    def get_stream_resolution(self):
        command = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "default=noprint_wrappers=1:nokey=1",
            self.rtsp_url
        ]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            **win_no_window_kwargs()
            )
        lines = result.stdout.splitlines()
        if len(lines) >= 2:
            width = int(lines[0])
            height = int(lines[1])
            return width, height
        else:
            log.error(f"Failed to get resolution for {self.rtsp_url}")
            raise RuntimeError(f"Camera {self.cam_id}: Cannot detect resolution")

    def run(self):
        self.running = True

        while self.running:
            try:
                if not self.rtsp_url:
                    log.error(f"Camera {self.cam_id} RTSP URL is empty.")
                    self.connectionStatus.emit(self.cam_id, False)
                    return

                width, height = self.get_stream_resolution()
                frame_size = width * height * 3

                log.info(f"Camera {self.cam_id}: Native resolution {width}x{height}")
                cmd = [
                    'ffmpeg',
                    '-hwaccel', 'dxva2',  # Windows hardware decoder
                    '-rtsp_transport', 'tcp',
                    '-i', self.rtsp_url,
                    '-f', 'rawvideo',
                    '-pix_fmt', 'bgr24',
                    '-an', 'pipe:1'
                ]

                ffmpeg_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=frame_size * 3,
                    **win_no_window_kwargs()  
                )

                self.connectionStatus.emit(self.cam_id, True)
                self.reconnect_attempts = 0
                frame_counter = 0

                while self.running:
                    raw_frame = ffmpeg_proc.stdout.read(frame_size)
                    if len(raw_frame) != frame_size:
                        log.warning(f"Camera {self.cam_id}: Incomplete frame.")
                        self.connectionStatus.emit(self.cam_id, False)
                        break

                    frame_counter += 1
                    if frame_counter % 2 == 1:
                        continue  # Optional: skip alternate frames

                    frame = np.frombuffer(raw_frame, np.uint8).reshape((height, width, 3))
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frameReady.emit(self.cam_id, rgb_frame)
                    self.msleep(1)

                ffmpeg_proc.terminate()
                ffmpeg_proc.wait()

            except Exception as e:
                log.error(f"Camera {self.cam_id} error: {e}")
                self.connectionStatus.emit(self.cam_id, False)
                self.reconnect_attempts += 1

                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    log.error(f"Camera {self.cam_id}: Max reconnect attempts reached.")
                    break

                self.msleep(self.retry_delay)

    def stop(self):
        log.info(f"Camera {self.cam_id}: Stop requested.")
        self.mutex.lock()
        self.running = False
        self.condition.wakeAll()
        self.mutex.unlock()
