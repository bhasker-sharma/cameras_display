import os
import cv2
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread
from utils.logging import log

class CameraRecorderWorker(QThread):

    def __init__(self, cam_id, rtsp_url, camera_name):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.camera_name = camera_name
        self.running = False

    def run(self):
        self.running = True
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        if not cap.isOpened():
            log.error(f"[Recorder] Failed to open RTSP for Camera {self.cam_id}")
            return

        # Get first valid frame to detect resolution
        ret, frame = cap.read()
        if not ret or frame is None:
            log.warning(f"[Recorder] No frame received from Camera {self.cam_id}")
            cap.release()
            return

        height, width = frame.shape[:2]
        log.info(f"[Recorder] Camera {self.cam_id} frame size: {width}x{height}")

        now = datetime.now()
        date_folder = now.strftime("%d-%m-%Y")
        hour = now.strftime("%H")
        next_hour = (now + timedelta(hours=1)).strftime("%H")
        base_folder = f"recordings/{date_folder}/camera{self.cam_id}"
        os.makedirs(base_folder, exist_ok=True)

        file_name = f"{self.camera_name}_{now.strftime('%d%m%Y')}_{hour}_{next_hour}.avi"
        full_path = os.path.join(base_folder, file_name)

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(full_path, fourcc, 20.0, (width, height))

        if not out.isOpened():
            log.error(f"[Recorder] Failed to open VideoWriter for {full_path}")
            cap.release()
            return

        log.info(f"[Recorder] Started writing: {full_path}")

        start_time = datetime.now()
        frame_count = 0

        while self.running and (datetime.now() - start_time).seconds < 3600:
            ret, frame = cap.read()
            if not ret or frame is None:
                log.warning(f"[Recorder] Frame read failed for Camera {self.cam_id}")
                break

            # Sanity check
            if frame.shape[:2] != (height, width):
                log.warning(f"[Recorder] Frame size mismatch. Resizing...")
                frame = cv2.resize(frame, (width, height))

            out.write(frame)
            frame_count += 1

            if frame_count % 100 == 0:
                log.info(f"[Recorder] Camera {self.cam_id}: written {frame_count} frames")

        out.release()
        cap.release()
        log.info(f"[Recorder] Finished {file_name}. Total frames: {frame_count}")


    def stop(self):
        self.running = False
        self.wait()
