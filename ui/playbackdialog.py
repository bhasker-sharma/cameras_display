from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QTimeEdit, QPushButton, QWidget, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import QDate, QTime, Qt, pyqtSignal
from PyQt5.QtGui import QTextCharFormat, QColor
import os
import vlc
import datetime
from ui.responsive import ScreenScaler
from utils.logging import Logger
from utils.helper import get_all_recorded_cameras
from core.camera_playback_worker import CameraPlaybackWorker
import json
import os
from core.camera_playback_worker import CameraPlaybackWorker

log = Logger.get_logger(name="DebugPlayback", log_file="pipeline1.log")
   

# ========== MAIN PLAYBACK DIALOG ==========
class PlaybackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Playback Dialog")

        # Responsive scaling
        self.scaler = ScreenScaler()
        screen_w = self.scaler.width
        screen_h = self.scaler.height
        self.setMinimumSize(int(screen_w * 0.6), int(screen_h * 0.6))

        # Main layout
        self.main_layout = QHBoxLayout()
        self.setLayout(self.main_layout)

        # Control panel (left)
        self.control_panel = ControlPanel()
        self.main_layout.addWidget(self.control_panel, 1)

        # Preview panel (right)
        self.preview_panel = PreviewPanel()
        self.main_layout.addWidget(self.preview_panel, 3)

        # Playback worker
        self.worker = CameraPlaybackWorker(self.preview_panel.get_video_frame())

        # Connect signals
        self.control_panel.preview_requested.connect(self.handle_preview)
        self.control_panel.extract_requested.connect(self.handle_extract)
        self.control_panel.info_requested.connect(self.handle_info)

    def handle_preview(self, cam, date_str, start_time, end_time):
        log.info(f"[UI] Preview requested: {cam}, {date_str}, {start_time.toString()} → {end_time.toString()}")

        path, error = self.worker.preview_clip(cam, date_str, start_time, end_time)
        if error:
            QMessageBox.warning(self, "Preview Error", error)

    def handle_extract(self):
        log.info("[UI] Extract requested")
        path, error = self.worker.extract_clip(self)
        if error:
            QMessageBox.warning(self, "Extract Error", error)
        else:
            QMessageBox.information(self, "Saved", f"Clip saved to:\n{path}")

    def handle_info(self, cam, date_str):
        log.info(f"[UI] Info requested for {cam} on {date_str}")
        metadata_entries = self.worker.get_metadata_for_display(cam, date_str)

        if not metadata_entries:
            QMessageBox.information(self, "No Data", "No metadata found.")
            return

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["File Name", "Start Time", "End Time"])
        table.setRowCount(len(metadata_entries))

        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.setColumnWidth(1, 100)
        table.setColumnWidth(2, 100)

        for row, entry in enumerate(metadata_entries):
            item0 = QTableWidgetItem(entry["file"])
            item1 = QTableWidgetItem(entry["start"])
            item2 = QTableWidgetItem(entry["end"])
            for item in (item0, item1, item2):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 0, item0)
            table.setItem(row, 1, item1)
            table.setItem(row, 2, item2)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Recording Info – {cam}")
        layout = QVBoxLayout(dialog)
        layout.addWidget(table)
        dialog.setMinimumWidth(500)
        dialog.exec_()



# ========== CONTROL PANEL (LEFT UI) ==========
class ControlPanel(QWidget):
    preview_requested = pyqtSignal(str, str, QTime, QTime)  # camera, date, start_time, end_time
    extract_requested = pyqtSignal()
    info_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.recorded_cameras = get_all_recorded_cameras()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Camera dropdown
        self.camera_dropdown = QComboBox()
        self.camera_dropdown.addItems(self.recorded_cameras)
        self.camera_dropdown.currentTextChanged.connect(self.highlight_available_dates)

        #single date picker
        self.date_picker = QDateEdit(calendarPopup=True)
        today = QDate.currentDate()
        self.date_picker.setDate(today)  
        self.date_picker.setDisplayFormat("yyyy-MM-dd")
        self.date_picker.setStyleSheet("QCalendarWidget QAbstractItemView { selection-background-color: green; }")
     
        #start and end time pickers
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        
        self.start_time.setTime(QTime(0, 0))
        self.end_time.setTime(QTime(0, 0))
        
        #buttons
        self.info_button = QPushButton("📋 TIME ZONE")
        self.preview_button = QPushButton("Preview")
        self.extract_button = QPushButton("Extract")

        self.layout.addWidget(QLabel("Select camera"))
        self.layout.addWidget(self.camera_dropdown)
        self.layout.addWidget(QLabel("Select date"))
        self.layout.addWidget(self.date_picker)
        self.layout.addWidget(QLabel("Start time"))
        self.layout.addWidget(self.start_time)
        self.layout.addWidget(QLabel("End time"))
        self.layout.addWidget(self.end_time)
        self.layout.addWidget(self.info_button)
        self.layout.addWidget(self.preview_button)
        self.layout.addWidget(self.extract_button)
        self.layout.addStretch()

        self.preview_button.clicked.connect(self.emit_preview)
        self.extract_button.clicked.connect(self.extract_requested.emit)
        self.info_button.clicked.connect(self.emit_info)
        
        # Trigger initial highlight
        self.highlight_available_dates(self.camera_dropdown.currentText())

    def emit_preview(self):
        self.preview_requested.emit(
            self.camera_dropdown.currentText(),
            self.date_picker.date().toString("yyyy_MM_dd"),
            self.start_time.time(),
            self.end_time.time()
        )

    def emit_info(self):
        self.info_requested.emit(
            self.camera_dropdown.currentText(),
            self.date_picker.date().toString("yyyy_MM_dd")
        )

    def highlight_available_dates(self, cam_name):
        calendar = self.date_picker.calendarWidget()
        fmt_default = QTextCharFormat()
        fmt_default.setBackground(QColor("transparent"))

        fmt_highlight = QTextCharFormat()
        fmt_highlight.setBackground(QColor("green"))

        # Clear previous formatting
        for d in range(1, 32):
            for m in range(1, 13):
                try:
                    date = QDate(QDate.currentDate().year(), m, d)
                    calendar.setDateTextFormat(date, fmt_default)
                except:
                    continue

        # Backend call moved here
        available_dates = CameraPlaybackWorker.get_available_recording_dates(cam_name)
        for date in available_dates:
            calendar.setDateTextFormat(date, fmt_highlight)

# ========== PREVIEW PANEL (VIDEO DISPLAY) ==========
class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setStyleSheet("background-color: #333; border: 1px solid #555;")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.video_frame = QWidget(self)
        self.video_frame.setStyleSheet("background-color: black;")
        layout.addWidget(self.video_frame)

    def get_video_frame(self):
        return self.video_frame

    def get_win_id(self):
        return int(self.video_frame.winId())
        
    
    