from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDateEdit,
    QTimeEdit, QPushButton, QWidget, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSlider, QSizePolicy
)
from PyQt5.QtCore import QDate, QTime, Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QTextCharFormat, QColor, QPainter, QPen, QFont, QIcon
import os
import vlc
import datetime
import time
import json
from ui.responsive import ScreenScaler
from utils.logging import Logger
from utils.helper import get_all_recorded_cameras
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

# ========== MEDIA CONTROLS ==========
class MediaControls(QWidget):
    # Signals for player control
    play_pause_clicked = pyqtSignal()
    position_changed = pyqtSignal(float)  # 0.0 to 1.0
    volume_changed = pyqtSignal(int)  # 0 to 100
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = None
        self.total_duration = 0
        self.is_seeking = False
        
        # Timer to update position
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        self.position_timer.start(1000)  # Update every second
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Progress bar and time display
        progress_layout = QHBoxLayout()
        
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("color: white; font-weight: bold;")
        self.current_time_label.setMinimumWidth(50)
        
        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.setValue(0)
        self.position_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: #444;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border: 1px solid #777;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::add-page:horizontal {
                background: #666;
                border: 1px solid #777;
                height: 8px;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #5c5c5c;
                width: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
        """)
        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_slider_released)
        self.position_slider.valueChanged.connect(self.on_slider_moved)
        
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("color: white; font-weight: bold;")
        self.total_time_label.setMinimumWidth(50)
        
        progress_layout.addWidget(self.current_time_label)
        progress_layout.addWidget(self.position_slider)
        progress_layout.addWidget(self.total_time_label)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        # Play/Pause button
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setFixedSize(40, 30)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        self.play_pause_btn.clicked.connect(self.play_pause_clicked.emit)
        
        # Volume control
        volume_label = QLabel("🔊")
        volume_label.setStyleSheet("color: white;")
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(100)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: #444;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #0078d4;
                border: 1px solid #777;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #5c5c5c;
                width: 12px;
                margin: -3px 0;
                border-radius: 6px;
            }
        """)
        self.volume_slider.valueChanged.connect(self.volume_changed.emit)
        
        controls_layout.addWidget(self.play_pause_btn)
        controls_layout.addStretch()
        controls_layout.addWidget(volume_label)
        controls_layout.addWidget(self.volume_slider)
        
        layout.addLayout(progress_layout)
        layout.addLayout(controls_layout)
        
        self.setLayout(layout)
        self.setStyleSheet("background-color: #2d2d2d; border-top: 1px solid #555;")
        self.setFixedHeight(80)
        
        # Add keyboard shortcut support
        self.setFocusPolicy(Qt.StrongFocus)
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Space:
            self.play_pause_clicked.emit()
            event.accept()
        elif event.key() == Qt.Key_Left:
            if self.player and self.total_duration > 0:
                current_pos = self.player.get_position()
                new_pos = max(0, current_pos - (10000 / self.total_duration))
                self.player.set_position(new_pos)
            event.accept()
        elif event.key() == Qt.Key_Right:
            if self.player and self.total_duration > 0:
                current_pos = self.player.get_position()
                new_pos = min(1.0, current_pos + (10000 / self.total_duration))
                self.player.set_position(new_pos)
            event.accept()
        else:
            super().keyPressEvent(event)
        
    def set_player(self, player):
        """Connect to VLC player instance"""
        self.player = player
        if self.player:
            self.player.audio_set_volume(self.volume_slider.value())
            
    def on_slider_pressed(self):
        self.is_seeking = True
        
    def on_slider_released(self):
        if self.player and self.total_duration > 0:
            position = self.position_slider.value() / 1000.0
            self.player.set_position(position)
            # Only pause if user seeks to very end (99.5% or more)
            if position >= 0.995:
                self.player.pause()
                print(f"[Media Control] Seeked to end ({position:.3f}), pausing")
        self.is_seeking = False
        
    def on_slider_moved(self, value):
        if self.is_seeking and self.total_duration > 0:
            position = value / 1000.0
            current_seconds = int(position * self.total_duration / 1000)
            self.current_time_label.setText(self.format_time(current_seconds))
            
    def update_position(self):
        """Update position slider and time display"""
        if self.player and not self.is_seeking:
            position = self.player.get_position()
            length = self.player.get_length()
            state = self.player.get_state()
            
            if length > 0:
                self.total_duration = length
                self.position_slider.setValue(int(position * 1000))
                current_seconds = int(position * length / 1000)
                total_seconds = int(length / 1000)
                self.current_time_label.setText(self.format_time(current_seconds))
                self.total_time_label.setText(self.format_time(total_seconds))
                
                # More precise end-of-video detection - only change button if truly ended
                if state == vlc.State.Ended:
                    self.play_pause_btn.setText("▶")
                elif state == vlc.State.Playing:
                    self.play_pause_btn.setText("⏸")
                elif state == vlc.State.Paused:
                    self.play_pause_btn.setText("▶")
                else:
                    # For other states (Opening, Buffering, etc.), keep current button state
                    pass
                    
    def format_time(self, seconds):
        """Format seconds to MM:SS or HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
            
    def reset(self):
        """Reset controls to initial state"""
        self.position_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        self.play_pause_btn.setText("▶")
        self.total_duration = 0

# ========== MAIN PLAYBACK DIALOG ==========
class PlaybackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Playback Dialog")
        
        # Add state tracking to prevent restart loops
        self.last_restart_time = 0
        self.restart_cooldown = 1.0  # 1 second cooldown between restarts

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
        self.worker.video_loaded.connect(self.on_video_loaded)
        
        # Connect media controls to player
        self.preview_panel.set_player(self.worker.player)
        self.preview_panel.media_controls.play_pause_clicked.connect(self.toggle_play_pause)
        self.preview_panel.media_controls.volume_changed.connect(self.set_volume)

    def on_ffmpeg_finished(self, success, error_message):
        """Handle FFmpeg completion - hide loading and show errors if any"""
        self.preview_panel.hide_loading()
        if not success and error_message:
            QMessageBox.warning(self, "Preview Error", f"Failed to process video: {error_message}")

    def on_video_loaded(self):
        """Called when video is loaded and ready to play"""
        # Reset controls when new video is loaded
        self.preview_panel.reset_controls()

    def toggle_play_pause(self):
        """Toggle play/pause state of the video with end-of-video restart logic"""
        if self.worker.player:
            current_time = time.time()
            
            state = self.worker.player.get_state()
            position = self.worker.player.get_position()
            
            print(f"[Media Control] Current state: {state}, position: {position:.3f}")
            
            # Check if video has truly ended (be more specific about end detection)
            if state == vlc.State.Ended or (position >= 0.98 and state != vlc.State.Playing):
                # Check cooldown to prevent rapid restarts
                if current_time - self.last_restart_time > self.restart_cooldown:
                    print("[Media Control] Video ended, restarting from beginning")
                    self.worker.player.stop()  # Stop first to clear state
                    self.worker.player.set_position(0.0)
                    self.worker.player.play()
                    self.last_restart_time = current_time
                else:
                    print("[Media Control] Restart cooldown active, ignoring request")
            elif state == vlc.State.Playing:
                # Currently playing, so pause
                self.worker.player.pause()
                print("[Media Control] Video paused")
            else:
                # Not playing (paused, stopped, etc.), so play from current position
                self.worker.player.play()
                print(f"[Media Control] Video resumed from position {position:.3f}")
                
    def set_volume(self, volume):
        """Set player volume (0-100)"""
        if self.worker.player:
            self.worker.player.audio_set_volume(volume)

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
        
        # Add media controls at the bottom
        self.media_controls = MediaControls(self)
        layout.addWidget(self.media_controls)
        
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
        
    def set_player(self, player):
        """Connect the media controls to the VLC player"""
        self.media_controls.set_player(player)
        
    def reset_controls(self):
        """Reset media controls to initial state"""
        self.media_controls.reset()

    def get_video_frame(self):
        return self.video_frame

    def get_win_id(self):
        return int(self.video_frame.winId())
