from PyQt5.QtCore import QThread, pyqtSignal
import os
import subprocess
import datetime
import time
import re
from utils.logging import log
import json
from utils.helper import sanitize_filename, save_metadata
from utils.subproc import win_no_window_kwargs, kill_process_tree
from utils.paths import get_ffmpeg_path, get_data_dir


class CameraRecorderWorker(QThread):
    recording_finished = pyqtSignal(int)

    def __init__(self, cam_id, cam_name, rtsp_url, record_enabled, recording_dir=None):
        super().__init__()
        self.cam_id = cam_id
        self.rtsp_url = rtsp_url
        self.record_enabled = record_enabled
        self.running = False
        self.process = None
        self.recording_dir = recording_dir or os.path.join(get_data_dir(), "recordings")
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
        return os.path.join(base_path, filename)

    def build_ffmpeg_command(self, output_file):
        log.info(f"[Recorder] Using CPU H.264 for {self.cam_name}")
        return [
            get_ffmpeg_path(), "-hwaccel", "none", "-i", self.rtsp_url, "-an",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-g", "25", "-f", "mp4", "-movflags", "+faststart+frag_keyframe+empty_moov",
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
            output_file = self.get_output_path(start_time)
            self.metadata_file = output_file.replace(".mp4", "_metadata.json")
            save_metadata(self.metadata_file, self.video_start_time)

            ffmpeg_cmd = self.build_ffmpeg_command(output_file)

            log.info(f"[Recorder] Writing to {output_file}")
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **win_no_window_kwargs()
            )

            # Calculate cutoff time (midnight or 24 hours max)
            next_midnight = (start_time + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            next_cutoff = min(next_midnight, start_time + datetime.timedelta(hours=24))
            time_to_sleep = (next_cutoff - datetime.datetime.now()).total_seconds()

            # Sleep in small intervals so stop() is responsive
            while time_to_sleep > 0 and self.running:
                time.sleep(min(time_to_sleep, 1.0))
                time_to_sleep = (next_cutoff - datetime.datetime.now()).total_seconds()

            self.stop_ffmpeg()
            end_time = datetime.datetime.now()
            duration_seconds = (end_time - self.video_start_time).total_seconds()
            save_metadata(self.metadata_file, start_time, duration_seconds, end_time)

            if self.running:
                self.recording_finished.emit(self.cam_id)

        log.info(f"[Recorder] Thread for Camera {self.cam_name} has exited.")

    def stop_ffmpeg(self):
        if self.process and self.process.poll() is None:
            log.info(f"[Recorder] Stopping recording process for Camera {self.cam_name}")
            # Send 'q' to FFmpeg to stop recording gracefully
            try:
                self.process.stdin.write(b'q')
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                log.warning(f"[Recorder] FFmpeg stdin already closed for {self.cam_name}")
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log.warning(f"[Recorder] FFmpeg process hung — forcing kill for {self.cam_name}")
                kill_process_tree(self.process.pid)
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
