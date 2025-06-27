import os,json
import cv2
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, pyqtSignal
from utils.logging import log

class CameraRecorderWorker(QThread):
    recording_finished = pyqtSignal(int)  # Signal to emit camera_id when recording finishes

    def __init__(self, cam_id, rtsp_url, camera_name):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.camera_name = camera_name
        self.running = False

    def run(self):
        self.running = True
        while self.running:  # Continuous recording loop
            self._record_one_hour()

    def _record_one_hour(self):
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

        if not cap.isOpened():
            log.error(f"[Recorder] Failed to open RTSP for Camera {self.cam_id}")
            self.cleanup(cap)
            return

        # Get first valid frame to detect resolution
        ret, frame = cap.read()
        if not ret or frame is None:
            log.warning(f"[Recorder] No frame received from Camera {self.cam_id}")
            self.cleanup(cap)
            return
        
        height, width = frame.shape[:2]
        # Detect FPS from the capture device
        fps = cap.get(cv2.CAP_PROP_FPS)         
        fps = fps if 0 < fps <= 60 else 20  # Default to 25 FPS if detection fails
        log.info(f"[Recorder] Camera {self.cam_id}: resolution ={width}*{height},fps = {fps}")
            
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        frame_interval = 1.0 / fps
        max_frames = int(fps * 86500) #frame for all the day
        current_date = datetime.now().date()
        start_time = datetime.now()
        frame_count = 0
        
        out, metadata_path = self.open_writer(start_time, current_date, width, height, fourcc, fps)
        log.info(f"[Recorder] Started {metadata_path.replace('.json','')}")

        while self.running:
            now = datetime.now()
            if frame_count >= max_frames or now.date() != current_date:
                out.release()
                log.info(f"[Recorder] Rollover: recorded {frame_count} frame")
                current_date = now.date()
                start_time = now
                frame_count = 0
                out, metadata_path = self.open_writer(start_time, current_date, width, height, fourcc, fps)
            
            ret, frame = cap.read()
            if not ret or frame is None:
                log.warning(f"[Recorder] Frame read failed for Camera {self.cam_id}")
                break
            if frame.shape[:2] != (height, width):
                log.warning(f"[Recorder] Frame size mismatch. Resizing...")
                frame = cv2.resize(frame, (width, height))
                # First: overlay the camera name (green, top-left)
            cv2.putText(
                frame,
                self.camera_name,
                (10, 30),  # x, y (top-left corner)
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,       # font scale
                (0, 255, 0),  # green color
                2,         # thickness
                cv2.LINE_AA
            )
            timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
            cv2.putText(frame, timestamp, 
                        (10, height - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.7, 
                        (255, 255, 255), 
                        2,
                        cv2.LINE_AA)
            
            out.write(frame)
            frame_count += 1

            if frame_count % int(fps*60) == 0:
                elapsed = (now - start_time).total_seconds()
                log.info(f"[Recorder] Cam{self.cam_id}: {frame_count} frames (~{elapsed:.1f}s)")

            sleep_time = start_time + timedelta(seconds=frame_count * frame_interval) - datetime.now()
            if sleep_time.total_seconds() > 0:
                cv2.waitKey(int(sleep_time.total_seconds()*1000))

        log.info(f"[Recorder] Finished: {frame_count} frames recorded.")
        out.release()
        cap.release()
        self.recording_finished.emit(self.cam_id)

    def open_writer(self, ts, date_obj, width, height, fourcc, fps):
        date_str = date_obj.strftime("%d-%m-%Y")
        folder = f"recordings/{date_str}/camera{self.cam_id}"
        os.makedirs(folder, exist_ok=True)

        file_ts = ts.strftime("%Y%m%d_%H%M%S")
        avi = os.path.join(folder, f"{self.camera_name}_{file_ts}.avi")
        json_path = avi.replace(".avi", ".json")
        out = cv2.VideoWriter(avi, fourcc, fps, (width, height))

        with open(json_path, "w") as f:
            f.write(json.dumps({"start_time": ts.strftime("%Y-%m-%d %H:%M:%S")}))
        return out, json_path
    

    def cleanup(self, cap):
        cap.release()
        self.running = False
        self.recording_finished.emit(self.cam_id)

    def stop(self):
        self.running = False
        self.wait()
