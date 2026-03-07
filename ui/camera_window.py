# camera_app/ui/camera_window.py

import os
import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QMessageBox,
    QPushButton, QSizePolicy, QLabel, QLineEdit, QDialog, QFrame, QGraphicsDropShadowEffect,
)
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import QTimer, Qt
from ui.camera_widget import CameraWidget
from utils.logging import log
from ui.playbackdialog import PlaybackDialog
from ui.responsive import ScreenScaler
from utils.paths import resource_path


_DIALOG_BG = "#1a1a2e"
_ACCENT = "#4a90d9"
_ACCENT_HOVER = "#5ca0e9"
_ACCENT_PRESSED = "#3a7cc0"
_DANGER = "#C62828"
_CARD_BG = "#252540"
_CARD_HOVER = "#2f2f50"
_TEXT = "#e0e0e0"
_TEXT_MUTED = "#888888"


class _SettingsKeyDialog(QDialog):
    """Styled password dialog for settings access."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings Access")
        self.setWindowFlags(
            Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.setFixedSize(400, 260)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        # --- Heading ---
        heading = QLabel("SETTINGS ACCESS")
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {_ACCENT}; letter-spacing: 2px;"
        )
        root.addWidget(heading)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background-color: {_ACCENT}; margin-top: 10px;")
        root.addWidget(sep)

        root.addSpacing(14)

        desc = QLabel("Enter admin key to access the\nsystem configuration panel.")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(f"font-size: 12px; color: {_TEXT_MUTED};")
        root.addWidget(desc)

        root.addSpacing(16)

        # --- Password field ---
        self._input = QLineEdit()
        self._input.setEchoMode(QLineEdit.Password)
        self._input.setPlaceholderText("Enter settings key")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0d0d1a;
                color: white;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 14px;
                selection-background-color: {_ACCENT};
            }}
            QLineEdit:focus {{
                border: 1px solid {_ACCENT};
            }}
        """)
        self._input.returnPressed.connect(self.accept)
        root.addWidget(self._input)

        root.addSpacing(18)

        # --- Error label (hidden by default) ---
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet(f"font-size: 11px; color: {_DANGER};")
        self._error_label.hide()
        root.addWidget(self._error_label)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                color: {_TEXT};
                padding: 9px 28px;
                border-radius: 6px;
                font-size: 13px;
                border: 1px solid #555;
            }}
            QPushButton:hover {{ background-color: #444; }}
        """)

        unlock_btn = QPushButton("Unlock")
        unlock_btn.setCursor(Qt.PointingHandCursor)
        unlock_btn.clicked.connect(self.accept)
        unlock_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {_ACCENT};
                color: white;
                padding: 9px 28px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{ background-color: {_ACCENT_HOVER}; }}
            QPushButton:pressed {{ background-color: {_ACCENT_PRESSED}; }}
        """)

        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(unlock_btn)
        root.addLayout(btn_row)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {_DIALOG_BG};
                border: 1px solid #333;
            }}
        """)

        self._input.setFocus()

    def get_key(self):
        return self._input.text()

    def show_error(self, msg):
        self._error_label.setText(msg)
        self._error_label.show()
        self._input.clear()
        self._input.setFocus()
        self._input.setStyleSheet(self._input.styleSheet().replace(
            "border: 1px solid #444", f"border: 1px solid {_DANGER}"
        ))


class _SettingsPanel(QDialog):
    """Styled settings panel with action cards."""

    # Signal-like flags so the caller knows which action was picked
    ACTION_CAMERA_COUNT = 1
    ACTION_CAMERA_CONFIG = 2
    ACTION_RECORDING_FOLDER = 3

    def __init__(self, recording_folder=None, parent=None):
        super().__init__(parent)
        self.chosen_action = None
        self.setWindowTitle("Configuration")
        self.setWindowFlags(
            Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.setFixedSize(420, 390)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(0)

        heading = QLabel("CONFIGURATION")
        heading.setAlignment(Qt.AlignCenter)
        heading.setStyleSheet(
            f"font-size: 17px; font-weight: bold; color: {_ACCENT}; letter-spacing: 2px;"
        )
        root.addWidget(heading)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background-color: {_ACCENT}; margin-top: 10px;")
        root.addWidget(sep)

        root.addSpacing(18)

        # --- Action cards ---
        root.addWidget(self._make_card(
            "Change Camera Count",
            "Modify the grid layout (4 - 64 cameras)",
            self.ACTION_CAMERA_COUNT,
        ))

        root.addSpacing(10)

        root.addWidget(self._make_card(
            "Configure Camera",
            "Edit RTSP URLs, names, and recording settings",
            self.ACTION_CAMERA_CONFIG,
        ))

        root.addSpacing(10)

        folder_subtitle = (
            f"Current: {recording_folder}"
            if recording_folder
            else "Not configured \u2014 recording is disabled"
        )
        root.addWidget(self._make_card(
            "Configure Recording Folder",
            folder_subtitle,
            self.ACTION_RECORDING_FOLDER,
        ))

        root.addStretch()

        # --- Close ---
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #333;
                color: {_TEXT};
                padding: 8px 0;
                border-radius: 6px;
                font-size: 13px;
                border: 1px solid #555;
            }}
            QPushButton:hover {{ background-color: #444; }}
        """)
        root.addWidget(close_btn)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {_DIALOG_BG};
                border: 1px solid #333;
            }}
        """)

    def _make_card(self, title, subtitle, action_id):
        card = QPushButton("")
        card.setCursor(Qt.PointingHandCursor)
        card.setFixedHeight(72)
        card.setStyleSheet(f"""
            QPushButton {{
                background-color: {_CARD_BG};
                border: 1px solid #3a3a5a;
                border-radius: 8px;
                text-align: left;
                padding: 14px 18px;
            }}
            QPushButton:hover {{
                background-color: {_CARD_HOVER};
                border: 1px solid {_ACCENT};
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 10, 18, 10)
        card_layout.setSpacing(4)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: white; background: transparent; border: none;"
        )
        lbl_title.setAttribute(Qt.WA_TransparentForMouseEvents)

        lbl_sub = QLabel(subtitle)
        lbl_sub.setStyleSheet(
            f"font-size: 11px; color: {_TEXT_MUTED}; background: transparent; border: none;"
        )
        lbl_sub.setAttribute(Qt.WA_TransparentForMouseEvents)

        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_sub)

        card.clicked.connect(lambda: self._pick(action_id))

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 80))
        card.setGraphicsEffect(shadow)

        return card

    def _pick(self, action_id):
        self.chosen_action = action_id
        self.accept()


