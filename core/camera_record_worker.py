from PyQt5.QtCore import QThread, pyqtSignal
import os
import subprocess
import datetime
import time
import re
from utils.logging import log
import json
from utils.helper import sanitize_filename, save_metadata
from utils.subproc import win_no_window_kwargs


class CameraRecorderWorker(QThread):
    recording_finished = pyqtSignal(int)

    def __init__(self, cam_id, cam_name, rtsp_url, record_enabled):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.record_enabled = record_enabled
        self.running = False
        self.process = None
        self.recording_dir = "recordings"
        self.video_start_time = None
        self.metadata_file = None

        self.cam_name = sanitize_filename(cam_name or f"Camera_{cam_id}")
        log.debug(f"[Recorder] Sanitized camera name: {self.cam_name}")

    def get_output_path(self, timestamp):
        date_str = timestamp.strftime("%Y_%m_%d")
        time_str = timestamp.strftime("%H_%M_%S")
        base_path = os.path.join(self.recording_dir, date_str, self.cam_name)
        os.makedirs(base_path, exist_ok=True)

        filename = f"{self.cam_name}_{date_str}_{time_str}.mp4"
        log_path = os.path.join(base_path, f"{self.cam_name}_{date_str}_{time_str}.log")

        return os.path.join(base_path, filename), log_path

    def build_ffmpeg_command(self, output_file):
        return [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            "-an",  # No audio
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-g", "25",  # Force keyframe every 25 frames 
            "-f", "mp4",
            "-movflags", "+faststart+frag_keyframe+empty_moov",  # For smoother playback and fragmented MP4
            output_file
        ]

    def run(self):
        if not self.record_enabled:
            log.info(f"[Recorder] Recording is disabled for Camera {self.cam_name}")
            return

        self.running = True
        log.info(f"[Recorder] Starting recording for Camera {self.cam_name}")

        while self.running:
            start_time = datetime.datetime.now()
            self.video_start_time = start_time
            output_file, log_file = self.get_output_path(start_time)
            self.metadata_file = output_file.replace(".mp4", "_metadata.json")
            #save start time now 
            save_metadata(self.metadata_file, self.video_start_time)

            ffmpeg_cmd = self.build_ffmpeg_command(output_file)

            log.info(f"[Recorder] Writing to {output_file}")
            with open(log_file, "w", encoding="utf-8") as log_fh:
                self.process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=subprocess.PIPE,  
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    **win_no_window_kwargs()
                )

                # Calculate cutoff time (midnight or 24 hours max)
                next_midnight = (start_time + datetime.timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                next_cutoff = min(next_midnight, start_time + datetime.timedelta(hours=24))
                time_to_sleep = (next_cutoff - datetime.datetime.now()).total_seconds()

                if time_to_sleep > 0:
                    time.sleep(time_to_sleep)

                self.stop_ffmpeg()
                end_time = datetime.datetime.now()
                duration_seconds = (end_time - self.video_start_time).total_seconds()

                #update metadata with duration
                save_metadata(self.metadata_file, start_time, duration_seconds,end_time)

            if self.running:
                self.recording_finished.emit(self.cam_id)

        log.info(f"[Recorder] Thread for Camera {self.cam_name} has exited.")

    def stop_ffmpeg(self):
        if self.process and self.process.poll() is None:
            log.info(f"[Recorder] Stopping recording process for Camera {self.cam_name}")
            # Send 'q' to FFmpeg to stop recording
            self.process.stdin.write(b'q')
            self.process.stdin.flush()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warning(f"[Recorder] FFmpeg process hung — forcing kill for {self.cam_name}")
                self.process.kill()
            self.process = None

    def stop(self):
        log.info(f"[Recorder] Stop requested for Camera {self.cam_name}")
        self.running = False
        if self.video_start_time and self.metadata_file:
            end_time = datetime.datetime.now()
            duration_seconds = (end_time - self.video_start_time).total_seconds()
            save_metadata(self.metadata_file, self.video_start_time, duration_seconds,end_time)

        self.stop_ffmpeg()
        log.info(f"[Recorder] Recording stopped for Camera {self.cam_name}")
