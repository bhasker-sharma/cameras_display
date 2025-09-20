# camera_app/ui/camera_window.py

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,QMessageBox,
    QPushButton, QSizePolicy
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer
from ui.camera_widget import CameraWidget
from utils.logging import log
from core.camera_playback_worker import PlaybackDialog
from ui.responsive import ScreenScaler


class CameraWindow(QMainWindow):
    def __init__(self, title, camera_ids, rows, cols, stream_config, controller=None):
        super().__init__()
        self.setWindowTitle(title)
        if os.path.exists("assets/logo.png"):
            self.setWindowIcon(QIcon("assets/logo.png"))
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

        self.central_widget = QWidget()
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)
        self.setCentralWidget(self.central_widget)

        if controller:
            nav = QHBoxLayout()

            change_btn = QPushButton("Change Camera Count")
            change_btn.clicked.connect(self.controller.change_camera_count)

            config_btn = QPushButton("Configure Camera")
            config_btn.clicked.connect(self.controller.open_camera_config)

            playback_btn = QPushButton("Playback")
            playback_btn.clicked.connect(self.open_playback_dialog)

            # for btn in (refresh_btn ,chnage_btn, config_btn):
            for btn in (change_btn, config_btn, playback_btn):
                font = btn.font()
                font.setPointSize(scaler.scale(11))
                btn.setFont(font)

                btn.setStyleSheet(f"""
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

            # nav.addWidget(refresh_btn)
            nav.addStretch()
            nav.addWidget(change_btn)
            nav.addWidget(config_btn)
            nav.addWidget(playback_btn)
            layout.addLayout(nav)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.grid_widget)

        self.camera_widgets = {}

        for idx, cam_id in enumerate(camera_ids):
            r, c = divmod(idx, cols)
            stream_cfg = self.stream_config.get_camera_config(cam_id)
            cam_name = stream_cfg.get("name", f"Camera {cam_id}")

            widget = CameraWidget(cam_id, name=cam_name)
            widget.doubleClicked.connect(self.toggle_focus_view)
            widget.connectionStatusChanged.connect(self.handle_connection_update)#new connnection 
            self.camera_widgets[cam_id] = widget
            self.grid_layout.addWidget(widget, r, c)

        for i in range(rows):
            self.grid_layout.setRowMinimumHeight(i, 180)
            self.grid_layout.setRowStretch(i, 1)
        for i in range(cols):
            self.grid_layout.setColumnMinimumWidth(i, 240)
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
        else:
            if cam_id not in self.disconnected_cams:
                self.disconnected_cams.add(cam_id)
                log.info(f"Camera {cam_id} added to disconnected set.")

        # Optional: Update UI title or log current count
        self.setWindowTitle(f"Camera Viewer ({len(self.disconnected_cams)} disconnected)")

    def initialize_streams(self):
        log.info(f"Initializing streams for {len(self.camera_widgets)} cameras")
        for cam_id, widget in self.camera_widgets.items():
            stream_cfg = self.config_manager.get_camera_config(cam_id)
            rtsp_url = stream_cfg.get("rtsp", "")
            is_enabled = stream_cfg.get("enabled", True)

            widget.configure(rtsp_url, is_enabled)

            if is_enabled and rtsp_url:
                widget.start_stream(rtsp_url)
                log.info(f"Camera {cam_id} stream started.")
            else:
                log.info(f"Camera {cam_id} disabled or no RTSP.")

    def toggle_focus_view(self, cam_id):
        widget = self.camera_widgets.get(cam_id)
        if cam_id in self.disconnected_cams or (widget and not widget.is_connected):
            log.info(f"Skipping fullscreen: Camera {cam_id} is disconnected.")
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Connection Error")
            msg_box.setText(f"Can't open Camera {cam_id} due to connection error.")
            msg_box.exec_()
            return

        if not self.focused:
            log.info(f"[{self.windowTitle()}] Focusing Camera {cam_id}.")
            self.focused = True
            self.focused_cam_id = cam_id

            self.grid_widget.hide()

            stream_cfg = self.stream_config.get_camera_config(cam_id)
            cam_name = stream_cfg.get("name", f"Camera {cam_id}")
            rtsp_url = stream_cfg.get("rtsp", "")
            is_enabled = stream_cfg.get("enabled", True)

            self.focused_widget = CameraWidget(cam_id, name=cam_name)
            self.focused_widget.doubleClicked.connect(self.toggle_focus_view)
            self.centralWidget().layout().addWidget(self.focused_widget)
            self.focused_widget.configure(rtsp_url, is_enabled)

            if is_enabled and rtsp_url:
                self.focused_widget.start_stream(rtsp_url)
        else:
            log.info(f"[{self.windowTitle()}] Returning to grid.")
            self.focused = False
            if hasattr(self, "focused_widget"):
                self.focused_widget.stop_stream()
                self.centralWidget().layout().removeWidget(self.focused_widget)
                self.focused_widget.deleteLater()
                self.focused_widget = None
            self.focused_cam_id = None
            self.grid_widget.show()

    def cleanup_streams(self):
        log.info(f"Cleaning up all camera streams.")
        for widget in self.camera_widgets.values():
            widget.stop_stream()
        if hasattr(self, 'focused_widget') and self.focused_widget:
            self.focused_widget.stop_stream()

    def closeEvent(self, event):
        log.info("Shutting down: cleaning up all streams.")
        self.cleanup_streams()
        log.info("Exiting application.")
        event.accept()

    def open_playback_dialog(self):
        dialog = PlaybackDialog(parent =self)
        dialog.exec_()