class CameraWindow(QMainWindow):
    def __init__(self, title, camera_ids, rows, cols, stream_config, controller=None):
        super().__init__()
        self.setWindowTitle(title)
        _logo = resource_path("assets/logo.png")
        if os.path.exists(_logo):
            self.setWindowIcon(QIcon(_logo))
        scaler = ScreenScaler()
        self.disconnected_cams = set() #this is to keep the track of the cameras that are disconnected

        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_disconnected_cameras)
        self.poll_timer.start(5 * 60 * 1000)  # Every 5 minutes

        self.camera_ids = camera_ids
        self.rows = rows
        self.cols = cols
        self.config_manager = stream_config
        self.stream_config = stream_config
        self.controller = controller

        self.grid_layout = None
        self.focused = False
        self.focused_cam_id = None
        self._streams_cleaned = False
        self._pre_focus_size = None

        self.central_widget = QWidget()
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)
        self.setCentralWidget(self.central_widget)

        if controller:
            nav = QHBoxLayout()

            playback_btn = QPushButton("Playback")
            playback_btn.clicked.connect(self.open_playback_dialog)
            font = playback_btn.font()
            font.setPointSize(scaler.scale(11))
            playback_btn.setFont(font)
            playback_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #555;
                    color: white;
                    padding: {scaler.scale(6)}px {scaler.scale(14)}px;
                    border-radius: {scaler.scale(4)}px;
                }}
                QPushButton:hover {{
                    background-color: #777;
                }}
            """)

            # Settings gear button (password-protected)
            self._settings_btn = QPushButton("\u2699")
            self._settings_btn.setToolTip("Settings")
            self._settings_btn.setCursor(Qt.PointingHandCursor)
            self._settings_btn.clicked.connect(self._open_settings)
            settings_font = self._settings_btn.font()
            settings_font.setPointSize(scaler.scale(16))
            self._settings_btn.setFont(settings_font)
            self._settings_btn.setFixedSize(scaler.scale(38), scaler.scale(38))
            self._settings_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #555;
                    color: white;
                    border-radius: {scaler.scale(4)}px;
                }}
                QPushButton:hover {{
                    background-color: #777;
                }}
            """)

            # Metrics label (left side of navbar — bold and visible)
            self._metrics_label = QLabel("CPU: --  |  RAM: -- GB  |  App: -- MB  |  Rec: -- / -- GB")
            metrics_font = self._metrics_label.font()
            metrics_font.setPointSize(scaler.scale(12))
            metrics_font.setBold(True)
            self._metrics_label.setFont(metrics_font)
            self._metrics_label.setStyleSheet(f"""
                QLabel {{
                    color: #cccccc;
                    padding: 0 {scaler.scale(6)}px;
                }}
            """)

            # Datetime label (center of navbar)
            self._datetime_label = QLabel()
            dt_font = self._datetime_label.font()
            dt_font.setPointSize(scaler.scale(12))
            dt_font.setBold(True)
            self._datetime_label.setFont(dt_font)
            self._datetime_label.setStyleSheet(f"""
                QLabel {{
                    color: #cccccc;
                    padding: 0 {scaler.scale(6)}px;
                }}
            """)
            self._update_datetime()

            # 1-second timer for live clock
            self._dt_timer = QTimer(self)
            self._dt_timer.timeout.connect(self._update_datetime)
            self._dt_timer.start(1000)

            nav.addWidget(self._metrics_label)
            nav.addStretch()
            nav.addWidget(self._datetime_label)
            nav.addSpacing(scaler.scale(10))
            nav.addWidget(playback_btn)
            nav.addWidget(self._settings_btn)
            layout.addLayout(nav)

            # System metrics collector (lightweight, updates every 3 s)
            from utils.metrics import SystemMetrics
            self._metrics = SystemMetrics(
                interval_ms=3000,
                recording_folder=self.controller.config_mgr.get_recording_folder(),
                parent=self,
            )
            self._metrics.updated.connect(self._update_metrics_display)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(2)
        self.grid_layout.setContentsMargins(2, 2, 2, 2)
        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.grid_widget)

        self.camera_widgets = {}

        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)
            stream_cfg = self.stream_config.get_camera_config(cam_id)
            cam_name = stream_cfg.get("name", f"Camera {cam_id}")

            widget = CameraWidget(cam_id, name=cam_name, logo_path=resource_path("assets/logo.png"))
            widget.doubleClicked.connect(self.toggle_focus_view)
            widget.connectionStatusChanged.connect(self.handle_connection_update)#new connnection 
            self.camera_widgets[cam_id] = widget
            self.grid_layout.addWidget(widget, r, c)

        for i in range(rows):
            self.grid_layout.setRowMinimumHeight(i, 100)
            self.grid_layout.setRowStretch(i, 1)
        for i in range(cols):
            self.grid_layout.setColumnMinimumWidth(i, 120)
            self.grid_layout.setColumnStretch(i, 1)

        self.showMaximized()
        self.initialize_streams()

    def poll_disconnected_cameras(self):
        if not self.disconnected_cams:
            log.info("Polling: No disconnected cameras.")
            return

        log.info(f"Polling disconnected cameras: {self.disconnected_cams}")

        for cam_id in list(self.disconnected_cams):
            widget = self.camera_widgets.get(cam_id)
            if widget and not widget.is_streaming:
                stream_cfg = self.stream_config.get_camera_config(cam_id)
                rtsp_url = stream_cfg.get("rtsp", "")
                if rtsp_url:
                    success = widget.start_stream(rtsp_url)
                    if success:
                        log.info(f"Polling reconnect successful for Camera {cam_id}")
                    else:
                        log.warning(f"Polling reconnect failed for Camera {cam_id}")
                        
    def handle_connection_update(self, cam_id, connected):
        if connected:
            if cam_id in self.disconnected_cams:
                self.disconnected_cams.discard(cam_id)
                log.info(f"Camera {cam_id} removed from disconnected set.")
            # Start recorder only AFTER display stream is connected
            # so the recorder doesn't steal the camera's RTSP session
            if self.controller:
                self.controller.start_recording_for_camera(cam_id)
        else:
            if cam_id not in self.disconnected_cams:
                self.disconnected_cams.add(cam_id)
                log.info(f"Camera {cam_id} added to disconnected set.")

            # If this camera is in fullscreen, auto-return to grid
            if self.focused and self.focused_cam_id == cam_id:
                log.info(f"Camera {cam_id} disconnected while in fullscreen — returning to grid.")
                self.toggle_focus_view(cam_id)

        # Update UI title with disconnected count
        disc = len(self.disconnected_cams)
        self.setWindowTitle(f"Camera Viewer ({disc} disconnected)" if disc > 0 else "Camera Viewer")

    def initialize_streams(self):
        log.info(f"Initializing streams for {len(self.camera_widgets)} cameras")
        self._stream_queue = []

        for cam_id, widget in self.camera_widgets.items():
            stream_cfg = self.config_manager.get_camera_config(cam_id)
            rtsp_url = stream_cfg.get("rtsp", "")
            is_enabled = stream_cfg.get("enabled", True)

            widget.configure(rtsp_url, is_enabled)

            if is_enabled and rtsp_url:
                self._stream_queue.append((cam_id, widget, rtsp_url))
            else:
                log.info(f"Camera {cam_id} disabled or no RTSP.")

        # Stagger stream starts to avoid overwhelming network/CPU
        self._start_next_stream()

    def _start_next_stream(self):
        if not self._stream_queue:
            return
        cam_id, widget, rtsp_url = self._stream_queue.pop(0)
        widget.start_stream(rtsp_url)
        log.info(f"Camera {cam_id} stream started.")

        if self._stream_queue:
            # 2s gap per camera
            QTimer.singleShot(2000, self._start_next_stream)

    def toggle_focus_view(self, cam_id):
        if self.focused:
            # ---- EXIT focus ----
            log.info(f"[{self.windowTitle()}] Returning to grid.")

            # Pin the window to its pre-focus size before restoring layout.
            # Without this, restoring column min-widths makes Qt re-expand
            # the window beyond the screen edge.
            if self._pre_focus_size is not None:
                self.setFixedSize(self._pre_focus_size)

            # Show all camera widgets
            for w in self.camera_widgets.values():
                w.show()

            # Restore every row and column to its original constraints
            for i in range(self.rows):
                self.grid_layout.setRowMinimumHeight(i, 100)
                self.grid_layout.setRowStretch(i, 1)
            for i in range(self.cols):
                self.grid_layout.setColumnMinimumWidth(i, 120)
                self.grid_layout.setColumnStretch(i, 1)

            self.focused = False
            self.focused_cam_id = None

            # Release the fixed-size pin so normal resizing works again
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            return

        # ---- ENTER focus (block if disconnected) ----
        widget = self.camera_widgets.get(cam_id)
        if cam_id in self.disconnected_cams or (widget and not widget.is_connected):
            log.info(f"Skipping fullscreen: Camera {cam_id} is disconnected.")
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Connection Error")
            msg_box.setText(f"Can't open Camera {cam_id} due to connection error.")
            msg_box.exec_()
            return

        log.info(f"[{self.windowTitle()}] Focusing Camera {cam_id}.")

        # Save the exact window size before touching the layout
        self._pre_focus_size = self.size()
        # Pin the window so Qt cannot resize it during layout changes
        self.setFixedSize(self._pre_focus_size)

        self.focused = True
        self.focused_cam_id = cam_id

        # Find this camera's row and column in the grid
        idx = self.camera_ids.index(cam_id)
        focused_row, focused_col = divmod(idx, self.cols)

        # Hide every other camera widget
        for cid, w in self.camera_widgets.items():
            if cid != cam_id:
                w.hide()

        # Collapse all rows/columns to zero size and no stretch
        for i in range(self.rows):
            self.grid_layout.setRowMinimumHeight(i, 0)
            self.grid_layout.setRowStretch(i, 0)
        for i in range(self.cols):
            self.grid_layout.setColumnMinimumWidth(i, 0)
            self.grid_layout.setColumnStretch(i, 0)

        # Give all available space to the focused row and column only
        self.grid_layout.setRowMinimumHeight(focused_row, 100)
        self.grid_layout.setRowStretch(focused_row, 1)
        self.grid_layout.setColumnMinimumWidth(focused_col, 120)
        self.grid_layout.setColumnStretch(focused_col, 1)

        # Release the fixed-size pin
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)

    def cleanup_streams(self, blocking=True):
        if self._streams_cleaned:
            return
        self._streams_cleaned = True
        log.info(f"Cleaning up all camera streams (blocking={blocking}).")
        for widget in self.camera_widgets.values():
            widget.stop_stream(blocking=blocking)

    def closeEvent(self, event):
        log.info("Window closing: signaling all streams to stop.")
        self.poll_timer.stop()
        if hasattr(self, '_metrics'):
            self._metrics.stop()
        if hasattr(self, '_dt_timer'):
            self._dt_timer.stop()
        # Non-blocking: just signal threads to stop, don't wait.
        # The process exit will clean up everything.
        self.cleanup_streams(blocking=False)
        log.info("Window closed.")
        event.accept()

    def _open_settings(self):
        expected = self.controller.config_mgr.get_settings_key()

        # --- Step 1: password gate ---
        key_dlg = _SettingsKeyDialog(self)
        while True:
            if key_dlg.exec_() != QDialog.Accepted:
                return
            if key_dlg.get_key() == expected:
                break
            key_dlg.show_error("Invalid key. Please try again.")

        # --- Step 2: settings panel ---
        recording_folder = self.controller.config_mgr.get_recording_folder()
        panel = _SettingsPanel(recording_folder=recording_folder, parent=self)
        if panel.exec_() == QDialog.Accepted:
            if panel.chosen_action == _SettingsPanel.ACTION_CAMERA_COUNT:
                self.controller.change_camera_count()
            elif panel.chosen_action == _SettingsPanel.ACTION_CAMERA_CONFIG:
                self.controller.open_camera_config()
            elif panel.chosen_action == _SettingsPanel.ACTION_RECORDING_FOLDER:
                self.controller.configure_recording_folder()

    def _update_metrics_display(self, data):
        self._metrics_label.setText(
            f"CPU: {data['cpu_percent']:.0f}%  |  "
            f"RAM: {data['mem_total_gb']:.1f} GB  |  "
            f"App: {data['proc_mem_mb']:.0f} MB  |  "
            f"Rec: {data['rec_free_gb']:.1f} / {data['rec_total_gb']:.1f} GB"
        )

    def open_playback_dialog(self):
        recording_folder = None
        if self.controller:
            recording_folder = self.controller.config_mgr.get_recording_folder()
        dialog = PlaybackDialog(recording_folder=recording_folder, parent=self)
        dialog.exec_()

    def _update_datetime(self):
        """Update the live clock label in the navbar."""
        self._datetime_label.setText(
            datetime.datetime.now().strftime("%a, %d %b %Y   %H:%M:%S")
        )

