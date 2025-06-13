import os
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
            self.running = False
            self.recording_finished.emit(self.cam_id)
            return

        # Get first valid frame to detect resolution
        ret, frame = cap.read()
        if not ret or frame is None:
            log.warning(f"[Recorder] No frame received from Camera {self.cam_id}")
            cap.release()
            self.running = False
            self.recording_finished.emit(self.cam_id)
            return

        height, width = frame.shape[:2]
        log.info(f"[Recorder] Camera {self.cam_id} frame size: {width}x{height}")

        # Detect FPS from the capture device
        fps = cap.get(cv2.CAP_PROP_FPS)
        # if fps <= 0 or fps > 60:  # Sanity check for FPS value
        if fps <= 0:
            fps = 20.0  # Default fallback FPS
            log.info(f"[Recorder] Using default FPS: {fps}")
        else:
            log.info(f"[Recorder] Camera {self.cam_id} FPS detected: {fps}")

        # Create new file for current hour
        now = datetime.now()
        date_folder = now.strftime("%d-%m-%Y")
        minute = now.strftime("%H%M")
        next_minute = (now + timedelta(minutes=1)).strftime("%H%M")
        base_folder = f"recordings/{date_folder}/camera{self.cam_id}"
        os.makedirs(base_folder, exist_ok=True)

        file_name = f"{self.camera_name}_{now.strftime('%d%m%Y')}_{minute}_{next_minute}.avi"
        full_path = os.path.join(base_folder, file_name)

        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(full_path, fourcc, fps, (width, height))

        if not out.isOpened():
            log.error(f"[Recorder] Failed to open VideoWriter for {full_path}")
            cap.release()
            self.running = False
            self.recording_finished.emit(self.cam_id)
            return

        log.info(f"[Recorder] Started writing: {full_path}")

        start_time = datetime.now()
        frame_count = 0
        target_frames = int(fps * 3600)  # Total frames needed for 1 hhour
        frame_interval = 1.0 / fps  # Time between frames in seconds

        log.info(f"[Recorder] Starting recording. Target: {target_frames} frames at {fps} FPS")
        next_frame_time = start_time

        while self.running and frame_count < target_frames:
            current_time = datetime.now()
            elapsed_time = (current_time - start_time).total_seconds()
            
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
                log.info(f"[Recorder] Camera {self.cam_id}: Frame {frame_count}/{target_frames}, Time: {elapsed_time:.2f}s")

            # Calculate time until next frame should be captured
            next_frame_time = start_time + timedelta(seconds=frame_count * frame_interval)
            sleep_time = (next_frame_time - datetime.now()).total_seconds()
            
            if sleep_time > 0:
                cv2.waitKey(int(sleep_time * 1000))

        final_time = (datetime.now() - start_time).total_seconds()
        log.info(f"[Recorder] Recording complete. Duration: {final_time:.2f}s, Frames: {frame_count}")

        out.release()
        cap.release()
        log.info(f"[Recorder] Finished {file_name}. Total frames: {frame_count}")


    def stop(self):
        self.running = False
        self.wait()
