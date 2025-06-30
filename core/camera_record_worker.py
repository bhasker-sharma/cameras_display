import os, json, cv2, subprocess
from datetime import datetime, timedelta
from PyQt5.QtCore import QThread, pyqtSignal
from utils.logging import log

class CameraRecorderWorker(QThread):
    recording_finished = pyqtSignal(int)

    def __init__(self, cam_id, rtsp_url, camera_name):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.camera_name = camera_name
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            self._record_with_ffmpeg()

    def _record_with_ffmpeg(self):
        cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            log.error(f"[Recorder] Failed to open RTSP for Camera {self.cam_id}")
            return

        ret, frame = cap.read()
        if not ret or frame is None:
            log.warning(f"[Recorder] No frame from Camera {self.cam_id}")
            cap.release()
            return

        height, width = frame.shape[:2]
        fps = cap.get(cv2.CAP_PROP_FPS)
        fps = fps if 0 < fps <= 60 else 20

        log.info(f"[Recorder] Camera {self.cam_id}: resolution={width}x{height}, fps={fps}")

        start_time = datetime.now()
        current_date = start_time.date()
        frame_interval = 1.0 / fps
        frame_count = 0

        ffmpeg_proc, output_path, metadata_path = self._start_ffmpeg_writer(width, height, fps)
        self.latest_metadata_path = metadata_path

        while self.running:
            now = datetime.now()
            if now.date() != current_date or (now - start_time).total_seconds() >= 86400:
                log.info(f"[Recorder] Rollover: {frame_count} frames")
                ffmpeg_proc.stdin.close()
                ffmpeg_proc.wait()
                self.finalize_metadata(metadata_path)

                start_time = now
                current_date = now.date()
                frame_count = 0
                ffmpeg_proc, output_path, metadata_path = self._start_ffmpeg_writer(width, height, fps)
                self.latest_metadata_path = metadata_path

            ret, frame = cap.read()
            if not ret or frame is None:
                log.warning(f"[Recorder] Camera {self.cam_id} frame failed.")
                break

            # Overlay camera name and timestamp
            cv2.putText(frame, self.camera_name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2, cv2.LINE_AA)
            cv2.putText(frame, now.strftime("%d-%m-%Y %H:%M:%S"), (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2, cv2.LINE_AA)

            try:
                ffmpeg_proc.stdin.write(frame.tobytes())
            except Exception as e:
                log.error(f"[Recorder] FFmpeg write failed: {e}")
                break

            frame_count += 1
            if frame_count % int(fps * 60) == 0:
                elapsed = (now - start_time).total_seconds()
                log.info(f"[Recorder] Cam{self.cam_id}: {frame_count} frames (~{elapsed:.1f}s)")

            sleep_time = start_time + timedelta(seconds=frame_count * frame_interval) - datetime.now()
            if sleep_time.total_seconds() > 0:
                cv2.waitKey(int(sleep_time.total_seconds() * 1000))

        cap.release()
        ffmpeg_proc.stdin.close()
        ffmpeg_proc.wait()
        self.finalize_metadata(metadata_path)
        self.recording_finished.emit(self.cam_id)

    def _start_ffmpeg_writer(self, width, height, fps):
        now = datetime.now()
        date_str = now.strftime("%d-%m-%Y")
        ts = now.strftime("%Y%m%d_%H%M%S")
        folder = f"recordings/{date_str}/camera{self.cam_id}"
        os.makedirs(folder, exist_ok=True)

        avi_path = os.path.join(folder, f"{self.camera_name}_{ts}.avi")
        json_path = avi_path.replace(".avi", ".json")

        cmd = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "mjpeg",
        "-qscale:v", "3",
        avi_path
        ]

        log.debug(f"[Recorder] Starting FFmpeg: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        with open(json_path, "w") as f:
            f.write(json.dumps({"start_time": now.strftime("%Y-%m-%d %H:%M:%S")}))

        return proc, avi_path, json_path

    def stop(self):
        log.debug(f"[Recorder] stop() called for cam {self.cam_id}")
        self.running = False
        self.wait()
        try:
            if hasattr(self, 'latest_metadata_path'):
                self.finalize_metadata(self.latest_metadata_path)
        except Exception as e:
            log.error(f"[Recorder] finalize_metadata failed: {e}")

    def finalize_metadata(self, metadata_path):
        try:
            with open(metadata_path, "r+", encoding="utf-8") as f:
                meta = json.load(f)
                meta["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.seek(0)
                json.dump(meta, f, indent=4)
                f.truncate()
            log.debug(f"[Recorder] Updated metadata: {metadata_path}")
        except Exception as e:
            log.error(f"[Recorder] Failed to update metadata: {e}")
