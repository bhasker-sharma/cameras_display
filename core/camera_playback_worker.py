# core/camera_playback_worker.py

import os
import json
import subprocess
import datetime as dt
from datetime import datetime, time
from utils.helper import find_recording_file_for_time_range, get_available_metadata_for_camera
from utils.logging import Logger
import vlc
from PyQt5.QtCore import QDate,pyqtSignal, QThread, QObject


log = Logger.get_logger(name="PlaybackWorker", log_file="pipeline1.log")

class FFmpegWorker(QThread): 
    finished = pyqtSignal(bool, str)  # success, error_message

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
        self.success = False
        self.error_message = ""

    def run(self):
        try:
            import subprocess
            result = subprocess.run(self.cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.success = (result.returncode == 0)
            self.error_message = "" if self.success else "FFmpeg failed"
        except Exception as e:
            self.success = False
            self.error_message = str(e)
        self.finished.emit(self.success, self.error_message)
        
class CameraPlaybackWorker(QObject):
    # Signals to communicate with UI
    ffmpeg_started = pyqtSignal()
    ffmpeg_finished = pyqtSignal(bool, str)  # success, error_message
    video_loaded = pyqtSignal()  # New signal when video is loaded
    
    def __init__(self, video_widget):
        super().__init__()
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()
        self.video_widget = video_widget  # PreviewPanel's video_frame
        self.preview_path = None
        self.preview_filename = None

        # Attach VLC output to UI widget
        self.player.set_hwnd(int(self.video_widget.winId()))

    def _on_ffmpeg_done(self, success, error):
        # Emit signal to hide loading
        self.ffmpeg_finished.emit(success, error)
        
        if success:
            log.info(f"[Preview] Clip saved: {self.preview_path}")
            media = self.vlc_instance.media_new(self.preview_path)
            self.player.set_media(media)
            self.player.play()
            self.video_loaded.emit()  # Notify that video is loaded
        else:
            log.error(f"[Preview] FFmpeg error: {error}")
            # Optionally, emit a signal to the UI to show an error message
            
    def play_full_video(self, cam_name, date_str, real_start_time):
        """
        Play the full original video file directly without extraction.
        Used for double-click preview from info table.
        """
        log.info(f"[Play Full] Request: {cam_name} @ {date_str}, start_time: {real_start_time}")
        
        # Find the video file based on start time
        folder_path = os.path.join("recordings", date_str, cam_name)
        if not os.path.exists(folder_path):
            return False, f"Recording folder not found: {folder_path}"
        
        # Look for the video file that matches this start time
        for filename in os.listdir(folder_path):
            if filename.endswith("_metadata.json"):
                metadata_path = os.path.join(folder_path, filename)
                try:
                    with open(metadata_path, "r") as f:
                        metadata = json.load(f)
                    
                    if metadata["start_time"] == real_start_time:
                        # Found the matching metadata, get the video file
                        video_filename = filename.replace("_metadata.json", ".mp4")
                        video_path = os.path.join(folder_path, video_filename)
                        
                        if os.path.exists(video_path):
                            log.info(f"[Play Full] Playing: {video_path}")
                            # Play directly without extraction
                            media = self.vlc_instance.media_new(video_path)
                            self.player.set_media(media)
                            self.player.play()
                            self.video_loaded.emit()  # Notify that video is loaded
                            return True, None
                        else:
                            return False, f"Video file not found: {video_path}"
                            
                except Exception as e:
                    log.warning(f"Failed to read metadata: {metadata_path} — {e}")
                    continue
        
        return False, "No matching video file found for the selected recording."

    def preview_clip(self, cam_name, date_str, start_time, end_time):
        log.info(f"[Preview] Request: {cam_name} @ {date_str} from {start_time.toString()} to {end_time.toString()}")

        video_path, metadata_path, recording_start = find_recording_file_for_time_range(
            cam_name, date_str, start_time, end_time
        )

        if not video_path or not os.path.exists(metadata_path):
            log.warning("No matching video or metadata file found.")
            get_available_metadata_for_camera(cam_name, date_str)
            return False, "No recording found for selected time."

        try:
            # Load metadata and compute offset/duration
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            recording_start = datetime.fromisoformat(metadata["start_time"])

            clip_start_dt = datetime.combine(recording_start.date(), start_time.toPyTime())
            clip_end_dt = datetime.combine(recording_start.date(), end_time.toPyTime())
            
            if clip_start_dt < recording_start:
                clip_start_dt = recording_start

            if clip_end_dt <= clip_start_dt:
                return False, "End time must be after start time."

            offset_seconds = (clip_start_dt - recording_start).total_seconds()
            duration_seconds = (clip_end_dt - clip_start_dt).total_seconds()

            if offset_seconds < 0 or duration_seconds <= 0:
                return False, "Invalid time range or clip duration."

            # Prepare temp clip path
            user_start_str = start_time.toString("HH_mm_ss")
            user_end_str = end_time.toString("HH_mm_ss")
            self.preview_filename = f"{cam_name}_{date_str}_{user_start_str}_{user_end_str}.mp4"
            self.preview_path = os.path.join("temp", self.preview_filename)
            os.makedirs("temp", exist_ok=True)

            cmd = [
                "ffmpeg", "-ss", str(offset_seconds), "-i", video_path,
                "-t", str(duration_seconds), "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                self.preview_path
            ]
            
            # Emit signal that FFmpeg is starting
            self.ffmpeg_started.emit()
            
            self.ffmpeg_worker = FFmpegWorker(cmd)
            self.ffmpeg_worker.finished.connect(self._on_ffmpeg_done)
            self.ffmpeg_worker.start()
            return True, None
        
        except Exception as e:
            log.exception("[Preview] Error occurred")
            return False, f"Failed to preview: {str(e)}"

    def extract_clip(self, target_path):
        if not self.preview_path or not os.path.exists(self.preview_path):
            return False, "Preview file does not exist."

        try:
            import shutil
            shutil.copyfile(self.preview_path, target_path)
            log.info(f"[Extract] Clip saved to: {target_path}")
            return True, None
        except Exception as e:
            log.exception("[Extract] Error during clip save")
            return False, f"Failed to save clip: {str(e)}"

    def stop_playback(self):
        if self.player:
            self.player.stop()

    def get_preview_file_name(self):
        return self.preview_filename or ""

    def get_metadata_for_display(self, cam_name, date_str):
        folder_path = os.path.join("recordings", date_str, cam_name)
        entries = []

        if not os.path.exists(folder_path):
            return []

        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith("_metadata.json"):
                try:
                    with open(os.path.join(folder_path, filename), "r") as f:
                        meta = json.load(f)
                    start = datetime.fromisoformat(meta["start_time"])
                    duration = meta.get("duration_seconds")
                    end = start + dt.timedelta(seconds=duration) if duration else None
                    log.info(f"[Metadata Debug] Processing {filename}: real_start={meta['start_time']}, duration={duration}")
                    entries.append({
                        "file": filename.replace("_metadata.json", ".mp4"),
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M") if end else "🔴 Ongoing",
                        "real_start": meta["start_time"],  # ISO string
                        "duration": duration               # seconds (float)
                    })
                except Exception as e:
                    log.warning(f"Failed to read metadata: {filename} — {e}")
        return entries

    @staticmethod
    def get_available_recording_dates(cam_name, root="recordings"):
        """
        Returns a list of QDate objects where recordings exist for this camera.
        """
        available_dates = []

        if not os.path.exists(root):
            return []

        for folder_name in os.listdir(root):
            folder_path = os.path.join(root, folder_name)
            if not os.path.isdir(folder_path):
                continue

            cam_folder = os.path.join(folder_path, cam_name)
            if not os.path.exists(cam_folder):
                continue

            try:
                year, month, day = map(int, folder_name.split("_"))
                available_dates.append(QDate(year, month, day))
            except ValueError:
                continue

        return available_dates