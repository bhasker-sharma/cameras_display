from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QTimeEdit, QPushButton, QWidget, QFileDialog
)
from PyQt5.QtCore import QDate, QTime
from PyQt5.QtGui import QTextCharFormat, QColor
import os
import vlc

from ui.responsive import ScreenScaler
from utils.logging import log
from utils.helper import get_recording_enabled_cameras



class PlaybackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Responsive scaling
        self.scaler = ScreenScaler()
        screen_w = self.scaler.width
        screen_h = self.scaler.height
        self.setMinimumSize(int(screen_w * 0.6), int(screen_h * 0.6))

        self.setWindowTitle("Playback Dialog")

        # VLC player instance
        self.vlc_instance = vlc.Instance()
        self.player = self.vlc_instance.media_player_new()

        #load camera list
        self.enabled_cameras = get_recording_enabled_cameras()
        # Main layout
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        # Build and add left and right panels
        self.build_control_panel()
        self.build_video_preview()

    def build_control_panel(self):
        self.control_layout = QVBoxLayout()

        self.camera_dropdown = QComboBox()
        self.enabled_cameras = get_recording_enabled_cameras()
        self.camera_dropdown.addItems(self.enabled_cameras.keys())

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

        # Trigger date highlight initially
        if self.camera_dropdown.count() > 0:
            self.update_available_dates(self.camera_dropdown.currentText())

    def build_video_preview(self):
        self.video_frame = QWidget()
        self.video_frame.setStyleSheet("background-color: #ccc;")
        self.main_layout.addWidget(self.video_frame, 3)

    def preview_video(self):
        # Temporary: manual file selection
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Video File", "", "MP4 Files (*.mp4)")
        if file_path:
            media = self.vlc_instance.media_new(file_path)
            self.player.set_media(media)
            self.player.set_xwindow(self.video_frame.winId())  # Linux; use .set_hwnd() on Windows
            self.player.play()
            
    def update_available_dates(self, cam_name):
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

