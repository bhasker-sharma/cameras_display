# camera_app/ui/camera_window.py

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QSizePolicy
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from ui.camera_widget import CameraWidget
from utils.logging import log

class CameraWindow(QMainWindow):
    def __init__(self, title, camera_ids, rows, cols, stream_config, controller=None):
        super().__init__()
        self.setWindowTitle(title)
        if os.path.exists("assets/logo.png"):
            self.setWindowIcon(QIcon("assets/logo.png"))

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

            # refresh_btn = QPushButton("Refresh System")
            # refresh_btn.clicked.connect(self.controller.refresh_configurations)

            change_btn = QPushButton("Change Camera Count")
            change_btn.clicked.connect(self.controller.change_camera_count)

            config_btn = QPushButton("Configure Camera")
            config_btn.clicked.connect(self.controller.open_camera_config)

            # for btn in (refresh_btn ,chnage_btn, config_btn):
            for btn in (change_btn, config_btn):
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #555;
                        color: white;
                        padding: 6px 14px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #777;
                    }
                """)

            # nav.addWidget(refresh_btn)
            nav.addStretch()
            nav.addWidget(change_btn)
            nav.addWidget(config_btn)
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

    def refresh_widgets(self):
        for cam_id, widget in self.camera_widgets.items():
            stream_cfg = self.stream_config.get_camera_config(cam_id)
            cam_name = stream_cfg.get("name", f"Camera {cam_id}")
            rtsp_url = stream_cfg.get("rtsp", "")
            is_enabled = stream_cfg.get("enabled", True)

            widget.update_name(cam_name)
            widget.configure(rtsp_url, is_enabled)

            if widget.is_streaming:
                if not is_enabled or not rtsp_url:
                    widget.stop_stream()
            elif is_enabled and rtsp_url:
                widget.start_stream(rtsp_url)

        # Refresh focused widget too
        if self.focused and hasattr(self, 'focused_widget'):
            stream_cfg = self.stream_config.get_camera_config(self.focused_cam_id)
            cam_name = stream_cfg.get("name", f"Camera {self.focused_cam_id}")
            rtsp_url = stream_cfg.get("rtsp", "")
            is_enabled = stream_cfg.get("enabled", True)

            self.focused_widget.update_name(cam_name)
            self.focused_widget.configure(rtsp_url, is_enabled)

            if self.focused_widget.is_streaming:
                if not is_enabled or not rtsp_url:
                    self.focused_widget.stop_stream()
            elif is_enabled and rtsp_url:
                self.focused_widget.start_stream(rtsp_url)

    def cleanup_streams(self):
        log.info(f"Cleaning up all camera streams.")
        for widget in self.camera_widgets.values():
            widget.stop_stream()
        if hasattr(self, 'focused_widget') and self.focused_widget:
            self.focused_widget.stop_stream()

    def closeEvent(self, event):
        self.cleanup_streams()
        super().closeEvent(event)
