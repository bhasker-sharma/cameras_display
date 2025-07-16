from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QTimeEdit, QPushButton, QWidget, QFileDialog, QMessageBox
)
from PyQt5.QtCore import QDate, QTime
from PyQt5.QtGui import QTextCharFormat, QColor
import os
import vlc
import datetime
from ui.responsive import ScreenScaler
from utils.logging import Logger
from utils.helper import get_all_recorded_cameras , find_recording_file_for_time_range, get_available_metadata_for_camera
import subprocess
import json
from datetime import datetime,time
from PyQt5.QtCore import QTimer

log = Logger.get_logger(name="DebugPlayback",log_file="pipeline1.log")

class PlaybackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Responsive scaling
        self.scaler = ScreenScaler()
        screen_w = self.scaler.width
        screen_h = self.scaler.height
        self.setMinimumSize(int(screen_w * 0.6), int(screen_h * 0.6))

        self.setWindowTitle("Playback Dialog")
        log.debug("Initializing PlaybackDialog")
        
        # VLC player instance
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()

        #load camera list
        self.recorded_cameras = get_all_recorded_cameras()
        log.info(f"Available recorded cameras: {self.recorded_cameras}")

        # Main layout
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        # Build and add left and right panels
        self.build_control_panel()
        self.build_video_preview()

    
    def build_control_panel(self):
        self.control_layout = QVBoxLayout()

        self.camera_dropdown = QComboBox()
        self.recorded_cameras = get_all_recorded_cameras()
        self.camera_dropdown.addItems(self.recorded_cameras)

        self.start_date = QDateEdit(calendarPopup=True)
        self.end_date = QDateEdit(calendarPopup=True)
        self.start_time = QTimeEdit()
        self.end_time = QTimeEdit()

        today = QDate.currentDate()
        self.start_date.setDate(today)
        self.end_date.setDate(today)

        self.start_time.setTime(QTime(0, 0))
        self.end_time.setTime(QTime(0, 0))

        self.preview_button = QPushButton("Preview")
        self.preview_button.setStyleSheet("background-color: #e06666; color: white;")
        self.extract_button = QPushButton("Extract")

        self.control_layout.addWidget(QLabel("Select camera"))
        self.control_layout.addWidget(self.camera_dropdown)
        self.control_layout.addWidget(QLabel("Start date"))
        self.control_layout.addWidget(self.start_date)
        self.control_layout.addWidget(QLabel("End date"))
        self.control_layout.addWidget(self.end_date)
        self.control_layout.addWidget(QLabel("Start time"))
        self.control_layout.addWidget(self.start_time)
        self.control_layout.addWidget(QLabel("End time"))
        self.control_layout.addWidget(self.end_time)
        self.control_layout.addWidget(self.preview_button)
        self.control_layout.addWidget(self.extract_button)
        self.control_layout.addStretch()

        # Wrap in QWidget for layout
        left_widget = QWidget()
        left_widget.setLayout(self.control_layout)
        self.main_layout.addWidget(left_widget, 1)

        # Connect button
        self.preview_button.clicked.connect(self.preview_video)
        self.extract_button.clicked.connect(self.extract_video)
    
        # Trigger date highlight initially
        if self.camera_dropdown.count() > 0:
            self.update_available_dates(self.camera_dropdown.currentText())

    def build_video_preview(self):
        self.video_frame = QWidget()
        self.video_frame.setStyleSheet("background-color: #ccc;")
        self.main_layout.addWidget(self.video_frame, 3)

    def preview_video(self):
        import subprocess

        cam_name = self.camera_dropdown.currentText()
        date_str = self.start_date.date().toString("yyyy_MM_dd")
        start_time = self.start_time.time()
        end_time = self.end_time.time()

        log.debug(f"Previewing video for {cam_name} on {date_str} from {start_time.toString()} to {end_time.toString()}")   

        video_path, metadata_path, recording_start = find_recording_file_for_time_range(
            cam_name, date_str, start_time, end_time
        )

        if not video_path or not os.path.exists(metadata_path):
            log.warning("no matching viedo or metadata file found")
            get_available_metadata_for_camera(cam_name, date_str)
            QMessageBox.warning(self, "Recording Not Found", f"No recording found for selected time.")
            return
        try:
            # Load metadata and compute offset + duration
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            recording_start = datetime.fromisoformat(metadata["start_time"])
            
            if isinstance(start_time, QTime):
                start_time = time(start_time.hour(), start_time.minute(), start_time.second())
            if isinstance(end_time, QTime):
                end_time = time(end_time.hour(), end_time.minute(), end_time.second())
            clip_start_dt = datetime.combine(recording_start.date(), start_time)
            clip_end_dt = datetime.combine(recording_start.date(), end_time)
            if clip_start_dt < recording_start:
                log.warning(f"Clip start time {clip_start_dt} is before recording start {recording_start}. Adjusting to recording start.")
                clip_start_dt = recording_start
            if clip_end_dt <= clip_start_dt:
                log.warning(f"Clip end time {clip_end_dt} is not after clip start {clip_start_dt}. Aborting preview.")
                QMessageBox.warning(self, "Invalid Time Range", "End time must be after start time.")
                return
            
            self.offset_seconds = (clip_start_dt - recording_start).total_seconds()
            duration_seconds = (clip_end_dt - clip_start_dt).total_seconds()

            log.info(f"calculated offset: {self.offset_seconds}, duration: {duration_seconds}")
            if self.offset_seconds < 0 or duration_seconds <= 0:
                QMessageBox.warning(self, "Invalid Time", "Start/end time is invalid or out of bounds.")
                return

            # Prepare temp clip path
            user_start_str = start_time.strftime("%H_%M_%S")
            user_end_str = end_time.strftime("%H_%M_%S")
            self.preview_filename = f"{cam_name}_{date_str}_{user_start_str}_{user_end_str}.mp4"
            self.preview_path = os.path.join("temp", self.preview_filename)
            os.makedirs("temp", exist_ok=True)

            # Extract using FFmpeg
            cmd = [
                "ffmpeg", "-ss", str(self.offset_seconds), "-i", video_path,
                "-t", str(duration_seconds), "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                self.preview_path
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info(f"Preview video saved to {self.preview_path}")

            # Load into VLC
            media = self.vlc_instance.media_new(self.preview_path)
            self.player.set_media(media)
            self.player.set_hwnd(int(self.video_frame.winId()))
            self.player.play()
        except Exception as e:
            log.error(f"Error during video preview: {e}")
            QMessageBox.critical(self, "Playback Error", f"Failed to preview video:\n{str(e)}")
            return
      
    def extract_video(self):
        log.debug("Triggered extract_video()")

        if not hasattr(self, "preview_path"):
            log.error("preview_path attribute not set on class.")
            QMessageBox.warning(self, "Missing Data", "Preview path not set. Please preview a clip first.")
            return

        if not os.path.exists(self.preview_path):
            log.error(f"Preview file not found at: {self.preview_path}")
            QMessageBox.warning(self, "File Not Found", "Preview file does not exist.")
            return

        if not hasattr(self, "preview_filename") or not self.preview_filename:
            log.error("preview_filename is not defined.")
            QMessageBox.critical(self, "Filename Error", "No valid preview filename found.")
            return

        # Use Save File dialog
        suggested_name = self.preview_filename
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Extracted Clip",
            os.path.join(os.getcwd(), suggested_name),
            "MP4 files (*.mp4);;All files (*)"
        )
        log.debug(f"User selected output path: {save_path}")

        if not save_path:
            log.info("User cancelled the save dialog.")
            return

        try:
            import shutil
            shutil.copyfile(self.preview_path, save_path)
            log.info(f"Clip successfully saved to: {save_path}")
            QMessageBox.information(self, "Clip Saved", f"Saved successfully to:\n{save_path}")
        except FileNotFoundError:
            log.exception(f"Preview file missing during save: {self.preview_path}")
            QMessageBox.critical(self, "Save Error", "Preview file could not be found during saving.")
        except PermissionError:
            log.exception(f"Permission denied while saving to: {save_path}")
            QMessageBox.critical(self, "Save Error", "Permission denied. Please choose another folder.")
        except Exception as e:
            log.exception(f"Unexpected error during clip save: {e}")
            QMessageBox.critical(self, "Save Error", f"An unexpected error occurred:\n{str(e)}")

    def update_available_dates(self, cam_name):
        log.debug(f"Updating available dates for camera: {cam_name}")
        recordings_root = "recordings"
        green_format = QTextCharFormat()
        green_format.setForeground(QColor("green"))

        # Clear previous formatting
        self.start_date.calendarWidget().setDateTextFormat(QDate(), QTextCharFormat())
        self.end_date.calendarWidget().setDateTextFormat(QDate(), QTextCharFormat())

        if not os.path.exists(recordings_root):
            return

        for folder in os.listdir(recordings_root):
            folder_path = os.path.join(recordings_root, folder)
            cam_path = os.path.join(folder_path, cam_name)

            if os.path.isdir(cam_path):
                try:
                    date = QDate.fromString(folder, "yyyy_MM_dd")
                    if date.isValid():
                        self.start_date.calendarWidget().setDateTextFormat(date, green_format)
                        self.end_date.calendarWidget().setDateTextFormat(date, green_format)
                except Exception as e:
                    log.warning(f"Invalid date folder: {folder} — {e}")
