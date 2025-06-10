import os
import cv2, shutil
import time
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
        reconnect_delay = 5  # seconds between reconnection attempts
        
        while self.running:
            try:
                # Open capture with larger buffer
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 10)

                if not cap.isOpened():
                    log.error(f"[Recorder] Failed to open RTSP for camera {self.cam_id}")
                    if self.running:
                        log.info(f"[Recorder] Retrying in {reconnect_delay} seconds...")
                        cap.release()
                        time.sleep(reconnect_delay)
                        continue
                    return

                # Get actual frame size and FPS from camera
                frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))
                
                # Fallback values if detection fails
                if frame_width == 0 or frame_height == 0:
                    frame_width, frame_height = 640, 480
                    log.warning(f"[Recorder] Could not detect resolution for Camera {self.cam_id}, using fallback 640x480")
                else:
                    log.info(f"[Recorder] Camera {self.cam_id} resolution: {frame_width}x{frame_height}")
                
                if fps == 0:
                    fps = 20
                    log.warning(f"[Recorder] Could not detect FPS for Camera {self.cam_id}, using fallback 20 FPS")
                else:
                    log.info(f"[Recorder] Camera {self.cam_id} FPS: {fps}")

                while self.running:
                    now = datetime.now()
                    date_folder = now.strftime("%d-%m-%Y")
                    hour = now.strftime("%H")
                    next_hour = (now + timedelta(hours=1)).strftime("%H")
                    base_folder = f"recordings/{date_folder}/camera{self.cam_id}"
                    
                    os.makedirs(base_folder, exist_ok=True)

                    file_name = f"{self.camera_name}_{now.strftime('%d%m%Y')}_{hour}_{next_hour}.mp4"
                    full_path = os.path.join(base_folder, file_name)
                    temp_path = full_path + ".temp"  # Use temporary file while recording
                    
                    log.info(f"[Recorder] Starting new file: {full_path}")

                    fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
                    out = None
                    frame_count = 0
                    consecutive_failures = 0
                    MAX_CONSECUTIVE_FAILURES = 30  # Allow 30 consecutive frame read failures
                    
                    try:
                        out = cv2.VideoWriter(temp_path, fourcc, fps, (frame_width, frame_height))
                        if not out.isOpened():
                            raise Exception("Failed to create VideoWriter")
                            
                        start_time = datetime.now()
                        
                        while self.running and (datetime.now() - start_time).seconds < 3600:
                            ret, frame = cap.read()
                            
                            if not ret or frame is None:
                                consecutive_failures += 1
                                log.warning(f"[Recorder] Failed to read frame from Camera {self.cam_id} ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})")
                                
                                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                                    log.error(f"[Recorder] Too many consecutive frame read failures for Camera {self.cam_id}")
                                    break
                                    
                                time.sleep(0.1)  # Short delay before retry
                                continue
                            
                            consecutive_failures = 0  # Reset on successful frame read
                            out.write(frame)
                            frame_count += 1

                        log.info(f"[Recorder] Recorded {frame_count} frames to {file_name}")
                        
                    except Exception as e:
                        log.error(f"[Recorder] Error during recording: {str(e)}")
                        
                    finally:
                        if out is not None:
                            out.release()
                            
                        # Handle the temporary file
                        if os.path.exists(temp_path):
                            if frame_count > 0:  # Only keep file if frames were recorded
                                if os.path.exists(full_path):
                                    os.remove(full_path)
                                os.rename(temp_path, full_path)
                            else:
                                os.remove(temp_path)
                                log.error(f"[Recorder] No frames recorded, removing empty file")

                    # If we broke out of the recording loop due to too many failures,
                    # break the capture loop to trigger a reconnection
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        break

            except Exception as e:
                log.error(f"[Recorder] Critical error: {str(e)}")
                if self.running:
                    log.info(f"[Recorder] Retrying in {reconnect_delay} seconds...")
                    time.sleep(reconnect_delay)
                
            finally:
                if cap is not None:
                    cap.release()

        log.info(f"[Recorder] Recording stopped for Camera {self.cam_id}")
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
