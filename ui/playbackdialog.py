from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QTimeEdit, QPushButton, QWidget, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import QDate, QTime, Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QTextCharFormat, QColor, QPainter, QPen, QFont
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

# ========== LOADING SPINNER WIDGET ==========
class LoadingSpinner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self.angle = 0
        
        # Timer for animation
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)
        
        # Set up widget properties
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px;")
        
    def start_animation(self):
        self.timer.start(50)  # Update every 50ms for smooth animation
        self.show()
        
    def stop_animation(self):
        self.timer.stop()
        self.hide()
        
    def rotate(self):
        self.angle = (self.angle + 10) % 360
        self.update()  # Trigger paintEvent
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background circle
        painter.setPen(QPen(QColor(100, 100, 100), 3))
        painter.drawEllipse(20, 20, 40, 40)
        
        # Draw spinning arc
        painter.setPen(QPen(QColor(0, 150, 255), 4))
        painter.drawArc(20, 20, 40, 40, self.angle * 16, 90 * 16)  # 90 degree arc
        
        # Draw center text
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Arial", 8))
        painter.drawText(self.rect(), Qt.AlignCenter, "Loading...")

# ========== LOADING OVERLAY ==========
class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        self.spinner = LoadingSpinner()
        layout.addWidget(self.spinner, 0, Qt.AlignCenter)
        
        self.status_label = QLabel("Processing video clip...")
        self.status_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        self.hide()
        
    def show_loading(self, message="Processing video clip..."):
        self.status_label.setText(message)
        self.spinner.start_animation()
        self.show()
        self.raise_()  # Bring to front
        
    def hide_loading(self):
        self.spinner.stop_animation()
        self.hide()
        
    def resizeEvent(self, event):
        # Make sure overlay covers the entire parent
        if self.parent():
            self.resize(self.parent().size())
        super().resizeEvent(event)
   

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
        
        # Connect worker signals for loading animation
        self.worker.ffmpeg_started.connect(lambda: self.preview_panel.show_loading("Extracting video clip..."))
        self.worker.ffmpeg_finished.connect(self.on_ffmpeg_finished)

    def on_ffmpeg_finished(self, success, error_message):
        """Handle FFmpeg completion - hide loading and show errors if any"""
        self.preview_panel.hide_loading()
        if not success and error_message:
            QMessageBox.warning(self, "Preview Error", f"Failed to process video: {error_message}")

    def handle_preview(self, cam, date_str, start_time, end_time):
        log.info(f"[UI] Preview requested: {cam}, {date_str}, {start_time.toString()} → {end_time.toString()}")

        success, error = self.worker.preview_clip(cam, date_str, start_time, end_time)
        if error:
            QMessageBox.warning(self, "Preview Error", error)

    def handle_extract(self):
        log.info("[UI] Extract requested")
        
        # Get the preview filename as a suggestion
        suggested_name = self.worker.get_preview_file_name()
        if not suggested_name:
            suggested_name = "extracted_clip.mp4"
        
        # Ask user where to save the file
        target_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Extracted Clip", 
            suggested_name,
            "MP4 Files (*.mp4);;All Files (*)"
        )
        
        if not target_path:  # User cancelled
            return
            
        success, error = self.worker.extract_clip(target_path)
        if error:
            QMessageBox.warning(self, "Extract Error", error)
        else:
            QMessageBox.information(self, "Saved", f"Clip saved to:\n{target_path}")
    
    def handle_info_row_double_clicked(self, row, column):
        log.info(f"[UI Debug] Double-clicked row {row}, column {column}")
        table = self.info_table
        item0 = table.item(row, 0)
        real_start = item0.data(Qt.UserRole)
        duration = item0.data(Qt.UserRole + 1)
        log.info(f"[UI Debug] Retrieved real_start: {real_start}, duration: {duration}")
        
        if real_start and duration:
            from datetime import datetime, timedelta
            from PyQt5.QtCore import QTime
            start_dt = datetime.fromisoformat(real_start)
            end_dt = start_dt + timedelta(seconds=duration)
            log.info(f"[UI Debug] Calculated start_dt: {start_dt}, end_dt: {end_dt}")
            
            start_qtime = QTime(start_dt.hour, start_dt.minute, start_dt.second)
            end_qtime = QTime(end_dt.hour, end_dt.minute, end_dt.second)
            log.info(f"[UI Debug] QTime objects: {start_qtime.toString()} to {end_qtime.toString()}")
            
            # Set the time fields for reference
            self.control_panel.start_time.setTime(start_qtime)
            self.control_panel.end_time.setTime(end_qtime)
            
            # Play the full video directly (no extraction needed)
            log.info(f"[UI Debug] Playing full video directly...")
            success, error = self.worker.play_full_video(
                self.control_panel.camera_dropdown.currentText(),
                self.control_panel.date_picker.date().toString("yyyy_MM_dd"),
                real_start
            )
            
            if error:
                QMessageBox.warning(self, "Playback Error", error)
                
        else:
            log.warning(f"[UI Debug] Missing real_start or duration data")
        
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
            # Store real start and duration in item0
            item0.setData(Qt.UserRole, entry.get("real_start"))
            item0.setData(Qt.UserRole + 1, entry.get("duration"))
            for item in (item0, item1, item2):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row, 0, item0)
            table.setItem(row, 1, item1)
            table.setItem(row, 2, item2)

        # Save table as instance variable for access in the slot
        self.info_table = table
        table.cellDoubleClicked.connect(self.handle_info_row_double_clicked)
        
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
        
        # Add loading overlay
        self.loading_overlay = LoadingOverlay(self)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Make sure the loading overlay covers the entire preview panel
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.resize(self.size())

    def show_loading(self, message="Processing video clip..."):
        self.loading_overlay.show_loading(message)
        
    def hide_loading(self):
        self.loading_overlay.hide_loading()

    def get_video_frame(self):
        return self.video_frame

    def get_win_id(self):
        return int(self.video_frame.winId())
        
    
    