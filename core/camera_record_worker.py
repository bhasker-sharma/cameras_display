import os
import cv2 , shutil
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread
from utils.logging import log


class CameraRecorderWorker(QThread):

    def __init__(self, cam_id,rtsp_url , camera_name):

        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.camera_name = camera_name
        self.running = False

    def run(self):
        self.running = True
        cap = cv2.VideoCapture(self.rtsp_url , cv2.CAP_FFMPEG)

        if not cap.isOpened():
            log.error(f"[recorder] Failed to open rtsp for camera {self.cam_id}")
            return

        while self.running:
            now = datetime.now()
            date_folder = now.strftime("%d-%m-%Y")
            hour =  now.strftime("%H")
            next_hour = (now + timedelta(hours = 1)).strftime("%H")   
            base_folder = f"recordings/{date_folder}/camera{self.cam_id}"
            
            os.makedirs(base_folder, exist_ok=True)

            file_name = f"{self.camera_name}_{now.strftime('%d%m%Y')}_{hour}_{next_hour}"

            full_path = os.path.join(base_folder , file_name)
            log.info(f"[Recoder]Starting new file: {full_path}")

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(full_path, fourcc, 20.0, (640, 480))
            start_time = datetime.now()
            while self.running and (datetime.now() - start_time).seconds < 3600:
                ret, frame = cap.read()
                if not ret:
                    log.warning(f"[Recorder] Failed to read frame from Camera {self.cam_id}")
                    break
                out.write(frame)

            out.release()
            log.info(f"[Recorder] Finished recording file: {file_name}")

        cap.release()

    def stop(self):
        self.running = False
        self.wait()            
